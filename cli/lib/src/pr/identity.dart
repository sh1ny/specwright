import 'dart:io' show Directory;

import '../commit/task_cover.dart' show pyStrip;
import '../fence/urls.dart';
import '../settings/rules.dart' show RemoteSelection;
import '../settings/values.dart' show pySpaceClass;
import 'context.dart';
import 'pair.dart';
import 'settings_commands.dart' show prGitHubSettings;

/// URL syntax supported by GitHub, independent of the configured hostname.
final RegExp _repoUrl = RegExp(
  r'^(?:(?:https?|ssh|git)://(?:[^@/SP]+@)?[^:@/SP]+(?::\d+)?/'
          r'|(?:[^@/SP]+@)?[^:@/SP]+:)'
          r'([^/?#SP]+)/([^/?#SP]+?)(?:\.git)?/?$'
      .replaceAll('SP', pySpaceClass),
  caseSensitive: false,
);

String? parseRepo(String url, {String host = defaultGitHubHost}) {
  final text = pyStrip(url);
  if (!ghUrl(text, host: host)) return null;
  final m = _repoUrl.firstMatch(text);
  return m == null ? null : '${m.group(1)}/${m.group(2)}';
}

final _scheme = RegExp(r'^([a-z][a-z0-9+.-]*)://', caseSensitive: false);
final _supported = {'http', 'https', 'ssh', 'git', 'ftp', 'ftps'};

bool _knownDestination(String url) {
  if (url.isEmpty || url.contains(RegExp(r'[\x00-\x1f\x7f]'))) return false;
  final scheme = _scheme.firstMatch(url);
  if (scheme != null) {
    final type = scheme[1]!.toLowerCase();
    if (type == 'file') return url.length > scheme.end;
    return _supported.contains(type) && gitUrlHost(url) != null;
  }
  return !url.contains('://') && !url.contains('::');
}

/// A successful local read proves there is no PR target for this role.
class NoPrRemote extends PairStop {
  NoPrRemote(super.error, super.message, {super.extra});
}

/// Repository the role's selected remote fetches from and pushes to.
/// [NoPrRemote] is positive evidence of an absent or exclusively off-host
/// target; a failed read or a mixed target must never become a manual handoff.
Future<Map<String, Object?>> identityOf(
  PrContext ctx,
  String dir, {
  String host = defaultGitHubHost,
  RemoteSelection selection = const RemoteSelection(),
}) async {
  if (dir.isEmpty ||
      !Directory(dir).existsSync() ||
      (await ctx.git(dir, ['rev-parse', '--git-dir'])).code != 0) {
    throw PairStop('not-a-repo', '$dir is not a git work tree');
  }
  final remote = selection.name;
  PairStop unreadable(String kind) => PairStop(
    'remote_unreadable',
    "cannot read $kind for remote '$remote' in $dir",
  );
  final names = await ctx.git(dir, ['remote']);
  if (names.code != 0) throw unreadable('configured remotes');
  if (!names.names('remote names').split(RegExp(r'\r?\n')).contains(remote)) {
    throw NoPrRemote(
      remote == 'origin' ? 'no-origin' : 'no-remote',
      '$dir has no $remote remote',
    );
  }
  final r = await ctx.git(dir, ['remote', 'get-url', remote]);
  final pr = await ctx.git(dir, [
    'remote',
    'get-url',
    '--push',
    '--all',
    remote,
  ]);
  if (r.code != 0) throw unreadable('fetch URL');
  if (pr.code != 0) throw unreadable('push URLs');
  final fetchUrl = pyStrip(r.names('fetch URL'));
  final pushUrls = pyStrip(pr.names('push URLs')).split(RegExp(r'\r?\n'));
  if (!_knownDestination(fetchUrl) ||
      pushUrls.any((u) => !_knownDestination(u))) {
    throw unreadable('effective URLs');
  }
  final fetch = parseRepo(fetchUrl, host: host);
  final push = [for (final u in pushUrls) parseRepo(u, host: host)];
  if (fetch == null || push.any((p) => p == null)) {
    final urls = pushUrls.map(mask).toList();
    final safeFetch = mask(fetchUrl);
    final message =
        '$remote of $dir is not a GitHub repository on $host: fetch $safeFetch, push ${urls.join(', ')}';
    final details = <String, Object?>{
      'fetch_url': safeFetch,
      'push_urls': urls,
    };
    if (![fetchUrl, ...pushUrls].any((url) => ghUrl(url, host: host))) {
      throw NoPrRemote('not-github', message, extra: details);
    }
    throw PairStop('not-github', message, extra: details);
  }
  final pushed = push.cast<String>();
  if (pushed.any((p) => p.toLowerCase() != fetch.toLowerCase())) {
    throw PairStop(
      'mismatch',
      '$remote of $dir fetches from $fetch but pushes to ${pushed.join(', ')}; '
          'forks and mirrors as push targets are not supported',
      extra: {'fetch': fetch, 'push': pushed},
    );
  }
  final slash = fetch.indexOf('/');
  return {
    'ok': true,
    'repo': fetch,
    'owner': fetch.substring(0, slash),
    'name': fetch.substring(slash + 1),
    'fetch': fetch,
    'push': pushed,
  };
}

/// `cmd_identity`.
Future<int> runIdentity(PrContext ctx, List<String> argv) =>
    runPairCommand(ctx, () async {
      final a = parsePairArgs(argv, const {});
      if (a.positional.length != 1) pairUsage('identity <dir>');
      final dir = a.positional[0];
      final settings = await prGitHubSettings(ctx, directory: dir);
      return identityOf(
        ctx,
        dir,
        host: settings.connection.host,
        selection: settings.remote,
      );
    });
