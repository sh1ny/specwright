import 'dart:io';
import 'dart:typed_data';

import '../process/bounded_run.dart';
import '../process/limit_line.dart';
import '../process/limits.dart';
import '../process/platform_tree.dart';
import '../vcs/codec.dart';
import '../vcs/tool_runner.dart';

/// What one bounded `gh` (or `sw pr reviewers`) call ended in. Without a [limit],
/// the output and [exitCode] are the command's own; a call that could not
/// start is exit 127 with the reason on [stderr].
class GhResult {
  GhResult({
    required this.exitCode,
    this.limit,
    this.limitLine,
    required this.stdout,
    required this.stderr,
  });

  final int exitCode;

  /// The limit that ended the call, if one did.
  final BoundedLimit? limit;

  /// `bounded: <limit>: <command> <first argument>\n` when [limit] is set.
  final String? limitLine;
  final Uint8List stdout;
  final Uint8List stderr;
}

/// [vcsPrelude] with the `bounded:` message prefix `sw run --bounded` printed.
final String boundedPrelude = vcsPrelude.replaceAll(
  'vcs: argument transport failed',
  'bounded: argument transport failed',
);

/// Runs `gh <args>` in [cwd] under the bounded helper: a deadline, a byte bound
/// on each stream and a stop of the whole process tree.
///
/// Constraint C16: `gh` and `sw pr reviewers` arguments reach the command only as
/// escaped records on stdin, never through Dart's process arguments. The helper
/// starts `bash -c '<prelude>; exec "$@"'`, which reads the working directory
/// and the argument records the parent sends after the go byte, so on every OS
/// MSYS never expands them and on POSIX an escaped byte keeps its value.
///
/// [environment] is the whole environment of the call (see
/// [BoundedRun.environment]); null keeps `sw`'s own. [paged] picks the longer
/// paged deadline. [limits] overrides the resolved ones, and [helperCommand] the
/// helper's command line (tests run it from source).
Future<GhResult> runGh(
  String bash,
  String cwd,
  List<String> args, {
  Map<String, String>? environment,
  bool paged = false,
  RunLimits? limits,
  List<String>? helperCommand,
}) => _run(
  bash,
  'gh',
  frameCommand(cwd, ['gh', ...args]),
  ['gh', ...args],
  environment: environment,
  paged: paged,
  limits: limits,
  helperCommand: helperCommand,
);

/// [runGh] with the bytes sent on stdin given as they are, so a test can send
/// a bad count or a short read.
Future<GhResult> runGhFramed(
  String bash,
  List<int> stdinBytes, {
  Map<String, String>? environment,
  RunLimits? limits,
  List<String>? helperCommand,
}) => _run(
  bash,
  'gh',
  stdinBytes,
  const ['gh'],
  environment: environment,
  paged: false,
  limits: limits,
  helperCommand: helperCommand,
);

/// Runs `sw pr reviewers <args>` the same way (the caller's [command] starts with
/// the `sw` executable).
Future<GhResult> runBoundedCommand(
  String bash,
  String cwd,
  List<String> command, {
  Map<String, String>? environment,
  bool paged = false,
  RunLimits? limits,
  List<String>? helperCommand,
}) => _run(
  bash,
  command.first,
  frameCommand(cwd, command),
  command,
  environment: environment,
  paged: paged,
  limits: limits,
  helperCommand: helperCommand,
);

Future<GhResult> _run(
  String bash,
  String name,
  List<int> stdinBytes,
  List<String> logical, {
  required Map<String, String>? environment,
  required bool paged,
  required RunLimits? limits,
  required List<String>? helperCommand,
}) async {
  final result = await BoundedRun(
    command: [bash, '-c', '$boundedPrelude; exec "\$@"', name],
    stdinBytes: stdinBytes,
    environment: environment,
    // the scripts' `gh()` passed `--paged` whenever SW_PAGED was set, too
    limits:
        limits ??
        resolveLimits(
          _platformEnv(environment),
          paged:
              paged || (_platformEnv(environment)['SW_PAGED'] ?? '').isNotEmpty,
        ),
    helperCommand: helperCommand,
    treeFor: () => platformTree(environment ?? _platformEnv(null)),
    note: (_) {},
  ).run();
  final limit = result.limit;
  if (limit != null) {
    return GhResult(
      exitCode: limit.exitCode,
      limit: limit,
      limitLine: limitLine(limit, [bash, '-c', 'exec "\$@"', ...logical]),
      stdout: Uint8List(0),
      stderr: Uint8List(0),
    );
  }
  if (result.helperExited) {
    return GhResult(
      exitCode: 127,
      stdout: Uint8List(0),
      stderr: encodeEscaped(
        'bounded: helper exited during startup: ${commandLabel(logical)}\n',
      ),
    );
  }
  final startError = result.startError;
  if (startError != null) {
    return GhResult(
      exitCode: 127,
      stdout: Uint8List(0),
      stderr: encodeEscaped(
        'bounded: cannot start ${logical.first}: $startError\n',
      ),
    );
  }
  return GhResult(
    exitCode: result.exitCode ?? 127,
    stdout: Uint8List.fromList(result.stdout),
    stderr: Uint8List.fromList(result.stderr),
  );
}

Map<String, String> _platformEnv(Map<String, String>? given) =>
    given ?? Platform.environment;
