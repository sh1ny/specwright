import 'dart:io';

import '../vcs/codec.dart';
import '../vcs/tool_runner.dart';

/// One folder `os.walk` yields: [rel] is its path from the walk root (`''` for
/// the root, `/` separators), [path] the root and [rel] joined with `/`, and
/// [dirs] and [files] the names inside it. Every string is
/// [decodeEscaped] text, so [encodeEscaped] gives back the original bytes.
class WalkDirectory {
  WalkDirectory(this.path, this.rel, this.dirs, this.files);

  final String path;
  final String rel;
  final List<String> dirs;
  final List<String> files;

  @override
  String toString() => '$rel dirs=$dirs files=$files';
}

/// One entry `find` listed, classified by a stat that follows links:
/// [isDir] is true for a folder and for a link to one; [isLink] says it is a
/// link (a linked folder is listed in `dirs` and not entered).
class WalkRecord {
  WalkRecord(this.name, {required this.isDir, required this.isLink});

  /// The name as `find` printed it: the root, then the path below it.
  final String name;
  final bool isDir;
  final bool isLink;
}

/// The complete NUL-terminated records of [out], decoded with
/// [decodeEscaped]. A last record with no NUL is dropped.
List<String> splitRecords(List<int> out) {
  final records = <String>[];
  var start = 0;
  for (var i = 0; i < out.length; i++) {
    if (out[i] == 0) {
      records.add(decodeEscaped(out.sublist(start, i)));
      start = i + 1;
    }
  }
  return records;
}

class _Node {
  _Node(this.rel);

  final String rel;
  final List<String> dirs = [];
  final List<String> files = [];
}

/// Regroups `find`'s depth-first [records] under [root] (the `find` start path,
/// with its trailing `/`) into `os.walk`'s top-down order: the root first, and
/// for each folder its files and its subfolders in listing order, then each
/// subfolder in turn, depth first. A linked folder is in `dirs` and has no
/// entry of its own. A record that does not start with [root], or whose folder
/// was not listed, is dropped.
List<WalkDirectory> groupWalk(String root, List<WalkRecord> records) {
  final nodes = <String, _Node>{'': _Node('')};
  for (final record in records) {
    if (!record.name.startsWith(root)) continue;
    final rel = record.name.substring(root.length);
    final slash = rel.lastIndexOf('/');
    final parent = nodes[slash < 0 ? '' : rel.substring(0, slash)];
    if (parent == null) continue;
    final leaf = rel.substring(slash + 1);
    if (record.isDir) {
      parent.dirs.add(leaf);
      if (!record.isLink) nodes[rel] = _Node(rel);
    } else {
      parent.files.add(leaf);
    }
  }
  var base = root;
  while (base.length > 1 && base.endsWith('/')) {
    base = base.substring(0, base.length - 1);
  }
  final walk = <WalkDirectory>[];
  void emit(_Node node) {
    walk.add(
      WalkDirectory(
        node.rel.isEmpty ? base : '$base/${node.rel}',
        node.rel,
        node.dirs,
        node.files,
      ),
    );
    for (final name in node.dirs) {
      final child = nodes[node.rel.isEmpty ? name : '${node.rel}/$name'];
      if (child != null) emit(child);
    }
  }

  emit(nodes['']!);
  return walk;
}

/// `os.walk(root)` (top-down, links not followed) on [decodeEscaped] strings;
/// [root] is an absolute path. Nothing is pruned.
///
/// Names come from `find ROOT/ -mindepth 1 -print0`, run through the
/// transport as `BASH -c 'command -p find "$@"'` as the VCS walker starts it,
/// never from `Directory.list()`, whose entries expose only a lossy `path`.
/// Each name is classified by a stat on its raw bytes (`Directory.fromRawPath(
/// ..).existsSync()` follows links; `Link.fromRawPath(..).existsSync()` does
/// not), so a name that is not valid UTF-8 is still found. `find` exit status
/// and stderr are ignored: a folder it could not list has no records below it,
/// as `os.walk` skips a folder it cannot list. A [root] that is not a folder
/// gives an empty list, as `os.walk` yields nothing for it.
Future<List<WalkDirectory>> walkTree(
  String bash,
  String root, {
  Map<String, String>? environment,
}) async {
  if (!Directory.fromRawPath(encodeEscaped(root)).existsSync()) return [];
  var findRoot = Platform.isWindows ? root.replaceAll(r'\', '/') : root;
  if (!findRoot.endsWith('/')) findRoot = '$findRoot/';
  final result = await runTool(bash, root, [
    // The bash handed in, not the name `bash` (see the VCS walker).
    bash,
    '-c',
    'command -p find "\$@"',
    'finish',
    findRoot,
    '-mindepth',
    '1',
    '-print0',
  ], environment: environment);
  final records = <WalkRecord>[];
  for (final name in splitRecords(result.stdout)) {
    final raw = encodeEscaped(name);
    records.add(
      WalkRecord(
        name,
        isDir: Directory.fromRawPath(raw).existsSync(),
        isLink: Link.fromRawPath(raw).existsSync(),
      ),
    );
  }
  return groupWalk(findRoot, records);
}
