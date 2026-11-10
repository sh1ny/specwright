import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:specwright_cli/src/pr/reviewers.dart';
import 'package:specwright_cli/src/pr/text.dart';
import 'package:test/test.dart';

/// Runs `sw pr reviewers` in-process on [args]: (exit code, stdout, stderr).
({int code, String out, String err}) run(List<String> args) {
  final out = <int>[];
  final err = <int>[];
  final code = runReviewers(args, writeOut: out.addAll, writeErr: err.addAll);
  return (code: code, out: utf8.decode(out), err: utf8.decode(err));
}

void main() {
  late Directory dir;

  setUp(() => dir = Directory.systemTemp.createTempSync('reviewers-test-'));
  tearDown(() => dir.deleteSync(recursive: true));

  String write(String name, Object doc) {
    final f = File('${dir.path}/$name')..writeAsStringSync(jsonEncode(doc));
    return f.path;
  }

  Map<String, Object?> config(Map<String, String> report) => {
    'format': 2,
    'reviewers': [
      {'login': 'rev-bot', 'role': 'required', 'timeout': 60, 'report': report},
    ],
  };

  group('a name that is not UTF-8', () {
    test(
      'a config whose name is not UTF-8 is read through its bytes',
      () {
        final name = [
          ...utf8.encode('${dir.path}/reviewers-'),
          0xff,
          ...utf8.encode('.json'),
        ];
        File.fromRawPath(
          Uint8List.fromList(name),
        ).writeAsStringSync(jsonEncode(config({'sha_pattern': '([0-9a-f]+)'})));
        final r = run(['--check-config', '${dir.path}/reviewers-\uDCFF.json']);
        expect(r.code, 0, reason: r.err);
        expect(jsonDecode(r.out)['logins'], ['rev-bot']);
      },
      skip: Platform.isLinux
          ? false
          : 'a file name that is not UTF-8 needs Linux',
    );
  });

  group('the group count', () {
    int groups(String p) => groupCount(RegExp(p, unicode: true));

    test('counts capturing groups, not the others', () {
      expect(groups('abc'), 0);
      expect(groups('(a)(b)'), 2);
      expect(groups('(?:a)(b)'), 1);
      expect(groups(r'(?<sha>[0-9a-f]+)'), 1);
      expect(groups('(a(b))|c'), 2);
      expect(groups('(?=(a))(?!b)'), 1);
    });

    test('a top-level alternation does not escape the probe', () {
      expect(groups('a|(b)'), 1);
      expect(groups('a|b'), 0);
    });
  });

  group('the JavaScript dialect', () {
    for (final pattern in [
      '(?P<sha>[0-9a-f]+)',
      r'\A([0-9a-f]+)',
      r'([0-9a-f]+)\Z',
      '(?i)([0-9a-f]+)',
      '([0-9a-f]{,3})',
      '([0-9a-f]+',
    ]) {
      test('${jsonEncode(pattern)} is refused, naming reviewer and key', () {
        for (final key in ['sha_pattern', 'ignore']) {
          final r = run([
            '--check-config',
            write('c.json', config({key: pattern})),
          ]);
          expect(r.code, 2, reason: key);
          expect(r.out, '');
          expect(r.err, startsWith('reviewers.py: '));
          expect(r.err, contains('rev-bot'));
          expect(r.err, contains('report.$key'));
          expect(r.err, contains('does not compile'));
        }
      });
    }

    test('a sha_pattern without a group is refused', () {
      final r = run([
        '--check-config',
        write('c.json', config({'sha_pattern': 'abc'})),
      ]);
      expect(r.code, 2);
      expect(r.err, contains('report.sha_pattern'));
      expect(r.err, contains('capture group'));
    });

    test('the repository pattern compiles', () {
      final r = run([
        '--check-config',
        write(
          'c.json',
          config({'sha_pattern': r'Reviewed commit:\*\* `([0-9a-f]{7,40})`'}),
        ),
      ]);
      expect(r.code, 0, reason: r.err);
      expect(jsonDecode(r.out)['logins'], ['rev-bot']);
    });
  });

  group('JSON input that is not plain JSON', () {
    const oid = 'a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2';

    test('NaN and Infinity in material stop naming the file', () {
      for (final number in ['NaN', 'Infinity', '-Infinity']) {
        // one in a field the evaluator copies through, one in the clock it reads
        for (final body in [
          '{"head_oid":"$oid","cfg":{"now":1700000000},"extra":$number}',
          '{"head_oid":"$oid","cfg":{"now":$number}}',
        ]) {
          final f = File('${dir.path}/m.json')..writeAsStringSync(body);
          final r = run(['--material', f.path, '--head', oid]);
          expect(r.code, 1, reason: body);
          expect(r.out, '', reason: body);
          expect(r.err, startsWith('reviewers.py: ${f.path}: '), reason: body);
          expect(r.err.trim().split('\n'), hasLength(1), reason: body);
        }
      }
    });

    test('a timeout beyond 64 bits is a config error', () {
      // A2: such an integer decodes to a double, so the exact-int check refuses it
      for (final timeout in [
        '9223372036854775808',
        '99999999999999999999',
        '1e2',
        '1.0',
      ]) {
        final f = File('${dir.path}/c.json')
          ..writeAsStringSync(
            '{"format":2,"reviewers":[{"login":"rev-bot","role":"required","timeout":$timeout}]}',
          );
        final r = run(['--check-config', f.path]);
        expect(r.code, 2, reason: timeout);
        expect(r.out, '', reason: timeout);
        expect(
          r.err,
          'reviewers.py: rev-bot: timeout: must be a non-negative integer\n',
          reason: timeout,
        );
      }
    });

    test('a timeout at the 64-bit edge is accepted', () {
      final f = File('${dir.path}/c.json')
        ..writeAsStringSync(
          '{"format":2,"reviewers":[{"login":"rev-bot","role":"required","timeout":9223372036854775807}]}',
        );
      final r = run(['--check-config', f.path]);
      expect(r.code, 0, reason: r.err);
    });

    test('the reviewers document keeps the compact keys the watcher reads', () {
      final cfg = File('${dir.path}/c.json')
        ..writeAsStringSync(jsonEncode(config({'sha_pattern': '([0-9a-f]+)'})));
      final check = run(['--check-config', cfg.path]);
      expect(loginsOf(check.out), '"rev-bot"');

      final material = File('${dir.path}/m.json')
        ..writeAsStringSync(
          jsonEncode({
            'head_oid': oid,
            'cfg': {'now': 1700000000},
            'recheck': ['a1', 'b2'],
            'fail_names': ['Y2k='],
            'fail_run_ids': [11, 22],
            'merge_state': 'DIRTY',
            'complete': false,
            'checks': {'total': 1},
            'checks_all': [
              {'name': 'build', 'state': 'pending'},
            ],
          }),
        );
      final r = run([
        '--config',
        cfg.path,
        '--material',
        material.path,
        '--head',
        oid,
      ]);
      expect(r.code, 0, reason: r.err);
      expect(r.out.endsWith('\n'), true);
      expect(r.out.trimRight().contains('\n'), false);
      expect(headOidOf(r.out), oid);
      expect(failNamesOf(r.out), ['"Y2k="']);
      expect(failRunIdsOf(r.out), ['11', '22']);
      expect(recheckBatches(r.out), ['"a1","b2"']);
      expect(r.out, contains('"merge_state":"DIRTY"'));
      expect(r.out, contains('"complete":false'));
      expect(RegExp(r'"ci_pending":[1-9]').hasMatch(r.out), true);
      expect(memberOf(r.out, 'sig'), startsWith('"sig":"'));
      expect(memberOf(r.out, 'attn'), startsWith('"attn":"'));
    });
  });

  group('the config format', () {
    test('format 1 is refused', () {
      final r = run([
        '--check-config',
        write('c.json', {'format': 1, 'reviewers': <Object?>[]}),
      ]);
      expect(r.code, 2);
      expect(r.err, 'reviewers.py: ${dir.path}/c.json: format must be 2\n');
    });
  });
}
