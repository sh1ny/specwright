import '../commit/task_cover.dart' show pyStrip;
import '../settings/yaml.dart' show pySpaceClass;
import 'context.dart';
import 'pair.dart';

// `sw pr identity <dir>`: `pr-pair.sh identity` (pr-pair.sh:180-182, 800-820, 1132-1136). The GitHub repository that
// origin fetches from and pushes to, or why it is not exactly one.

/// `GH_URL`: an http(s), ssh or git URL, or an scp-style `host:` form, of github.com (or ssh.github.com), with an owner
/// and a name.
final RegExp _ghUrl = RegExp(
  r'^(?:(?:https?|ssh|git)://(?:[^@/SP]+@)?(?:ssh\.)?github\.com\.?(?::\d+)?/'
          r'|(?:[^@/SP]+@)?(?:ssh\.)?github\.com\.?:)'
          r'([^/SP]+)/([^/SP]+?)(?:\.git)?/?$'
      .replaceAll('SP', pySpaceClass),
  caseSensitive: false,
);

/// `parse_repo`: `owner/name` of a GitHub URL (stripped first), else null.
String? parseRepo(String url) {
  final m = _ghUrl.firstMatch(pyStrip(url));
  return m == null ? null : '${m.group(1)}/${m.group(2)}';
}

/// `identity(d)`: the answer, or a [PairStop] (`not-a-repo`, `no-origin`, `not-github`, `mismatch`).
Future<Map<String, Object?>> identityOf(PrContext ctx, String dir) async {
  if (dir.isEmpty ||
      !rawDirectory(dir).existsSync() ||
      (await ctx.git(dir, ['rev-parse', '--git-dir'])).code != 0) {
    throw PairStop('not-a-repo', '$dir is not a git work tree');
  }
  final r = await ctx.git(dir, ['remote', 'get-url', 'origin']);
  if (r.code != 0) {
    throw PairStop('no-origin', '$dir has no origin remote');
  }
  final fetchUrl = pyStrip(r.stdout);
  var pushUrls = [
    for (final u in (await ctx.git(dir, [
      'remote',
      'get-url',
      '--push',
      '--all',
      'origin',
    ])).stdout.split('\n'))
      if (pyStrip(u).isNotEmpty) u,
  ];
  if (pushUrls.isEmpty) pushUrls = [fetchUrl];
  final fetch = parseRepo(fetchUrl);
  final push = [for (final u in pushUrls) parseRepo(u)];
  if (fetch == null || push.any((p) => p == null)) {
    throw PairStop(
      'not-github',
      'origin of $dir is not a GitHub repository: fetch $fetchUrl, push ${pushUrls.join(', ')}',
      extra: {'fetch_url': fetchUrl, 'push_urls': pushUrls},
    );
  }
  final pushed = push.cast<String>();
  if (pushed.any((p) => p.toLowerCase() != fetch.toLowerCase())) {
    throw PairStop(
      'mismatch',
      'origin of $dir fetches from $fetch but pushes to ${pushed.join(', ')}; '
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
      return identityOf(ctx, a.positional[0]);
    });
