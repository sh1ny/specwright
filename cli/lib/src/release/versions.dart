import 'dart:convert';
import 'dart:io';
import 'dart:math';
import 'dart:typed_data';

import 'package:path/path.dart' as p;

import '../fs/link.dart' show replaceFile;
import '../process/launch.dart';
import 'glob.dart';
import 'settings.dart';
import 'stop.dart';

/// Where version files are read: the working tree or one commit.
abstract class VersionTree {
  /// How a stop names the tree: `the working tree` or `commit <12 hex>`.
  String get label;

  /// The files [pattern] matches, sorted relative paths; stops with
  /// `bad_version_files` for a link.
  Future<List<String>> files(String pattern);

  /// The bytes of each of [paths]; a file missing at a commit reads as empty.
  Future<Map<String, Uint8List>> readAll(Iterable<String> paths);
}

/// The working tree of the repository at [root].
class WorkTree implements VersionTree {
  WorkTree(this.root);

  final String root;

  @override
  final String label = 'the working tree';

  @override
  Future<List<String>> files(String pattern) async =>
      workTreeFiles(root, pattern);

  @override
  Future<Map<String, Uint8List>> readAll(Iterable<String> paths) async => {
    for (final path in paths) path: File(p.join(root, path)).readAsBytesSync(),
  };
}

/// The tree of one [commit] of the repository at [root], read through local
/// `git ls-tree` and one `git cat-file --batch` per [readAll]. A history walk
/// can use [catBlobs] to read many commits in one batch.
class CommitTree implements VersionTree {
  CommitTree(this.root, this.commit)
    : label = 'commit ${commit.substring(0, min(12, commit.length))}';

  final String root;
  final String commit;

  @override
  final String label;

  List<String>? _names;
  final Set<String> _links = {};

  /// Every file name of the commit.
  Future<List<String>> names() async {
    final cached = _names;
    if (cached != null) return cached;
    final r = await _git(root, ['ls-tree', '-r', '-z', commit]);
    if (r.exitCode != 0) {
      throw ReleaseStop(
        'git_failed',
        'git ls-tree failed at $commit: ${_text(r.stderr)}',
        code: 3,
      );
    }
    final names = <String>[];
    for (final row in _lossy(r.stdout).split('\x00')) {
      final tab = row.indexOf('\t');
      if (tab < 0) continue;
      final name = row.substring(tab + 1);
      names.add(name);
      if (row.startsWith('120000 ')) _links.add(name);
    }
    return _names = names;
  }

  @override
  Future<List<String>> files(String pattern) async =>
      commitFiles(pattern, await names(), _links, label);

  @override
  Future<Map<String, Uint8List>> readAll(Iterable<String> paths) async {
    final list = paths.toList();
    final blobs = await catBlobs(root, [for (final f in list) '$commit:$f']);
    return {
      for (var i = 0; i < list.length; i++) list[i]: blobs[i] ?? Uint8List(0),
    };
  }
}

/// The contents of each `<commit>:<path>` spec through one `git cat-file
/// --batch` in [root], null for a missing object. Local git, no deadline.
Future<List<Uint8List?>> catBlobs(String root, List<String> specs) async {
  if (specs.isEmpty) return [];
  final r = await _git(root, [
    'cat-file',
    '--batch',
  ], input: utf8.encode('${specs.join('\n')}\n'));
  if (r.exitCode != 0) {
    throw ReleaseStop(
      'git_failed',
      'git cat-file failed: ${_text(r.stderr)}',
      code: 3,
    );
  }
  final buffer = r.stdout;
  var pos = 0;
  final out = <Uint8List?>[];
  for (var i = 0; i < specs.length; i++) {
    final nl = buffer.indexOf(0x0a, pos);
    final head = _lossy(buffer.sublist(pos, nl)).split(' ');
    pos = nl + 1;
    if (head.last == 'missing' || head.length < 3) {
      out.add(null);
      continue;
    }
    final size = int.parse(head[2]);
    out.add(Uint8List.sublistView(buffer, pos, pos + size));
    pos += size + 1;
  }
  return out;
}

Future<LaunchResult> _git(String root, List<String> args, {List<int>? input}) =>
    launch(['git', ...args], cwd: root, input: input);

String _lossy(List<int> bytes) => utf8.decode(bytes, allowMalformed: true);

String _text(List<int> bytes) => _lossy(bytes).trim();

/// One version match: the captured value and its span in the text of the file
/// as [VersionFile.text] decodes it.
class VersionHit {
  VersionHit(this.value, this.start, this.end);

  final String value;
  final int start;
  final int end;
}

/// One entry's matches in one file.
class VersionFile {
  VersionFile(this.file, this.raw, VersionEntry entry) {
    text = _lossy(raw);
    hits = [
      for (final m in entry.located.allMatches(text))
        VersionHit(m.group(1)!, m[2]!.length, m[3]!.length),
    ];
  }

  final String file;
  final Uint8List raw;

  /// The file read lossily as UTF-8 (a malformed byte is U+FFFD; a leading
  /// byte order mark is dropped). A multiline `$` matches before a `\r`, so
  /// CRLF text matches as it is and the spans index [text] itself.
  late final String text;
  late final List<VersionHit> hits;

  /// The byte offset in [raw] of the [text] offset, for a valid UTF-8 file.
  int byteOffset(int textOffset) {
    final bom =
        raw.length >= 3 && raw[0] == 0xef && raw[1] == 0xbb && raw[2] == 0xbf
        ? 3
        : 0;
    return bom + utf8.encode(text.substring(0, textOffset)).length;
  }
}

/// Every entry applied to a tree: the matches, and the problems found, as the
/// JSON objects a `version_files_invalid` stop lists (`kind` `no_file` or
/// `match_count`, plus a `text`).
class VersionRead {
  VersionRead(this.tree, this.files, this.problems);

  final VersionTree tree;
  final List<VersionFile> files;
  final List<Map<String, Object?>> problems;
}

/// Applies every entry to [tree]. A file counts as a problem when an entry
/// matches no file, or a pattern does not match a file exactly once.
Future<VersionRead> readVersions(
  VersionTree tree,
  List<VersionEntry> entries,
) async {
  final problems = <Map<String, Object?>>[];
  final perEntry = <(VersionEntry, List<String>)>[];
  for (final entry in entries) {
    final found = await tree.files(entry.path);
    if (found.isEmpty) {
      problems.add({
        'kind': 'no_file',
        'entry': entry.path,
        'text':
            "version_files entry '${entry.path}' matches no file in ${tree.label}",
      });
    }
    perEntry.add((entry, found));
  }
  final wanted = {for (final (_, found) in perEntry) ...found}.toList()..sort();
  final data = await tree.readAll(wanted);
  final files = <VersionFile>[];
  for (final (entry, found) in perEntry) {
    for (final file in found) {
      final read = VersionFile(file, data[file]!, entry);
      files.add(read);
      if (read.hits.length != 1) {
        problems.add({
          'kind': 'match_count',
          'file': file,
          'entry': entry.path,
          'pattern': entry.pattern,
          'count': read.hits.length,
          'text':
              "$file: pattern '${entry.pattern}' (entry '${entry.path}') matches "
              '${read.hits.length} times, expected exactly 1',
        });
      }
    }
  }
  return VersionRead(tree, files, problems);
}

/// The sorted names of the files [read] holds.
List<String> readFiles(VersionRead read) =>
    {for (final f in read.files) f.file}.toList()..sort();

/// The `version_files_invalid` stop for [read]'s problems.
ReleaseStop invalidVersions(VersionRead read) => ReleaseStop(
  'version_files_invalid',
  'version files are not readable in ${read.tree.label}: '
      '${read.problems.map((problem) => problem['text']).join('; ')}',
  extra: {
    'problems': [
      for (final problem in read.problems)
        {
          for (final e in problem.entries)
            if (e.key != 'text') e.key: e.value,
        },
    ],
    'files': readFiles(read),
  },
);

/// The `version_files_disagree` stop: [by] maps each version to its files.
ReleaseStop disagreeStop(
  VersionTree tree,
  Map<String, List<String>> by,
  List<String> files,
) => ReleaseStop(
  'version_files_disagree',
  'version files disagree in ${tree.label}: '
      '${by.entries.map((e) => '${e.key} in ${e.value.join(', ')}').join('; ')}',
  extra: {'versions': by, 'files': files},
);

/// Each version of [read] with the files that carry it, in first-seen order.
/// Every file must have exactly one match.
Map<String, List<String>> groupVersions(VersionRead read) {
  final by = <String, List<String>>{};
  for (final f in read.files) {
    by.putIfAbsent(f.hits.first.value, () => []).add(f.file);
  }
  return by;
}

/// Exactly one match per file and one shared version, else a stop naming each
/// offending file. Returns the version and the files read.
Future<({String version, List<String> files})> agree(
  VersionTree tree,
  List<VersionEntry> entries,
) async {
  final read = await readVersions(tree, entries);
  if (read.problems.isNotEmpty) throw invalidVersions(read);
  final by = groupVersions(read);
  final files = readFiles(read);
  if (by.length > 1) throw disagreeStop(tree, by, files);
  return (version: by.keys.first, files: files);
}

/// `MAJOR.MINOR.PATCH` as numbers, or null.
List<int>? parseSemver(String version) {
  final m = RegExp(r'^(\d+)\.(\d+)\.(\d+)$').firstMatch(version);
  return m == null ? null : [for (var i = 1; i <= 3; i++) int.parse(m[i]!)];
}

/// Negative, zero or positive as [a] is before, equal to or after [b].
int compareSemver(List<int> a, List<int> b) {
  for (var i = 0; i < 3; i++) {
    if (a[i] != b[i]) return a[i].compareTo(b[i]);
  }
  return 0;
}

/// What a bump changed.
class BumpResult {
  BumpResult(this.from, this.to, this.changed, this.files);

  final String from;
  final String to;
  final List<String> changed;
  final List<String> files;

  Map<String, Object?> toJson() => {
    'ok': true,
    'from': from,
    'to': to,
    'changed': changed,
    'files': files,
  };
}

/// Moves every version file of the working tree at [root] to [target]. It
/// stops on a target that is not `MAJOR.MINOR.PATCH` (`bad_target`) or not
/// greater than the current version (`target_not_greater`), on files that do
/// not read (`version_files_invalid`) or disagree (`version_files_disagree`),
/// and on a file that is not valid UTF-8 (`bad_version_files`), all before the
/// first write. A rerun to the same target completes an interrupted bump: the
/// files already at [target] are left alone.
Future<BumpResult> bump(
  String root,
  List<VersionEntry> entries,
  String target,
) async {
  final goal = parseSemver(target);
  if (goal == null) {
    throw ReleaseStop(
      'bad_target',
      'the target version must be MAJOR.MINOR.PATCH (digits only, e.g. 0.5.0), '
          "got '$target'",
    );
  }
  final tree = WorkTree(root);
  final read = await readVersions(tree, entries);
  if (read.problems.isNotEmpty) throw invalidVersions(read);
  final by = groupVersions(read);
  final files = readFiles(read);
  final present = by.keys.toList()
    ..sort((a, b) {
      final x = parseSemver(a), y = parseSemver(b);
      if (x == null || y == null) {
        return x == y ? a.compareTo(b) : (x == null ? 1 : -1);
      }
      final c = compareSemver(x, y);
      return c != 0 ? c : a.compareTo(b);
    });
  final String current;
  if (present.length == 1) {
    current = present.first;
    final now = parseSemver(current);
    if (now == null) {
      throw ReleaseStop(
        'bad_current',
        "the current version '$current' is not MAJOR.MINOR.PATCH, so $target "
            'cannot be compared',
      );
    }
    if (compareSemver(goal, now) <= 0) {
      throw ReleaseStop(
        'target_not_greater',
        'the target $target must be greater than the current version $current',
      );
    }
  } else if (present.length == 2 &&
      present[1] == target &&
      parseSemver(present[0]) != null &&
      compareSemver(parseSemver(present[0])!, goal) < 0) {
    current = present[0]; // an interrupted bump to this same target
  } else {
    throw disagreeStop(tree, by, files);
  }
  final plan = planBump(read, target);
  final changed = writePlan(root, plan, target);
  return BumpResult(current, target, changed, files);
}

/// The new bytes of each file [read] holds that does not carry [target], by
/// file name in sorted order. Everything is computed in memory first: a file
/// that is not valid UTF-8 stops with `bad_version_files` naming it, so
/// nothing is written and no other byte of a file is ever altered. Entries
/// that match the same file each contribute their capture; two that capture
/// overlapping text stop with `bad_version_files`.
Map<String, Uint8List> planBump(VersionRead read, String target) {
  final spans = <String, Set<(int, int)>>{};
  final source = <String, VersionFile>{};
  for (final f in read.files) {
    final hit = f.hits.first;
    source.putIfAbsent(f.file, () => f);
    if (hit.value != target) {
      spans.putIfAbsent(f.file, () => {}).add((hit.start, hit.end));
    }
  }
  final names = spans.keys.toList()..sort();
  for (final name in names) {
    try {
      utf8.decode(source[name]!.raw);
    } on FormatException {
      throw ReleaseStop(
        'bad_version_files',
        '$name is not valid UTF-8, so bump would alter bytes beyond the '
            'version; nothing was written. Re-save the file as UTF-8 or '
            'remove it from release.version_files',
        extra: {'file': name},
      );
    }
  }
  final plan = <String, Uint8List>{};
  for (final name in names) {
    final file = source[name]!;
    final ordered = spans[name]!.toList()..sort((a, b) => a.$1.compareTo(b.$1));
    final out = BytesBuilder(copy: false);
    var pos = 0, previousEnd = 0;
    for (final (start, end) in ordered) {
      if (start < previousEnd) {
        throw ReleaseStop(
          'bad_version_files',
          '$name: two version_files entries capture overlapping text; make '
              'their patterns capture the same version or separate ones',
          extra: {'file': name},
        );
      }
      out
        ..add(file.raw.sublist(pos, file.byteOffset(start)))
        ..add(utf8.encode(target));
      pos = file.byteOffset(end);
      previousEnd = end;
    }
    out.add(file.raw.sublist(pos));
    plan[name] = out.takeBytes();
  }
  return plan;
}

/// Writes each planned file through a temp file in its directory and a rename,
/// in sorted order, and returns the files written. The temp file starts as a
/// copy of the original, so the file keeps its mode. A failure stops with
/// `write_failed` listing the files written and the files pending.
List<String> writePlan(
  String root,
  Map<String, Uint8List> plan,
  String target,
) {
  final changed = <String>[];
  final pending = plan.keys.toList()..sort();
  for (final name in List.of(pending)) {
    final full = p.join(root, name);
    final temp = File(
      p.join(
        p.dirname(full),
        '.release-${Random().nextInt(1 << 32).toRadixString(36)}',
      ),
    );
    try {
      File(full).copySync(temp.path);
      temp.writeAsBytesSync(plan[name]!, flush: true);
      replaceFile(temp.path, full);
      changed.add(name);
      pending.remove(name);
    } on FileSystemException catch (e) {
      throw ReleaseStop(
        'write_failed',
        'writing $name failed: ${e.message}; written: '
            "${changed.isEmpty ? 'none' : changed.join(', ')}; not written: "
            '${pending.join(', ')}. Rerun bump --to $target to complete it',
        extra: {'written': changed, 'pending': pending},
      );
    } finally {
      if (temp.existsSync()) temp.deleteSync();
    }
  }
  return changed;
}
