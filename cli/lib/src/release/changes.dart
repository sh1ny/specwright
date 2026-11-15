import 'package:path/path.dart' as p;

import '../vcs/document.dart' show decodeJson;
import 'git.dart';
import 'history.dart';
import 'notes.dart' show changeName;
import 'settings.dart';
import 'stop.dart';
import 'versions.dart' show catBlobs;

/// One archived change of a release: the archive directory and the pull
/// request that carried it, when known.
typedef ArchiveRow = ({String dir, int? pr});

/// One first-parent commit of a release range.
typedef RangeCommit = ({String sha, String subject});

/// The changes of a release range and where their proposals are read.
class ChangeSet {
  ChangeSet(this.rows, this.commit, this.prefix, this.git, [this.store]);

  /// The archive directories, oldest first.
  final List<ArchiveRow> rows;

  /// The commit the proposals are read at.
  final String commit;

  /// The planning prefix (`openspec`).
  final String prefix;

  /// The repository the proposals are read from: the code repository, or the
  /// store.
  final ReleaseGit git;

  /// The `store` field of the status document (null without `--store`).
  final Map<String, Object?>? store;
}

/// The first-parent commits in (prev, rel], oldest first.
Future<List<RangeCommit>> rangeCommits(
  ReleaseGit git,
  String? prev,
  String rel,
) async {
  final spec = prev != null ? '$prev..$rel' : rel;
  final r = await git.run([
    'log',
    '--first-parent',
    '--reverse',
    '--format=%H%x02%s',
    spec,
  ]);
  if (r.exitCode != 0) {
    throw ReleaseStop(
      'git_failed',
      'git log failed: ${trimmed(r.stderr)}',
      code: 3,
    );
  }
  return [
    for (final line in lossy(r.stdout).split('\n'))
      if (line.contains('\x02'))
        (
          sha: line.substring(0, line.indexOf('\x02')),
          subject: line.substring(line.indexOf('\x02') + 1),
        ),
  ];
}

/// The names of the archive directories under `<prefix>/changes/archive/` at
/// [commit].
Future<Set<String>> archiveDirs(
  ReleaseGit git,
  String commit,
  String prefix,
) async {
  final base = '$prefix/changes/archive/';
  final r = await git.run([
    '-c',
    'core.quotepath=off',
    'ls-tree',
    '-d',
    '--name-only',
    commit,
    base,
  ]);
  if (r.exitCode != 0) {
    throw ReleaseStop(
      'git_failed',
      'git ls-tree failed at $commit: ${trimmed(r.stderr)}',
      code: 3,
    );
  }
  return {
    for (final line in trimmed(r.stdout).split('\n'))
      if (line.startsWith(base)) line.substring(base.length),
  };
}

/// The first first-parent commit in (prev, rel] that adds a file under each
/// archive directory.
Future<Map<String, RangeCommit>> archiveAdders(
  ReleaseGit git,
  String? prev,
  String rel,
  String prefix,
) async {
  final spec = prev != null ? '$prev..$rel' : rel;
  final r = await git.run([
    '-c',
    'core.quotepath=off',
    'log',
    '--first-parent',
    '-m',
    '--no-renames',
    '--name-only',
    '--diff-filter=A',
    '--reverse',
    '--format=%x01%H%x02%s',
    spec,
    '--',
    ':(literal)$prefix/changes/archive',
  ]);
  if (r.exitCode != 0) {
    throw ReleaseStop(
      'git_failed',
      'git log failed: ${trimmed(r.stderr)}',
      code: 3,
    );
  }
  final out = <String, RangeCommit>{};
  final base = '$prefix/changes/archive/';
  for (final chunk in lossy(r.stdout).split('\x01').skip(1)) {
    final lines = chunk.split('\n');
    final head = lines.first;
    final cut = head.indexOf('\x02');
    final commit = (
      sha: head.substring(0, cut),
      subject: head.substring(cut + 1),
    );
    for (final f in lines.skip(1)) {
      if (f.startsWith(base) && f.substring(base.length).contains('/')) {
        out.putIfAbsent(
          f.substring(base.length).split('/').first,
          () => commit,
        );
      }
    }
  }
  return out;
}

/// The repository's own archive directories present at [rel] and absent at
/// [prev], oldest first by the commit that first holds them, each with the
/// pull request its commit's subject names.
Future<ChangeSet> localChanges(
  ReleaseGit git,
  String? prev,
  String rel,
  List<RangeCommit> range,
) async {
  const prefix = 'openspec';
  final fresh = (await archiveDirs(git, rel, prefix))
    ..removeAll(prev != null ? await archiveDirs(git, prev, prefix) : {});
  final adders = await archiveAdders(git, prev, rel, prefix);
  final position = {for (var i = 0; i < range.length; i++) range[i].sha: i};
  final subjects = {for (final c in range) c.sha: c.subject};
  final rows = [
    for (final d in fresh)
      (
        position[adders[d]?.sha ?? rel] ?? position.length,
        d,
        subjectPr(subjects[adders[d]?.sha ?? rel] ?? ''),
      ),
  ]..sort((a, b) => a.$1 != b.$1 ? a.$1.compareTo(b.$1) : a.$2.compareTo(b.$2));
  return ChangeSet(
    [for (final r in rows) (dir: r.$2, pr: r.$3)],
    rel,
    prefix,
    git,
  );
}

/// The change branch's prefix from the name's first token, as
/// specwright-branch derives it (anything else: `feat`).
String branchPrefix(String change) {
  const prefixes = {
    'feat': ['add', 'feat', 'feature', 'implement', 'introduce'],
    'bugfix': ['fix', 'bugfix', 'hotfix', 'patch', 'resolve'],
    'refactor': ['refactor', 'restructure', 'cleanup'],
    'docs': ['docs', 'doc', 'document'],
    'chore': ['chore', 'bump', 'deps', 'ci', 'build'],
  };
  final first = change.split('-').first.toLowerCase();
  for (final e in prefixes.entries) {
    if (e.value.contains(first)) return e.key;
  }
  return 'feat';
}

/// The closed pull requests into the code main: one `gh api --paginate
/// --slurp` call. Exit 3 (`pr_discovery_failed`) when it fails. [base] names
/// the GitHub base branch when given; else it is taken from an `origin/<name>`
/// ref (a bare commit, as a jj run reads, names no branch).
Future<({String slug, List<Map<String, Object?>> pulls})> mergedPulls(
  ReleaseGit git,
  String ref,
  String? base,
) async {
  final slug = await git.releaseSlug();
  if (slug == null) {
    throw ReleaseStop(
      'no_github_origin',
      'store-backed notes in pr mode need origin to be a github.com repository '
          '(to find the merged code PRs)',
    );
  }
  final branch =
      base ??
      (ref.startsWith('origin/') ? ref.substring('origin/'.length) : ref);
  final url = 'repos/$slug/pulls?state=closed&base=$branch&per_page=100';
  final shown = 'gh api --paginate $url';
  final r = await git.gh(['api', '--paginate', '--slurp', url], paged: true);
  if (r.exitCode != 0) {
    final why = failureText(r);
    throw ReleaseStop(
      'pr_discovery_failed',
      '$shown failed: ${why.contains('slurp') ? '$why (--slurp needs gh 2.48 or later)' : why}',
      code: 3,
      extra: {'call': shown},
    );
  }
  final pulls = <Map<String, Object?>>[];
  try {
    final pages = decodeJson(lossy(r.stdout));
    if (pages is! List) throw const FormatException('not a list');
    for (final page in pages) {
      if (page is! List) throw const FormatException('not a list');
      pulls.addAll(page.cast<Map<String, Object?>>());
    }
  } on FormatException catch (e) {
    throw ReleaseStop(
      'pr_discovery_failed',
      '$shown returned unreadable output: ${e.message}',
      code: 3,
      extra: {'call': shown},
    );
  } on TypeError {
    throw ReleaseStop(
      'pr_discovery_failed',
      '$shown returned unreadable output: not a list of pull requests',
      code: 3,
      extra: {'call': shown},
    );
  }
  return (slug: slug, pulls: pulls);
}

final RegExp _planningOnly = RegExp(
  r'^code_changes:\s*none\s*$',
  multiLine: true,
);

Map<String, Object?> _map(Object? value) =>
    value is Map ? value.cast<String, Object?>() : const {};

/// The store's archive directories (on its main, not planning-only) whose
/// code-merge proof lies in the code range (prev, rel]: a `merge: <name>`
/// subject (finish: local), or a merged pull request from the code
/// repository's own `<prefix>/<name>` branch (finish: pr, one `gh api
/// --paginate --slurp` call). The proof is the pull request's merge commit
/// being in [rel] and not in [prev].
Future<ChangeSet> storeChanges(
  ReleaseGit git,
  ReleaseSettings settings, {
  required String store,
  String? storeMain,
  String? storePrefix,
  String? main,
  String? base,
  String? prev,
  required String rel,
  required List<RangeCommit> range,
}) async {
  final probe = ReleaseGit(store);
  final topText = await probe.run(['rev-parse', '--show-toplevel']);
  if (topText.exitCode != 0 || trimmed(topText.stdout).isEmpty) {
    throw ReleaseStop(
      'store_not_a_repo',
      '--store $store is not inside a git work tree',
    );
  }
  final top = p.normalize(trimmed(topText.stdout));
  final sg = ReleaseGit(top);
  final prefix = storePrefix ?? 'openspec';
  var ref = storeMain;
  if (ref == null || ref.isEmpty) {
    final configured = readReleaseSettings(top).mainBranch;
    final names = [configured ?? 'main', if (configured == null) 'master'];
    for (final n in names) {
      if (await sg.refExists('refs/remotes/origin/$n')) {
        ref = 'origin/$n';
        break;
      }
      if (await sg.refExists('refs/heads/$n')) {
        ref = n;
        break;
      }
    }
  }
  if (ref == null || ref.isEmpty || !await sg.refExists(ref)) {
    throw ReleaseStop(
      'no_store_main',
      "the store's main ref '${ref == null || ref.isEmpty ? 'main' : ref}' does not exist in $top",
    );
  }
  final dirs = (await archiveDirs(sg, ref, prefix)).toList()..sort();
  final marks = await catBlobs(top, [
    for (final d in dirs)
      '$ref:$prefix/changes/archive/$d/specwright-change.yaml',
  ]);
  final candidates = <String, String>{
    for (var i = 0; i < dirs.length; i++)
      if (!(marks[i] != null && _planningOnly.hasMatch(lossy(marks[i]!))))
        changeName(dirs[i]): dirs[i],
  };
  final mode = settings.finish == 'local' ? 'local' : 'pr';
  final found = <(int, String, int?)>[];
  if (mode == 'local') {
    for (var i = 0; i < range.length; i++) {
      final m = RegExp(r'^merge: (\S+)$').firstMatch(range[i].subject.trim());
      if (m != null && candidates.containsKey(m[1])) {
        found.add((i, candidates[m[1]]!, null));
      }
    }
  } else if (candidates.isNotEmpty) {
    final mainName = main == null || main.isEmpty
        ? await detectMain(git, settings.mainBranch)
        : main;
    final merged = await mergedPulls(git, mainName, base);
    final position = {for (var i = 0; i < range.length; i++) range[i].sha: i};
    final pulls = [...merged.pulls]
      ..sort(
        (a, b) =>
            ((a['number'] as int?) ?? 0).compareTo((b['number'] as int?) ?? 0),
      );
    for (final pull in pulls) {
      final head = _map(pull['head']);
      final sha = pull['merge_commit_sha'];
      final headRef = (head['ref'] as String?) ?? '';
      final repo = (_map(head['repo'])['full_name'] as String?) ?? '';
      if (pull['merged_at'] == null ||
          sha is! String ||
          sha.isEmpty ||
          repo.toLowerCase() != merged.slug.toLowerCase() ||
          !headRef.contains('/')) {
        continue;
      }
      final name = headRef.substring(headRef.lastIndexOf('/') + 1);
      if (!candidates.containsKey(name) ||
          headRef != '${branchPrefix(name)}/$name' ||
          found.any((f) => f.$2 == candidates[name])) {
        continue;
      }
      if (await git.isAncestor(sha, rel) &&
          !(prev != null && await git.isAncestor(sha, prev))) {
        found.add((
          position[sha] ?? position.length,
          candidates[name]!,
          pull['number'] as int?,
        ));
      }
    }
  }
  found.sort(
    (a, b) => a.$1 != b.$1 ? a.$1.compareTo(b.$1) : a.$2.compareTo(b.$2),
  );
  return ChangeSet(
    [for (final f in found) (dir: f.$2, pr: f.$3)],
    ref,
    prefix,
    sg,
    {
      'dir': top,
      'main': ref,
      'prefix': prefix,
      'mode': mode,
      'candidates': candidates.length,
    },
  );
}
