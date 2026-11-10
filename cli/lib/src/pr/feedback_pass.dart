import 'dart:convert';
import 'dart:io';
import 'dart:math';

import '../settings/rules.dart';
import '../settings/yaml.dart' show pyTruthy;
import '../vcs/codec.dart';
import '../vcs/document.dart';
import 'context.dart';
import 'feedback_environment.dart';
import 'feedback_record.dart';
import 'pair.dart';
import 'settings_commands.dart';
import 'workflow.dart';

typedef PassDocument = Map<String, Object?>;

PassDocument _map(Object? value) => value is Map<String, Object?>
    ? value
    : value is Map<dynamic, dynamic>
    ? value.cast<String, Object?>()
    : <String, Object?>{};
List<Object?> _list(Object? value) => value is List<Object?> ? value : [];
String _text(Object? value) => value is String ? value : '';
String _norm(String value) => value.replaceAll(r'\', '/');
bool _exists(String path) =>
    rawFile(path).existsSync() || rawDirectory(path).existsSync();
List<Object?> _listify(Object? value) => value == null
    ? []
    : value is List<Object?>
    ? value
    : [value];

/// C4: an exact integer is an `int`; one past 64 bits reads as a `double` and is not an integer here.
int? _integer(Object? value) => value is int ? value : null;
bool _positive(Object? value) => (_integer(value) ?? 0) > 0;

PassDocument _record(Object? value, {bool planning = false}) {
  if (value is! Map<String, Object?>) {
    throw StateError('feedback record must be an object');
  }
  final owner = value['owner'];
  if (pyTruthy(owner) && owner is! Map<String, Object?>) {
    throw StateError('feedback record owner must be an object');
  }
  if (planning) {
    for (final key in ['findings', 'round', 'branch']) {
      if (!value.containsKey(key)) {
        throw StateError('feedback record lacks $key');
      }
    }
    final findings = value['findings'];
    if (findings is! List<Object?>) {
      throw StateError('feedback record findings must be a list');
    }
    for (final finding in findings) {
      if (finding is! Map<String, Object?> ||
          [
            'id',
            'source',
            'destination',
            'item',
            'edits',
            'revision',
            'disposition',
          ].any((key) => !finding.containsKey(key)) ||
          finding['edits'] is! List<Object?> ||
          finding['revision'] is! Map<String, Object?> ||
          finding['disposition'] is! Map<String, Object?>) {
        throw StateError('feedback record has an unreadable finding');
      }
    }
  }
  return value;
}

List<PassDocument> _edits(PassDocument finding, String repo) => [
  for (final value in _list(finding['edits']))
    if ((_map(value)['repo'] ?? finding['destination']) == repo) _map(value),
];

String _judgeText(PassDocument edit, bool exists, String content) {
  if (pyTruthy(edit['deleted'])) return exists ? 'pending' : 'done';
  final contains = _listify(edit['contains']),
      absent = _listify(edit['absent']);
  if (contains.isEmpty && absent.isEmpty) return 'unjudgeable';
  if (!exists) return 'pending';
  return contains.every((v) => content.contains(v as String)) &&
          !absent.any((v) => content.contains(v as String))
      ? 'done'
      : 'pending';
}

List<PassDocument> _requests(RepoContext context) {
  if (context.requestsDisabled) return [];
  final rr = context.reviewRequest;
  if (context.reviewers.isNotEmpty) {
    final poster = context.requestAs.isNotEmpty
        ? context.requestAs
        : rr.login.isNotEmpty
        ? rr.login
        : context.login;
    return [
      for (final reviewer in context.reviewers.values)
        if (reviewer.request.isNotEmpty)
          {'body': reviewer.request, 'poster': poster},
    ];
  }
  return rr.body.isNotEmpty && rr.afterFixes
      ? [
          {
            'body': rr.body,
            'poster': rr.login.isEmpty ? context.login : rr.login,
          },
        ]
      : [];
}

String _iso(DateTime time) =>
    '${time.toUtc().toIso8601String().split('.').first}Z';

/// C3: feedback records remain readable by the frozen script and native calls
/// in both directions. Keys, version-2 contents, ownership, migration,
/// exclusive publication and atomic owner replacement belong to the record
/// store; plans are derived again from current snapshots and repository
/// evidence, never persisted as proof of completion.
class FeedbackPass {
  FeedbackPass(this.workflow, {FeedbackRecordStore? records, this.readAs})
    // A field formal would rename the existing records injection parameter.
    // ignore: prefer_initializing_formals
    : _records = records;
  final Workflow workflow;
  FeedbackRecordStore? _records;
  late final _directories = feedbackDirectory(ctx);
  FeedbackRecordStore get records =>
      _records ??= FeedbackRecordStore(_directories.recordDirectory);
  List<String> get _leftLocks => _records?.leftLocks ?? const [];
  final void Function(String repo, String login)? readAs;
  PrContext get ctx => workflow.ctx;
  static final _random = Random.secure();

  PairArgs _args(List<String> argv, Map<String, String> extra) {
    final a = parsePairArgs(argv, {
      '--code': 'code',
      '--store': 'store',
      '--code-repo': 'code_repo',
      '--change': 'change',
      '--snapshot': '+snapshot',
      ...extra,
    });
    needArgs(a, ['code', 'code_repo', 'change']);
    return a;
  }

  Future<PassDocument> _readJson(String path, String error) async {
    final Object? value;
    try {
      value = readJsonFile(path);
    } on Object catch (e) {
      throw PairStop(error, '$path: $e', code: 2);
    }
    if (value is Map<String, Object?>) return value;
    if (error == 'snapshot_unreadable') {
      throw StateError('snapshot must be an object');
    }
    throw PairStop(error, '$path: object required', code: 2);
  }

  Future<Map<String, PassDocument>> _snapshots(PairArgs args) async {
    final out = <String, PassDocument>{};
    for (final spec in args.lists['snapshot'] ?? <String>[]) {
      final split = spec.indexOf('=');
      if (split < 0 ||
          !['code', 'store'].contains(spec.substring(0, split)) ||
          split == spec.length - 1) {
        pairUsage('--snapshot is code=<file> or store=<file>');
      }
      out[spec.substring(0, split)] = await _readJson(
        spec.substring(split + 1),
        'snapshot_unreadable',
      );
    }
    return out;
  }

  Future<PassDocument> _vcs(List<String> argv) => workflow.vcs(argv);

  Future<PassDocument> _owner(String id, String checkout) async {
    final native = await ctx.native(checkout);
    final absolute = hasEscapedBytes(native)
        ? (Directory(native).isAbsolute ? native : '${ctx.cwd}/$native')
        : Directory(native).absolute.path;
    return {
      'id': id,
      'at': _iso(DateTime.now()),
      'checkout': _norm(absolute),
      'host': Platform.localHostname,
    };
  }

  void _checkHeader(PassDocument intent, bool local) {
    Never invalid(String message) =>
        throw PairStop('invalid_intent', message, code: 2);
    if (intent['branch'] is! String || _text(intent['branch']).trim().isEmpty) {
      invalid('branch must be a non-empty string');
    }
    if (!_positive(intent['round'])) {
      invalid('round must be a positive integer');
    }
    final prs = intent['prs'];
    if (prs is! Map<String, Object?> ||
        prs.keys.any((k) => !['code', 'store'].contains(k))) {
      invalid('prs must contain only code and store entries');
    }
    if (local && prs['store'] != null) {
      invalid('prs.store must be absent for a repo-local change');
    }
    for (final entry in prs.entries) {
      if (entry.value == null) continue;
      final pr = _map(entry.value);
      if (entry.value is! Map<String, Object?> ||
          pr['repo'] is! String ||
          !RegExp(r'^[^/\s]+/[^/\s]+$').hasMatch(_text(pr['repo'])) ||
          !_positive(pr['number'])) {
        invalid(
          'prs.${entry.key} must name owner/name and a positive PR number',
        );
      }
    }
  }

  Future<String?> _marker(
    String store,
    String branch,
    String change,
    String prefix,
    String? main,
  ) async {
    final archive = '$prefix/changes/archive';
    final result = await ctx.git(store, [
      'ls-tree',
      '-d',
      '--name-only',
      'refs/heads/$branch',
      '--',
      '$archive/',
    ]);
    if (result.code != 0) return null;
    final expression = RegExp(
      '^${RegExp.escape(archive)}/(?:[0-9]{4}-[0-9]{2}-[0-9]{2}-)?${RegExp.escape(change)}\$',
    );
    final mref = main == null ? null : await workflow.mainRef(store, main);
    final dirs = <String>[];
    for (final directory
        in result.stdout.split('\n').where(expression.hasMatch)) {
      if (mref == null ||
          (await ctx.git(store, ['cat-file', '-e', '$mref:$directory'])).code !=
              0) {
        dirs.add(directory);
      }
    }
    if (dirs.length > 1) {
      throw PairStop(
        'marker_ambiguous',
        'more than one new archive of $change on $branch',
        extra: {'paths': dirs},
      );
    }
    for (final directory in dirs) {
      final path = '$directory/specwright-change.yaml';
      final body = await ctx.git(store, ['show', 'refs/heads/$branch:$path']);
      if (body.code == 0 &&
          RegExp(
            r'^code_changes:\s*none\s*$',
            multiLine: true,
          ).hasMatch(body.stdout)) {
        return path;
      }
    }
    return null;
  }

  Future<PassDocument> write(List<String> argv) async {
    final args = _args(argv, {
      '--intent': 'intent',
      '--store-prefix': 'prefix',
    });
    needArgs(args, ['intent']);
    final intent = await _readJson(args['intent']!, 'invalid_intent');
    for (final key in ['branch', 'round', 'prs', 'findings']) {
      if (!intent.containsKey(key)) {
        throw PairStop('invalid_intent', 'intent lacks $key', code: 2);
      }
    }
    final local = args['store'] == null || args['store']!.isEmpty;
    _checkHeader(intent, local);
    final code = await ctx.native(args['code']!);
    final store = local ? null : await ctx.native(args['store']!);
    final path = records.locate(args['code_repo']!, args['change']!).path;
    if (_exists(path)) {
      throw PairStop(
        'record_exists',
        'a feedback pass record exists at $path; resume that pass',
        extra: {'path': path},
      );
    }
    final rawFindings = intent['findings'];
    if (rawFindings is! List<Object?> ||
        rawFindings.any((v) => v is! Map<String, Object?>)) {
      throw PairStop(
        'invalid_intent',
        'findings must be a list of objects',
        code: 2,
      );
    }
    final findings = rawFindings.map(_map).toList(), seen = <Object?>{};
    final prefix = (args['prefix'] ?? 'openspec').replaceAll(
      RegExp(r'^/+|/+$'),
      '',
    );
    for (final finding in findings) {
      for (final key in [
        'id',
        'item',
        'source',
        'destination',
        'edits',
        'disposition',
        'revision',
      ]) {
        if (!finding.containsKey(key)) {
          throw PairStop('invalid_intent', 'finding lacks $key', code: 2);
        }
      }
      final kind = finding['kind'] ?? 'thread', edits = _list(finding['edits']);
      if (!seen.add(finding['id']) ||
          !['code', 'store', 'both'].contains(finding['destination']) ||
          !['code', 'store'].contains(finding['source']) ||
          finding['item'] is! String ||
          _text(finding['item']).isEmpty ||
          !['thread', 'comment', 'review'].contains(kind) ||
          finding['disposition'] is! Map<String, Object?> ||
          finding['revision'] is! Map<String, Object?> ||
          finding['edits'] is! List<Object?> ||
          edits.isEmpty ||
          edits.any(
            (e) =>
                e is! Map<String, Object?> ||
                e['file'] is! String ||
                _text(e['file']).isEmpty,
          )) {
        throw PairStop(
          'invalid_intent',
          'finding ${finding['id']} is duplicated or malformed',
          code: 2,
        );
      }
      if (local &&
          (finding['source'] != 'code' || finding['destination'] != 'code')) {
        throw PairStop(
          'misrouted',
          'a repo-local finding must use code',
          extra: {'finding': finding['id']},
        );
      }
      if (kind == 'thread' && !_positive(finding['root_id'])) {
        throw PairStop(
          'invalid_intent',
          'thread finding needs a positive root_id',
          code: 2,
        );
      }
      for (final raw in edits) {
        final edit = _map(raw), repo = edit['repo'];
        if (finding['destination'] == 'both'
            ? !['code', 'store'].contains(repo)
            : repo != null && repo != finding['destination']) {
          throw PairStop(
            'invalid_intent',
            'edit repo must match its destination',
            code: 2,
          );
        }
      }
      for (final edit in _edits(finding, 'store')) {
        if (!_norm(_text(edit['file'])).startsWith('$prefix/')) {
          throw PairStop(
            'misrouted',
            '${edit['file']} is outside $prefix/',
            extra: {'finding': finding['id'], 'file': edit['file']},
          );
        }
      }
    }
    final heads = <String, Object?>{}, branch = _text(intent['branch']);
    for (final entry in {'code': code, 'store': ?store}.entries) {
      final result = await ctx.git(entry.value, [
        'rev-parse',
        'refs/heads/$branch',
      ]);
      if (result.code != 0) {
        throw PairStop('branch_missing', '${entry.key} has no branch $branch');
      }
      heads[entry.key] = result.stdout.trim();
    }
    final contexts = store == null
        ? null
        : await workflowContexts(ctx, code, store);
    final marker =
        store != null && findings.any((f) => _edits(f, 'code').isNotEmpty)
        ? await _marker(
            store,
            branch,
            args['change']!,
            prefix,
            contexts?.store?.main,
          )
        : null;
    final owner = await _owner(
      List.generate(
        16,
        (_) => _random.nextInt(256).toRadixString(16).padLeft(2, '0'),
      ).join(),
      code,
    );
    final record = <String, Object?>{
      ...intent,
      'version': 2,
      'owner': owner,
      'change': args['change'],
      'code_repo': args['code_repo'],
      'heads': heads,
      'marker': marker,
      'written_at': owner['at'],
    };
    if ((await workflowVcsChoices(ctx, code)).code == 'gitbutler') {
      final state = await _vcs([
        'state',
        '--repo',
        code,
        '--role',
        'code',
        '--code',
        code,
        '--branch',
        branch,
      ]);
      record['preexisting'] = _list(state['unassigned_paths']).cast<String>()
        ..sort();
    }
    records.writeNew(path, record);
    return {
      'ok': true,
      'path': _norm(path),
      'round': record['round'],
      'heads': heads,
      'marker': marker,
      'owner': owner['id'],
    };
  }

  Future<(String?, bool)> _fixCommit(
    String dir,
    String original,
    String branch,
    Object? round,
  ) async {
    if ((await ctx.git(dir, [
          'merge-base',
          '--is-ancestor',
          original,
          'refs/heads/$branch',
        ])).code !=
        0) {
      return (null, false);
    }
    final log = await ctx.git(dir, [
      'log',
      '$original..refs/heads/$branch',
      '--format=%H%x1f%s%x1f%B%x1e',
    ]);
    if (log.code != 0) return (null, false);
    for (final item in log.stdout.split('\x1e')) {
      if (item.trim().isEmpty) continue;
      final parts = item.replaceAll(RegExp(r'^\n+|\n+$'), '').split('\x1f');
      if (parts.length < 3) continue;
      final want = _integer(round);
      if (want != null &&
          RegExp(
            r'^Feedback-Round:[ \t]*(\d+)[ \t]*$',
            multiLine: true,
          ).allMatches(parts[2]).any((m) => int.tryParse(m[1]!) == want)) {
        return (parts[0].trim(), true);
      }
    }
    return (null, true);
  }

  Future<String> _judge(
    String dir,
    PassDocument edit, [
    String? revision,
  ]) async {
    if (revision != null) {
      final file = await ctx.git(dir, [
        'cat-file',
        'blob',
        '$revision:${edit['file']}',
      ]);
      return _judgeText(edit, file.code == 0, file.stdout);
    }
    final file = rawFile('$dir/${edit['file']}');
    if (pyTruthy(edit['deleted'])) {
      return _judgeText(
        edit,
        file.existsSync() || rawDirectory('$dir/${edit['file']}').existsSync(),
        '',
      );
    }
    if (!file.existsSync()) return _judgeText(edit, false, '');
    final text = utf8
        .decode(file.readAsBytesSync(), allowMalformed: true)
        .replaceAll('\r\n', '\n')
        .replaceAll('\r', '\n');
    return _judgeText(edit, true, text);
  }

  Future<Set<String>> _dirty(String dir) async {
    final status = await ctx.git(dir, ['status', '--porcelain', '-z', '-uall']);
    final parts = status.stdout.split('\x00'), out = <String>{};
    for (var i = 0; i < parts.length; i++) {
      final item = parts[i];
      if (item.length <= 3) continue;
      out.add(item.substring(3));
      if ('RC'.contains(item[0]) || 'RC'.contains(item[1])) i++;
    }
    return out;
  }

  String? _firstSeen(String repo, Object? number, String oid) {
    final state = _directories.stateRoot;
    try {
      final lines = rawFile(
        '$state/heads/${'$repo/$number'.toLowerCase()}/$oid',
      ).readAsLinesSync();
      final line = lines.first.trim();
      if (!RegExp(r'^[A-Za-z]{3}, [0-9]{2} [A-Za-z]{3} [0-9]{4} [0-9:]{8} GMT$')
          .hasMatch(line)) {
        return null;
      }
      return _iso(HttpDate.parse(line));
    } on Object {
      return null;
    }
  }

  Future<PassDocument> _requestState(
    String repo,
    Object? number,
    String branch,
    String tip,
    List<PassDocument> requests,
    String? written,
  ) async {
    final activity = await workflow.list(
      'repos/$repo/activity?ref=refs/heads/$branch&per_page=100',
    );
    String? pushed;
    for (final value in activity) {
      final item = _map(value);
      if (item['after'] == tip) {
        pushed = item['timestamp'] as String?;
        break;
      }
    }
    var cutoff = pushed, source = 'push';
    if (cutoff == null || cutoff.isEmpty) {
      cutoff = _firstSeen(repo, number, tip);
      source = 'first_seen';
    }
    if (cutoff == null || cutoff.isEmpty) {
      cutoff = written;
      source = 'pass_written';
    }
    if (cutoff == null || cutoff.isEmpty) source = 'none';
    final comments = await workflow.list(
      'repos/$repo/issues/$number/comments?per_page=100',
    );
    final states = <PassDocument>[];
    for (final request in requests) {
      final supplied = _text(request['poster']);
      final poster =
          (supplied.isEmpty ? await workflow.ambientLogin() : supplied)
              .toLowerCase();
      final done =
          cutoff != null &&
          cutoff.isNotEmpty &&
          comments.any((raw) {
            final comment = _map(raw);
            return _text(_map(comment['user'])['login']).toLowerCase() ==
                    poster &&
                _text(comment['body']).trim() ==
                    _text(request['body']).trim() &&
                _text(comment['created_at']).compareTo(cutoff!) >= 0;
          });
      states.add({
        'body': request['body'],
        'poster': request['poster'],
        'done': done,
      });
    }
    return {
      'requests': states,
      'push_time': pushed,
      'cutoff': cutoff,
      'cutoff_source': source,
    };
  }

  Future<bool> _reaction(
    String repo,
    String kind,
    Object? target,
    String reaction,
    String viewer,
  ) async {
    final who = viewer.toLowerCase();
    if (kind == 'thread') {
      final content = reaction == '+1' ? '%2B1' : '-1';
      final values = await workflow.list(
        'repos/$repo/pulls/comments/$target/reactions?content=$content&per_page=100',
      );
      return values.any(
        (raw) =>
            _text(_map(_map(raw)['user'])['login']).toLowerCase() == who &&
            _map(raw)['content'] == reaction,
      );
    }
    final content = reaction == '+1' ? 'THUMBS_UP' : 'THUMBS_DOWN';
    final query =
        'query(\$id: ID!, \$cursor: String) { node(id: \$id) { ... on Reactable { reactions(first: 100, content: $content, after: \$cursor) { nodes { user { login } } pageInfo { hasNextPage endCursor } } } } }';
    String? cursor;
    for (var pages = 1; ; pages++) {
      final result = await workflow.gh([
        'api',
        'graphql',
        '-f',
        'query=$query',
        '-f',
        'id=$target',
        if (cursor != null && cursor.isNotEmpty) ...['-f', 'cursor=$cursor'],
      ], repo: repo);
      if (result.exitCode != 0) workflowUnknown(workflow.reason(result));
      late bool more;
      try {
        final data = decodeJson(decodeReplacing(result.stdout));
        final reactions = _map(_map(_map(data)['data'])['node'])['reactions'];
        if (reactions is! Map<String, Object?> ||
            reactions['nodes'] is! List<Object?>) {
          throw const FormatException();
        }
        if (_list(reactions['nodes']).any(
          (raw) => _text(_map(_map(raw)['user'])['login']).toLowerCase() == who,
        )) {
          return true;
        }
        final info = _map(reactions['pageInfo']);
        more = info['hasNextPage'] as bool;
        cursor = info['endCursor'] as String?;
      } on Object {
        workflowUnknown('unreadable reactions of $target');
      }
      if (!more || cursor == null || cursor.isEmpty) return false;
      if (pages >= 50) {
        throw PairStop(
          'response_too_large',
          'GitHub state unknown: response_too_large: reactions of $target exceed 50 pages',
          code: 3,
          extra: {'unknown': true},
        );
      }
    }
  }

  Future<bool> _linked(
    String repo,
    Object? number,
    String kind,
    String url,
  ) async {
    final pr = _map(await workflow.object('repos/$repo/pulls/$number'));
    if (_text(pr['body']).contains(url)) return true;
    final marker = RegExp(
      r'<!--\s*specwright:link\s+(store|code)\s+(\S+)\s*-->',
    );
    final comments = await workflow.list(
      'repos/$repo/issues/$number/comments?per_page=100',
    );
    return comments.any((raw) {
      final match = marker.firstMatch(_text(_map(raw)['body']));
      return match != null && match[1] == kind && match[2] == url;
    });
  }

  Future<PassDocument> plan(List<String> argv) async {
    final args = _args(argv, {'--owner': 'owner'});
    final located = records.locate(args['code_repo']!, args['change']!);
    final value = records.load(located.path);
    if (value == null) {
      return {
        'ok': true,
        'record': false,
        'new_pass_allowed': true,
        'status': 'none',
        'rows': <Object?>[],
        'stops': <Object?>[],
        'delete_record': false,
        'needs_user': false,
      };
    }
    final record = _record(value, planning: true), held = _map(record['owner']);
    final bool? owned = held.isEmpty ? null : args['owner'] == held['id'];
    final snapshots = await _snapshots(args);
    final findings = _list(record['findings']).map(_map).toList();
    final round = record['round'], branch = _text(record['branch']);
    var prs = _map(record['prs']);
    final sources = findings.map((f) => _text(f['source'])).toSet().toList()
      ..sort();
    for (final source in sources) {
      if (!snapshots.containsKey(source)) {
        throw PairStop(
          'snapshot_required',
          'pass plan needs --snapshot $source=<file>',
          code: 2,
          extra: {'source': source},
        );
      }
    }
    final code = await ctx.native(args['code']!);
    final store = args['store'] == null || args['store']!.isEmpty
        ? null
        : await ctx.native(args['store']!);
    final contexts = await workflowContexts(ctx, code, store);
    final directories = {'code': code, 'store': store},
        marker = record['marker'];
    final codeGitbutler =
        (await workflowVcsChoices(ctx, code)).code == 'gitbutler';
    final destinations = [
      for (final repo in ['store', 'code'])
        if (findings.any((f) => _edits(f, repo).isNotEmpty) ||
            repo == 'store' && pyTruthy(marker))
          repo,
    ];
    if (store == null &&
        (destinations.contains('store') ||
            pyTruthy(prs['store']) ||
            sources.contains('store'))) {
      throw PairStop(
        'store_required',
        'this record names the store repo; pass plan needs --store <dir>',
        code: 2,
      );
    }
    final rows = <PassDocument>[], stops = <PassDocument>[];
    final fixes = <String, String?>{}, tips = <String, String>{};
    final slugs = <String, String?>{
      for (final key in ['code', 'store'])
        key:
            (_map(prs[key])['repo'] ??
                    (key == 'code' ? record['code_repo'] : null))
                as String?,
    };
    final storeLogin = contexts.store?.login ?? '';
    if (slugs['store'] != null &&
        storeLogin.isNotEmpty &&
        storeLogin.toLowerCase() != contexts.code.login.toLowerCase()) {
      readAs?.call(slugs['store']!, storeLogin);
    }
    for (final repo in destinations) {
      final directory = directories[repo]!;
      final tip = await ctx.git(directory, ['rev-parse', 'refs/heads/$branch']);
      if (tip.code != 0) {
        throw PairStop('branch_missing', '$repo has no branch $branch');
      }
      tips[repo] = tip.stdout.trim();
      var (sha, reachable) = await _fixCommit(
        directory,
        _text(_map(record['heads'])[repo]),
        branch,
        round,
      );
      if (!reachable) {
        stops.add({
          'reason': 'head_unreachable',
          'repo': repo,
          'detail':
              '${_map(record['heads'])[repo]} is not reachable from $branch',
        });
      }
      final edits = <PassDocument>[
        for (final finding in findings)
          for (final edit in _edits(finding, repo))
            {...edit, 'finding': finding['id']},
        if (repo == 'store' && pyTruthy(marker))
          {'file': marker, 'deleted': true, 'finding': 'marker'},
      ];
      final files = edits.map((e) => _norm(_text(e['file']))).toSet().toList()
        ..sort();
      final row = <String, Object?>{
        'step': 'fix_commit',
        'repo': repo,
        'state': sha == null ? 'todo' : 'done',
        'sha': sha,
        'trailer': 'Feedback-Round: $round',
        'files': files,
      };
      final state = repo == 'code' && codeGitbutler
          ? await _vcs([
              'state',
              '--repo',
              directory,
              '--role',
              'code',
              '--code',
              code,
              '--branch',
              branch,
            ])
          : null;
      final mine = state == null
          ? null
          : <String>{
              ..._list(state['change_paths']).cast<String>(),
              ..._list(state['unassigned_paths']).cast<String>(),
            };
      final verdicts = <(PassDocument, String)>[];
      for (final edit in edits) {
        verdicts.add((
          edit,
          await _judge(
            directory,
            edit,
            mine == null || mine.contains(_norm(_text(edit['file'])))
                ? null
                : tips[repo],
          ),
        ));
      }
      final pending = <PassDocument>[
        for (final verdict in verdicts)
          if (verdict.$2 == 'pending')
            {
              'file': _norm(_text(verdict.$1['file'])),
              'finding': verdict.$1['finding'],
              'reason': 'not_made',
            },
      ];
      for (final verdict in verdicts) {
        if (verdict.$2 == 'unjudgeable') {
          stops.add({
            'reason': 'edit_unjudgeable',
            'repo': repo,
            'finding': verdict.$1['finding'],
            'file': _norm(_text(verdict.$1['file'])),
            'detail': 'the recorded edit has no contains/absent/deleted check, so it cannot be judged done',
          });
        }
      }
      final dirty = mine == null
          ? await _dirty(directory)
          : mine.difference(
              _list(record['preexisting'])
                  .cast<String>()
                  .toSet()
                  .difference(files.toSet()),
            );
      final extra = dirty.difference(files.toSet()).toList()..sort();
      if (extra.isNotEmpty) {
        stops.add({
          'reason': 'unrecorded_change',
          'repo': repo,
          'files': extra,
          'detail': 'the working tree has changes outside the files this pass recorded',
        });
      }
      final uncommitted = dirty.intersection(files.toSet()).toList()..sort();
      final blocked =
          pending.isNotEmpty ||
          verdicts.any((v) => v.$2 == 'unjudgeable') ||
          extra.isNotEmpty;
      if (sha != null && (blocked || uncommitted.isNotEmpty)) {
        row.addAll({'state': 'todo', 'sha': null, 'partial_commit': sha});
        sha = null;
      }
      if (sha == null) {
        row.addAll({
          'pending_edits': pending,
          'committable': !blocked,
          'action': pending.isNotEmpty
              ? 'finish_edits'
              : blocked
              ? 'ask'
              : 'validate_and_commit',
        });
      }
      fixes[repo] = sha;
      rows.add(row);
    }
    List<String> unmet(List<String> ids) => [
      for (final id in ids)
        if (!rows.any(
          (r) =>
              '${r['step']}:${r['repo']}' == id &&
              ['done', 'not_applicable'].contains(r['state']),
        ))
          id,
    ];
    PassDocument? adopted;
    if (destinations.contains('code') && !pyTruthy(prs['code'])) {
      final found = await workflow.discover(
        slugs['code']!,
        branch,
        base: contexts.code.main,
      );
      final opened = _list(found['prs'])
          .map(_map)
          .where((pr) => pr['state'] == 'OPEN')
          .toList();
      if (opened.isNotEmpty) {
        adopted = {'repo': slugs['code'], 'number': opened.first['number']};
        prs = {...prs, 'code': adopted};
      }
    }
    for (final repo in destinations) {
      final pr = _map(prs[repo]);
      final row = <String, Object?>{
        'step': 'push',
        'repo': repo,
        'branch': branch,
        'after': <String>[],
        'blocked': false,
      };
      if (pr.isEmpty && repo == 'code') {
        final after = [
          ...unmet(['fix_commit:code']),
          if (pyTruthy(marker)) ...unmet(['fix_commit:store']),
        ];
        row.addAll({
          'state': 'todo',
          'action': 'ship',
          'after': after,
          'blocked': after.isNotEmpty,
          'detail': 'the code repo now has commits but no open code PR: ship it (push, ensure-pr, review request), then plan again',
        });
      } else if (pr.isEmpty) {
        row.addAll({'state': 'not_applicable', 'share_by_hand': true});
      } else {
        final after = [
          ...unmet(['fix_commit:$repo']),
          if (repo == 'code' && pyTruthy(marker))
            ...unmet(['fix_commit:store']),
        ];
        final complete =
            after.isEmpty &&
            fixes[repo] != null &&
            await workflow.remoteContains(
              directories[repo]!,
              branch,
              fixes[repo]!,
            );
        row.addAll({
          'after': after,
          'blocked': after.isNotEmpty,
          'state': complete ? 'done' : 'todo',
        });
      }
      rows.add(row);
    }
    for (final repo in destinations) {
      final pr = _map(prs[repo]),
          config = repo == 'code' ? contexts.code : contexts.store!;
      final requests = pr.isEmpty ? <PassDocument>[] : _requests(config);
      final row = <String, Object?>{
        'step': 'rerequest',
        'repo': repo,
        'pr': pr.isEmpty ? null : {'repo': pr['repo'], 'number': pr['number']},
        'requests': [
          for (final request in requests) {...request, 'done': false},
        ],
      };
      if (requests.isEmpty) {
        row['state'] = 'not_applicable';
      } else {
        final after = unmet(['push:$repo']);
        row.addAll({
          'after': after,
          'blocked': after.isNotEmpty,
          'state': 'todo',
        });
        if (after.isEmpty) {
          row.addAll(
            await _requestState(
              _text(pr['repo']),
              pr['number'],
              branch,
              tips[repo]!,
              requests,
              (record['written_at'] ?? held['at']) as String?,
            ),
          );
          row['state'] =
              _list(row['requests'])
                  .every((request) => _map(request)['done'] == true)
              ? 'done'
              : 'todo';
        }
      }
      rows.add(row);
    }
    if (adopted != null && pyTruthy(prs['store'])) {
      final codePr = _map(prs['code']), storePr = _map(prs['store']);
      final urls = <String, String>{};
      for (final repo in ['code', 'store']) {
        final pr = _map(prs[repo]);
        urls[repo] = _text(
          _map(
            await workflow.object('repos/${pr['repo']}/pulls/${pr['number']}'),
          )['html_url'],
        );
      }
      final linked =
          await _linked(
            _text(codePr['repo']),
            codePr['number'],
            'store',
            urls['store']!,
          ) &&
          await _linked(
            _text(storePr['repo']),
            storePr['number'],
            'code',
            urls['code']!,
          );
      rows.add({
        'step': 'link',
        'state': linked ? 'done' : 'todo',
        for (final repo in ['code', 'store'])
          repo: {..._map(prs[repo]), 'url': urls[repo]},
      });
    }
    for (final finding in findings) {
      await _findingRows(
        finding,
        snapshots,
        prs,
        slugs,
        fixes,
        contexts.react,
        unmet,
        rows,
        stops,
      );
    }
    final complete =
        stops.isEmpty &&
        rows.every((row) => ['done', 'not_applicable'].contains(row['state']));
    return {
      'ok': true,
      'record': true,
      'round': round,
      'branch': branch,
      'new_pass_allowed': false,
      'status': stops.isNotEmpty
          ? 'stop'
          : complete
          ? 'complete'
          : 'resume',
      'stops': stops,
      'rows': rows,
      'delete_record': complete,
      'needs_user':
          stops.isNotEmpty || rows.any((row) => row['state'] == 'ask'),
      'share_by_hand': [
        for (final row in rows)
          if (row['step'] == 'push' && row['share_by_hand'] == true)
            row['repo'],
      ],
      'path': _norm(located.path),
      'owner': record['owner'],
      'owned': owned,
      if (located.ignoredLegacy != null)
        'legacy_record_ignored': located.ignoredLegacy,
    };
  }

  Future<void> _findingRows(
    PassDocument finding,
    Map<String, PassDocument> snapshots,
    PassDocument prs,
    Map<String, String?> slugs,
    Map<String, String?> fixes,
    bool reactOn,
    List<String> Function(List<String>) unmet,
    List<PassDocument> rows,
    List<PassDocument> stops,
  ) async {
    final source = _text(finding['source']),
        kind = _text(finding['kind'] ?? 'thread');
    final repos = [
      for (final repo in ['store', 'code'])
        if (_edits(finding, repo).isNotEmpty) repo,
    ];
    final snapshot = snapshots[source]!;
    final rawItems =
        snapshot[{
          'thread': 'threads',
          'comment': 'comments',
          'review': 'reviews',
        }[kind]];
    if (pyTruthy(rawItems) &&
        (rawItems is! List<Object?> ||
            rawItems.any((item) => item is! Map<String, Object?>))) {
      throw StateError('snapshot items must be objects in a list');
    }
    final items = _list(rawItems);
    PassDocument? item;
    for (final value in items) {
      if (_map(value)['id'] == finding['item']) {
        item = _map(value);
        break;
      }
    }
    final revision = _map(finding['revision']),
        previous = _map(_map(finding['revision'])['last_reviewer_comment']);
    final viewer = _text(snapshot['viewer']),
        disposition = _map(finding['disposition']);
    final resolve = pyTruthy(disposition['resolve']) && kind == 'thread';
    final String? reaction =
        reactOn && ['+1', '-1'].contains(disposition['react'])
        ? disposition['react'] as String
        : null;
    var answered = item == null, stale = false;
    final activity = <PassDocument>[];
    if (item != null) {
      final comments = _list(item['comments']).map(_map).toList();
      if (kind == 'thread' &&
          (pyTruthy(item['awaiting_reviewer']) ||
              comments.any(
                (comment) =>
                    comment['author'] == snapshot['viewer'] &&
                    _text(comment['at']).compareTo(_text(previous['at'])) > 0,
              ))) {
        answered = true;
      } else if (item['rev'] != revision['rev']) {
        stale = true;
        if (kind == 'thread') {
          for (final comment in comments) {
            final at = _text(comment['at']), edited = _text(comment['edited']);
            if (comment['author'] != snapshot['viewer'] &&
                (at.compareTo(edited) > 0 ? at : edited).compareTo(
                      _text(previous['at']),
                    ) >
                    0) {
              activity.add({
                for (final key in ['id', 'author', 'at', 'edited'])
                  key: comment[key],
              });
            }
          }
        } else {
          activity.add({
            'id': item['id'],
            'author': item['author'],
            'at': item['at'],
            'edited': null,
          });
        }
      }
    }
    final base = {'finding': finding['id']};
    if (stale) {
      stops.add({
        'reason': 'stale_disposition',
        ...base,
        'item': finding['item'],
        'new_activity': activity,
        'detail': 'the reviewer added to or edited this item since the disposition was judged; post nothing, list the activity and ask',
      });
      for (final step in ['reply', 'resolve', 'react']) {
        rows.add({...base, 'step': step, 'state': 'stopped'});
      }
      return;
    }
    final pr = _map(prs[source]);
    final after = [
      for (final repo in repos) ...unmet(['fix_commit:$repo', 'push:$repo']),
    ];
    final links = [
      for (final repo in repos) {'repo': slugs[repo], 'sha': fixes[repo]},
    ];
    rows.add({
      ...base,
      'step': 'reply',
      'state': answered ? 'done' : 'todo',
      'kind': kind,
      'item': finding['item'],
      'root_id': finding['root_id'],
      'pr': {'repo': pr['repo'], 'number': pr['number']},
      'resolve': resolve && !answered,
      'react': answered ? null : reaction,
      'link_commit': links.first,
      'link_commits': links,
      'after': answered ? <String>[] : after,
      'blocked': after.isNotEmpty && !answered,
    });
    if (!resolve) {
      rows.add({...base, 'step': 'resolve', 'state': 'not_applicable'});
    } else if (item == null || pyTruthy(item['resolved'])) {
      rows.add({...base, 'step': 'resolve', 'state': 'done'});
    } else if (!answered) {
      rows.add({
        ...base,
        'step': 'resolve',
        'state': 'todo',
        'after': ['reply:${finding['id']}'],
      });
    } else {
      rows.add({
        ...base,
        'step': 'resolve',
        'state': 'ask',
        'thread': finding['item'],
        'resolve_pending': pyTruthy(item['resolve_pending']),
        'detail': 'the reply is posted but the thread is unresolved: list it and ask; never re-resolve silently',
      });
    }
    if (reaction == null) {
      rows.add({...base, 'step': 'react', 'state': 'not_applicable'});
    } else {
      final target = kind == 'thread' ? finding['root_id'] : finding['item'];
      final seen =
          answered &&
          await _reaction(
            _text(pr['repo'] ?? slugs[source]),
            kind,
            target,
            reaction,
            viewer,
          );
      rows.add({
        ...base,
        'step': 'react',
        'state': seen ? 'done' : 'todo',
        'react': reaction,
        'comment': target,
        'pr': {'repo': pr['repo'], 'number': pr['number']},
        'idempotent': true,
      });
    }
  }

  Future<PassDocument> done(List<String> argv) async {
    final args = _args(argv, {'--owner': 'owner'});
    needArgs(args, ['owner']);
    final path = records.locate(args['code_repo']!, args['change']!).path;
    if (!_exists(path)) {
      return {'ok': true, 'deleted': false, 'record': false};
    }
    return records.withLock(path, () async {
      final value = records.load(path);
      if (value == null) return {'ok': true, 'deleted': false, 'record': false};
      final record = _record(value), owner = _map(record['owner']);
      if (owner['id'] != args['owner']) {
        throw PairStop(
          'not_owner',
          'the record at ${_norm(path)} belongs to ${owner['id'] ?? 'no session'}; show its owner and ask the user',
          extra: {'owner': record['owner']},
        );
      }
      final result = await plan(argv);
      if (result['delete_record'] != true) {
        throw PairStop(
          'not_complete',
          'the pass still has steps to do; run pass plan',
          extra: {'status': result['status']},
        );
      }
      rawFile(path).deleteSync();
      return {'ok': true, 'deleted': true};
    });
  }

  Future<PassDocument> adopt(List<String> argv) async {
    final args = _args(argv, {'--owner': 'owner', '--from': 'from'});
    needArgs(args, ['owner', 'from']);
    final path = records.locate(args['code_repo']!, args['change']!).path;
    if (!_exists(path)) {
      throw PairStop('no_record', 'no feedback pass record at ${_norm(path)}');
    }
    return records.withLock(path, () async {
      final value = records.load(path);
      if (value == null) {
        throw PairStop(
          'no_record',
          'no feedback pass record at ${_norm(path)}',
        );
      }
      final record = _record(value), owner = _map(record['owner']);
      final current = owner['id'],
          from = args['from'] == 'none' ? null : args['from'];
      if (current != from) {
        throw PairStop(
          'not_owner',
          'the record at ${_norm(path)} is owned by ${current ?? 'no session'}, not ${args['from']}; nothing changed',
          extra: {'owner': record['owner']},
        );
      }
      final written = record['written_at'] ?? owner['at'];
      final replacement = <String, Object?>{
        ...record,
        'version': 2,
        'owner': await _owner(args['owner']!, args['code']!),
      };
      if (written != null) {
        replacement['written_at'] = written;
      } else {
        replacement.remove('written_at');
      }
      records.replaceRecord(path, replacement);
      return {
        'ok': true,
        'path': _norm(path),
        'owner': args['owner'],
        'previous': current,
      };
    });
  }

  Future<Map<String, Object?>> run(List<String> argv) async {
    if (argv.isEmpty) pairUsage('pass write|plan|done|adopt ...');
    try {
      final result = await switch (argv.first) {
        'write' => write(argv.sublist(1)),
        'plan' => plan(argv.sublist(1)),
        'done' => done(argv.sublist(1)),
        'adopt' => adopt(argv.sublist(1)),
        _ => pairUsage('pass write|plan|done|adopt ...'),
      };
      return {...result, if (_leftLocks.isNotEmpty) 'lock_left': _leftLocks};
    } on PairStop catch (e) {
      if (_leftLocks.isEmpty) rethrow;
      throw PairStop(
        e.error,
        e.message,
        code: e.code,
        extra: {...e.extra, 'lock_left': _leftLocks},
      );
    } on Object catch (e) {
      if (_leftLocks.isEmpty) rethrow;
      throw PairStop(
        'internal_error',
        '${e.runtimeType}: $e',
        extra: {'lock_left': _leftLocks},
      );
    }
  }
}
