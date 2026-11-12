import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:path/path.dart' as p;

import 'bounded_run.dart';
import 'command_line.dart';
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

/// Input [launch] cannot hand to a tool whole: a NUL, a lone surrogate, or on
/// Windows a command line past the operating system's limit (D5).
class Unrepresentable implements Exception {
  const Unrepresentable(this.command, this.what);

  /// The command's name, as the caller gave it.
  final String command;

  /// What cannot be represented: `command`, `argument`, `environment variable
  /// name`, `environment variable value`, `working directory` or `command
  /// line`.
  final String what;

  @override
  String toString() => 'unrepresentable $what: $command';
}

/// The longest command line `CreateProcessW` takes, in UTF-16 units.
const int windowsCommandLineLimit = 32767;

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

/// Units one argument takes on a Windows command line: wrapped in quotes when
/// it is empty or holds a space, tab or quote, with a quote and the backslashes
/// before it (or before the closing quote) escaped.
int _quotedLength(String arg) {
  if (arg.isNotEmpty && !RegExp(r'[ \t"]').hasMatch(arg)) return arg.length;
  var n = 2;
  var slashes = 0;
  for (final u in arg.codeUnits) {
    if (u == 0x5c) {
      slashes++;
      n++;
      continue;
    }
    if (u == 0x22) n += slashes + 1;
    slashes = 0;
    n++;
  }
  return n + slashes;
}

void _checkLine(String name, List<String> command, bool windows) {
  if (!windows) return;
  var units = command.length - 1; // the separating spaces
  for (final item in command) {
    units += _quotedLength(item);
  }
  if (units > windowsCommandLineLimit) {
    throw Unrepresentable(name, 'command line');
  }
}

/// Throws [Unrepresentable] (`command line`, named by [name]) when, on Windows
/// ([windows], default: this system), the native [command] (the resolved path
/// first) would make a command line past [windowsCommandLineLimit] units. A
/// batch command is not checked here: `planLaunch` keeps its own line limit.
void checkNativeLine(String name, List<String> command, {bool? windows}) =>
    _checkLine(name, command, windows ?? Platform.isWindows);

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
  _checkLine(name, command, windows ?? Platform.isWindows);
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
    );
  }
  checkNativeLine(name, [path, ...command.skip(1)]);
  return _native(
    name,
    path,
    command.skip(1).toList(),
    dir,
    inherit ? null : environment,
    input,
    stdoutCap,
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
  var tooLarge = false;
  late final StreamSubscription<List<int>> outSub;
  outSub = process.stdout.listen(
    (chunk) {
      if (tooLarge) return;
      out.add(chunk);
      if (cap != null && out.length > cap) {
        tooLarge = true;
        outSub.cancel();
        process.kill(ProcessSignal.sigkill);
        if (!outDone.isCompleted) outDone.complete();
      }
    },
    onDone: () {
      if (!outDone.isCompleted) outDone.complete();
    },
    onError: (Object _) {
      if (!outDone.isCompleted) outDone.complete();
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

  await outDone.future;
  final code = await process.exitCode;
  if (tooLarge) {
    await errSub.cancel();
  } else {
    await errDone.future;
  }
  // POSIX reports a signal as its negative number; Windows codes stay as they
  // are (0xC0000005 arrives negative).
  final exit = code < 0 && !Platform.isWindows ? 128 - code : code;
  return LaunchResult(
    exit,
    out.takeBytes(),
    err.takeBytes(),
    outputTooLarge: tooLarge,
  );
}
