import '../pr/gh.dart' show GhResult;
import 'git.dart';
import 'history.dart';
import 'settings.dart';
import 'status.dart';
import 'stop.dart';

/// `publish --version V`: tags the release commit and publishes the tag and
/// the GitHub release. Each step reads its state first and does only what is
/// missing, so a re-run resumes after any stop. A tag is never moved, deleted
/// or forced (ADR 0010); a bound that cuts the push or the release create is
/// settled by one read-back, never a retry.
Future<Map<String, Object?>> publishDocument(
  ReleaseGit git,
  ReleaseSettings settings,
  StatusArgs args,
) async {
  settings.gate(rebase: true);
  final v = args.version;
  if (v == null || v.isEmpty) {
    throw ReleaseStop('usage', 'publish needs --version', code: 2);
  }
  final remoteName = git.remote;
  final target = await git.bindTarget();
  final proof = args.proof;
  final verified = proof != null
      ? await git.verifyProof(
          proof,
          await releaseMainBranch(git, settings, args.base),
        )
      : target?.slug != null
      ? await git.proveMain(await releaseMainBranch(git, settings, args.base))
      : null;
  final loaded = await loadMain(git, settings, verified?.commit ?? args.main);
  await releaseCommitOf(git, loaded, v);
  refuseOlderUntagged(
    settings.tag,
    loaded.rel,
    await git.publishedTags(),
    await git.localTags(),
    v,
    remote: remoteName,
  );
  final doc = await statusDocument(
    git,
    settings,
    args,
    loaded: loaded,
    mainBranch: verified?.branch,
    release: false,
    command: 'publish',
  );
  final tag = doc['tag'] as String;
  final sha = doc['release_commit'] as String;
  final notes = doc['notes'] as String;
  if (!await git.hasRemote()) {
    throw ReleaseStop(
      remoteName == 'origin' ? 'no_origin' : 'no_remote',
      "publish needs the '$remoteName' remote to push the tag to",
    );
  }
  final local = doc['tag_local'] as String?;
  final remote = doc['tag_remote'] as String?;
  for (final (where, at) in [('locally', local), ('on $remoteName', remote)]) {
    if (at != null && at != sha) {
      throw _conflict(tag, v, sha, at, where, 'nothing was written');
    }
  }
  final lightweight = (doc['tag_lightweight'] as List).cast<String>();
  if (lightweight.isNotEmpty) {
    throw ReleaseStop(
      'lightweight_tag',
      'tag $tag exists ${lightweight.join(' and ')} as a lightweight tag at '
          'the release commit; a release is an annotated tag, and nothing was '
          'written. Replace it by hand: publish never moves, deletes or '
          'forces a tag',
      extra: {'tag': tag, 'where': lightweight},
    );
  }
  final objects = doc['tag_object'] as Map<String, Object?>;
  final localObject = objects['local'] as String?;
  final remoteObject = objects['remote'] as String?;
  if (local != null && remote != null && localObject != remoteObject) {
    throw _mismatch(
      tag,
      localObject!,
      remoteObject!,
      remoteName,
      'nothing was written',
    );
  }

  final String tagLocal;
  if (local != null) {
    tagLocal = 'existing';
  } else if (remote != null) {
    final r = await _net(() => git.fetchTag(tag));
    if (r.exitCode != 0) {
      throw ReleaseStop(
        'tag_fetch_failed',
        'git fetch $remoteName refs/tags/$tag:refs/tags/$tag failed: '
            '${failureText(r)}; a re-run retries',
        code: 3,
        extra: {'call': 'git fetch $remoteName refs/tags/$tag'},
      );
    }
    tagLocal = 'fetched';
  } else {
    final r = await git.createTag(tag, sha, '$notes\n');
    if (r.exitCode != 0) {
      throw ReleaseStop(
        'tag_create_failed',
        'git tag -a $tag failed: ${trimmed(r.stderr)} (the tagger is git\'s '
            'committer identity)',
        code: 3,
        extra: {'call': 'git tag -a $tag'},
      );
    }
    tagLocal = 'created';
  }

  final String tagRemote;
  if (remote != null) {
    tagRemote = 'existing';
  } else {
    final call = 'git push $remoteName refs/tags/$tag';
    try {
      final r = await git.pushTag(tag);
      if (r.exitCode != 0) {
        throw ReleaseStop(
          'tag_push_failed',
          'git push $remoteName refs/tags/$tag:refs/tags/$tag failed: '
              '${failureText(r)}; the local tag $tag exists and a re-run pushes '
              "it (or stops with tag_mismatch if another clone's $tag reached "
              '$remoteName first); no GitHub release was created',
          code: 3,
          extra: {'call': call},
        );
      }
    } on ReleaseCut catch (cut) {
      // returns only when the tag landed
      await _pushReadBack(git, tag, v, sha, ReleaseCut(cut.limit, call));
    }
    tagRemote = 'pushed';
  }

  final (state, url) = await _githubRelease(git, settings, tag);
  return {
    'ok': true,
    'version': v,
    'tag': tag,
    'release_commit': sha,
    'tag_local': tagLocal,
    'tag_remote': tagRemote,
    'github_release': state,
    'notes': (await git.tagMessage(tag)).replaceFirst(RegExp(r'\n+$'), ''),
    'repo': git.root,
    'tag_repo': git.root,
    // they describe notes derived now, not the tag's
    'warnings': tagLocal == 'created' ? doc['warnings'] : [],
    'release_url': ?url,
    'store': ?doc['store'],
  };
}

/// Runs a network call, turning a bound's cut into the cut stop.
Future<T> _net<T>(Future<T> Function() call) async {
  try {
    return await call();
  } on ReleaseCut catch (cut) {
    throw cutStop(cut);
  }
}

ReleaseStop _conflict(
  String tag,
  String v,
  String sha,
  String at,
  String where,
  String written,
) => ReleaseStop(
  'tag_conflict',
  'tag $tag already points at $at $where, but the release commit for $v is '
      '$sha; $written. Fix the tag by hand: publish never moves, deletes or '
      'forces a tag',
  extra: {'tag': tag, 'tag_commit': at, 'release_commit': sha, 'where': where},
);

ReleaseStop _mismatch(
  String tag,
  String localObject,
  String remoteObject,
  String remote,
  String written,
) => ReleaseStop(
  'tag_mismatch',
  'tag $tag is at the release commit both locally and on $remote, but as '
      'different tag objects (local ${_short(localObject)}, $remote '
      '${_short(remoteObject)}): a lost push race. The release body must be '
      "the tag message on $remote, and $written. Delete the local tag by hand "
      "(git tag -d $tag); a re-run fetches the tag from $remote: publish never "
      'moves, deletes or forces a tag',
  extra: {
    'tag': tag,
    'local_object': localObject,
    'remote_object': remoteObject,
  },
);

String _short(String sha) => sha.length > 12 ? sha.substring(0, 12) : sha;

/// The tag push was cut off, so it may or may not have landed. Reads origin's
/// tag back once, never retried: returns only when origin holds the local tag
/// object at the release commit; another commit is `tag_conflict`, the same
/// commit as another tag object is `tag_mismatch`, absent stops with the
/// limit, and an unreadable origin leaves the state `unknown`.
Future<void> _pushReadBack(
  ReleaseGit git,
  String tag,
  String v,
  String sha,
  ReleaseCut cut,
) async {
  final ({String? commit, bool? annotated, String? object}) remote;
  try {
    remote = await git.remoteTag(tag);
  } on Object catch (e) {
    if (e is! ReleaseStop && e is! ReleaseCut) rethrow;
    throw _unknown(
      cut,
      'reading $tag back from ${git.remote} failed too: the state of the tag '
      'is unknown; no GitHub release was created. The local tag $tag stays, '
      'and a re-run reads ${git.remote} again before it pushes',
    );
  }
  if (remote.commit == null) {
    throw cutStop(
      cut,
      'the tag $tag is not on ${git.remote} (read back), so nothing landed. The '
      'local tag stays and a re-run pushes it; no GitHub release was created',
    );
  }
  if (remote.commit != sha) {
    throw _conflict(
      tag,
      v,
      sha,
      remote.commit!,
      'on ${git.remote}',
      'the push was stopped by ${cut.limit} and another clone\'s tag won; no '
          'GitHub release was created',
    );
  }
  final localObject = await git.text(['rev-parse', 'refs/tags/$tag']);
  if (remote.object != localObject) {
    throw _mismatch(
      tag,
      localObject,
      remote.object!,
      git.remote,
      'the push was stopped by ${cut.limit} and another clone\'s tag won; no '
      'GitHub release was created',
    );
  }
}

ReleaseStop _unknown(ReleaseCut cut, String rest) => ReleaseStop(
  cut.limit,
  '${cut.limit}: ${cut.call} was stopped by its bound and $rest',
  code: 3,
  extra: {'call': cut.call, 'state': 'unknown'},
);

/// The GitHub release step: `created` (with its URL), `existing`, `disabled`
/// or `not_github`.
Future<(String, String?)> _githubRelease(
  ReleaseGit git,
  ReleaseSettings settings,
  String tag,
) async {
  final (:state, :slug) = await git.releaseState(
    tag,
    githubRelease: settings.githubRelease,
  );
  if (state != 'absent') return (state, null);
  final shown = 'gh release create $tag --repo $slug --verify-tag';
  final message = await git.tagMessage(tag);
  final GhResult r;
  try {
    r = await withTempFile(
      message,
      (path) => git.gh([
        'release',
        'create',
        tag,
        '--repo',
        slug!,
        '--verify-tag',
        '--title',
        tag,
        '--notes-file',
        path,
      ], writes: true),
    );
  } on ReleaseCut catch (cut) {
    await _releaseReadBack(
      git,
      settings,
      tag,
      ReleaseCut(cut.limit, 'gh release create $tag'),
    );
    return ('created', 'https://${git.host}/$slug/releases/tag/$tag');
  }
  if (r.exitCode == 0) {
    final out = lossy(r.stdout).trim();
    return ('created', out.isEmpty ? null : out.split('\n').last.trim());
  }
  // another session won the race
  if (lossy(r.stderr).toLowerCase().contains('already exists') &&
      (await git.releaseState(
            tag,
            githubRelease: settings.githubRelease,
          )).state ==
          'existing') {
    return ('existing', null);
  }
  throw ReleaseStop(
    'release_create_failed',
    '$shown failed: ${failureText(r)}; the tag $tag is on ${git.remote}, a re-run '
        'creates only the release',
    code: 3,
    extra: {'call': shown},
  );
}

/// `gh release create` was cut off: reads the release back once, never
/// retried. Returns when it exists (counts as created); not found stops with
/// the limit; a failed read-back leaves the state `unknown`.
Future<void> _releaseReadBack(
  ReleaseGit git,
  ReleaseSettings settings,
  String tag,
  ReleaseCut cut,
) async {
  final String state;
  try {
    state = (await git.releaseState(
      tag,
      githubRelease: settings.githubRelease,
    )).state;
  } on Object catch (e) {
    if (e is! ReleaseStop && e is! ReleaseCut) rethrow;
    throw _unknown(
      cut,
      'reading the release back failed too: the state of the GitHub release '
      'is unknown. The tag $tag is on ${git.remote} and a re-run reads the release '
      'again',
    );
  }
  if (state == 'existing') return;
  throw cutStop(
    cut,
    'the release was not created (read back). The tag $tag is on ${git.remote} and '
    'a re-run creates only the release',
  );
}
