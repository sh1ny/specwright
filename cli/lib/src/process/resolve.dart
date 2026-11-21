import 'dart:convert';
import 'dart:io';

import 'package:path/path.dart' as p;

import '../native/libc.dart' as libc;

/// Finds the file `sw run` starts for [name], or null when there is none.
///
/// A name with a path separator is used as given. Otherwise `PATH` is walked,
/// and on Windows each `PATHEXT` extension in order (default
/// `.COM;.EXE;.BAT;.CMD`). [isFile] is replaceable for tests.
///
/// Constraint C9: on POSIX an empty `PATH` entry (leading, trailing or between
/// two colons) is the current directory, searched in its position as the shell
/// and `execvp` search it, and found as `./<name>`. On Windows empty entries
/// are dropped (#202).
///
/// With [workingDirectory] a relative name, and a relative `PATH` entry
/// (including the `.` an empty POSIX entry stands for), is looked for under
/// that directory and the result is the joined path (on POSIX with its `..`
/// kept, as the OS follows links before `..`); nothing is
/// checked against this process's own directory (C11). Without it, relative
/// candidates are checked and returned as they are.
///
/// On POSIX a `PATH` candidate is taken only when [canExecute] accepts it too,
/// so a same-named file the user cannot execute is skipped and the search goes
/// on, as the shell does. [canExecute] defaults to always true when [isFile] is
/// injected, and to the effective-ID check on POSIX otherwise; Windows does not
/// use it. A name with a separator is checked by [isFile] alone.
///
/// Constraint C26: lookup and start stay separate. A candidate that passes
/// lookup and then fails to start (its permission removed in between) is
/// reported as that start failure; no launcher goes on down `PATH` after a
/// failed start.
String? resolveCommand(
  String name,
  Map<String, String> env, {
  bool? windows,
  bool Function(String path)? isFile,
  bool Function(String path)? canExecute,
  String? workingDirectory,
}) {
  final win = windows ?? Platform.isWindows;
  final exists = isFile ?? _isFile;
  final bool Function(String path) executable = win
      ? (_) => true
      : canExecute ?? (isFile != null ? (_) => true : _canExecute);
  final separator = win ? RegExp(r'[\\/]') : RegExp('/');
  final style = win ? p.Context(style: p.Style.windows) : p.posix;
  // A relative candidate is anchored to the working directory when the caller
  // names one. Windows resolves `..` by name, so it is normalised there; POSIX
  // resolves `..` after following a link, so only `.` segments go.
  String anchor(String candidate) {
    if (workingDirectory == null || style.isAbsolute(candidate)) {
      return candidate;
    }
    final joined = style.join(workingDirectory, candidate);
    return win ? style.normalize(joined) : _dropDots(joined);
  }

  if (name.contains(separator)) {
    final found = anchor(name);
    return exists(found) ? found : null;
  }

  final path = _lookup(env, 'PATH', win);
  if (path == null) return null; // no PATH searches nothing, not `.`
  final dirs = path
      .split(win ? ';' : ':')
      .map((d) => win ? d.trim().replaceAll('"', '') : (d.isEmpty ? '.' : d))
      .where((d) => d.isNotEmpty)
      .toList();
  final extensions = win ? _pathExt(_lookup(env, 'PATHEXT', win)) : const [''];
  final hasKnownExtension = win && extensions.contains(_extension(name));
  for (final dir in dirs) {
    final base = dir.endsWith('/') || (win && dir.endsWith(r'\'))
        ? '$dir$name'
        : '$dir${win ? r'\' : '/'}$name';
    if (hasKnownExtension && exists(anchor(base)) && executable(anchor(base))) {
      return anchor(base);
    }
    for (final ext in extensions) {
      final candidate = anchor('$base$ext');
      if (exists(candidate) && executable(candidate)) return candidate;
    }
  }
  return null;
}

/// [path] without its `.` segments and repeated `/`, its `..` kept.
String _dropDots(String path) {
  final kept = path.split('/').where((s) => s.isNotEmpty && s != '.');
  final joined = kept.join('/');
  if (path.startsWith('/')) return '/$joined';
  return joined.isEmpty ? '.' : joined;
}

/// The lower-cased extension of [name] with its dot, or ''.
String _extension(String name) {
  final dot = name.lastIndexOf('.');
  return dot <= 0 ? '' : name.substring(dot).toLowerCase();
}

List<String> _pathExt(String? value) {
  final list = (value == null || value.trim().isEmpty)
      ? '.COM;.EXE;.BAT;.CMD'
      : value;
  return list
      .split(';')
      .map((e) => e.trim().toLowerCase())
      .where((e) => e.isNotEmpty)
      .toList();
}

/// Environment lookup that ignores case on Windows.
String? _lookup(Map<String, String> env, String key, bool windows) {
  if (!windows) return env[key];
  for (final entry in env.entries) {
    if (entry.key.toUpperCase() == key) return entry.value;
  }
  return null;
}

/// The default file check: a regular file, and on POSIX one with an execute
/// bit. It is all a name with a separator gets, so an explicit path the user
/// cannot execute still reaches the start and fails there.
///
/// Constraint C22: POSIX command lookup accepts a `PATH` candidate only when
/// `faccessat(AT_FDCWD, path, X_OK, AT_EACCESS)` succeeds ([_canExecute]).
/// `AT_EACCESS` is required because the start uses the effective IDs, and plain
/// `access` (real IDs) could accept a candidate the user cannot start and skip
/// a runnable one later on `PATH`.
bool _isFile(String path) {
  if (FileSystemEntity.typeSync(path) != FileSystemEntityType.file) {
    return false;
  }
  if (Platform.isWindows) return true;
  return File(path).statSync().mode & 0x49 != 0; // any execute bit
}

bool _canExecute(String path) => libc.canExecuteEffective(utf8.encode(path));
