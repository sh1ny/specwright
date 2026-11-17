import 'dart:convert';
import 'dart:io';

import 'package:specwright_cli/src/update/file_ops.dart';
import 'package:specwright_cli/src/update/openspec.dart';
import 'package:specwright_cli/src/update/options.dart';
import 'package:specwright_cli/src/update/plan.dart';
import 'package:specwright_cli/src/update/stop.dart';
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

Future<OpenspecResult> passing(
  List<String> args,
  String cwd, {
  Duration? timeout,
}) async => const OpenspecResult(0, '{"items":[{"valid":true}]}', '');

void main() {
  late Directory tmp;
  late String code;
  late String dl;

  setUp(() {
    // resolved: Windows may hand out an 8.3 short temp path that git reports long
    tmp = Directory(
      Directory.systemTemp
          .createTempSync('sw-update-plan-')
          .resolveSymbolicLinksSync(),
    );
    code = '${fwd(tmp.path)}/code';
    dl = '${fwd(tmp.path)}/dl';
    Directory(code).createSync(recursive: true);
    git(code, ['init', '-q', '-b', 'main']);
    File('$code/README').writeAsStringSync('x');
    git(code, ['add', '.']);
    git(code, ['commit', '-q', '-m', 'first']);
    File('$dl/VERSION')
      ..createSync(recursive: true)
      ..writeAsStringSync('0.38.0\n');
    File('$dl/schemas/specwright/schema.yaml')
      ..createSync(recursive: true)
      ..writeAsStringSync('name: specwright\nartifacts:\n  - id: proposal\n');
    for (final s in ['specwright-commit', 'specwright-pr']) {
      File('$dl/skills/$s/SKILL.md')
        ..createSync(recursive: true)
        ..writeAsStringSync('s');
    }
    File('$dl/agents/claude/specwright-reviewer.md')
      ..createSync(recursive: true)
      ..writeAsStringSync('a');
  });
  tearDown(() => tmp.deleteSync(recursive: true));

  UpdateOptions options({
    List<String>? skills,
    List<String>? agents,
    String? ref,
    List<String> packs = const [],
    String? root,
  }) => UpdateOptions(
    subcommand: 'plan',
    code: code,
    root: root ?? code,
    download: dl,
    ref: ref,
    skills: skills ?? ['$code/.claude/skills'],
    agents: agents ?? [],
    packs: packs,
  );

  Future<Map<String, Object?>> plan(
    UpdateOptions o, {
    Map<String, String>? env,
  }) async => (await makePlan(
    o,
    check: true,
    run: passing,
    ops: UpdateFileOps(environment: {}),
    environment: env ?? const {},
  )).doc;

  List<String> codes(Map<String, Object?> doc) => [
    for (final r in doc['refusals'] as List) '${(r as Map)['code']}',
  ];

  test('a fresh install: kind, targets in group order, interface 3, nothing refused', () async {
    final doc = await plan(options(agents: ['claude=$code/.claude/agents']));
    expect(doc['ok'], isTrue, reason: '$doc');
    expect(doc['interface'], 3);
    expect(doc['kind'], 'fresh');
    expect(doc['from'], isNull);
    expect(doc['to'], '0.38.0');
    expect(doc['role'], 'none');
    expect(doc['unchanged'], isTrue);
    expect(doc['inflight_checked'], isTrue);
    expect(doc.containsKey('sw'), isFalse);
    final targets = (doc['targets'] as List).cast<Map<String, Object?>>();
    expect(
      [for (final t in targets) '${t['group']}/${t['name']}'],
      [
        'skills-1/specwright-commit',
        'skills-1/specwright-pr',
        'agents-1-claude/specwright-reviewer.md',
        'schema/specwright',
        'record/packs.json',
      ],
    );
    expect(targets.first['installed'], isFalse);
    expect(targets[3]['dir'], '$code/openspec/schemas');
  });

  test('kinds follow the installed version', () {
    expect(kindOf(null, '1.2.3'), 'fresh');
    expect(kindOf('1.2.3', '1.2.3'), 'reinstall');
    expect(kindOf('1.2.4', '1.2.3'), 'downgrade');
    expect(kindOf('1.2.3', '1.2.9'), 'patch');
    expect(kindOf('1.2.3', '1.3.0'), 'workflow');
    expect(kindOf('1.2.3', '2.0.0'), 'workflow');
    expect(workflowUpdate(null, '1.0.0'), isTrue);
    expect(workflowUpdate('1.0.1', '1.0.9'), isFalse);
  });

  test('a patch update skips the in-flight check; installed targets show as installed', () async {
    File('$code/openspec/.specwright/VERSION')
      ..createSync(recursive: true)
      ..writeAsStringSync('0.38.0\n');
    Directory('$code/.claude/skills/specwright-commit')
        .createSync(recursive: true);
    final doc = await plan(options());
    expect(doc['kind'], 'reinstall');
    expect(doc['inflight_checked'], isFalse);
    expect(
      [for (final t in doc['targets'] as List) (t as Map)['installed']],
      [true, false, false, false],
    );
  });

  test('refuses bad versions, a download with no skills, no targets and an unknown agent kind', () async {
    File('$code/openspec/.specwright/VERSION')
      ..createSync(recursive: true)
      ..writeAsStringSync('v1\n');
    File('$dl/VERSION').writeAsStringSync('abc');
    Directory('$dl/skills').deleteSync(recursive: true);
    final doc = await plan(options(skills: [], agents: ['nope=$code/x']));
    expect(codes(doc), [
      'installed_version_invalid',
      'download_version_invalid',
      'download_incomplete',
      'agent_kind',
    ]);
    expect(doc['ok'], isFalse);
    expect(doc['error'], 'refused');
    expect(
      (doc['refusals'] as List).first['message'],
      "openspec/.specwright/VERSION holds 'v1', not MAJOR.MINOR.PATCH",
    );
    expect(doc['message'], (doc['refusals'] as List).first['message']);
    final none = await plan(options(skills: [], agents: []));
    expect(codes(none), contains('no_targets'));
  });

  test('orphans: specwright directories and agent files the download no longer ships', () async {
    Directory('$code/.claude/skills/specwright-gone')
        .createSync(recursive: true);
    Directory('$code/.claude/skills/other').createSync(recursive: true);
    File('$code/.claude/agents/specwright-old.md')
      ..createSync(recursive: true)
      ..writeAsStringSync('x');
    final doc = await plan(options(agents: ['claude=$code/.claude/agents']));
    expect(doc['orphans'], [
      {
        'group': 'skills-1',
        'dir': '$code/.claude/skills',
        'name': 'specwright-gone',
      },
      {
        'group': 'agents-1-claude',
        'dir': '$code/.claude/agents',
        'name': 'specwright-old.md',
      },
    ]);
  });

  test('a journal: unreadable is refused and unchanged is false; a swapped one stays changed', () async {
    File('$code/openspec/.specwright/update.json')
      ..createSync(recursive: true)
      ..writeAsStringSync('nope');
    var doc = await plan(options());
    expect(codes(doc), ['journal_unreadable']);
    expect(
      doc['unchanged'],
      isTrue,
      reason: 'an unreadable journal is no proof of a started swap',
    );
    expect(doc['installed'], isNull);
    File('$code/openspec/.specwright/update.json').writeAsStringSync(
      '{"format": 2, "from": "0.37.0", "to": "0.38.0", "phase": "swapped"}\n',
    );
    doc = await plan(options());
    expect(doc['journal'], {
      'from': '0.37.0',
      'to': '0.38.0',
      'phase': 'swapped',
      'format': 2,
    });
    expect(doc['installed'], isNull);
    final state = jsonDecode(jsonEncode(doc)) as Map;
    expect(state['unchanged'], isFalse);
  });

  test(
    'a tag ref reports the sw asset of this host, or the unsupported platform',
    () async {
      var doc = await plan(
        options(ref: 'v0.38.0'),
        env: {'SPECWRIGHT_TEST_HOST': 'Linux/aarch64'},
      );
      expect(doc['sw'], {'asset': 'sw-linux-arm64', 'target': 'linux-arm64'});
      doc = await plan(
        options(ref: 'v0.38.0'),
        env: {'SPECWRIGHT_TEST_HOST': 'Windows/AMD64'},
      );
      expect(doc['sw'], {
        'asset': 'sw-windows-x64.exe',
        'target': 'windows-x64',
      });
      doc = await plan(
        options(ref: 'v0.38.0'),
        env: {'SPECWRIGHT_TEST_HOST': 'Plan9/mips'},
      );
      expect(doc['sw'], {'asset': null, 'reason': 'unsupported_platform'});
      doc = await plan(options(ref: 'main'));
      expect(doc.containsKey('sw'), isFalse);
    },
  );

  test(
    'a change in flight that fails the new schema refuses the update',
    () async {
      File('$code/openspec/changes/add-x/.openspec.yaml')
        ..createSync(recursive: true)
        ..writeAsStringSync('schema: specwright\n');
      final o = options();
      final doc = (await makePlan(
        o,
        check: true,
        ops: UpdateFileOps(environment: {}),
        run: (args, cwd, {timeout}) async => args.first == 'validate'
            ? const OpenspecResult(
                0,
                '{"items":[{"valid":false,"issues":[{"path":"p","message":"bad"}]}]}',
                '',
              )
            : const OpenspecResult(0, '{}', ''),
      )).doc;
      expect(codes(doc), ['change_invalid']);
      expect(
        doc['message'],
        'change add-x (working tree) fails validation against 0.38.0: openspec validate add-x: p: bad',
      );
      expect((doc['refusals'] as List).single['ref'], isNull);
    },
  );

  group('planning stores and worktrees', () {
    late String store;

    setUp(() {
      store = '${fwd(tmp.path)}/store';
      Directory(store).createSync(recursive: true);
      git(store, ['init', '-q', '-b', 'main']);
      File('$store/README').writeAsStringSync('x');
      git(store, ['add', '.']);
      git(store, ['commit', '-q', '-m', 'first']);
      git(code, ['remote', 'add', 'origin', 'https://github.com/me/proj.git']);
    });

    test('a store this project owns: role, store member, own staging suffix, no pack lines', () async {
      File('$store/openspec/.specwright/STORE')
        ..createSync(recursive: true)
        ..writeAsStringSync('version: 0.37.0\nowner: github.com/me/proj\n');
      final doc = await plan(options(root: store));
      expect(doc['role'], 'owner');
      expect(doc['store'], {
        'root': store,
        'version': '0.37.0',
        'owner': 'github.com/me/proj',
        'id': 'github.com/me/proj',
      });
      final withPack = await plan(options(root: store, packs: ['gamedev']));
      expect(codes(withPack), contains('packs_on_store'));
    });

    test("another project's store at another release is refused, naming the tag problem", () async {
      File('$store/openspec/.specwright/STORE')
        ..createSync(recursive: true)
        ..writeAsStringSync(
          'version: 0.37.0\nowner: github.com/someone/else\n',
        );
      final doc = await plan(options(root: store));
      expect(doc['role'], 'other');
      expect(codes(doc), ['store_version']);
      expect(
        doc['message'],
        "the store records version 0.37.0 and its schema is owned by github.com/someone/else, so this project's update to 0.38.0 "
        "would leave that version, and only the owner replaces the store's schema. Nothing was written. "
        'The highest 0.37 release could not be named (the download has no origin to list tags from): '
        'update this project to it instead, or have github.com/someone/else update the store first',
      );
      final groups = [
        for (final t in doc['targets'] as List) (t as Map)['group'],
      ];
      expect(groups, isNot(contains('schema')));
    });

    test('a root in another worktree of the code repo is refused', () async {
      final tree = '${fwd(tmp.path)}/wt';
      git(code, ['worktree', 'add', '-q', '-b', 'feat/wt', tree]);
      Directory('$tree/openspec').createSync();
      final doc = await plan(options(root: tree));
      expect(codes(doc), contains('root_other_worktree'));
      final message = (doc['refusals'] as List).firstWhere(
        (r) => (r as Map)['code'] == 'root_other_worktree',
      )['message'];
      expect(
        message,
        startsWith(
          '--root is in the worktree $tree, another worktree of the code repo\'s worktree $code; commits there',
        ),
      );
    });
  });

  test(
    'plan stops with settings_invalid before reading anything else',
    () async {
      File('$code/openspec/specwright.yaml')
        ..createSync(recursive: true)
        ..writeAsStringSync('review:\n  preship: yes\n');
      await expectLater(
        planDocument(options(), environment: const {}),
        throwsA(
          isA<UpdateStop>()
              .having((e) => e.code, 'code', 'settings_invalid')
              .having((e) => e.message, 'message', contains('line 2')),
        ),
      );
    },
  );

  test('a recovery seam adds its members to the plan document', () async {
    final (doc, status) = await planDocument(
      options(),
      environment: const {},
      run: passing,
      recover: (o) async => {
        'recovered': {'action': 'finished'},
      },
    );
    expect(status, 0, reason: '$doc');
    expect(doc['recovered'], {'action': 'finished'});
  });
}
