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
  const LaunchPlan(this.command, this.stdinBytes, {this.rawLine = false});

  /// The command and its arguments. With [rawLine] it is the application and
  /// the exact Windows command line, nothing else.
  final List<String> command;

  /// Bytes to write on the command's stdin right after the go byte.
  final List<int> stdinBytes;

  /// The helper hands [command]'s second item to `CreateProcessW` as it is,
  /// because Dart's own quoting would escape the quotes `cmd.exe` must see.
  final bool rawLine;
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

/// The plan for [command] once its first item resolved to [path]: a batch
/// file on Windows runs as `cmd.exe /d /s /c "<line>"` ([quoteBatchLine]); a
/// Windows `bash -c` sends its arguments on stdin ([transportFor]); anything
/// else starts directly. Throws [UnsafeBatchArgument] before anything starts.
LaunchPlan planLaunch(
  String path,
  List<String> command,
  Map<String, String> env, {
  bool? windows,
}) {
  final win = windows ?? Platform.isWindows;
  if (win && isBatchFile(path)) {
    final line = quoteBatchLine(path, command.skip(1).toList());
    final shell = commandInterpreter(env);
    return LaunchPlan(
      [shell, '"$shell" /d /s /c "$line"'],
      const [],
      rawLine: true,
    );
  }
  final transport = transportFor([path, ...command.skip(1)], windows: win);
  return LaunchPlan(transport.command, transport.stdinBytes);
}
