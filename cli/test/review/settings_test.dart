import 'dart:io';

import 'package:specwright_cli/src/review/settings.dart';
import 'package:specwright_cli/src/review/stop.dart';
import 'package:test/test.dart';

void main() {
  late Directory root;
  setUp(
    () => root = Directory.systemTemp.createTempSync('sw-review-settings-'),
  );
  tearDown(() => root.deleteSync(recursive: true));

  String write(String base, String text) {
    final file = File('${root.path}/$base/openspec/specwright.yaml')
      ..createSync(recursive: true)
      ..writeAsStringSync(text);
    return file.parent.parent.path;
  }

  test('cwd settings take precedence over repository settings', () {
    final cwd = write(
      'cwd',
      'review:\n  timeout: 4m\n  routes:\n    omp:\n      tools: [read, grep, glob, lsp]\n',
    );
    final top = write('top', 'review:\n  timeout: 9m\n');
    final got = readReviewSettings(bases: [cwd, top]);
    expect(got.review['timeout'], '4m');
    expect(got.routes['omp']!.tools, ['read', 'grep', 'glob', 'lsp']);
  });

  test('falls back to the toplevel and keeps shared YAML scalar semantics', () {
    final top = write('top', 'review:\n  cross_model: no\n  timeout: 5m\n');
    final got = readReviewSettings(bases: ['${root.path}/absent', top]);
    expect(got.review['cross_model'], isFalse);
    expect(got.review['timeout'], '5m');
  });

  test('no settings retains the safe route configuration', () {
    final got = readReviewSettings(bases: [root.path]);
    expect(got.review, isEmpty);
    expect(got.routes['omp']!.tools, ['read', 'grep', 'glob']);
  });

  test(
    'explicit settings replaces search without touching the project file',
    () {
      final project = write('project', 'review:\n  timeout: 3m\n');
      final explicit = File('${root.path}/explicit.yml')
        ..writeAsStringSync(
          'review:\n  timeout: 8m\n  routes:\n    claude:\n      args: ["--no-session-persistence"]\n',
        );
      final before = File('$project/openspec/specwright.yaml')
          .readAsBytesSync();
      final got = readReviewSettings(
        bases: [project],
        settingsPath: explicit.path,
      );
      expect(got.review['timeout'], '8m');
      expect(got.routes['claude']!.args, ['--no-session-persistence']);
      expect(
        File('$project/openspec/specwright.yaml').readAsBytesSync(),
        before,
      );
    },
  );

  test(
    'unsupported YAML stops with the actual line before lenient parsing',
    () {
      final top = write('top', 'review:\n  order:\n    - codex\n');
      expect(
        () => readReviewSettings(bases: [top]),
        throwsA(
          isA<ReviewStop>()
              .having((e) => e.error, 'error', 'bad_settings')
              .having((e) => e.code, 'code', 1)
              .having((e) => e.message, 'message', contains('line 3')),
        ),
      );
    },
  );

  test(
    'invalid route settings are checked even before a route is selected',
    () {
      final top = write(
        'top',
        'review:\n  routes:\n    omp:\n      tools: [read, eval]\n',
      );
      expect(
        () => readReviewSettings(bases: [top]),
        throwsA(
          isA<ReviewStop>()
              .having((e) => e.error, 'error', 'route_setting_unsafe')
              .having(
                (e) => e.message,
                'message',
                contains('review.routes.omp.tools'),
              ),
        ),
      );
    },
  );

  test(
    'missing explicit settings keeps the usage stop rather than defaults',
    () {
      expect(
        () => readReviewSettings(
          bases: [root.path],
          settingsPath: '${root.path}/missing.yml',
        ),
        throwsA(isA<ReviewStop>().having((e) => e.code, 'code', 2)),
      );
    },
  );
}
