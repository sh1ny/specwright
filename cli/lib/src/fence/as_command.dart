import 'dart:io';
import 'dart:typed_data';

import '../pr/gh.dart';
import '../vcs/codec.dart';
import '../vcs/tool_runner.dart';
import 'exec_inherit.dart';
import 'fence.dart';

const String asUsage = 'usage: sw as --args-file <path>';

/// `sw as --args-file <path>`: the handoff of the `as.sh` shim and nothing
/// else on [args] (anything else is a usage stop, exit 2, before any lookup).
/// The file holds NUL-terminated records: the scripts directory, the bash, then
/// every argument of `as.sh`. It is read whole and deleted first, so a failed
/// parse leaves nothing behind and the fenced command keeps the caller's stdin
/// (ADR 0029). A file that cannot be read or deleted is exit 3 with
/// `as.sh: handoff: <reason>`; fewer than two records, or a last byte that is
/// not NUL, is exit 3 with `as.sh: handoff: malformed`. Exactly the two header
/// records is `as.sh` called with no argument: its usage line, exit 1.
///
/// [gh], [git] and [launch] are the seams the tests replace; by default they
/// run the bounded gh lookups, the fence's plain git reads, and the command
/// under [runFenced].
Future<int> runAsCommand(
  List<String> args, {
  required void Function(List<int> bytes) writeOut,
  required void Function(List<int> bytes) writeErr,
  Map<String, String>? environment,
  GhCall? gh,
  GitCall? git,
  Launch? launch,
  List<String>? helperCommand,
}) async {
  void err(String text) => writeErr(encodeEscaped(text));
  if (args.length != 2 || args.first != '--args-file') {
    err('$asUsage\n');
    return 2;
  }
  final records = _readHandoff(args[1], err);
  if (records == null) return 3;
  if (records.length < 2) {
    err('as.sh: handoff: malformed\n');
    return 3;
  }
  final bash = records[1];
  final env = environment ?? Map<String, String>.of(Platform.environment);
  return runFence(
    records.sublist(2),
    environment: env,
    gh:
        gh ??
        (ghArgs, e) => runGh(
          bash,
          '.',
          ghArgs,
          environment: e,
          helperCommand: helperCommand,
        ),
    git:
        git ??
        (command, e) async {
          final r = await runTool('.', command, environment: e);
          return r;
        },
    launch: launch ?? (command, e) => runFenced(bash, command, e),
    out: (text) => writeOut(encodeEscaped(text)),
    err: err,
  );
}

/// The records of the handoff file at [path], which is deleted; null after the
/// reason was written when it could not be read or deleted.
List<String>? _readHandoff(String path, void Function(String text) err) {
  final Uint8List bytes;
  try {
    final file = File(path);
    bytes = file.readAsBytesSync();
    file.deleteSync();
  } on FileSystemException catch (e) {
    err('as.sh: handoff: ${e.osError?.message ?? e.message}\n');
    return null;
  }
  if (bytes.isNotEmpty && bytes.last != 0) {
    err('as.sh: handoff: malformed\n');
    return null;
  }
  final records = <String>[];
  var start = 0;
  for (var i = 0; i < bytes.length; i++) {
    if (bytes[i] == 0) {
      records.add(decodeEscaped(Uint8List.sublistView(bytes, start, i)));
      start = i + 1;
    }
  }
  return records;
}
