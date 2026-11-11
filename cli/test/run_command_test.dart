import 'dart:convert';
import 'dart:io';

import 'package:specwright_cli/src/commands/run.dart';
import 'package:specwright_cli/src/process/resolve.dart';
import 'package:specwright_cli/src/process/transport.dart';
import 'package:test/test.dart';

void main() {
  group('parseRunArgs', () {
    test('flags, the separator and the command', () {
      final run = parseRunArgs([
        '--bounded',
        '--paged',
        '--secret',
        '--',
        'gh',
        'api',
        '--bounded',
      ])!;
      expect(run.paged, isTrue);
      expect(run.secret, isTrue);
      expect(run.command, ['gh', 'api', '--bounded']);
    });

    test('flags default to off', () {
      final run = parseRunArgs(['--bounded', '--', 'x'])!;
      expect((run.paged, run.secret), (false, false));
    });

    for (final bad in [
      <String>['--bounded', 'x'],
      ['--bounded', '--'],
      ['--bounded', '--bogus', '--', 'x'],
      ['--', 'x'],
      <String>[],
    ]) {
      test('$bad is invalid', () => expect(parseRunArgs(bad), isNull));
    }
  });

  group('resolveCommand', () {
    bool Function(String) files(Set<String> present) => present.contains;

    test('a path separator is used as given', () {
      expect(
        resolveCommand(
          'bin/tool',
          {'PATH': '/x'},
          windows: false,
          isFile: files({'bin/tool'}),
        ),
        'bin/tool',
      );
      expect(
        resolveCommand('bin/none', {}, windows: false, isFile: files({})),
        isNull,
      );
    });

    test('POSIX walks PATH in order', () {
      expect(
        resolveCommand(
          'gh',
          {'PATH': '/a:/b'},
          windows: false,
          isFile: files({'/a/gh', '/b/gh'}),
        ),
        '/a/gh',
      );
    });

    test('Windows tries PATHEXT in order, per directory', () {
      final present = files({r'C:\a\gh.cmd', r'C:\b\gh.exe'});
      expect(
        resolveCommand(
          'gh',
          {'Path': r'C:\a;C:\b', 'PATHEXT': '.EXE;.CMD'},
          windows: true,
          isFile: present,
        ),
        r'C:\a\gh.cmd',
      );
      expect(
        resolveCommand(
          'gh',
          {'PATH': r'C:\b;C:\a'},
          windows: true,
          isFile: present,
        ),
        r'C:\b\gh.exe',
      );
    });

    test('Windows default PATHEXT is COM, EXE, BAT, CMD', () {
      expect(
        resolveCommand(
          'tool',
          {'PATH': r'C:\a'},
          windows: true,
          isFile: files({r'C:\a\tool.bat', r'C:\a\tool.cmd'}),
        ),
        r'C:\a\tool.bat',
      );
    });

    test('a name that is already an executable name resolves', () {
      expect(
        resolveCommand(
          'gh.exe',
          {'PATH': r'C:\a'},
          windows: true,
          isFile: files({r'C:\a\gh.exe'}),
        ),
        r'C:\a\gh.exe',
      );
    });

    test('nothing found is null', () {
      expect(
        resolveCommand('gh', {'PATH': '/a'}, windows: false, isFile: files({})),
        isNull,
      );
    });
  });

  group('transportFor', () {
    test('only a Windows bash -c with a name is transported', () {
      for (final cmd in [
        ['bash', '-c', 'echo'],
        ['sh', '-c', 'echo', 'n', 'a'],
        ['git', 'status'],
      ]) {
        final t = transportFor(cmd, windows: true);
        expect(t.command, cmd);
        expect(t.stdinBytes, isEmpty);
      }
      final posix = transportFor([
        'bash',
        '-c',
        'echo',
        'n',
        'a',
      ], windows: false);
      expect(posix.command, ['bash', '-c', 'echo', 'n', 'a']);
      expect(posix.stdinBytes, isEmpty);
    });

    test('arguments after the name go NUL-separated with an end marker', () {
      final t = transportFor([
        r'C:\Git\usr\bin\bash.exe',
        '-c',
        'echo "\$1"',
        'name',
        'a b',
        'é',
      ], windows: true);
      expect(t.command.length, 4);
      expect(t.command[0], r'C:\Git\usr\bin\bash.exe');
      expect(t.command[1], '-c');
      expect(t.command[2], startsWith(argvPrelude));
      expect(t.command[2], endsWith('; echo "\$1"'));
      expect(t.command[3], 'name');
      expect(utf8.decode(t.stdinBytes), 'a b\x00é\x00$argvEndMarker\x00');
    });

    test('no arguments after the name sends just the marker', () {
      final t = transportFor(['bash', '-c', 'x', 'name'], windows: true);
      expect(utf8.decode(t.stdinBytes), '$argvEndMarker\x00');
    });
  });

  // native-cli-launcher D5: input the launcher cannot represent is refused
  // first, with exit 2 and no process. A NUL cannot be put in a real argv, so
  // the black-box evals cannot reach this; the command line is given here.
  group('sw run --bounded input checks', () {
    Future<(int, String)> run(
      List<String> command,
      Map<String, String> env,
    ) async {
      final err = StringBuffer();
      final code = await runCommand(
        ['--bounded', '--', ...command],
        err: err,
        writeOut: (_) {},
        writeErr: (_) {},
        env: env,
      );
      return (code, err.toString());
    }

    test('a NUL argument is unrepresentable and nothing starts', () async {
      final (code, err) = await run(['tool', 'a\x00b'], {'PATH': ''});
      expect(code, 2);
      expect(err, 'bounded: unrepresentable argument: tool\n');
    });

    test(
      'a NUL argument to a batch command is not the unsafe-batch refusal',
      () async {
        final dir = Directory.systemTemp.createTempSync('sw-run-nul-');
        addTearDown(() => dir.deleteSync(recursive: true));
        File('${dir.path}/fake.cmd').writeAsStringSync('@exit /b 0\r\n');
        final (code, err) = await run(
          ['fake.cmd', 'a\x00b%PATH%'],
          {...Platform.environment, 'PATH': dir.path},
        );
        expect(code, 2);
        expect(err, 'bounded: unrepresentable argument: fake.cmd\n');
      },
      skip: Platform.isWindows
          ? false
          : 'platform: batch shims are Windows only',
    );
  });
}
