import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import '../vcs/codec.dart';
import 'context.dart';
import '../vcs/tool_runner.dart';
import 'paths.dart';

const int _limit = 72;

/// Entry point of `sw commit fit-subject`: [fitSubject] with an unexpected
/// exception turned into one stderr line and exit 2.
Future<int> runFitSubject(List<String> args, CommitContext ctx) async {
  try {
    return await fitSubject(args, ctx);
  } on Object catch (e) {
    final text = '$e'.replaceAll(RegExp(r'\s+'), ' ');
    return _fail(ctx, 'fit-subject.sh: unexpected failure: $text', 2);
  }
}

/// fit-subject rewrites the message file only through a sibling temporary file
/// and a rename, and leaves it untouched on every non-zero exit.
///
/// Keeps the contract of `fit-subject.sh` (design D5, D9): the one argument is
/// the message file; line 1 (up to the first `\n`, one trailing CR stripped)
/// must start with `<word>: task X.Y ` or `<word>: group N ` (ASCII digits).
/// When it is longer than 72 characters (bytes outside 0x80-0xBF), it is cut
/// at a 0x20 byte to the longest run that fits, trailing spaces removed. The
/// work is on bytes: the CR, every byte from the first `\n` on and any invalid
/// UTF-8 are kept. Prints the final subject and `\n`. Exit 0 fitted or already
/// fitting, 1 no word fits, 2 anything else; the stderr texts are the
/// script's. [windows] and [environment] are test seams for [nativePath].
Future<int> fitSubject(
  List<String> args,
  CommitContext ctx, {
  bool? windows,
  Map<String, String>? environment,
}) async {
  final arg = args.isEmpty ? '' : args.first;
  final String path;
  try {
    path = await nativePath(
      arg,
      ctx.bash,
      windows: windows,
      environment: environment,
    );
  } on BadPathException {
    return _fail(ctx, 'fit-subject.sh: could not convert path: $arg', 2);
  }
  final file = arg.isEmpty ? null : File.fromRawPath(encodeEscaped(path));
  if (file == null || !file.existsSync()) {
    return _fail(ctx, "fit-subject.sh: no message file: '$arg'", 2);
  }

  final content = await file.readAsBytes();
  var nl = content.indexOf(0x0a);
  final hasNewline = nl >= 0;
  if (!hasNewline) nl = content.length;
  var lineEnd = nl;
  var cr = false;
  if (lineEnd > 0 && content[lineEnd - 1] == 0x0d) {
    cr = true;
    lineEnd--;
  }
  final line = Uint8List.sublistView(content, 0, lineEnd);

  final prefixLength = _prefixLength(line);
  if (prefixLength == null) {
    return _failBytes(ctx, [
      ...utf8.encode(
        "fit-subject.sh: line 1 is not '<type>(<scope>): task X.Y <task "
        "text>' or '<type>(<scope>): group N <group heading>': ",
      ),
      ...line,
      0x0a,
    ], 2);
  }

  Uint8List? fitted;
  if (_chars(line, line.length) <= _limit) {
    fitted = line;
  } else {
    for (var cut = line.length - 1; cut >= prefixLength; cut--) {
      if (line[cut] != 0x20) continue;
      var end = cut;
      while (end > 0 && line[end - 1] == 0x20) {
        end--;
      }
      if (end < prefixLength) break;
      if (_chars(line, end) <= _limit) {
        fitted = Uint8List.sublistView(line, 0, end);
        break;
      }
    }
  }
  if (fitted == null) {
    return _failBytes(ctx, [
      ...utf8.encode(
        'fit-subject.sh: no word of the task or group text fits in $_limit '
        'characters: ',
      ),
      ...line,
      0x0a,
    ], 1);
  }

  if (fitted.length != line.length) {
    final tmpPath = '$path.fit.$pid';
    final tmp = File.fromRawPath(encodeEscaped(tmpPath));
    try {
      final out = BytesBuilder(copy: false)
        ..add(fitted)
        ..add(cr ? const [0x0d] : const [])
        ..add(Uint8List.sublistView(content, nl));
      await tmp.writeAsBytes(out.takeBytes(), flush: true);
      // `File.rename` takes a decoded String, which loses a name's bytes that
      // are not UTF-8 (POSIX). `mv` through the transport gets them exactly,
      // as the script's own `mv -f` did.
      final moved = await runTool(ctx.bash, '.', [
        'mv',
        '-f',
        '--',
        tmpPath,
        path,
      ]);
      if (moved.exitCode != 0) throw FileSystemException('mv failed', tmpPath);
    } on Object {
      try {
        if (tmp.existsSync()) await tmp.delete();
      } on Object {
        // A directory or a locked file in the way: nothing more to remove.
      }
      return _fail(ctx, 'fit-subject.sh: could not rewrite $arg', 2);
    }
  }
  ctx.writeOut([...fitted, 0x0a]);
  return 0;
}

/// Length of the `<word>: task X.Y ` or `<word>: group N ` prefix of [line]
/// (matched on bytes, ASCII digits only), or null.
int? _prefixLength(List<int> line) {
  final text = String.fromCharCodes(line);
  final m = _taskPrefix.matchAsPrefix(text) ?? _groupPrefix.matchAsPrefix(text);
  return m?.end;
}

final RegExp _taskPrefix = RegExp(r'[^ ]+: task [0-9]+\.[0-9]+ ');
final RegExp _groupPrefix = RegExp(r'[^ ]+: group [0-9]+ ');

/// UTF-8 characters in the first [end] bytes: those outside 0x80-0xBF.
int _chars(List<int> bytes, int end) {
  var n = 0;
  for (var i = 0; i < end; i++) {
    if (bytes[i] < 0x80 || bytes[i] > 0xbf) n++;
  }
  return n;
}

int _fail(CommitContext ctx, String message, int code) =>
    _failBytes(ctx, [...utf8.encode(message), 0x0a], code);

int _failBytes(CommitContext ctx, List<int> message, int code) {
  ctx.writeErr(message);
  return code;
}
