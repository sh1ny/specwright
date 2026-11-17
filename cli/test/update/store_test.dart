import 'dart:io';

import 'package:specwright_cli/src/update/options.dart';
import 'package:specwright_cli/src/update/repo.dart';
import 'package:specwright_cli/src/update/settings.dart';
import 'package:specwright_cli/src/update/store.dart';
import 'package:specwright_cli/src/update/store_gate.dart';
import 'package:specwright_cli/src/update/file_ops.dart';
import 'package:specwright_cli/src/update/stop.dart';
import 'package:test/test.dart';

import '../helper_support.dart';

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

String fwd(String path) => path.replaceAll(r'\', '/');

void main() {
  late Directory tmp;

  setUp(() => tmp = Directory.systemTemp.createTempSync('sw-update-store-'));
  tearDown(() => tmp.deleteSync(recursive: true));

  String repo(String name, {String? origin}) {
    final dir = '${fwd(tmp.path)}/$name';
    Directory(dir).createSync(recursive: true);
    git(dir, ['init', '-q', '-b', 'main']);
    File('$dir/a.txt').writeAsStringSync('a\n');
    git(dir, ['add', '.']);
    git(dir, ['commit', '-q', '-m', 'first']);
    if (origin != null) git(dir, ['remote', 'add', 'origin', origin]);
    return dir;
  }

  group('store record', () {
    test('an absent file is no record and no problem', () {
      final read = readStoreRecord('${tmp.path}/none');
      expect(read.record, isNull);
      expect(read.problem, isNull);
    });

    test('reads version and owner; names what is missing or malformed', () {
      final path = '${fwd(tmp.path)}/STORE';
      File(path).writeAsStringSync('version: 0.37.1\nowner: h/o/r\n');
      final ok = readStoreRecord(path);
      expect(ok.record!.version, '0.37.1');
      expect(ok.record!.owner, 'h/o/r');
      File(path).writeAsStringSync('version: 0.37.1\n');
      expect(readStoreRecord(path).problem, '$path has no owner');
      File(path).writeAsStringSync('hello\n');
      expect(
        readStoreRecord(path).problem,
        '$path has no version and no owner',
      );
      File(path).writeAsStringSync('version: 0.37\nowner: a\n');
      expect(
        readStoreRecord(path).problem,
        "$path has the version '0.37', not MAJOR.MINOR.PATCH (field version)",
      );
    });

    test('compares versions numerically', () {
      expect(
        compareVersions(versionTuple('0.9.0'), versionTuple('0.10.0')),
        -1,
      );
      expect(compareVersions(versionTuple('1.0.0'), versionTuple('1.0.0')), 0);
    });
  });

  group('store roles', () {
    test('none for a repo-local planning root', () async {
      final code = repo('code');
      final repoState = UpdateRepo(
        code: code,
        root: code,
        settings: loadUpdateSettings(code),
      );
      expect((await storeInfo(repoState)).role, 'none');
    });

    test('claim, owner and other by the STORE record', () async {
      final code = repo('code', origin: 'https://github.com/me/proj.git');
      final store = repo('store');
      final r = UpdateRepo(
        code: code,
        root: store,
        settings: loadUpdateSettings(code),
      );
      expect((await storeInfo(r)).role, 'claim');
      File('$store/openspec/.specwright/STORE')
        ..createSync(recursive: true)
        ..writeAsStringSync('version: 0.37.0\nowner: github.com/me/proj\n');
      final owner = await storeInfo(
        UpdateRepo(code: code, root: store, settings: loadUpdateSettings(code)),
      );
      expect(owner.role, 'owner');
      expect(owner.id, 'github.com/me/proj');
      File(
        '$store/openspec/.specwright/STORE',
      ).writeAsStringSync('version: 0.37.0\nowner: github.com/someone/else\n');
      final other = await storeInfo(
        UpdateRepo(code: code, root: store, settings: loadUpdateSettings(code)),
      );
      expect(other.role, 'other');
      expect(other.record!.owner, 'github.com/someone/else');
      File('$store/openspec/.specwright/STORE').writeAsStringSync('junk\n');
      final bad = await storeInfo(
        UpdateRepo(code: code, root: store, settings: loadUpdateSettings(code)),
      );
      expect(bad.role, isNull);
      expect(bad.problem, contains('has no version and no owner'));
    });

    test('origin URLs become host/owner/repo', () {
      expect(normaliseOrigin('git@github.com:a/b.git'), 'github.com/a/b');
      expect(
        normaliseOrigin('https://u@Host.com:8080/a/b.git/'),
        'Host.com/a/b',
      );
      expect(normaliseOrigin('/local/path'), isNull);
    });
  });

  group('store gate lock', () {
    test('names the holder, and an earlier swap of this checkout', () {
      final gate = '${fwd(tmp.path)}/specwright-gate.lock';
      final ops = UpdateFileOps(environment: {});
      gateAcquire(ops, gate, '/c');
      File('$gate/owner').writeAsStringSync(
        'time: T\nchange: specwright-update 0.36.0 -> 0.37.0\ncode: /c\ntoken: tok\n',
      );
      expect(gateInspect(gate, 'tok', '/c'), GateState.ours);
      expect(gateInspect(gate, 'zzz', '/c'), GateState.other);
      expect(gateInspect(gate, '', '/c'), GateState.other);
      expect(
        () => gateAcquire(ops, gate, '/c'),
        throwsA(
          isA<UpdateStop>()
              .having((e) => e.code, 'code', 'store_locked')
              .having(
                (e) => e.message,
                'message',
                contains('held by an earlier swap of this checkout'),
              ),
        ),
      );
      File('$gate/owner').writeAsStringSync('change: roadmap\n');
      expect(
        gateStopLocked(gate, '/c').message,
        contains('held by roadmap; another session is in its gate'),
      );
      expect(gateInspect('${gate}x', 't', '/c'), GateState.none);
    });

    test('an owner-less lock is unverified only while a token is known', () {
      final gate = Directory('${fwd(tmp.path)}/g')..createSync();
      expect(gateInspect(gate.path, 'tok', '/c'), GateState.unverified);
      expect(gateInspect(gate.path, '', '/c'), GateState.other);
    });
  });

  group('is the store free', () {
    test(
      'busy on another branch, on uncommitted changes; free otherwise',
      () async {
        final code = repo('code');
        final store = repo('store');
        final r = UpdateRepo(
          code: code,
          root: store,
          settings: loadUpdateSettings(code),
        );
        final options = UpdateOptions(
          subcommand: 'plan',
          code: code,
          root: store,
          download: code,
        );
        expect(
          (await storeBusyReason(options, r, store, (_) => false)).$1,
          isNull,
        );
        File('$store/openspec/x.md')
          ..createSync(recursive: true)
          ..writeAsStringSync('x');
        final dirty = await storeBusyReason(options, r, store, (_) => false);
        expect(dirty.$1, 'the store has uncommitted changes: openspec/x.md');
        expect(
          (await storeBusyReason(
            options,
            r,
            store,
            (p) => p == 'openspec/x.md',
          )).$1,
          isNull,
        );
        File('$store/openspec/x.md').deleteSync();
        git(store, ['checkout', '-q', '-b', 'feat/x']);
        expect(
          (await storeBusyReason(options, r, store, (_) => false)).$1,
          'the store is on feat/x, not on its main (main)',
        );
      },
    );

    test(
      'another checkout staging is named ahead of the generic reason',
      () async {
        final code = repo('code');
        final store = repo('store');
        File('$store/openspec/.specwright-update-schemas-abc/specwright/s.yaml')
          ..createSync(recursive: true)
          ..writeAsStringSync('x');
        final r = UpdateRepo(
          code: code,
          root: store,
          settings: loadUpdateSettings(code),
        );
        final options = UpdateOptions(
          subcommand: 'plan',
          code: code,
          root: store,
          download: code,
        );
        expect(
          (await storeBusyReason(options, r, store, (_) => false)).$1,
          "another checkout's update is staged in the store: "
          'openspec/.specwright-update-schemas-abc; finish or recover it by '
          'rerunning the update in that checkout',
        );
      },
    );
  });

  group('a jj store is read in process', () {
    final jjFound =
        Process.runSync('jj', ['--version'], runInShell: true).exitCode == 0;

    test('names the change bookmark at @-, and is free on main', () async {
      final code = repo('code');
      final store = repo('store');
      File('$code/openspec/specwright.yaml')
        ..createSync(recursive: true)
        ..writeAsStringSync('planning_store:\n  vcs: jj\n');
      final env = {'JJ_USER': 'T', 'JJ_EMAIL': 't@example.com'};
      void jj(List<String> args) {
        final r = Process.runSync(
          'jj',
          args,
          workingDirectory: store,
          environment: env,
          runInShell: true,
        );
        expect(r.exitCode, 0, reason: '${r.stdout}${r.stderr}');
      }

      jj(['git', 'init', '--colocate']);
      jj(['new', 'root()']);
      jj(['new', 'main']);
      final r = UpdateRepo(
        code: code,
        root: store,
        settings: loadUpdateSettings(code),
      );
      expect(r.settings.storeIsJj, isTrue);
      final options = UpdateOptions(
        subcommand: 'plan',
        code: code,
        root: store,
        download: code,
      );
      final free = await storeBusyReason(
        options,
        r,
        store,
        (p) => p.startsWith('.jj'),
      );
      expect(free.$1, isNull, reason: '${free.$1}');
      expect(free.$2, 'main');
      jj(['bookmark', 'create', 'feat/busy', '-r', '@-']);
      final busy = await storeBusyReason(options, r, store, (p) => true);
      expect(busy.$1, 'the store is on feat/busy, not on its main (main)');
    }, skip: jjFound ? false : 'jj is not installed');
  });

  group('tag lookup (git ls-remote --tags, bounded)', () {
    late List<String> helper;
    late Directory built;

    setUpAll(() async {
      built = Directory.systemTemp.createTempSync('sw-update-tags-helper-');
      helper = await buildHelper(built);
    });
    tearDownAll(() => built.deleteSync(recursive: true));

    String origin() {
      final dir = repo('origin');
      for (final t in [
        'v0.36.0',
        'v0.37.0',
        'v0.37.2',
        'v0.37.10',
        'v0.38.0',
        'nottag',
      ]) {
        git(dir, ['tag', t]);
      }
      return dir;
    }

    UpdateOptions download(String originUrl) {
      final dl = repo('dl', origin: originUrl);
      return UpdateOptions(
        subcommand: 'plan',
        code: dl,
        root: dl,
        download: dl,
      );
    }

    test('names the highest patch of the recorded major.minor', () async {
      final found = await highestTag(
        download(origin()),
        0,
        37,
        helperCommand: helper,
      );
      expect(found.tag, 'v0.37.10');
      expect(found.problem, isNull);
    });

    test('says so when no tag of that release exists', () async {
      final found = await highestTag(
        download(origin()),
        0,
        5,
        helperCommand: helper,
      );
      expect(found.tag, isNull);
      expect(found.problem, 'no tag v0.5.* exists');
    });

    test('a download with no origin has nothing to list', () async {
      final dl = repo('plain');
      final found = await highestTag(
        UpdateOptions(subcommand: 'plan', code: dl, root: dl, download: dl),
        0,
        37,
        helperCommand: helper,
      );
      expect(found.problem, 'the download has no origin to list tags from');
    });

    test('a failing git names the first stderr line', () async {
      final found = await highestTag(
        download('${fwd(tmp.path)}/missing'),
        0,
        37,
        helperCommand: helper,
      );
      expect(found.tag, isNull);
      expect(found.problem, startsWith('git ls-remote --tags failed: '));
    });

    test('a response over the size limit stops it, naming the limit', () async {
      final found = await highestTag(
        download(origin()),
        0,
        37,
        environment: {
          ...Platform.environment,
          'SPECWRIGHT_NET_MAX_BYTES': '10',
        },
        helperCommand: helper,
      );
      expect(found.tag, isNull);
      expect(found.problem, 'response_too_large: git ls-remote --tags');
    });

    test(
      'a lookup past its deadline stops the tree, naming the limit',
      () async {
        final started = DateTime.now();
        final found = await highestTag(
          download('ssh://example.invalid/repo'),
          0,
          37,
          environment: {
            ...Platform.environment,
            'SPECWRIGHT_NET_DEADLINE': '1',
            'GIT_SSH_COMMAND': 'sleep 30 #',
          },
          helperCommand: helper,
        );
        expect(found.tag, isNull);
        expect(found.problem, 'deadline_exceeded: git ls-remote --tags');
        expect(
          DateTime.now().difference(started),
          lessThan(const Duration(seconds: 20)),
        );
      },
    );
  });
}
