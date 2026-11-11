import 'dart:convert';
import 'dart:io';

import 'package:specwright_cli/src/vcs/stop.dart';
import 'package:specwright_cli/src/vcs/tool_runner.dart';
import 'package:test/test.dart';

import 'bash_support.dart';

List<int> _record(String text) => [...utf8.encode(text), 0];

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
    dir = Directory.systemTemp.createTempSync('claude-ncv-g4-run-');
  });
  tearDown(() => dir.deleteSync(recursive: true));

  /// `bash -c <script> sh <args>`: a tool that reads its arguments and stdin.
  List<String> sh(String script, [List<String> args = const []]) => [
    bash!,
    '-c',
    script,
    'sh',
    ...args,
  ];

  /// A native tool (not an MSYS one, which expands wildcards in its own
  /// arguments) that prints each argument as UTF-8 followed by a NUL.
  List<String> printArgs(List<String> args) => [
    Platform.isWindows ? 'python' : 'python3',
    '-c',
    r"import sys;sys.stdout.buffer.write(b''.join(a.encode()+b'\0' for a in sys.argv[1:]))",
    ...args,
  ];

  group('runTool arguments', () {
    test(
      'an argument that looks like a marker or a number is unchanged',
      () async {
        final args = ['a', '3', '__SW_ARGV_END__', '', 'b c', '-n', 'z'];
        final r = await runTool(dir.path, printArgs(args));
        expect(r.exitCode, 0);
        expect(_split(r.stdout), args);
      },
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
        final r = await runTool(dir.path, printArgs(args));
        expect(r.exitCode, 0);
        expect(_split(r.stdout), args);
      },
    );

    test('non-ASCII text reaches the tool as UTF-8', () async {
      final args = ['café', '€', '\u{1f600}'];
      final r = await runTool(dir.path, printArgs(args));
      expect(_split(r.stdout), args);
    });

    test('a NUL inside an argument is unrepresentable and starts nothing', () {
      final marker = File('${dir.path}/ran');
      expect(
        () => runTool(dir.path, sh('touch ran; : "\$1"', ['a\u0000b'])),
        throwsA(
          isA<Unrepresentable>().having((e) => e.what, 'what', 'argument'),
        ),
      );
      expect(marker.existsSync(), isFalse);
    }, skip: skip);

    test('a lone surrogate in an argument is unrepresentable', () {
      expect(
        () => runTool(dir.path, ['tool', 'a\udcffb']),
        throwsA(
          isA<Unrepresentable>()
              .having((e) => e.command, 'command', 'tool')
              .having((e) => e.what, 'what', 'argument'),
        ),
      );
    });
  });

  group('runTool input', () {
    test('tool input reaches the tool', () async {
      final input = [...utf8.encode('first\n'), 0, ...utf8.encode('3'), 0, 10];
      final r = await runTool(dir.path, sh('cat'), input: input);
      expect(r.exitCode, 0);
      expect(r.stdout, input);
    }, skip: skip);

    test('input that looks like a frame is still tool input', () async {
      final input = [..._record('2'), ..._record('x'), ..._record('y')];
      final r = await runTool(dir.path, sh('cat'), input: input);
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
        dir.path,
        ['git', 'check-ignore', '-z', '--stdin'],
        input: [..._record('ignored.txt'), ..._record('kept.txt')],
      );
      expect(r.exitCode, 0);
      expect(utf8.decode(r.stdout), 'ignored.txt\u0000');
    });

    test('without input stdin is closed', () async {
      final r = await runTool(dir.path, sh('cat'));
      expect(r.exitCode, 0);
      expect(r.stdout, isEmpty);
    }, skip: skip);
  });

  group('runTool result', () {
    test('returns the exit code and both streams as raw bytes', () async {
      final r = await runTool(
        dir.path,
        sh(r"printf 'o\377'; printf 'e\377' >&2; exit 7"),
      );
      expect(r.exitCode, 7);
      expect(r.stdout, [0x6f, 0xff]);
      expect(r.stderr, [0x65, 0xff]);
      expect(r.startFailed, isFalse);
    }, skip: skip);

    test('a missing tool exits 127 and names it', () async {
      final r = await runTool(dir.path, ['no-such-tool-vcs-g4']);
      expect(r.exitCode, 127);
      expect(r.stdout, isEmpty);
      expect(r.startFailed, isTrue);
      expect(utf8.decode(r.stderr), 'no-such-tool-vcs-g4: command not found\n');
    });

    test('a replacement environment reaches the tool', () async {
      final r = await runTool(
        dir.path,
        sh(r'printf %s "$VCS_G4"'),
        environment: {...Platform.environment, 'VCS_G4': 'yes'},
      );
      expect(utf8.decode(r.stdout), 'yes');
    }, skip: skip);

    test('the parent environment is inherited by default', () async {
      final key = Platform.environment.keys.firstWhere(
        (k) => RegExp(r'^[A-Za-z_][A-Za-z0-9_]*$').hasMatch(k) && k != '_',
      );
      final r = await runTool(dir.path, sh('test -n "\${$key+set}"'));
      expect(r.exitCode, 0);
    }, skip: skip);
  });

  group('runToolCapped', () {
    test('returns the output when it stays within the cap', () async {
      final r = await runToolCapped(dir.path, sh('printf 0123456789'), cap: 10);
      expect(r.outputTooLarge, isFalse);
      expect(r.exitCode, 0);
      expect(utf8.decode(r.stdout), '0123456789');
    }, skip: skip);

    test(
      'kills the child once stdout goes past the cap',
      () async {
        final watch = Stopwatch()..start();
        final r = await runToolCapped(
          dir.path,
          sh(r'head -c 200000 /dev/zero | tr "\0" a; exec sleep 5'),
          cap: 1000,
        );
        expect(r.outputTooLarge, isTrue);
        expect(watch.elapsed, lessThan(const Duration(seconds: 15)));
      },
      skip: skip,
      timeout: const Timeout(Duration(seconds: 60)),
    );

    test('a failing tool keeps its exit code and stderr', () async {
      final r = await runToolCapped(
        dir.path,
        sh('echo nope >&2; exit 4'),
        cap: 100,
      );
      expect(r.exitCode, 4);
      expect(utf8.decode(r.stderr), 'nope\n');
    }, skip: skip);

    test('a missing tool is the tool_missing stop', () async {
      await expectLater(
        runToolCapped(dir.path, ['no-such-but-vcs-g4'], cap: 10),
        throwsA(
          isA<VcsStop>()
              .having((e) => e.error, 'error', 'tool_missing')
              .having(
                (e) => e.message,
                'message',
                'no-such-but-vcs-g4 could not run: '
                    'no-such-but-vcs-g4: command not found',
              ),
        ),
      );
    });

    test('a missing directory is the tool_missing stop', () async {
      final missing = '${dir.path}/gone';
      await expectLater(
        runToolCapped(missing, ['but', 'status'], cap: 10),
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
    });
  });

  group('working directory', () {
    final escaped = String.fromCharCode(0xdcff);

    test('the tool runs in it', () async {
      final sub = Directory('${dir.path}/sub')..createSync();
      final r = await runTool(sub.path, sh('pwd'));
      expect(r.exitCode, 0);
      expect(utf8.decode(r.stdout).trim(), endsWith('/sub'));
    }, skip: skip);

    test('a missing directory starts nothing and gives exit 127', () async {
      final missing = '${dir.path}/gone';
      final r = await runTool(missing, sh('touch "\$1"', ['${dir.path}/ran']));
      expect(r.exitCode, 127);
      expect(r.stdout, isEmpty);
      expect(utf8.decode(r.stderr), '${missingDirectoryText(missing)}\n');
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

    test('a directory that is not well-formed Unicode is unrepresentable', () {
      expect(
        () => runTool('${dir.path}/d$escaped', ['tool']),
        throwsA(
          isA<Unrepresentable>().having(
            (e) => e.what,
            'what',
            'working directory',
          ),
        ),
      );
    });
  });
}
