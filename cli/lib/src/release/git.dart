import 'dart:convert';
import 'dart:io';

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

/// The configured `owner/name` of a `github.com` URL in any form (https, ssh,
/// scp-like, any case), or null.
RegExpMatch? githubUrl(String url) => _githubUrl.firstMatch(url);

final RegExp _githubUrl = RegExp(
  r'^(?:(?:https?|ssh|git)://(?:[^@/\s]+@)?(?:ssh\.)?github\.com\.?(?::\d+)?/|(?:[^@/\s]+@)?(?:ssh\.)?github\.com\.?:)'
  r'([^/\s]+)/([^/\s]+?)(?:\.git)?/?$',
  caseSensitive: false,
);

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
  ReleaseGit(this.root, {Map<String, String>? environment})
    : _environment = environment ?? Platform.environment;

  final String root;
  final Map<String, String> _environment;
  Set<String>? _published;

  /// A local `git` call: no deadline.
  Future<LaunchResult> run(List<String> args, {List<int>? input}) =>
      launch(['git', ...args], cwd: root, input: input);

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
  Future<GhResult> net(List<String> args) => _bounded(
    ['git', ...args],
    'git ${args.take(2).join(' ')}',
    {'GIT_TERMINAL_PROMPT': '0', ..._environment},
  );

  /// `gh <args>` in the repository with `GH_REPO` unset (the call always names
  /// the repository), under the network bounds; [paged] picks the longer
  /// deadline. Throws [ReleaseCut] when a bound stopped it.
  Future<GhResult> gh(List<String> args, {bool paged = false}) => _bounded(
    ['gh', ...args],
    'gh ${args.take(2).join(' ')}',
    {..._environment}..remove('GH_REPO'),
    paged: paged,
  );

  Future<GhResult> _bounded(
    List<String> command,
    String shown,
    Map<String, String> environment, {
    bool paged = false,
  }) async {
    final r = await runBoundedCommand(
      root,
      command,
      environment: environment,
      paged: paged,
    );
    final limit = r.limit;
    if (limit != null) throw ReleaseCut(limit.label, shown);
    return r;
  }

  /// `remote.origin.url` as configured, or null with no origin remote.
  Future<String?> originUrl() async {
    final r = await run(['config', '--get', 'remote.origin.url']);
    final url = trimmed(r.stdout);
    return r.exitCode == 0 && url.isNotEmpty ? url : null;
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
    if (await originUrl() == null) return localTags();
    final cached = _published;
    if (cached != null) return cached;
    const shown = 'git ls-remote --tags --refs origin';
    final r = await net(['ls-remote', '--tags', '--refs', 'origin']);
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
    if (await originUrl() == null) {
      return (commit: null, annotated: null, object: null);
    }
    final r = await net([
      'ls-remote',
      '--tags',
      'origin',
      'refs/tags/$tag',
      'refs/tags/$tag^{}',
    ]);
    if (r.exitCode != 0) {
      final shown = 'git ls-remote --tags origin refs/tags/$tag';
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
        (path) =>
            run(['tag', '-a', '--cleanup=verbatim', '-F', path, tag, sha]),
      );

  /// Fetches origin's [tag] into the local tags, under the network bounds.
  Future<GhResult> fetchTag(String tag) =>
      net(['fetch', 'origin', 'refs/tags/$tag:refs/tags/$tag']);

  /// Pushes only `refs/tags/<tag>` to origin, under the network bounds.
  Future<GhResult> pushTag(String tag) =>
      net(['push', 'origin', 'refs/tags/$tag:refs/tags/$tag']);

  /// The `owner/name` of the GitHub release: the configured origin URL when it
  /// is a github.com URL, else the fetch URL after `insteadOf` rewriting (a
  /// shorthand git expands to github.com), else null (not GitHub).
  Future<String?> releaseSlug() async {
    var m = githubUrl(await originUrl() ?? '');
    if (m == null) {
      final r = await run(['remote', 'get-url', 'origin']);
      m = r.exitCode == 0 ? githubUrl(trimmed(r.stdout)) : null;
    }
    return m == null ? null : '${m[1]}/${m[2]}';
  }

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
