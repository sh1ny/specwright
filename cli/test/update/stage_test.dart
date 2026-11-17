import 'dart:convert';
import 'dart:io';

import 'package:specwright_cli/src/update/file_ops.dart';
import 'package:test/test.dart';

import 'lifecycle_support.dart';

/// Damages the staged copy of one file right after it is copied, as a faulty
/// disk or a race with the download would.
class _TamperOps extends UpdateFileOps {
  _TamperOps() : super(environment: const {});

  @override
  void copy(String source, String destDir) {
    super.copy(source, destDir);
    final victim = '$destDir/specwright-beta/SKILL.md';
    if (File(victim).existsSync()) {
      File(victim).writeAsStringSync('tampered\n', mode: FileMode.append);
    }
  }
}

void main() {
  late Directory tmp;
  late Layout co;
  late String dl;

  setUp(() {
    tmp = Directory.systemTemp.createTempSync('sw-update-stage-');
    co = Layout(tmp)..init(version: '0.5.0');
    dl = makeDownload('${fwd(tmp.path)}/dl-new', '0.6.0');
  });
  tearDown(() => tmp.deleteSync(recursive: true));

  Future<(int, Map<String, Object?>)> stage({
    UpdateFileOps? ops,
    Map<String, String>? env,
  }) => update(
    [...co.args(dl), 'stage'],
    ops: ops,
    env: env,
    openspec: passingOpenspec,
  );

  test('stages every target beside its target and leaves the installed files '
      'as they are', () async {
    final before = co.installed();
    final (code, doc) = await stage();
    expect(code, 0, reason: '$doc');
    expect(doc['ok'], isTrue);
    expect(doc['subcommand'], 'stage');
    expect(doc['state'], 'staged');
    expect(
      [doc['from'], doc['to'], doc['kind']],
      ['0.5.0', '0.6.0', 'workflow'],
    );
    expect(doc['installed'], '0.5.0');
    expect(doc['unchanged'], isTrue);
    expect(co.installed(), before);

    expect(co.stagingDirs(), [
      '.claude/.specwright-update-agents',
      '.claude/.specwright-update-skills',
      'openspec/.specwright-update-record',
      'openspec/.specwright-update-schemas',
    ]);
    for (final name in ['specwright-alpha', 'specwright-beta']) {
      expect(
        textSnapshot('${co.code}/.claude/.specwright-update-skills/new/$name'),
        textSnapshot('$dl/skills/$name'),
      );
    }
    expect(
      File(
        '${co.code}/.claude/.specwright-update-agents/new/specwright-impl.md',
      ).readAsStringSync(),
      File('$dl/agents/claude/specwright-impl.md').readAsStringSync(),
    );
    expect(
      textSnapshot(
        '${co.code}/openspec/.specwright-update-schemas/new/specwright',
      ),
      textSnapshot('$dl/schemas/specwright'),
    );
    expect(
      File('${co.code}/openspec/.specwright-update-record/new/packs.json')
          .existsSync(),
      isTrue,
    );
    expect(Directory(co.lock).existsSync(), isFalse);

    final groups = (doc['groups'] as List).cast<Map<String, Object?>>();
    expect(
      [for (final g in groups) g['id']],
      ['skills-1', 'agents-1-claude', 'schema', 'record'],
    );
    expect([for (final g in groups) g['targets']], [2, 1, 1, 1]);
    expect(doc['files'], 6);
  });

  test('writes the format-2 journal as update.sh lays it out', () async {
    await stage();
    final text = File(co.journal).readAsStringSync();
    final lines = text.split('\n');
    expect(lines.first, '{');
    expect(lines[1], '  "format": 2,');
    expect(lines.last, '');
    expect(lines[lines.length - 2], '}');
    // the scalar members, then one group, target and manifest entry per line
    expect(
      lines
          .where((l) => RegExp(r'^  "[a-z_]+": ').hasMatch(l))
          .map((l) => l.split('"')[1]),
      [
        'format',
        'from',
        'to',
        'ref',
        'kind',
        'role',
        'code',
        'root',
        'inflight',
        'owner_id',
        'store_owner',
        'store_version',
        'store_record',
        'store_lock',
        'store_staging',
        'store_state',
        'token',
        'prev_config',
        'prev_store',
        'config_sha',
        'prev_packs',
        'phase',
        'groups',
        'targets',
        'manifest',
      ],
    );
    expect(
      text,
      contains(
        '    {"gid": "skills-1", "name": "specwright-alpha", "type": "dir", '
        '"dir": "${co.skills}", '
        '"staging": "${co.code}/.claude/.specwright-update-skills", '
        '"installed": true, "state": "staged"},\n',
      ),
    );
    expect(
      text,
      contains(
        '    {"id": "agents-1-claude", "kind": "agents", '
        '"dir": "${co.agents}", '
        '"staging": "${co.code}/.claude/.specwright-update-agents", '
        '"agent_kind": "claude"},\n',
      ),
    );
    final journal = readJournal(co.journal);
    expect(journal['format'], 2);
    expect([journal['from'], journal['to']], ['0.5.0', '0.6.0']);
    expect(journal['role'], 'none');
    expect(journal['phase'], 'staged');
    expect(journal['store_state'], 'none');
    expect(journal['prev_packs'], <Object?>[]);
    final targets = (journal['targets'] as List).cast<Map<String, Object?>>();
    expect(targets, isNotEmpty);
    expect(targets.every((t) => t['state'] == 'staged'), isTrue);
  });

  test(
    'the manifest holds the SHA-256 of every staged file, in group order',
    () async {
      await stage();
      final manifest = (readJournal(co.journal)['manifest'] as List)
          .cast<Map<String, Object?>>();
      expect(
        [for (final m in manifest) '${m['group']}:${m['path']}'],
        [
          'skills-1:specwright-alpha/SKILL.md',
          'skills-1:specwright-alpha/scripts/run.sh',
          'skills-1:specwright-beta/SKILL.md',
          'agents-1-claude:specwright-impl.md',
          'schema:specwright/schema.yaml',
          'record:packs.json',
        ],
      );
      expect(
        manifest[0]['sha256'],
        sha(File('$dl/skills/specwright-alpha/SKILL.md').readAsBytesSync()),
      );
      expect(
        manifest[4]['sha256'],
        sha(File('$dl/schemas/specwright/schema.yaml').readAsBytesSync()),
      );
      expect(
        manifest.every(
          (m) => RegExp(r'^[0-9a-f]{64}$').hasMatch('${m['sha256']}'),
        ),
        isTrue,
      );
      // the record is hashed from the bytes stage wrote
      expect(
        manifest[5]['sha256'],
        sha(
          File('${co.code}/openspec/.specwright-update-record/new/packs.json')
              .readAsBytesSync(),
        ),
      );
    },
  );

  test('an agent file carries the installed model line into the staged copy '
      'and the manifest', () async {
    final installed = File('${co.agents}/specwright-impl.md');
    installed.writeAsStringSync(
      installed.readAsStringSync().replaceFirst('model: sonnet', 'model: opus'),
    );
    await stage();
    final staged = File(
      '${co.code}/.claude/.specwright-update-agents/new/specwright-impl.md',
    );
    expect(staged.readAsStringSync(), contains('model: opus'));
    expect(staged.readAsStringSync(), contains('body 0.6.0'));
    final manifest = (readJournal(co.journal)['manifest'] as List)
        .cast<Map<String, Object?>>();
    final entry = manifest.firstWhere((m) => m['group'] == 'agents-1-claude');
    expect(entry['sha256'], sha(staged.readAsBytesSync()));
  });

  test('a staged script keeps its executable bit', () async {
    await stage();
    final staged = File(
      '${co.code}/.claude/.specwright-update-skills/new/specwright-alpha/'
      'scripts/run.sh',
    );
    expect(staged.statSync().mode & 0x40, isNot(0));
  }, skip: Platform.isWindows ? 'POSIX mode bits' : false);

  test(
    'a staged copy that differs from the manifest stops verification_failed '
    'with staging and journal removed and no installed file changed',
    () async {
      final before = textSnapshot(co.code);
      final (code, doc) = await stage(ops: _TamperOps());
      expect(code, 1, reason: '$doc');
      expect(doc['ok'], isFalse);
      expect(doc['error'], 'verification_failed');
      expect(
        doc['message'],
        'the staged copy differs from the download: '
        'specwright-beta/SKILL.md (changed)',
      );
      final mismatches = (doc['mismatches'] as List)
          .cast<Map<String, Object?>>();
      expect(mismatches.single['group'], 'skills-1');
      expect(mismatches.single['path'], 'specwright-beta/SKILL.md');
      expect(mismatches.single['problem'], 'changed');
      expect(doc['unchanged'], isTrue);
      expect(doc['installed'], '0.5.0');
      expect(co.stagingDirs(), isEmpty);
      expect(File(co.journal).existsSync(), isFalse);
      expect(Directory(co.lock).existsSync(), isFalse);
      expect(textSnapshot(co.code), before);
    },
  );

  test(
    'a file staged that the manifest does not list is a mismatch too',
    () async {
      final ops = _ExtraFileOps();
      final (code, doc) = await stage(ops: ops);
      expect(code, 1, reason: '$doc');
      expect(doc['error'], 'verification_failed');
      final mismatches = (doc['mismatches'] as List)
          .cast<Map<String, Object?>>();
      expect(mismatches.single['problem'], 'unexpected');
      expect(mismatches.single['path'], 'specwright-alpha/stray.txt');
      expect(co.stagingDirs(), isEmpty);
      expect(File(co.journal).existsSync(), isFalse);
    },
  );

  test(
    'stage refuses while a journal is pending and leaves it as it is',
    () async {
      final (first, _) = await stage();
      expect(first, 0);
      final journal = File(co.journal).readAsStringSync();
      final staging = co.stagingDirs();
      final (code, doc) = await stage();
      expect(code, 1, reason: '$doc');
      expect(doc['error'], 'journal_pending');
      expect(
        doc['message'],
        'an unfinished update to 0.6.0 is recorded in ${co.journal}; run '
        'recover first',
      );
      expect(File(co.journal).readAsStringSync(), journal);
      expect(co.stagingDirs(), staging);
      expect(Directory(co.lock).existsSync(), isFalse);
    },
  );

  test(
    'a journal that does not parse stops stage as journal_unreadable',
    () async {
      put(co.state, 'update.json', '{"format": 9}\n');
      final before = textSnapshot(co.code);
      final (code, doc) = await stage();
      // plan refuses first, exactly as for plan
      expect(code, 1, reason: '$doc');
      expect([
        for (final r in doc['refusals'] as List) (r as Map)['code'],
      ], contains('journal_unreadable'));
      expect(textSnapshot(co.code), before);
    },
  );

  test(
    'a refused plan is the answer: nothing is written, not even the lock',
    () async {
      Directory('$dl/skills').deleteSync(recursive: true);
      final before = textSnapshot(co.code);
      final (code, doc) = await stage();
      expect(code, 1, reason: '$doc');
      expect(doc['error'], 'refused');
      expect(
        [for (final r in doc['refusals'] as List) (r as Map)['code']],
        ['download_incomplete'],
      );
      expect(textSnapshot(co.code), before);
    },
  );

  test('leftovers of an earlier run go: scratch, a temporary journal, old '
      'staging', () async {
    put(dl, '.update-scratch/x/y', 'scratch\n');
    put(co.state, 'update.json.tmp', '{');
    put(co.code, '.claude/.specwright-update-skills/old/junk', 'old\n');
    final (code, doc) = await stage();
    expect(code, 0, reason: '$doc');
    expect(Directory('$dl/.update-scratch').existsSync(), isFalse);
    expect(File('${co.state}/update.json.tmp').existsSync(), isFalse);
    expect(
      File('${co.code}/.claude/.specwright-update-skills/old/junk')
          .existsSync(),
      isFalse,
    );
    expect(File(co.journal).existsSync(), isTrue);
  });

  test('every file operation is counted, and a kill leaves the journal in '
      'phase staging with the installed files as they were', () async {
    final count = '${fwd(tmp.path)}/count.log';
    final ops = KillableOps(count);
    final (code, doc) = await stage(ops: ops);
    expect(code, 0, reason: '$doc');
    final log = countLog(count);
    final ops0 = [for (final l in log) l.split(' ').skip(1).take(2).join(' ')];
    expect(ops0.where((o) => o.startsWith('mkdir ')).length, greaterThan(0));
    expect(ops0.where((o) => o == 'cp -R').length, 3);
    expect(ops0.where((o) => o.startsWith('cp ')).length, 4);
    expect(ops0.where((o) => o.startsWith('mv ')).length, 3);
    expect(
      log.where((l) => l.contains('mv ${co.journal}.tmp ${co.journal}')).length,
      3,
      reason: 'the journal is written three times: new, targets, phase',
    );
    expect(log.last, contains('rm -rf ${co.lock}'));
    expect(log[log.length - 2], contains('mv ${co.journal}.tmp ${co.journal}'));

    // a fresh run, killed at the first copy
    Directory(co.code).deleteSync(recursive: true);
    co.init(version: '0.5.0');
    final before = co.installed();
    final count2 = '${fwd(tmp.path)}/count2.log';
    final firstCp = log.indexWhere((l) => l.contains(' cp ')) + 1;
    final killed = await runKilled(
      [...co.args(dl), 'stage'],
      count2,
      firstCp,
      openspec: passingOpenspec,
    );
    expect(killed, isTrue);
    expect(readJournal(co.journal)['phase'], 'staging');
    expect(co.installed(), before);
    expect(co.stagingDirs(), isNotEmpty);
  });

  test('the staged journal text is valid JSON of one object', () async {
    await stage();
    expect(
      jsonDecode(File(co.journal).readAsStringSync()),
      isA<Map<String, Object?>>(),
    );
  });
}

/// Puts a file into the staged copy that the download does not have.
class _ExtraFileOps extends UpdateFileOps {
  _ExtraFileOps() : super(environment: const {});

  @override
  void copy(String source, String destDir) {
    super.copy(source, destDir);
    final dir = '$destDir/specwright-alpha';
    if (Directory(dir).existsSync()) {
      File('$dir/stray.txt').writeAsStringSync('stray\n');
    }
  }
}
