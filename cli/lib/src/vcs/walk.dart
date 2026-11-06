import 'dart:io';

import 'codec.dart';
import 'tool_runner.dart';

/// A regular file the walk found: its name as `vcs.sh` reports it (relative to
/// the repo, `/` separators, invalid bytes as surrogate escapes) and its size.
class WalkedFile {
  WalkedFile(this.name, this.size);

  final String name;
  final int size;

  @override
  String toString() => '$name ($size)';
}

/// `os.walk(os.path.join(repo, path))` with `.git` and `.jj` directories
/// pruned (`vcs.sh:933-943`), as `(name, size)` pairs in `os.walk` order for
/// every regular, non-link file. The caller applies `listed` and the size
/// limit.
///
/// Names come from `find -print0` run through the transport (never
/// `Directory.list()`, whose entries expose only a lossy `path`): `find
/// ROOT/ -mindepth 1 ( -type d ( -name .git -o -name .jj ) -prune ) -o -type
/// f -print0`, started as `BASH -c 'command -p find "$@"'` so that the system
/// `find` is used, not one on the inherited `PATH`. Every complete
/// NUL-terminated record is used and `find`'s exit status and stderr are
/// ignored, as `os.walk` skips a directory it cannot list; a last record with
/// no NUL is dropped. A tool run that cannot start (a missing `bash` or repo)
/// gives no records, as `vcs.sh`'s `run` gave no output.
Future<List<WalkedFile>> walkFiles(
  String bash,
  String repo,
  String path, {
  Map<String, String>? environment,
}) async {
  final windows = Platform.isWindows;
  var findRoot = walkRoot(repo, path);
  if (windows) findRoot = findRoot.replaceAll(r'\', '/');
  if (!findRoot.endsWith('/')) findRoot = '$findRoot/';
  final result = await runTool(bash, repo, [
    // The bash handed in, not the name `bash`: `exec` looks a bare name up on
    // the inherited PATH, where Windows puts System32's WSL launcher
    // (bash.exe) ahead of Git's.
    bash,
    '-c',
    'command -p find "\$@"',
    'vcs',
    findRoot,
    '-mindepth',
    '1',
    '(',
    '-type',
    'd',
    '(',
    '-name',
    '.git',
    '-o',
    '-name',
    '.jj',
    ')',
    '-prune',
    ')',
    '-o',
    '-type',
    'f',
    '-print0',
  ], environment: environment);
  final out = result.stdout;
  final records = <String>[];
  var start = 0;
  for (var i = 0; i < out.length; i++) {
    if (out[i] == 0) {
      records.add(decodeEscaped(out.sublist(start, i)));
      start = i + 1;
    }
  }
  return statRecords(walkOrder(findRoot, records), repo);
}

/// For each record (an absolute name as `find` printed it), in order, on the
/// name's raw bytes only: a link (`Link.fromRawPath(..).existsSync()`) is
/// skipped; so is a name for which `File.fromRawPath(..).existsSync()` is false
/// (gone, a directory, a FIFO or another non-regular file); the size is
/// `File.fromRawPath(..).lengthSync()`, and a name for which that throws is
/// skipped. `File.statSync` is never used: it stats the lossy `path` string and
/// misses a name that is not valid UTF-8. The reported name is
/// [relpathText]`(record, repo)`.
List<WalkedFile> statRecords(List<String> records, String repo) {
  final found = <WalkedFile>[];
  for (final record in records) {
    final bytes = encodeEscaped(record);
    if (Link.fromRawPath(bytes).existsSync()) continue;
    final file = File.fromRawPath(bytes);
    try {
      if (!file.existsSync()) continue;
      found.add(WalkedFile(relpathText(record, repo), file.lengthSync()));
    } on FileSystemException {
      continue;
    }
  }
  return found;
}

class _Node {
  final List<String> files = [];
  final Map<String, _Node> children = {};
}

/// Regroups `find`'s depth-first [records] into `os.walk`'s order: within each
/// directory its own files first, in the order `find` printed them, then each
/// child directory's subtree, in the order its first record appeared. [root]
/// is the `find` start path with its trailing `/`; a record that does not
/// start with it is kept as one name.
List<String> walkOrder(String root, List<String> records) {
  final top = _Node();
  for (final record in records) {
    final rel = record.startsWith(root)
        ? record.substring(root.length)
        : record;
    final parts = rel.split('/');
    var node = top;
    for (var i = 0; i < parts.length - 1; i++) {
      node = node.children.putIfAbsent(parts[i], _Node.new);
    }
    node.files.add(record);
  }
  final ordered = <String>[];
  void emit(_Node node) {
    ordered.addAll(node.files);
    node.children.values.forEach(emit);
  }

  emit(top);
  return ordered;
}

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

(String, List<String>) _normalize(String path, bool windows) {
  var drive = '';
  var rest = path;
  if (windows) {
    (drive, rest) = _splitDrive(path.replaceAll('/', r'\'));
    rest = rest;
  }
  final rooted = windows ? rest.startsWith(r'\') : rest.startsWith('/');
  final parts = rest.split(windows ? r'\' : '/');
  final out = <String>[];
  for (final part in parts) {
    if (part.isEmpty || part == '.') continue;
    if (part == '..') {
      if (out.isNotEmpty && out.last != '..') {
        out.removeLast();
      } else if (!rooted) {
        out.add('..');
      }
    } else {
      out.add(part);
    }
  }
  return (drive, out);
}

/// `os.path.relpath(full, repo)` followed by `path_text` (`\` to `/`), ported
/// lexically on the escaped strings: both paths are normalised (repeated
/// separators and `.` and `..` components collapsed; on Windows `\` and `/` are
/// both separators and case is ignored when comparing), the common leading
/// components dropped, and `..` added for what is left of [repo]. A different
/// Windows drive is a [StateError], as Python raises `ValueError`.
String relpathText(String full, String repo, {bool? windows}) {
  final win = windows ?? Platform.isWindows;
  final (pathDrive, path) = _normalize(full, win);
  final (startDrive, start) = _normalize(repo, win);
  String key(String s) => win ? s.toLowerCase() : s;
  if (win && key(pathDrive) != key(startDrive)) {
    throw StateError(
      "path is on mount '$pathDrive', start on mount '$startDrive'",
    );
  }
  var i = 0;
  while (i < path.length && i < start.length && key(path[i]) == key(start[i])) {
    i++;
  }
  final rel = [...List.filled(start.length - i, '..'), ...path.sublist(i)];
  if (rel.isEmpty) return '.';
  return rel.join(win ? r'\' : '/').replaceAll(r'\', '/');
}
