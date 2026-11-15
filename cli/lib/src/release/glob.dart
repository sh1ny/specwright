import 'dart:io';

import 'package:path/path.dart' as p;

import 'stop.dart';

/// A version-file glob over whole relative paths with `/` separators: `*` and
/// `?` stop at `/`, `**/` spans any number of directories (also none), a final
/// `**` segment matches every path below, and `[...]` is a class (`[!...]` and
/// `[^...]` negate it).
///
/// The work-tree glob skips dot-names under wildcards, while the commit glob
/// matches them: kept from the script, not a goal.
class VersionGlob {
  VersionGlob(this.pattern) : _regex = _compile(pattern);

  final String pattern;
  final RegExp _regex;

  /// True when [path] holds a wildcard, so it is a glob and not one file.
  static bool hasGlob(String path) => path.contains(RegExp(r'[*?\[]'));

  /// True when the whole of [path] matches the glob.
  bool matches(String path) => _regex.hasMatch(path);

  static RegExp _compile(String glob) {
    final out = StringBuffer();
    var i = 0;
    while (i < glob.length) {
      final c = glob[i];
      final close = i + 2 > glob.length ? -1 : glob.indexOf(']', i + 2);
      if (glob.startsWith('**/', i)) {
        out.write('(?:.*/)?');
        i += 3;
        continue;
      } else if (i + 2 == glob.length &&
          glob.startsWith('**', i) &&
          (i == 0 || glob[i - 1] == '/')) {
        // a final `**` segment spans every name below, files in nested
        // directories too, as the script's recursive glob did
        out.write('.+');
        i += 2;
        continue;
      } else if (c == '*') {
        out.write('[^/]*');
      } else if (c == '?') {
        out.write('[^/]');
      } else if (c == '[' && close > 0) {
        var body = glob.substring(i + 1, close);
        final negated = body.startsWith('!') || body.startsWith('^');
        if (negated) body = body.substring(1);
        out.write('[${negated ? '^' : ''}${body.replaceAll(r'\', r'\\')}]');
        i = close;
      } else {
        out.write(RegExp.escape(c));
      }
      i++;
    }
    return RegExp('^$out\$', unicode: true, dotAll: true);
  }
}

/// The files of the work tree under [root] that match [pattern], as sorted
/// relative paths with `/` separators. A path with no wildcard names one file.
/// A wildcard segment, and every directory a `**` segment spans, skips a name
/// that starts with `.` unless the segment itself starts with `.`; a literal
/// segment matches it. A link at any path segment of a match stops with
/// `bad_version_files`.
List<String> workTreeFiles(String root, String pattern) {
  final segments = pattern.split('/');
  final hits = <String>{};

  List<String> names(String dir) {
    final out = [
      for (final e in Directory(dir).listSync(followLinks: false))
        p.basename(e.path),
    ];
    return out..sort();
  }

  void walk(String rel, int k) {
    final dir = rel.isEmpty ? root : p.join(root, rel);
    final segment = segments[k];
    final last = k == segments.length - 1;
    String child(String name) => rel.isEmpty ? name : '$rel/$name';
    if (segment == '**' && last) {
      // every file below, in nested directories too; dot-names are skipped
      void all(String at) {
        final full = at.isEmpty ? root : p.join(root, at);
        for (final name in names(full)) {
          if (name.startsWith('.')) continue;
          final path = at.isEmpty ? name : '$at/$name';
          final entity = p.join(root, path);
          if (FileSystemEntity.isFileSync(entity)) {
            hits.add(path);
          } else if (FileSystemEntity.isDirectorySync(entity) &&
              !FileSystemEntity.isLinkSync(entity)) {
            all(path);
          }
        }
      }

      all(rel);
      return;
    }
    if (segment == '**' && !last) {
      walk(rel, k + 1);
      for (final entity in Directory(dir).listSync(followLinks: false)) {
        final name = p.basename(entity.path);
        if (entity is Directory && !name.startsWith('.')) walk(child(name), k);
      }
      return;
    }
    final Iterable<String> picked;
    if (VersionGlob.hasGlob(segment)) {
      final glob = VersionGlob(segment);
      picked = names(dir).where(
        (n) =>
            (!n.startsWith('.') || segment.startsWith('.')) && glob.matches(n),
      );
    } else {
      picked = [segment];
    }
    for (final name in picked) {
      final path = child(name);
      final full = p.join(root, path);
      if (last) {
        if (FileSystemEntity.isFileSync(full)) hits.add(path);
      } else if (FileSystemEntity.isDirectorySync(full)) {
        walk(path, k + 1);
      }
    }
  }

  walk('', 0);
  final found = hits.toList()..sort();
  for (final rel in found) {
    _refuseLinks(root, pattern, rel);
  }
  return found;
}

void _refuseLinks(String root, String pattern, String rel) {
  var current = root;
  for (final segment in rel.split('/')) {
    current = p.join(current, segment);
    if (!FileSystemEntity.isLinkSync(current)) continue;
    final real = Directory(root).resolveSymbolicLinksSync();
    final target = File(p.join(root, rel)).resolveSymbolicLinksSync();
    if (!p.isWithin(real, target)) {
      throw ReleaseStop(
        'bad_version_files',
        "release.version_files entry '$pattern' reaches $rel through a symlink "
            'outside the repository',
      );
    }
    throw ReleaseStop(
      'bad_version_files',
      "release.version_files entry '$pattern' reaches $rel through a symlink; "
          'git stores a link as its text, so status and publish could not read '
          'the version at a commit. List the file the link points to instead',
    );
  }
}

/// The names of a commit tree (from `git ls-tree -r`) that match [pattern],
/// sorted. [links] holds the names stored as symlinks: a matching one stops
/// with `bad_version_files`, naming [label] (for example `commit abc123`).
List<String> commitFiles(
  String pattern,
  List<String> names,
  Set<String> links,
  String label,
) {
  final List<String> hits;
  if (!VersionGlob.hasGlob(pattern)) {
    hits = names.contains(pattern) ? [pattern] : [];
  } else {
    final glob = VersionGlob(pattern);
    hits = names.where(glob.matches).toList()..sort();
  }
  for (final name in hits) {
    if (links.contains(name)) {
      throw ReleaseStop(
        'bad_version_files',
        "release.version_files entry '$pattern' matches $name, a symlink at "
            '$label; git stores a link as its text, so no version can be read '
            'there. List the file the link points to instead',
      );
    }
  }
  return hits;
}
