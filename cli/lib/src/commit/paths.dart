import 'dart:io';

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

/// On Windows, path arguments starting with `/` are converted by fixed rules
/// (design D7), because the stdin handoff skips Git Bash's own argument
/// conversion. No `cygpath` runs and no fstab is read. A path that cannot be
/// converted stops (bad_path, exit 2; fit-subject exit 2) and is never replaced
/// by the unconverted path.
///
/// Returns [path] unchanged when [windows] (default: this OS) is false or the
/// path does not start with `/` (a drive form, a relative path). Otherwise:
/// `/x` or `/x/...` with one drive letter is `X:/...`; `//host/share/...` stays
/// UNC; `/tmp` and `/tmp/...` go under `TEMP`, else `TMP` (Git for Windows'
/// `usertemp` mount); any other `/...` goes under the Git root, which is
/// [bash] without a trailing `\usr\bin\bash.exe` or `\bin\bash.exe`, matched
/// without regard to case. A missing `TEMP`/`TMP` or Git root throws
/// [BadPathException]. [environment] (default: this process's) is where `TEMP`
/// and `TMP` are read.
Future<String> nativePath(
  String path,
  String bash, {
  bool? windows,
  Map<String, String>? environment,
}) async {
  if (!(windows ?? Platform.isWindows) || !path.startsWith('/')) return path;
  final drive = _driveForm.firstMatch(path);
  if (drive != null) return '${drive[1]!.toUpperCase()}:/${drive[2] ?? ''}';
  if (_uncForm.hasMatch(path)) return path;
  final String base;
  final String rest;
  if (path == '/tmp' || path.startsWith('/tmp/')) {
    final env = environment ?? Platform.environment;
    final temp = _first(env['TEMP'], env['TMP']);
    if (temp == null) throw BadPathException(path);
    base = temp;
    rest = path.substring('/tmp'.length);
  } else if (path.startsWith('//')) {
    throw BadPathException(path);
  } else {
    final root = _gitRoot(bash);
    if (root == null) throw BadPathException(path);
    base = root;
    rest = path;
  }
  return '${_trimEnd(base.replaceAll(r'\', '/'))}$rest';
}

/// `/c` or `/c/rest`: one drive letter, then the rest of the path.
final RegExp _driveForm = RegExp(r'^/([A-Za-z])(?:/(.*))?$');

/// `//host/share...`: two slashes, then a name.
final RegExp _uncForm = RegExp(r'^//[^/]');

/// The Git for Windows install root named by [bash], or null.
String? _gitRoot(String bash) {
  final text = bash.replaceAll(r'\', '/');
  final m = RegExp(
    r'^(.+?)/(?:usr/)?bin/bash\.exe$',
    caseSensitive: false,
  ).firstMatch(text);
  return m?[1];
}

String? _first(String? a, String? b) => a != null && a.isNotEmpty
    ? a
    : b != null && b.isNotEmpty
    ? b
    : null;

String _trimEnd(String path) => path.replaceFirst(RegExp(r'/+$'), '');
