import 'dart:io';

import 'package:specwright_cli/src/commit/paths.dart';
import 'package:test/test.dart';

import '../vcs/bash_support.dart';
import '../support/exe_shim.dart';

/// A stub `cygpath` first on PATH: it logs its arguments, then prints
/// `$STUB_OUT` (raw, with the printf escapes) and exits `$STUB_EXIT`.
const String _stub = r'''#!/bin/sh
printf '%s\n' "$*" >> "$STUB_LOG"
if [ -n "$STUB_OUT" ]; then printf "$STUB_OUT"; fi
exit "${STUB_EXIT:-0}"
''';

void main() {
  useExeShim();
  final bash = findBash();
  late Directory dir;
  late File log;
  setUp(() {
    dir = Directory.systemTemp.createTempSync('claude-ncc-g2-paths-');
    final stub = File('${dir.path}/cygpath')..writeAsStringSync(_stub);
    if (!Platform.isWindows) Process.runSync('chmod', ['+x', stub.path]);
    shimExe(stub.path);
    log = File('${dir.path}/log.txt');
  });
  tearDown(() => dir.deleteSync(recursive: true));

  Map<String, String> env({String out = '', int exit = 0}) {
    final sep = Platform.isWindows ? ';' : ':';
    return {
      ...Platform.environment,
      'PATH': '${dir.path}$sep${Platform.environment['PATH'] ?? ''}',
      'STUB_LOG': log.path.replaceAll(r'\', '/'),
      'STUB_OUT': out,
      'STUB_EXIT': '$exit',
    };
  }

  Future<String> convert(
    String path, {
    String out = '',
    int exit = 0,
    bool windows = true,
  }) => nativePath(
    path,
    bash!,
    windows: windows,
    environment: env(out: out, exit: exit),
  );

  group('nativePath', () {
    test('accepts the drive form and strips the newline', () async {
      expect(
        await convert('/tmp/m.txt', out: r'C:/Users/x/m.txt\n'),
        'C:/Users/x/m.txt',
      );
      expect(log.readAsStringSync().trim(), '-m -- /tmp/m.txt');
    });

    test('strips a CR before the newline', () async {
      expect(
        await convert('/tmp/m.txt', out: r'C:/Users/x/m.txt\r\n'),
        'C:/Users/x/m.txt',
      );
    });

    test('accepts the UNC form', () async {
      expect(
        await convert('//server/share/m.txt', out: r'//server/share/m.txt\n'),
        '//server/share/m.txt',
      );
      expect(log.readAsStringSync().trim(), '-m -- //server/share/m.txt');
    });

    for (final (name, out, exit) in [
      ('a non-zero exit', r'C:/Users/x/m.txt\n', 1),
      ('empty output', '', 0),
      ('a newline only', r'\n', 0),
      ('relative output', r'tmp/m.txt\n', 0),
      ('a POSIX path as output', r'/tmp/m.txt\n', 0),
    ]) {
      test('rejects $name and names the path', () async {
        await expectLater(
          convert('/tmp/m.txt', out: out, exit: exit),
          throwsA(
            isA<BadPathException>().having((e) => e.path, 'path', '/tmp/m.txt'),
          ),
        );
      });
    }

    test('a drive-form path runs no cygpath', () async {
      expect(await convert('C:/x/m.txt'), 'C:/x/m.txt');
      expect(await convert(r'C:\x\m.txt'), r'C:\x\m.txt');
      expect(log.existsSync(), isFalse);
    });

    test('a relative path runs no cygpath', () async {
      expect(await convert('m.txt'), 'm.txt');
      expect(await convert('./a/m.txt'), './a/m.txt');
      expect(log.existsSync(), isFalse);
    });

    test('a POSIX path off Windows runs no cygpath', () async {
      expect(await convert('/tmp/m.txt', windows: false), '/tmp/m.txt');
      expect(log.existsSync(), isFalse);
    });

    test('the doc comment carries constraint C7', () {
      final source = File('lib/src/commit/paths.dart')
          .readAsStringSync()
          .replaceAll(RegExp(r'\s*\r?\n\s*///\s*'), ' ');
      expect(
        source,
        contains(
          'On Windows, path arguments starting with `/` are converted with '
          '`cygpath -m` through the handoff\'s bash before any use, because '
          'the stdin handoff skips Git Bash\'s own argument conversion.',
        ),
      );
    });
  }, skip: bash == null ? 'no bash on this machine' : false);
}
