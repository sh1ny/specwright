import 'dart:io';

import '../release/commands.dart';
import '../vcs/args.dart';
import '../vcs/document.dart' show documentBytes;
import '../vcs/stop.dart';
import 'vcs.dart' show readAllStdin;

const String _handoffUsage =
    'usage: sw release --args-stdin (stdin: scripts dir, bash path, subcommand and arguments, each record ending in a NUL byte)';

/// `sw release [--dir <repo>] <sub> [options]`: runs one release subcommand
/// from plain arguments in the current directory, writes exactly one JSON
/// document and returns its status (0 done, 1 a stop, 2 usage, 3 a git or
/// network call failed).
///
/// `sw release --args-stdin` is the handoff of the `release.sh` shim: stdin
/// holds the script directory, its bash path and the original arguments as
/// NUL-terminated records, and the run is the same as the plain call with
/// those arguments.
Future<int> runReleaseCommand(
  List<String> args, {
  required void Function(List<int> bytes) writeOut,
  Future<List<int>> Function()? readStdin,
}) async {
  var argv = args;
  if (args.length == 1 && args.single == '--args-stdin') {
    try {
      var stdin = await (readStdin ?? readAllStdin)();
      // no original arguments: the shim sent two records; the third is empty
      if (stdin.isNotEmpty &&
          stdin.last == 0 &&
          stdin.where((byte) => byte == 0).length == 2) {
        stdin = [...stdin, 0];
      }
      argv = parseHandoff(stdin, _handoffUsage).argv;
    } on VcsStop catch (stop) {
      writeOut(documentBytes(stop.object()));
      return stop.code;
    } on Object catch (error) {
      final refusal = VcsStop.refusal(error);
      if (refusal is! VcsStop) rethrow;
      writeOut(documentBytes(refusal.object()));
      return refusal.code;
    }
  }
  final outcome = await releaseOutcome(argv, cwd: Directory.current.path);
  writeOut(documentBytes(outcome.document));
  return outcome.code;
}
