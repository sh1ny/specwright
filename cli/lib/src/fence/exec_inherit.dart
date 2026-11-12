import 'dart:async';
import 'dart:io';

import '../native/kernel32.dart' as k32;
import '../process/command_line.dart';
import '../process/launch.dart' show checkLaunchInput;
import '../process/resolve.dart';

/// Native-cli-launcher D3. The fenced command starts directly, with no shell
/// and no file of its own: [command]'s first item is found by [resolveCommand]
/// (on Windows by `PATHEXT` only, so an extensionless script is not found, D9)
/// and started with `sw`'s own stdin, stdout and stderr, exactly [environment]
/// and nothing of `sw`'s own, in the directory `sw` is in. The caller's stdin
/// is never read here. The returned status is the command's; a command ended by
/// signal N gives 128+N (Dart reports -N on POSIX). On POSIX, SIGINT, SIGTERM
/// and SIGHUP sent to `sw` are sent on to the command while it runs. A command
/// that is not found ends 127 with `as.sh: <name>: command not found` on
/// stderr. A command the launcher cannot represent (a NUL, a lone surrogate, a
/// Windows line past its limit) throws `Unrepresentable` before anything
/// starts, which `runFence` turns into its `as.sh:` refusal.
///
/// On Windows a `.cmd` or `.bat` command runs through `cmd.exe` as `planLaunch`
/// builds the line, started by [k32.runWithCommandLine] in this process: it
/// inherits the caller's handles, so no helper, frame or pipe stands between the
/// caller and the command. The call blocks until the command exits, which the
/// fence only waits for anyway. An argument quotes cannot protect is
/// `as.sh: unsafe batch argument: <name>`, exit 2, before the start.
///
/// `sw` got `PWD` in its drive form from the shim's bash, so on Windows it is
/// left out of the command's environment: the command works its own out.
Future<int> runFenced(
  List<String> command,
  Map<String, String> environment,
) async {
  final cwd = Directory.current.path;
  final env = Map.of(environment);
  if (Platform.isWindows) {
    env.removeWhere((key, _) => key.toUpperCase() == 'PWD');
  }
  checkLaunchInput(command, cwd: cwd, environment: env);
  final name = command.first;
  final path = resolveCommand(name, env, workingDirectory: cwd);
  if (path == null) {
    stderr.writeln('as.sh: $name: command not found');
    return 127;
  }
  if (Platform.isWindows && isBatchFile(path)) {
    final LaunchPlan plan;
    try {
      plan = planLaunch(path, command, env);
    } on UnsafeBatchArgument {
      stderr.writeln('as.sh: unsafe batch argument: $name');
      return 2;
    }
    final result = k32.runWithCommandLine(
      plan.command[0],
      plan.command[1],
      environment: env,
      workingDirectory: cwd,
    );
    final status = result.status;
    if (status == null) {
      stderr.writeln('as.sh: cannot start $name (error ${result.error})');
      return 127;
    }
    return status;
  }
  // D5: the resolved path's Windows line is checked by planLaunch (it throws
  // Unrepresentable, which runFence refuses); the fence starts the raw
  // arguments, so the plan is only asked for its check.
  planLaunch(path, command, env, transport: false);
  return _inherit(name, path, command.skip(1).toList(), env);
}

/// Starts [path] with [args], [env] only, and this process's stdio, and returns
/// its status, forwarding SIGINT, SIGTERM and SIGHUP on POSIX meanwhile.
Future<int> _inherit(
  String name,
  String path,
  List<String> args,
  Map<String, String> env,
) async {
  final subscriptions = <StreamSubscription<ProcessSignal>>[];
  try {
    final Process process;
    try {
      process = await Process.start(
        path,
        args,
        environment: env,
        includeParentEnvironment: false,
        mode: ProcessStartMode.inheritStdio,
      );
    } on ProcessException catch (e) {
      stderr.writeln('as.sh: cannot start $name: ${e.message}');
      return 127;
    }
    if (!Platform.isWindows) {
      for (final signal in [
        ProcessSignal.sigint,
        ProcessSignal.sigterm,
        ProcessSignal.sighup,
      ]) {
        subscriptions.add(signal.watch().listen(process.kill));
      }
    }
    final code = await process.exitCode;
    return code < 0 && !Platform.isWindows ? 128 - code : code;
  } finally {
    for (final subscription in subscriptions) {
      unawaited(subscription.cancel());
    }
  }
}
