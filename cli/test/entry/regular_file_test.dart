import 'dart:io';
import 'dart:typed_data';

import 'package:specwright_cli/src/entry/regular_file.dart';
import 'package:test/test.dart';

void main() {
  late Directory tmp;
  setUp(() => tmp = Directory.systemTemp.createTempSync('sw-regular-file-'));
  tearDown(() => tmp.deleteSync(recursive: true));

  String at(String name) => '${tmp.path}/$name';

  group('readRegularFile', () {
    test('a regular file is read whole', () {
      File(at('a')).writeAsBytesSync([1, 2, 3]);
      expect(readRegularFile(at('a')), Uint8List.fromList([1, 2, 3]));
    });

    test('a path that is not there is missing, not an error', () {
      expect(readRegularFile(at('none')), isNull);
    });

    test('a dangling link is missing', () {
      try {
        Link(at('dangling')).createSync(at('none'));
      } on FileSystemException {
        markTestSkipped('no symbolic links here');
        return;
      }
      expect(readRegularFile(at('dangling')), isNull);
    });

    test('a link to a regular file is read', () {
      File(at('target')).writeAsBytesSync([7]);
      try {
        Link(at('link')).createSync(at('target'));
      } on FileSystemException {
        markTestSkipped('no symbolic links here');
        return;
      }
      expect(readRegularFile(at('link')), Uint8List.fromList([7]));
    });

    test('a directory is refused, naming the path', () {
      Directory(at('dir')).createSync();
      expect(
        () => readRegularFile(at('dir')),
        throwsA(isA<NotRegularFile>().having((e) => e.path, 'path', at('dir'))),
      );
    });

    test('a link to a directory is refused', () {
      Directory(at('dir')).createSync();
      try {
        Link(at('link')).createSync(at('dir'));
      } on FileSystemException {
        markTestSkipped('no symbolic links here');
        return;
      }
      expect(() => readRegularFile(at('link')), throwsA(isA<NotRegularFile>()));
    });

    test('a FIFO is refused without being opened', () {
      if (Platform.isWindows) {
        markTestSkipped('no FIFO on Windows');
        return;
      }
      final made = Process.runSync('mkfifo', [at('pipe')]);
      expect(made.exitCode, 0);
      // opening a FIFO that has no writer would block this test for ever
      expect(() => readRegularFile(at('pipe')), throwsA(isA<NotRegularFile>()));
    }, timeout: const Timeout(Duration(seconds: 60)));

    test('a link to a FIFO is refused without being opened', () {
      if (Platform.isWindows) {
        markTestSkipped('no FIFO on Windows');
        return;
      }
      Process.runSync('mkfifo', [at('pipe')]);
      Link(at('link')).createSync(at('pipe'));
      expect(() => readRegularFile(at('link')), throwsA(isA<NotRegularFile>()));
    }, timeout: const Timeout(Duration(seconds: 60)));

    test('a limit reads at most that many bytes', () {
      File(at('big')).writeAsBytesSync(List.filled(100, 9));
      expect(readRegularFile(at('big'), limit: 10)!.length, 10);
      expect(readRegularFile(at('big'), limit: 1000)!.length, 100);
    });
  });

  group('copyRegularFile', () {
    test('copies a regular file', () {
      File(at('from')).writeAsBytesSync([4, 5]);
      copyRegularFile(at('from'), at('to'));
      expect(File(at('to')).readAsBytesSync(), [4, 5]);
    });

    test('a directory source is refused and nothing is written', () {
      Directory(at('dir')).createSync();
      expect(
        () => copyRegularFile(at('dir'), at('to')),
        throwsA(isA<NotRegularFile>()),
      );
      expect(File(at('to')).existsSync(), isFalse);
    });

    test('a missing source is a file system error', () {
      expect(
        () => copyRegularFile(at('none'), at('to')),
        throwsA(isA<FileSystemException>()),
      );
    });
  });

  group('the single reader (C38)', () {
    // Any call that opens a work-tree file for reading or copies one.
    final opens = RegExp(
      r'\.(readAsBytes|readAsString|readAsLines|openRead|open|openSync|copy|copySync)(Sync)?\s*\(',
    );
    final files = [
      ...Directory('lib/src/finish')
          .listSync()
          .whereType<File>()
          .where((f) => f.path.endsWith('.dart'))
          .map((f) => f.path),
      'lib/src/entry/project_version.dart',
    ];

    test(
      'no file-opening API appears in the finish code or the version check',
      () {
        expect(files.length, greaterThan(2));
        for (final path in files) {
          final lines = File(path).readAsLinesSync();
          for (var i = 0; i < lines.length; i++) {
            final line = lines[i];
            if (line.trimLeft().startsWith('//')) continue;
            expect(
              opens.hasMatch(line),
              isFalse,
              reason:
                  '$path:${i + 1} opens a file outside regular_file.dart: '
                  '$line',
            );
          }
        }
      },
    );
  });
}
