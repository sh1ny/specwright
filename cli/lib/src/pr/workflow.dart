import 'dart:convert';
import 'dart:io';

import '../vcs/codec.dart';
import 'context.dart';
import 'gh.dart';
import 'pair.dart';
import 'identity.dart';
import 'settings_commands.dart';
import 'workflow_transport.dart';
import 'closing.dart';
import '../process/limits.dart';

Never workflowUnknown(String why) => throw PairStop(
  'lookup_failed',
  'GitHub state unknown: $why',
  code: 3,
  extra: {'unknown': true},
);

class Workflow {
  Workflow(this.ctx);
  final PrContext ctx;
  final _repoLogin = <String, String>{};
  final _tokens = <String, String>{};
  String? _ambient;

  Future<String> ambientLogin() async {
    if (_ambient != null) return _ambient!;
    final r = await gh(['api', 'user', '--jq', '.login']);
    final login = decodeReplacing(r.stdout).trim();
    if (r.exitCode != 0 || login.isEmpty) {
      workflowUnknown('cannot read the ambient gh login');
    }
    return _ambient = login;
  }

  Future<String?> fetchRepo(String dir) async {
    try {
      return (await identityOf(ctx, dir))['repo'] as String;
    } on PairStop {
      final r = await ctx.git(dir, ['remote', 'get-url', 'origin']);
      return r.code == 0 ? parseRepo(r.stdout.trim()) : null;
    }
  }

  Map<String, String> unfencedEnvironment() {
    if (!ctx.env.containsKey('AS_SH_ORIG_SET')) {
      return Map<String, String>.of(ctx.env);
    }
    final filter = RegExp(
      r'^(?:GH_TOKEN|GIT_SSH_COMMAND|GIT_TERMINAL_PROMPT|GCM_INTERACTIVE|GIT_ASKPASS|SSH_ASKPASS|GIT_CONFIG_COUNT|GIT_CONFIG_(?:KEY|VALUE)_\d+|AS_SH_ORIG_\w+)$',
    );
    return {
      for (final e in ctx.env.entries)
        if (!filter.hasMatch(e.key)) e.key: e.value,
      for (final key in ctx.env['AS_SH_ORIG_SET']!.split(RegExp(r'\s+')))
        if (key.isNotEmpty) key: ctx.env['AS_SH_ORIG_$key'] ?? '',
    };
  }

  Future<GhResult> gitNetwork(String dir, List<String> args) async {
    final slug = await fetchRepo(dir);
    final limits = resolveLimits(ctx.env, paged: false);
    if (slug == null) {
      return runBoundedCommand(
        ctx.bash,
        dir,
        ['git', ...args],
        environment: unfencedEnvironment(),
        limits: limits,
        helperCommand: ctx.helperCommand,
      );
    }
    var login = _repoLogin[slug.toLowerCase()];
    final top = (await ctx.git(dir, [
      'rev-parse',
      '--show-toplevel',
    ])).stdout.trim();
    final started = (await ctx.git(ctx.cwd, [
      'rev-parse',
      '--show-toplevel',
    ])).stdout.trim();
    if (login == null && top.isNotEmpty && top == started) {
      return runBoundedCommand(
        ctx.bash,
        dir,
        ['git', ...args],
        environment: ctx.env,
        limits: limits,
        helperCommand: ctx.helperCommand,
      );
    }
    login ??= await ambientLogin();
    await tokenFor(login);
    return WorkflowTransport.native(
      directory: dir,
      bash: ctx.bash,
      environment: ctx.env,
      helperCommand: ctx.helperCommand,
    ).fenced(login, ['git', ...args], outer: limits);
  }

  Future<bool> remoteContains(String dir, String branch, String sha) async {
    final r = await gitNetwork(dir, [
      'ls-remote',
      'origin',
      'refs/heads/$branch',
    ]);
    if (r.exitCode != 0 || r.limit != null) {
      throw PairStop(
        'remote_unreadable',
        'git ls-remote origin failed in $dir: ${decodeReplacing(r.stderr).trim()}',
        code: 3,
        extra: {'unknown': true},
      );
    }
    final line = decodeReplacing(r.stdout).trim().split('\n').first.trim();
    if (line.isEmpty) return false;
    final remote = line.split(RegExp(r'\s+')).first;
    if (remote == sha) return true;
    if ((await ctx.git(dir, ['cat-file', '-e', '$remote^{commit}'])).code !=
        0) {
      final top = (await ctx.git(dir, [
        'rev-parse',
        '--show-toplevel',
      ])).stdout.trim();
      final gb = (await ctx.git(dir, ['rev-parse', '--git-path', 'gitbutler']));
      final metadata = gb.stdout.trim();
      final absolute =
          metadata.startsWith('/') ||
          Platform.isWindows &&
              RegExp(r'^(?:[A-Za-z]:[\\/]|\\)').hasMatch(metadata);
      final isolated =
          Directory('$top/.jj').existsSync() ||
          gb.code == 0 &&
              metadata.isNotEmpty &&
              Directory(absolute ? metadata : '$dir/$metadata').existsSync();
      await gitNetwork(dir, [
        'fetch',
        '-q',
        if (isolated) '--refmap=',
        'origin',
        'refs/heads/$branch',
      ]);
    }
    final merged = await ctx.git(dir, [
      'merge-base',
      '--is-ancestor',
      sha,
      remote,
    ]);
    if (merged.code == 0 || merged.code == 1) return merged.code == 0;
    throw PairStop(
      'remote_unreadable',
      'cannot tell whether origin/$branch contains $sha in $dir: ${merged.stderr.trim()}',
      code: 3,
      extra: {'unknown': true},
    );
  }

  Future<String> tokenFor(String login) async {
    if (_tokens[login] case final token?) return token;
    final bare = Map<String, String>.of(ctx.env)
      ..removeWhere(
        (k, v) => [
          'GH_TOKEN',
          'GITHUB_TOKEN',
          'GH_HOST',
          'GH_ENTERPRISE_TOKEN',
          'GITHUB_ENTERPRISE_TOKEN',
        ].contains(k),
      );
    final r = await ctx.gh([
      'auth',
      'token',
      '--hostname',
      'github.com',
      '--user',
      login,
    ], environment: bare);
    if (r.limit != null) {
      throw PairStop(
        r.limit!.label,
        'GitHub state unknown: ${r.limit!.label}: gh auth',
        code: 3,
        extra: {'unknown': true},
      );
    }
    final token = r.exitCode == 0 ? decodeReplacing(r.stdout).trim() : '';
    if (token.isEmpty) {
      throw PairStop(
        'no_credential',
        "no gh credential for '$login' (planning_store.login); run gh auth login",
        code: 3,
        extra: {'login': login},
      );
    }
    final who = await ctx.gh(
      ['api', '--hostname', 'github.com', 'user', '--jq', '.login'],
      environment: {...bare, 'GH_TOKEN': token},
    );
    if (who.limit != null) {
      throw PairStop(
        who.limit!.label,
        'GitHub state unknown: ${who.limit!.label}: gh api',
        code: 3,
        extra: {'unknown': true},
      );
    }
    final actual = decodeReplacing(who.stdout).trim();
    if (actual != login) {
      throw PairStop(
        'identity_mismatch',
        "the token for '$login' resolves to '$actual'; refusing",
        code: 3,
        extra: {'login': login},
      );
    }
    return _tokens[login] = token;
  }

  Future<GhResult> gh(
    List<String> args, {
    String? repo,
    bool limitOk = false,
  }) async {
    for (var i = 0; i < args.length; i++) {
      final m = RegExp(r'^/?repos/([^/]+/[^/?]+)').firstMatch(args[i]);
      if (m != null) {
        repo = m[1];
        break;
      }
      if (args[i] == '--repo' && i + 1 < args.length) {
        repo = args[i + 1];
        break;
      }
    }
    final login = _repoLogin[repo?.toLowerCase()];
    Map<String, String>? env;
    if (login != null) {
      env = {...ctx.env, 'GH_TOKEN': await tokenFor(login)}
        ..removeWhere(
          (k, v) => [
            'GH_HOST',
            'GH_ENTERPRISE_TOKEN',
            'GITHUB_ENTERPRISE_TOKEN',
          ].contains(k),
        );
    }
    final r = await ctx.gh(
      args,
      paged: args.contains('--paginate'),
      environment: env,
    );
    if (r.limit != null && !limitOk) {
      throw PairStop(
        r.limit!.label,
        'GitHub state unknown: ${r.limit!.label}: gh ${args.first}',
        code: 3,
        extra: {'unknown': true},
      );
    }
    return r;
  }

  String reason(GhResult r) {
    final err = decodeReplacing(r.stderr).trim();
    final out = decodeReplacing(r.stdout).trim();
    return err.isNotEmpty
        ? err
        : out.isNotEmpty
        ? out
        : 'gh exited ${r.exitCode}';
  }

  Future<Object?> object(String endpoint) async {
    final r = await gh(['api', endpoint]);
    if (r.exitCode != 0) workflowUnknown(reason(r));
    try {
      return jsonDecode(decodeReplacing(r.stdout));
    } on FormatException catch (e) {
      workflowUnknown('unreadable response: $e');
    }
  }

  Future<List<dynamic>> list(String endpoint) async {
    final r = await gh(['api', '--paginate', endpoint]);
    if (r.exitCode != 0) workflowUnknown(reason(r));
    final text = decodeReplacing(r.stdout);
    final items = <dynamic>[];
    var start = 0, depth = 0;
    var quoted = false, escaped = false, pages = 0;
    try {
      for (var i = 0; i < text.length; i++) {
        final c = text[i];
        if (quoted) {
          if (escaped) {
            escaped = false;
          } else if (c == r'\') {
            escaped = true;
          } else if (c == '"') {
            quoted = false;
          }
        } else if (c == '"') {
          quoted = true;
        } else if (c == '[' || c == '{') {
          if (depth++ == 0) start = i;
        } else if (c == ']' || c == '}') {
          if (--depth == 0) {
            final page = jsonDecode(text.substring(start, i + 1));
            if (page is! List) workflowUnknown('unexpected response shape');
            items.addAll(page);
            pages++;
          }
        } else if (depth == 0 && c.trim().isNotEmpty) {
          workflowUnknown('unreadable response');
        }
      }
      if (depth != 0 || quoted) workflowUnknown('unreadable response');
      if (pages == 0) workflowUnknown('empty response');
    } on FormatException catch (e) {
      workflowUnknown('unreadable response: $e');
    }
    return items;
  }

  Map<String, dynamic> normalize(Map<dynamic, dynamic> p) => {
    'number': p['number'],
    'url': p['html_url'],
    'state': p['merged_at'] != null
        ? 'MERGED'
        : p['state'] == 'open'
        ? 'OPEN'
        : 'CLOSED',
    'base': (p['base'] as Map<dynamic, dynamic>?)?['ref'],
    'head_sha': (p['head'] as Map<dynamic, dynamic>?)?['sha'],
    'merged_at': p['merged_at'],
    'merge_commit_sha': p['merge_commit_sha'],
    'title': p['title'] ?? '',
  };

  Future<Map<String, dynamic>> discover(
    String repo,
    String branch, {
    String? base,
    List<String>? states,
  }) async {
    final owner = repo.split('/').first;
    final items = await list(
      'repos/$repo/pulls?state=all&head=$owner:$branch&per_page=100',
    );
    final own = <int, Map<String, dynamic>>{};
    for (final p in items) {
      final h = p['head'] as Map<dynamic, dynamic>? ?? {};
      if (((h['repo'] as Map<dynamic, dynamic>?)?['full_name'] ?? '')
                  .toString()
                  .toLowerCase() ==
              repo.toLowerCase() &&
          h['ref'] == branch) {
        own[p['number'] as int] = normalize(p as Map<dynamic, dynamic>);
      }
    }
    var prs = own.values.toList()
      ..sort((a, b) => (b['number'] as int).compareTo(a['number'] as int));
    final other = base == null || base.isEmpty
        ? <Map<String, dynamic>>[]
        : prs.where((p) => p['base'] != base).toList();
    if (base != null && base.isNotEmpty) {
      prs = prs.where((p) => p['base'] == base).toList();
    }
    if (states != null && !states.contains('all')) {
      prs = prs
          .where((p) => states.contains((p['state'] as String).toLowerCase()))
          .toList();
    }
    return {
      'ok': true,
      'repo': repo,
      'branch': branch,
      'base': base,
      'prs': prs,
      'other_base': other,
      'newest': prs.isEmpty ? null : prs.first,
    };
  }

  static const closingQuery =
      'query(\$owner: String!, \$name: String!, \$number: Int!) { repository(owner: \$owner, name: \$name) { defaultBranchRef { name } pullRequest(number: \$number) { body baseRefName closingIssuesReferences(first: 100) { nodes { number repository { nameWithOwner } } pageInfo { hasNextPage } } } } }';
  static const closedPrQuery =
      'query(\$owner: String!, \$name: String!, \$number: Int!) { repository(owner: \$owner, name: \$name) { defaultBranchRef { name } pullRequest(number: \$number) { state url body baseRefName mergedAt } } }';
  static const closedIssueQuery =
      'query(\$owner: String!, \$name: String!, \$number: Int!) { repository(owner: \$owner, name: \$name) { issue(number: \$number) { state timelineItems(last: 1, itemTypes: [CLOSED_EVENT]) { nodes { ... on ClosedEvent { createdAt } } } } } }';

  Future<Map<dynamic, dynamic>> graphql(
    String query,
    String repo,
    String number,
  ) async {
    final parts = repo.split('/');
    final r = await gh([
      'api',
      'graphql',
      '-f',
      'query=$query',
      '-f',
      'owner=${parts[0]}',
      '-f',
      'name=${parts[1]}',
      '-F',
      'number=$number',
    ], repo: repo);
    if (r.exitCode != 0) workflowUnknown(reason(r));
    try {
      final data = jsonDecode(decodeReplacing(r.stdout));
      if (data is! Map<dynamic, dynamic> || data['errors'] != null) {
        workflowUnknown(
          'GraphQL errors: ${data is Map<dynamic, dynamic> ? data['errors'] : data}',
        );
      }
      return data;
    } on FormatException {
      workflowUnknown('unreadable GraphQL response');
    }
  }

  Future<List<String>> closingTargets(String body, String repo) async {
    if (body.trim().isEmpty) return [];
    final temp = await Directory.systemTemp.createTemp('sw-closing-');
    try {
      final file = File('${temp.path}/render.json');
      await file.writeAsString(
        jsonEncode({'text': body, 'mode': 'gfm', 'context': repo}),
      );
      final r = await gh([
        'api',
        '-X',
        'POST',
        'markdown',
        '--input',
        file.path,
      ], repo: repo);
      if (r.exitCode != 0) workflowUnknown(reason(r));
      return intendedReferences(decodeReplacing(r.stdout), repo);
    } finally {
      await temp.delete(recursive: true);
    }
  }

  Future<Map<String, Object?>> closingCheck(
    String command,
    List<String> argv,
  ) async {
    final closed = command == 'closed-check';
    final a = parsePairArgs(argv, {
      '--repo': 'repo',
      '--pr': 'pr',
      if (closed) '--repos': 'repos',
      if (closed) '--login': '+login',
    });
    needArgs(a, ['repo', 'pr', if (closed) 'repos']);
    bool slug(String s) => RegExp(r'^[^/\s]+/[^/\s]+$').hasMatch(s);
    final repo = a['repo']!, number = a['pr']!;
    final scope = closed
        ? a['repos']!.split(',').where((s) => s.isNotEmpty).toList()
        : <String>[];
    if (!slug(repo) ||
        !RegExp(r'^\d+$').hasMatch(number) ||
        (closed && (scope.isEmpty || !scope.every(slug)))) {
      pairUsage('--repo is owner/name and --pr a number');
    }
    for (final pair in a.lists['login'] ?? <String>[]) {
      final at = pair.indexOf('=');
      if (at < 1 || at == pair.length - 1 || !slug(pair.substring(0, at))) {
        pairUsage('--login is owner/name=login');
      }
      _repoLogin[pair.substring(0, at).toLowerCase()] = pair.substring(at + 1);
    }
    final data = await graphql(
      closed ? closedPrQuery : closingQuery,
      repo,
      number,
    );
    late Map<dynamic, dynamic> pr;
    late String base, defaultBranch, body;
    List<String> linked = [];
    try {
      final rep = data['data']['repository'];
      pr = rep['pullRequest'] as Map<dynamic, dynamic>;
      if (!pr.containsKey('body') ||
          (closed &&
              (pr['state'] is! String ||
                  pr['url'] is! String ||
                  !pr.containsKey('mergedAt')))) {
        throw const FormatException('missing PR evidence');
      }
      base = pr['baseRefName'] as String;
      defaultBranch = rep['defaultBranchRef']['name'] as String;
      body = (pr['body'] ?? '') as String;
      if (!closed) {
        final refs = pr['closingIssuesReferences'];
        if (refs['pageInfo']['hasNextPage'] as bool) {
          workflowUnknown(
            'the PR closes more than 100 issues; the closing list is cut off',
          );
        }
        linked = [
          for (final n in refs['nodes'] as List<dynamic>)
            '${n['repository']['nameWithOwner']}#${n['number']}',
        ];
      }
    } on PairStop {
      rethrow;
    } on Object {
      workflowUnknown(
        'unexpected GraphQL response shape (PR, default branch or closing list missing)',
      );
    }
    final intended = await closingTargets(body, repo);
    if (!closed) {
      final lowLinked = linked.map((s) => s.toLowerCase()).toSet(),
          lowIntended = intended.map((s) => s.toLowerCase()).toSet();
      final missing = base == defaultBranch
          ? intended.where((s) => !lowLinked.contains(s.toLowerCase())).toList()
          : <String>[];
      final extra = base == defaultBranch
          ? linked.where((s) => !lowIntended.contains(s.toLowerCase())).toList()
          : <String>[];
      return {
        'ok': true,
        'intended': intended,
        'linked': linked,
        'base': base,
        'default_branch': defaultBranch,
        'status': base != defaultBranch
            ? 'not_default_base'
            : missing.isEmpty
            ? 'match'
            : 'mismatch',
        'missing': missing,
        'extra': extra,
      };
    }
    final out = <String, Object?>{
      'ok': true,
      'status': 'merged',
      'pr_url': pr['url'],
      'base': base,
      'default_branch': defaultBranch,
      'intended': intended,
      'open': <String>[],
      'reopened': <String>[],
      'closed': <String>[],
      'outside': <String>[],
    };
    if (pr['state'] != 'MERGED') return {...out, 'status': 'not_merged'};
    final merged = pr['mergedAt'];
    if (merged is! String || merged.isEmpty) {
      workflowUnknown('the merged PR has no mergedAt');
    }
    if (base != defaultBranch) return {...out, 'status': 'not_default_base'};
    for (final target in intended) {
      final split = target.lastIndexOf('#'),
          slug = target.substring(0, target.lastIndexOf('#'));
      if (!scope.any((s) => s.toLowerCase() == slug.toLowerCase())) {
        (out['outside'] as List).add(target);
        continue;
      }
      final read = await graphql(
        closedIssueQuery,
        slug,
        target.substring(split + 1),
      );
      late String state;
      String? last;
      try {
        final issue = read['data']['repository']['issue'];
        state = issue['state'] as String;
        final events = issue['timelineItems']['nodes'] as List;
        last = events.isEmpty ? null : events.last['createdAt'] as String?;
      } on Object {
        workflowUnknown('unexpected GraphQL response shape for $target');
      }
      if (state == 'CLOSED') {
        (out['closed'] as List).add(target);
      } else if (state == 'OPEN') {
        (out[last != null && last.compareTo(merged) >= 0 ? 'reopened' : 'open']
                as List)
            .add(target);
      } else {
        workflowUnknown('$target has unexpected state $state');
      }
    }
    return out;
  }

  int? httpStatus(GhResult r) {
    final m = RegExp(r'\(HTTP (\d{3})\)').firstMatch(decodeReplacing(r.stderr));
    return m == null ? null : int.parse(m[1]!);
  }

  String replyMessage(GhResult r) {
    try {
      final d = jsonDecode(decodeReplacing(r.stdout));
      if (d is Map<dynamic, dynamic> &&
          d['message'] is String &&
          (d['message'] as String).isNotEmpty) {
        return d['message'] as String;
      }
    } on FormatException {
      /* An unreadable message falls back to stderr/exit status. */
    }
    return reason(r);
  }

  Future<Map<String, Object?>> merge(List<String> argv) async {
    final a = parsePairArgs(argv, {
      '--repo': 'repo',
      '--pr': 'pr',
      '--method': 'method',
      '--head': 'head',
    });
    needArgs(a, ['repo', 'pr', 'method', 'head']);
    final repo = a['repo']!,
        number = a['pr']!,
        method = a['method']!,
        head = a['head']!;
    if (!RegExp(r'^[1-9][0-9]*$').hasMatch(number)) {
      pairUsage('--pr must be a positive integer');
    }
    if (!{'merge', 'squash', 'rebase'}.contains(method)) {
      pairUsage('--method must be merge, squash or rebase');
    }
    if (!RegExp(r'^[0-9a-fA-F]{7,40}$').hasMatch(head)) {
      pairUsage('--head must be a commit id of 7 to 40 hex digits');
    }
    final n = int.parse(number),
        r = await gh([
          'api',
          '-X',
          'PUT',
          'repos/$repo/pulls/$number/merge',
          '-f',
          'merge_method=$method',
          '-f',
          'sha=$head',
        ], limitOk: true);
    final status = httpStatus(r), message = replyMessage(r);
    late Map<dynamic, dynamic> pr;
    try {
      pr = await object('repos/$repo/pulls/$number') as Map<dynamic, dynamic>;
    } on PairStop catch (e) {
      throw PairStop(
        e.error,
        e.message,
        code: e.code,
        extra: {...e.extra, 'status': 'unknown'},
      );
    }
    if (pr['merged_at'] != null) {
      return {
        'ok': true,
        'status': 'merged',
        'repo': repo,
        'pr': n,
        'head_sha': (pr['head'] as Map<dynamic, dynamic>?)?['sha'],
        'merge_commit_sha': pr['merge_commit_sha'],
      };
    }
    if (r.exitCode == 0 || status == null || status >= 500) {
      throw PairStop(
        'lookup_failed',
        'GitHub state unknown: merge of $repo#$number is not confirmed: $message',
        code: 3,
        extra: {'unknown': true, 'status': 'unknown'},
      );
    }
    throw PairStop(
      'refused',
      message,
      extra: {
        'status': 'refused',
        'reason': status == 409 ? 'head_changed' : 'refused',
        'http_status': status,
        'repo': repo,
        'pr': n,
      },
    );
  }

  Future<Map<String, Object?>> deleteRemote(List<String> argv) async {
    final a = parsePairArgs(argv, {
      '--repo': 'repo',
      '--branch': 'branch',
      '--head': 'head',
    });
    needArgs(a, ['repo', 'branch', 'head']);
    final repo = a['repo']!, branch = a['branch']!, head = a['head']!;
    if (!RegExp(r'^[0-9a-fA-F]{40}$').hasMatch(head)) {
      pairUsage('--head must be a full 40-digit commit id');
    }
    final path = branch.split('/').map(Uri.encodeComponent).join('/'),
        base = <String, Object?>{'repo': repo, 'branch': branch};
    var r = await gh(['api', 'repos/$repo/git/ref/heads/$path']);
    if (r.exitCode != 0) {
      if (httpStatus(r) == 404) return {'ok': true, 'status': 'gone', ...base};
      workflowUnknown(replyMessage(r));
    }
    Object? sha;
    try {
      sha = (jsonDecode(
        decodeReplacing(r.stdout),
      ) as Map<dynamic, dynamic>)['object']['sha'];
    } on Object {
      workflowUnknown('unreadable ref response');
    }
    if (sha is! String || sha.toLowerCase() != head.toLowerCase()) {
      return {'ok': true, 'status': 'moved', ...base, 'sha': sha};
    }
    final based = await list(
      'repos/$repo/pulls?state=open&base=${Uri.encodeComponent(branch)}&per_page=100',
    );
    if (based.isNotEmpty) {
      return {
        'ok': true,
        'status': 'based_on',
        ...base,
        'prs': [for (final p in based) p['number']],
      };
    }
    r = await gh(['api', '-X', 'DELETE', 'repos/$repo/git/refs/heads/$path']);
    if (r.exitCode == 0) return {'ok': true, 'status': 'deleted', ...base};
    final status = httpStatus(r), message = replyMessage(r);
    if (status == null) workflowUnknown(message);
    if (status == 422 && message.toLowerCase().contains('does not exist')) {
      return {'ok': true, 'status': 'gone', ...base};
    }
    throw PairStop(
      'kept',
      message,
      extra: {'status': 'kept', 'http_status': status, ...base},
    );
  }

  Future<Map<String, Object?>> itemIssues(List<String> argv) async {
    final a = parsePairArgs(argv, {'--repo': 'repo', '--item': '+items'});
    needArgs(a, ['repo']);
    final items = a.lists['items'] ?? <String>[];
    if (items.isEmpty) pairUsage('missing --items');
    final r = await gh([
      'api',
      '--paginate',
      'repos/${a['repo']}/issues?state=all&per_page=100',
      '--jq',
      '.[] | select(.pull_request == null and ((.body // "") | contains("specwright:pr-item "))) | {number, body}',
    ], repo: a['repo']);
    if (r.exitCode != 0) workflowUnknown(reason(r));
    final markers = <String, int>{};
    for (final raw in decodeReplacing(r.stdout).split('\n')) {
      if (raw.trim().isEmpty) continue;
      try {
        final issue = jsonDecode(raw) as Map<dynamic, dynamic>;
        final number = issue['number'] as int;
        final body = (issue['body'] ?? '') as String;
        for (final text in body.split('\n')) {
          final line = text.trim();
          if (line.startsWith('specwright:pr-item ')) {
            final old = markers[line];
            if (old == null || number < old) markers[line] = number;
          }
        }
      } on Object {
        workflowUnknown('unreadable response');
      }
    }
    return {
      'ok': true,
      'found': {
        for (final item in items)
          if (markers.containsKey('specwright:pr-item $item'))
            item: markers['specwright:pr-item $item'],
      },
      'missing': [
        for (final item in items)
          if (!markers.containsKey('specwright:pr-item $item')) item,
      ],
    };
  }

  Future<Map<String, Object?>> run(String command, List<String> argv) async {
    if (command == 'closing-check' || command == 'closed-check') {
      return closingCheck(command, argv);
    }
    if (command == 'merge') return merge(argv);
    if (command == 'delete-remote') return deleteRemote(argv);
    if (command == 'item-issues') return itemIssues(argv);
    if (command == 'expected' || command == 'pair-state') {
      return expectedCommand(command, argv);
    }
    if (command == 'rounds') return rounds(argv);
    if (command == 'discover') {
      final a = parsePairArgs(argv, {
        '--repo': 'repo',
        '--branch': 'branch',
        '--base': 'base',
        '--state': 'state',
      });
      needArgs(a, ['repo', 'branch']);
      return discover(
        a['repo']!,
        a['branch']!,
        base: a['base'],
        states: a['state']
            ?.split(',')
            .map((s) => s.trim().toLowerCase())
            .toList(),
      );
    }
    if (command == 'ensure-pr') {
      final a = parsePairArgs(argv, {
        '--repo': 'repo',
        '--branch': 'branch',
        '--base': 'base',
        '--title': 'title',
        '--body-file': 'body_file',
      });
      needArgs(a, ['repo', 'branch', 'base', 'title', 'body_file']);
      final repo = a['repo']!, branch = a['branch']!, base = a['base']!;
      final prs = (await discover(repo, branch))['prs'] as List;
      final opens = prs.where((p) => p['state'] == 'OPEN').toList();
      for (final p in opens) {
        if (p['base'] != base) {
          throw PairStop(
            'wrong_base',
            'PR #${p['number']} ${p['url']} targets ${p['base']}, not $base; nothing was opened or linked',
            extra: {'pr': p, 'base': p['base']},
          );
        }
      }
      if (opens.isNotEmpty) {
        return {'ok': true, 'action': 'found', 'pr': opens.first};
      }
      final based = prs.where((p) => p['base'] == base).toList();
      if (based.isNotEmpty && based.first['state'] == 'MERGED') {
        throw PairStop(
          'already_merged',
          'PR #${based.first['number']} ${based.first['url']} from $branch is already merged; not opening another',
          extra: {'pr': based.first},
        );
      }
      final r = await gh([
        'pr',
        'create',
        '--repo',
        repo,
        '--head',
        branch,
        '--base',
        base,
        '--title',
        a['title']!,
        '--body-file',
        a['body_file']!,
      ]);
      if (r.exitCode != 0) throw PairStop('create_failed', reason(r));
      final m = RegExp(r'(https://\S+/pull/(\d+))')
          .firstMatch(decodeReplacing(r.stdout));
      if (m == null) {
        throw PairStop(
          'create_failed',
          'gh pr create printed no PR URL: ${decodeReplacing(r.stdout).trim()}',
        );
      }
      return {
        'ok': true,
        'action': 'created',
        'pr': {
          'number': int.parse(m[2]!),
          'url': m[1],
          'state': 'OPEN',
          'base': base,
        },
      };
    }
    if (command == 'link') return link(argv);
    pairUsage('unknown workflow command $command');
  }

  Future<bool> hasRef(String d, String ref) async =>
      (await ctx.git(d, ['show-ref', '--verify', '--quiet', ref])).code == 0;
  Future<String?> mainRef(String d, String main) async {
    for (final ref in ['refs/heads/$main', 'refs/remotes/origin/$main']) {
      if (await hasRef(d, ref)) return ref;
    }
    return null;
  }

  Future<Map<String, Object?>> expected(
    String code,
    String store,
    String branch,
  ) async {
    final c = await workflowContexts(ctx, code, store);
    final cid = await identityOf(ctx, code);
    final cd = await discover(cid['repo'] as String, branch, base: c.code.main);
    final mref = await mainRef(code, c.code.main);
    var commits = 0;
    if (mref != null && await hasRef(code, 'refs/heads/$branch')) {
      final r = await ctx.git(code, [
        'rev-list',
        '--count',
        '$mref..refs/heads/$branch',
      ]);
      if (r.code == 0) {
        commits = int.parse(r.stdout.trim().isEmpty ? '0' : r.stdout.trim());
      }
    }
    dynamic selected(List<dynamic> prs) {
      for (final p in prs) {
        if (p['state'] == 'OPEN') return p;
      }
      return prs.isEmpty ? null : prs.first;
    }

    final cp = cd['prs'] as List;
    final cs = {
      'expected': cp.isNotEmpty || commits > 0,
      'repo': cid['repo'],
      'main': c.code.main,
      'commits': commits,
      'reason': cp.isNotEmpty
          ? 'pr_exists'
          : commits > 0
          ? 'commits'
          : 'none',
      'pr': selected(cp),
      'other_base': cd['other_base'],
    };
    Map<String, Object?>? sid;
    try {
      sid = await identityOf(ctx, store);
    } on PairStop catch (e) {
      if (!['not-github', 'no-origin'].contains(e.error)) rethrow;
    }
    final ss = <String, Object?>{
      'expected': sid != null,
      'repo': sid?['repo'],
      'main': c.store!.main,
      'reason': sid != null ? 'github_origin' : 'no_github_origin',
      'pr': null,
      'other_base': [],
    };
    if (sid != null) {
      final slug = sid['repo'] as String;
      final s = c.store!.login, login = c.code.login;
      if (s.isNotEmpty && s.toLowerCase() != login.toLowerCase()) {
        _repoLogin[slug.toLowerCase()] = s;
      }
      final sd = await discover(slug, branch, base: c.store!.main);
      ss['pr'] = selected(sd['prs'] as List);
      ss['other_base'] = sd['other_base'];
    }
    final members = [
      if (ss['expected'] == true) 'store',
      if (cs['expected'] == true) 'code',
    ];
    final report = members.length == 2
        ? ['both', 'Both PR URLs.']
        : members.contains('code')
        ? ['code_only', 'Code PR only; the store branch is shared by hand.']
        : members.contains('store')
        ? ['store_only', 'Store PR only; the change has no code changes.']
        : [
            'none',
            'No PR to open: the store branch is shared by hand and nothing is watched.',
          ];
    return {
      'ok': true,
      'branch': branch,
      'set': members,
      'code': cs,
      'store': ss,
      'ship': {'report': report[0], 'note': report[1]},
    };
  }

  Future<Map<String, Object?>> expectedCommand(
    String command,
    List<String> argv,
  ) async {
    final a = parsePairArgs(argv, {
      '--code': 'code',
      '--store': 'store',
      '--branch': 'branch',
      if (command == 'pair-state') ...{
        '--snapshot': '+snapshot',
        '--dropped': '+dropped',
        '--carry-over': '+carry',
      },
    });
    needArgs(a, ['code', 'store', 'branch']);
    final e = await expected(
      await ctx.native(a['code']!),
      await ctx.native(a['store']!),
      a['branch']!,
    );
    if (command == 'expected') return e;
    final carry = a.lists['carry'] ?? <String>[];
    if (carry.any((k) => !['code', 'store'].contains(k))) {
      pairUsage(
        '--carry-over is code or store: the side whose archive head carries its reviewers\' reports over',
      );
    }
    final snaps = <String, Map<dynamic, dynamic>>{};
    for (final spec in a.lists['snapshot'] ?? <String>[]) {
      final at = spec.indexOf('=');
      if (at < 0 ||
          !['code', 'store'].contains(spec.substring(0, at)) ||
          at == spec.length - 1) {
        pairUsage('--snapshot is code=<file> or store=<file>');
      }
      final path = spec.substring(at + 1);
      try {
        snaps[spec.substring(0, at)] =
            await readWorkflowJson(path) as Map<dynamic, dynamic>;
      } on Object catch (err) {
        throw PairStop('snapshot_unreadable', '$path: $err', code: 2);
      }
    }
    final dropped = a.lists['dropped'] ?? <String>[];
    final members = e['set'] as List<String>;
    final prs = {
      for (final k in members) k: (e[k] as Map<dynamic, dynamic>)['pr'],
    };
    final states = {for (final k in members) k: prs[k]?['state']};
    final missing = members.where((k) => states[k] == null).toList();
    final merged = members.where((k) => states[k] == 'MERGED').toList();
    final closed = members.where((k) => states[k] == 'CLOSED').toList();
    final open = members.where((k) => states[k] == 'OPEN').toList();
    final ready = <String, bool>{}, blocking = <String, List<String>>{};
    final refresh = <String>[], waiting = <String>[];
    final r = <String, Object?>{
      'ok': true,
      'set': members,
      'states': states,
      'waits': [],
      'ready': ready,
      'waiting_on': waiting,
      'blocking': blocking,
      'missing': missing,
      'refresh': refresh,
      'merged': merged,
      'closed': closed,
      'open': open,
      'stop_waits': false,
      'archive': false,
      'rerequest': false,
      'share_store_by_hand':
          members.contains('code') && !members.contains('store'),
      'prs': prs,
      'ship': e['ship'],
    };
    if (members.isEmpty) return {...r, 'action': 'no_watch'};
    if (missing.isNotEmpty) return {...r, 'action': 'ship'};
    if (merged.isNotEmpty || closed.isNotEmpty) {
      return {
        ...r,
        'action': open.isNotEmpty ? 'split_hand_off' : 'cleanup',
        'stop_waits': true,
      };
    }
    for (final k in members) {
      final s = snaps[k], p = prs[k] as Map<dynamic, dynamic>;
      final b = <String>[];
      if (s == null) {
        b.add('no_snapshot');
      } else {
        if (s['complete'] == false) b.add('incomplete');
        if (s['pending_review'] == true) b.add('pending_review');
        if ((s['state'] ?? 'OPEN') != 'OPEN') b.add('not_open');
        if (s['mergeable'] != 'MERGEABLE') b.add('not_mergeable');
        final ck = s['checks'] as Map<dynamic, dynamic>? ?? {};
        bool truth(dynamic v) =>
            v != null &&
            v != false &&
            v != 0 &&
            v != '' &&
            !(v is Iterable && v.isEmpty) &&
            !(v is Map<dynamic, dynamic> && v.isEmpty);
        final ciDone = ck['ci_pending'] == 0 && !truth(ck['failing']);
        if (!(s['merge_state'] == 'CLEAN' ||
            s['merge_state'] == 'UNSTABLE' && ciDone)) {
          b.add('merge_state:${s['merge_state'] ?? 'None'}');
        }
        if (truth(ck[carry.contains(k) ? 'ci_pending' : 'pending'])) {
          b.add('checks_pending');
        }
        if (truth(ck['failing'])) b.add('checks_failing');
        for (final kind in ['threads', 'comments', 'reviews']) {
          if ((s[kind] as List<dynamic>? ?? <dynamic>[]).any(
            (i) => !dropped.contains('${i['id']}@${i['rev']}'),
          )) {
            b.add(kind);
          }
        }
        if (!carry.contains(k)) {
          for (final reviewer
              in s['reviewers'] as List<dynamic>? ?? <dynamic>[]) {
            if ((reviewer['role'] ?? 'required') == 'required' &&
                    reviewer['state'] != 'reported' ||
                reviewer['role'] == 'advisory' &&
                    reviewer['state'] == 'waiting') {
              b.add('reviewer:${reviewer['login']}:${reviewer['state']}');
            }
          }
        }
        String? stale;
        final re = RegExp(r'https?://[^/]+/([^/]+/[^/]+)/pull/(\d+)');
        final got = re.firstMatch(s['url'] is String ? s['url'] as String : ''),
            want = re.firstMatch((p['url'] ?? '') as String);
        if (s['number'] != p['number'] ||
            got == null ||
            want == null ||
            got[1]!.toLowerCase() != want[1]!.toLowerCase()) {
          var n = s['number']?.toString() ?? '?';
          if (s['number'] == p['number'] && got != null) {
            n = '${got[1]}#${s['number']}';
          }
          stale = 'refresh:pr:$n!=${p['number']}';
        } else if (((s['head_oid'] ?? '') as String).isEmpty ||
            s['head_oid'] != p['head_sha']) {
          String short(String v) =>
              v.isEmpty ? '?' : v.substring(0, v.length < 7 ? v.length : 7);
          stale =
              'refresh:head:${short((s['head_oid'] ?? '') as String)}!=${short((p['head_sha'] ?? '') as String)}';
        }
        if (stale != null) {
          b.insert(0, stale);
          refresh.add(k);
        } else if (b.length == 1 &&
            b.first == 'merge_state:BLOCKED' &&
            truth(s['stale_verdicts'])) {
          (r.putIfAbsent(
            'ready_except_stale_verdicts',
            () => <String>[],
          ) as List).add(k);
        }
      }
      ready[k] = b.isEmpty;
      if (b.isNotEmpty) {
        blocking[k] = b;
        waiting.add(k);
      }
    }
    return {
      ...r,
      'waits': members,
      'action': waiting.isEmpty ? 'ready' : 'wait',
    };
  }

  Future<Map<String, Object?>> rounds(List<String> argv) async {
    final a = parsePairArgs(argv, {
      '--code': 'code',
      '--store': 'store',
      '--branch': 'branch',
    });
    needArgs(a, ['code', 'branch']);
    final code = await ctx.native(a['code']!);
    final store = a['store'] == null ? null : await ctx.native(a['store']!);
    final c = await workflowContexts(ctx, code, store);
    final per = <String, Object?>{};
    final trailers = <String, Map<String, BigInt>>{};
    var top = BigInt.zero;
    var legacy = 0;
    for (final entry in {'code': code, 'store': ?store}.entries) {
      final main = entry.key == 'code' ? c.code.main : c.store!.main;
      final mref = await mainRef(entry.value, main);
      var count = 0;
      var maxTrailer = BigInt.zero;
      final bySha = <String, BigInt>{};
      if (mref != null &&
          await hasRef(entry.value, 'refs/heads/${a['branch']}')) {
        final r = await ctx.git(entry.value, [
          'log',
          '$mref..refs/heads/${a['branch']}',
          '--format=%H%x1f%s%x1f%B%x1e',
        ]);
        if (r.code == 0) {
          for (final rec in r.stdout.split('\x1e')) {
            if (rec.trim().isEmpty) continue;
            final parts = rec
                .replaceAll(RegExp(r'^\n+|\n+$'), '')
                .split('\x1f');
            if (parts.length < 3) continue;
            var number = BigInt.zero;
            if (RegExp(
              'address review feedback',
              caseSensitive: false,
            ).hasMatch(parts[1])) {
              count++;
            }
            for (final m in RegExp(
              r'^Feedback-Round:[ \t]*(\d+)[ \t]*$',
              multiLine: true,
            ).allMatches(parts[2])) {
              final n = BigInt.parse(m[1]!);
              if (n > maxTrailer) maxTrailer = n;
              if (n > number) number = n;
            }
            bySha[parts[0].trim()] = number;
          }
        }
      }
      if (maxTrailer > top) top = maxTrailer;
      if (count > legacy) legacy = count;
      per[entry.key] = {'max_trailer': maxTrailer, 'subject_count': count};
      trailers[entry.key] = bySha;
    }
    final rounds = top > BigInt.zero ? top : BigInt.from(legacy);
    final unpushed = <String, List<String>>{}, unreadable = <String>[];
    if (top > BigInt.zero) {
      if (store != null && trailers['store']!.values.contains(top)) {
        final slug = await fetchRepo(store);
        final s = c.store!.login;
        if (slug != null &&
            s.isNotEmpty &&
            s.toLowerCase() != c.code.login.toLowerCase()) {
          _repoLogin[slug.toLowerCase()] = s;
        }
        if (slug != null && _repoLogin[slug.toLowerCase()] != null) {
          await tokenFor(_repoLogin[slug.toLowerCase()]!);
        }
      }
      for (final e in {'code': code, 'store': ?store}.entries) {
        final missing = <String>[];
        try {
          for (final t in trailers[e.key]!.entries) {
            if (t.value == top &&
                !await remoteContains(e.value, a['branch']!, t.key)) {
              missing.add(t.key);
            }
          }
        } on PairStop catch (err) {
          // The old rounds wrapper catches outer read/transport failures as
          // unreadable, but an as.sh-prefixed nested fence refusal still stops.
          if (err.error == 'fence_refused') rethrow;
          unreadable.add(e.key);
          continue;
        }
        if (missing.isNotEmpty) unpushed[e.key] = missing;
      }
    }
    return {
      'ok': true,
      'rounds': rounds,
      'code': per['code'],
      'store': per['store'],
      'max_fix_rounds': c.maxFixRounds,
      'limit_reached': rounds >= BigInt.parse(c.maxFixRounds.toString()),
      'after_limit': c.afterLimit,
      'unpushed': unpushed,
      'remote_unreadable': unreadable,
    };
  }

  Future<Map<String, Object?>> link(List<String> argv) async {
    final a = parsePairArgs(argv, {
      '--repo': 'repo',
      '--pr': 'pr',
      '--kind': 'kind',
      '--peer-url': 'peer',
      '--login': 'login',
    });
    needArgs(a, ['repo', 'pr', 'kind', 'peer']);
    final repo = a['repo']!, n = a['pr']!, kind = a['kind']!, peer = a['peer']!;
    if (kind != 'code' && kind != 'store') pairUsage('--kind is store or code');
    final pr = await object('repos/$repo/pulls/$n') as Map<dynamic, dynamic>;
    if ((pr['body'] ?? '').toString().contains(peer)) {
      return {'ok': true, 'action': 'skipped', 'reason': 'description'};
    }
    final found = <Map<dynamic, dynamic>>[];
    final marker = RegExp(
      r'<!--\s*specwright:link\s+(store|code)\s+(\S+)\s*-->',
    );
    for (final c in await list('repos/$repo/issues/$n/comments?per_page=100')) {
      final m = marker.firstMatch((c['body'] ?? '').toString());
      if (m != null && m[1] == kind) {
        if (m[2] == peer) {
          return {
            'ok': true,
            'action': 'skipped',
            'reason': 'marker',
            'comment_id': c['id'],
          };
        }
        found.add(c as Map<dynamic, dynamic>);
      }
    }
    var login = a['login'];
    if (login == null || login.isEmpty) {
      final r = await gh(['api', 'user', '--jq', '.login']);
      login = decodeReplacing(r.stdout).trim();
      if (r.exitCode != 0 || login.isEmpty) {
        workflowUnknown('cannot read the ambient gh login');
      }
    }
    final mine = found
        .where(
          (c) =>
              ((c['user'] as Map<dynamic, dynamic>?)?['login'] ?? '')
                  .toString()
                  .toLowerCase() ==
              login!.toLowerCase(),
        )
        .toList();
    final temp = await Directory.systemTemp.createTemp('sw-link-');
    try {
      final f = File('${temp.path}/body.json');
      await f.writeAsString(
        jsonEncode({
          'body':
              '${kind == 'store' ? 'Store' : 'Code'} PR for this change: $peer\n\n<!-- specwright:link $kind $peer -->\n',
        }),
      );
      final update = mine.isNotEmpty;
      var cid = update ? mine.last['id'] : null;
      final endpoint = update
          ? 'repos/$repo/issues/comments/$cid'
          : 'repos/$repo/issues/$n/comments';
      final r = await gh([
        'api',
        '-X',
        update ? 'PATCH' : 'POST',
        endpoint,
        '--input',
        f.path,
      ]);
      if (r.exitCode != 0) throw PairStop('link_failed', reason(r));
      try {
        cid ??= (jsonDecode(
          decodeReplacing(r.stdout),
        ) as Map<dynamic, dynamic>)['id'];
      } on FormatException {
        /* An unreadable message falls back to stderr/exit status. */
      }
      return {
        'ok': true,
        'action': update ? 'updated' : 'created',
        'comment_id': cid,
      };
    } finally {
      await temp.delete(recursive: true);
    }
  }
}

Future<int> runWorkflow(PrContext ctx, String command, List<String> argv) =>
    runPairCommand(ctx, () => Workflow(ctx).run(command, argv));

/// C7: workflow inputs, feedback records and derived rows keep their existing
/// whole-file, uncapped behavior. A new size policy belongs to a separate
/// change; this reader must not truncate or treat an unreadable input as absent.
Future<Object?> readWorkflowJson(String path) async =>
    jsonDecode(await File(path).readAsString(encoding: utf8));
