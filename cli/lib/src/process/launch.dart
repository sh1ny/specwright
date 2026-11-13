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
/// Constraint C9: a [stdoutCap] bounds stdout only. Once stdout holds more than
/// that many bytes the child is killed, and [LaunchResult.outputTooLarge] is
/// set. A capped native executable is not run under a tree stop: overflow
/// kills the direct child only, as it did before the launcher, so a
/// descendant of the tool may outlive it. (A batch file runs under the
/// helper, whose tree is stopped.) No call has a deadline or a bound on
/// stderr, and no deadline or byte bound is added to a call that had none.
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
  List<String>? helperCommand,
  Future<void> Function(List<int>)? stdoutSink,
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
      helperCommand,
      stdoutSink,
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
    stdoutSink,
  );
}

Future<LaunchResult> _batch(
  String name,
  String path,
  List<String> command,
  String dir,
  Map<String, String> env,
  Map<String, String>? environment,
  List<int>? input,
  int? stdoutCap,
  List<String>? helperCommand,
  Future<void> Function(List<int>)? stdoutSink,
) async {
  final plan = planLaunch(path, command, env);
  final result = await BoundedRun(
    command: plan.command,
    rawLine: plan.rawLine,
    stdinBytes: [...plan.stdinBytes, ...?input],
    limits: RunLimits(stdoutCap: stdoutCap),
    treeFor: () => platformTree(env),
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
  return LaunchResult(
    result.exitCode ?? 127,
    Uint8List.fromList(result.stdout),
    Uint8List.fromList(result.stderr),
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
  Future<void> Function(List<int>)? stdoutSink,
) async {
  final Process process;
  try {
    process = await Process.start(
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
        if (!outDone.isCompleted) outDone.complete();
        settleSink();
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
    onError: (Object _) {
      if (!outDone.isCompleted) outDone.complete();
      settleSink();
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
    if (tooLarge) {
      await errSub.cancel();
    } else {
      await errDone.future;
    }
    // POSIX reports a signal as its negative number; Windows codes stay as
    // they are (0xC0000005 arrives negative).
    final exit = code < 0 && !Platform.isWindows ? 128 - code : code;
    return LaunchResult(
      exit,
      out.takeBytes(),
      err.takeBytes(),
      outputTooLarge: tooLarge,
    );
  } catch (_) {
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
