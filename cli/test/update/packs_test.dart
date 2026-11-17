import 'dart:convert';
import 'dart:io';

import 'package:specwright_cli/src/update/options.dart';
import 'package:specwright_cli/src/update/packs.dart';
import 'package:specwright_cli/src/update/repo.dart';
import 'package:specwright_cli/src/update/settings.dart';
import 'package:test/test.dart';

String fwd(String path) => path.replaceAll(r'\', '/');

void main() {
  late Directory tmp;
  late String dl;
  late String code;

  setUp(() {
    tmp = Directory.systemTemp.createTempSync('sw-update-packs-');
    dl = '${fwd(tmp.path)}/dl';
    code = '${fwd(tmp.path)}/code';
    Directory(code).createSync(recursive: true);
    File('$dl/schemas/specwright/schema.yaml')
      ..createSync(recursive: true)
      ..writeAsStringSync(
        'name: specwright\nartifacts:\n  - id: proposal\n  - id: design\n  - id: tasks\n',
      );
  });
  tearDown(() => tmp.deleteSync(recursive: true));

  void pack(
    String name,
    Map<String, Object?> manifest, {
    List<String> skills = const [],
  }) {
    File('$dl/packs/$name/pack.json')
      ..createSync(recursive: true)
      ..writeAsStringSync(jsonEncode(manifest));
    for (final s in skills) {
      File('$dl/packs/$name/skills/$s/SKILL.md')
        ..createSync(recursive: true)
        ..writeAsStringSync('skill $s\n');
    }
  }

  Map<String, Object?> good(
    String name, [
    Map<String, Object?> more = const {},
  ]) => {'format': 1, 'name': name, 'description': 'A pack', ...more};

  List<String> codes(PackCheck r) => [
    for (final f in r.refusals) '${f['code']}',
  ];

  group('pack-check', () {
    test('a well-formed pack passes', () {
      pack(
        'gamedev',
        good('gamedev', {
          'skills': ['gamedev-art'],
          'context': ['Engine is Godot.'],
          'rules': {
            'proposal': ['Name the player verb.'],
          },
          'operations': {
            'apply': {
              'guidance': ['Playtest each task.'],
            },
          },
          'documents': {
            'gdd': {'path': 'docs/gdd.md', 'template': 'gdd.md'},
          },
          'init': {
            'questions': ['Which engine?'],
          },
          'signals': ['project.godot'],
        }),
        skills: ['gamedev-art'],
      );
      File('$dl/packs/gamedev/gdd.md').writeAsStringSync('# GDD\n');
      final r = checkPacks(dl, [])!;
      expect(r.refusals, isEmpty);
      expect(r.packs, [
        {'name': 'gamedev', 'ok': true},
      ]);
    });

    test('no schema means no check', () {
      File('$dl/schemas/specwright/schema.yaml').deleteSync();
      expect(checkPacks(dl, []), isNull);
      final (doc, status) = packCheckDocument(
        UpdateOptions(
          subcommand: 'pack-check',
          code: code,
          root: code,
          download: dl,
        ),
      );
      expect(status, 1);
      expect(
        (doc['refusals'] as List).single,
        containsPair('code', 'schema_missing'),
      );
    });

    test('refuses source, unknown field, wrong format and a name mismatch', () {
      pack('a', {
        'format': 2,
        'name': 'b',
        'description': 'd',
        'source': 'x',
        'extra': 1,
      });
      expect(
        codes(checkPacks(dl, ['a'])!),
        containsAll([
          'external_pack_unsupported',
          'manifest_invalid',
          'format_unsupported',
          'name_mismatch',
        ]),
      );
    });

    test(
      'refuses a reserved name and unknown artifacts, operations and lines',
      () {
        pack(
          'opsx-more',
          good('opsx-more', {
            'rules': {
              'nope': ['x'],
              'design': ['[pack:opsx-more] twice'],
            },
            'operations': {
              'ship': {
                'guidance': ['x'],
              },
            },
            'context': ['   '],
          }),
        );
        final c = codes(checkPacks(dl, [])!);
        expect(
          c,
          containsAll([
            'manifest_invalid',
            'unknown_artifact',
            'unknown_operation',
            'line_invalid',
          ]),
        );
      },
    );

    test('a line that pairs a gate term with a relaxing term is refused', () {
      pack(
        'p',
        good('p', {
          'rules': {
            'tasks': ['You may skip the review when small.'],
          },
        }),
      );
      final r = checkPacks(dl, ['p'])!;
      expect(codes(r), ['relaxes_gate']);
      expect(
        r.refusals.single['message'],
        contains('rules.tasks[0] pairs a gate term with a relaxing term'),
      );
    });

    test('trip relaxes only after a negator', () {
      expect(relaxesGate('You must trip T4 early.'), isFalse);
      expect(relaxesGate('Do not trip T2 here.'), isTrue);
      expect(relaxesGate("Don't trip T2 here."), isTrue);
      expect(relaxesGate('Skip the movie.'), isFalse);
      expect(relaxesGate('Waive the FULL tier'), isTrue);
      expect(relaxesGate('use light tier'), isFalse);
    });

    test('limits: 40 lines, 2048 context bytes, 500 characters', () {
      pack('p', good('p', {'context': List.filled(41, 'ok')}));
      pack(
        'q',
        good('q', {
          'context': [
            ('x' * 400),
            ('y' * 400),
            ('z' * 400),
            ('w' * 400),
            ('v' * 400),
            ('u' * 400),
          ],
        }),
      );
      pack(
        'r',
        good('r', {
          'rules': {
            'tasks': ['x' * 501],
          },
        }),
      );
      expect(codes(checkPacks(dl, ['p'])!), ['too_many_lines']);
      expect(codes(checkPacks(dl, ['q'])!), ['context_too_large']);
      expect(codes(checkPacks(dl, ['r'])!), ['line_invalid']);
    });

    test('skills: prefix, owner, missing and unlisted', () {
      pack(
        'game',
        good('game', {
          'skills': ['game-a', 'other-b', 'game-missing'],
        }),
        skills: ['game-a', 'game-extra'],
      );
      pack('game-deep', good('game-deep'));
      final c = codes(checkPacks(dl, ['game'])!);
      expect(c, containsAll(['skill_name', 'skill_missing', 'skill_unlisted']));
    });

    test('requires: missing pack and a cycle', () {
      pack(
        'a',
        good('a', {
          'requires': ['b', 'ghost'],
        }),
      );
      pack(
        'b',
        good('b', {
          'requires': ['a'],
        }),
      );
      final r = checkPacks(dl, [])!;
      expect(codes(r), containsAll(['pack_requires', 'pack_cycle']));
      expect(
        r.refusals.firstWhere((f) => f['code'] == 'pack_cycle')['message'],
        'requires form a cycle: a -> b -> a',
      );
    });

    test('documents: unsafe path and a missing template', () {
      pack(
        'p',
        good('p', {
          'documents': {
            'a': {'path': '../x.md', 'template': 'a.md'},
            'b': {'path': 'ok.md', 'template': 'missing.md'},
          },
        }),
      );
      final r = checkPacks(dl, ['p'])!;
      expect(codes(r), ['document_invalid', 'document_invalid']);
    });

    test('an unknown pack names the packs the download has', () {
      pack('p', good('p'));
      final r = checkPacks(dl, ['zzz'])!;
      expect(
        r.refusals.single['message'],
        'the download has no pack zzz; it has: p',
      );
    });

    test('a manifest that is not JSON', () {
      File('$dl/packs/p/pack.json')
        ..createSync(recursive: true)
        ..writeAsStringSync('{');
      expect(
        checkPacks(dl, ['p'])!.refusals.single['message'] as String,
        startsWith('pack.json is not valid JSON'),
      );
    });
  });

  group('packs in plan', () {
    UpdateOptions options({
      List<String> packs = const [],
      List<String> docs = const [],
      List<String>? skills,
    }) => UpdateOptions(
      subcommand: 'plan',
      code: code,
      root: code,
      download: dl,
      packs: packs,
      packDocs: docs,
      skills: skills ?? ['$code/.claude/skills'],
    );

    UpdateRepo repoOf(UpdateOptions o) =>
        UpdateRepo.of(o, loadUpdateSettings(code));

    test('refuses packs on a store, outside the checkout, and an unenabled requirement', () async {
      pack(
        'a',
        good('a', {
          'requires': ['b'],
        }),
      );
      pack('b', good('b'));
      final o = options(
        packs: ['a'],
        skills: ['${fwd(tmp.path)}/elsewhere/skills'],
      );
      final refusals = <Map<String, Object?>>[];
      await planPacks(
        o,
        repoOf(o),
        '$code/openspec/.specwright',
        'claim',
        refusals,
      );
      expect([
        for (final f in refusals) f['code'],
      ], containsAll(['packs_on_store', 'packs_user_level', 'pack_requires']));
      expect(
        refusals.firstWhere((f) => f['code'] == 'pack_requires')['message'],
        'a requires b, which packs: does not enable; enable b too (it is never enabled on its own), or remove a. Nothing was written',
      );
    });

    test(
      'orders dependencies first and resolves documents, with an override',
      () async {
        pack(
          'a',
          good('a', {
            'requires': ['b'],
            'documents': {
              'd': {'path': 'docs/d.md', 'template': 't.md'},
            },
          }),
        );
        File('$dl/packs/a/t.md').writeAsStringSync('t');
        pack('b', good('b'));
        File('$code/docs/own.md')
          ..createSync(recursive: true)
          ..writeAsStringSync('mine');
        final o = options(packs: ['a', 'b'], docs: ['a.d=docs/own.md']);
        final refusals = <Map<String, Object?>>[];
        final pk = await planPacks(
          o,
          repoOf(o),
          '$code/openspec/.specwright',
          'none',
          refusals,
        );
        expect(refusals, isEmpty);
        expect(pk.order, ['b', 'a']);
        expect(pk.documents['a'], [
          {'id': 'd', 'path': 'docs/own.md', 'exists': true},
        ]);
      },
    );

    test('document path refusals and --pack-doc forms', () async {
      pack(
        'a',
        good('a', {
          'documents': {
            'd': {'path': 'docs/d.md', 'template': 't.md'},
          },
        }),
      );
      File('$dl/packs/a/t.md').writeAsStringSync('t');
      final o = options(
        packs: ['a'],
        docs: ['a.d=/abs.md', 'nonsense', 'zz.d=x', 'a.q=x'],
      );
      final refusals = <Map<String, Object?>>[];
      await planPacks(
        o,
        repoOf(o),
        '$code/openspec/.specwright',
        'none',
        refusals,
      );
      expect(
        [for (final f in refusals) f['code']],
        [
          'pack_doc_invalid',
          'pack_doc_unknown',
          'pack_doc_unknown',
          'pack_doc_path',
        ],
      );
      expect(
        refusals.first['message'],
        "--pack-doc 'nonsense' is not <pack>.<id>=<path>",
      );
      expect(
        refusals.last['message'],
        'document d of pack a: the path /abs.md is absolute. Nothing was written',
      );
    });

    test('an unreadable record is a refusal, a missing one is none', () async {
      final o = options();
      var refusals = <Map<String, Object?>>[];
      var pk = await planPacks(
        o,
        repoOf(o),
        '$code/openspec/.specwright',
        'none',
        refusals,
      );
      expect(refusals, isEmpty);
      expect(pk.previous, isEmpty);
      File('$code/openspec/.specwright/packs.json')
        ..createSync(recursive: true)
        ..writeAsStringSync(
          '{"format": 1, "packs": {"a": {"skills": ["a-x"]}}}',
        );
      refusals = [];
      pk = await planPacks(
        o,
        repoOf(o),
        '$code/openspec/.specwright',
        'none',
        refusals,
      );
      expect(pk.previous, ['a']);
      File('$code/openspec/.specwright/packs.json').writeAsStringSync('[]');
      refusals = [];
      await planPacks(
        o,
        repoOf(o),
        '$code/openspec/.specwright',
        'none',
        refusals,
      );
      expect(refusals.single['code'], 'packs_record_unreadable');
      expect(
        refusals.single['message'],
        'openspec/.specwright/packs.json is not a format 1 record with a packs object. '
        'Nothing was written; fix or remove the file, then rerun the update',
      );
    });

    test('skills: an identical unrecorded directory is adopted, a different one refused, a dropped pack removed', () async {
      pack(
        'a',
        good('a', {
          'skills': ['a-one', 'a-two'],
        }),
        skills: ['a-one', 'a-two'],
      );
      final skills = '$code/.claude/skills';
      Directory('$skills/a-one').createSync(recursive: true);
      File('$skills/a-one/SKILL.md').writeAsStringSync('skill a-one\n');
      File('$skills/a-two/SKILL.md')
        ..createSync(recursive: true)
        ..writeAsStringSync('edited\n');
      File('$skills/old-x/SKILL.md')
        ..createSync(recursive: true)
        ..writeAsStringSync('old');
      File('$code/openspec/.specwright/packs.json')
        ..createSync(recursive: true)
        ..writeAsStringSync(
          '{"format":1,"packs":{"old":{"skills":["old-x","evil"]}}}',
        );
      final o = options(packs: ['a']);
      final refusals = <Map<String, Object?>>[];
      final pk = await planPacks(
        o,
        repoOf(o),
        '$code/openspec/.specwright',
        'none',
        refusals,
      );
      final group = <String, Object?>{
        'id': 'skills-1',
        'dir': skills,
        'items': <Map<String, Object?>>[],
      };
      final orphans = <Map<String, Object?>>[];
      await addPackSkillItems(o, repoOf(o), group, pk, refusals, orphans);
      expect(pk.adopted['a']!.single['name'], 'a-one');
      expect(refusals.single['code'], 'unmanaged_skill');
      final items = group['items'] as List<Map<String, Object?>>;
      expect(
        [for (final i in items) '${i['name']}:${i['type']}'],
        ['a-one:dir', 'a-two:dir', 'old-x:remove'],
      );
    });

    test('the record bytes list enabled packs, then the catalogue', () async {
      pack(
        'a',
        good('a', {
          'init': {
            'questions': ['Q?'],
          },
          'signals': ['s'],
          'requires': ['b'],
        }),
      );
      pack('b', good('b'));
      File('$dl/packs/bad/pack.json')
        ..createSync(recursive: true)
        ..writeAsStringSync('nope');
      final o = options(packs: ['a', 'b']);
      final refusals = <Map<String, Object?>>[];
      final pk = await planPacks(
        o,
        repoOf(o),
        '$code/openspec/.specwright',
        'none',
        refusals,
      );
      expect(refusals.where((f) => f['pack'] != 'bad'), isEmpty);
      final doc = jsonDecode(
        utf8.decode(await packRecordBytes(o, repoOf(o), '0.37.0', pk)),
      ) as Map;
      expect(doc['format'], 1);
      expect((doc['packs'] as Map).keys, ['b', 'a']);
      expect((doc['packs'] as Map)['a'], {
        'version': '0.37.0',
        'skills': <Object?>[],
        'documents': <String, Object?>{},
        'init': {
          'questions': ['Q?'],
        },
      });
      expect(
        [for (final c in doc['catalogue'] as List) (c as Map)['name']],
        ['a', 'b'],
      );
    });
  });
}
