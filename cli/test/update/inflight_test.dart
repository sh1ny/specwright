import 'dart:convert';
import 'dart:io';

import 'package:specwright_cli/src/update/file_ops.dart';
import 'package:specwright_cli/src/update/inflight.dart';
import 'package:specwright_cli/src/update/openspec.dart';
import 'package:specwright_cli/src/update/repo.dart';
import 'package:specwright_cli/src/update/settings.dart';
import 'package:test/test.dart';

String fwd(String path) => path.replaceAll(r'\', '/');

void git(String dir, List<String> args) {
  final r = Process.runSync('git', [
    '-C',
    dir,
    '-c',
    'user.name=t',
    '-c',
    'user.email=t@example.com',
    ...args,
  ]);
  expect(r.exitCode, 0, reason: '${r.stdout}${r.stderr}');
}

/// The runs of a fake `openspec`: [answers] maps the joined arguments to a
/// result; everything else passes with `{}`.
class Fake {
  Fake(this.answers);

  final Map<String, OpenspecResult> answers;
  final List<String> calls = [];
  final List<String> dirs = [];

  Future<OpenspecResult> call(
    List<String> args,
    String cwd, {
    Duration? timeout,
  }) async {
    final key = args.join(' ');
    calls.add(key);
    dirs.add(cwd);
    for (final e in answers.entries) {
      if (key.startsWith(e.key)) return e.value;
    }
    return const OpenspecResult(0, '{}', '');
  }
}

const pass = OpenspecResult(0, '{"items":[{"valid":true}]}', '');
OpenspecResult ok(Object json) => OpenspecResult(0, jsonEncode(json), '');

void main() {
  late Directory tmp;

  // resolved: Windows may hand out an 8.3 short temp path that git reports long
  setUp(
    () => tmp = Directory(
      Directory.systemTemp
          .createTempSync('sw-update-inflight-')
          .resolveSymbolicLinksSync(),
    ),
  );
  tearDown(() => tmp.deleteSync(recursive: true));

  group('first error', () {
    test(
      'takes the first error line, else the first line, skipping Note lines',
      () {
        expect(
          firstError('Note: x\nsomething\nError: bad\nmore'),
          'Error: bad',
        );
        expect(firstError('Note: x\n\nfirst\nsecond'), 'first');
        expect(firstError(''), 'no output');
      },
    );
  });

  group('the three checks', () {
    test('a change that passes all three', () async {
      final fake = Fake({
        'validate': pass,
        'status': ok({'status': <Object?>[], 'artifacts': <Object?>[]}),
      });
      expect(await checkChange(fake.call, '/s', 'c1'), isNull);
      expect(fake.calls, [
        'schema validate specwright',
        'validate c1 --json',
        'status --change c1 --json',
      ]);
    });

    test('an invalid schema stops at the first run', () async {
      final fake = Fake({
        'schema': const OpenspecResult(1, '', 'Error: broken yaml\n'),
      });
      final failure = await checkChange(fake.call, '/s', 'c1');
      expect(failure!.step, 'schema');
      expect(
        failure.error,
        'openspec schema validate specwright: Error: broken yaml',
      );
      expect(fake.calls.length, 1);
    });

    test('a validation issue names its path and message', () async {
      final fake = Fake({
        'validate': ok({
          'items': [
            {
              'valid': false,
              'issues': [
                {'path': 'specs/a', 'message': 'no scenarios'},
              ],
            },
          ],
        }),
      });
      final failure = await checkChange(fake.call, '/s', 'c1');
      expect(failure!.step, 'validate');
      expect(failure.error, 'openspec validate c1: specs/a: no scenarios');
    });

    test('a failed run fails even when its item says valid', () async {
      final fake = Fake({
        'validate': const OpenspecResult(
          1,
          '{"items":[{"valid":true}]}',
          'Error: crashed',
        ),
      });
      final failure = await checkChange(fake.call, '/s', 'c1');
      expect(failure!.step, 'error');
      expect(failure.error, 'openspec validate c1: Error: crashed');
    });

    test('a status error and a dependency that is not done', () async {
      var fake = Fake({
        'validate': pass,
        'status': ok({
          'status': [
            {'severity': 'error', 'message': 'cycle'},
          ],
        }),
      });
      expect(
        (await checkChange(fake.call, '/s', 'c1'))!.error,
        'openspec status c1: cycle',
      );
      fake = Fake({
        'validate': pass,
        'status': ok({
          'artifacts': [
            {
              'id': 'design',
              'status': 'done',
              'requires': ['proposal'],
            },
            {'id': 'proposal', 'status': 'ready'},
          ],
        }),
      });
      expect(
        (await checkChange(fake.call, '/s', 'c1'))!.error,
        'openspec status c1: artifact design exists but its dependency proposal is ready',
      );
    });
  });

  group('changes in flight', () {
    late String code;
    late String download;

    void change(String base, String name, {String schema = 'specwright'}) {
      File('$base/openspec/changes/$name/.openspec.yaml')
        ..createSync(recursive: true)
        ..writeAsStringSync('schema: $schema\ncreated: 2026-01-01\n');
      File('$base/openspec/changes/$name/proposal.md')
          .writeAsStringSync('# $name\n');
    }

    setUp(() {
      code = '${fwd(tmp.path)}/code';
      download = '${fwd(tmp.path)}/dl';
      Directory(code).createSync(recursive: true);
      git(code, ['init', '-q', '-b', 'main']);
      File('$code/README').writeAsStringSync('x');
      git(code, ['add', '.']);
      git(code, ['commit', '-q', '-m', 'first']);
      File('$download/schemas/specwright/schema.yaml')
        ..createSync(recursive: true)
        ..writeAsStringSync('name: specwright\n');
    });

    Future<
      ({
        List<Map<String, Object?>> entries,
        List<Map<String, Object?>> warnings,
      })
    >
    run(Fake fake, {String role = 'none', String to = '0.38.0'}) {
      final repo = UpdateRepo(
        code: code,
        root: code,
        settings: loadUpdateSettings(code),
      );
      return inflightEntries(
        repo: repo,
        ops: UpdateFileOps(environment: {}),
        run: fake.call,
        download: download,
        stateDir: '$code/openspec/.specwright',
        to: to,
        schemaDir: '$download/schemas/specwright',
        role: role,
      );
    }

    test('validates a working-tree change in a scratch root and removes the scratch', () async {
      change(code, 'add-x');
      change(code, 'other-schema', schema: 'spec-driven');
      Directory('$code/openspec/changes/archive/old')
          .createSync(recursive: true);
      final fake = Fake({'validate': pass, 'status': ok({})});
      final found = await run(fake);
      expect(found.entries, [
        {
          'name': 'add-x',
          'source': 'working tree',
          'status': 'validated',
          'validated_against': '0.38.0',
        },
        {
          'name': 'other-schema',
          'source': 'working tree',
          'status': 'not on specwright',
          'validated_against': null,
        },
      ]);
      expect(fake.dirs.every((d) => d.contains('.update-scratch')), isTrue);
      expect(Directory('$download/.update-scratch').existsSync(), isFalse);
    });

    test('reads a change that exists only on a local branch from git, not the checkout', () async {
      git(code, ['checkout', '-q', '-b', 'feat/on-branch']);
      change(code, 'on-branch');
      git(code, ['add', '.']);
      git(code, ['commit', '-q', '-m', 'change']);
      git(code, ['checkout', '-q', 'main']);
      expect(Directory('$code/openspec/changes').existsSync(), isFalse);
      final fake = Fake({'validate': pass, 'status': ok({})});
      final found = await run(fake);
      expect(found.entries.single['name'], 'on-branch');
      expect(found.entries.single['source'], 'feat/on-branch');
      expect(found.entries.single['status'], 'validated');
    });

    test(
      'an invalid change carries its error and the installed-schema note',
      () async {
        change(code, 'broken');
        File('$code/openspec/.specwright/VERSION')
          ..createSync(recursive: true)
          ..writeAsStringSync('0.37.0\n');
        File('$code/openspec/schemas/specwright/schema.yaml')
          ..createSync(recursive: true)
          ..writeAsStringSync('name: specwright\n');
        final fake = Fake({
          'validate': ok({
            'items': [
              {
                'valid': false,
                'issues': [
                  {'path': 'p', 'message': 'm'},
                ],
              },
            ],
          }),
          'status': ok({}),
        });
        final found = await run(fake);
        final entry = found.entries.single;
        expect(entry['status'], 'invalid');
        expect(entry['error'], 'openspec validate broken: p: m');
        expect(
          entry['note'],
          '; it already fails on 0.37.0 (openspec validate broken: p: m), so the update to 0.38.0 did not cause it',
        );
      },
    );

    test(
      'in a store, a change with no local branch belongs to another project',
      () async {
        change(code, 'theirs');
        git(code, ['branch', 'feat/mine']);
        change(code, 'mine');
        final fake = Fake({'validate': pass, 'status': ok({})});
        final found = await run(fake, role: 'owner');
        final byName = {for (final e in found.entries) '${e['name']}': e};
        expect(byName['theirs']!['status'], 'other project');
        expect(byName['theirs']!['validated_against'], isNull);
        expect(byName['mine']!['status'], 'validated');
      },
    );
  });
}
