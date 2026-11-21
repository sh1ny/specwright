import 'dart:convert';
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
import '../process/tree_stop.dart' show ProcessTreeFactory;

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
    this.merged,
  });

  final int exitCode;

  /// The limit that ended the call, if one did.
  final BoundedLimit? limit;

  /// `bounded: <limit>: <command> <first argument>\n` when [limit] is set.
  final String? limitLine;
  final Uint8List stdout;
  final Uint8List stderr;

  /// The output of a call that ran in merged mode (the `--log-failed` call):
  /// stdout and stderr in the order their chunks reached `sw`. Null for every
  /// other result, including a call that never started a process, whose own
  /// output is [stderr].
  final Uint8List? merged;
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
/// [environment] is the whole environment of the call (see
/// [BoundedRun.environment]); null keeps `sw`'s own. [paged] picks the longer
/// paged deadline. [limits] overrides the resolved ones, and [helperCommand] the
/// helper's command line (tests run it from source).
Future<GhResult> runGh(
  String cwd,
  List<String> args, {
  Map<String, String>? environment,
  bool paged = false,
  RunLimits? limits,
  List<String>? helperCommand,
  ProcessStarter startProcess = startHelperProcess,
  ProcessTreeFactory? treeFor,
}) => _run(
  cwd,
  ['gh', ...args],
  // D8: an inherited GH_REPO never picks the repository of a gh call
  environment: {...(environment ?? Platform.environment)}..remove('GH_REPO'),
  paged: paged,
  // D4: the failed-job log is one stream in arrival order, under one budget
  mergeOutput: args.contains('--log-failed'),
  limits: limits,
  helperCommand: helperCommand,
  startProcess: startProcess,
  treeFor: treeFor,
);

/// Runs `sw pr reviewers <args>` the same way (the caller's [command] starts with
/// the `sw` executable). A [command] that starts `bash -c` keeps the Windows
/// stdin transport of `planLaunch`.
Future<GhResult> runBoundedCommand(
  String cwd,
  List<String> command, {
  Map<String, String>? environment,
  bool paged = false,
  RunLimits? limits,
  List<String>? helperCommand,
  ProcessStarter startProcess = startHelperProcess,
  ProcessTreeFactory? treeFor,
}) => _run(
  cwd,
  command,
  environment: environment,
  paged: paged,
  mergeOutput: false,
  limits: limits,
  helperCommand: helperCommand,
  startProcess: startProcess,
  treeFor: treeFor,
);

GhResult _notStarted(String text) => GhResult(
  exitCode: 127,
  stdout: Uint8List(0),
  stderr: utf8.encode('bounded: $text\n'),
);

Future<GhResult> _run(
  String cwd,
  List<String> command, {
  required Map<String, String>? environment,
  required bool paged,
  required bool mergeOutput,
  required RunLimits? limits,
  required List<String>? helperCommand,
  required ProcessStarter startProcess,
  required ProcessTreeFactory? treeFor,
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
  final BoundedLaunchPlan launchPlan;
  try {
    launchPlan = planBoundedLaunch(
      path,
      command,
      env,
      effectiveHelperCommand(helperCommand),
    );
  } on UnsafeBatchArgument catch (e) {
    return _notStarted('cannot start $name: $e');
  } on Unrepresentable catch (e) {
    return _notStarted('cannot start $name: $e');
  }
  final plan = launchPlan.plan;
  final result = await BoundedRun(
    command: plan.command,
    rawLine: plan.rawLine,
    helperArgv: launchPlan.helperArgv,
    lineTooLong: launchPlan.lineTooLong,
    mergeOutput: mergeOutput,
    startProcess: startProcess,
    stdinBytes: plan.stdinBytes,
    workingDirectory: dir,
    environment: environment,
    // the scripts' `gh()` passed `--paged` whenever SW_PAGED was set, too
    limits:
        limits ??
        resolveLimits(env, paged: paged || (env['SW_PAGED'] ?? '').isNotEmpty),
    helperCommand: helperCommand,
    treeFor: treeFor ?? () => platformTree(env),
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
      stderr: utf8.encode(
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
    merged: result.merged == null ? null : Uint8List.fromList(result.merged!),
  );
}

Map<String, String> _platformEnv(Map<String, String>? given) =>
    given ?? Platform.environment;
