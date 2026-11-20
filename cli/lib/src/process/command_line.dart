import 'dart:io';

import 'transport.dart';

/// The longest command string `cmd.exe` accepts after `/c`.
const int batchLineLimit = 8191;

/// A batch argument or path that double quotes cannot protect from `cmd.exe`.
class UnsafeBatchArgument implements Exception {
  const UnsafeBatchArgument(this.reason);

  final String reason;

  @override
  String toString() => 'unsafe batch argument: $reason';
}

/// How a resolved command is started.
class LaunchPlan {
  const LaunchPlan(
    this.command,
    this.stdinBytes, {
    this.rawLine = false,
    this.lineTooLong = false,
  });

  /// The command and its arguments. With [rawLine] it is the application and
  /// the exact Windows command line, nothing else.
  final List<String> command;

  /// Bytes to write on the command's stdin right after the go byte.
  final List<int> stdinBytes;

  /// The helper hands [command]'s second item to `CreateProcessW` as it is,
  /// because Dart's own quoting would escape the quotes `cmd.exe` must see.
  final bool rawLine;

  /// The started line is over the limit only with its terminating NUL: the
  /// resolved native line or the raw `cmd.exe` line. Set only when [planLaunch]
  /// was asked not to throw (a bounded launch, D5).
  final bool lineTooLong;
}

/// Quotes a batch path and its arguments for `cmd.exe /d /s /c`: each in double
/// quotes (`""` for an empty argument), separated by spaces, no caret escaping,
/// and a run of backslashes at the end of an argument doubled so a native
/// program the shim forwards `%*` to reads the original value. Backslashes
/// elsewhere stay as they are, because `"` is refused and none can precede a
/// quote.
///
/// Throws [UnsafeBatchArgument] for what quotes cannot protect: `%`, `!`, `"`,
/// CR, LF and NUL in an argument, `%` or `!` in [path], and a line over
/// [batchLineLimit] characters (UTF-16 units).
String quoteBatchLine(String path, List<String> args) {
  if (path.contains('%') || path.contains('!') || path.contains('"')) {
    throw const UnsafeBatchArgument('path');
  }
  final buffer = StringBuffer('"$path"');
  for (final arg in args) {
    if (RegExp('[%!"\r\n\x00]').hasMatch(arg)) {
      throw const UnsafeBatchArgument('argument');
    }
    var trailing = 0;
    while (trailing < arg.length && arg[arg.length - 1 - trailing] == r'\') {
      trailing++;
    }
    buffer.write(' "$arg${r'\' * trailing}"');
  }
  final line = buffer.toString();
  if (line.length > batchLineLimit) {
    throw const UnsafeBatchArgument('line too long');
  }
  return line;
}

/// Whether [path] names a batch file `cmd.exe` runs.
bool isBatchFile(String path) =>
    RegExp(r'\.(cmd|bat)$', caseSensitive: false).hasMatch(path);

/// The command interpreter: `COMSPEC` when it names a file, else
/// `%SystemRoot%\System32\cmd.exe`.
String commandInterpreter(Map<String, String> env) {
  String? lookup(String key) {
    for (final entry in env.entries) {
      if (entry.key.toUpperCase() == key) return entry.value;
    }
    return null;
  }

  final comspec = lookup('COMSPEC');
  if (comspec != null && File(comspec).existsSync()) return comspec;
  final root = lookup('SYSTEMROOT') ?? r'C:\Windows';
  return '$root\\System32\\cmd.exe';
}

/// Input the launcher cannot hand to a tool whole: a NUL, a lone surrogate, or
/// on Windows a command line past the operating system's limit (D5).
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

/// Units [command] takes as one Windows command line: each item quoted, one
/// space between them, no terminating NUL.
int commandLineUnits(List<String> command) {
  var units = command.length - 1; // the separating spaces
  for (final item in command) {
    units += _quotedLength(item);
  }
  return units;
}

/// Whether a line of [units] visible units is too long for `CreateProcessW`,
/// which takes [windowsCommandLineLimit] units including the terminating NUL.
bool _tooLong(int units, bool countNul) =>
    units + (countNul ? 1 : 0) > windowsCommandLineLimit;

/// Throws [Unrepresentable] (`command line`, named by [name]) when, on Windows
/// ([windows], default: this system), [command] would make a command line past
/// [windowsCommandLineLimit] units. With [countNul] the terminating NUL counts
/// too (a line that is started: 32,766 visible units is the longest); without
/// it the line is the one as given, which keeps today's threshold of 32,767.
void checkCommandLine(
  String name,
  List<String> command, {
  bool? windows,
  bool countNul = false,
}) {
  if (!(windows ?? Platform.isWindows)) return;
  if (_tooLong(commandLineUnits(command), countNul)) {
    throw Unrepresentable(name, 'command line');
  }
}

/// How a bounded launch starts its helper: the helper's own argv, and whether
/// a check this change adds refused the line (D5, C1).
class BoundedLaunchPlan {
  const BoundedLaunchPlan(this.plan, this.helperArgv, this.lineTooLong);

  /// The command's plan, as [planLaunch] gives it.
  final LaunchPlan plan;

  /// The helper's executable and arguments, exactly as started: the helper
  /// command, `--cmdline` for a raw line, `--`, then the plan's command.
  final List<String> helperArgv;

  /// The started line, the raw `cmd.exe` line or the helper's own line is over
  /// the limit with its terminating NUL.
  final bool lineTooLong;
}

/// The helper's argv: [helperCommand], `--cmdline` when [rawLine], `--`, then
/// [command]. The one place it is built, so what is checked is what starts.
List<String> helperArguments(
  List<String> helperCommand,
  bool rawLine,
  List<String> command,
) => [...helperCommand, if (rawLine) '--cmdline', '--', ...command];

/// Plans a bounded launch of [command], whose first item resolved to [path].
///
/// Constraint C1: every bounded launch is planned through this function, which
/// checks the serialized helper argv against the Windows 32,767-unit limit
/// (the terminating NUL included), after [planLaunch] has checked the started
/// line. The checks that existed before, the as-given precheck, a NUL or lone
/// surrogate, the batch payload cap and a resolved native line over 32,767
/// visible units, still throw. A check this change adds (a resolved line of
/// exactly 32,767 units, the raw `cmd.exe` line, the helper line) does not
/// throw: it sets [BoundedLaunchPlan.lineTooLong], and `BoundedRun` returns a
/// failed helper start without spawning anything.
BoundedLaunchPlan planBoundedLaunch(
  String path,
  List<String> command,
  Map<String, String> env,
  List<String> helperCommand, {
  bool? windows,
  bool transport = true,
}) {
  final win = windows ?? Platform.isWindows;
  final plan = planLaunch(
    path,
    command,
    env,
    windows: win,
    transport: transport,
    refuseLongLine: false,
  );
  final argv = helperArguments(helperCommand, plan.rawLine, plan.command);
  final tooLong =
      plan.lineTooLong || (win && _tooLong(commandLineUnits(argv), true));
  return BoundedLaunchPlan(plan, argv, tooLong);
}

/// The plan for [command] once its first item resolved to [path]: a batch
/// file on Windows runs as `cmd.exe /d /s /c "<line>"` ([quoteBatchLine]); a
/// Windows `bash -c` sends its arguments on stdin ([transportFor], unless
/// [transport] is false); anything else starts directly. Throws
/// [UnsafeBatchArgument] for a batch line, and [Unrepresentable] (`command
/// line`, named by `command.first`) for a native Windows command line past
/// [windowsCommandLineLimit] with the resolved [path], before anything starts.
/// Every native launch plan passes through here, so the check lives only here.
LaunchPlan planLaunch(
  String path,
  List<String> command,
  Map<String, String> env, {
  bool? windows,
  bool transport = true,
  bool refuseLongLine = true,
}) {
  final win = windows ?? Platform.isWindows;
  if (win && isBatchFile(path)) {
    final line = quoteBatchLine(path, command.skip(1).toList());
    final shell = commandInterpreter(env);
    final raw = '"$shell" /d /s /c "$line"';
    final tooLong = _tooLong(raw.length, true);
    if (tooLong && refuseLongLine) {
      throw Unrepresentable(command.first, 'command line');
    }
    return LaunchPlan(
      [shell, raw],
      const [],
      rawLine: true,
      lineTooLong: tooLong,
    );
  }
  final resolved = [path, ...command.skip(1)];
  final started = transport
      ? transportFor(resolved, windows: win)
      : Transport(resolved, const []);
  // the line over the limit before this change keeps throwing
  checkCommandLine(command.first, started.command, windows: win);
  final tooLong = win && _tooLong(commandLineUnits(started.command), true);
  if (tooLong && refuseLongLine) {
    throw Unrepresentable(command.first, 'command line');
  }
  return LaunchPlan(started.command, started.stdinBytes, lineTooLong: tooLong);
}
