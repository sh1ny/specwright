import 'dart:io';

import '../vcs/codec.dart';
import '../vcs/tool_runner.dart';

/// A path argument could not be converted to a native path (design D9). The
/// callers stop: task-cover prints `"error": "bad_path"` and exits 2,
/// fit-subject prints `fit-subject.sh: could not convert path: <path>` on
/// stderr and exits 2. [path] is the argument as given.
class BadPathException implements Exception {
  BadPathException(this.path);

  final String path;

  @override
  String toString() => 'could not convert path: $path';
}

/// On Windows, path arguments starting with `/` are converted with `cygpath -m`
/// through the handoff's bash before any use, because the stdin handoff skips
/// Git Bash's own argument conversion. A failed conversion stops (bad_path,
/// exit 2; fit-subject exit 2) and is never replaced by the unconverted path.
///
/// Returns [path] unchanged when [windows] (default: this OS) is false or the
/// path does not start with `/` (a drive form, a relative path): nothing runs.
/// Otherwise runs `cygpath -m -- <path>` with [bash] and returns its output
/// without the trailing newline: the drive form (`C:/Users/x/m.txt`) or the
/// UNC form (`//server/share/m.txt`). A non-zero exit, empty output or output
/// that is neither absolute form throws [BadPathException]. [environment]
/// replaces the child's environment (tests put a stub `cygpath` first on PATH).
Future<String> nativePath(
  String path,
  String bash, {
  bool? windows,
  Map<String, String>? environment,
}) async {
  if (!(windows ?? Platform.isWindows) || !path.startsWith('/')) return path;
  final result = await runTool(Directory.current.path, [
    'cygpath',
    '-m',
    '--',
    path,
  ], environment: environment);
  if (result.exitCode != 0) throw BadPathException(path);
  var out = decodeEscaped(result.stdout);
  if (out.endsWith('\n')) out = out.substring(0, out.length - 1);
  if (out.endsWith('\r')) out = out.substring(0, out.length - 1);
  if (!_absoluteNative.hasMatch(out)) throw BadPathException(path);
  return out;
}

/// A drive form (`C:/x`) or a UNC form (`//server/share`).
final RegExp _absoluteNative = RegExp(r'^(?:[A-Za-z]:/|//[^/])');
