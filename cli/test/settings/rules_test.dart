import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:specwright_cli/src/settings/rules.dart';
import 'package:specwright_cli/src/settings/yaml.dart';
import 'package:specwright_cli/src/vcs/document.dart';
import 'package:test/test.dart';

// The expected values come from CPython 3.14 running the frozen `duration`, `settle_of`, `reviewers_of`, `merge_mode`,
// `merge_options`, `repo_ctx`, `contexts`, `cmd_vcs` and `cmd_tier` of skills/specwright-pr/scripts/pr-pair.sh.

YamlMap _pr(String yaml) => parseYaml(yaml)['pr']! as YamlMap;

Object? _json(Object? v) => jsonDecode(documentText(v));

String _problemsJson(List<SettingProblem> ps) =>
    documentText([for (final p in ps) p.toJson()]);

void main() {
  group('duration', () {
    test('reads <int>[s|m|h] after strip, with spaces between', () {
      expect(duration('90', 7), 90);
      expect(duration('90s', 7), 90);
      expect(duration('5m', 7), 300);
      expect(duration('2h', 7), 7200);
      expect(duration(' 5 m ', 7), 300);
      expect(duration('5 m', 7), 300);
      expect(duration('5\u{a0}m', 7), 300, reason: r'Python \s takes U+00A0');
    });

    test('reads Unicode decimal digits', () {
      expect(duration('\u{665}m', 7), 300);
      expect(duration('\u{661}\u{662}', 7), 12);
    });

    test('uses the default for unset, empty and unreadable values', () {
      for (final v in [
        null,
        '',
        '5x',
        'm',
        '1.5m',
        '-5',
        [1],
        '5 mm',
      ]) {
        expect(duration(v, 7), 7, reason: '$v');
      }
    });

    test('returns an integer as it is, a boolean too (bool is an int)', () {
      expect(duration(5, 7), 5);
      expect(duration(0, 7), 0);
      expect(duration(true, 7), true);
      expect(duration(false, 7), false);
    });

    test('keeps a product past 64 bits as a BigInt', () {
      expect(
        duration('99999999999999999999h', 7),
        BigInt.parse('359999999999999999996400'),
      );
    });
  });

  group('settleOf', () {
    test('is 300 when unset or empty, with no problem', () {
      for (final yaml in ['pr:\n  x: 1\n', 'pr:\n  settle: ""\n']) {
        final r = settleOf(_pr(yaml));
        expect(r.seconds, 300);
        expect(r.problem, isNull);
      }
    });

    test('reads 1m to 1h written as <number>s, m or h', () {
      for (final (v, s) in [
        ('1m', 60),
        ('10m', 600),
        ('90s', 90),
        ('60s', 60),
        ('1h', 3600),
        ('3600s', 3600),
        ('45m', 2700),
      ]) {
        final r = settleOf(_pr('pr:\n  settle: $v\n'));
        expect(r.seconds, s, reason: v);
        expect(r.problem, isNull, reason: v);
      }
    });

    test('anything else is 300 and a pr.settle problem naming the text', () {
      for (final (yaml, written) in [
        ('59s', '59s'),
        ('3601s', '3601s'),
        ('2h', '2h'),
        ('yes', 'yes'),
        ('5', '5'),
        ('0', '0'),
        ("'1.5m'", "'1.5m'"),
        ("' 5m'", "' 5m'"),
        ('\u{665}m', '\u{665}m'),
        ('99999999999999999999h', '99999999999999999999h'),
      ]) {
        final r = settleOf(_pr('pr:\n  settle: $yaml\n'));
        expect(r.seconds, 300, reason: yaml);
        expect(r.problem, isNotNull, reason: yaml);
        expect(r.problem!.error, 'bad_setting');
        expect(r.problem!.key, 'pr.settle');
        expect(r.problem!.why, startsWith('$written must be a duration'));
        expect(r.problem!.text, startsWith('pr.settle: $written must be'));
        expect(r.problem!.toJson(), {
          'error': 'bad_setting',
          'key': 'pr.settle',
          'why': r.problem!.why,
        });
      }
    });

    test('a flow-map pr has no text: a boolean reads as true', () {
      final pr =
          parseYaml('pr: {settle: yes}\n')['pr']! as Map<String, Object?>;
      expect(settleOf(pr).problem!.why, startsWith('true must be'));
    });
  });

  group('reviewersOf', () {
    test('reads role, timeout, request and report with their defaults', () {
      final out = reviewersOf({
        'kody-ai': {
          'role': 'advisory',
          'timeout': '15m',
          'request': '@kody review',
        },
        'plain': <String, Object?>{},
        'scalar': 'x',
      });
      expect(_json({for (final e in out.entries) e.key: e.value.toJson()}), {
        'kody-ai': {
          'role': 'advisory',
          'timeout': 900,
          'request': '@kody review',
          'report': <String, Object?>{},
        },
        'plain': {
          'role': 'required',
          'timeout': 1200,
          'request': '',
          'report': <String, Object?>{},
        },
        'scalar': {
          'role': 'required',
          'timeout': 1200,
          'request': '',
          'report': <String, Object?>{},
        },
      });
      expect(
        documentText(out['kody-ai']!.toJson()),
        '{"role": "advisory", "timeout": 900, "request": "@kody review", "report": {}}',
        reason: 'the field order is the script\'s',
      );
    });

    test('strips [bot] at the end, and before a final newline', () {
      final out = reviewersOf({
        'check-bot[bot]': <String, Object?>{},
        'a[bot]\n': <String, Object?>{},
        'b[bot]x': <String, Object?>{},
        '[bot]': <String, Object?>{},
        'c[bot][bot]': <String, Object?>{},
        'd[bot]\n\n': <String, Object?>{},
      });
      expect(out.keys.toList(), [
        'check-bot',
        'a\n',
        'b[bot]x',
        '',
        'c[bot]',
        'd[bot]\n\n',
      ]);
    });

    test('two logins that strip to one name leave the later entry', () {
      final out = reviewersOf({
        'dup[bot]': {'role': 'x'},
        'other': <String, Object?>{},
        'dup': {'role': 'y'},
      });
      expect(out.keys.toList(), ['dup', 'other']);
      expect(out['dup']!.role, 'y');
    });

    test('writes non-text role, timeout and request as Python str() does', () {
      final out = reviewersOf({
        'c': {'role': true, 'timeout': true, 'request': 5},
        'd': {
          'role': '',
          'timeout': '',
          'request': ['a', "it's"],
        },
      });
      expect(out['c']!.role, 'True');
      expect(out['c']!.timeout, true);
      expect(out['c']!.request, '5');
      expect(out['d']!.role, 'required');
      expect(out['d']!.timeout, 1200);
      expect(out['d']!.request, '[\'a\', "it\'s"]');
    });

    test('a report of strings is kept, unknown keys too', () {
      final out = reviewersOf({
        'r': {
          'report': {'check': 'Bot Code Review', 'zzz': 'x'},
        },
        'empty': {'report': <String, Object?>{}},
        'blank': {'report': ''},
      });
      expect(out['r']!.report, {'check': 'Bot Code Review', 'zzz': 'x'});
      expect(out['empty']!.report, isEmpty);
      expect(out['blank']!.report, isEmpty);
    });

    test(
      'a report that is not a mapping of strings is a problem, read as none',
      () {
        final problems = <SettingProblem>[];
        final out = reviewersOf({
          'check-bot[bot]': {
            'report': {'check': 'Bot Code Review', 'n': 1},
          },
          'e': {'report': 'x'},
          'f': {'report': <String, Object?>{}},
          'g': {'report': <Object?>[]},
          'i': {
            'report': {'a': 's', 'b': 2, 'c': 't'},
          },
        }, problems: problems);
        expect(out['check-bot']!.report, isEmpty);
        expect(out['e']!.report, isEmpty);
        expect(out['g']!.report, isEmpty);
        expect(out['i']!.report, isEmpty);
        expect(
          [for (final p in problems) p.key],
          [
            'pr.reviewers.check-bot.report',
            'pr.reviewers.e.report',
            'pr.reviewers.g.report',
            'pr.reviewers.i.report',
          ],
        );
        expect(problems.every((p) => p.error == 'bad_setting'), true);
        expect(problems[0].why, startsWith('n must be a string'));
        expect(problems[1].why, startsWith('must be a mapping'));
        expect(problems[3].why, startsWith('b must be a string'));
      },
    );

    test('the where argument names a planning_store set', () {
      final problems = <SettingProblem>[];
      reviewersOf(
        {
          'x': {'report': 'bad'},
        },
        problems: problems,
        where: 'planning_store.reviewers',
      );
      expect(problems.single.key, 'planning_store.reviewers.x.report');
    });

    test('no problems list: nothing is collected and nothing fails', () {
      expect(
        reviewersOf({
          'x': {'report': 'bad'},
        }),
        hasLength(1),
      );
      expect(reviewersOf(null), isEmpty);
      expect(reviewersOf(''), isEmpty);
    });

    test('20 reviewers are fine; 21 is too_many_reviewers and the set is read whole', () {
      final twenty = {for (var i = 0; i < 20; i++) 'r$i': <String, Object?>{}};
      var problems = <SettingProblem>[];
      expect(reviewersOf(twenty, problems: problems), hasLength(20));
      expect(problems, isEmpty);

      final twentyOne = {
        for (var i = 0; i < 21; i++) 'r$i': <String, Object?>{},
      };
      problems = <SettingProblem>[];
      final out = reviewersOf(twentyOne, problems: problems);
      expect(out, hasLength(21), reason: 'the set is still read whole');
      expect(problems, hasLength(1));
      expect(problems.single.error, 'too_many_reviewers');
      expect(problems.single.key, 'pr.reviewers');
      expect(
        problems.single.why,
        contains('21 reviewers is too_many_reviewers'),
      );
      expect(problems.single.why, contains('at most 20'));
    });

    test('the cap counts the entries as written, before [bot] merges two', () {
      final raw = {
        for (var i = 0; i < 20; i++) 'r$i': <String, Object?>{},
        'r0[bot]': <String, Object?>{},
      };
      final problems = <SettingProblem>[];
      expect(reviewersOf(raw, problems: problems), hasLength(20));
      expect(problems.single.error, 'too_many_reviewers');
    });

    test('a set that is not a mapping is not counted', () {
      final problems = <SettingProblem>[];
      expect(reviewersOf(['a', 'b'], problems: problems), isEmpty);
      expect(problems, isEmpty);
    });
  });

  group('mergeMode', () {
    test('user, agent, unset and empty carry no note', () {
      for (final (yaml, mode) in [
        ('pr:\n  merge: agent\n', 'agent'),
        ('pr:\n  merge: user\n', 'user'),
        ("pr:\n  merge: ''\n", 'user'),
        ('pr:\n  x: 1\n', 'user'),
      ]) {
        final r = mergeMode(_pr(yaml));
        expect(r.mode, mode, reason: yaml);
        expect(r.note, isNull, reason: yaml);
      }
    });

    test('another value is user with a note naming it as written', () {
      for (final (v, written) in [
        ('Agent', 'Agent'),
        ('yes', 'yes'),
        ('5', '5'),
      ]) {
        final r = mergeMode(_pr('pr:\n  merge: $v\n'));
        expect(r.mode, 'user');
        expect(
          r.note,
          'pr.merge: $written is not user or agent; treated as user',
        );
      }
    });
  });

  group('mergeOptions', () {
    test('defaults to merge and delete_branch true', () {
      final r = mergeOptions(_pr('pr:\n  x: 1\n'));
      expect(r.method, 'merge');
      expect(r.deleteBranch, true);
    });

    test('reads the three methods and a boolean', () {
      var r = mergeOptions(
        _pr('pr:\n  merge_method: squash\n  delete_branch: no\n'),
      );
      expect((r.method, r.deleteBranch), ('squash', false));
      r = mergeOptions(
        _pr('pr:\n  merge_method: rebase\n  delete_branch: true\n'),
      );
      expect((r.method, r.deleteBranch), ('rebase', true));
      r = mergeOptions(_pr('pr:\n  merge_method: merge\n'));
      expect(r.method, 'merge');
    });

    test('a bad value stops with bad_setting, exit 2, naming the text', () {
      for (final (yaml, message) in [
        (
          'merge_method: Squash',
          'pr.merge_method: Squash must be merge, squash or rebase',
        ),
        (
          "merge_method: ''",
          "pr.merge_method: '' must be merge, squash or rebase",
        ),
        (
          'merge_method: yes',
          'pr.merge_method: yes must be merge, squash or rebase',
        ),
        (
          'delete_branch: maybe',
          'pr.delete_branch: maybe must be true or false',
        ),
        ('delete_branch: 1', 'pr.delete_branch: 1 must be true or false'),
        ("delete_branch: ''", "pr.delete_branch: '' must be true or false"),
      ]) {
        try {
          mergeOptions(_pr('pr:\n  $yaml\n'));
          fail('$yaml should stop');
        } on SettingsStop catch (e) {
          expect(e.error, 'bad_setting', reason: yaml);
          expect(e.code, 2, reason: yaml);
          expect(e.message, message, reason: yaml);
        }
      }
    });
  });

  group('contexts', () {
    for (final (name, yaml, code, store, check, want) in _contextCases) {
      test(name, () {
        final problems = <SettingProblem>[];
        String got;
        try {
          final c = contexts(
            parseYaml(yaml),
            code,
            store,
            detectMain: (d) => 'detected-${d.split('/').last}',
            checkMerge: check,
            problems: problems,
          );
          got = '${documentText(c.toJson())}\n${_problemsJson(problems)}';
        } on SettingsStop catch (e) {
          got = 'STOP ${e.error} ${e.code}\n${_problemsJson(problems)}';
        }
        expect(got, want);
      });
    }

    test(
      'both contexts: the store inherits pr.reviewers unless it has its own',
      () {
        final c = contexts(
          parseYaml(
            'pr:\n  reviewers:\n    codex: { role: required }\n'
            'planning_store:\n  login: s\n',
          ),
          '/c',
          '/s',
          detectMain: (_) => 'main',
        );
        expect(c.code.reviewers.keys, ['codex']);
        expect(c.store!.reviewers.keys, ['codex']);
        expect(c.store!.login, 's');
        expect(c.code.main, 'main');
      },
    );

    test('detectMain is asked only when no main is set', () {
      final asked = <String>[];
      contexts(
        parseYaml('main_branch: trunk\nplanning_store:\n  main_branch: dev\n'),
        '/c',
        '/s',
        detectMain: (d) {
          asked.add(d);
          return 'x';
        },
      );
      expect(asked, isEmpty);
    });
  });

  group('vcsChoices', () {
    test('defaults to git for both', () {
      final r = vcsChoices(parseYaml(''));
      expect((r.code, r.store), ('git', 'git'));
    });

    test('reads each backend', () {
      var r = vcsChoices(parseYaml('vcs: gitbutler\nfinish: pr\n'));
      expect((r.code, r.store), ('gitbutler', 'git'));
      r = vcsChoices(parseYaml('planning_store:\n  vcs: jj\n'));
      expect((r.code, r.store), ('git', 'jj'));
      r = vcsChoices(parseYaml('vcs: jj\n'));
      expect((r.code, r.store), ('jj', 'git'));
      r = vcsChoices(parseYaml('planning_store: x\nvcs: git\n'));
      expect((r.code, r.store), ('git', 'git'));
    });

    test('a refusal keeps the script\'s error code', () {
      for (final (yaml, error) in [
        ('vcs: gitbutler\n', 'unsupported_combination'),
        ('vcs: gitbutler\nfinish: local\n', 'unsupported_combination'),
        ('vcs: gitbutler\nfinish: yes\n', 'unsupported_combination'),
        ('vcs: svn\n', 'unknown_vcs'),
        ('vcs: yes\n', 'unknown_vcs'),
        ('planning_store:\n  vcs: gitbutler\n', 'unsupported_vcs'),
        ('planning_store:\n  vcs: svn\n', 'unknown_vcs'),
      ]) {
        try {
          vcsChoices(parseYaml(yaml));
          fail('${yaml.trim()} should stop');
        } on SettingsStop catch (e) {
          expect(e.error, error, reason: yaml);
          expect(e.code, 1);
        }
      }
    });

    test('names an unknown backend with Python repr', () {
      try {
        vcsChoices(parseYaml('vcs: svn\n'));
        fail('should stop');
      } on SettingsStop catch (e) {
        expect(
          e.message,
          "unknown code VCS 'svn'; accepted values: git, jj, gitbutler",
        );
      }
      try {
        vcsChoices(parseYaml('planning_store:\n  vcs: svn\n'));
        fail('should stop');
      } on SettingsStop catch (e) {
        expect(
          e.message,
          "unknown planning_store VCS 'svn'; accepted values: git, jj",
        );
      }
    });
  });

  group('tierChoice', () {
    test('reads cheap_tier.enabled', () {
      for (final (yaml, want) in [
        ('', {'ok': true, 'cheap_tier': false}),
        ('cheap_tier:\n  enabled: true\n', {'ok': true, 'cheap_tier': true}),
        ('cheap_tier:\n  enabled: false\n', {'ok': true, 'cheap_tier': false}),
        ('cheap_tier:\n  enabled: yes\n', {'ok': true, 'cheap_tier': true}),
        ('cheap_tier: {enabled: yes}\n', {'ok': true, 'cheap_tier': true}),
        ('cheap_tier:\n  other: 1\n', {'ok': true, 'cheap_tier': false}),
        ('cheap_tier:\n', {'ok': true, 'cheap_tier': false}),
      ]) {
        expect(tierChoice(parseYaml(yaml)), want, reason: yaml);
      }
    });

    test('anything else is false with a note', () {
      expect(tierChoice(parseYaml('cheap_tier:\n  enabled: maybe\n')), {
        'ok': true,
        'cheap_tier': false,
        'note':
            'cheap_tier.enabled: maybe is not true or false; treated as false',
      });
      for (final yaml in [
        'cheap_tier: x\n',
        'cheap_tier: []\n',
        'cheap_tier: true\n',
      ]) {
        expect(tierChoice(parseYaml(yaml)), {
          'ok': true,
          'cheap_tier': false,
          'note': 'cheap_tier must hold enabled: true|false; treated as false',
        }, reason: yaml);
      }
    });
  });

  group('settings text', () {
    late Directory tmp;
    setUp(() => tmp = Directory.systemTemp.createTempSync('claude-g3-rules-'));
    tearDown(() => tmp.deleteSync(recursive: true));

    String write(String dir, List<int> bytes) {
      final f = File('${tmp.path}/$dir/openspec/specwright.yaml')
        ..createSync(recursive: true)
        ..writeAsBytesSync(bytes);
      return f.parent.parent.path;
    }

    test(
      'reads a checkout whose directory name is not UTF-8',
      () {
        final raw = [...utf8.encode('${tmp.path}/co-'), 0xff];
        final dir = Uint8List.fromList([...raw, ...utf8.encode('/openspec')]);
        Directory.fromRawPath(dir).createSync(recursive: true);
        File.fromRawPath(
          Uint8List.fromList([...dir, ...utf8.encode('/specwright.yaml')]),
        ).writeAsStringSync('x: 1\n');
        expect(readSettingsText(['${tmp.path}/co-\uDCFF']), 'x: 1\n');
      },
      skip: Platform.isLinux
          ? false
          : 'a file name that is not UTF-8 needs Linux',
    );

    test('reads the first base that holds the file', () {
      final a = write('a', utf8.encode('x: 1\n'));
      final b = write('b', utf8.encode('x: 2\n'));
      expect(readSettingsText([a, b]), 'x: 1\n');
      expect(readSettingsText(['${tmp.path}/none', b]), 'x: 2\n');
      expect(readSettingsText(['${tmp.path}/none']), isNull);
    });

    test('decodes UTF-8 with U+FFFD for bad bytes and reads newlines as Python text mode', () {
      final a = write('a', [
        ...utf8.encode('a: x'),
        0xff,
        ...utf8.encode('y\r\nb: 1\rc: 2\n'),
      ]);
      expect(readSettingsText([a]), 'a: x\u{fffd}y\nb: 1\nc: 2\n');
    });

    test('loadSettings: no text is an empty map, else the lenient read', () {
      expect(loadSettings(null), isEmpty);
      expect(loadSettings('a: yes\n'), {'a': true});
    });
  });
}

// Generated from the frozen pr-pair.sh `contexts` (with `detect_main` answering `detected-<last path part>`).
final _contextCases = <(String, String, String, String?, bool, String)>[
  (
    'every setting',
    'github:\n  login: me\n  review_request:\n    body: "@codex review"\n    login: poster\n    after_fixes: yes\nmain_branch: trunk\nfinish: pr\nplanning_store:\n  login: storeme\n  validate: make check\n  reviewers:\n    store-bot: { role: required }\npr:\n  request_as: asker\n  validate: make test\n  reviewers:\n    kody-ai: { role: advisory }\n    codex: { role: required, request: "@codex review" }\n  max_fix_rounds: 3\n  after_limit: stop\n  react: yes\n  poll_interval: 2m\n  settle: 2m\n  merge: agent\n  merge_method: squash\n  delete_branch: no\n',
    '/w/code',
    '/w/store',
    true,
    '{"code": {"dir": "/w/code", "review_request": {"body": "@codex review", "login": "poster", "after_fixes": true}, "request_as": "asker", "login": "me", "main": "trunk", "validate": "make test", "reviewers": {"kody-ai": {"role": "advisory", "timeout": 1200, "request": "", "report": {}}, "codex": {"role": "required", "timeout": 1200, "request": "@codex review", "report": {}}}, "requests_disabled": false, "merge_ready": true, "merge_reason": null}, "store": {"dir": "/w/store", "review_request": {"body": "@codex review", "login": "poster", "after_fixes": true}, "request_as": "asker", "login": "storeme", "main": "detected-store", "validate": "make check", "reviewers": {"store-bot": {"role": "required", "timeout": 1200, "request": "", "report": {}}}, "requests_disabled": false, "merge_ready": true, "merge_reason": null}, "finish": "pr", "max_fix_rounds": 3, "after_limit": "stop", "react": true, "poll_interval": 120, "settle": 120, "merge": "agent", "merge_method": "squash", "delete_branch": false}\n[]',
  ),
  (
    'no store and no merge check',
    'github:\n  login: me\n  review_request:\n    body: "@codex review"\n    login: poster\n    after_fixes: yes\nmain_branch: trunk\nfinish: pr\nplanning_store:\n  login: storeme\n  validate: make check\n  reviewers:\n    store-bot: { role: required }\npr:\n  request_as: asker\n  validate: make test\n  reviewers:\n    kody-ai: { role: advisory }\n    codex: { role: required, request: "@codex review" }\n  max_fix_rounds: 3\n  after_limit: stop\n  react: yes\n  poll_interval: 2m\n  settle: 2m\n  merge: agent\n  merge_method: squash\n  delete_branch: no\n',
    '/w/code',
    null,
    false,
    '{"code": {"dir": "/w/code", "review_request": {"body": "@codex review", "login": "poster", "after_fixes": true}, "request_as": "asker", "login": "me", "main": "trunk", "validate": "make test", "reviewers": {"kody-ai": {"role": "advisory", "timeout": 1200, "request": "", "report": {}}, "codex": {"role": "required", "timeout": 1200, "request": "@codex review", "report": {}}}, "requests_disabled": false, "merge_ready": true, "merge_reason": null}, "store": null, "finish": "pr", "max_fix_rounds": 3, "after_limit": "stop", "react": true, "poll_interval": 120, "settle": 120, "merge": "agent", "merge_method": "merge", "delete_branch": true}\n[]',
  ),
  (
    'empty settings',
    '',
    '/w/code',
    '/w/store',
    true,
    '{"code": {"dir": "/w/code", "review_request": {"body": "", "login": "", "after_fixes": false}, "request_as": "", "login": "", "main": "detected-code", "validate": "", "reviewers": {}, "requests_disabled": false, "merge_ready": false, "merge_reason": "no_required_reviewer"}, "store": {"dir": "/w/store", "review_request": {"body": "", "login": "", "after_fixes": false}, "request_as": "", "login": "", "main": "detected-store", "validate": "", "reviewers": {}, "requests_disabled": false, "merge_ready": false, "merge_reason": "no_required_reviewer"}, "finish": "", "max_fix_rounds": 2, "after_limit": "ask", "react": false, "poll_interval": 300, "settle": 300, "merge": "user", "merge_method": "merge", "delete_branch": true}\n[]',
  ),
  (
    'agent merge with default options',
    'pr:\n  merge: agent\n',
    '/w/code',
    null,
    true,
    '{"code": {"dir": "/w/code", "review_request": {"body": "", "login": "", "after_fixes": false}, "request_as": "", "login": "", "main": "detected-code", "validate": "", "reviewers": {}, "requests_disabled": false, "merge_ready": false, "merge_reason": "no_required_reviewer"}, "store": null, "finish": "", "max_fix_rounds": 2, "after_limit": "ask", "react": false, "poll_interval": 300, "settle": 300, "merge": "agent", "merge_method": "merge", "delete_branch": true}\n[]',
  ),
  (
    'a bad merge_method stops the agent merge',
    'pr:\n  merge: agent\n  merge_method: Squash\n',
    '/w/code',
    null,
    true,
    'STOP bad_setting 2\n[]',
  ),
  (
    'a bad merge_method is not read when unchecked',
    'pr:\n  merge: agent\n  merge_method: Squash\n',
    '/w/code',
    null,
    false,
    '{"code": {"dir": "/w/code", "review_request": {"body": "", "login": "", "after_fixes": false}, "request_as": "", "login": "", "main": "detected-code", "validate": "", "reviewers": {}, "requests_disabled": false, "merge_ready": false, "merge_reason": "no_required_reviewer"}, "store": null, "finish": "", "max_fix_rounds": 2, "after_limit": "ask", "react": false, "poll_interval": 300, "settle": 300, "merge": "agent", "merge_method": "merge", "delete_branch": true}\n[]',
  ),
  (
    'a bad merge_method is not read in user mode',
    'pr:\n  merge_method: Squash\n',
    '/w/code',
    null,
    true,
    '{"code": {"dir": "/w/code", "review_request": {"body": "", "login": "", "after_fixes": false}, "request_as": "", "login": "", "main": "detected-code", "validate": "", "reviewers": {}, "requests_disabled": false, "merge_ready": false, "merge_reason": "no_required_reviewer"}, "store": null, "finish": "", "max_fix_rounds": 2, "after_limit": "ask", "react": false, "poll_interval": 300, "settle": 300, "merge": "user", "merge_method": "merge", "delete_branch": true}\n[]',
  ),
  (
    'a merge note, a boolean round count and a bad settle',
    'pr:\n  merge: Agent\n  max_fix_rounds: yes\n  settle: 30s\n',
    '/w/code',
    null,
    true,
    '{"code": {"dir": "/w/code", "review_request": {"body": "", "login": "", "after_fixes": false}, "request_as": "", "login": "", "main": "detected-code", "validate": "", "reviewers": {}, "requests_disabled": false, "merge_ready": false, "merge_reason": "no_required_reviewer"}, "store": null, "finish": "", "max_fix_rounds": 1, "after_limit": "ask", "react": false, "poll_interval": 300, "settle": 300, "merge": "user", "merge_note": "pr.merge: Agent is not user or agent; treated as user", "merge_method": "merge", "delete_branch": true}\n[{"error": "bad_setting", "key": "pr.settle", "why": "30s must be a duration of 1m to 1h written as <number>s, <number>m or <number>h"}]',
  ),
  (
    'the store\'s own empty reviewer set disables requests',
    'planning_store:\n  reviewers: {}\npr:\n  reviewers:\n    a: {}\n',
    '/w/code',
    '/w/store',
    true,
    '{"code": {"dir": "/w/code", "review_request": {"body": "", "login": "", "after_fixes": false}, "request_as": "", "login": "", "main": "detected-code", "validate": "", "reviewers": {"a": {"role": "required", "timeout": 1200, "request": "", "report": {}}}, "requests_disabled": false, "merge_ready": true, "merge_reason": null}, "store": {"dir": "/w/store", "review_request": {"body": "", "login": "", "after_fixes": false}, "request_as": "", "login": "", "main": "detected-store", "validate": "", "reviewers": {}, "requests_disabled": true, "merge_ready": false, "merge_reason": "no_required_reviewer"}, "finish": "", "max_fix_rounds": 2, "after_limit": "ask", "react": false, "poll_interval": 300, "settle": 300, "merge": "user", "merge_method": "merge", "delete_branch": true}\n[]',
  ),
  (
    'quoted values and a bad poll_interval',
    'pr:\n  max_fix_rounds: \'3\'\n  react: \'false\'\n  after_limit: \'\'\n  poll_interval: 1x\n',
    '/w/code',
    null,
    true,
    '{"code": {"dir": "/w/code", "review_request": {"body": "", "login": "", "after_fixes": false}, "request_as": "", "login": "", "main": "detected-code", "validate": "", "reviewers": {}, "requests_disabled": false, "merge_ready": false, "merge_reason": "no_required_reviewer"}, "store": null, "finish": "", "max_fix_rounds": 2, "after_limit": "ask", "react": true, "poll_interval": 300, "settle": 300, "merge": "user", "merge_method": "merge", "delete_branch": true}\n[]',
  ),
  (
    'no required reviewer',
    'pr:\n  reviewers:\n    a: { role: advisory }\n',
    '/w/code',
    null,
    true,
    '{"code": {"dir": "/w/code", "review_request": {"body": "", "login": "", "after_fixes": false}, "request_as": "", "login": "", "main": "detected-code", "validate": "", "reviewers": {"a": {"role": "advisory", "timeout": 1200, "request": "", "report": {}}}, "requests_disabled": false, "merge_ready": false, "merge_reason": "no_required_reviewer"}, "store": null, "finish": "", "max_fix_rounds": 2, "after_limit": "ask", "react": false, "poll_interval": 300, "settle": 300, "merge": "user", "merge_method": "merge", "delete_branch": true}\n[]',
  ),
  (
    'a round count past 64 bits',
    'pr:\n  max_fix_rounds: 99999999999999999999\n',
    '/w/code',
    null,
    true,
    '{"code": {"dir": "/w/code", "review_request": {"body": "", "login": "", "after_fixes": false}, "request_as": "", "login": "", "main": "detected-code", "validate": "", "reviewers": {}, "requests_disabled": false, "merge_ready": false, "merge_reason": "no_required_reviewer"}, "store": null, "finish": "", "max_fix_rounds": 99999999999999999999, "after_limit": "ask", "react": false, "poll_interval": 300, "settle": 300, "merge": "user", "merge_method": "merge", "delete_branch": true}\n[]',
  ),
];
