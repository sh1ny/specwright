import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:specwright_cli/src/pr/reviewers.dart';
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
