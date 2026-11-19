import 'dart:io';

import 'package:specwright_cli/src/gate/lock.dart';
import 'package:test/test.dart';

// The store gate lock of `sw gate` (planning-stores "sw gate lock takes the
// store gate lock", "sw gate show reports the lock and changes nothing", "sw
// gate unlock releases only the lock it is given"). The lock directory is made
// by the code under test inside a temporary directory; no git, no process.

void main() {
  late Directory tmp;
  late String lock;

  setUp(() {
    tmp = Directory.systemTemp.createTempSync('gate-test-');
    lock = '${tmp.path}/specwright-gate.lock'.replaceAll(r'\', '/');
  });
  tearDown(() => tmp.deleteSync(recursive: true));

  group('gateLock', () {
    test('owner file is written by rename', () {
      late bool ownerBefore;
      late List<String> before;
      final (doc, status) = gateLock(
        lock,
        'add-x',
        '/code',
        beforeRename: () {
          // killed here: the lock exists, the owner file does not (never half)
          ownerBefore = File('$lock/owner').existsSync();
          before = [
            for (final e in Directory(lock).listSync())
              e.path.split(RegExp(r'[\\/]')).last,
          ];
        },
      );
      expect(status, 0);
      expect(doc['ok'], true);
      expect(ownerBefore, isFalse);
      expect(before, hasLength(1), reason: 'a finished temporary file waits');
      expect(File('$lock/owner').existsSync(), isTrue);
      expect(
        Directory(lock).listSync(),
        hasLength(1),
        reason: 'the temporary file is gone',
      );
    });

    test('a kill between mkdir and rename leaves a lock show reports with no owner', () {
      expect(
        () => gateLock(
          lock,
          'add-x',
          '/code',
          beforeRename: () => throw StateError('killed'),
        ),
        throwsStateError,
      );
      expect(File('$lock/owner').existsSync(), isFalse);
      final shown = gateShow(lock);
      expect(shown['held'], true);
      expect(shown['owner'], {
        'time': '',
        'change': '',
        'code': '',
        'token': '',
      });
    });

    test('writes time, change, code and a fresh token in the lines of earlier versions', () {
      final (doc, _) = gateLock(lock, 'add-x', '/code');
      final text = File('$lock/owner').readAsStringSync();
      final lines = text.split('\n');
      expect(
        lines[0],
        matches(RegExp(r'^time: \d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$')),
      );
      expect(lines[1], 'change: add-x');
      expect(lines[2], 'code: /code');
      expect(lines[3], 'token: ${doc['token']}');
      expect(lines[4], '');
      expect(doc['token'], isNotEmpty);
    });

    test('token generation: two locks get different tokens', () {
      expect(gateToken(), isNot(gateToken()));
      final (first, _) = gateLock(lock, 'a', '/c');
      gateUnlock(lock, token: first['token'] as String);
      final (second, _) = gateLock(lock, 'a', '/c');
      expect(second['token'], isNot(first['token']));
    });

    test('a held lock is gate_locked with its owner and changes nothing', () {
      Directory(lock).createSync();
      File('$lock/owner').writeAsStringSync(
        'time: 2026-01-01T00:00:00Z\nchange: add-y\ncode: /d\n',
      );
      final (doc, status) = gateLock(lock, 'add-x', '/code');
      expect(status, 1);
      expect(doc['ok'], false);
      expect(doc['error'], 'gate_locked');
      expect(doc['owner'], {
        'time': '2026-01-01T00:00:00Z',
        'change': 'add-y',
        'code': '/d',
        'token': '',
      });
      expect(
        File('$lock/owner').readAsStringSync(),
        'time: 2026-01-01T00:00:00Z\nchange: add-y\ncode: /d\n',
      );
      expect(Directory(lock).listSync(), hasLength(1));
    });
  });

  group('gateShow', () {
    test('reads all four lines', () {
      Directory(lock).createSync();
      File('$lock/owner').writeAsStringSync(
        'time: T\r\nchange: add-x\r\ncode: /c\r\ntoken: t1\r\n',
      );
      final before = File('$lock/owner').readAsStringSync();
      final shown = gateShow(lock);
      expect(shown['ok'], true);
      expect(shown['held'], true);
      expect(shown['owner'], {
        'time': 'T',
        'change': 'add-x',
        'code': '/c',
        'token': 't1',
      });
      expect(File('$lock/owner').readAsStringSync(), before);
    });

    test('no lock: held false, nothing created', () {
      final shown = gateShow(lock);
      expect(shown['held'], false);
      expect(shown.containsKey('owner'), false);
      expect(Directory(lock).existsSync(), false);
    });
  });

  group('gateUnlock', () {
    String taken(String branch) =>
        gateLock(lock, branch, '/c').$1['token'] as String;

    test('own token releases the lock', () {
      final t = taken('add-x');
      final (doc, status) = gateUnlock(lock, token: t);
      expect((status, doc['removed']), (0, true));
      expect(Directory(lock).existsSync(), false);
    });

    test('another token is gate_not_owner and removes nothing', () {
      final t1 = taken('add-x');
      gateUnlock(lock, token: t1);
      final t2 = taken('add-x');
      final (doc, status) = gateUnlock(lock, token: t1);
      expect(status, 1);
      expect(doc['error'], 'gate_not_owner');
      expect((doc['owner'] as Map)['token'], t2);
      expect(Directory(lock).existsSync(), true);
    });

    test('no lock: removed false, ok', () {
      final (doc, status) = gateUnlock(lock, token: 't1');
      expect((status, doc['ok'], doc['removed']), (0, true, false));
    });

    test(
      '--stale with the shown token removes it; a replaced lock is refused',
      () {
        final t9 = taken('add-y');
        expect(gateUnlock(lock, token: t9, stale: true).$1['removed'], true);
        final t10 = taken('add-y');
        final (doc, status) = gateUnlock(lock, token: t9, stale: true);
        expect((status, doc['error']), (1, 'gate_not_owner'));
        expect((doc['owner'] as Map)['token'], t10);
        expect(Directory(lock).existsSync(), true);
      },
    );

    test('--stale refuses a store update lock, naming its code', () {
      Directory(lock).createSync();
      gateWriteOwner(lock, '0.5.0', '0.6.0', '/a', 'tok');
      final (doc, status) = gateUnlock(lock, token: 'tok', stale: true);
      expect(
        (status, doc['error'], doc['code']),
        (1, 'gate_update_held', '/a'),
      );
      expect(File('$lock/owner').existsSync(), true);
    });

    test('--stale --ownerless removes a lock without a token only', () {
      Directory(lock).createSync();
      final (doc, status) = gateUnlock(lock, stale: true, ownerless: true);
      expect((status, doc['removed']), (0, true));
      final t = taken('add-x');
      final (refused, code) = gateUnlock(lock, stale: true, ownerless: true);
      expect((code, refused['error']), (1, 'gate_not_owner'));
      expect((refused['owner'] as Map)['token'], t);
      expect(Directory(lock).existsSync(), true);
    });
  });
}
