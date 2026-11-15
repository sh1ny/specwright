import 'changes.dart';
import 'git.dart';
import 'history.dart';
import 'notes.dart';
import 'settings.dart';
import 'stop.dart';
import 'versions.dart';

/// The options of `status` and `publish`.
class StatusArgs {
  StatusArgs({
    this.version,
    this.main,
    this.base,
    this.store,
    this.storeMain,
    this.storePrefix,
  });

  /// `--version`.
  final String? version;

  /// `--main`: the ref whose first-parent history holds the release commit.
  final String? main;

  /// `--base`: the GitHub base branch the closed-PR read lists.
  final String? base;

  /// `--store`, `--store-main` and `--store-prefix`.
  final String? store;
  final String? storeMain;
  final String? storePrefix;
}

/// The entries, the main ref and its history, as [loadMain] reads them.
typedef LoadedMain = ({List<VersionEntry> entries, String ref, Releases rel});

/// The entries, the ref for [main] (default: the local main) and its
/// [Releases]; stops with `no_main` for a ref that does not exist.
Future<LoadedMain> loadMain(
  ReleaseGit git,
  ReleaseSettings settings,
  String? main,
) async {
  final entries = settings.entries();
  final ref = main != null && main.isNotEmpty
      ? main
      : await detectMain(git, settings.mainBranch);
  if (!await git.refExists(ref)) {
    throw ReleaseStop('no_main', "main ref '$ref' does not exist");
  }
  return (
    entries: entries,
    ref: ref,
    rel: Releases(await primaryHistory(git, entries, ref)),
  );
}

/// The release commit of [version]: the first commit on [ref]'s history whose
/// primary file reads it, which must be a merge or a squash commit.
Future<String> releaseCommitOf(
  ReleaseGit git,
  LoadedMain loaded,
  String version,
) async {
  final sha = loaded.rel.first[version];
  if (sha == null) {
    throw ReleaseStop(
      'no_release_commit',
      "no commit on ${loaded.ref}'s first-parent history carries $version in "
          "the primary file '${loaded.entries.first.path}': the release commit "
          'must be on main (merged), not only on a branch',
    );
  }
  await requireReleaseShape(git, sha);
  return sha;
}

/// Everything `status` reports for one version: the release commit, notes,
/// previous release, local and remote tag and, unless [release] is false, the
/// GitHub release. [command] names the caller in a usage stop. [loaded] is
/// what [loadMain] read, when the caller has it already.
Future<Map<String, Object?>> statusDocument(
  ReleaseGit git,
  ReleaseSettings settings,
  StatusArgs args, {
  LoadedMain? loaded,
  bool release = true,
  String command = 'status',
}) async {
  final v = args.version;
  if (v == null || v.isEmpty) {
    throw ReleaseStop('usage', '$command needs --version', code: 2);
  }
  final main = loaded ?? await loadMain(git, settings, args.main);
  final sha = await releaseCommitOf(git, main, v);
  final agreed = await agree(CommitTree(git.root, sha), main.entries);
  if (agreed.version != v) {
    throw ReleaseStop(
      'version_mismatch',
      'version files at release commit ${sha.substring(0, 12)} read '
          '${agreed.version}, not $v',
    );
  }
  // a clone that never fetched tags still sees origin's
  final tags = {...await git.localTags(), ...await git.publishedTags()};
  final prev = previousRelease(settings.tag, main.rel, v, tags);
  final range = await rangeCommits(git, prev?.sha, sha);
  final ChangeSet set;
  if (args.store != null) {
    set = await storeChanges(
      git,
      settings,
      store: args.store!,
      storeMain: args.storeMain,
      storePrefix: args.storePrefix,
      main: args.main,
      base: args.base,
      prev: prev?.sha,
      rel: sha,
      range: range,
    );
  } else {
    set = await localChanges(git, prev?.sha, sha, range);
  }
  final secs = await readSections(set.git, set.commit, set.prefix, set.rows, v);
  final chosen = summaryChoice([
    for (final r in set.rows)
      if (secs[r.dir] != null) secs[r.dir]!,
  ]);
  bool hasSection(String dir) => secs[dir]?.section != null;
  final why = await whyLines(
    set.git,
    set.commit,
    set.prefix,
    [
      for (final r in set.rows)
        if (!hasSection(r.dir)) r.dir,
    ].take(100).toList(),
  );
  final changes = [
    for (final r in set.rows)
      ReleaseChange(changeName(r.dir), why[r.dir], r.pr),
  ];
  final warnings = [
    for (final r in set.rows)
      if (secs[r.dir]?.warning != null)
        {'change': changeName(r.dir), 'error': secs[r.dir]!.warning},
  ];
  final tag = tagFor(settings.tag, v);
  final tagLocal = await git.run([
    'rev-parse',
    '--verify',
    '--quiet',
    'refs/tags/$tag^{commit}',
  ]);
  final remote = await git.remoteTag(tag);
  final tagObject = tagLocal.exitCode == 0
      ? await git.run(['rev-parse', '--verify', '--quiet', 'refs/tags/$tag'])
      : null;
  final lightweight = [
    if (tagLocal.exitCode == 0 &&
        await git.text(['cat-file', '-t', 'refs/tags/$tag']) != 'tag')
      'locally',
    if (remote.commit != null && remote.annotated != true) 'on origin',
  ];
  final notes = buildNotes(
    tag,
    changes,
    sections: [
      for (final r in set.rows) hasSection(r.dir) ? secs[r.dir]!.section : null,
    ],
    summary: chosen?.section!.summary,
  );
  final state = release
      ? (await git.releaseState(
          tag,
          githubRelease: settings.githubRelease,
        )).state
      : null;
  return {
    'ok': true,
    'version': v,
    'tag': tag,
    'release_commit': sha,
    'main': main.ref,
    'files': agreed.files,
    'previous': {
      'commit': prev?.sha,
      'version': prev?.version,
      'basis': prev?.basis,
    },
    'range': {'from': prev?.sha, 'to': sha, 'commits': range.length},
    'changes': [for (final c in changes) c.toJson()],
    'warnings': warnings,
    'notes': notes,
    'tag_local': tagLocal.exitCode == 0 ? trimmed(tagLocal.stdout) : null,
    'tag_remote': remote.commit,
    'tag_lightweight': lightweight,
    'tag_object': {
      'local': tagObject != null && tagObject.exitCode == 0
          ? trimmed(tagObject.stdout)
          : null,
      'remote': remote.object,
    },
    'github_release': ?state,
    'repo': git.root,
    'tag_repo': git.root,
    'store': ?set.store,
  };
}
