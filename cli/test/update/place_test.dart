import 'dart:convert';
import 'dart:io';

import 'package:specwright_cli/src/commands/version.dart';
import 'package:specwright_cli/src/update/file_ops.dart';
import 'package:specwright_cli/src/update/place.dart';
import 'package:specwright_cli/src/update/stop.dart';
import 'package:test/test.dart';

import 'fake_sw.dart';

// Design D6 and D7 of native-cli-update: a downloaded binary is checked by
// running it with `version --json` (10 s, 1 MiB), the version must be the
// download's and the interface the running binary's; the notice is placed
// before the binary, the binary is replaced only by a rename, and the running
// file is never moved.

final _exe = Platform.isWindows ? 'sw.exe' : 'sw';

void main() {
  late Directory temp;
  late String fake;
  late String vdir;
  late String log;

  setUpAll(() async {
    temp = Directory.systemTemp.createTempSync('sw-place-');
    fake = await compileFakeSw(temp);
  });

  tearDownAll(() => temp.deleteSync(recursive: true));

  var n = 0;
  late Directory work;
  setUp(() {
    work = Directory('${temp.path}/case-${n++}')..createSync();
    vdir = '${work.path}/bin/0.37.0';
    Directory(vdir).createSync(recursive: true);
    log = '${work.path}/ops.log';
  });

  UpdateFileOps counted() => UpdateFileOps(
    environment: {'SPECWRIGHT_UPDATE_COUNT': log},
    exitProcess: (_) {},
  );

  List<String> ops() => File(log).existsSync()
      ? File(log).readAsLinesSync().where((l) => l.isNotEmpty).toList()
      : <String>[];

  group('checkBinary', () {
    Future<BinaryCheck> check(
      String file, {
      String version = '0.37.0',
      int interface = interfaceVersion,
      Duration deadline = const Duration(seconds: 10),
    }) => checkBinary(
      file,
      version: version,
      expectedInterface: interface,
      deadline: deadline,
    );

    test('a binary reporting the version and the interface passes', () async {
      final path = installFakeSw(fake, '${work.path}/a', _exe);
      final result = await check(path);
      expect(result.ok, isTrue, reason: result.detail);
    });

    test('the interface is the running binary\'s, by default', () async {
      final path = installFakeSw(fake, '${work.path}/a', _exe);
      expect(
        (await checkBinary(path, version: '0.37.0')).ok,
        isTrue,
        reason: 'the fake reports interface $interfaceVersion',
      );
    });

    test('another version fails and names both', () async {
      final path = installFakeSw(fake, '${work.path}/a', _exe);
      final result = await check(path, version: '9.9.9');
      expect(result.ok, isFalse);
      expect(result.detail, allOf(contains('0.37.0'), contains('9.9.9')));
    });

    test('another interface fails and names both', () async {
      final path = installFakeSw(
        fake,
        '${work.path}/a',
        _exe,
        config: 'print\n{"version":"0.37.0","interface":7}\n',
      );
      final result = await check(path);
      expect(result.ok, isFalse);
      expect(
        result.detail,
        allOf(contains('interface 7'), contains('interface $interfaceVersion')),
      );
    });

    for (final (label, config) in [
      ('not JSON', 'print\nhello\n'),
      ('a JSON array', 'print\n[1]\n'),
      ('no version', 'print\n{"interface":1}\n'),
      ('no interface', 'print\n{"version":"0.37.0"}\n'),
      ('a number for the version', 'print\n{"version":37,"interface":1}\n'),
      ('a non-zero exit', 'exit 3\n'),
    ]) {
      test('$label fails the check', () async {
        final path = installFakeSw(
          fake,
          '${work.path}/a',
          _exe,
          config: config,
        );
        expect((await check(path)).ok, isFalse);
      });
    }

    test('output past 1 MiB fails the check', () async {
      final path = installFakeSw(fake, '${work.path}/a', _exe, config: 'big\n');
      final result = await check(path);
      expect(result.ok, isFalse);
      expect(result.detail, contains('1 MiB'));
    });

    test(
      'stderr without end is stopped at 1 MiB, not at the deadline',
      () async {
        final path = installFakeSw(
          fake,
          '${work.path}/a',
          _exe,
          config: 'spew\n',
        );
        final watch = Stopwatch()..start();
        final result = await check(path, deadline: const Duration(seconds: 60));
        expect(result.ok, isFalse);
        expect(result.detail, contains('1 MiB'));
        expect(watch.elapsed, lessThan(const Duration(seconds: 50)));
      },
    );

    test('a binary that hangs fails at the deadline', () async {
      final path = installFakeSw(
        fake,
        '${work.path}/a',
        _exe,
        config: 'hang\n',
      );
      final watch = Stopwatch()..start();
      final result = await check(
        path,
        deadline: const Duration(milliseconds: 700),
      );
      expect(result.ok, isFalse);
      expect(result.detail, contains('deadline'));
      expect(watch.elapsed, lessThan(const Duration(seconds: 8)));
    });

    test('a missing file fails the check', () async {
      final result = await check('${work.path}/none/$_exe');
      expect(result.ok, isFalse);
      expect(result.detail, contains('does not exist'));
    });
  });

  group('placement', () {
    String sha(String path) => fileSha(path);

    String partOf(String name, {String? version}) => installFakeSw(
      fake,
      '${work.path}/parts/$name',
      _exe,
      version: version ?? '0.37.0',
    );

    String notice(String text) {
      final path = '${work.path}/parts/notice-$text.part';
      Directory('${work.path}/parts').createSync(recursive: true);
      File(path).writeAsStringSync(text);
      return path;
    }

    Future<String> place(String part, {String? noticePart, String? running}) =>
        placeChecked(
          files: counted(),
          part: part,
          finalPath: '$vdir/$_exe',
          partSha: sha(part),
          version: '0.37.0',
          asset: 'sw-linux-x64',
          ref: 'v0.37.0',
          noticePart: noticePart,
          noticeFinal: '$vdir/THIRD_PARTY_NOTICES.txt',
          noticeSha: noticePart == null ? null : sha(noticePart),
          running: running,
        );

    test('a fresh file is installed, the notice renamed before it', () async {
      final part = partOf('one');
      final noticePart = notice('n1');
      final bytes = File(part).readAsBytesSync();
      expect(await place(part, noticePart: noticePart), 'installed');
      expect(File('$vdir/$_exe').readAsBytesSync(), bytes);
      expect(File('$vdir/THIRD_PARTY_NOTICES.txt').readAsStringSync(), 'n1');
      final moves = ops().where((l) => l.contains(' mv ')).toList();
      expect(moves, hasLength(2));
      expect(moves[0], contains('THIRD_PARTY_NOTICES.txt'));
      expect(moves[1], contains('$vdir/$_exe'));
      expect(ops().where((l) => l.contains(' cp ')), isEmpty);
    });

    test('another file there is replaced, by a rename only', () async {
      File('$vdir/$_exe').writeAsStringSync('stale');
      final part = partOf('two');
      final bytes = File(part).readAsBytesSync();
      expect(await place(part), 'replaced');
      expect(File('$vdir/$_exe').readAsBytesSync(), bytes);
      expect(ops().where((l) => l.contains(' mv ')), hasLength(1));
      expect(ops().where((l) => l.contains(' cp ')), isEmpty);
    });

    test('the same runnable file is kept and not touched', () async {
      final existing = installFakeSw(fake, vdir, _exe);
      final before = File(existing).statSync().modified;
      final part = partOf('three');
      expect(await place(part), 'kept');
      expect(File(existing).statSync().modified, before);
      expect(ops().where((l) => l.contains(' mv ')), isEmpty);
    });

    test('a kept binary still gets a missing notice', () async {
      installFakeSw(fake, vdir, _exe);
      final part = partOf('four');
      expect(await place(part, noticePart: notice('n4')), 'kept');
      expect(File('$vdir/THIRD_PARTY_NOTICES.txt').readAsStringSync(), 'n4');
    });

    test('a matching notice is left alone', () async {
      File('$vdir/THIRD_PARTY_NOTICES.txt').writeAsStringSync('n5');
      final noticePart = notice('n5');
      expect(await place(partOf('five'), noticePart: noticePart), 'installed');
      expect(
        ops().where((l) => l.contains('THIRD_PARTY_NOTICES.txt')),
        isEmpty,
      );
    });

    test('a notice that cannot be placed stops before the binary', () async {
      // a directory at the notice's path cannot be replaced by a file
      Directory('$vdir/THIRD_PARTY_NOTICES.txt').createSync();
      File('$vdir/$_exe').writeAsStringSync('existing');
      final stop = await _stopOf(
        place(partOf('six'), noticePart: notice('n6')),
      );
      expect(stop.code, 'notice_write_failed');
      expect(stop.message, contains('the binary was not replaced'));
      expect(File('$vdir/$_exe').readAsStringSync(), 'existing');
    });

    test('a blocked rename leaves the part for the caller', () async {
      // a directory at the final path cannot be replaced by a file
      Directory('$vdir/$_exe').createSync();
      final part = partOf('seven');
      final stop = await _stopOf(place(part));
      expect(stop.code, 'sw_in_use');
      expect(stop.message, contains('sw-linux-x64 of release v0.37.0'));
      expect(Directory('$vdir/$_exe').existsSync(), isTrue);
      expect(File(part).existsSync(), isTrue, reason: 'the caller owns it');
    });

    test('the running file is never moved', () async {
      final running = installFakeSw(fake, '${work.path}/running', _exe);
      final stop = await _stopOf(place(running, running: running));
      expect(stop.code, 'sw_in_use');
      expect(File(running).existsSync(), isTrue);
      expect(File('$vdir/$_exe').existsSync(), isFalse);
      expect(ops().where((l) => l.contains(' mv ')), isEmpty);
    });

    test('the default running file is this process\'s', () async {
      final stop = await _stopOf(
        placeChecked(
          files: counted(),
          part: Platform.resolvedExecutable,
          finalPath: '$vdir/$_exe',
          partSha: 'x',
          version: '0.37.0',
          asset: 'sw-linux-x64',
          ref: 'v0.37.0',
        ),
      );
      expect(stop.code, 'sw_in_use');
      expect(File(Platform.resolvedExecutable).existsSync(), isTrue);
    });
  });

  test('fileSha is the SHA-256 in lowercase hex', () {
    final path = '${work.path}/hello';
    File(path).writeAsBytesSync(utf8.encode('hello'));
    expect(
      fileSha(path),
      '2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824',
    );
  });
}

Future<UpdateStop> _stopOf(Future<Object?> run) async {
  try {
    await run;
  } on UpdateStop catch (e) {
    return e;
  }
  fail('expected an UpdateStop');
}
