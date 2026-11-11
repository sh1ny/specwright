import 'dart:convert';
import 'dart:io';

import 'package:path/path.dart' as p;

import '../vcs/codec.dart';

/// What the walk does with links and with `.git` and `.jj` directories. The
/// caller's policy, not the walk's: each caller keeps the handling it had.
enum WalkPolicy {
  /// The VCS walk: links are skipped, and so are directories named `.git` or
  /// `.jj` below the root. A file named `.git` is listed. File sizes are read
  /// and a file that cannot be sized (gone since the listing) is skipped.
  vcs,

  /// The finish walk: nothing is pruned. A link to a directory is listed under
  /// `dirs` and not entered; any other link, a broken one too, is listed under
  /// `files`. A file is listed even when it cannot be sized (size 0).
  finish,
}

/// One directory of a walk. [rel] is its path from the walk root (`''` for the
/// root, `/` separators); [dirs] and [files] are the names inside it, sorted by
/// their UTF-8 bytes; [sizes] holds one size per entry of [files], in the same
/// order.
class WalkDirectory {
  WalkDirectory(this.rel);

  final String rel;
  final List<String> dirs = [];
  final List<String> files = [];
  final List<int> sizes = [];

  @override
  String toString() => '$rel dirs=$dirs files=$files';
}

/// A file a walk found: its path from the walk root (plus the caller's prefix),
/// with `/` separators, and its size in bytes.
class WalkedFile {
  WalkedFile(this.name, this.size);

  final String name;
  final int size;

  @override
  String toString() => '$name ($size)';
}

/// Orders [a] before [b] by the bytes of their UTF-8 encoding, the same on
/// every OS (Dart's own `String.compareTo` orders by UTF-16 code unit, which
/// differs above U+FFFF).
int compareUtf8(String a, String b) =>
    _compareBytes(utf8.encode(a), utf8.encode(b));

int _compareBytes(List<int> a, List<int> b) {
  final n = a.length < b.length ? a.length : b.length;
  for (var i = 0; i < n; i++) {
    if (a[i] != b[i]) return a[i] < b[i] ? -1 : 1;
  }
  return a.length - b.length;
}

/// Lists the tree under [root], top-down and depth first: the root first, then
/// each of its subdirectories in turn. A [root] that is not a directory (or is
/// missing) gives an empty list; a root that is a link to a directory is
/// entered.
///
/// The walk sorts by UTF-8 bytes of the relative path and never descends into a
/// linked directory; whether links are skipped (VCS) or listed (finish:
/// directory links under `dirs`, others under `files`) is the caller's
/// [policy]. A U+FFFD name whose path does not exist, or that another entry of
/// its directory decodes to, is a non-UTF-8 name, reported with U+FFFD because
/// the raw bytes are not exposed (constraint C3).
///
/// The directory is listed with `listSync(followLinks: false)`, which decodes a
/// byte that is not UTF-8 to U+FFFD in the entry's `path` while the entry
/// itself keeps the raw name. A listed name with U+FFFD is therefore checked:
/// the path built from the name (not followed through links) must exist, and no
/// other entry of the directory may have the same name. Otherwise the walk
/// throws [NotUtf8] showing the path from the root, behind [prefix], with
/// U+FFFD in place of each invalid sequence. A directory that cannot be listed
/// is left empty and the walk goes on. The listing is a snapshot: a name that
/// vanishes after it is skipped, except that a U+FFFD name which vanishes
/// before its check cannot be told from a non-UTF-8 one and throws.
List<WalkDirectory> walkTree(
  String root, {
  WalkPolicy policy = WalkPolicy.vcs,
  String prefix = '',
}) {
  final top = Directory(root);
  if (!top.existsSync()) return [];
  final walk = <WalkDirectory>[];
  _visit(top, '', policy, prefix, walk);
  return walk;
}

/// The files of [walkTree], in one list sorted by the UTF-8 bytes of the whole
/// path from [root]; each name is behind [prefix] (`prefix/` and the path, or
/// the path alone when [prefix] is empty).
List<WalkedFile> walkFiles(
  String root, {
  WalkPolicy policy = WalkPolicy.vcs,
  String prefix = '',
}) {
  final keyed = <(List<int>, WalkedFile)>[];
  for (final dir in walkTree(root, policy: policy, prefix: prefix)) {
    for (var i = 0; i < dir.files.length; i++) {
      final rel = dir.rel.isEmpty ? dir.files[i] : '${dir.rel}/${dir.files[i]}';
      final name = prefix.isEmpty ? rel : '$prefix/$rel';
      keyed.add((utf8.encode(name), WalkedFile(name, dir.sizes[i])));
    }
  }
  keyed.sort((a, b) => _compareBytes(a.$1, b.$1));
  return [for (final (_, file) in keyed) file];
}

class _Entry {
  _Entry(this.name, this.bytes, this.entity);

  final String name;
  final List<int> bytes;
  final FileSystemEntity entity;
}

void _visit(
  Directory dir,
  String rel,
  WalkPolicy policy,
  String prefix,
  List<WalkDirectory> walk,
) {
  final node = WalkDirectory(rel);
  walk.add(node);
  final List<FileSystemEntity> listed;
  try {
    listed = dir.listSync(followLinks: false);
  } on FileSystemException {
    return;
  }
  final entries = [
    for (final e in listed)
      _Entry(p.basename(e.path), utf8.encode(p.basename(e.path)), e),
  ]..sort((a, b) => _compareBytes(a.bytes, b.bytes));

  final seen = <String, int>{};
  for (final e in entries) {
    seen[e.name] = (seen[e.name] ?? 0) + 1;
  }
  for (final e in entries) {
    if (!e.name.contains('\u{fffd}')) continue;
    final built = '${dir.path}${Platform.pathSeparator}${e.name}';
    final missing =
        FileSystemEntity.typeSync(built, followLinks: false) ==
        FileSystemEntityType.notFound;
    if (missing || seen[e.name]! > 1) {
      final path = rel.isEmpty ? e.name : '$rel/${e.name}';
      throw NotUtf8('file name', prefix.isEmpty ? path : '$prefix/$path');
    }
  }

  final subdirectories = <Directory>[];
  for (final e in entries) {
    final entity = e.entity;
    switch (entity) {
      case Directory():
        if (policy == WalkPolicy.vcs && (e.name == '.git' || e.name == '.jj')) {
          continue;
        }
        node.dirs.add(e.name);
        subdirectories.add(entity);
      case Link():
        if (policy == WalkPolicy.vcs) continue;
        if (FileSystemEntity.isDirectorySync(entity.path)) {
          node.dirs.add(e.name);
        } else {
          node.files.add(e.name);
          node.sizes.add(0);
        }
      default:
        var size = 0;
        try {
          size = (entity as File).lengthSync();
        } on FileSystemException {
          if (policy == WalkPolicy.vcs) continue;
        }
        node.files.add(e.name);
        node.sizes.add(size);
    }
  }
  for (final sub in subdirectories) {
    final name = p.basename(sub.path);
    _visit(sub, rel.isEmpty ? name : '$rel/$name', policy, prefix, walk);
  }
}
