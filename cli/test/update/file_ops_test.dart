import 'dart:io';

import 'package:specwright_cli/src/update/file_ops.dart';
import 'package:test/test.dart';

class _Exited implements Exception {
  _Exited(this.code);
  final int code;
}

void main() {
  late Directory temp;
  late String log;
  late List<int> exits;

  setUp(() {
    temp = Directory.systemTemp.createTempSync('sw-file-ops-');
    log = '${temp.path}/count.log';
    exits = [];
  });

  tearDown(() {
    temp.deleteSync(recursive: true);
  });

  UpdateFileOps ops({int? killAt, bool counting = true}) => UpdateFileOps(
    environment: {
      if (counting) 'SPECWRIGHT_UPDATE_COUNT': log,
      if (killAt != null) 'SPECWRIGHT_UPDATE_KILL_AT': '$killAt',
    },
    exitProcess: (code) {
      exits.add(code);
      throw _Exited(code);
    },
  );

  String p(String name) => '${temp.path}/$name';

  List<String> lines() =>
      File(log).existsSync() ? File(log).readAsLinesSync() : [];

  group('the operations', () {
    test('mkdir creates the directory and its parents', () {
      ops().mkdir(p('a/b/c'));
      expect(Directory(p('a/b/c')).existsSync(), isTrue);
    });

    test('mkdirExclusive creates one directory and says whether it did', () {
      final o = ops();
      expect(o.mkdirExclusive(p('lock')), isTrue);
      expect(o.mkdirExclusive(p('lock')), isFalse);
      expect(o.mkdirExclusive(p('no/parent')), isFalse);
      expect(Directory(p('lock')).existsSync(), isTrue);
      expect(Directory(p('no')).existsSync(), isFalse);
      expect(lines(), [
        '1 mkdir ${p('lock')}',
        '2 mkdir ${p('lock')}',
        '3 mkdir ${p('no/parent')}',
      ]);
    });

    test('mkdirExclusive is killed before it creates the directory', () {
      final o = ops(killAt: 1);
      expect(() => o.mkdirExclusive(p('lock')), throwsA(isA<_Exited>()));
      expect(Directory(p('lock')).existsSync(), isFalse);
    });

    test('copy puts a file in a directory under its own name', () {
      File(p('src.txt')).writeAsStringSync('x');
      Directory(p('dest')).createSync();
      ops().copy(p('src.txt'), p('dest'));
      expect(File(p('dest/src.txt')).readAsStringSync(), 'x');
      expect(File(p('src.txt')).existsSync(), isTrue);
    });

    test('copy of a directory copies the tree into the directory', () {
      Directory(p('tree/sub')).createSync(recursive: true);
      File(p('tree/a.txt')).writeAsStringSync('a');
      File(p('tree/sub/b.txt')).writeAsStringSync('b');
      Directory(p('dest')).createSync();
      ops().copy(p('tree'), p('dest'));
      expect(File(p('dest/tree/a.txt')).readAsStringSync(), 'a');
      expect(File(p('dest/tree/sub/b.txt')).readAsStringSync(), 'b');
    });

    test('rename moves a file, replacing a file there', () {
      File(p('a')).writeAsStringSync('new');
      File(p('b')).writeAsStringSync('old');
      ops().rename(p('a'), p('b'));
      expect(File(p('a')).existsSync(), isFalse);
      expect(File(p('b')).readAsStringSync(), 'new');
    });

    test('rename moves a directory', () {
      Directory(p('d')).createSync();
      File(p('d/f')).writeAsStringSync('f');
      ops().rename(p('d'), p('e'));
      expect(Directory(p('d')).existsSync(), isFalse);
      expect(File(p('e/f')).readAsStringSync(), 'f');
    });

    test('rename fails when the source is missing', () {
      expect(
        () => ops().rename(p('nope'), p('b')),
        throwsA(isA<FileSystemException>()),
      );
    });

    test('remove deletes a file or a tree and ignores a missing path', () {
      Directory(p('d/x')).createSync(recursive: true);
      File(p('d/x/f')).writeAsStringSync('f');
      File(p('g')).writeAsStringSync('g');
      final o = ops();
      o.remove(p('d'));
      o.remove(p('g'));
      o.remove(p('missing'));
      expect(Directory(p('d')).existsSync(), isFalse);
      expect(File(p('g')).existsSync(), isFalse);
    });
  });

  group('SPECWRIGHT_UPDATE_COUNT', () {
    test('logs "<n> <op> <args>" before each operation, appending', () {
      File(p('src')).writeAsStringSync('x');
      Directory(p('dest')).createSync();
      Directory(p('tree')).createSync();
      final o = ops();
      o.mkdir(p('m'));
      o.copy(p('src'), p('dest'));
      o.copy(p('tree'), p('dest'));
      o.rename(p('src'), p('moved'));
      o.remove(p('moved'));
      expect(lines(), [
        '1 mkdir -p ${p('m')}',
        '2 cp ${p('src')} ${p('dest')}',
        '3 cp -R ${p('tree')} ${p('dest')}',
        '4 mv ${p('src')} ${p('moved')}',
        '5 rm -rf ${p('moved')}',
      ]);
    });

    test('a failing operation is still logged first', () {
      expect(
        () => ops().rename(p('nope'), p('b')),
        throwsA(isA<FileSystemException>()),
      );
      expect(lines(), ['1 mv ${p('nope')} ${p('b')}']);
    });

    test('numbering continues from the file across instances (one run '
        'after another shares one counter)', () {
      ops().mkdir(p('a'));
      ops().mkdir(p('b'));
      ops().mkdir(p('c'));
      expect(lines(), [
        '1 mkdir -p ${p('a')}',
        '2 mkdir -p ${p('b')}',
        '3 mkdir -p ${p('c')}',
      ]);
    });

    test('without the variable nothing is logged', () {
      ops(counting: false).mkdir(p('a'));
      expect(File(log).existsSync(), isFalse);
      expect(Directory(p('a')).existsSync(), isTrue);
    });
  });

  group('SPECWRIGHT_UPDATE_KILL_AT', () {
    test('ends the process at operation n, before performing it', () {
      final o = ops(killAt: 3);
      o.mkdir(p('a'));
      o.mkdir(p('b'));
      expect(() => o.mkdir(p('c')), throwsA(isA<_Exited>()));
      expect(exits, [137]);
      expect(Directory(p('a')).existsSync(), isTrue);
      expect(Directory(p('b')).existsSync(), isTrue);
      expect(Directory(p('c')).existsSync(), isFalse);
      expect(lines().last, '3 mkdir -p ${p('c')}', reason: 'logged before it');
    });

    test('counts every kind of operation, and across instances', () {
      File(p('src')).writeAsStringSync('x');
      Directory(p('dest')).createSync();
      ops(killAt: 4).mkdir(p('a'));
      ops(killAt: 4).copy(p('src'), p('dest'));
      ops(killAt: 4).rename(p('src'), p('moved'));
      expect(() => ops(killAt: 4).remove(p('moved')), throwsA(isA<_Exited>()));
      expect(File(p('moved')).existsSync(), isTrue, reason: 'not removed');
    });

    test('an exit function that returns still leaves the operation undone', () {
      final o = UpdateFileOps(
        environment: {
          'SPECWRIGHT_UPDATE_COUNT': log,
          'SPECWRIGHT_UPDATE_KILL_AT': '1',
        },
        exitProcess: exits.add,
      );
      o.mkdir(p('a'));
      expect(exits, [137]);
      expect(Directory(p('a')).existsSync(), isFalse);
    });

    test('kills nothing without the count file', () {
      final o = ops(killAt: 1, counting: false);
      o.mkdir(p('a'));
      expect(exits, isEmpty);
      expect(Directory(p('a')).existsSync(), isTrue);
    });

    test('a value that is not a number kills nothing', () {
      final o = UpdateFileOps(
        environment: {
          'SPECWRIGHT_UPDATE_COUNT': log,
          'SPECWRIGHT_UPDATE_KILL_AT': 'soon',
        },
        exitProcess: (code) => throw _Exited(code),
      );
      o.mkdir(p('a'));
      expect(Directory(p('a')).existsSync(), isTrue);
    });

    test('the real exit ends the process with 137', () async {
      final result = await Process.run(
        Platform.resolvedExecutable,
        ['run', 'test/update/file_ops_helper.dart', p('x'), p('y'), p('z')],
        environment: {
          'SPECWRIGHT_UPDATE_COUNT': log,
          'SPECWRIGHT_UPDATE_KILL_AT': '2',
        },
      );
      expect(result.exitCode, 137, reason: '${result.stdout}${result.stderr}');
      expect(Directory(p('x')).existsSync(), isTrue);
      expect(Directory(p('y')).existsSync(), isFalse);
      expect(Directory(p('z')).existsSync(), isFalse);
      expect(lines(), ['1 mkdir -p ${p('x')}', '2 mkdir -p ${p('y')}']);
    });
  });
}
