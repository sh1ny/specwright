import 'dart:convert';
import 'dart:io';
import 'dart:math';

import '../fence/fence.dart';
import '../fence/urls.dart';
import '../pr/identity.dart' show parseRepo;
import '../pr/workflow_transport.dart' show hostGhArgs, hostGhEnvironment;
import '../settings/reviewer_config.dart' show sha256Hex;
import 'settings.dart';
import '../pr/gh.dart';
import '../process/launch.dart';
import 'stop.dart';

/// A network command that a bound stopped: [limit] is `deadline_exceeded` or
/// `response_too_large`, [call] names the command (`git push origin`, `gh api
/// --paginate`).
class ReleaseCut implements Exception {
  ReleaseCut(this.limit, this.call);

  final String limit;
  final String call;

  @override
  String toString() => '$limit: $call';
}

/// The stop for a bound: `error` is the limit, exit 3, naming the command.
ReleaseStop cutStop(
  ReleaseCut cut, [
  String what = 'a re-run of publish resumes',
  Map<String, Object?> extra = const {},
]) => ReleaseStop(
  cut.limit,
  '${cut.limit}: ${cut.call} was stopped by its bound; $what',
  code: 3,
  extra: {'call': cut.call, ...extra},
);

/// [bytes] as text, a malformed byte read as U+FFFD.
String lossy(List<int> bytes) => utf8.decode(bytes, allowMalformed: true);

/// [lossy] without the surrounding whitespace.
String trimmed(List<int> bytes) => lossy(bytes).trim();

/// Runs [use] with the path of a temp file holding [text], removed afterwards.
Future<T> withTempFile<T>(
  String text,
  Future<T> Function(String path) use,
) async {
  final dir = await Directory.systemTemp.createTemp('release-notes-');
  try {
    final file = File('${dir.path}${Platform.pathSeparator}notes');
    await file.writeAsString(text);
    return await use(file.path);
  } finally {
    await dir.delete(recursive: true);
  }
}

/// The selected Git remote as read in the environment that runs Git. URLs
/// stay private; only the binding hash is ever printed in a proof.
class ReleaseTarget {
  ReleaseTarget(this.remote, this.host, this.raw, this.fetch, this.pushes)
    : slug = parseRepo(raw, host: host) ?? parseRepo(fetch, host: host);

  final String remote, host, raw, fetch;
  final List<String> pushes;
  final String? slug;

  late final String binding = sha256Hex(
    utf8.encode(
      jsonEncode([remote, host, raw, fetch, pushes, slug?.toLowerCase()]),
    ),
  );

  bool sameRepo(String a, String b) {
    final sa = parseRepo(a, host: host), sb = parseRepo(b, host: host);
    if (sa != null && sb != null) return sa.toLowerCase() == sb.toLowerCase();
    String norm(String url) => url.replaceFirst(RegExp(r'(?:\.git)?/*$'), '');
    return norm(a) == norm(b);
  }

  void check() {
    if (parseRepo(raw, host: host) != null &&
        parseRepo(fetch, host: host) != null &&
        !sameRepo(raw, fetch)) {
      throw ReleaseStop(
        'push_url_mismatch',
        '$remote is configured as ${mask(raw)} but a URL rewrite (insteadOf) '
            'makes Git reach ${mask(fetch)}; nothing was written',
        extra: {'fetch_url': mask(fetch), 'configured_url': mask(raw)},
      );
    }
    if (pushes.any((p) => !sameRepo(fetch, p))) {
      throw ReleaseStop(
        'push_url_mismatch',
        '$remote fetches from ${mask(fetch)} but pushes to '
            '${pushes.map(mask).join(', ')}. Nothing was written. Publish from a '
            'remote whose push and fetch URLs name the same repository',
        extra: {
          'fetch_url': mask(fetch),
          'push_urls': pushes.map(mask).toList(),
        },
      );
    }
  }
}

final _proofSha = RegExp(r'^(?:[0-9a-f]{40}|[0-9a-f]{64})$');
final _random = Random.secure();

/// A proof from the release fetch, not from a user or remote-tracking ref.
class ReleaseMain {
  ReleaseMain(this.branch, this.commit, this.proof, {this.runLogin});

  final String branch, commit;
  final String? proof, runLogin;

  Map<String, Object?> toJson() => {
    'ok': true,
    'main_branch': branch,
    'commit': commit,
    'proof': proof,
    'run_login': ?runLogin,
  };
}

/// How a release command reaches `git` and `gh` in the repository at [root].
///
/// Release network commands keep ADR 0012's bounds (120 s, 300 s for the
/// paged closed-PR read, 32 MiB per stream), and a local `git` call gets no
/// deadline it did not have. `git ls-remote`, `fetch` and `push` and every
/// `gh` call run through `runBoundedCommand`; `gh` starts directly, with
/// `GH_REPO` removed from its environment. Local `git` starts through
/// `launch`. The caller's environment, including a fenced `GH_TOKEN`, is
/// inherited unchanged.
class ReleaseGit {
  ReleaseGit(
    this.root, {
    Map<String, String>? environment,
    this.settings,
    this.runLogin,
  }) : _environment = environment ?? Platform.environment;

  final String root;
  final Map<String, String> _environment;
  final ReleaseSettings? settings;
  final String? runLogin;
  String? _authenticatedLogin;
  String get remote => settings?.remote.name ?? 'origin';
  String get host => settings?.connection.host ?? defaultGitHubHost;
  bool get _fence => settings?.connection.fence ?? true;
  late final _ambient = originalGitEnvironment(_environment)!;
  late final _inherited =
      _fence &&
      runLogin == null &&
      _environment.keys.any((k) => k.toUpperCase() == 'AS_SH_ORIG_SET');
  Map<String, String> get _input => _inherited ? _environment : _ambient;
  Map<String, String>? _gitEnv, _ghEnv;
  ReleaseTarget? _target;
  bool _bound = false, _writeAttempted = false;

  Future<ReleaseTarget?> _readTarget(
    String remote,
    String host,
    Map<String, String> env,
  ) async {
    Future<LaunchResult> read(List<String> args) =>
        _localGit(['git', ...args], env);
    final raw = await read(['config', '--get', 'remote.$remote.url']);
    if (raw.exitCode == 1) {
      final remotes = await read(['remote']);
      if (remotes.exitCode != 0) _unreadable(remote);
      if (!lossy(remotes.stdout).split(RegExp(r'\r?\n')).contains(remote)) {
        return null;
      }
    }
    if (raw.exitCode != 0) _unreadable(remote);
    final fetch = await read(['remote', 'get-url', remote]);
    final push = await read(['remote', 'get-url', '--push', '--all', remote]);
    String url(LaunchResult r) {
      if (r.exitCode != 0) _unreadable(remote);
      final v = trimmed(r.stdout);
      if (v.isEmpty) _unreadable(remote);
      return v;
    }

    return ReleaseTarget(
      remote,
      host,
      url(raw),
      url(fetch),
      url(push).split(RegExp(r'\r?\n')),
    );
  }

  Never _unreadable(String remote) => throw ReleaseStop(
    'remote_unreadable',
    "cannot read release remote '$remote'",
    code: 3,
  );

  Never _changed() => throw ReleaseStop(
    'release_target_changed',
    _writeAttempted
        ? 'The release destination changed or could not be read after a write was attempted; state is unknown. Check the original destination by hand.'
        : 'The release destination changed or could not be read; nothing was written. Fetch a new release proof.',
    code: _writeAttempted ? 3 : 1,
    extra: {if (_writeAttempted) 'state': 'unknown'},
  );

  Future<ReleaseTarget?> bindTarget() async {
    if (_bound) return _target;
    final target = await _readTarget(remote, host, _input);
    target?.check();
    _target = target;
    _bound = true;
    if (target?.slug == null || !_fence) {
      _gitEnv = _ambient;
      _ghEnv = _ambient;
    } else if (_inherited) {
      _gitEnv = _environment;
      _ghEnv = _environment;
    }
    return target;
  }

  Future<void> _credentials() async {
    if (_gitEnv != null) return;
    final discovery = discoveryEnvironment(saveOriginals(_environment));
    Future<GhResult> probe(List<String> args, Map<String, String> env) =>
        _runNetwork(['gh', ...args], env);
    try {
      await checkGhVersion(probe, discovery);
      final configured = runLogin ?? settings?.githubLogin ?? '';
      final login = configured.isEmpty
          ? await resolveLogin(probe, discovery, host: host)
          : configured;
      final verified = await verifyIdentity(
        login,
        probe,
        discovery,
        host: host,
      );
      _authenticatedLogin = login;
      _gitEnv = await prepareFencedCommand(
        const ['git'],
        verified,
        _localGit,
        host: host,
      );
      _ghEnv = verified;
    } on FenceStop catch (e) {
      throw ReleaseStop('fence_refused', e.message, code: e.code);
    }
  }

  Future<void> verifyTarget() async {
    final current = await () async {
      try {
        final now = settings == null ? null : readReleaseSettings(root);
        if (now != null &&
            (now.connection.fence != _fence ||
                now.githubLogin != settings!.githubLogin ||
                now.mainBranch != settings!.mainBranch)) {
          return (ok: false, binding: null);
        }
        final name = now?.remote.name ?? remote,
            hostname = now?.connection.host ?? host;
        final source = await _readTarget(name, hostname, _input);
        final execution = _gitEnv;
        if (execution != null && !identical(execution, _input)) {
          final effective = await _readTarget(name, hostname, execution);
          if (source?.binding != effective?.binding) {
            return (ok: false, binding: null);
          }
        }
        return (ok: true, binding: source?.binding);
      } on ReleaseStop {
        return (ok: false, binding: null);
      }
    }();
    if (!current.ok || current.binding != _target?.binding) _changed();
  }

  Future<T> guarded<T>(
    Future<T> Function() action, {
    bool writes = false,
  }) async {
    await bindTarget();
    await verifyTarget();
    if (writes) _writeAttempted = true;
    try {
      return await action();
    } finally {
      await verifyTarget();
    }
  }

  Future<void> _validateBranch(String branch) async {
    if (branch.isEmpty ||
        !await succeeds(['check-ref-format', 'refs/heads/$branch'])) {
      throw ReleaseStop(
        'usage',
        'release needs a main branch name, not a ref or commit',
        code: 2,
      );
    }
  }

  String _proofDigest(ReleaseTarget target, String branch, String commit) =>
      sha256Hex(utf8.encode(jsonEncode([target.binding, branch, commit])));

  String _encodeProof(String branch, String commit, String digest) =>
      base64Url.encode(utf8.encode(jsonEncode([branch, commit, digest])));

  Future<File> _receipt(String digest) async {
    final dir = await text(['rev-parse', '--absolute-git-dir']);
    if (dir.isEmpty) {
      throw ReleaseStop(
        'release_proof_missing',
        'cannot find release receipt directory',
      );
    }
    return File('$dir/specwright-release-proofs/$digest');
  }

  Future<void> _recordProof(File receipt) async {
    try {
      await receipt.parent.create(recursive: true);
      await receipt.create(exclusive: true);
    } on PathExistsException {
      if (await FileSystemEntity.type(receipt.path, followLinks: false) ==
          FileSystemEntityType.file) {
        return;
      }
      throw ReleaseStop(
        'release_proof_missing',
        'release receipt is not a regular file',
      );
    } on FileSystemException {
      throw ReleaseStop(
        'release_proof_missing',
        'cannot record the release fetch receipt',
      );
    }
  }

  Future<ReleaseMain> proveMain(String branch) async {
    await _validateBranch(branch);
    final target = await bindTarget();
    if (target?.slug == null) {
      final ref = 'refs/heads/$branch';
      final commit = await text([
        'rev-parse',
        '--verify',
        '--quiet',
        '$ref^{commit}',
      ]);
      if (!_proofSha.hasMatch(commit)) {
        throw ReleaseStop('no_main', "main ref '$ref' does not exist");
      }
      return ReleaseMain(branch, commit, null);
    }
    final id = List.generate(
      16,
      (_) => _random.nextInt(256).toRadixString(16).padLeft(2, '0'),
    ).join();
    final ref = 'refs/specwright/release/$id';
    String? observed;
    try {
      final result = await net([
        'fetch',
        '--refmap=',
        '--no-write-fetch-head',
        '--no-tags',
        '--no-prune',
        '--no-prune-tags',
        '--no-recurse-submodules',
        remote,
        'refs/heads/$branch:$ref',
      ]);
      if (result.exitCode != 0) {
        throw ReleaseStop(
          'release_fetch_failed',
          "cannot fetch refs/heads/$branch from '$remote' for release; nothing was written",
          code: 3,
        );
      }
      final commit = await text(['rev-parse', '--verify', '--quiet', ref]);
      if (_proofSha.hasMatch(commit)) observed = commit;
      if (observed == null ||
          await text(['cat-file', '-t', commit]) != 'commit') {
        throw ReleaseStop(
          'release_fetch_failed',
          'release fetch returned no commit',
          code: 3,
        );
      }
      await verifyTarget();
    } finally {
      final id =
          observed ?? await text(['rev-parse', '--verify', '--quiet', ref]);
      if (_proofSha.hasMatch(id) &&
          !await succeeds(['update-ref', '-d', ref, id])) {
        throw ReleaseStop(
          'release_fetch_cleanup_failed',
          'cannot remove the private release ref',
          code: 3,
        );
      }
    }
    final commit = observed;
    final digest = _proofDigest(target!, branch, commit);
    await _recordProof(await _receipt(digest));
    return ReleaseMain(
      branch,
      commit,
      _encodeProof(branch, commit, digest),
      runLogin: _authenticatedLogin,
    );
  }

  Future<ReleaseMain> verifyProof(String proof, String main) async {
    final target = await bindTarget();
    if (target?.slug == null) _changed();
    final Object? fields;
    try {
      fields = jsonDecode(utf8.decode(base64Url.decode(proof)));
    } on FormatException {
      _changed();
    }
    if (fields is! List ||
        fields.length != 3 ||
        fields[0] is! String ||
        fields[1] is! String) {
      _changed();
    }
    final branch = fields[0] as String, commit = fields[1] as String;
    final digest = _proofDigest(target!, branch, commit);
    if (!_proofSha.hasMatch(commit) ||
        branch != main ||
        _encodeProof(branch, commit, digest) != proof ||
        !await refExists(commit)) {
      _changed();
    }
    final receipt = await _receipt(digest);
    if (await FileSystemEntity.type(receipt.path, followLinks: false) !=
        FileSystemEntityType.file) {
      throw ReleaseStop(
        'release_proof_missing',
        'no release fetch receipt for this checkout; run release prove-main again',
      );
    }
    await _validateBranch(branch);
    await verifyTarget();
    return ReleaseMain(branch, commit, proof);
  }

  Set<String>? _published;

  /// A local `git` call: no deadline.
  Future<LaunchResult> run(List<String> args, {List<int>? input}) =>
      _localGit(['git', ...args], _ambient, input: input);
  Future<LaunchResult> _localGit(
    List<String> command,
    Map<String, String> env, {
    List<int>? input,
  }) => launch(command, cwd: root, input: input, environment: env);

  /// The trimmed stdout of a local `git` call.
  Future<String> text(List<String> args) async =>
      trimmed((await run(args)).stdout);

  /// True when a local `git` call exits 0.
  Future<bool> succeeds(List<String> args) async =>
      (await run(args)).exitCode == 0;

  /// True when [ref] names a commit.
  Future<bool> refExists(String ref) =>
      succeeds(['rev-parse', '--verify', '--quiet', '$ref^{commit}']);

  /// True when [sha] is an ancestor of [tip].
  Future<bool> isAncestor(String sha, String tip) =>
      succeeds(['merge-base', '--is-ancestor', sha, tip]);

  /// A `git` command that reaches origin (`ls-remote`, `fetch`, `push`), under
  /// the network bounds. Throws [ReleaseCut] when a bound stopped it.
  Future<GhResult> net(List<String> args, {bool writes = false}) async {
    await bindTarget();
    await _credentials();
    return guarded(
      () => _bounded(
        ['git', ...args],
        'git ${args.take(2).join(' ')}',
        {..._gitEnv!, 'GIT_TERMINAL_PROMPT': '0'},
      ),
      writes: writes,
    );
  }

  /// `gh <args>` in the repository with `GH_REPO` unset (the call always names
  /// the repository), under the network bounds; [paged] picks the longer
  /// deadline. Throws [ReleaseCut] when a bound stopped it.
  Future<GhResult> gh(
    List<String> args, {
    bool paged = false,
    bool writes = false,
  }) async {
    await bindTarget();
    await _credentials();
    return guarded(
      () => _bounded(
        ['gh', ...hostGhArgs(args, host)],
        'gh ${args.take(2).join(' ')}',
        hostGhEnvironment(_ghEnv!, host, fenced: _fence),
        paged: paged,
      ),
      writes: writes,
    );
  }

  Future<GhResult> _bounded(
    List<String> command,
    String shown,
    Map<String, String> environment, {
    bool paged = false,
  }) async {
    final r = await _runNetwork(command, environment, paged: paged);
    final limit = r.limit;
    if (limit != null) throw ReleaseCut(limit.label, shown);
    return r;
  }

  Future<GhResult> _runNetwork(
    List<String> command,
    Map<String, String> environment, {
    bool paged = false,
  }) =>
      runBoundedCommand(root, command, environment: environment, paged: paged);

  Future<bool> hasRemote() async {
    if (_bound) return _target != null;
    final r = await run(['remote']);
    if (r.exitCode != 0) _unreadable(remote);
    return lossy(r.stdout).split(RegExp(r'\r?\n')).contains(remote);
  }

  /// The local tags.
  Future<Set<String>> localTags() async {
    final r = await run(['tag', '-l']);
    return r.exitCode == 0
        ? trimmed(r.stdout)
              .split(RegExp(r'\s+'))
              .where((t) => t.isNotEmpty)
              .toSet()
        : {};
  }

  /// The tags that count as published: the ones on origin, or with no origin
  /// remote the local ones. A local tag whose push failed is not published.
  /// Exit 3 (`remote_tags_unreadable`) when origin cannot be read. Read once
  /// per run: publish asks twice (the older-untagged gate and the notes range).
  Future<Set<String>> publishedTags() async {
    if (!await hasRemote()) return localTags();
    final cached = _published;
    if (cached != null) return cached;
    final shown = 'git ls-remote --tags --refs $remote';
    final r = await net(['ls-remote', '--tags', '--refs', remote]);
    if (r.exitCode != 0) {
      throw ReleaseStop(
        'remote_tags_unreadable',
        '$shown failed: ${_why(r)}; no tag was written',
        code: 3,
        extra: {'call': shown},
      );
    }
    const prefix = 'refs/tags/';
    return _published = {
      for (final line in trimmed(r.stdout).split('\n'))
        if (line.contains('\t') &&
            line.substring(line.indexOf('\t') + 1).startsWith(prefix))
          line.substring(line.indexOf('\t') + 1 + prefix.length),
    };
  }

  /// `tag` on origin: the commit it points at (the peeled commit of an
  /// annotated tag, [annotated] true) and the ref's object id; all null when
  /// absent or with no origin remote. Exit 3 when origin cannot be read.
  Future<({String? commit, bool? annotated, String? object})> remoteTag(
    String tag,
  ) async {
    if (!await hasRemote()) {
      return (commit: null, annotated: null, object: null);
    }
    final r = await net([
      'ls-remote',
      '--tags',
      remote,
      'refs/tags/$tag',
      'refs/tags/$tag^{}',
    ]);
    if (r.exitCode != 0) {
      final shown = 'git ls-remote --tags $remote refs/tags/$tag';
      throw ReleaseStop(
        'remote_tags_unreadable',
        '$shown failed: ${_why(r)}; no tag was written',
        code: 3,
        extra: {'call': shown},
      );
    }
    String? object, peeled;
    for (final line in trimmed(r.stdout).split('\n')) {
      final tab = line.indexOf('\t');
      if (tab < 0) continue;
      final name = line.substring(tab + 1);
      if (name == 'refs/tags/$tag') object = line.substring(0, tab);
      if (name == 'refs/tags/$tag^{}') peeled = line.substring(0, tab);
    }
    if (object == null) return (commit: null, annotated: null, object: null);
    return (
      commit: peeled ?? object,
      annotated: peeled != null,
      object: object,
    );
  }

  /// The message of local tag [tag], with one final newline. Exit 3
  /// (`git_failed`) when `git tag -l` fails.
  Future<String> tagMessage(String tag) async {
    final r = await run(['tag', '-l', '--format=%(contents)', tag]);
    if (r.exitCode != 0) {
      throw ReleaseStop(
        'git_failed',
        'git tag -l $tag failed: ${trimmed(r.stderr)}',
        code: 3,
      );
    }
    return '${lossy(r.stdout).replaceFirst(RegExp(r'\n+$'), '')}\n';
  }

  /// Creates the annotated local tag [tag] at [sha] with [message] verbatim,
  /// passed through a temp file that is removed after the call.
  Future<LaunchResult> createTag(String tag, String sha, String message) =>
      withTempFile(
        message,
        (path) => guarded(
          () => run(['tag', '-a', '--cleanup=verbatim', '-F', path, tag, sha]),
          writes: true,
        ),
      );

  /// Fetches origin's [tag] into the local tags, under the network bounds.
  Future<GhResult> fetchTag(String tag) => net([
    'fetch',
    '--refmap=',
    '--no-write-fetch-head',
    '--no-tags',
    '--no-prune',
    '--no-prune-tags',
    '--no-recurse-submodules',
    remote,
    'refs/tags/$tag:refs/tags/$tag',
  ], writes: true);

  /// Pushes only `refs/tags/<tag>` to origin, under the network bounds.
  Future<GhResult> pushTag(String tag) =>
      net(['push', remote, 'refs/tags/$tag:refs/tags/$tag'], writes: true);

  /// The `owner/name` of the GitHub release: the configured origin URL when it
  /// is a github.com URL, else the fetch URL after `insteadOf` rewriting (a
  /// shorthand git expands to github.com), else null (not GitHub).
  Future<String?> releaseSlug() async => (await bindTarget())?.slug;

  /// The GitHub release of [tag]: `existing`, `absent`, `disabled` (when
  /// [githubRelease] is off) or `not_github`, and the slug when there is one.
  /// One read-only `gh release view`: "release not found" is absent, any other
  /// failure is exit 3 (`release_view_failed`).
  Future<({String state, String? slug})> releaseState(
    String tag, {
    required bool githubRelease,
  }) async {
    if (!githubRelease) return (state: 'disabled', slug: null);
    final slug = await releaseSlug();
    if (slug == null) return (state: 'not_github', slug: null);
    final GhResult r;
    try {
      r = await gh(['release', 'view', tag, '--repo', slug]);
    } on ReleaseCut catch (cut) {
      throw cutStop(cut);
    }
    if (r.exitCode == 0) return (state: 'existing', slug: slug);
    if (lossy(r.stderr).trim().toLowerCase().contains('release not found')) {
      return (state: 'absent', slug: slug);
    }
    final shown = 'gh release view $tag --repo $slug';
    throw ReleaseStop(
      'release_view_failed',
      '$shown failed: ${_why(r)}; a re-run of publish resumes',
      code: 3,
      extra: {'call': shown},
    );
  }
}

/// A failed bounded call's reason: its stderr, else `exit <n>`.
String _why(GhResult r) {
  final err = trimmed(r.stderr);
  return err.isEmpty ? 'exit ${r.exitCode}' : err;
}

/// [why] for callers outside this file.
String failureText(GhResult r) => _why(r);
