import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:path/path.dart' as p;

import 'bounded_run.dart';
import 'command_line.dart';

export 'command_line.dart' show Unrepresentable, windowsCommandLineLimit;
import 'limit_line.dart' show BoundedLimit;
import 'limits.dart';
import 'missing_directory.dart';
import 'platform_tree.dart';
import 'resolve.dart';
import 'tree_stop.dart' show ProcessTreeFactory;

/// What a launch produced: the exit code and the raw output bytes. Decoding is
/// the caller's choice. The fields are those of the `ToolResult` the tool
/// runners return, so they can hand a [LaunchResult] on as it is.
class LaunchResult {
  LaunchResult(
    this.exitCode,
    this.stdout,
    this.stderr, {
    this.outputTooLarge = false,
    this.startFailed = false,
    this.timedOut = false,
    this.streamError,
  });

  final int exitCode;
  final Uint8List stdout;
  final Uint8List stderr;

  /// Only a call with a `stdoutCap`: stdout went past the cap and the tool was
  /// killed.
  final bool outputTooLarge;

  /// Nothing ran: the working directory is missing, the command was not found,
  /// or the start failed. The exit code is 127 and [stderr] says which.
  final bool startFailed;

  /// Only a call with a `deadline`: the tool ran past it and was killed.
  final bool timedOut;

  /// The first error a stdout or stderr pipe reported (C49). It is not a clean
  /// end of stream: [exitCode] and the bytes read stay as they were.
  final Object? streamError;
}

bool _hasNul(String s) => s.contains('\x00');

bool _hasLoneSurrogate(String s) {
  final units = s.codeUnits;
  for (var i = 0; i < units.length; i++) {
    final u = units[i];
    if (u >= 0xd800 && u <= 0xdbff) {
      if (i + 1 < units.length &&
          units[i + 1] >= 0xdc00 &&
          units[i + 1] <= 0xdfff) {
        i++;
        continue;
      }
      return true;
    }
    if (u >= 0xdc00 && u <= 0xdfff) return true;
  }
  return false;
}

/// Constraint C25: on Windows the launchers that check the command as given
/// before lookup keep doing so; a relative spelling over the limit that would
/// resolve to a short path is refused, because moving the check changes
/// existing refusals. This is a deliberate gap. The as-given check counts no
/// terminating NUL (32,767 visible units pass); only a line that is started
/// does (`planLaunch`, `planBoundedLaunch`).
///
/// Throws [Unrepresentable] for a NUL or a lone surrogate in [command] (its
/// first item is `command`, the others `argument`), in [environment] (key or
/// value) or in [cwd], and, when [windows] (default: this system), for a
/// command line past [windowsCommandLineLimit] units. Nothing starts before
/// these checks, and they come before the batch rules of `planLaunch`.
void checkLaunchInput(
  List<String> command, {
  required String cwd,
  Map<String, String>? environment,
  bool? windows,
}) {
  final name = command.first;
  void check(String text, String what) {
    if (_hasNul(text) || _hasLoneSurrogate(text)) {
      throw Unrepresentable(name, what);
    }
  }

  for (var i = 0; i < command.length; i++) {
    check(command[i], i == 0 ? 'command' : 'argument');
  }
  for (final entry in (environment ?? const <String, String>{}).entries) {
    check(entry.key, 'environment variable name');
    check(entry.value, 'environment variable value');
  }
  check(cwd, 'working directory');
  checkCommandLine(name, command, windows: windows);
}

LaunchResult _startFailed(String text) => LaunchResult(
  127,
  Uint8List(0),
  Uint8List.fromList(utf8.encode(text)),
  startFailed: true,
);

/// Starts [command] (the tool's name or path first) in [cwd] without a shell
/// and returns its exit code and raw output.
///
/// The input is checked first ([checkLaunchInput]; a refusal is thrown as
/// [Unrepresentable]). A [cwd] that is not a directory, a command that is not
/// found and a start that fails give exit 127 with [LaunchResult.startFailed]
/// and the reason on stderr (`<name>: command not found` for a missing
/// command). The command is found by `resolveCommand`, so on Windows only a
/// `PATHEXT` extension counts and an extensionless file is never chosen (D9).
/// [input], when given, is written on the tool's stdin, which is then closed.
/// When [stdoutSink] is given, stdout is consumed sequentially by that async
/// sink with backpressure and is not retained in [LaunchResult.stdout]. A sink
/// failure stops the command, cancels its readers and is rethrown.
/// [environment], when non-empty, is the tool's whole environment; otherwise
/// it inherits this process's. A tool ended by a signal reports 128 plus the
/// signal number on Linux and macOS.
///
/// A native executable starts directly with `Process.start`. A `.cmd` or
/// `.bat` command on Windows runs through [BoundedRun], whose helper starts
/// the `planLaunch` raw `cmd.exe` line; `planLaunch` can throw
/// [UnsafeBatchArgument] for such a command, after the input checks. A batch
/// file that cannot start gives 127 as above. [helperCommand] replaces the
/// helper (`sw __exec`) for tests.
///
/// Constraint C49: the native and bounded launchers never read a stdout or
/// stderr stream error as a clean end of stream: they record it on the result
/// ([LaunchResult.streamError], `BoundedResult.streamError`), and an error on
/// either pipe before the go byte is a failed start that sends no go byte. Only
/// the shared inventory reader turns a recorded stream error into a failed
/// read; every other caller, including `sw run --bounded` and `runGh`, keeps
/// today's mapping of status and captured output, so the native-cli and
/// pr-script-runtime contracts are unchanged.
///
/// Constraint C9: a [stdoutCap] bounds stdout only. Once stdout holds more than
/// that many bytes the child is killed, and [LaunchResult.outputTooLarge] is
/// set. A [stderrCap] does the same for stderr, while it is read; only the
/// self-check of a downloaded `sw` passes one. On the batch path a
/// [stderrCap] without a [stdoutCap] bounds stdout too (the helper's one
/// byte bound). A capped native executable is not run under a tree stop:
/// overflow kills the direct child only, as it did before the launcher, so a
/// descendant of the tool may outlive it. (A batch file runs under the
/// helper, whose tree is stopped.) No deadline or byte bound is added to a
/// call that had none.
///
/// A [deadline], when given, kills a native tool that has not ended by then
/// (the batch path stops its tree) and sets [LaunchResult.timedOut]. Without
/// one a call has no deadline, as before.
///
/// Constraint C11: the working directory comes from the caller, as an absolute
/// path. A relative command path or `PATH` entry, including the current
/// directory an empty POSIX entry stands for, is looked for under [cwd], and the
/// tool runs there. Nothing here changes `sw`'s own directory, and nothing
/// depends on it.
Future<LaunchResult> launch(
  List<String> command, {
  required String cwd,
  List<int>? input,
  Map<String, String>? environment,
  int? stdoutCap,
  int? stderrCap,
  Duration? deadline,
  List<String>? helperCommand,
  Future<void> Function(List<int>)? stdoutSink,
  ProcessStarter? startProcess,
  ProcessTreeFactory? treeFor,
}) async {
  checkLaunchInput(command, cwd: cwd, environment: environment);
  final name = command.first;
  final dir = p.absolute(cwd);
  if (!Directory(dir).existsSync()) {
    return _startFailed(
      '${missingDirectoryText(cwd, isFile: File(dir).existsSync())}\n',
    );
  }
  final inherit = environment == null || environment.isEmpty;
  final env = inherit ? Platform.environment : environment;
  final path = resolveCommand(name, env, workingDirectory: dir);
  if (path == null) return _startFailed('$name: command not found\n');
  if (Platform.isWindows && isBatchFile(path)) {
    return _batch(
      name,
      path,
      command,
      dir,
      env,
      inherit ? null : environment,
      input,
      stdoutCap,
      stderrCap,
      deadline,
      helperCommand,
      stdoutSink,
      startProcess ?? startHelperProcess,
      treeFor,
    );
  }
  // D5: the resolved path's Windows line is checked by planLaunch, the one
  // place every native plan passes through. launch() starts the raw arguments
  // (no bash transport), so the plan is only asked for its check.
  planLaunch(path, command, env, transport: false);
  return _native(
    name,
    path,
    command.skip(1).toList(),
    dir,
    inherit ? null : environment,
    input,
    stdoutCap,
    stderrCap,
    deadline,
    stdoutSink,
    startProcess ?? _startTool,
  );
}

/// Starts an external tool directly, without a shell: the default
/// [ProcessStarter] of a native launch.
Future<Process> _startTool(
  String executable,
  List<String> arguments, {
  Map<String, String>? environment,
  bool includeParentEnvironment = true,
  String? workingDirectory,
}) => Process.start(
  executable,
  arguments,
  environment: environment,
  includeParentEnvironment: includeParentEnvironment,
  workingDirectory: workingDirectory,
);

Future<LaunchResult> _batch(
  String name,
  String path,
  List<String> command,
  String dir,
  Map<String, String> env,
  Map<String, String>? environment,
  List<int>? input,
  int? stdoutCap,
  int? stderrCap,
  Duration? deadline,
  List<String>? helperCommand,
  Future<void> Function(List<int>)? stdoutSink,
  ProcessStarter startProcess,
  ProcessTreeFactory? treeFor,
) async {
  final launchPlan = planBoundedLaunch(
    path,
    command,
    env,
    effectiveHelperCommand(helperCommand),
  );
  final plan = launchPlan.plan;
  final result = await BoundedRun(
    command: plan.command,
    rawLine: plan.rawLine,
    helperArgv: launchPlan.helperArgv,
    lineTooLong: launchPlan.lineTooLong,
    startProcess: startProcess,
    stdinBytes: [...plan.stdinBytes, ...?input],
    // maxBytes bounds stderr (and stdout too when there is no stdoutCap)
    limits: RunLimits(
      stdoutCap: stdoutCap,
      maxBytes: stderrCap,
      deadline: deadline,
    ),
    treeFor: treeFor ?? () => platformTree(env),
    helperCommand: helperCommand,
    environment: environment,
    workingDirectory: dir,
    stdoutSink: stdoutSink,
    note: (_) {},
  ).run();
  final limit = result.limit;
  if (limit == BoundedLimit.responseTooLarge) {
    return LaunchResult(137, Uint8List(0), Uint8List(0), outputTooLarge: true);
  }
  if (limit != null) return _startFailed('$name: stopped: ${limit.label}\n');
  if (result.helperExited) {
    return _startFailed('$name: helper exited during startup\n');
  }
  final startError = result.startError;
  if (startError != null) {
    return _startFailed('cannot start $name: $startError\n');
  }
  if (result.pipesHeld) {
    return _startFailed('$name: stopped: output pipe held after exit\n');
  }
  return LaunchResult(
    result.exitCode ?? 127,
    Uint8List.fromList(result.stdout),
    Uint8List.fromList(result.stderr),
    streamError: result.streamError,
  );
}

Future<LaunchResult> _native(
  String name,
  String path,
  List<String> args,
  String dir,
  Map<String, String>? environment,
  List<int>? input,
  int? cap,
  int? stderrCap,
  Duration? deadline,
  Future<void> Function(List<int>)? stdoutSink,
  ProcessStarter startProcess,
) async {
  final Process process;
  try {
    process = await startProcess(
      path,
      args,
      workingDirectory: dir,
      environment: environment,
      includeParentEnvironment: environment == null,
    );
  } on ProcessException catch (e) {
    return _startFailed('${e.toString()}\n');
  }

  final out = BytesBuilder(copy: false);
  final err = BytesBuilder(copy: false);
  final outDone = Completer<void>();
  final errDone = Completer<void>();
  final sinkSettled = stdoutSink == null ? null : Completer<void>();
  Object? sinkError;
  StackTrace? sinkStack;
  Future<void> throwSinkError() async {
    await sinkSettled!.future;
    if (sinkError != null) {
      Error.throwWithStackTrace(sinkError!, sinkStack!);
    }
  }

  void settleSink() {
    final settled = sinkSettled;
    if (settled != null && !settled.isCompleted) settled.complete();
  }

  // Ends every wait of this call: a descendant that inherited stdout or
  // stderr can keep either pipe open after the kill, so neither is awaited
  // once the call is over (the readers are cancelled below).
  void stopWaiting() {
    if (!outDone.isCompleted) outDone.complete();
    if (!errDone.isCompleted) errDone.complete();
    settleSink();
  }

  Object? streamError; // C49: a pipe error is not a clean end of stream
  var timedOut = false;
  // armed until both readers end, not only until the tool exits
  final timer = deadline == null
      ? null
      : Timer(deadline, () {
          timedOut = true;
          process.kill(ProcessSignal.sigkill);
          stopWaiting();
        });
  var stdoutBytes = 0;
  var tooLarge = false;
  late final StreamSubscription<List<int>> outSub;
  outSub = process.stdout.listen(
    (chunk) {
      if (tooLarge || sinkError != null) return;
      if (stdoutSink == null) {
        out.add(chunk);
        stdoutBytes = out.length;
      } else {
        stdoutBytes += chunk.length;
      }
      if (cap != null && stdoutBytes > cap) {
        tooLarge = true;
        unawaited(outSub.cancel().catchError((Object _) {}));
        process.kill(ProcessSignal.sigkill);
        stopWaiting();
        return;
      }
      final sink = stdoutSink;
      if (sink == null) return;
      outSub.pause();
      unawaited(() async {
        try {
          await sink(chunk);
          if (sinkError == null && !tooLarge) outSub.resume();
        } catch (error, stack) {
          if (sinkError == null) {
            sinkError = error;
            sinkStack = stack;
            if (!sinkSettled!.isCompleted) sinkSettled.complete();
            process.kill(ProcessSignal.sigkill);
            if (!outDone.isCompleted) outDone.complete();
            unawaited(outSub.cancel().catchError((Object _) {}));
          }
        }
      }());
    },
    onDone: () {
      if (!outDone.isCompleted) outDone.complete();
      settleSink();
    },
    onError: (Object error) {
      streamError ??= error;
      if (!outDone.isCompleted) outDone.complete();
      settleSink();
    },
    cancelOnError: true,
  );
  final errSub = process.stderr.listen(
    (chunk) {
      if (tooLarge) return;
      err.add(chunk);
      if (stderrCap != null && err.length > stderrCap) {
        tooLarge = true;
        process.kill(ProcessSignal.sigkill);
        unawaited(outSub.cancel().catchError((Object _) {}));
        stopWaiting();
      }
    },
    onDone: () {
      if (!errDone.isCompleted) errDone.complete();
    },
    onError: (Object error) {
      streamError ??= error;
      if (!errDone.isCompleted) errDone.complete();
    },
    cancelOnError: true,
  );

  // Both streams drain while the input goes in, so a tool that fills stderr
  // before it reads its stdin cannot deadlock. A tool that exits without
  // reading its input is not an error here: its exit code says so.
  unawaited(process.stdin.done.catchError((Object _) {}));
  try {
    if (input != null && input.isNotEmpty) process.stdin.add(input);
    await process.stdin.close();
  } on Object {
    // broken pipe
  }

  try {
    await Future.any<Object?>([
      outDone.future,
      if (sinkSettled != null) throwSinkError(),
    ]);
    if (sinkSettled?.isCompleted == true) await throwSinkError();
    final code = await process.exitCode;
    if (sinkSettled?.isCompleted == true) await throwSinkError();
    // the deadline or a cap ends this wait too (stopWaiting)
    await errDone.future;
    timer?.cancel();
    if (tooLarge || timedOut) {
      await Future.wait([
        outSub.cancel().catchError((Object _) {}),
        errSub.cancel().catchError((Object _) {}),
      ]);
    }
    // POSIX reports a signal as its negative number; Windows codes stay as
    // they are (0xC0000005 arrives negative).
    final exit = code < 0 && !Platform.isWindows ? 128 - code : code;
    return LaunchResult(
      exit,
      out.takeBytes(),
      err.takeBytes(),
      outputTooLarge: tooLarge,
      timedOut: timedOut,
      streamError: streamError,
    );
  } catch (_) {
    timer?.cancel();
    process.kill(ProcessSignal.sigkill);
    await Future.wait([
      outSub.cancel().catchError((Object _) {}),
      errSub.cancel().catchError((Object _) {}),
    ]);
    await process.exitCode;
    settleSink();
    rethrow;
  }
}
