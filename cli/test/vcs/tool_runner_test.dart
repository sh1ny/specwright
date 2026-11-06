import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:specwright_cli/src/vcs/stop.dart';
import 'package:specwright_cli/src/vcs/tool_runner.dart';
import 'package:test/test.dart';

import 'bash_support.dart';

List<int> _record(String text) => [...utf8.encode(text), 0];

/// `printf '%s\0' args...` prints each argument followed by a NUL.
const _printArgs = ['printf', r'%s\0'];

List<String> _split(List<int> out) {
  final parts = utf8.decode(out).split('\u0000');
  expect(parts.last, isEmpty, reason: 'every argument ends with a NUL');
  return parts..removeLast();
}

void main() {
  final bash = findBash();
  final skip = bash == null ? 'no bash installed' : false;
  late Directory dir;

  setUp(() {
    dir = Directory.systemTemp.createTempSync('claude-ncv-g2-run-');
  });
  tearDown(() => dir.deleteSync(recursive: true));

  group('runTool arguments', () {
    test(
      'an argument that looks like a marker or a number is unchanged',
      () async {
        final args = ['a', '3', '__SW_ARGV_END__', '', 'b c', '-n', 'z'];
        final r = await runTool(bash!, dir.path, [..._printArgs, ...args]);
        expect(r.exitCode, 0);
        expect(_split(r.stdout), args);
      },
      skip: skip,
    );

    test(
      'braces, wildcards, quotes and backslashes are not expanded',
      () async {
        File('${dir.path}/x1.txt').writeAsStringSync('');
        File('${dir.path}/x2.txt').writeAsStringSync('');
        final args = [
          '{a,b}',
          '*.txt',
          '*',
          '?',
          '[x]*',
          '~',
          r'$HOME',
          '"q"',
          "it's",
          r'ends\',
          r'a\"b',
          'two\nlines',
          ' lead and trail ',
        ];
        final r = await runTool(bash!, dir.path, [..._printArgs, ...args]);
        expect(r.exitCode, 0);
        expect(_split(r.stdout), args);
      },
      skip: skip,
    );

    test('non-ASCII text reaches the tool as UTF-8', () async {
      final args = ['café', '€', '\u{1f600}'];
      final r = await runTool(bash!, dir.path, [..._printArgs, ...args]);
      expect(_split(r.stdout), args);
    }, skip: skip);

    test(
      'an escaped byte reaches the tool as that byte',
      () async {
        final r = await runTool(bash!, dir.path, [..._printArgs, 'a\udcffb']);
        expect(r.stdout, [0x61, 0xff, 0x62, 0]);
      },
      skip: bash == null
          ? 'no bash installed'
          : Platform.isWindows
          ? 'Windows passes arguments as UTF-16, there is no raw byte 0xFF'
          : false,
    );

    test('a NUL inside an argument is refused before anything runs', () {
      expect(
        () => runTool(bash ?? 'bash', dir.path, ['printf', 'a\u0000b']),
        throwsArgumentError,
      );
    });
  });

  group('runTool input', () {
    test('tool input after the last record reaches the tool', () async {
      final input = [...utf8.encode('first\n'), 0, ...utf8.encode('3'), 0, 10];
      final r = await runTool(bash!, dir.path, ['cat'], input: input);
      expect(r.exitCode, 0);
      expect(r.stdout, input);
    }, skip: skip);

    test('input that looks like another frame is still tool input', () async {
      final input = [..._record('2'), ..._record('x'), ..._record('y')];
      final r = await runTool(bash!, dir.path, ['cat'], input: input);
      expect(r.stdout, input);
    }, skip: skip);

    test('git check-ignore -z --stdin sees its names', () async {
      expect(
        Process.runSync('git', [
          'init',
          '-q',
        ], workingDirectory: dir.path).exitCode,
        0,
      );
      File('${dir.path}/.gitignore').writeAsStringSync('ignored.txt\n');
      final r = await runTool(
        bash!,
        dir.path,
        ['git', 'check-ignore', '-z', '--stdin'],
        input: [..._record('ignored.txt'), ..._record('kept.txt')],
      );
      expect(r.exitCode, 0);
      expect(utf8.decode(r.stdout), 'ignored.txt\u0000');
    }, skip: skip);

    test('without input stdin is closed after the records', () async {
      final r = await runTool(bash!, dir.path, ['cat']);
      expect(r.exitCode, 0);
      expect(r.stdout, isEmpty);
    }, skip: skip);
  });

  group('runTool result', () {
    test('returns the exit code and both streams as raw bytes', () async {
      final r = await runTool(bash!, dir.path, [
        'bash',
        '-c',
        r"printf 'o\377'; printf 'e\377' >&2; exit 7",
      ]);
      expect(r.exitCode, 7);
      expect(r.stdout, [0x6f, 0xff]);
      expect(r.stderr, [0x65, 0xff]);
    }, skip: skip);

    test('a missing tool exits 127', () async {
      final r = await runTool(bash!, dir.path, ['no-such-tool-vcs-g2']);
      expect(r.exitCode, 127);
    }, skip: skip);

    test('an unstartable bash exits 127 with the error text', () async {
      final r = await runTool('no-such-bash-vcs-g2', dir.path, ['cat']);
      expect(r.exitCode, 127);
      expect(r.stdout, isEmpty);
      expect(r.stderr, isNotEmpty);
    });

    test('a replacement environment reaches the tool', () async {
      final r = await runTool(
        bash!,
        dir.path,
        ['bash', '-c', r'printf %s "$VCS_G2"'],
        environment: {...Platform.environment, 'VCS_G2': 'yes'},
      );
      expect(utf8.decode(r.stdout), 'yes');
    }, skip: skip);

    test('the parent environment is inherited by default', () async {
      final key = Platform.environment.keys.firstWhere(
        (k) => RegExp(r'^[A-Za-z_][A-Za-z0-9_]*$').hasMatch(k) && k != '_',
      );
      final r = await runTool(bash!, dir.path, [
        'bash',
        '-c',
        'test -n "\${$key+set}"',
      ]);
      expect(r.exitCode, 0);
    }, skip: skip);
  });

  group('transport failures exit 126 before any tool runs', () {
    Future<void> expectRefused(List<int> stdinBytes) async {
      final marker = File('${dir.path}/ran');
      final r = await runFramed(bash!, [
        ..._record(cwdRecord(dir.path)),
        ...stdinBytes,
      ]);
      expect(r.exitCode, 126);
      expect(utf8.decode(r.stderr), contains('argument transport failed'));
      expect(marker.existsSync(), isFalse);
    }

    test('a count that is not digits', () async {
      await expectRefused([
        ..._record('x'),
        ..._record('touch'),
        ..._record('ran'),
      ]);
      await expectRefused([..._record('1x'), ..._record('touch')]);
      await expectRefused([..._record('-1'), ..._record('touch')]);
      await expectRefused([..._record(''), ..._record('touch')]);
    }, skip: skip);

    test('a zero count', () async {
      await expectRefused(_record('0'));
    }, skip: skip);

    test('an absurdly long count', () async {
      await expectRefused([..._record('9' * 40), ..._record('touch')]);
    }, skip: skip);

    test('fewer records than the count', () async {
      await expectRefused([
        ..._record('3'),
        ..._record('touch'),
        ..._record('ran'),
      ]);
    }, skip: skip);

    test('an unterminated last record', () async {
      await expectRefused([
        ..._record('2'),
        ..._record('touch'),
        ...utf8.encode('ran'),
      ]);
    }, skip: skip);

    test('empty stdin after the directory', () async {
      await expectRefused(const []);
    }, skip: skip);

    test('no stdin at all', () async {
      final r = await runFramed(bash!, const []);
      expect(r.exitCode, 126);
    }, skip: skip);
  });

  group('runToolCapped', () {
    test('returns the output when it stays within the cap', () async {
      final r = await runToolCapped(bash!, dir.path, [
        'bash',
        '-c',
        'printf 0123456789',
      ], cap: 10);
      expect(r.outputTooLarge, isFalse);
      expect(r.exitCode, 0);
      expect(utf8.decode(r.stdout), '0123456789');
    }, skip: skip);

    test(
      'kills the child once stdout goes past the cap',
      () async {
        final watch = Stopwatch()..start();
        final r = await runToolCapped(bash!, dir.path, [
          'bash',
          '-c',
          r'head -c 200000 /dev/zero | tr "\0" a; exec sleep 5',
        ], cap: 1000);
        expect(r.outputTooLarge, isTrue);
        expect(watch.elapsed, lessThan(const Duration(seconds: 15)));
      },
      skip: skip,
      timeout: const Timeout(Duration(seconds: 60)),
    );

    test('a failing tool keeps its exit code and stderr', () async {
      final r = await runToolCapped(bash!, dir.path, [
        'bash',
        '-c',
        'echo nope >&2; exit 4',
      ], cap: 100);
      expect(r.exitCode, 4);
      expect(utf8.decode(r.stderr), 'nope\n');
    }, skip: skip);

    test('an unstartable bash is the tool_missing stop', () async {
      await expectLater(
        runToolCapped('no-such-bash-vcs-g2', dir.path, ['but'], cap: 10),
        throwsA(
          isA<VcsStop>()
              .having((e) => e.error, 'error', 'tool_missing')
              .having(
                (e) => e.message,
                'message',
                startsWith('but could not run: '),
              ),
        ),
      );
    });

    test('a missing directory is the tool_missing stop', () async {
      final missing = '${dir.path}/gone';
      await expectLater(
        runToolCapped(bash!, missing, ['but', 'status'], cap: 10),
        throwsA(
          isA<VcsStop>()
              .having((e) => e.error, 'error', 'tool_missing')
              .having((e) => e.code, 'code', 1)
              .having(
                (e) => e.message,
                'message',
                'but could not run: ${missingDirectoryText(missing)}',
              ),
        ),
      );
    }, skip: skip);
  });

  group('working directory', () {
    final escaped = String.fromCharCode(0xdcff);

    test('cwdRecord uses the drive form with / on Windows only', () {
      expect(cwdRecord(r'C:\Users\a b\r', windows: true), 'C:/Users/a b/r');
      expect(cwdRecord(r'/tmp/a\b', windows: false), r'/tmp/a\b');
    });

    test('the tool runs in it', () async {
      final sub = Directory('${dir.path}/sub')..createSync();
      final r = await runTool(bash!, sub.path, ['pwd']);
      expect(r.exitCode, 0);
      expect(utf8.decode(r.stdout).trim(), endsWith('/sub'));
    }, skip: skip);

    test('a CDPATH in the environment does not redirect cd or print', () async {
      Directory('${dir.path}/sub').createSync();
      final env = {...Platform.environment, 'CDPATH': dir.path};
      final r = await runTool(bash!, '${dir.path}/sub', [
        'bash',
        '-c',
        r'printf "%s|" "$CDPATH"; pwd',
      ], environment: env);
      expect(r.exitCode, 0);
      final out = utf8.decode(r.stdout);
      // The tool sees CDPATH unchanged, and cd printed nothing before it.
      expect(out, startsWith('${dir.path}|'));
      expect(out.trim(), endsWith('/sub'));
      expect(r.stderr, isEmpty);
    }, skip: skip);

    test(
      'a directory with a byte that is not UTF-8 is entered',
      () async {
        final raw = Uint8List.fromList([
          ...utf8.encode(dir.path),
          0x2f,
          0x64,
          0xff,
        ]);
        Directory.fromRawPath(raw).createSync();
        final r = await runTool(bash!, '${dir.path}/d$escaped', ['pwd']);
        expect(r.exitCode, 0);
        expect(r.stdout, contains(0xff));
      },
      skip: bash == null
          ? 'no bash installed'
          : Platform.isLinux
          ? false
          : 'Linux only: macOS (APFS) refuses names that are not valid UTF-8, '
                'and Windows names are UTF-16',
    );

    test('a missing directory starts nothing and gives exit 127', () async {
      final missing = '${dir.path}/gone';
      final r = await runTool(bash!, missing, ['touch', '${dir.path}/ran']);
      expect(r.exitCode, 127);
      expect(r.stdout, isEmpty);
      expect(utf8.decode(r.stderr), missingDirectoryText(missing));
      expect(File('${dir.path}/ran').existsSync(), isFalse);
    }, skip: skip);

    test("the missing-directory text is Python's str(OSError)", () {
      expect(
        missingDirectoryText('/x/y', windows: false),
        "[Errno 2] No such file or directory: '/x/y'",
      );
      expect(
        missingDirectoryText('C:/x/y', windows: true),
        '[WinError 267] The directory name is invalid',
      );
    });

    test("the text quotes the directory as Python's repr does", () {
      String t(String d) => missingDirectoryText(d, windows: false);
      const head = '[Errno 2] No such file or directory: ';
      expect(t("/it's"), '$head"/it\'s"');
      expect(t('/a"b\'c'), "$head'/a\"b\\'c'");
      expect(t(r'/a\b'), "$head'/a\\\\b'");
      expect(t('/n\nl'), "$head'/n\\nl'");
      expect(t('/d$escaped'), "$head'/d\\udcff'");
    });

    test(
      'a directory removed before the prelude enters it exits 127, silent',
      () async {
        final r = await runFramed(bash!, [
          ..._record('${dir.path}/gone'),
          ...frameArguments(['touch', '${dir.path}/ran']),
        ]);
        expect(r.exitCode, 127);
        expect(r.stdout, isEmpty);
        expect(r.stderr, isEmpty);
        expect(File('${dir.path}/ran').existsSync(), isFalse);
      },
      skip: skip,
    );
  });
}
