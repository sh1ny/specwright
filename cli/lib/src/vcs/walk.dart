import 'dart:io';

import 'package:path/path.dart' as p;

/// `os.path.join(repo, path)` on the escaped strings (`ntpath.join` when
/// [windows]): an absolute [path] replaces [repo].
String walkRoot(String repo, String path, {bool? windows}) {
  if (!(windows ?? Platform.isWindows)) {
    if (path.startsWith('/')) return path;
    if (repo.isEmpty || repo.endsWith('/')) return '$repo$path';
    return '$repo/$path';
  }
  final (repoDrive, repoRest) = _splitDrive(repo);
  final (pathDrive, pathRest) = _splitDrive(path);
  bool isSep(String s) => s.startsWith(r'\') || s.startsWith('/');
  if (pathRest.isNotEmpty && isSep(pathRest)) {
    if (pathDrive.isNotEmpty || repoDrive.isEmpty) return path;
    return '$repoDrive$pathRest';
  }
  if (pathDrive.isNotEmpty &&
      pathDrive.toLowerCase() != repoDrive.toLowerCase()) {
    return path;
  }
  final tail = pathDrive.isNotEmpty ? pathRest : path;
  if (repo.isEmpty) return tail;
  final last = repo[repo.length - 1];
  if (last == r'\' || last == '/' || last == ':') return '$repo$tail';
  return '$repo\\$tail';
}

(String, String) _splitDrive(String p) {
  if (p.length >= 2 && p[1] == ':') return (p.substring(0, 2), p.substring(2));
  return ('', p);
}

/// The path [full] relative to [repo], both absolute, with `/` separators
/// (on Windows both separators and any letter case match, as `path`'s windows
/// style compares them).
///
/// A relative path across Windows drives stays an error and never becomes an
/// accepted path: `path` returns the other drive's absolute path, and this
/// throws a [StateError] instead of passing it on (C9).
String relpathText(String full, String repo, {bool? windows}) {
  final win = windows ?? Platform.isWindows;
  final ctx = p.Context(style: win ? p.Style.windows : p.Style.posix);
  final rel = ctx.relative(full, from: repo);
  if (ctx.isAbsolute(rel)) {
    throw StateError("path $full is on another drive than $repo");
  }
  return rel.replaceAll(r'\', '/');
}
