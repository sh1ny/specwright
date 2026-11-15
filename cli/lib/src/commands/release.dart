import 'dart:io';

import '../commit/paths.dart';
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
      final handoff = parseHandoff(stdin, _handoffUsage);
      argv = await nativeReleaseArgs(handoff.argv, handoff.bash);
    } on BadPathException catch (e) {
      writeOut(
        documentBytes(VcsStop('bad_path', e.toString(), code: 2).object()),
      );
      return 2;
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

/// The options whose value is a path: `--dir` (leading), `--store` and
/// `--proposal`.
const _pathOptions = {'--dir', '--store', '--proposal'};

/// The options that take a value that is not a path.
const _valueOptions = {
  '--main',
  '--branch',
  '--to',
  '--version',
  '--base',
  '--store-main',
  '--store-prefix',
};

/// [argv] with each path option's value converted by [nativePath]: the stdin
/// handoff skips Git Bash's own conversion, so on Windows `/c/x` would
/// otherwise reach `sw` as written. [windows] and [environment] are test
/// seams; an unconvertible path throws [BadPathException].
Future<List<String>> nativeReleaseArgs(
  List<String> argv,
  String bash, {
  bool? windows,
  Map<String, String>? environment,
}) async {
  final out = [...argv];
  var i = 0;
  while (i < out.length) {
    final t = out[i];
    if (i + 1 < out.length && _pathOptions.contains(t)) {
      out[i + 1] = await nativePath(
        out[i + 1],
        bash,
        windows: windows,
        environment: environment,
      );
      i += 2;
    } else if (_valueOptions.contains(t)) {
      i += 2;
    } else {
      i++;
    }
  }
  return out;
}
