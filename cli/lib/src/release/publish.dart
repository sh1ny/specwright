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
  // before any network read: every URL must name one repository
  await _checkPushDestination(git);
  final loaded = await loadMain(git, settings, args.main);
  await releaseCommitOf(git, loaded, v);
  refuseOlderUntagged(
    settings.tag,
    loaded.rel,
    await git.publishedTags(),
    await git.localTags(),
    v,
  );
  final doc = await statusDocument(
    git,
    settings,
    args,
    loaded: loaded,
    release: false,
    command: 'publish',
  );
  final tag = doc['tag'] as String;
  final sha = doc['release_commit'] as String;
  final notes = doc['notes'] as String;
  if (await git.originUrl() == null) {
    throw ReleaseStop(
      'no_origin',
      'publish needs an origin remote to push the tag to',
    );
  }
  final local = doc['tag_local'] as String?;
  final remote = doc['tag_remote'] as String?;
  for (final (where, at) in [('locally', local), ('on origin', remote)]) {
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
    throw _mismatch(tag, localObject!, remoteObject!, 'nothing was written');
  }

  final String tagLocal;
  if (local != null) {
    tagLocal = 'existing';
  } else if (remote != null) {
    final r = await _net(() => git.fetchTag(tag));
    if (r.exitCode != 0) {
      throw ReleaseStop(
        'tag_fetch_failed',
        'git fetch origin refs/tags/$tag:refs/tags/$tag failed: '
            '${failureText(r)}; a re-run retries',
        code: 3,
        extra: {'call': 'git fetch origin refs/tags/$tag'},
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
    final call = 'git push origin refs/tags/$tag';
    try {
      final r = await git.pushTag(tag);
      if (r.exitCode != 0) {
        throw ReleaseStop(
          'tag_push_failed',
          'git push origin refs/tags/$tag:refs/tags/$tag failed: '
              '${failureText(r)}; the local tag $tag exists and a re-run pushes '
              "it (or stops with tag_mismatch if another clone's $tag reached "
              'origin first); no GitHub release was created',
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
  String written,
) => ReleaseStop(
  'tag_mismatch',
  'tag $tag is at the release commit both locally and on origin, but as '
      'different tag objects (local ${_short(localObject)}, origin '
      '${_short(remoteObject)}): a lost push race. The release body must be '
      "origin's tag message, and $written. Delete the local tag by hand "
      "(git tag -d $tag); a re-run then fetches origin's: publish never "
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
      "reading origin's $tag back failed too: the state of the tag on origin "
      'is unknown; no GitHub release was created. The local tag $tag stays, '
      'and a re-run reads origin again before it pushes',
    );
  }
  if (remote.commit == null) {
    throw cutStop(
      cut,
      'the tag $tag is not on origin (read back), so nothing landed. The '
      'local tag stays and a re-run pushes it; no GitHub release was created',
    );
  }
  if (remote.commit != sha) {
    throw _conflict(
      tag,
      v,
      sha,
      remote.commit!,
      'on origin',
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
      ]),
    );
  } on ReleaseCut catch (cut) {
    await _releaseReadBack(
      git,
      settings,
      tag,
      ReleaseCut(cut.limit, 'gh release create $tag'),
    );
    return ('created', 'https://github.com/$slug/releases/tag/$tag');
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
    '$shown failed: ${failureText(r)}; the tag $tag is on origin, a re-run '
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
      'is unknown. The tag $tag is on origin and a re-run reads the release '
      'again',
    );
  }
  if (state == 'existing') return;
  throw cutStop(
    cut,
    'the release was not created (read back). The tag $tag is on origin and '
    'a re-run creates only the release',
  );
}

/// Stops unless the fetch URL, the push URLs and the configured origin URL
/// name one repository, so the tag lands where it was checked and released. A
/// rewrite (`insteadOf`) to a mirror that is not on github.com is fine. Local
/// reads only.
Future<void> _checkPushDestination(ReleaseGit git) async {
  final raw = await git.originUrl();
  if (raw == null) return;
  final f = await git.run(['remote', 'get-url', 'origin']);
  final p = await git.run(['remote', 'get-url', '--push', '--all', 'origin']);
  if (f.exitCode != 0 || p.exitCode != 0) {
    final why = trimmed(f.stderr).isNotEmpty
        ? trimmed(f.stderr)
        : trimmed(p.stderr);
    throw ReleaseStop(
      'git_failed',
      'git remote get-url origin failed: $why',
      code: 3,
    );
  }
  final fetch = trimmed(f.stdout);
  final pushes = [
    for (final l in lossy(p.stdout).split('\n'))
      if (l.trim().isNotEmpty) l.trim(),
  ];
  if (githubUrl(raw) != null &&
      githubUrl(fetch) != null &&
      !_sameRemote(raw, fetch)) {
    throw ReleaseStop(
      'push_url_mismatch',
      'origin is configured as ${_mask(raw)} but a URL rewrite (insteadOf) '
          'makes git reach ${_mask(fetch)}; the GitHub release would go to the '
          'first, the tag to the second. Nothing was written',
      extra: {'fetch_url': _mask(fetch), 'configured_url': _mask(raw)},
    );
  }
  final bad = [
    for (final u in pushes)
      if (!_sameRemote(fetch, u)) u,
  ];
  if (bad.isNotEmpty) {
    throw ReleaseStop(
      'push_url_mismatch',
      'origin fetches from ${_mask(fetch)} but pushes to '
          '${bad.map(_mask).join(', ')}; publish checks the tag and creates '
          'the release on the fetch URL, so the tag would land elsewhere. '
          'Nothing was written. Publish from a remote whose push and fetch '
          'URLs name the same repository',
      extra: {
        'fetch_url': _mask(fetch),
        'push_urls': pushes.map(_mask).toList(),
      },
    );
  }
}

String _mask(String url) => url.replaceAll(RegExp(r'//[^@/\s]+@'), '//***@');

/// True when two remote URLs name the same repository: the same owner/name on
/// github.com (any URL form, any case), else the same URL apart from a
/// trailing `.git` or slash.
bool _sameRemote(String a, String b) {
  final ma = githubUrl(a), mb = githubUrl(b);
  if (ma != null && mb != null) {
    return ma[1]!.toLowerCase() == mb[1]!.toLowerCase() &&
        ma[2]!.toLowerCase() == mb[2]!.toLowerCase();
  }
  String norm(String u) => u.trim().replaceFirst(RegExp(r'(?:\.git)?/*$'), '');
  return norm(a) == norm(b);
}
