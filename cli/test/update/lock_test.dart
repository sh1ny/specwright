import 'dart:io';

import 'package:specwright_cli/src/update/file_ops.dart';
import 'package:specwright_cli/src/update/lock.dart';
import 'package:test/test.dart';

// The lock cases of evals/update/test_update.py (TestLockWithoutOwner and
// TestStaleLockRace) and the lock rules of scripts/update.sh: a directory
// made with mkdir that holds `pid:` and `host:`; a dead pid on this host, or a
// lock with no complete owner file once the directory is older than 60 s, is
// replaced and reported as lock_replaced; any other holder is `locked`.

const _host = 'build-host';

/// An [UpdateFileOps] that runs [onRename] just before each rename.
class _HookedOps extends UpdateFileOps {
  _HookedOps(this.onRename, {super.environment});

  final void Function(String from, String to) onRename;

  @override
  void rename(String from, String to) {
    onRename(from, to);
    super.rename(from, to);
  }
}

void main() {
  late Directory temp;
  late String state;
  late String lock;
  // How far past the real time the lock's judge believes it is: a directory's
  // modification time cannot be set from Dart, so an old lock is a late clock.
  late Duration skew;

  setUp(() {
    temp = Directory.systemTemp.createTempSync('sw-lock-');
    state = '${temp.path}/openspec/.specwright';
    lock = '$state/update.lock';
    skew = Duration.zero;
  });

  tearDown(() {
    temp.deleteSync(recursive: true);
  });

  UpdateLock make({
    UpdateFileOps? ops,
    bool Function(int)? alive,
    int pid = 4711,
  }) => UpdateLock(
    state,
    ops ?? UpdateFileOps(environment: const {}),
    hostname: _host,
    pid: pid,
    isAlive: alive ?? (_) => false,
    now: () => DateTime.now().add(skew),
  );

  void makeLock({String? owner}) {
    Directory(lock).createSync(recursive: true);
    if (owner != null) File('$lock/owner').writeAsStringSync(owner);
  }

  List<String> leftovers() => [
    for (final e in Directory(state).listSync())
      if (e.path.split(RegExp(r'[/\\]')).last.startsWith('update.lock.stale.'))
        e.path,
  ];

  void expectLocked(UpdateLock l, Object message) {
    expect(
      l.acquire,
      throwsA(
        isA<UpdateLocked>()
            .having((e) => e.code, 'code', 'locked')
            .having((e) => e.message, 'message', wrapMatcher(message)),
      ),
    );
  }

  group('a free lock', () {
    test('is made with the owner file, and removed on release', () {
      final l = make();
      l.acquire();
      expect(l.path, lock);
      expect(Directory(lock).existsSync(), isTrue);
      expect(
        File('$lock/owner').readAsStringSync(),
        'pid: 4711\nhost: $_host\n',
      );
      expect(l.replaced, isNull);
      l.release();
      expect(Directory(lock).existsSync(), isFalse);
      l.release(); // a second release, or one without a lock held, is nothing
    });

    test('release without acquire leaves another run\'s lock alone', () {
      makeLock(owner: 'pid: 1\nhost: other\n');
      make().release();
      expect(Directory(lock).existsSync(), isTrue);
    });

    test('creates the state directory, and its operations are counted', () {
      final log = '${temp.path}/count.log';
      final l = make(
        ops: UpdateFileOps(environment: {'SPECWRIGHT_UPDATE_COUNT': log}),
      );
      l.acquire();
      l.release();
      expect(File(log).readAsLinesSync(), [
        '1 mkdir -p $state',
        '2 mkdir $lock',
        '3 rm -rf $lock',
      ]);
    });
  });

  group('a lock held by someone', () {
    test('alive on this host is locked, and left as it is', () {
      makeLock(owner: 'pid: 4242\nhost: $_host\n');
      expectLocked(
        make(alive: (_) => true),
        'another update holds $lock (pid 4242 on $_host); '
        'wait for it to finish',
      );
      expect(
        File('$lock/owner').readAsStringSync(),
        'pid: 4242\nhost: $_host\n',
      );
      expect(leftovers(), isEmpty);
    });

    test('dead on another host is locked: its pid means nothing here', () {
      makeLock(owner: 'pid: 999999\nhost: elsewhere\n');
      expectLocked(
        make(),
        'another update holds $lock (pid 999999 on elsewhere); '
        'wait for it to finish',
      );
      expect(Directory(lock).existsSync(), isTrue);
    });

    test('a pid that is not a number is locked', () {
      makeLock(owner: 'pid: soon\nhost: $_host\n');
      expectLocked(make(), contains('pid soon on $_host'));
    });

    test('an owner file that is not UTF-8 is judged, never a crash', () {
      Directory(lock).createSync(recursive: true);
      File('$lock/owner').writeAsBytesSync([
        ...'pid: 12\nhost: $_host\n'.codeUnits,
        0xff, 0xfe, 0x0a, // not UTF-8
      ]);
      expectLocked(make(alive: (_) => true), contains('pid 12 on $_host'));
    });
  });

  group('a dead owner on this host', () {
    test('is taken over without leftovers and reported as lock_replaced', () {
      makeLock(owner: 'pid: 999999\nhost: $_host\n');
      final l = make();
      l.acquire();
      expect(l.replaced, {'pid': 999999, 'host': _host});
      expect(
        File('$lock/owner').readAsStringSync(),
        'pid: 4711\nhost: $_host\n',
      );
      expect(leftovers(), isEmpty);
      l.release();
      expect(Directory(lock).existsSync(), isFalse);
    });

    test('is judged by the pid alive check', () {
      makeLock(owner: 'pid: 31337\nhost: $_host\n');
      final asked = <int>[];
      make(
        alive: (pid) {
          asked.add(pid);
          return false;
        },
      ).acquire();
      expect(asked, [
        31337,
        31337,
      ], reason: 'judged, then judged again once aside');
    });
  });

  group('a lock without a complete owner file', () {
    test('old and ownerless is taken over (lock_without_owner)', () {
      makeLock();
      skew = const Duration(hours: 1);
      final l = make();
      l.acquire();
      expect(l.replaced, {
        'pid': null,
        'host': null,
        'reason': 'lock_without_owner',
      });
      expect(File('$lock/owner').existsSync(), isTrue);
      expect(leftovers(), isEmpty);
    });

    test('fresh and ownerless reports locked', () {
      makeLock();
      expectLocked(
        make(),
        'another update holds $lock (pid unknown on unknown host); '
        'wait for it to finish',
      );
      expect(Directory(lock).isAbsolute, isTrue);
      expect(Directory(lock).existsSync(), isTrue);
    });

    test('60 s is the edge: 59 s is locked, 61 s is stale', () {
      makeLock();
      skew = const Duration(seconds: 59);
      expectLocked(make(), contains('pid unknown'));
      skew = const Duration(seconds: 62);
      make().acquire();
    });

    test(
      'old with only the pid line (killed mid owner write) is taken over',
      () {
        makeLock(owner: 'pid: 4242\n');
        skew = const Duration(hours: 1);
        final l = make(alive: (_) => true);
        l.acquire();
        expect(l.replaced, containsPair('reason', 'lock_without_owner'));
        expect(leftovers(), isEmpty);
      },
    );

    test('fresh with only the pid line is locked, naming the pid', () {
      makeLock(owner: 'pid: 4242\n');
      expectLocked(make(), contains('(pid 4242 on unknown host)'));
    });

    test('an owner file with a host and no pid is old enough to take', () {
      makeLock(owner: 'host: $_host\n');
      skew = const Duration(hours: 1);
      final l = make();
      l.acquire();
      expect(l.replaced, containsPair('reason', 'lock_without_owner'));
    });
  });

  group('a stale lock another run takes meanwhile', () {
    // The race shim of the eval: at the first rename naming the lock, another
    // run removes the stale lock and makes it afresh (before its owner write),
    // then the real rename runs on what is there now.
    UpdateFileOps racing({bool third = false}) {
      var seen = false;
      var thirdDone = false;
      return _HookedOps((from, to) {
        if (!seen && (from == lock || to == lock)) {
          seen = true;
          Directory(lock).deleteSync(recursive: true);
          Directory(lock).createSync();
          skew = Duration.zero; // the new lock is as old as now
        } else if (third && seen && !thirdDone && to == lock) {
          thirdDone = true;
          Directory(lock).createSync();
          File('$lock/third').writeAsStringSync('');
        }
      }, environment: const {});
    }

    test('an ownerless lock is kept, with no leftover', () {
      makeLock();
      skew = const Duration(hours: 1);
      expectLocked(
        make(ops: racing()),
        'another update holds $lock (pid unknown on unknown host); '
        'wait for it to finish',
      );
      expect(Directory(lock).existsSync(), isTrue);
      expect(leftovers(), isEmpty);
    });

    test('a dead-owner lock is kept, with no leftover', () {
      makeLock(owner: 'pid: 999999\nhost: $_host\n');
      expectLocked(make(ops: racing()), startsWith('another update holds'));
      expect(Directory(lock).existsSync(), isTrue);
      expect(leftovers(), isEmpty);
    });

    test('a lock a third run took before the put back is untouched', () {
      makeLock();
      skew = const Duration(hours: 1);
      expectLocked(
        make(ops: racing(third: true)),
        'another update took $lock while this run was replacing a stale lock; '
        'its lock was left at $lock.stale.4711',
      );
      expect(
        [
          for (final e in Directory(lock).listSync())
            e.path.split(RegExp(r'[/\\]')).last,
        ],
        ['third'],
        reason: "the third run's lock is untouched",
      );
      expect(leftovers(), hasLength(1), reason: 'the renamed lock stays aside');
    });
  });
}
