import 'dart:convert';
import 'dart:io';

import 'package:specwright_cli/src/update/file_ops.dart';
import 'package:test/test.dart';

import 'lifecycle_support.dart';

void main() {
  late Directory tmp;
  late Layout co;
  late String dl;
  final backups = <String, String>{};

  setUp(() {
    backups.clear();
    tmp = Directory.systemTemp.createTempSync('sw-update-swap-');
    co = Layout(tmp)..init(version: '0.5.0');
    dl = makeDownload('${fwd(tmp.path)}/dl-new', '0.6.0');
  });
  tearDown(() => tmp.deleteSync(recursive: true));

  Future<(int, Map<String, Object?>)> sub(
    String name, {
    List<String> more = const [],
    UpdateFileOps? ops,
    String? download,
  }) => update(
    [...co.args(download ?? dl, more: more), name],
    ops: ops,
    openspec: passingOpenspec,
  );

  Future<Map<String, Object?>> ok(
    String name, {
    List<String> more = const [],
  }) async {
    final (code, doc) = await sub(name, more: more);
    expect(code, 0, reason: '$doc');
    return doc;
  }

  Future<Map<String, Object?>> stop(
    String name,
    String error, {
    List<String> more = const [],
  }) async {
    final (code, doc) = await sub(name, more: more);
    expect(code, 1, reason: '$doc');
    expect(doc['ok'], isFalse);
    expect(doc['error'], error, reason: '$doc');
    return doc;
  }

  void stamp(String version) => File(co.versionFile).writeAsStringSync(
    '$version\n',
  );

  /// The disk after the download is installed (what a finished swap gives).
  Future<Map<String, Object?>> installedAfterSwap() async {
    await ok('stage');
    await ok('swap');
    return co.installed();
  }

  void backup(List<String> dirs) {
    for (final d in dirs) {
      final to = '${fwd(tmp.path)}/bak-${backups.length}';
      copyTree(d, to);
      backups[d] = to;
    }
  }

  void restore() {
    for (final e in backups.entries) {
      Directory(e.key).deleteSync(recursive: true);
      copyTree(e.value, e.key);
    }
  }

  /// A killed process leaves its lock behind; nobody holds it any more.
  void forgetKilledProcess() {
    if (Directory(co.lock).existsSync()) {
      Directory(co.lock).deleteSync(recursive: true);
    }
  }

  group('swap', () {
    test('swaps every staged copy in and records phase swapped', () async {
      final before = co.installed();
      await ok('stage');
      final doc = await ok('swap');
      expect(doc['subcommand'], 'swap');
      expect(doc['state'], 'swapped');
      expect([doc['from'], doc['to']], ['0.5.0', '0.6.0']);
      expect(doc['store_written'], isFalse);
      expect(
        doc['restart'],
        'Agent sessions started before this update still run 0.5.0; restart '
        'them before they continue a change on 0.6.0.',
      );
      final after = co.installed();
      expect(after, isNot(before));
      expect(
        textSnapshot('${co.skills}/specwright-alpha'),
        textSnapshot('$dl/skills/specwright-alpha'),
      );
      expect(
        File('${co.agents}/specwright-impl.md').readAsStringSync(),
        File('$dl/agents/claude/specwright-impl.md').readAsStringSync(),
      );
      // the stamp is the prompt's, not swap's
      expect(File(co.versionFile).readAsStringSync(), '0.5.0\n');
      final journal = readJournal(co.journal);
      expect(journal['phase'], 'swapped');
      expect(
        (journal['targets'] as List).every((t) => (t as Map)['state'] == 'swapped'),
        isTrue,
      );
      expect(Directory(co.lock).existsSync(), isFalse);
    });

    test('no journal, an unstaged journal and a started swap stop', () async {
      await stop('swap', 'no_journal');
      await ok('stage');
      final text = File(co.journal).readAsStringSync();
      File(co.journal).writeAsStringSync(
        text.replaceFirst('"phase": "staged"', '"phase": "staging"'),
      );
      expect((await stop('swap', 'not_staged'))['message'], contains("phase 'staging'"));
      File(co.journal).writeAsStringSync(
        text.replaceFirst('"phase": "staged"', '"phase": "swapping"'),
      );
      expect(
        (await stop('swap', 'swap_interrupted'))['message'],
        'this update\'s swap was started (phase swapping); run recover from '
        'this checkout to finish or undo it',
      );
    });

    test('a staged copy that changed since stage is refused before any rename, '
        'with staging and journal removed', () async {
      final before = co.installed();
      await ok('stage');
      File(
        '${co.code}/.claude/.specwright-update-skills/new/specwright-beta/SKILL.md',
      ).writeAsStringSync('tampered\n');
      final doc = await stop('swap', 'verification_failed');
      expect(doc['mismatches'], isNotEmpty);
      expect(co.installed(), before);
      expect(File(co.journal).existsSync(), isFalse);
      expect(co.stagingDirs(), isEmpty);
    });

    test('changes in flight that differ from the plan refuse the swap', () async {
      await ok('stage');
      final journal = File(co.journal).readAsStringSync();
      // the plan recorded a checked set; a change that is now missing differs
      File(co.journal).writeAsStringSync(
        journal.replaceFirst(
          RegExp(r'"inflight": \{[^\n]*\},'),
          '"inflight": {"checked": true, "changes": [{"name": "gone", '
          '"source": "working tree", "status": "validated", '
          '"validated_against": "0.6.0"}], "warnings": []},',
        ),
      );
      final before = co.installed();
      final doc = await stop('swap', 'inflight_changed');
      expect(doc['differences'], [
        'gone (working tree) was in flight when the update was planned and is '
            'not now',
      ]);
      expect(co.installed(), before);
      expect(File(co.journal).existsSync(), isFalse);
    });

    test('every file operation is counted; the killed run leaves what recover '
        'decides from', () async {
      await ok('stage');
      final count = '${fwd(tmp.path)}/count.log';
      backup([co.code]);
      final full = await sub('swap', ops: KillableOps(count));
      expect(full.$1, 0);
      final log = countLog(count);
      final after = co.installed();
      final total = log.length;
      expect(total, greaterThan(10));
      expect(
        log.where((l) => l.contains(' mv ${co.journal}.tmp ${co.journal}')).length,
        greaterThan(4),
      );
      restore();
      final before = co.installed();
      var resumed = 0, discarded = 0;
      for (var n = 1; n <= total; n++) {
        final killed = await runKilled(
          [...co.args(dl), 'swap'],
          '${fwd(tmp.path)}/k$n.log',
          n,
          openspec: passingOpenspec,
        );
        expect(killed, isTrue, reason: 'op $n');
        forgetKilledProcess();
        final (code, doc) = await sub('recover');
        expect(code, 0, reason: 'op $n: $doc');
        final action = (doc['action'] as String);
        if (action == 'discarded') {
          discarded++;
          expect(co.installed(), before, reason: 'op $n');
        } else {
          resumed++;
          expect(action, 'resumed', reason: 'op $n: $doc');
          expect(co.installed(), after, reason: 'op $n');
          expect(readJournal(co.journal)['phase'], 'swapped');
        }
        expect(Directory(co.lock).existsSync(), isFalse);
        restore();
      }
      expect(resumed, greaterThan(0));
      expect(discarded, greaterThan(0));
      // One killed run and one recover per counted operation: about 25 s on
      // its own, so the default 30 s timeout is too tight under a parallel run.
    }, timeout: const Timeout(Duration(minutes: 5)));
  });

  group('note-config and finish', () {
    test('note-config records the merged config; before swap, or without a '
        'config, it stops', () async {
      await stop('note-config', 'no_journal');
      await ok('stage');
      expect(
        (await stop('note-config', 'not_swapped'))['message'],
        "the recorded update is in phase 'staged', not swapped; note-config "
        'runs after swap, right after Step 5',
      );
      await ok('swap');
      File(co.config).deleteSync();
      expect(
        (await stop('note-config', 'config_missing'))['message'],
        '${co.config} does not exist; run Step 5 first',
      );
      File(co.config).writeAsStringSync('schema: specwright\nmerged: 1\n');
      final doc = await ok('note-config');
      expect(doc['subcommand'], 'note-config');
      expect(doc['config'], co.config);
      expect(doc['sha256'], sha(File(co.config).readAsBytesSync()));
      expect(readJournal(co.journal)['config_sha'], doc['sha256']);
    });

    test('finish: nothing in progress, not stamped, not swapped, then done',
        () async {
      var doc = await ok('finish');
      expect(doc, {
        'ok': true,
        'interface': 3,
        'subcommand': 'finish',
        'state': 'done',
        'finished': false,
        'message': 'no update is in progress',
      });
      await ok('stage');
      expect(
        (await stop('finish', 'not_stamped'))['message'],
        "VERSION reads '0.5.0', not 0.6.0; finish runs after the stamp",
      );
      stamp('0.6.0');
      expect(
        (await stop('finish', 'not_swapped'))['message'],
        "the recorded update is in phase 'staged', not swapped; run recover "
        'first',
      );
      stamp('0.5.0');
      await ok('swap');
      stamp('0.6.0');
      doc = await ok('finish');
      expect(doc['state'], 'done');
      expect(doc['finished'], isTrue);
      expect(doc['subcommand'], 'finish');
      expect(File(co.journal).existsSync(), isFalse);
      expect(co.stagingDirs(), isEmpty);
    });
  });

  group('recover', () {
    test('nothing recorded', () async {
      final doc = await ok('recover');
      expect(doc, {
        'ok': true,
        'interface': 3,
        'subcommand': 'recover',
        'installed': '0.5.0',
        'action': 'none',
        'message': 'no unfinished update',
        'from': null,
        'to': null,
        'store_written': false,
        'sw_note': null,
      });
    });

    test('a staged update that never swapped is discarded', () async {
      final before = co.installed();
      await ok('stage');
      final doc = await ok('recover');
      expect(doc['action'], 'discarded');
      expect(doc['message'], 'discarded unfinished update to 0.6.0');
      expect([doc['from'], doc['to']], ['0.5.0', '0.6.0']);
      expect(co.installed(), before);
      expect(File(co.journal).existsSync(), isFalse);
      expect(co.stagingDirs(), isEmpty);
    });

    test('a swap killed halfway with a complete staged copy is resumed',
        () async {
      await ok('stage');
      backup([co.code]);
      final count = '${fwd(tmp.path)}/count.log';
      await sub('swap', ops: KillableOps(count));
      final after = co.installed();
      restore();
      final log = countLog(count);
      final firstMove = log.indexWhere(
        (l) => l.contains(' mv ${co.code}/.claude/.specwright-update-skills/new/'),
      );
      expect(firstMove, greaterThan(0));
      expect(
        await runKilled(
          [...co.args(dl), 'swap'],
          '${fwd(tmp.path)}/k.log',
          firstMove + 2,
          openspec: passingOpenspec,
        ),
        isTrue,
      );
      forgetKilledProcess();
      final doc = await ok('recover');
      expect(doc['action'], 'resumed');
      expect(doc['message'], 'resumed update to 0.6.0');
      expect(co.installed(), after);
      expect(readJournal(co.journal)['phase'], 'swapped');
    });

    test('a resumed update whose stamp nobody will write is stamped and '
        'finished', () async {
      await ok('stage');
      final count = '${fwd(tmp.path)}/count.log';
      backup([co.code]);
      await sub('swap', ops: KillableOps(count));
      restore();
      final log = countLog(count);
      final n = log.indexWhere((l) => l.contains(' mv ${co.code}/.claude/')) + 2;
      await runKilled(
        [...co.args(dl), 'swap'],
        '${fwd(tmp.path)}/k.log',
        n,
        openspec: passingOpenspec,
      );
      forgetKilledProcess();
      // a download that is not this update's own
      final other = makeDownload('${fwd(tmp.path)}/dl-other', '0.7.0');
      final (code, doc) = await sub('recover', download: other);
      expect(code, 0, reason: '$doc');
      expect(doc['action'], 'resumed');
      expect(File(co.versionFile).readAsStringSync(), '0.6.0\n');
      expect(File(co.journal).existsSync(), isFalse);
      expect(co.stagingDirs(), isEmpty);
    });

    test('a damaged staged copy is rolled back, not resumed', () async {
      final before = co.installed();
      await ok('stage');
      final count = '${fwd(tmp.path)}/count.log';
      backup([co.code]);
      await sub('swap', ops: KillableOps(count));
      restore();
      final log = countLog(count);
      final n = log.indexWhere((l) => l.contains(' mv ${co.code}/.claude/')) + 2;
      await runKilled(
        [...co.args(dl), 'swap'],
        '${fwd(tmp.path)}/k.log',
        n,
        openspec: passingOpenspec,
      );
      forgetKilledProcess();
      File(
        '${co.code}/openspec/.specwright-update-schemas/new/specwright/schema.yaml',
      ).writeAsStringSync('damaged\n');
      final doc = await ok('recover');
      expect(doc['action'], 'rolled-back');
      expect(doc['message'], 'rolled back to 0.5.0');
      expect(doc['sw_note'], isA<String>());
      expect(co.installed(), before);
      expect(File(co.journal).existsSync(), isFalse);
      expect(co.stagingDirs(), isEmpty);
    });

    test('--rollback undoes a finished swap that nobody stamped', () async {
      final before = co.installed();
      await installedAfterSwap();
      final doc = await ok('recover', more: ['--rollback']);
      expect(doc['action'], 'rolled-back');
      expect(doc['message'], 'rolled back to 0.5.0');
      expect(co.installed(), before);
      expect(File(co.journal).existsSync(), isFalse);
      expect(co.stagingDirs(), isEmpty);
    });

    test('a stamped update is finished; --rollback refuses it', () async {
      final after = await installedAfterSwap();
      stamp('0.6.0');
      final refused = await stop('recover', 'rollback_stamped', more: ['--rollback']);
      expect(
        refused['message'],
        'VERSION already reads 0.6.0: the update is complete and cannot be '
        'rolled back',
      );
      expect(File(co.journal).existsSync(), isTrue);
      final doc = await ok('recover');
      expect(doc['action'], 'finished');
      expect(doc['message'], 'finished update to 0.6.0');
      expect(doc['installed'], '0.6.0');
      expect(File(co.journal).existsSync(), isFalse);
      expect(co.stagingDirs(), isEmpty);
      expect(co.installed()['skills'], after['skills']);
    });

    test('a first install rolls back to the state before it', () async {
      Directory(co.code).deleteSync(recursive: true);
      co = Layout(tmp)..init();
      // the files (an install may leave the empty directories it made)
      Map<String, String?> files() => {
        for (final e in textSnapshot(co.code).entries)
          if (e.value != null && !e.key.startsWith('.git/')) e.key: e.value,
      };
      final before = files();
      await ok('stage');
      await ok('swap');
      final doc = await ok('recover', more: ['--rollback']);
      expect(doc['message'], 'rolled back to the state before the first install');
      expect(doc['from'], isNull);
      expect(doc['sw_note'], isNull);
      expect(files(), before);
    });
  });

  group('config rollback', () {
    test('the config as it was comes back', () async {
      final prev = File(co.config).readAsStringSync();
      await ok('stage');
      await ok('swap');
      File(co.config).writeAsStringSync('schema: specwright\nmerged: 1\n');
      await ok('note-config');
      final doc = await ok('recover', more: ['--rollback']);
      expect(doc['message'], 'rolled back to 0.5.0');
      expect(File(co.config).readAsStringSync(), prev);
    });

    test('a config edited after note-config is kept, and the message says so',
        () async {
      await ok('stage');
      await ok('swap');
      File(co.config).writeAsStringSync('merged: 1\n');
      await ok('note-config');
      File(co.config).writeAsStringSync('edited by hand\n');
      final doc = await ok('recover', more: ['--rollback']);
      expect(
        doc['message'],
        'rolled back to 0.5.0; config.yaml kept: it was edited after '
        'note-config',
      );
      expect(File(co.config).readAsStringSync(), 'edited by hand\n');
    });

    test('a config the update created is removed, unless it was edited',
        () async {
      Directory(co.code).deleteSync(recursive: true);
      co = Layout(tmp)..init();
      await ok('stage');
      await ok('swap');
      File(co.config).writeAsStringSync('schema: specwright\n');
      await ok('note-config');
      await ok('recover', more: ['--rollback']);
      expect(File(co.config).existsSync(), isFalse);

      await ok('stage');
      await ok('swap');
      File(co.config).writeAsStringSync('one\n');
      await ok('note-config');
      File(co.config).writeAsStringSync('two\n');
      final doc = await ok('recover', more: ['--rollback']);
      expect(doc['message'], contains('config.yaml kept'));
      expect(File(co.config).existsSync(), isTrue);
    });
  });

  group('a journal from 0.36.0 update.sh', () {
    /// Mid-swap: specwright-alpha is moved aside, its staged copy waits in
    /// new/, the laid-out text is what `update.sh format_journal` writes.
    String format2Journal() {
      final staging = '${co.code}/.claude/.specwright-update-skills';
      final entries = <String>[];
      for (final f in [
        'specwright-alpha/SKILL.md',
        'specwright-alpha/scripts/run.sh',
      ]) {
        final bytes = File('$dl/skills/$f').readAsBytesSync();
        entries.add(
          '    {"group": "skills-1", "path": "$f", "sha256": "${sha(bytes)}"}',
        );
      }
      return '''{
  "format": 2,
  "from": "0.5.0",
  "to": "0.6.0",
  "ref": null,
  "kind": "workflow",
  "role": "none",
  "code": "${co.code}",
  "root": "${co.root}",
  "inflight": {"checked": false, "changes": [], "warnings": []},
  "owner_id": "x",
  "store_owner": null,
  "store_version": null,
  "store_record": "${co.root}/openspec/.specwright/STORE",
  "store_lock": null,
  "store_staging": null,
  "store_state": "none",
  "token": null,
  "prev_config": "present",
  "prev_store": "absent",
  "config_sha": null,
  "prev_packs": ["gamedev"],
  "phase": "swapping",
  "groups": [
    {"id": "skills-1", "kind": "skills", "dir": "${co.skills}", "staging": "$staging"}
  ],
  "targets": [
    {"gid": "skills-1", "name": "specwright-alpha", "type": "dir", "dir": "${co.skills}", "staging": "$staging", "installed": true, "state": "old-moved"}
  ],
  "manifest": [
${entries.join(',\n')}
  ]
}
''';
    }

    void layOut() {
      final staging = '${co.code}/.claude/.specwright-update-skills';
      copyTree('$dl/skills/specwright-alpha', '$staging/new/specwright-alpha');
      Directory('$staging/old').createSync(recursive: true);
      Directory('${co.skills}/specwright-alpha')
          .renameSync('$staging/old/specwright-alpha');
      File(co.journal)
        ..createSync(recursive: true)
        ..writeAsStringSync(format2Journal());
    }

    test('recover resumes it', () async {
      layOut();
      final doc = await ok('recover');
      expect(doc['action'], 'resumed');
      expect(doc['message'], 'resumed update to 0.6.0');
      expect(
        textSnapshot('${co.skills}/specwright-alpha'),
        textSnapshot('$dl/skills/specwright-alpha'),
      );
      expect(readJournal(co.journal)['phase'], 'swapped');
      expect(readJournal(co.journal)['format'], 2);
    });

    test('plan recovers it first and says so', () async {
      layOut();
      final (code, doc) = await sub('plan');
      expect(code, isIn([0, 1]));
      final recovered = doc['recovered'] as Map<String, Object?>;
      expect(recovered['action'], 'resumed');
      expect(recovered['message'], 'resumed update to 0.6.0');
      expect(recovered['from'], '0.5.0');
      expect(recovered['to'], '0.6.0');
      expect(recovered['store_written'], isFalse);
      expect(recovered.containsKey('sw_note'), isTrue);
      expect(
        textSnapshot('${co.skills}/specwright-alpha'),
        textSnapshot('$dl/skills/specwright-alpha'),
      );
    });

    test('a recovery that finished the swap hands the packs enabled before it '
        'to plan', () async {
      layOut();
      // the stamp is written, the swap is done: recovery finishes it
      File('${co.skills}/specwright-beta/SKILL.md')
          .writeAsStringSync('beta 0.6.0\n');
      Directory('${co.code}/.claude/.specwright-update-skills/new/specwright-alpha')
          .deleteSync(recursive: true);
      copyTree(
        '$dl/skills/specwright-alpha',
        '${co.skills}/specwright-alpha',
      );
      File(co.journal).writeAsStringSync(
        File(co.journal)
            .readAsStringSync()
            .replaceFirst('"phase": "swapping"', '"phase": "swapped"')
            .replaceFirst('"state": "old-moved"', '"state": "swapped"'),
      );
      stamp('0.6.0');
      final (_, doc) = await sub('plan');
      final recovered = doc['recovered'] as Map<String, Object?>;
      expect(recovered['action'], 'finished');
      expect(doc['packs_previous'], ['gamedev']);
      expect(File(co.journal).existsSync(), isFalse);
    });

    test('a format it does not know is refused and nothing is touched',
        () async {
      layOut();
      final text = File(co.journal).readAsStringSync().replaceFirst(
        '"format": 2',
        '"format": 9',
      );
      File(co.journal).writeAsStringSync(text);
      final before = textSnapshot(co.code);
      final doc = await stop('recover', 'journal_unreadable');
      expect(doc['message'], 'update.json has format 9, not 1 or 2');
      expect(doc.containsKey('installed'), isFalse);
      expect(textSnapshot(co.code), before);

      final (code, plan) = await sub('plan');
      expect(code, 1);
      expect(plan.containsKey('recovered'), isFalse);
      expect(plan['unchanged'], isTrue);
      expect(
        (plan['refusals'] as List).map((r) => (r as Map)['code']),
        contains('journal_unreadable'),
      );
      expect(textSnapshot(co.code), before);
    });

    test('text after the journal is garbage: refused, nothing touched',
        () async {
      layOut();
      File(co.journal).writeAsStringSync(
        '${File(co.journal).readAsStringSync()}trailing\n',
      );
      final before = textSnapshot(co.code);
      await stop('recover', 'journal_unreadable');
      expect(textSnapshot(co.code), before);
    });
  });

  group('the store half', () {
    late String store;
    late String patch;

    String storeFile(String rel) => '$store/$rel';
    String record() => File(storeFile('openspec/.specwright/STORE'))
        .readAsStringSync();

    setUp(() {
      Directory(co.code).deleteSync(recursive: true);
      store = '${fwd(tmp.path)}/store';
      Directory(store).createSync(recursive: true);
      git(store, ['init', '-q', '-b', 'main']);
      put(store, 'README', 'x\n');
      co = Layout(tmp, root: store)..init(version: '0.5.0');
      git(co.code, [
        'remote',
        'add',
        'origin',
        'https://github.com/me/proj.git',
      ]);
      put(
        store,
        'openspec/.specwright/STORE',
        'version: 0.5.0\nowner: github.com/me/proj\n',
      );
      git(store, ['add', '-A']);
      git(store, ['commit', '-q', '-m', 'store']);
      patch = makeDownload('${fwd(tmp.path)}/dl-patch', '0.5.1');
      File('$patch/schemas/specwright/schema.yaml').writeAsStringSync(
        File('${fwd(tmp.path)}/dl-0.5.0/schemas/specwright/schema.yaml')
            .readAsStringSync(),
      );
    });

    test('an owner swap writes STORE and releases the gate lock', () async {
      final staged = await ok('stage');
      expect(staged['role'], 'owner');
      final lock = readJournal(co.journal)['store_lock'] as String;
      final doc = await ok('swap');
      expect(doc['store_written'], isTrue);
      final s = doc['store'] as Map<String, Object?>;
      expect(s['written'], isTrue);
      expect(s['claimed'], isFalse);
      expect(s['owner'], 'github.com/me/proj');
      expect(s['version'], '0.6.0');
      expect(s['uncommitted'], contains('openspec/.specwright/STORE'));
      expect(record(), 'version: 0.6.0\nowner: github.com/me/proj\n');
      expect(Directory(lock).existsSync(), isFalse);
      expect(readJournal(co.journal)['store_state'], 'written');
      expect(
        File(storeFile('openspec/schemas/specwright/schema.yaml'))
            .readAsStringSync(),
        contains('0.6.0'),
      );
    });

    test('a busy store refuses the swap with everything kept as it was',
        () async {
      await ok('stage');
      final lock = readJournal(co.journal)['store_lock'] as String;
      final before = co.installed();
      put(store, 'notes.txt', 'someone is working\n');
      final doc = await stop('swap', 'store_busy');
      expect(
        doc['message'],
        startsWith('the store has uncommitted changes: notes.txt. A store '
            'schema is swapped only on a free store'),
      );
      expect(co.installed(), before);
      expect(record(), 'version: 0.5.0\nowner: github.com/me/proj\n');
      expect(Directory(lock).existsSync(), isFalse);
      expect(File(co.journal).existsSync(), isFalse);
      expect(co.stagingDirs(), isEmpty);
    });

    test('a record another owner wrote since the plan stops the swap',
        () async {
      await ok('stage');
      File(storeFile('openspec/.specwright/STORE')).writeAsStringSync(
        'version: 0.5.0\nowner: github.com/someone/else\n',
      );
      final doc = await stop('swap', 'store_owner_changed');
      expect(
        doc['message'],
        "the store's schema is now owned by github.com/someone/else (version "
        '0.5.0), not by github.com/me/proj; nothing was written. Rerun the '
        'update to plan it again',
      );
      expect(File(co.journal).existsSync(), isFalse);
    });

    test('a held gate lock stops the swap naming the holder', () async {
      await ok('stage');
      final lock = readJournal(co.journal)['store_lock'] as String;
      Directory(lock).createSync(recursive: true);
      File('$lock/owner').writeAsStringSync(
        'time: 2026-01-01T00:00:00Z\nchange: add-thing\ncode: /elsewhere\n'
        'token: t\n',
      );
      final doc = await stop('swap', 'store_locked');
      expect(
        doc['message'],
        contains('is held by add-thing (from /elsewhere), taken '
            '2026-01-01T00:00:00Z; another session is in its gate or roadmap '
            'step for this store'),
      );
      expect(Directory(lock).existsSync(), isTrue);
    });

    test('a patch on a busy store swaps the code side only', () async {
      put(store, 'notes.txt', 'busy\n');
      final (code, staged) = await update(
        [...co.args(patch), 'stage'],
        openspec: passingOpenspec,
      );
      expect(code, 0, reason: '$staged');
      final (c2, doc) = await update(
        [...co.args(patch), 'swap'],
        openspec: passingOpenspec,
      );
      expect(c2, 0, reason: '$doc');
      expect(doc['store_written'], isFalse);
      expect((doc['store'] as Map)['message'], 'store schema already current');
      expect(record(), 'version: 0.5.0\nowner: github.com/me/proj\n');
      expect(
        File('${co.skills}/specwright-alpha/SKILL.md').readAsStringSync(),
        'alpha 0.5.1\n',
      );
      expect(readJournal(co.journal)['store_state'], 'current');
    });

    Future<List<String>> countedSwap() async {
      await ok('stage');
      backup([co.code, store]);
      final count = '${fwd(tmp.path)}/count.log';
      final (c, d) = await sub('swap', ops: KillableOps(count));
      expect(c, 0, reason: '$d');
      restore();
      return countLog(count);
    }

    test('a swap killed after the renames, before STORE, is resumed under the '
        'gate lock it still holds', () async {
      final log = await countedSwap();
      final n = log.indexWhere((l) => l.contains('STORE.new')) + 1;
      expect(n, greaterThan(0));
      final lock = readJournal(co.journal)['store_lock'] as String;
      expect(
        await runKilled(
          [...co.args(dl), 'swap'],
          '${fwd(tmp.path)}/k.log',
          n,
          openspec: passingOpenspec,
        ),
        isTrue,
      );
      forgetKilledProcess();
      expect(Directory(lock).existsSync(), isTrue);
      expect(record(), 'version: 0.5.0\nowner: github.com/me/proj\n');
      final doc = await ok('recover');
      expect(doc['action'], 'resumed');
      expect(doc['store_written'], isTrue);
      expect(record(), 'version: 0.6.0\nowner: github.com/me/proj\n');
      expect(Directory(lock).existsSync(), isFalse);
    });

    test('--rollback restores the store files and releases the gate lock',
        () async {
      await ok('stage');
      final beforeCode = co.installed();
      await ok('swap');
      final doc = await ok('recover', more: ['--rollback']);
      expect(doc['action'], 'rolled-back');
      expect(doc['message'], 'rolled back to 0.5.0');
      expect(record(), 'version: 0.5.0\nowner: github.com/me/proj\n');
      expect(co.installed(), beforeCode);
      expect(co.stagingDirs(), isEmpty);
      final status = Process.runSync('git', ['-C', store, 'status', '--porcelain']);
      expect('${status.stdout}'.trim(), isEmpty);
    });

    test('a foreign gate lock stops the rollback; the journal is kept',
        () async {
      await ok('stage');
      final lock = readJournal(co.journal)['store_lock'] as String;
      await ok('swap');
      Directory(lock).createSync(recursive: true);
      File('$lock/owner').writeAsStringSync(
        'time: 2026-01-01T00:00:00Z\nchange: add-thing\ncode: /elsewhere\n'
        'token: t\n',
      );
      await stop('recover', 'store_locked', more: ['--rollback']);
      expect(File(co.journal).existsSync(), isTrue);
    });

    test('a gate lock without owner information is not taken over', () async {
      await ok('stage');
      final lock = readJournal(co.journal)['store_lock'] as String;
      await ok('swap');
      Directory(lock).createSync(recursive: true);
      final doc = await stop('recover', 'gate_lock_unverified');
      expect(doc['message'], contains('has no owner information'));
      expect(File(co.journal).existsSync(), isTrue);
    });
  });

  test('the journal the commands write parses as one JSON object', () async {
    await ok('stage');
    await ok('swap');
    expect(jsonDecode(File(co.journal).readAsStringSync()), isA<Map<String, Object?>>());
  });
}
