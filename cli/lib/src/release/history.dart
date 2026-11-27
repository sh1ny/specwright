import 'dart:typed_data';

import 'git.dart';
import 'glob.dart';
import 'settings.dart';
import 'stop.dart';
import 'versions.dart';

/// A primary file that exists but does not read exactly one version (or whose
/// files disagree). It proves nothing on its own, but a version outside
/// [versions] (what the file did match, possibly nothing) is still a change.
class Unreadable {
  Unreadable(this.versions);

  final Set<String> versions;
}

String _pathspec(String path) =>
    VersionGlob.hasGlob(path) ? ':(glob)$path' : ':(literal)$path';

/// Every value [entry] captures in [raw], read lossily as UTF-8.
Iterable<String> _captures(VersionEntry entry, Uint8List raw) => [
  for (final m in entry.regex.allMatches(lossy(raw))) m.group(1)!,
];

/// The commits on [ref]'s first-parent history that touch the primary file,
/// oldest first, each with the one version the file reads there (every match
/// of every file the entry names); null when it reads none or several. One
/// `git log` and one `cat-file --batch`; for a glob the log's first-parent
/// name-status tracks which matching files exist at each commit.
Future<List<(String, String?)>> primaryHistory(
  ReleaseGit git,
  List<VersionEntry> entries,
  String ref,
) async {
  final entry = entries.first;
  final spec = _pathspec(entry.path);
  var r = await git.run([
    'log',
    '--first-parent',
    '--format=%H',
    '--reverse',
    ref,
    '--',
    spec,
  ]);
  if (r.exitCode != 0) throw _logFailed(r.stderr);
  final shas = trimmed(r.stdout)
      .split(RegExp(r'\s+'))
      .where((s) => s.isNotEmpty)
      .toList();
  final blobs = <List<Uint8List>>[];
  if (VersionGlob.hasGlob(entry.path)) {
    // -m with --first-parent diffs a merge against its first parent on any
    // git (the diff-merges option needs 2.31); the -c pins that on 2.31+,
    // where -m follows log.diffMerges (older git ignores the key)
    r = await git.run([
      '-c',
      'log.diffMerges=first-parent',
      'log',
      '-z',
      '--first-parent',
      '-m',
      '--no-renames',
      '--name-status',
      '--format=%x01%H',
      '--reverse',
      ref,
      '--',
      spec,
    ]);
    if (r.exitCode != 0) throw _logFailed(r.stderr);
    final glob = VersionGlob(entry.path);
    final present = <String>{};
    final perSha = <String, List<String>>{};
    String? sha;
    final tokens = lossy(r.stdout).split('\x00').iterator;
    while (tokens.moveNext()) {
      final token = tokens.current;
      if (token.startsWith('\x01')) {
        if (sha != null) perSha[sha] = present.toList()..sort();
        sha = token.substring(1);
      } else if (token.trim().isNotEmpty) {
        final name = tokens.moveNext() ? tokens.current : '';
        if (glob.matches(name)) {
          token.trim() == 'D' ? present.remove(name) : present.add(name);
        }
      }
    }
    if (sha != null) perSha[sha] = present.toList()..sort();
    final files = [for (final s in shas) perSha[s] ?? <String>[]];
    final got = (await catBlobs(git.root, [
      for (var i = 0; i < shas.length; i++)
        for (final f in files[i]) '${shas[i]}:$f',
    ])).iterator;
    for (final fs in files) {
      blobs.add([
        for (final _ in fs)
          if (got.moveNext() && got.current != null) got.current!,
      ]);
    }
  } else {
    final got = await catBlobs(git.root, [
      for (final s in shas) '$s:${entry.path}',
    ]);
    for (final b in got) {
      blobs.add([?b]);
    }
  }
  return [
    for (var i = 0; i < shas.length; i++)
      (shas[i], _single({for (final b in blobs[i]) ..._captures(entry, b)})),
  ];
}

String? _single(Set<String> values) => values.length == 1 ? values.first : null;

ReleaseStop _logFailed(List<int> stderr) =>
    ReleaseStop('git_failed', 'git log failed: ${trimmed(stderr)}', code: 3);

/// What the primary file's first-parent history says: each distinct value's
/// first appearance (its release commit) and the value that preceded it.
class Releases {
  Releases(this.hist) {
    String? last;
    for (final (sha, value) in hist) {
      if (value == null) continue;
      if (!first.containsKey(value)) {
        first[value] = sha;
        order.add(value);
        before[value] = last;
      }
      last = value;
    }
    current = last;
  }

  /// The history as [primaryHistory] returns it.
  final List<(String, String?)> hist;

  /// Version to the sha of its first appearance.
  final Map<String, String> first = {};

  /// The versions by first appearance.
  final List<String> order = [];

  /// Version to the value read just before its first appearance (null for the
  /// first).
  final Map<String, String?> before = {};

  /// The last value the file read, or null when it never read one.
  late final String? current;
}

/// The release commit of [version]: the first commit on [ref]'s first-parent
/// history whose primary file reads it, or null.
Future<String?> releaseCommit(
  ReleaseGit git,
  List<VersionEntry> entries,
  String ref,
  String version,
) async => Releases(await primaryHistory(git, entries, ref)).first[version];

/// The tag for [version] under the `release.tag` template [template].
String tagFor(String template, String version) =>
    template.replaceAll('{version}', version);

/// The previous release for [version]: the highest lower version with a tag,
/// else the value read just before [version] first appeared; null when there
/// is none. `basis` is `tag` or `history`.
({String version, String sha, String basis})? previousRelease(
  String template,
  Releases rel,
  String version,
  Set<String> tags,
) {
  final me = parseSemver(version);
  final lower = [
    for (final v in rel.order)
      if (me != null &&
          parseSemver(v) != null &&
          compareSemver(parseSemver(v)!, me) < 0 &&
          tags.contains(tagFor(template, v)))
        v,
  ];
  if (lower.isNotEmpty) {
    final v = _highest(lower);
    return (version: v, sha: rel.first[v]!, basis: 'tag');
  }
  final b = rel.before[version];
  return b == null ? null : (version: b, sha: rel.first[b]!, basis: 'history');
}

String _highest(List<String> versions) => versions.reduce(
  (a, b) => compareSemver(parseSemver(b)!, parseSemver(a)!) > 0 ? b : a,
);

/// The versions after the latest tagged one (the highest semver with a tag)
/// in first-appearance order that have no tag; with no tag at all, only the
/// current version. A version whose tag is in [local] but not in [tags] (a tag
/// push that failed) is listed too, whatever the anchor. [latest] is the
/// latest tagged version or null.
({List<String> versions, String? latest}) untaggedSinceLatest(
  String template,
  Releases rel,
  Set<String> tags, {
  Set<String> local = const {},
}) {
  bool tagged(String v) => tags.contains(tagFor(template, v));
  final taggedVersions = [
    for (final v in rel.order)
      if (parseSemver(v) != null && tagged(v)) v,
  ];
  final latest = taggedVersions.isEmpty ? null : _highest(taggedVersions);
  final Set<String> want;
  if (latest == null) {
    want = {if (rel.current != null) rel.current!};
  } else {
    want = {
      for (final v in rel.order.skip(rel.order.indexOf(latest) + 1))
        if (parseSemver(v) != null) v,
    };
  }
  want.addAll([
    for (final v in rel.order)
      if (parseSemver(v) != null && local.contains(tagFor(template, v))) v,
  ]);
  return (
    versions: [
      for (final v in rel.order)
        if (want.contains(v) && !tagged(v)) v,
    ],
    latest: latest,
  );
}

/// Stops with `older_untagged` when a version older than [version] is not
/// published, so a release never lands before an older one. [published] is
/// the tags on origin, [local] the local ones.
void refuseOlderUntagged(
  String template,
  Releases rel,
  Set<String> published,
  Set<String> local,
  String version, {
  String remote = 'origin',
}) {
  final me = parseSemver(version);
  final older = [
    for (final u in untaggedSinceLatest(
      template,
      rel,
      published,
      local: local,
    ).versions)
      if (me != null &&
          parseSemver(u) != null &&
          compareSemver(parseSemver(u)!, me) < 0)
        u,
  ];
  if (older.isEmpty) return;
  throw ReleaseStop(
    'older_untagged',
    'older version(s) not published (no tag on $remote): ${older.join(', ')}; '
        'publish ${older.first} (tag ${tagFor(template, older.first)}) before $version',
    extra: {'versions': older},
  );
}

final RegExp _subjectPr = RegExp(
  r'\(#(\d+)\)\s*$|^Merge pull request #(\d+)\b',
);

/// The pull request number a commit subject names: a trailing `(#n)` or
/// `Merge pull request #n`, else null.
int? subjectPr(String subject) {
  final m = _subjectPr.firstMatch(subject);
  return m == null ? null : int.parse(m[1] ?? m[2]!);
}

/// Stops with `rebase_release_commit` unless [sha] is a merge commit or a
/// squash commit (its subject ends `(#n)`): a replayed bump is refused.
Future<void> requireReleaseShape(ReleaseGit git, String sha) async {
  final r = await git.run(['log', '-1', '--format=%P%x00%s', sha]);
  if (r.exitCode != 0) {
    throw ReleaseStop(
      'git_failed',
      'git log failed at $sha: ${trimmed(r.stderr)}',
      code: 3,
    );
  }
  final out = lossy(r.stdout).replaceFirst(RegExp(r'\n+$'), '');
  final cut = out.indexOf('\x00');
  final parents = out
      .substring(0, cut)
      .split(RegExp(r'\s+'))
      .where((p) => p.isNotEmpty);
  final subject = out.substring(cut + 1);
  if (parents.length >= 2 || RegExp(r'\(#\d+\)\s*$').hasMatch(subject)) return;
  throw ReleaseStop(
    'rebase_release_commit',
    "the release commit ${sha.substring(0, 12)} ('$subject') is neither a merge "
        'commit nor a commit whose subject ends in (#<n>): the release commit '
        'must be a merge or squash commit (a rebase merge or a direct push '
        'replays the bump as its own commit)',
    extra: {'commit': sha},
  );
}

/// The main branch name: the setting, else `main`, else `master`, whichever
/// exists locally; the first name when none does.
Future<String> detectMain(ReleaseGit git, String? mainBranch) async {
  final names = [mainBranch ?? 'main', if (mainBranch == null) 'master'];
  for (final n in names) {
    if (await git.succeeds([
      'show-ref',
      '--verify',
      '--quiet',
      'refs/heads/$n',
    ])) {
      return n;
    }
  }
  return names.first;
}

/// The version the primary file reads at [commit] as a `String`; null when
/// the file is absent there; an [Unreadable] carrying the versions it matched
/// when a file matches other than once or the files disagree.
Future<Object?> primaryAt(
  ReleaseGit git,
  List<VersionEntry> entries,
  String commit,
) async {
  final entry = entries.first;
  final tree = CommitTree(git.root, commit);
  final blobs = await tree.readAll(await tree.files(entry.path));
  if (blobs.isEmpty) return null;
  final values = <String>{};
  var once = true;
  // exactly one match per file, as readVersions requires; the files must then agree
  for (final raw in blobs.values) {
    final found = _captures(entry, raw).toList();
    once = once && found.length == 1;
    values.addAll(found);
  }
  return once && values.length == 1 ? values.first : Unreadable(values);
}

List<int>? _sv(String v) => parseSemver(v);

bool _greater(String a, String b) => compareSemver(_sv(a)!, _sv(b)!) > 0;

/// The version [commit] is judged against: its parent's, or, while that is
/// unreadable and not on [ref], the version of the nearest first-parent
/// ancestor that is readable or on [ref].
Future<Object?> judgedParent(
  ReleaseGit git,
  List<VersionEntry> entries,
  String commit,
  String ref,
) async {
  var at = '$commit^';
  Object? parent = await git.refExists(at)
      ? await primaryAt(git, entries, at)
      : null;
  while (parent is Unreadable) {
    final sha = await git.text(['rev-parse', at]);
    if (await git.isAncestor(sha, ref) || !await git.refExists('$sha^')) break;
    at = '$sha^';
    parent = await primaryAt(git, entries, at);
  }
  return parent;
}

/// Whether the newest of [commits] (newest first) that changed the primary
/// version raised it. An edit that keeps the version (a manifest's
/// dependencies) is skipped, and a bump reverted later on the branch is no
/// bump. Each commit is judged against [judgedParent]: an unreadable parent on
/// the branch is looked past, so a bump made through an unreadable version
/// counts and a stray line added and then removed does not.
///
/// A commit whose immediate parent is unreadable and on the branch is a change
/// when it matched a version that parent did not; it is a bump when each
/// version it matched is greater than the version it is judged against (than
/// each semver of it, when that is unreadable too), else no bump, and the walk
/// stops. Any other commit: one whose own version is unreadable is no change
/// when that version is among those it matched (or it is unreadable too), else
/// a bump only when it matched at least one version and every one is greater.
/// One judged against an unreadable version (on [ref]) is no change when its
/// version is the greatest semver among those matched, no bump when it is a
/// lower one of them, else a bump when greater than every semver among them
/// (or none).
Future<bool> ownBump(
  ReleaseGit git,
  List<VersionEntry> entries,
  List<String> commits,
  String ref,
) async {
  for (final c in commits) {
    final mine = await primaryAt(git, entries, c);
    final parent = await judgedParent(git, entries, c, ref);
    if (await git.refExists('$c^')) {
      final direct = await primaryAt(git, entries, '$c^');
      if (direct is Unreadable &&
          !await git.isAncestor(await git.text(['rev-parse', '$c^']), ref)) {
        final matched = mine is Unreadable
            ? mine.versions
            : {if (mine != null) mine as String};
        if (matched.difference(direct.versions).isNotEmpty) {
          final seen = parent is Unreadable
              ? [for (final v in parent.versions) ?_sv(v)]
              : [
                  if (parent != null && _sv(parent as String) != null)
                    _sv(parent)!,
                ];
          return matched.every(
            (v) =>
                _sv(v) != null &&
                seen.every((s) => compareSemver(_sv(v)!, s) > 0),
          );
        }
      }
    }
    if (mine is Unreadable) {
      if (parent is Unreadable ||
          (parent != null && mine.versions.contains(parent))) {
        continue;
      }
      if (mine.versions.isEmpty) return false;
      if (parent == null || _sv(parent as String) == null) return true;
      return mine.versions.every((v) => _sv(v) != null && _greater(v, parent));
    }
    if (mine == parent) continue;
    if (mine == null) return false;
    final version = mine as String;
    if (parent is Unreadable) {
      final seen = [for (final v in parent.versions) ?_sv(v)];
      if (parent.versions.contains(version)) {
        if (_sv(version) != null &&
            seen.isNotEmpty &&
            compareSemver(_sv(version)!, _maxSemver(seen)) < 0) {
          return false; // it kept a lower one of its parent's versions: the higher one, a bump, is dropped
        }
        continue; // it kept the highest of its parent's versions, which is on ref: no change
      }
      return seen.isEmpty ||
          _sv(version) == null ||
          seen.every((s) => compareSemver(_sv(version)!, s) > 0);
    }
    return parent == null ||
        _sv(version) == null ||
        _sv(parent as String) == null ||
        _greater(version, parent);
  }
  return false;
}

List<int> _maxSemver(List<List<int>> all) =>
    all.reduce((a, b) => compareSemver(b, a) > 0 ? b : a);

/// A branch that bumped must be greater than [ref]'s version: stops with
/// `version_not_ahead_of_main` otherwise. [version] is the branch's, read at
/// [tip]. An unreadable version at [ref] passes, as an absent one does; an
/// unreadable merge base counts as bumped only when [version] is not among
/// those it matched.
Future<void> checkAheadOf(
  ReleaseGit git,
  List<VersionEntry> entries,
  String ref,
  String version, {
  String tip = 'HEAD',
}) async {
  if (!await git.refExists(ref)) {
    throw ReleaseStop('no_main', "main ref '$ref' does not exist");
  }
  final theirs = await primaryAt(git, entries, ref);
  if (theirs == null || theirs is Unreadable) return;
  final base = await git.run(['merge-base', tip, ref]);
  final baseSha = trimmed(base.stdout);
  final baseVersion = base.exitCode == 0 && baseSha.isNotEmpty
      ? await primaryAt(git, entries, baseSha)
      : null;
  var bumped = baseVersion is Unreadable
      ? !baseVersion.versions.contains(version)
      : baseVersion != version;
  if (!bumped) {
    final r = await git.run([
      'log',
      '--no-merges',
      '--topo-order',
      '--format=%H',
      '$ref..$tip',
      '--',
      _pathspec(entries.first.path),
    ]);
    if (r.exitCode != 0) {
      throw ReleaseStop(
        'git_failed',
        'git log failed: ${trimmed(r.stderr)}',
        code: 3,
      );
    }
    bumped = await ownBump(
      git,
      entries,
      trimmed(r.stdout)
          .split(RegExp(r'\s+'))
          .where((s) => s.isNotEmpty)
          .toList(),
      ref,
    );
  }
  final main = theirs as String;
  if (bumped &&
      !(_sv(version) != null && _sv(main) != null && _greater(version, main))) {
    throw ReleaseStop(
      'version_not_ahead_of_main',
      "this branch bumped to $version, which is not greater than $ref's $main: "
          'another change reached $ref first. Rerun bump --to with a version '
          'greater than $main',
      extra: {'version': version, 'main_version': main, 'main': ref},
    );
  }
}
