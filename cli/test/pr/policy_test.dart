import 'dart:convert';
import 'dart:io';

import 'package:specwright_cli/src/pr/gh.dart' show GhResult;
import 'package:specwright_cli/src/pr/policy.dart';
import 'package:specwright_cli/src/process/limit_line.dart' show BoundedLimit;
import 'package:specwright_cli/src/settings/reviewer_config.dart';
import 'package:test/test.dart';

import 'pr_support.dart';

// `sw pr policy` against `pr-pair.sh policy` (pr-pair.sh:2732-2914), with a fake `gh`.

const String head = 'a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2';

const String reviewersMain = '''
pr:
  merge: agent
  merge_method: squash
  reviewers:
    rev[bot]:
      role: required
      timeout: 60
''';

/// The contents API answer for [text].
String contents(String text) => jsonEncode({
  'type': 'file',
  'encoding': 'base64',
  'content': base64.encode(utf8.encode(text)),
});

GhResult notFound() => answer(
  '{"message":"Not Found"}',
  exit: 1,
  stderr: 'gh: Not Found (HTTP 404)\n',
);

/// The digest of a one-reviewer set (login `rev`, required, timeout 60, no report).
final String revDigest = sha256Hex(
  utf8.encode(
    '{"format":2,"reviewers":[{"login":"rev","report":{},"role":"required","timeout":60}]}',
  ),
);

void main() {
  late Fixture f;
  late Directory state;
  setUp(() {
    state = Directory.systemTemp.createTempSync('sw-policy-state-');
    f = Fixture(
      environment: {
        'SPECWRIGHT_STATE_DIR': state.path.replaceAll(r'\', '/'),
        'GH_REPO': 'wrong/repo',
        'PATH': Platform.environment['PATH'] ?? '',
      },
    );
  });
  tearDown(() {
    f.dispose();
    state.deleteSync(recursive: true);
  });

  /// Serves `repos/o/n` and the two contents reads: [main] and [headText] are the settings (null: 404), or a full
  /// answer when [mainRaw] / [headRaw] is given.
  void serve({
    String defaultBranch = 'main',
    String? main,
    String? headText,
    GhResult? mainRaw,
    GhResult? headRaw,
    GhResult? repoRaw,
  }) {
    f.onGh = (args) {
      final endpoint = args[1];
      if (endpoint == 'repos/o/n') {
        return repoRaw ?? answer('{"default_branch":"$defaultBranch"}');
      }
      final ref = Uri.decodeComponent(endpoint.split('?ref=')[1]);
      if (ref == defaultBranch) {
        return mainRaw ?? (main == null ? notFound() : answer(contents(main)));
      }
      return headRaw ??
          (headText == null ? notFound() : answer(contents(headText)));
    };
  }

  File snapshotFile(String name, Object doc) => f.file(name, jsonEncode(doc));

  Future<({int code, Map<String, Object?> json})> policy(
    List<String> argv,
  ) async {
    final code = await runPolicy(f.ctx, argv);
    return (
      code: code,
      json: jsonDecode(f.stdout.trim()) as Map<String, Object?>,
    );
  }

  /// A snapshot of [head] that names the one-reviewer config, reported by `rev`.
  Map<String, Object?> snap({
    String oid = head,
    String? config,
    String state = 'reported',
    String login = 'rev',
  }) => {
    'head_oid': oid,
    'reviewer_config': config ?? revDigest,
    'reviewers': [
      {'login': login, 'state': state},
    ],
  };

  Future<({int code, Map<String, Object?> json})> run({
    Map<String, Object?>? snapshot,
    List<String> extra = const [],
  }) async {
    final s = snapshotFile('code.json', snapshot ?? snap());
    return policy([
      '--repo',
      'o/n',
      '--head',
      head,
      '--snapshot',
      'code=${s.path}',
      ...extra,
    ]);
  }

  group('the reads', () {
    test(
      'three gh calls: the repo, then the default branch and the head',
      () async {
        serve(
          defaultBranch: 'release/1.0',
          main: reviewersMain,
          headText: reviewersMain,
        );
        final r = await run();
        expect(r.code, 0, reason: f.stdout);
        expect(f.ghCalls, [
          ['api', 'repos/o/n'],
          [
            'api',
            'repos/o/n/contents/openspec/specwright.yaml?ref=release%2F1.0',
          ],
          ['api', 'repos/o/n/contents/openspec/specwright.yaml?ref=$head'],
        ]);
        expect(r.json['default_branch'], 'release/1.0');
      },
    );

    test('every call runs without GH_REPO', () async {
      serve(main: reviewersMain, headText: reviewersMain);
      await run();
      expect(f.ghEnvs, hasLength(3));
      for (final env in f.ghEnvs) {
        expect(env, isNotNull);
        expect(env!.containsKey('GH_REPO'), isFalse);
        expect(env['SPECWRIGHT_STATE_DIR'], isNotEmpty);
      }
    });

    test('the ref is percent-encoded as quote(ref, safe="")', () async {
      serve(defaultBranch: 'a b/ü~!', main: '', headText: '');
      await run();
      expect(
        f.ghCalls[1][1],
        'repos/o/n/contents/openspec/specwright.yaml?ref=a%20b%2F%C3%BC~%21',
      );
    });

    test('no file on the default branch is user mode', () async {
      serve(main: null, headText: reviewersMain);
      final r = await run();
      expect(r.code, 0);
      expect(r.json['merge'], 'user');
      expect(r.json['main'], containsPair('pr.merge', 'user'));
      expect(r.json['merge_ready'], {'code': false});
      expect(r.json['merge_reason'], {'code': 'no_required_reviewer'});
    });

    test('no file at the head is lookup_failed', () async {
      serve(main: reviewersMain, headText: null);
      final r = await run();
      expect(r.code, 3);
      expect(r.json['ok'], false);
      expect(r.json['error'], 'lookup_failed');
      expect(r.json['unknown'], true);
      expect(
        r.json['message'],
        'merge policy unknown: no openspec/specwright.yaml readable at $head',
      );
    });

    test('the repo itself missing is lookup_failed too', () async {
      serve(repoRaw: notFound());
      final r = await run();
      expect(r.code, 3);
      expect(
        r.json['message'],
        'merge policy unknown: cannot read the default branch of o/n',
      );
    });

    test('a limit is lookup_failed with exit 3', () async {
      f.onGh = (args) => answer(
        '',
        exit: 124,
        limitLine: 'bounded: deadline_exceeded: gh api\n',
        limit: BoundedLimit.deadlineExceeded,
      );
      final r = await run();
      expect(r.code, 3);
      expect(r.json['error'], 'lookup_failed');
      expect(r.json['unknown'], true);
      expect(
        r.json['message'],
        'merge policy unknown: deadline_exceeded: gh api',
      );
      expect(f.ghCalls, hasLength(1));
    });

    test('another failure is lookup_failed with gh message', () async {
      f.onGh = (args) => answer(
        '{"message":"Bad credentials"}',
        exit: 1,
        stderr: 'gh: Bad credentials (HTTP 401)\n',
      );
      var r = await run();
      expect(r.code, 3);
      expect(r.json['message'], 'merge policy unknown: Bad credentials');
      f.onGh = (args) => answer('', exit: 4, stderr: 'auth needed\n');
      f.out.clear();
      r = await run();
      expect(r.json['message'], 'merge policy unknown: auth needed');
      f.onGh = (args) => answer('', exit: 4);
      f.out.clear();
      r = await run();
      expect(r.json['message'], 'merge policy unknown: gh exited 4');
    });
  });

  group('the contents answer is read strictly (D7)', () {
    Future<Map<String, Object?>> stopFor(String body) async {
      serve(
        main: reviewersMain,
        headText: reviewersMain,
        mainRaw: answer(body),
      );
      final r = await run();
      expect(r.code, 3, reason: body);
      expect(r.json['error'], 'lookup_failed');
      expect(r.json['unknown'], true);
      expect(
        r.json['message'],
        startsWith(
          'merge policy unknown: unreadable openspec/specwright.yaml at main: ',
        ),
        reason: body,
      );
      f.out.clear();
      return r.json;
    }

    String file(
      String content, {
      String type = 'file',
      String enc = 'base64',
    }) => jsonEncode({'type': type, 'encoding': enc, 'content': content});

    test('not a base64 file', () async {
      await stopFor(file('QQ==', type: 'dir'));
      await stopFor(file('QQ==', enc: 'none'));
      await stopFor('[1]');
      await stopFor('not json');
      await stopFor('');
    });

    test('URL-safe characters are refused', () async {
      await stopFor(file('--__'));
      await stopFor(file('ab_d'));
    });

    test('missing padding is refused', () async {
      await stopFor(file('QQ'));
      await stopFor(file('QUI'));
      await stopFor(file('Q'));
    });

    test('too much padding, or padding in the middle, is refused', () async {
      await stopFor(file('QQ==='));
      await stopFor(file('QQ==QQ=='));
      await stopFor(file('=QQQ'));
      await stopFor(file('QUJD='));
    });

    test('a stray character is refused', () async {
      await stopFor(file('QUJD!'));
      await stopFor(file('QU\u00e9D'));
      await stopFor(file('QUJ.'));
    });

    test(
      'white space inside the content is dropped, as GitHub wraps lines',
      () async {
        final b64 = base64.encode(utf8.encode(reviewersMain));
        final wrapped = [
          for (var i = 0; i < b64.length; i += 20)
            b64.substring(i, i + 20 > b64.length ? b64.length : i + 20),
        ].join('\n');
        serve(mainRaw: answer(file('$wrapped\n')), headText: reviewersMain);
        final r = await run();
        expect(r.code, 0, reason: f.stdout);
        expect(r.json['merge'], 'agent');
      },
    );

    test('invalid UTF-8 is refused', () async {
      await stopFor(file(base64.encode([0x70, 0x72, 0x3a, 0xff, 0xfe])));
      await stopFor(file(base64.encode([0xc3])));
    });

    test('a byte-order mark is dropped, once', () async {
      serve(
        mainRaw: answer(
          file(
            base64.encode([0xef, 0xbb, 0xbf, ...utf8.encode(reviewersMain)]),
          ),
        ),
        headText: reviewersMain,
      );
      final r = await run();
      expect(r.code, 0, reason: f.stdout);
      expect(r.json['merge'], 'agent');
      f.out.clear();
      // a second one is U+FEFF in the text, which the strict check refuses
      await stopFor(
        file(
          base64.encode([
            0xef, 0xbb, 0xbf, 0xef, 0xbb, 0xbf, //
            ...utf8.encode(reviewersMain),
          ]),
        ),
      );
    });

    test('the strict YAML check names the line', () async {
      final json = await stopFor(
        file(
          base64.encode(utf8.encode('pr:\n  merge: agent\n\treviewers: {}\n')),
        ),
      );
      expect(json['message'], contains('line 3'));
    });

    test('a block sequence is refused', () async {
      await stopFor(
        file(base64.encode(utf8.encode('pr:\n  reviewers:\n    - a\n'))),
      );
    });

    test('the head file is read by the same rules', () async {
      serve(main: reviewersMain, headRaw: answer(file('QQ')));
      final r = await run();
      expect(r.code, 3);
      expect(
        r.json['message'],
        startsWith(
          'merge policy unknown: unreadable openspec/specwright.yaml at $head: ',
        ),
      );
    });

    test('an empty file is an empty mapping', () async {
      serve(main: '', headText: '');
      final r = await run();
      expect(r.code, 0);
      expect(r.json['merge'], 'user');
    });
  });

  group('the answer', () {
    test('keys, main and head, in the script order', () async {
      serve(main: reviewersMain, headText: reviewersMain);
      final r = await run();
      expect(r.code, 0, reason: f.stdout);
      expect(r.json.keys, [
        'ok',
        'repo',
        'default_branch',
        'main',
        'head',
        'drift',
        'invalid',
        'merge',
        'merge_method',
        'delete_branch',
        'settle',
        'merge_ready',
        'reported',
        'reviewer_config',
        'merge_reason',
      ]);
      const side = {
        'pr.merge': 'agent',
        'pr.merge_method': 'squash',
        'pr.delete_branch': true,
        'pr.reviewers': {
          'rev': {
            'role': 'required',
            'timeout': 60,
            'request': '',
            'report': <String, Object?>{},
          },
        },
        'pr.settle': 300,
      };
      expect(r.json['main'], side);
      expect(r.json['head'], side);
      expect((r.json['main']! as Map).keys, side.keys);
      expect(r.json['drift'], isEmpty);
      expect(r.json['invalid'], isEmpty);
      expect(r.json['merge'], 'agent');
      expect(r.json['merge_method'], 'squash');
      expect(r.json['delete_branch'], true);
      expect(r.json['settle'], 300);
      expect(r.json['merge_ready'], {'code': true});
      expect(r.json['merge_reason'], {'code': null});
      expect(f.stdout.trimRight().contains('\n'), isFalse);
    });

    test(
      'drift lists every key that differs, compared by type and value',
      () async {
        serve(
          main: reviewersMain,
          headText: 'pr:\n  merge: user\n  merge_method: merge\n  delete_branch: 1\n  settle: 2m\n  reviewers:\n    rev:\n      role: advisory\n      timeout: 60\n',
        );
        final r = await run();
        expect(r.code, 0);
        final drift = (r.json['drift']! as List).cast<Map<String, Object?>>();
        expect(
          [for (final d in drift) d['key']],
          [
            'pr.merge',
            'pr.merge_method',
            'pr.delete_branch',
            'pr.reviewers',
            'pr.settle',
          ],
        );
        expect(drift[0], {'key': 'pr.merge', 'main': 'agent', 'head': 'user'});
        expect(drift[2], {'key': 'pr.delete_branch', 'main': true, 'head': 1});
        expect(drift[4], {'key': 'pr.settle', 'main': 300, 'head': 120});
        // the decision comes from main alone
        expect(r.json['merge'], 'agent');
        expect(r.json['merge_method'], 'squash');
      },
    );

    test('a different reviewer rule is drift, an equal one is not', () async {
      serve(
        main: reviewersMain,
        headText: 'pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    rev:\n      role: required\n      timeout: 60\n      report:\n        sha_pattern: "([0-9a-f]+)"\n',
      );
      final r = await run();
      expect(
        [for (final d in r.json['drift']! as List) (d as Map)['key']],
        ['pr.reviewers'],
      );
    });

    test('invalid: reviewers that are not a mapping, per side', () async {
      serve(
        main: 'pr:\n  reviewers: nobody\n',
        headText: 'pr:\n  reviewers: [a, b]\n',
      );
      final r = await run();
      expect(r.code, 0, reason: f.stdout);
      expect(r.json['invalid'], [
        {'side': 'main', 'key': 'pr.reviewers', 'value': 'nobody'},
        {'side': 'head', 'key': 'pr.reviewers', 'value': '[a, b]'},
      ]);
      expect((r.json['main']! as Map)['pr.reviewers'], <String, Object?>{});
      expect(r.json['merge_ready'], {'code': false});
    });

    test('the head can be invalid where main would stop', () async {
      final many = [
        for (var i = 0; i < 21; i++) '    r$i:\n      role: required\n',
      ].join();
      serve(main: reviewersMain, headText: 'pr:\n  reviewers:\n$many');
      final r = await run();
      expect(r.code, 0, reason: f.stdout);
      final invalid = r.json['invalid']! as List;
      expect(invalid, hasLength(1));
      expect(invalid[0], {
        'side': 'head',
        'key': 'pr.reviewers',
        'value': 'too_many_reviewers',
      });
    });

    test(
      'a reviewer report that is not a string map: invalid on head',
      () async {
        serve(
          main: reviewersMain,
          headText: 'pr:\n  reviewers:\n    rev:\n      role: required\n      report: nope\n',
        );
        final r = await run();
        expect(r.code, 0, reason: f.stdout);
        expect(r.json['invalid'], [
          {
            'side': 'head',
            'key': 'pr.reviewers.rev.report',
            'value': 'must be a mapping of keys to strings',
          },
        ]);
      },
    );

    test('oversized head timeout is invalid with default values', () async {
      serve(
        main: reviewersMain,
        headText: 'pr:\n  reviewers:\n    rev:\n      role: required\n      timeout: 99999999999999999999\n',
      );
      final r = await run();
      expect(r.code, 0, reason: f.stdout);
      final invalid = r.json['invalid']! as List;
      expect(invalid, hasLength(1));
      expect((invalid[0] as Map)['side'], 'head');
      expect((invalid[0] as Map)['key'], 'pr.reviewers.rev.timeout');
      expect((invalid[0] as Map)['value'], contains('64'));
      final head = (r.json['head']! as Map)['pr.reviewers'] as Map;
      expect((head['rev'] as Map)['timeout'], 1200);
    });

    test('a raw merge_method beyond 64 bits is shown as written', () async {
      serve(main: 'pr:\n  merge_method: 99999999999999999999\n', headText: '');
      final r = await run();
      expect(r.code, 0, reason: f.stdout);
      expect(
        (r.json['main']! as Map)['pr.merge_method'],
        '99999999999999999999',
      );
      expect((r.json['drift']! as List).single, {
        'key': 'pr.merge_method',
        'main': '99999999999999999999',
        'head': 'merge',
      });
    });

    test(
      'merge_note names a pr.merge that is neither user nor agent',
      () async {
        serve(main: 'pr:\n  merge: maybe\n', headText: '');
        final r = await run();
        expect(r.json['merge'], 'user');
        expect(
          r.json['merge_note'],
          'pr.merge: maybe is not user or agent; treated as user',
        );
        expect(r.json.keys.last, 'merge_note');
      },
    );

    test('the store set inherits pr.reviewers unless it names its own', () async {
      const text =
          'pr:\n  reviewers:\n    rev:\n      role: required\n      timeout: 60\n';
      const own =
          'planning_store:\n  reviewers:\n    other:\n      role: advisory\n';
      serve(main: '$text$own', headText: text);
      final s1 = snapshotFile('c.json', snap());
      final s2 = snapshotFile('s.json', snap());
      final r = await policy([
        '--repo',
        'o/n',
        '--head',
        head,
        '--store',
        '--snapshot',
        'code=${s1.path}',
        '--snapshot',
        'store=${s2.path}',
        '--reviewed-head',
        'store=$head',
      ]);
      expect(r.code, 0, reason: f.stdout);
      final main = r.json['main']! as Map;
      expect(main.keys.last, 'planning_store.reviewers');
      expect((main['planning_store.reviewers']! as Map).keys, ['other']);
      expect((r.json['head']! as Map)['planning_store.reviewers'], isNull);
      expect(r.json['merge_ready'], {'code': true, 'store': false});
      expect(r.json['merge_reason'], {
        'code': null,
        'store': 'no_required_reviewer',
      });
      final drift = (r.json['drift']! as List).cast<Map<String, Object?>>();
      expect([for (final d in drift) d['key']], ['planning_store.reviewers']);
      final rc = r.json['reviewer_config']! as Map;
      expect((rc['main']! as Map).keys, ['code', 'store']);
      expect((rc['head']! as Map).keys, ['code', 'store']);
      // the head's store set is its pr.reviewers, so the two head files are one file
      expect((rc['head']! as Map)['code'], (rc['head']! as Map)['store']);
      expect(
        (rc['main']! as Map)['code'],
        isNot((rc['main']! as Map)['store']),
      );
    });
  });

  group('stops on main', () {
    test('a bad pr.settle on main is exit 2 bad_setting', () async {
      serve(main: 'pr:\n  settle: 5s\n', headText: '');
      final r = await run();
      expect(r.code, 2);
      expect(r.json['ok'], false);
      expect(r.json['error'], 'bad_setting');
      expect(r.json['message'], startsWith('pr.settle: 5s must be'));
    });

    test('an oversized timeout on main is exit 2 bad_setting', () async {
      serve(
        main: 'pr:\n  reviewers:\n    rev:\n      role: required\n      timeout: 99999999999999999999\n',
        headText: '',
      );
      final r = await run();
      expect(r.code, 2);
      expect(r.json['error'], 'bad_setting');
      expect(r.json['message'], startsWith('pr.reviewers.rev.timeout: '));
    });

    test('a bad head pr.settle only counts as the default', () async {
      serve(main: '', headText: 'pr:\n  settle: 5s\n');
      final r = await run();
      expect(r.code, 0);
      expect((r.json['head']! as Map)['pr.settle'], 300);
    });

    test(
      'more than 20 reviewers on main is exit 2 too_many_reviewers',
      () async {
        final many = [
          for (var i = 0; i < 21; i++) '    r$i:\n      role: required\n',
        ].join();
        serve(main: 'pr:\n  reviewers:\n$many', headText: '');
        final r = await run();
        expect(r.code, 2);
        expect(r.json['error'], 'too_many_reviewers');
        expect(r.json['message'], startsWith('pr.reviewers: 21 reviewers'));
      },
    );

    test('a bad report on main is exit 2 bad_setting', () async {
      serve(
        main: 'pr:\n  reviewers:\n    rev:\n      role: required\n      report:\n        sha_pattern: 5\n',
        headText: '',
      );
      final r = await run();
      expect(r.code, 2);
      expect(r.json['error'], 'bad_setting');
      expect(r.json['message'], startsWith('pr.reviewers.rev.report: '));
    });

    test('a bad merge_method with merge: agent on main is exit 2', () async {
      serve(main: 'pr:\n  merge: agent\n  merge_method: fast\n', headText: '');
      var r = await run();
      expect(r.code, 2);
      expect(r.json['error'], 'bad_setting');
      expect(r.json['message'], startsWith('pr.merge_method: fast'));
      f.out.clear();
      serve(main: 'pr:\n  merge: agent\n  delete_branch: sure\n', headText: '');
      r = await run();
      expect(r.code, 2);
      expect(r.json['message'], startsWith('pr.delete_branch: sure'));
    });

    test('without merge: agent a bad merge_method is only drift', () async {
      serve(main: 'pr:\n  merge_method: fast\n', headText: '');
      final r = await run();
      expect(r.code, 0);
      expect(r.json['merge_method'], 'merge');
      expect((r.json['main']! as Map)['pr.merge_method'], 'fast');
      expect((r.json['drift']! as List).single, {
        'key': 'pr.merge_method',
        'main': 'fast',
        'head': 'merge',
      });
    });
  });

  group('reported and reviewer_config', () {
    test(
      'ok when the snapshot is of the head, with the rules and the reviewer',
      () async {
        serve(main: reviewersMain, headText: reviewersMain);
        final r = await run();
        expect(r.json['reported'], {
          'main': {
            'code': {
              'ok': true,
              'missing': <String>[],
              'head_mismatch': false,
              'rules_mismatch': false,
              'snapshot_head': head,
              'reviewed_head': head,
            },
          },
          'head': {
            'code': {
              'ok': true,
              'missing': <String>[],
              'head_mismatch': false,
              'rules_mismatch': false,
              'snapshot_head': head,
              'reviewed_head': head,
            },
          },
        });
        final path =
            ((r.json['reviewer_config']! as Map)['main']! as Map)['code']!
                as String;
        expect(
          utf8.decode(File(path).readAsBytesSync()),
          '{"format":2,"reviewers":[{"login":"rev","report":{},"role":"required","timeout":60}]}',
        );
        expect(path, endsWith('/reviewers/$revDigest.json'));
        expect(
          ((r.json['reviewer_config']! as Map)['head']! as Map)['code'],
          path,
        );
      },
    );

    test('missing: a required reviewer that has not reported', () async {
      serve(main: reviewersMain, headText: reviewersMain);
      final r = await run(snapshot: snap(state: 'waiting'));
      final c = ((r.json['reported']! as Map)['main']! as Map)['code']! as Map;
      expect(c['ok'], false);
      expect(c['missing'], ['rev']);
    });

    test('a [bot] suffix and case do not matter in the snapshot', () async {
      serve(main: reviewersMain, headText: reviewersMain);
      final r = await run(snapshot: snap(login: 'REV[bot]'));
      final c = ((r.json['reported']! as Map)['main']! as Map)['code']! as Map;
      expect(c['ok'], true);
    });

    test('head_mismatch compares by prefix of 7 to 40 hex digits', () async {
      serve(main: reviewersMain, headText: reviewersMain);
      var r = await run(snapshot: snap(oid: head.substring(0, 12)));
      var c = ((r.json['reported']! as Map)['main']! as Map)['code']! as Map;
      expect((c['ok'], c['head_mismatch']), (true, false));
      expect(c['snapshot_head'], head.substring(0, 12));
      f.out.clear();
      r = await run(snapshot: snap(oid: 'f' * 40));
      c = ((r.json['reported']! as Map)['main']! as Map)['code']! as Map;
      expect((c['ok'], c['head_mismatch']), (false, true));
      f.out.clear();
      r = await run(snapshot: snap(oid: 'abc'));
      c = ((r.json['reported']! as Map)['main']! as Map)['code']! as Map;
      expect(c['head_mismatch'], true);
    });

    test('--reviewed-head code= is the carried-over head', () async {
      serve(main: reviewersMain, headText: reviewersMain);
      final other = 'b' * 40;
      final r = await run(
        snapshot: snap(oid: other),
        extra: ['--reviewed-head', 'code=$other'],
      );
      final c = ((r.json['reported']! as Map)['main']! as Map)['code']! as Map;
      expect(c['ok'], true);
      expect(c['reviewed_head'], other);
    });

    test('rules_mismatch: the digest is not that of the side\'s set', () async {
      serve(main: reviewersMain, headText: reviewersMain);
      final r = await run(snapshot: snap(config: 'f' * 64));
      final c = ((r.json['reported']! as Map)['main']! as Map)['code']! as Map;
      expect((c['ok'], c['rules_mismatch']), (false, true));
    });

    test('a format 1 digest is a rules_mismatch (D10)', () async {
      serve(main: reviewersMain, headText: reviewersMain);
      final format1 = sha256Hex(
        utf8.encode(
          '{"format":1,"reviewers":[{"login":"rev","report":{},"role":"required","timeout":60}]}',
        ),
      );
      final r = await run(snapshot: snap(config: format1));
      final c = ((r.json['reported']! as Map)['main']! as Map)['code']! as Map;
      expect(c['rules_mismatch'], true);
    });

    test(
      'each side is checked against its own set and written to its own file',
      () async {
        serve(
          main: reviewersMain,
          headText: 'pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    rev:\n      role: required\n      timeout: 30\n',
        );
        final r = await run();
        final reported = r.json['reported']! as Map;
        expect(((reported['main']! as Map)['code']! as Map)['ok'], true);
        expect(
          ((reported['head']! as Map)['code']! as Map)['rules_mismatch'],
          true,
        );
        final rc = r.json['reviewer_config']! as Map;
        expect(
          (rc['main']! as Map)['code'],
          isNot((rc['head']! as Map)['code']),
        );
      },
    );

    test('a set with no required reviewer is never ok', () async {
      serve(
        main: 'pr:\n  reviewers:\n    rev:\n      role: advisory\n',
        headText: '',
      );
      final r = await run();
      final c = ((r.json['reported']! as Map)['main']! as Map)['code']! as Map;
      expect(c['ok'], false);
      expect(c['missing'], <String>[]);
    });

    test('a snapshot that is not an object reports nothing', () async {
      serve(main: reviewersMain, headText: reviewersMain);
      final s = snapshotFile('code.json', [1, 2]);
      final r = await policy([
        '--repo',
        'o/n',
        '--head',
        head,
        '--snapshot',
        'code=${s.path}',
      ]);
      final c = ((r.json['reported']! as Map)['main']! as Map)['code']! as Map;
      expect(c['ok'], false);
      expect(c['snapshot_head'], isNull);
      expect(c['rules_mismatch'], true);
      expect(c['head_mismatch'], true);
    });
  });

  group('the arguments', () {
    Future<void> usage(List<String> argv, String message) async {
      f.out.clear();
      final r = await policy(argv);
      expect(r.code, 2, reason: '$argv');
      expect(r.json['error'], 'usage', reason: '$argv');
      expect(r.json['message'], message, reason: '$argv');
      expect(f.ghCalls, isEmpty, reason: 'no gh call for $argv');
    }

    test('usage stops come before the first gh call', () async {
      final s = snapshotFile('code.json', snap());
      final c = 'code=${s.path}';
      await usage([], 'missing --repo');
      await usage(['--repo', 'o/n'], 'missing --head');
      await usage([
        '--repo',
        'o/n',
        '--head',
        'xyz',
        '--snapshot',
        c,
      ], "--head must be a commit id of 7 to 40 hex digits, got 'xyz'");
      await usage([
        '--repo',
        'o/n',
        '--head',
        head,
        '--snapshot',
        'both=$c',
      ], '--snapshot is code=<file> or store=<file>');
      await usage([
        '--repo',
        'o/n',
        '--head',
        head,
        '--snapshot',
        'code=',
      ], '--snapshot is code=<file> or store=<file>');
      await usage([
        '--repo',
        'o/n',
        '--head',
        head,
      ], 'missing --snapshot code=<file>');
      await usage([
        '--repo',
        'o/n',
        '--head',
        head,
        '--snapshot',
        c,
        '--reviewed-head',
        'code=xyz',
      ], '--reviewed-head is code=<sha> or store=<sha> (7 to 40 hex digits)');
      await usage([
        '--repo',
        'o/n',
        '--head',
        head,
        '--snapshot',
        c,
        '--store',
      ], 'missing --snapshot store=<file>');
      await usage([
        '--repo', 'o/n', '--head', head, '--snapshot', c, //
        '--snapshot', 'store=${s.path}', '--store',
      ], '--store needs --reviewed-head store=<sha>');
      await usage([
        '--repo', 'o/n', '--head', head, '--snapshot', c, //
        '--reviewed-head', 'store=$head',
      ], '--snapshot store= and --reviewed-head store= need --store');
      await usage(['--repo', 'o/n', '--bogus'], 'unknown option --bogus');
    });

    test('an unreadable snapshot is exit 2 snapshot_unreadable', () async {
      final path = '${f.tempDir.path.replaceAll(r'\', '/')}/missing.json';
      var r = await policy([
        '--repo',
        'o/n',
        '--head',
        head,
        '--snapshot',
        'code=$path',
      ]);
      expect(r.code, 2);
      expect(r.json['error'], 'snapshot_unreadable');
      expect(r.json['message'], startsWith(path));
      f.out.clear();
      final bad = f.file('bad.json', '{not json');
      r = await policy([
        '--repo',
        'o/n',
        '--head',
        head,
        '--snapshot',
        'code=${bad.path}',
      ]);
      expect(r.code, 2);
      expect(r.json['error'], 'snapshot_unreadable');
      expect(f.ghCalls, isEmpty);
    });

    test('NaN in a snapshot is refused, naming the file', () async {
      serve(main: reviewersMain, headText: reviewersMain);
      final s = f.file(
        'nan.json',
        '{"head_oid": "$head", "reviewer_config": NaN, "reviewers": []}',
      );
      final r = await policy([
        '--repo',
        'o/n',
        '--head',
        head,
        '--snapshot',
        'code=${s.path}',
      ]);
      expect(r.code, 2, reason: f.stdout);
      expect(r.json['error'], 'snapshot_unreadable');
      expect(r.json['message'], startsWith('${s.path}: '));
    });
  });
}
