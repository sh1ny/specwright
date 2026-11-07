import 'dart:io';

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
String? resolveCommand(
  String name,
  Map<String, String> env, {
  bool? windows,
  bool Function(String path)? isFile,
}) {
  final win = windows ?? Platform.isWindows;
  final exists = isFile ?? _isFile;
  final separator = win ? RegExp(r'[\\/]') : RegExp('/');
  if (name.contains(separator)) return exists(name) ? name : null;

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
    if (hasKnownExtension && exists(base)) return base;
    for (final ext in extensions) {
      final candidate = '$base$ext';
      if (exists(candidate)) return candidate;
    }
  }
  return null;
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

bool _isFile(String path) {
  if (FileSystemEntity.typeSync(path) != FileSystemEntityType.file) {
    return false;
  }
  if (Platform.isWindows) return true;
  return File(path).statSync().mode & 0x49 != 0; // any execute bit
}
