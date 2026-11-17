import 'dart:convert';
import 'dart:io';

import 'package:specwright_cli/src/update/openspec.dart';
import 'package:specwright_cli/src/update/options.dart';
import 'package:specwright_cli/src/update/packs.dart';
import 'package:specwright_cli/src/update/repo.dart';
import 'package:specwright_cli/src/update/settings.dart';
import 'package:test/test.dart';

import 'lifecycle_support.dart' show update;

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

  group('pack-docs', () {
    const gdd = 'docs/domain/gdd.md';

    void record(Map<String, Object?> packs) {
      File('$code/openspec/.specwright/packs.json')
        ..createSync(recursive: true)
        ..writeAsStringSync(
          jsonEncode({'format': 1, 'packs': packs, 'catalogue': <Object?>[]}),
        );
    }

    Map<String, Object?> entry(Map<String, String> documents) => {
      'version': '0.5.0',
      'skills': <Object?>[],
      'documents': documents,
      'init': {'questions': <Object?>[]},
    };

    void domainPack({bool template = true}) {
      pack(
        'domain',
        good('domain', {
          'documents': {
            'gdd': {'path': gdd, 'template': 'documents/gdd.md'},
          },
        }),
      );
      if (template) {
        File('$dl/packs/domain/documents/gdd.md')
          ..createSync(recursive: true)
          ..writeAsStringSync('# GDD\n\nFill in.\n');
      }
    }

    Future<(int, Map<String, Object?>)> docs() =>
        update(['--code', code, '--root', code, '--download', dl, 'pack-docs']);

    test('creates a missing document from its template, parents too', () async {
      domainPack();
      record({
        'domain': entry({'gdd': gdd}),
      });
      final (status, doc) = await docs();
      expect(status, 0, reason: '$doc');
      expect(doc, {
        'ok': true,
        'interface': 3,
        'subcommand': 'pack-docs',
        'documents': [
          {'pack': 'domain', 'id': 'gdd', 'path': gdd, 'status': 'created'},
        ],
      });
      expect(File('$code/$gdd').readAsStringSync(), '# GDD\n\nFill in.\n');
      expect(
        Directory('$code/docs/domain')
            .listSync()
            .map((e) => fwd(e.path).split('/').last),
        ['gdd.md'],
        reason: 'no temporary file is left',
      );
    });

    test('never overwrites a document: a rerun keeps it', () async {
      domainPack();
      record({
        'domain': entry({'gdd': gdd}),
      });
      File('$code/$gdd')
        ..createSync(recursive: true)
        ..writeAsStringSync('# Ours\n');
      final (status, doc) = await docs();
      expect(status, 0);
      expect(
        (doc['documents'] as List)
            .cast<Map<String, Object?>>()
            .single['status'],
        'kept',
      );
      expect(File('$code/$gdd').readAsStringSync(), '# Ours\n');
    });

    test('no record, or no documents in it, is nothing to do', () async {
      var (status, doc) = await docs();
      expect([status, doc['ok'], doc['documents']], [0, true, <Object?>[]]);
      domainPack();
      record({'domain': entry({})});
      (status, doc) = await docs();
      expect([status, doc['documents']], [0, <Object?>[]]);
    });

    test('a path that leaves the checkout, or a template the download lacks, '
        'refuses before anything is written', () async {
      domainPack();
      record({
        'domain': entry({'gdd': '../outside.md'}),
      });
      var (status, doc) = await docs();
      expect(status, 1);
      expect(doc['error'], 'refused');
      expect(
        doc['message'],
        'document gdd of pack domain: the path ../outside.md contains ... '
        'Nothing was written',
      );
      expect(
        (doc['refusals'] as List).cast<Map<String, Object?>>().single['code'],
        'pack_doc_path',
      );
      expect(File('${fwd(tmp.path)}/outside.md').existsSync(), isFalse);

      File('$dl/packs/domain/documents/gdd.md').deleteSync();
      record({
        'domain': entry({'gdd': gdd}),
      });
      (status, doc) = await docs();
      expect(status, 1);
      expect(
        (doc['refusals'] as List).cast<Map<String, Object?>>().single['code'],
        'pack_doc_template',
      );
      expect(
        doc['message'],
        'document gdd of pack domain: the download has no template for it. '
        'Nothing was written',
      );
      expect(File('$code/$gdd').existsSync(), isFalse);
    });

    test('a record that cannot be read stops', () async {
      record({'domain': entry({})});
      File('$code/openspec/.specwright/packs.json').writeAsStringSync('{');
      final (status, doc) = await docs();
      expect(status, 1);
      expect(doc['error'], 'packs_record_unreadable');
      expect(doc['documents'], <Object?>[]);
      expect(
        doc['message'] as String,
        startsWith('openspec/.specwright/packs.json is not readable ('),
      );
    });

    test('a write that fails says so and leaves no partial document', () async {
      domainPack();
      record({
        'domain': entry({'gdd': gdd}),
      });
      File('$code/docs').writeAsStringSync('a file in the way\n');
      final (status, doc) = await docs();
      expect(status, 1);
      expect(doc['error'], 'pack_doc_write_failed');
      expect(
        doc['message'] as String,
        startsWith('document gdd of pack domain: could not write $gdd ('),
      );
      expect(
        doc['message'] as String,
        endsWith(
          'No partial document was left; rerun pack-docs once the cause is '
          'fixed',
        ),
      );
      expect(doc['documents'], <Object?>[]);
    });
  });

  group('pack-verify', () {
    void record(List<String> enabled) {
      File('$code/openspec/.specwright/packs.json')
        ..createSync(recursive: true)
        ..writeAsStringSync(
          jsonEncode({
            'format': 1,
            'packs': {
              for (final n in enabled)
                n: {
                  'version': '0.5.0',
                  'skills': <Object?>[],
                  'documents': <String, Object?>{},
                  'init': {'questions': <Object?>[]},
                },
            },
            'catalogue': <Object?>[],
          }),
        );
    }

    void config() => File('$code/openspec/config.yaml')
      ..createSync(recursive: true)
      ..writeAsStringSync('schema: specwright\n');

    void gamedev() => pack(
      'gamedev',
      good('gamedev', {
        'rules': {
          'proposal': ['Name the loop'],
        },
        'operations': {
          'apply': {
            'guidance': ['Playtest each task'],
          },
        },
        'context': ['A game'],
      }),
    );

    final delivered = <String, List<String>>{};
    var scratchChecked = false;
    final calls = <String>[];

    /// What OpenSpec answers for each ask, from [delivered].
    Future<OpenspecResult> fake(
      List<String> args,
      String cwd, {
      Duration? timeout,
    }) async {
      calls.add(args.join(' '));
      expect(timeout, const Duration(seconds: 120));
      expect(cwd, '$dl/.update-scratch/pack-verify');
      if (!scratchChecked) {
        scratchChecked = true;
        expect(
          File('$cwd/openspec/changes/pack-verify/.openspec.yaml')
              .readAsStringSync(),
          'schema: specwright\n',
        );
        expect(File('$cwd/openspec/config.yaml').existsSync(), isTrue);
        expect(
          File('$cwd/openspec/schemas/specwright/schema.yaml').existsSync(),
          isTrue,
        );
        expect(Directory('$cwd/openspec/specs').existsSync(), isTrue);
      }
      final what = args[1];
      final isOp = what == 'apply' || what == 'archive';
      final target = isOp ? 'operations.$what' : 'rules.$what';
      return OpenspecResult(
        0,
        jsonEncode({
          isOp ? 'operationGuidance' : 'rules': delivered[target] ?? <String>[],
          'context': (delivered['context'] ?? <String>[]).join('\n'),
        }),
        '',
      );
    }

    setUp(() {
      delivered.clear();
      calls.clear();
      scratchChecked = false;
      config();
    });

    Future<(int, Map<String, Object?>)> verify({
      List<String> previous = const [],
      OpenspecRunner? run,
    }) => update([
      '--code',
      code,
      '--root',
      code,
      '--download',
      dl,
      for (final p in previous) ...['--previous', p],
      'pack-verify',
    ], openspec: run ?? fake);

    List<Object?> problemCodes(Map<String, Object?> doc) => [
      for (final p in (doc['problems'] as List).cast<Map<String, Object?>>())
        p['code'],
    ];

    test('every line a pack declares reaches OpenSpec: ok, 5 runs, scratch '
        'removed', () async {
      gamedev();
      record(['gamedev']);
      delivered['rules.proposal'] = ['[pack:gamedev] Name the loop'];
      delivered['operations.apply'] = ['[pack:gamedev] Playtest each task'];
      delivered['context'] = ['[pack:gamedev] A game'];
      final (status, doc) = await verify();
      expect(status, 0, reason: '$doc');
      expect(doc, {
        'ok': true,
        'interface': 3,
        'subcommand': 'pack-verify',
        'checked': {
          'packs': ['gamedev'],
          'previous': <Object?>[],
          'lines': 3,
          'core_lines': 0,
          'runs': 5,
        },
        'problems': <Object?>[],
      });
      expect(calls, [
        'instructions proposal --change pack-verify --json',
        'instructions design --change pack-verify --json',
        'instructions tasks --change pack-verify --json',
        'instructions apply --change pack-verify --json',
        'instructions archive --change pack-verify --json',
      ]);
      expect(Directory('$dl/.update-scratch').existsSync(), isFalse);
    });

    test('a line that does not arrive is missing; one that arrives twice is a '
        'duplicate', () async {
      gamedev();
      record(['gamedev']);
      delivered['rules.proposal'] = [];
      delivered['operations.apply'] = [
        '[pack:gamedev] Playtest each task',
        '[pack:gamedev] Playtest each task',
      ];
      delivered['context'] = ['[pack:gamedev] A game'];
      final (status, doc) = await verify();
      expect(status, 1);
      expect(doc['ok'], isFalse);
      expect(problemCodes(doc), ['duplicate', 'missing']);
      final missing = (doc['problems'] as List)
          .cast<Map<String, Object?>>()
          .last;
      expect(missing['pack'], 'gamedev');
      expect(missing['line'], 'Name the loop');
      expect(missing['target'], 'rules.proposal');
      expect(
        missing['message'],
        "'[pack:gamedev] Name the loop' is expected 1 time(s) in "
        'rules.proposal and 0 reached OpenSpec',
      );
    });

    test('a line of a pack that is no longer enabled is not_enabled', () async {
      gamedev();
      record(['gamedev']);
      delivered['rules.proposal'] = [
        '[pack:gamedev] Name the loop',
        '[pack:old] Leftover',
        '[pack:other] not ours to manage',
      ];
      delivered['operations.apply'] = ['[pack:gamedev] Playtest each task'];
      delivered['context'] = ['[pack:gamedev] A game'];
      final (status, doc) = await verify(previous: ['old', 'gamedev']);
      expect(status, 1);
      expect(problemCodes(doc), ['not_enabled']);
      expect((doc['problems'] as List).single, {
        'code': 'not_enabled',
        'pack': 'old',
        'line': 'Leftover',
        'target': 'rules.proposal',
        'message':
            "'[pack:old] Leftover' in rules.proposal belongs to pack old, "
            'which is no longer enabled',
      });
      expect((doc['checked'] as Map<String, Object?>)['previous'], [
        'gamedev',
        'old',
      ]);
    });

    test('a core context line OpenSpec does not deliver is reported', () async {
      gamedev();
      record(['gamedev']);
      File('$dl/templates/openspec/config.yaml')
        ..createSync(recursive: true)
        ..writeAsStringSync(
          'schema: specwright\ncontext: |\n  # comment\n  Core line one\n'
          '  Core line two\nrules: {}\n',
        );
      delivered['rules.proposal'] = ['[pack:gamedev] Name the loop'];
      delivered['operations.apply'] = ['[pack:gamedev] Playtest each task'];
      delivered['context'] = ['[pack:gamedev] A game', 'Core line one'];
      final (status, doc) = await verify();
      expect(status, 1);
      expect((doc['checked'] as Map<String, Object?>)['core_lines'], 2);
      expect((doc['problems'] as List).single, {
        'code': 'core_context_missing',
        'pack': null,
        'line': 'Core line two',
        'target': 'context',
        'message':
            'a Specwright context line does not reach OpenSpec (is context '
            'over 50 KB?)',
      });
    });

    test('an openspec run that fails is a problem; a missing CLI stops the '
        'runs', () async {
      gamedev();
      record(['gamedev']);
      var n = 0;
      var (status, doc) = await verify(
        run: (args, cwd, {timeout}) async {
          n++;
          return n == 2
              ? const OpenspecResult(1, '', 'error: boom\n')
              : fake(args, cwd, timeout: timeout);
        },
      );
      expect(status, 1);
      expect(problemCodes(doc).where((c) => c == 'openspec_failed').length, 1);
      final failed = (doc['problems'] as List)
          .cast<Map<String, Object?>>()
          .firstWhere((p) => p['code'] == 'openspec_failed');
      expect(failed['target'], 'rules.design');
      expect(failed['message'], 'openspec instructions design: error: boom');

      calls.clear();
      (status, doc) = await verify(
        run: (args, cwd, {timeout}) async {
          calls.add(args.join(' '));
          return const OpenspecResult(
            127,
            '',
            'the openspec CLI is not on PATH',
          );
        },
      );
      expect(status, 1);
      expect(calls, hasLength(1));
      expect((doc['checked'] as Map<String, Object?>)['runs'], 1);
      expect(Directory('$dl/.update-scratch').existsSync(), isFalse);
    });

    test(
      'an unreadable manifest of an enabled pack is pack_unreadable',
      () async {
        record(['gone']);
        final (status, doc) = await verify();
        expect(status, 1);
        expect((doc['problems'] as List).first, {
          'code': 'pack_unreadable',
          'pack': 'gone',
          'line': null,
          'target': null,
          'message':
              'pack gone is enabled but its manifest in the download is '
              'unreadable: pack.json is missing',
        });
      },
    );

    test('a missing schema, config or an unreadable record stops with one '
        'error', () async {
      record([]);
      File('$code/openspec/config.yaml').deleteSync();
      var (status, doc) = await verify();
      expect(status, 1);
      expect(doc, {
        'ok': false,
        'interface': 3,
        'subcommand': 'pack-verify',
        'error': 'config_missing',
        'message':
            '$code/openspec/config.yaml does not exist; run Step 5 first',
        'problems': <Object?>[],
      });
      config();
      File('$code/openspec/.specwright/packs.json').writeAsStringSync('[');
      (status, doc) = await verify();
      expect(doc['error'], 'packs_record_unreadable');
      expect(
        doc['message'] as String,
        startsWith('openspec/.specwright/packs.json is not readable JSON ('),
      );
      File('$dl/schemas/specwright/schema.yaml').deleteSync();
      (status, doc) = await verify();
      expect(doc['error'], 'schema_missing');
      expect(
        doc['message'],
        '$dl/schemas/specwright/schema.yaml does not exist',
      );
    });
  });
}
