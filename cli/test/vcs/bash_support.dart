import 'dart:io';

/// Git Bash on Windows (usr\bin\bash.exe, never System32's WSL launcher), any
/// bash elsewhere; null when none is installed. Mirrors evals/bashexe.py.
String? findBash() {
  if (!Platform.isWindows) {
    for (final dir in (Platform.environment['PATH'] ?? '').split(':')) {
      final f = File('$dir/bash');
      if (dir.isNotEmpty && f.existsSync()) return f.path;
    }
    return null;
  }
  final env = Platform.environment;
  final candidates = <String>[
    ?env['GIT_BASH'],
    ?_under(env['SCOOP'], r'apps\git\current'),
    ?_under(env['USERPROFILE'], r'scoop\apps\git\current'),
    ?_under(env['ProgramFiles'], 'Git'),
    ?_under(env['ProgramFiles(x86)'], 'Git'),
    ?_under(env['LOCALAPPDATA'], r'Programs\Git'),
  ];
  for (final c in candidates) {
    if (File(c).existsSync()) return c;
  }
  final systemRoot = (env['SystemRoot'] ?? r'C:\Windows').toLowerCase();
  for (final dir in (env['PATH'] ?? '').split(';')) {
    final f = File('$dir\\bash.exe');
    final low = f.path.toLowerCase();
    if (dir.isEmpty ||
        !f.existsSync() ||
        low.startsWith(systemRoot) ||
        low.contains('windowsapps')) {
      continue;
    }
    // Git's bin\bash.exe is a launcher that reorders PATH; prefer usr\bin.
    final usr = File('$dir\\..\\usr\\bin\\bash.exe');
    return usr.existsSync() ? usr.absolute.path : f.path;
  }
  return null;
}

String? _under(String? root, String rel) =>
    root == null || root.isEmpty ? null : '$root\\$rel\\usr\\bin\\bash.exe';
