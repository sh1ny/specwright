import 'dart:io';
import 'dart:typed_data';

import 'package:path/path.dart' as p;

import '../process/bounded_run.dart';
import '../process/command_line.dart';
import '../process/launch.dart' show Unrepresentable, checkLaunchInput;
import '../process/limit_line.dart';
import '../process/limits.dart';
import '../process/missing_directory.dart';
import '../process/platform_tree.dart';
import '../process/resolve.dart';
import '../vcs/codec.dart';

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

/// Runs `gh <args>` in [cwd] under the bounded helper: a deadline, a byte bound
/// on each stream and a stop of the whole process tree.
///
/// `gh` is found by `resolveCommand` (on Windows only a `PATHEXT` name counts)
/// and started by the helper through `planLaunch`, with no shell: the arguments
/// reach it as they are, as process arguments, and the helper starts it in
/// [cwd]. A call that cannot start (no such directory, no such command, input
/// the launcher cannot represent, an unsafe batch argument) is exit 127 with
/// the reason on stderr.
///
/// [bash] is not used any more: the argument is kept until the callers drop it.
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
  cwd,
  ['gh', ...args],
  environment: environment,
  paged: paged,
  limits: limits,
  helperCommand: helperCommand,
);

/// Runs `sw pr reviewers <args>` the same way (the caller's [command] starts with
/// the `sw` executable). A [command] that starts `bash -c` keeps the Windows
/// stdin transport of `planLaunch`.
Future<GhResult> runBoundedCommand(
  String bash,
  String cwd,
  List<String> command, {
  Map<String, String>? environment,
  bool paged = false,
  RunLimits? limits,
  List<String>? helperCommand,
}) => _run(
  cwd,
  command,
  environment: environment,
  paged: paged,
  limits: limits,
  helperCommand: helperCommand,
);

GhResult _notStarted(String text) => GhResult(
  exitCode: 127,
  stdout: Uint8List(0),
  stderr: encodeEscaped('bounded: $text\n'),
);

Future<GhResult> _run(
  String cwd,
  List<String> command, {
  required Map<String, String>? environment,
  required bool paged,
  required RunLimits? limits,
  required List<String>? helperCommand,
}) async {
  final name = command.first;
  final env = _platformEnv(environment);
  try {
    checkLaunchInput(command, cwd: cwd, environment: environment);
  } on Unrepresentable catch (e) {
    return _notStarted('cannot start $name: $e');
  }
  final dir = p.absolute(cwd);
  if (!Directory(dir).existsSync()) {
    return _notStarted(
      missingDirectoryText(cwd, isFile: File(dir).existsSync()),
    );
  }
  final path = resolveCommand(name, env, workingDirectory: dir);
  if (path == null) return _notStarted('$name: command not found');
  final LaunchPlan plan;
  try {
    plan = planLaunch(path, command, env);
  } on UnsafeBatchArgument catch (e) {
    return _notStarted('cannot start $name: $e');
  }
  final result = await BoundedRun(
    command: plan.command,
    rawLine: plan.rawLine,
    stdinBytes: plan.stdinBytes,
    workingDirectory: dir,
    environment: environment,
    // the scripts' `gh()` passed `--paged` whenever SW_PAGED was set, too
    limits:
        limits ??
        resolveLimits(env, paged: paged || (env['SW_PAGED'] ?? '').isNotEmpty),
    helperCommand: helperCommand,
    treeFor: () => platformTree(env),
    note: (_) {},
  ).run();
  final limit = result.limit;
  if (limit != null) {
    return GhResult(
      exitCode: limit.exitCode,
      limit: limit,
      limitLine: limitLine(limit, command),
      stdout: Uint8List(0),
      stderr: Uint8List(0),
    );
  }
  if (result.helperExited) {
    return GhResult(
      exitCode: 127,
      stdout: Uint8List(0),
      stderr: encodeEscaped(
        'bounded: helper exited during startup: ${commandLabel(command)}\n',
      ),
    );
  }
  final startError = result.startError;
  if (startError != null) {
    return _notStarted('cannot start $name: $startError');
  }
  return GhResult(
    exitCode: result.exitCode ?? 127,
    stdout: Uint8List.fromList(result.stdout),
    stderr: Uint8List.fromList(result.stderr),
  );
}

Map<String, String> _platformEnv(Map<String, String>? given) =>
    given ?? Platform.environment;
