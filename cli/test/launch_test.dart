// Verifies assumptions A2 (what `Process.start` does with a NUL or a lone
// surrogate in an argument) and A4 (Windows argument quoting round-trips for
// a native executable) of the native-cli-launcher design.
@Tags(['process'])
library;

import 'dart:convert';
import 'dart:io';

import 'package:specwright_cli/src/process/launch.dart';
import 'package:specwright_cli/src/process/resolve.dart';
import 'package:test/test.dart';

import 'helper_support.dart';

const _recorder =
    'import sys, json; sys.stdout.buffer.write('
    "json.dumps(sys.argv[1:]).encode('ascii'))";

String get _python => Platform.isWindows ? 'python' : 'python3';

/// Starts the native recorder with [args] and returns what it recorded.
Future<List<String>> _record(List<String> args) async {
  final process = await Process.start(_python, ['-c', _recorder, ...args]);
  final out = process.stdout.transform(utf8.decoder).join();
  final err = process.stderr.transform(utf8.decoder).join();
  final code = await process.exitCode;
  expect(code, 0, reason: await err);
  return (jsonDecode(await out) as List<dynamic>).cast<String>();
}

void main() {
  _launchTests();

  group('A2: unrepresentable arguments', () {
    for (final entry in {
      'a NUL': 'a\u0000b',
      'a lone surrogate': 'a\uD800b',
    }.entries) {
      test('Process.start with ${entry.key} either throws or starts', () async {
        final String outcome;
        try {
          final recorded = await _record([entry.value]);
          // Recorded, not guessed: the child got one argument.
          expect(recorded, hasLength(1));
          outcome = 'child received ${jsonEncode(recorded.single)}';
        } on ProcessException {
          // D5 refuses such input before the start whatever Dart does.
          // ignore: avoid_print
          print(
            'A2 ${entry.key} on ${Platform.operatingSystem}: '
            'threw ProcessException',
          );
          return;
        } on ArgumentError catch (e) {
          // ignore: avoid_print
          print(
            'A2 ${entry.key} on ${Platform.operatingSystem}: '
            'threw ArgumentError: $e',
          );
          return;
        }
        // ignore: avoid_print
        print('A2 ${entry.key} on ${Platform.operatingSystem}: $outcome');
      });
    }
  });

  group('A4: Windows quoting round-trips', () {
    final values = <String, String>{
      'empty': '',
      'quotes': 'say "hi" and \'bye\'',
      'trailing backslashes': r'C:\dir with space\',
      'doubled trailing backslashes': r'path\',
      'backslashes before a quote': r'a\\"b',
      'spaces': 'two  spaces and a tab\there',
      '20,000 characters': List.filled(20000, 'x').join(),
    };

    for (final entry in values.entries) {
      test('${entry.key} reaches a native executable unchanged', () async {
        expect(await _record([entry.value]), [entry.value]);
      }, testOn: 'windows');
    }

    test('all values together reach a native executable unchanged', () async {
      final all = values.values.toList();
      expect(await _record(all), all);
    }, testOn: 'windows');
  });
}

// native-cli-launcher group 4: the launcher (`process/launch.dart`).

/// The environment with `PATH` set to [path] (case-insensitively on Windows,
/// where the inherited map names it `Path`), plus [extra].
Map<String, String> _env(String path, [Map<String, String> extra = const {}]) {
  final env = {...Platform.environment}
    ..removeWhere((k, _) => k.toUpperCase() == 'PATH');
  return {...env, 'PATH': path, ...extra};
}

/// The inherited `PATH`, whatever the case of its name.
String get _ownPath {
  for (final entry in Platform.environment.entries) {
    if (entry.key.toUpperCase() == 'PATH') return entry.value;
  }
  return '';
}

/// A tool in [dir] named [name] that runs the Python [source]: `<name>.cmd`
/// on Windows, an executable `<name>` elsewhere. Returns its path.
String _pyTool(Directory dir, String name, String source) {
  final script = File('${dir.path}${Platform.pathSeparator}$name.py')
    ..writeAsStringSync(source);
  if (Platform.isWindows) {
    final cmd = File('${dir.path}\\$name.cmd')
      ..writeAsStringSync('@"python" "${script.path}"\r\n');
    return cmd.path;
  }
  // The interpreter by absolute path: a test gives the tool a PATH of its own
  // (`:/bin`), on which `python3` would not be found.
  final tool = File('${dir.path}/$name')
    ..writeAsStringSync(
      '#!/bin/sh\nexec "${_pythonOnOwnPath()}" "${script.path}"\n',
    );
  Process.runSync('chmod', ['+x', tool.path]);
  return tool.path;
}

/// `python3` as the inherited `PATH` finds it, as an absolute path.
String _pythonOnOwnPath() {
  for (final entry in _ownPath.split(':')) {
    if (entry.isEmpty) continue;
    final candidate = File('$entry/python3');
    if (candidate.existsSync()) return candidate.path;
  }
  throw StateError('python3 is not on PATH');
}

String _real(String path) => Directory(path).resolveSymbolicLinksSync();

/// Deletes [dir]. On Windows a tool the launcher killed releases its working
/// directory a moment after the kill returns (job termination is not
/// synchronous), so a sharing violation is retried for up to 10 s. A process
/// that really outlives its call, a sleeping tool for instance, holds the
/// directory longer and the final attempt throws.
Future<void> _deleteWhenFree(Directory dir) async {
  final until = DateTime.now().add(const Duration(seconds: 10));
  while (true) {
    try {
      dir.deleteSync(recursive: true);
      return;
    } on FileSystemException {
      if (!Platform.isWindows || DateTime.now().isAfter(until)) rethrow;
      await Future<void>.delayed(const Duration(milliseconds: 100));
    }
  }
}

const _posixOnly = 'POSIX behaviour (needs CI on Linux/macOS)';
const _windowsOnly = 'Windows behaviour (Windows only)';

void _launchTests() {
  late Directory dir;
  setUp(() => dir = Directory.systemTemp.createTempSync('sw-launch-'));
  tearDown(() => _deleteWhenFree(dir));

  // The real helper, for `.cmd` runs on Windows.
  late Directory built;
  late List<String> helper;
  setUpAll(() async {
    if (!Platform.isWindows) return;
    built = Directory.systemTemp.createTempSync('sw-launch-helper-');
    helper = await buildHelper(built);
  });
  tearDownAll(() {
    if (Platform.isWindows) built.deleteSync(recursive: true);
  });

  group('lookup, exit status and stdin', () {
    test('stdin reaches the launched tool', () async {
      Process.runSync('git', ['init', '-q'], workingDirectory: dir.path);
      File('${dir.path}/.gitignore').writeAsStringSync('*.log\n');
      final result = await launch(
        ['git', 'check-ignore', '-z', '--stdin'],
        cwd: dir.path,
        input: utf8.encode('a.log\x00b.txt\x00'),
      );
      expect(result.exitCode, 0, reason: utf8.decode(result.stderr));
      expect(utf8.decode(result.stdout), 'a.log\x00');
    });

    test('lookup consults only the call\'s directory for relative entries', () {
      final seen = <String>[];
      final found = resolveCommand(
        'git',
        {'PATH': ':/usr/bin'},
        windows: false,
        workingDirectory: '/work/b',
        isFile: (path) {
          seen.add(path);
          return path == '/usr/bin/git';
        },
      );
      expect(found, '/usr/bin/git');
      expect(seen.first, '/work/b/git');
      expect(
        seen.where(
          (p) => !p.startsWith('/usr/bin') && !p.startsWith('/work/b'),
        ),
        isEmpty,
        reason: 'checked against another directory: $seen',
      );
    });

    test('relative lookup resolves in the call\'s directory', () async {
      final bin = Directory('${dir.path}/bin')..createSync();
      final b = Directory('${dir.path}/b')..createSync();
      _pyTool(bin, 'git', 'import os\nprint("later " + os.getcwd())\n');
      // PATH starts with an empty entry, the current directory, which for
      // this call is B and holds no `git`: the one later on PATH runs, in B.
      final result = await launch(
        ['git', 'status'],
        cwd: b.path,
        environment: _env(':${bin.path}'),
      );
      expect(result.exitCode, 0, reason: utf8.decode(result.stderr));
      final out = utf8.decode(result.stdout).trim();
      expect(out, startsWith('later '));
      expect(_real(out.substring('later '.length)), _real(b.path));
    }, skip: Platform.isWindows ? _posixOnly : false);

    test(
      'a tool in the call\'s directory is found by the empty entry',
      () async {
        final b = Directory('${dir.path}/b')..createSync();
        _pyTool(b, 'sw-here', 'print("here")\n');
        final result = await launch(
          ['sw-here'],
          cwd: b.path,
          environment: _env(':/nonexistent'),
        );
        expect(utf8.decode(result.stdout).trim(), 'here');
        expect(result.exitCode, 0);
      },
      skip: Platform.isWindows ? _posixOnly : false,
    );

    test('a missing command is 127 and names the command', () async {
      final result = await launch(['sw-no-such-tool-xyz', 'a'], cwd: dir.path);
      expect(result.exitCode, 127);
      expect(result.stdout, isEmpty);
      expect(utf8.decode(result.stderr), contains('sw-no-such-tool-xyz'));
      expect(utf8.decode(result.stderr), contains('command not found'));
    });

    test('a missing directory is 127 and nothing starts', () async {
      final marker = File('${dir.path}/ran');
      final tool = _pyTool(
        dir,
        'marker',
        'open(r"${marker.path}", "w").close()\n',
      );
      final result = await launch([tool], cwd: '${dir.path}/no-such-dir');
      expect(result.exitCode, 127);
      expect(result.stdout, isEmpty);
      expect(result.stderr, isNotEmpty);
      expect(marker.existsSync(), isFalse);
    });

    test('an extensionless file is not found on Windows (D9)', () async {
      File('${dir.path}\\sw-bare').writeAsStringSync('echo hi\r\n');
      final result = await launch(
        ['sw-bare'],
        cwd: dir.path,
        environment: _env(dir.path),
      );
      expect(result.exitCode, 127);
      expect(utf8.decode(result.stderr), contains('sw-bare'));
    }, skip: Platform.isWindows ? false : _windowsOnly);

    test('the environment given is the whole environment', () async {
      final tool = _pyTool(
        dir,
        'envtool',
        'import os\nprint(os.environ.get("SW_LAUNCH_X"), '
            'os.environ.get("SW_LAUNCH_GONE"))\n',
      );
      final result = await launch(
        [tool],
        cwd: dir.path,
        environment: _env(_ownPath, {'SW_LAUNCH_X': 'a b=c'}),
        helperCommand: Platform.isWindows ? helper : null,
      );
      expect(result.exitCode, 0, reason: utf8.decode(result.stderr));
      expect(utf8.decode(result.stdout).trim(), 'a b=c None');
    });

    test('a tool ended by SIGTERM is 143', () async {
      final tool = File('${dir.path}/term')
        ..writeAsStringSync('#!/bin/sh\nkill -TERM \$\$\nsleep 5\n');
      Process.runSync('chmod', ['+x', tool.path]);
      final result = await launch([tool.path], cwd: dir.path);
      expect(result.exitCode, 143);
    }, skip: Platform.isWindows ? _posixOnly : false);
  });

  group('bounds', () {
    const mib = 1024 * 1024;

    test(
      'an unbounded batch run passes 40 MiB (Windows)',
      () async {
        final tool = _pyTool(
          dir,
          'loud',
          'import sys\nsys.stdout.buffer.write(b"x" * ${40 * mib})\n',
        );
        final result = await launch(
          [tool],
          cwd: dir.path,
          environment: _env(_ownPath),
          helperCommand: helper,
        );
        expect(result.exitCode, 0, reason: utf8.decode(result.stderr));
        expect(result.outputTooLarge, isFalse);
        expect(result.stdout, hasLength(40 * mib));
      },
      skip: Platform.isWindows ? false : _windowsOnly,
      timeout: const Timeout(Duration(minutes: 3)),
    );

    test(
      'held batch output cannot report success (Windows)',
      () async {
        final tool = _pyTool(
          dir,
          'held-output',
          'import subprocess, sys\n'
              'subprocess.Popen([sys.executable, "-c", '
              '"import time; time.sleep(60)"], stdin=subprocess.DEVNULL)\n'
              'print("incomplete output", flush=True)\n',
        );
        final result = await launch(
          [tool],
          cwd: dir.path,
          environment: _env(_ownPath),
          helperCommand: helper,
        );
        expect(result.exitCode, 127);
        expect(result.stdout, isEmpty);
        expect(utf8.decode(result.stderr), contains(tool));
      },
      skip: Platform.isWindows ? false : _windowsOnly,
      timeout: const Timeout(Duration(minutes: 3)),
    );

    test('a capped call bounds stdout only', () async {
      final tool = _pyTool(
        dir,
        'noisy',
        'import sys\n'
            'sys.stderr.buffer.write(b"e" * ${40 * mib})\n'
            'sys.stderr.flush()\n'
            'sys.stdout.buffer.write(b"ok")\n'
            'sys.exit(3)\n',
      );
      final result = await launch(
        [tool],
        cwd: dir.path,
        stdoutCap: mib,
        environment: _env(_ownPath),
        helperCommand: Platform.isWindows ? helper : null,
      );
      expect(result.outputTooLarge, isFalse);
      expect(result.exitCode, 3);
      expect(utf8.decode(result.stdout), 'ok');
      expect(result.stderr, hasLength(40 * mib));
    }, timeout: const Timeout(Duration(minutes: 3)));

    test('a capped call stops on stdout overflow', () async {
      final tool = _pyTool(
        dir,
        'flood',
        'import sys, time\n'
            'sys.stdout.buffer.write(b"x" * ${4 * mib})\n'
            'sys.stdout.flush()\n'
            'time.sleep(30)\n',
      );
      final watch = Stopwatch()..start();
      final result = await launch(
        [tool],
        cwd: dir.path,
        stdoutCap: mib,
        environment: _env(_ownPath),
        helperCommand: Platform.isWindows ? helper : null,
      );
      expect(result.outputTooLarge, isTrue);
      expect(watch.elapsed, lessThan(const Duration(seconds: 25)));
    }, timeout: const Timeout(Duration(minutes: 3)));
  });

  group('input the launcher cannot represent', () {
    test('a lone surrogate is refused before the start', () async {
      final marker = File('${dir.path}/ran');
      final tool = _pyTool(
        dir,
        'marker',
        'open(r"${marker.path}", "w").close()\n',
      );
      await expectLater(
        launch([tool, 'a\uD800b'], cwd: dir.path),
        throwsA(
          isA<Unrepresentable>()
              .having((e) => e.command, 'command', tool)
              .having((e) => e.what, 'what', 'argument'),
        ),
      );
      expect(marker.existsSync(), isFalse, reason: 'the tool started');
    });

    test('a NUL anywhere in the input is Unrepresentable', () async {
      final cases = <String, Future<Object?> Function()>{
        'argument': () => launch(['tool', 'a\x00b'], cwd: dir.path),
        'command': () => launch(['to\x00ol'], cwd: dir.path),
        'environment variable name': () =>
            launch(['tool'], cwd: dir.path, environment: {'A\x00B': 'v'}),
        'environment variable value': () =>
            launch(['tool'], cwd: dir.path, environment: {'AB': 'v\x00'}),
        'working directory': () => launch(['tool'], cwd: '${dir.path}\x00'),
      };
      for (final entry in cases.entries) {
        await expectLater(
          entry.value(),
          throwsA(isA<Unrepresentable>()),
          reason: entry.key,
        );
      }
    });

    test('a lone surrogate anywhere is refused, a pair is not', () {
      expect(
        () =>
            checkLaunchInput(['tool'], cwd: '/', environment: {'A': '\uDC00'}),
        throwsA(isA<Unrepresentable>()),
      );
      expect(
        () => checkLaunchInput(['tool'], cwd: '/a\uD800'),
        throwsA(isA<Unrepresentable>()),
      );
      checkLaunchInput(['tool', '\u{1F600}'], cwd: '/');
    });

    test('a NUL in a batch argument is unrepresentable, not unsafe', () async {
      final tool = _pyTool(dir, 'batch', 'print("x")\n');
      await expectLater(
        launch([tool, 'a\x00b'], cwd: dir.path),
        throwsA(isA<Unrepresentable>()),
      );
    });

    test('a Windows line over 32,767 units is refused', () {
      // `a`, a space and the argument: 32,767 units pass, one more does not.
      checkLaunchInput(['a', 'x' * 32765], cwd: '/', windows: true);
      expect(
        () => checkLaunchInput(['a', 'x' * 32766], cwd: '/', windows: true),
        throwsA(
          isA<Unrepresentable>()
              .having((e) => e.command, 'command', 'a')
              .having((e) => e.what, 'what', 'command line'),
        ),
      );
      // quoting counts: an argument with a space is wrapped in two quotes
      expect(
        () => checkLaunchInput(['a', 'x ' * 16383], cwd: '/', windows: true),
        throwsA(isA<Unrepresentable>()),
      );
      // not a limit elsewhere
      checkLaunchInput(['a', 'x' * 40000], cwd: '/', windows: false);
    });

    test('a Windows line over the limit is refused before the start', () async {
      await expectLater(
        launch(['python', 'x' * 33000], cwd: dir.path),
        throwsA(isA<Unrepresentable>()),
      );
    }, skip: Platform.isWindows ? false : _windowsOnly);
  });
}
