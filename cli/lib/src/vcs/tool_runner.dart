import 'dart:async';
import 'dart:io';
import 'dart:typed_data';

import 'codec.dart';
import 'stop.dart';

/// Shell text put in front of `exec "$@"` in the transported `bash -c`.
///
/// It reads the working directory record, then the argument count (decimal
/// digits, NUL-terminated) and exactly that many NUL-terminated records, one
/// `read -r -d ''` at a time into the positional list, and leaves the rest of
/// stdin unread for the exec'd tool. A missing directory record, a count that
/// is not decimal digits (or is zero, or is longer than nine digits) and fewer
/// records than the count exit 126 before any tool runs. No argument value is
/// reserved. Last it enters the directory with `CDPATH= cd -- "$dir"` (an
/// empty `CDPATH` for `cd` only, so a drive-form path is never searched
/// through it, and nothing is printed); a directory that vanished exits 127,
/// silently.
///
/// The records are read with `LC_ALL=C`, and `LC_ALL` is restored (or unset)
/// before the tool runs: in a UTF-8 locale bash's `read` takes a lead byte at
/// the end of a record (`\xe9` then NUL) as the start of a character and
/// swallows the NUL that ends the record.
const String vcsPrelude =
    r'''__lcs=${LC_ALL+x}; __lc=${LC_ALL-}; LC_ALL=C; __d=; IFS= read -r -d '' __d || { echo "vcs: argument transport failed" >&2; exit 126; }; __c=; IFS= read -r -d '' __c || __c=x; case $__c in ''|*[!0-9]*|0*) echo "vcs: argument transport failed" >&2; exit 126;; esac; [ "${#__c}" -le 9 ] || { echo "vcs: argument transport failed" >&2; exit 126; }; set --; __i=0; while [ "$__i" -lt "$__c" ]; do IFS= read -r -d '' __a || { echo "vcs: argument transport failed" >&2; exit 126; }; set -- "$@" "$__a"; __i=$((__i+1)); done; if [ -n "$__lcs" ]; then LC_ALL=$__lc; else unset LC_ALL; fi; CDPATH= cd -- "$__d" >/dev/null 2>&1 || exit 127; unset __d __c __i __a __lc __lcs''';

/// What a tool run produced: the exit code and the raw output bytes. Decoding
/// is the caller's choice (see codec.dart).
class ToolResult {
  ToolResult(
    this.exitCode,
    this.stdout,
    this.stderr, {
    this.outputTooLarge = false,
  });

  final int exitCode;
  final Uint8List stdout;
  final Uint8List stderr;

  /// Only [runToolCapped]: stdout went past the cap and the child was killed.
  final bool outputTooLarge;
}

/// `bash` could not be started (the capped runner's `tool_missing` case).
class ToolStartException implements Exception {
  ToolStartException(this.message);

  final String message;

  @override
  String toString() => message;
}

/// The working directory as the transport's first record: absolute, and on
/// Windows in its drive form with `/` separators (`C:/Users/x`).
String cwdRecord(String cwd, {bool? windows}) =>
    (windows ?? Platform.isWindows) ? cwd.replaceAll(r'\', '/') : cwd;

/// The argument records: the count of [command] entries in decimal, then each
/// entry, every record followed by a NUL. Encoded with surrogateescape
/// ([encodeEscaped]).
Uint8List frameArguments(List<String> command) {
  final out = BytesBuilder(copy: false);
  _record(out, '${command.length}');
  for (final c in command) {
    _record(out, c);
  }
  return out.takeBytes();
}

/// Everything the child reads ahead of any tool input: the working directory
/// record ([cwdRecord]), then [frameArguments].
Uint8List frameCommand(String cwd, List<String> command) {
  final out = BytesBuilder(copy: false)
    ..add(_recordBytes(cwdRecord(cwd)))
    ..add(frameArguments(command));
  return out.takeBytes();
}

void _record(BytesBuilder out, String text) => out.add(_recordBytes(text));

Uint8List _recordBytes(String text) {
  final bytes = encodeEscaped(text);
  if (bytes.contains(0)) {
    throw ArgumentError('a transported record cannot hold a NUL byte');
  }
  return Uint8List.fromList([...bytes, 0]);
}

/// Python's `repr()` of a `str` (see [_pyRepr]); `%r` in `vcs.sh` messages.
String pyRepr(String s) => _pyRepr(s);

/// Python's `repr()` of a `str`: single quotes unless the text holds `'` and
/// no `"`; backslash, the quote, newline, return, tab and other controls
/// escaped; a lone surrogate as a `u` escape.
String _pyRepr(String s) {
  const bs = r'\';
  final quote = s.contains("'") && !s.contains('"') ? '"' : "'";
  final out = StringBuffer(quote);
  final units = s.codeUnits;
  for (var i = 0; i < units.length; i++) {
    final u = units[i];
    if (u == 0x5c) {
      out.write('$bs$bs');
    } else if (String.fromCharCode(u) == quote) {
      out.write('$bs$quote');
    } else if (u == 0x0a) {
      out.write('${bs}n');
    } else if (u == 0x0d) {
      out.write('${bs}r');
    } else if (u == 0x09) {
      out.write('${bs}t');
    } else if (u < 0x20 || u == 0x7f) {
      out.write('${bs}x${u.toRadixString(16).padLeft(2, '0')}');
    } else if (u >= 0xd800 && u <= 0xdbff) {
      final next = i + 1 < units.length ? units[i + 1] : 0;
      if (next >= 0xdc00 && next <= 0xdfff) {
        out
          ..writeCharCode(u)
          ..writeCharCode(next);
        i++;
      } else {
        out.write('${bs}u${u.toRadixString(16)}');
      }
    } else if (u >= 0xdc00 && u <= 0xdfff) {
      out.write('${bs}u${u.toRadixString(16)}');
    } else {
      out.writeCharCode(u);
    }
  }
  return (out..write(quote)).toString();
}

/// What Python's `str(OSError)` says when `Popen` is given a `cwd` that does
/// not name a directory: POSIX `[Errno 2] No such file or directory: '<dir>'`
/// (`[Errno 20] Not a directory` for a file), Windows `[WinError 267] The
/// directory name is invalid`.
String missingDirectoryText(String cwd, {bool? windows, bool isFile = false}) {
  if (windows ?? Platform.isWindows) {
    return '[WinError 267] The directory name is invalid';
  }
  return isFile
      ? '[Errno 20] Not a directory: ${_pyRepr(cwd)}'
      : '[Errno 2] No such file or directory: ${_pyRepr(cwd)}';
}

/// Null when [cwd] is a directory, else the [missingDirectoryText].
String? _cwdProblem(String cwd) {
  try {
    final raw = encodeEscaped(cwdRecord(cwd));
    if (Directory.fromRawPath(raw).existsSync()) return null;
    return missingDirectoryText(
      cwd,
      isFile: File.fromRawPath(raw).existsSync(),
    );
  } on FormatException {
    return missingDirectoryText(cwd);
  }
}

/// Runs `command` (tool name first) in [cwd] through the transported
/// `bash -c`, as `vcs.sh` does, and returns its exit code and raw output.
/// [cwd] is absolute (on Windows the drive form). [input], if any, is written
/// after the argument records, then stdin is closed. The environment is the
/// parent's, or [environment] when non-empty. When [cwd] is not a directory no
/// process starts: exit 127, empty stdout and [missingDirectoryText] on stderr,
/// as `vcs.sh` returned for a failed `Popen`. A `bash` that cannot start gives
/// exit 127 and the error text on stderr.
///
/// Constraint C2: there is no deadline and no byte bound, matching `vcs.sh`,
/// whose only bound is `but`'s output cap ([runToolCapped]). Adding bounds is
/// a behaviour change for its own change.
///
/// Constraint C3: tools never receive arguments through Dart's process
/// argument encoding. On Windows MSYS brace- and glob-expands unquoted
/// arguments, and on POSIX escaped bytes would be lost. Arguments and tool
/// input go only through this count-framed transport, which, unlike `sw run`'s,
/// leaves the bytes after the last argument record on stdin for the tool. The
/// working directory travels in the transport too, as its first record:
/// `Process.start`'s `workingDirectory` is a `String` and is never set.
Future<ToolResult> runTool(
  String bash,
  String cwd,
  List<String> command, {
  List<int>? input,
  Map<String, String>? environment,
}) async {
  final problem = _cwdProblem(cwd);
  if (problem != null) {
    return ToolResult(127, Uint8List(0), encodeEscaped(problem));
  }
  try {
    return await runFramed(bash, [
      ...frameCommand(cwd, command),
      ...?input,
    ], environment: environment);
  } on ToolStartException catch (e) {
    return ToolResult(127, Uint8List(0), encodeEscaped(e.message));
  }
}

/// [runTool] for `but`: no input, and once stdout holds more than [cap] bytes
/// the child is killed and [ToolResult.outputTooLarge] is set (`but_run`'s
/// `but_output_too_large`). A missing [cwd] or a `bash` that cannot start is
/// the `tool_missing` [VcsStop], `<tool> could not run: <text>`.
Future<ToolResult> runToolCapped(
  String bash,
  String cwd,
  List<String> command, {
  required int cap,
  Map<String, String>? environment,
}) async {
  final tool = command.first;
  final problem = _cwdProblem(cwd);
  if (problem != null) {
    throw VcsStop('tool_missing', '$tool could not run: $problem');
  }
  try {
    return await runFramed(
      bash,
      frameCommand(cwd, command),
      cap: cap,
      environment: environment,
    );
  } on ToolStartException catch (e) {
    throw VcsStop('tool_missing', '$tool could not run: ${e.message}');
  }
}

/// Starts the transported `bash` with [stdinBytes] exactly as given (the
/// directory record included). It is public so tests can send a bad count or
/// a short read. A start failure is a [ToolStartException].
///
/// Constraint C7: external tools still start through the framed bash transport
/// (`runFramed` with `vcsPrelude`), and fenced commands through the inherited
/// bash fence prelude (`exec_inherit.dart`, `fencedPrelude`); both stay until
/// `native-cli-launcher` replaces them.
Future<ToolResult> runFramed(
  String bash,
  List<int> stdinBytes, {
  int? cap,
  Map<String, String>? environment,
}) async {
  final Process process;
  try {
    process = await Process.start(
      bash,
      ['-c', '$vcsPrelude; exec "\$@"', 'vcs'],
      environment: environment,
      includeParentEnvironment: environment == null || environment.isEmpty,
    );
  } on ProcessException catch (e) {
    throw ToolStartException(e.toString());
  }

  final out = BytesBuilder(copy: false);
  final err = BytesBuilder(copy: false);
  final outDone = Completer<void>();
  final errDone = Completer<void>();
  var tooLarge = false;
  late final StreamSubscription<List<int>> outSub;
  outSub = process.stdout.listen(
    (chunk) {
      if (tooLarge) return;
      out.add(chunk);
      if (cap != null && out.length > cap) {
        tooLarge = true;
        outSub.cancel();
        process.kill(ProcessSignal.sigkill);
        if (!outDone.isCompleted) outDone.complete();
      }
    },
    onDone: () {
      if (!outDone.isCompleted) outDone.complete();
    },
    onError: (Object _) {
      if (!outDone.isCompleted) outDone.complete();
    },
    cancelOnError: true,
  );
  final errSub = process.stderr.listen(
    err.add,
    onDone: () {
      if (!errDone.isCompleted) errDone.complete();
    },
    onError: (Object _) {
      if (!errDone.isCompleted) errDone.complete();
    },
    cancelOnError: true,
  );

  // The tool may exit without reading its input; that is not an error here.
  unawaited(process.stdin.done.catchError((Object _) {}));
  try {
    process.stdin.add(stdinBytes);
    await process.stdin.close();
  } on Object {
    // Broken pipe: the tool is gone or never read; its exit code says so.
  }

  await outDone.future;
  final code = await process.exitCode;
  if (tooLarge) {
    await errSub.cancel();
  } else {
    await errDone.future;
  }
  return ToolResult(
    code,
    out.takeBytes(),
    err.takeBytes(),
    outputTooLarge: tooLarge,
  );
}
