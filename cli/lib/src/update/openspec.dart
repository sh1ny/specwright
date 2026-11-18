import 'dart:io';

import '../process/command_line.dart' show UnsafeBatchArgument;
import '../process/launch.dart';
import 'text.dart';

/// What one `openspec` run of `sw update` ended in: the exit code and the
/// text of both streams.
class OpenspecResult {
  const OpenspecResult(this.code, this.stdout, this.stderr);

  /// 127 when the CLI is not on `PATH` (or did not start), 124 after a
  /// timeout.
  final int code;
  final String stdout;
  final String stderr;
}

/// Runs `openspec` with [args] in [cwd], giving up after [timeout] when one
/// is set. The seam every `openspec` call of `sw update` goes through, so a
/// test can replace it.
typedef OpenspecRunner = Future<OpenspecResult> Function(
  List<String> args,
  String cwd, {
  Duration? timeout,
});

/// One `openspec` run, started through `launch()` with no shell and
/// `OPENSPEC_TELEMETRY=0` on top of [environment] (default: this process's).
/// The output of both streams is read in full, as `update.sh` did; a
/// [timeout] ends the tool and gives exit 124.
Future<OpenspecResult> runOpenspec(
  List<String> args,
  String cwd, {
  Duration? timeout,
  Map<String, String>? environment,
}) async {
  final env = {
    ...(environment ?? Platform.environment),
    'OPENSPEC_TELEMETRY': '0',
  };
  final LaunchResult result;
  try {
    result = await launch(
      ['openspec', ...args],
      cwd: cwd,
      environment: env,
      deadline: timeout,
    );
  } on Unrepresentable catch (e) {
    return OpenspecResult(127, '', 'cannot start openspec: $e');
  } on UnsafeBatchArgument catch (e) {
    return OpenspecResult(127, '', 'cannot start openspec: $e');
  }
  if (result.timedOut) {
    return OpenspecResult(
      124,
      '',
      'openspec ${args.join(' ')} did not finish in ${timeout?.inSeconds} s',
    );
  }
  final err = decodeLossy(result.stderr);
  if (result.startFailed) {
    return OpenspecResult(
      127,
      '',
      err.contains('command not found')
          ? 'the openspec CLI is not on PATH'
          : pyStrip(err),
    );
  }
  return OpenspecResult(result.exitCode, decodeLossy(result.stdout), err);
}
