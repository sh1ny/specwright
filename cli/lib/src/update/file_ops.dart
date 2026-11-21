import 'dart:io';

import 'exclusive_mkdir.dart';

/// The one place `sw update` copies, renames, removes and creates files.
///
/// SPECWRIGHT_UPDATE_KILL_AT and SPECWRIGHT_UPDATE_COUNT are a test seam that
/// ends only sw itself and counts only file operations. Every new file
/// operation in sw update must go through the counting wrapper, or the
/// interruption matrix silently skips it.
///
/// The seam (design D3 of native-cli-update). When `SPECWRIGHT_UPDATE_COUNT`
/// names a file, each operation first appends `<n> <op> <args>` to it, with
/// `<n>` the number of the operation counting from 1 across every run that
/// shares the file (a stage and the swap after it make one sequence). When
/// `SPECWRIGHT_UPDATE_KILL_AT=<n>` is also set, the process ends at once with
/// `exit(137)` at operation `<n>`, after that line is written and before the
/// operation is done: no `finally` runs and nothing else is flushed, as if
/// the process had been killed between two operations. This is the meaning of
/// the n-th counted `mv`, `cp` or `rm` of `scripts/update.sh`'s shims, which
/// counted a call and killed before it ran. Without the count file nothing is
/// logged and nothing is killed, whatever else is set.
///
/// The logged operations are `mkdir -p PATH`, `mkdir PATH` (one directory,
/// for the lock), `cp [-R] SOURCE DEST_DIR`, `mv FROM TO` and `rm -rf PATH`; a
/// recursive copy or remove is one operation. Writing a file's bytes is not one: a journal is
/// written to its temporary file first and renamed with [rename], and the
/// rename is the counted step.
///
/// [environment] and [exitProcess] default to the process environment and
/// `dart:io`'s `exit`; tests pass their own.
class UpdateFileOps {
  UpdateFileOps({
    Map<String, String>? environment,
    void Function(int code)? exitProcess,
  }) : _exit = exitProcess ?? exit {
    final env = environment ?? Platform.environment;
    final count = env[_countVariable];
    if (count != null && count.isNotEmpty) {
      _log = File(count);
      _next = _linesIn(_log!) + 1;
      _killAt = int.tryParse(env[_killVariable] ?? '');
    }
  }

  static const String _countVariable = 'SPECWRIGHT_UPDATE_COUNT';
  static const String _killVariable = 'SPECWRIGHT_UPDATE_KILL_AT';
  static const int _killedStatus = 137;

  final void Function(int code) _exit;
  File? _log;
  int _next = 1;
  int? _killAt;

  /// `mkdir -p path`.
  void mkdir(String path) {
    if (!_before('mkdir -p $path')) return;
    Directory(path).createSync(recursive: true);
  }

  /// `mkdir path`: creates one directory whose parent exists; false when it
  /// cannot (it is there already, or the parent is missing). Of two runs that
  /// call it for one path, one gets true: the update lock is made with it.
  bool mkdirExclusive(String path) {
    if (!_before('mkdir $path')) return false;
    return createDirectoryExclusive(path);
  }

  /// `cp [-R] source destDir`: puts [source], a file or a directory tree,
  /// into the directory [destDir] under its own name.
  void copy(String source, String destDir) {
    final directory =
        FileSystemEntity.typeSync(source, followLinks: false) ==
        FileSystemEntityType.directory;
    if (!_before('cp ${directory ? '-R ' : ''}$source $destDir')) return;
    final target = '$destDir/${_basename(source)}';
    if (directory) {
      _copyTree(Directory(source), Directory(target));
    } else {
      File(source).copySync(target);
    }
  }

  /// `mv from to`: a rename of a file or a directory. A file at [to] is
  /// replaced.
  void rename(String from, String to) {
    if (!_before('mv $from $to')) return;
    switch (FileSystemEntity.typeSync(from, followLinks: false)) {
      case FileSystemEntityType.directory:
        Directory(from).renameSync(to);
      case FileSystemEntityType.link:
        Link(from).renameSync(to);
      default:
        File(from).renameSync(to);
    }
  }

  /// `rm -rf path`: a missing path is no error; a link is removed, not what
  /// it points to.
  void remove(String path) {
    if (!_before('rm -rf $path')) return;
    switch (FileSystemEntity.typeSync(path, followLinks: false)) {
      case FileSystemEntityType.notFound:
        return;
      case FileSystemEntityType.directory:
        Directory(path).deleteSync(recursive: true);
      case FileSystemEntityType.link:
        Link(path).deleteSync();
      default:
        File(path).deleteSync();
    }
  }

  /// [remove] for a leftover nobody needs: a failure to delete it (a file
  /// another process holds, a directory that cannot be listed) is swallowed,
  /// and the leftover is swept later. The caller's own result stands.
  void removeQuietly(String path) {
    try {
      remove(path);
    } on FileSystemException {
      // best effort; the one-hour sweep of a later install takes it
    }
  }

  /// Logs [text] as the next operation; false when the seam ended the run
  /// here (only with an [exitProcess] that returns), so the caller skips it.
  bool _before(String text) {
    final log = _log;
    if (log == null) return true;
    final n = _next++;
    log.writeAsStringSync('$n $text\n', mode: FileMode.append, flush: true);
    if (n == _killAt) {
      _exit(_killedStatus);
      return false;
    }
    return true;
  }
}

int _linesIn(File log) {
  if (!log.existsSync()) return 0;
  return log.readAsLinesSync().where((line) => line.isNotEmpty).length;
}

String _basename(String path) {
  var end = path.length;
  while (end > 1 && (path[end - 1] == '/' || path[end - 1] == r'\')) {
    end--;
  }
  final trimmed = path.substring(0, end);
  final at = trimmed.lastIndexOf(RegExp(r'[/\\]'));
  return at < 0 ? trimmed : trimmed.substring(at + 1);
}

void _copyTree(Directory source, Directory target) {
  target.createSync(recursive: true);
  for (final entry in source.listSync(followLinks: false)) {
    final name = _basename(entry.path);
    final to = '${target.path}/$name';
    if (entry is Directory) {
      _copyTree(entry, Directory(to));
    } else if (entry is Link) {
      Link(to).createSync(entry.targetSync());
    } else if (entry is File) {
      entry.copySync(to);
    }
  }
}
