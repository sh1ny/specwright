@Tags(['process'])
library;

import 'dart:io';
import 'dart:math';

import 'package:specwright_cli/src/pr/context.dart';
import 'package:specwright_cli/src/pr/watch_state.dart';
import 'package:specwright_cli/src/vcs/codec.dart';
import 'package:test/test.dart';

/// A random source that answers [values] in turn.
class Fixed implements Random {
  Fixed(this.values);

  final List<int> values;
  var i = 0;

  @override
  int nextInt(int max) => values[i++ % values.length];

  @override
  bool nextBool() => false;

  @override
  double nextDouble() => 0;
}

void main() {
  late Directory dir;
  String names(Directory d) => ([
    for (final e in d.listSync())
      e.uri.pathSegments.where((s) => s.isNotEmpty).last,
  ]..sort()).join(' ');

  setUp(() => dir = Directory.systemTemp.createTempSync('sw-watch-'));
  tearDown(() => dir.deleteSync(recursive: true));

  PrContext context({Map<String, String>? env, PrMakeTemp? makeTemp}) =>
      PrContext(
        scriptsDir: 'scripts',
        bash: 'bash',
        writeOut: (_) {},
        writeErr: (_) {},
        environment: env,
        makeTemp: makeTemp,
      );

  group('the state directory', () {
    test('is SPECWRIGHT_STATE_DIR, else HOME/.cache/specwright', () async {
      final a = await stateBase(
        context(env: {'SPECWRIGHT_STATE_DIR': '${dir.path}/s', 'HOME': '/h'}),
      );
      expect(a, '${dir.path}/s');
      final b = await stateBase(context(env: {'HOME': '${dir.path}/h'}));
      expect(b, '${dir.path}/h/.cache/specwright');
      final c = await stateBase(
        context(env: {'SPECWRIGHT_STATE_DIR': '', 'HOME': '${dir.path}/h'}),
      );
      expect(
        c,
        '${dir.path}/h/.cache/specwright',
        reason: 'an empty value is unset, as ${'\${v:-}'} does',
      );
    });

    test(
      'a /tmp state base on Windows goes under TEMP, with no cygpath',
      () async {
        final base = await stateBase(
          context(
            env: {
              'SPECWRIGHT_STATE_DIR': '/tmp/state',
              'TEMP': dir.path,
              'PATH': '',
            },
          ),
        );
        expect(base, '${dir.path.replaceAll(r'\', '/')}/state');
        expect(Directory(base).parent.existsSync(), isTrue);
      },
      skip: Platform.isWindows ? false : 'a Windows path conversion',
    );

    test(
      'the claim and head directories are lower case ASCII, and only ASCII',
      () {
        expect(
          claimDirectory('/b', 'Owner', 'Name', '12'),
          '/b/watch/v2/owner/name/12',
        );
        expect(
          headsDirectory('/b', 'Owner', 'Name', '12'),
          '/b/heads/owner/name/12',
        );
        expect(
          claimDirectory('/b', 'ÖWNER', 'N', '1'),
          '/b/watch/v2/Öwner/n/1',
        );
      },
    );
  });

  group('a claim', () {
    test('is a file <n>-<pid>.<5 digits><5 digits>, one above the highest', () {
      Directory('${dir.path}/c').createSync();
      File('${dir.path}/c/3-old').createSync();
      final claim = WatchClaim.claim(
        '${dir.path}/c',
        random: Fixed([7, 32767]),
        pid: 4242,
      )!;
      expect(claim.number, 4);
      expect(claim.nonce, '4242.0000732767');
      expect(File('${dir.path}/c/4-4242.0000732767').existsSync(), isTrue);
    });

    test('the first claim is number 1, and the directory is created', () {
      final claim = WatchClaim.claim('${dir.path}/a/b/c')!;
      expect(claim.number, 1);
      expect(claim.nonce, matches(RegExp(r'^[0-9]+\.[0-9]{10}$')));
      expect(names(Directory('${dir.path}/a/b/c')), claim.name);
    });

    test(
      'is created without clobbering: a name that is taken is no claim',
      () {
        final c = Directory('${dir.path}/c')..createSync();
        // a dangling link is not listed (`-e` is false for it), but its name is taken
        Link('${c.path}/1-1.0000000000').createSync('/no/such/target');
        expect(WatchClaim.claim(c.path, random: Fixed([0, 0]), pid: 1), isNull);
      },
      skip: Platform.isWindows
          ? 'a symbolic link needs privileges here'
          : false,
    );

    test('a directory that cannot be made is no claim', () {
      File('${dir.path}/file').writeAsStringSync('x');
      expect(WatchClaim.claim('${dir.path}/file/under'), isNull);
    });

    test('removes the lower claims, and only claim files', () {
      final c = Directory('${dir.path}/c')..createSync();
      for (final n in ['1-a', '2-b', '07-c', 'x-y', '.hidden', 'notes', '5']) {
        File('${c.path}/$n').createSync();
      }
      final claim = WatchClaim.claim(c.path, random: Fixed([0, 0]), pid: 1)!;
      expect(claim.number, 8, reason: '07 is 7: numbers parse as decimal');
      expect(names(c), '.hidden 8-1.0000000000 notes x-y');
    });

    test('a bare number is a claim whose nonce is -', () {
      final c = Directory('${dir.path}/c')..createSync();
      File('${c.path}/9').createSync();
      final claim = WatchClaim.claim(c.path, random: Fixed([0, 0]), pid: 1)!;
      expect(claim.number, 10);
      expect(names(c), claim.name);
    });
  });

  group('ownership', () {
    late Directory c;
    late WatchClaim claim;
    setUp(() {
      c = Directory('${dir.path}/c')..createSync();
      claim = WatchClaim.claim(c.path, random: Fixed([0, 0]), pid: 1)!;
    });

    test('holds while the own file exists and no claim is above it', () {
      expect(claim.stillOwner(), isTrue);
      File('${c.path}/${claim.number - 1}-lower').createSync();
      expect(claim.stillOwner(), isTrue);
      File('${c.path}/x').createSync();
      expect(claim.stillOwner(), isTrue);
    });

    test('is lost to a higher number', () {
      File('${c.path}/${claim.number + 1}-newer').createSync();
      expect(claim.stillOwner(), isFalse);
    });

    test('is lost when the own file is gone', () {
      File('${c.path}/${claim.name}').deleteSync();
      expect(claim.stillOwner(), isFalse);
    });

    test('equal claim numbers order nonces by bytes', () {
      // claim number 1, nonce 1.0000000000
      expect(claim.above(1, '1.0000000001'), isTrue);
      expect(
        claim.above(1, '1.0000000000'),
        isFalse,
        reason: 'the same nonce is not above',
      );
      expect(claim.above(1, '0.9999999999'), isFalse);
      // by bytes B (0x42) and a (0x61) are above 1 (0x31); a locale's collation would put 1 above a letter's case
      expect(claim.above(1, 'B'), isTrue);
      expect(claim.above(1, 'a'), isTrue);
      expect(
        claim.above(1, '.'),
        isFalse,
        reason: '. (0x2e) is below 1 (0x31)',
      );
      // the byte order, not the length, decides, and a bare number's nonce is -
      expect(claim.above(1, '1.00000000009'), isTrue);
      expect(
        claim.above(1, '-'),
        isFalse,
        reason: '- (0x2d) is below 1 (0x31)',
      );
    });

    test('a claim of the other implementation with an equal number decides by the same order', () {
      File('${c.path}/${claim.number}-9.9').createSync();
      expect(
        claim.stillOwner(),
        isFalse,
        reason: '9.9 is above 1.0000000000 by bytes',
      );
      File('${c.path}/${claim.number}-9.9').deleteSync();
      File('${c.path}/${claim.number}-0.1').createSync();
      expect(claim.stillOwner(), isTrue);
    });
  });

  group('release', () {
    test('removes the own file by its name and no other', () {
      final c = Directory('${dir.path}/c')..createSync();
      final claim = WatchClaim.claim(c.path, random: Fixed([0, 0]), pid: 1)!;
      File('${c.path}/${claim.number + 1}-newer').createSync();
      claim.release();
      expect(names(c), '${claim.number + 1}-newer');
      claim.release(); // twice is fine
    });
  });

  group('the head record', () {
    const date = 'Mon, 02 Nov 2026 10:00:00 GMT';
    const later = 'Tue, 03 Nov 2026 11:00:00 GMT';
    final oid = 'a' * 40;
    late String heads;
    setUp(() => heads = '${dir.path.replaceAll(r'\', '/')}/heads/o/n/7');

    test('is written to a temp file and published with a hard link', () async {
      final seen = await resolveFirstSeen(
        context(),
        dir: heads,
        oid: oid,
        firstSeen: date,
      );
      expect((seen.date, seen.source), (date, 'first_seen'));
      expect(File('$heads/$oid').readAsStringSync(), '$date\n');
      expect(names(Directory(heads)), oid, reason: 'the temp file is removed');
    });

    test('the first writer wins', () async {
      await resolveFirstSeen(context(), dir: heads, oid: oid, firstSeen: date);
      final seen = await resolveFirstSeen(
        context(),
        dir: heads,
        oid: oid,
        firstSeen: later,
      );
      expect((seen.date, seen.source), (date, 'first_seen'));
      expect(File('$heads/$oid').readAsStringSync(), '$date\n');
    });

    test('publishing removes the records of the other heads', () async {
      await resolveFirstSeen(
        context(),
        dir: heads,
        oid: 'b' * 40,
        firstSeen: date,
      );
      File('$heads/.keep').writeAsStringSync('x');
      await resolveFirstSeen(context(), dir: heads, oid: oid, firstSeen: later);
      expect(names(Directory(heads)), '.keep $oid');
    });

    test(
      'mktemp runs once, with the template in the heads directory',
      () async {
        final calls = <String?>[];
        final seen = await resolveFirstSeen(
          context(
            makeTemp: ([t]) async {
              calls.add(t);
              return null;
            },
          ),
          dir: heads,
          oid: oid,
          firstSeen: date,
        );
        expect(calls, ['$heads/.tmp.XXXXXX']);
        expect((seen.date, seen.source), (date, 'first_seen_unsaved'));
        expect(File('$heads/$oid').existsSync(), isFalse);
      },
    );

    test('a directory that cannot be made is first_seen_unsaved', () async {
      File('${dir.path}/file').writeAsStringSync('x');
      final seen = await resolveFirstSeen(
        context(),
        dir: '${dir.path}/file/heads',
        oid: oid,
        firstSeen: date,
      );
      expect((seen.date, seen.source), (date, 'first_seen_unsaved'));
    });

    test('a record that is not a date is first_seen_unsaved', () async {
      Directory(heads).createSync(recursive: true);
      File('$heads/$oid').writeAsStringSync('not a date\n');
      final seen = await resolveFirstSeen(
        context(),
        dir: heads,
        oid: oid,
        firstSeen: later,
      );
      expect((seen.date, seen.source), (later, 'first_seen_unsaved'));
    });

    test('a record with a carriage return still reads', () async {
      Directory(heads).createSync(recursive: true);
      File('$heads/$oid')
          .writeAsBytesSync(encodeEscaped('$date\r\nsecond line\n'));
      final seen = await resolveFirstSeen(
        context(),
        dir: heads,
        oid: oid,
        firstSeen: later,
      );
      expect((seen.date, seen.source), (date, 'first_seen'));
    });

    test(
      'a failed link leaves no published record and the temp file is removed',
      () async {
        Directory(heads).createSync(recursive: true);
        final fake = File('$heads/.tmp.fake')..writeAsStringSync('');
        // a directory where the record goes: the no-clobber link fails
        Directory('$heads/$oid').createSync();
        final seen = await resolveFirstSeen(
          PrContext(
            scriptsDir: 's',
            bash: 'bash',
            writeOut: (_) {},
            writeErr: (_) {},
            makeTemp: ([t]) async => fake.path,
          ),
          dir: heads,
          oid: oid,
          firstSeen: date,
        );
        expect(seen.source, 'first_seen_unsaved');
        expect(fake.existsSync(), isFalse);
      },
    );
  });

  group('makeTemp (D8: no mktemp)', () {
    test('a template gets its X run replaced and a new empty file', () async {
      final slashed = dir.path.replaceAll(r'\', '/');
      final path = await context().makeTemp('$slashed/.tmp.XXXXXX');
      expect(path, isNotNull);
      expect(path, startsWith('$slashed/.tmp.'));
      expect(path!.length, '$slashed/.tmp.XXXXXX'.length);
      expect(path, isNot(endsWith('XXXXXX')));
      expect(File(path).existsSync(), isTrue);
      expect(File(path).lengthSync(), 0);
    });

    test('two calls never give the same file', () async {
      final slashed = dir.path.replaceAll(r'\', '/');
      final a = await context().makeTemp('$slashed/t.XXXXXX');
      final b = await context().makeTemp('$slashed/t.XXXXXX');
      expect(a, isNot(b));
    });

    test(
      'no template makes tmp.XXXXXXXXXX in the system temp directory',
      () async {
        final path = await context().makeTemp();
        addTearDown(() => File(path!).deleteSync());
        expect(path, isNotNull);
        expect(
          path!.split('/').last,
          matches(RegExp(r'^tmp\.[A-Za-z0-9]{10}$')),
        );
        expect(File(path).existsSync(), isTrue);
        expect(path.contains(r'\'), isFalse, reason: 'the drive form with /');
      },
    );

    test('POSIX files are owner-only (0600), as mktemp made them', () async {
      final slashed = dir.path.replaceAll(r'\', '/');
      final named = await context().makeTemp('$slashed/m.XXXXXX');
      final plain = await context().makeTemp();
      addTearDown(() => File(plain!).deleteSync());
      for (final path in [named!, plain!]) {
        expect(FileStat.statSync(path).mode & 0x1FF, 0x180, reason: path);
      }
    }, skip: Platform.isWindows ? 'POSIX modes only' : false);

    test('a template with no X, or in a missing directory, is null', () async {
      final slashed = dir.path.replaceAll(r'\', '/');
      expect(await context().makeTemp('$slashed/plain'), isNull);
      expect(await context().makeTemp('$slashed/none/t.XXXXXX'), isNull);
    });
  });
}
