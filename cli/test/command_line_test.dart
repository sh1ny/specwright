import 'package:specwright_cli/src/process/command_line.dart';
import 'package:specwright_cli/src/process/resolve.dart';
import 'package:test/test.dart';

void main() {
  // D5 on Linux and macOS CI too: the check takes the platform as a parameter.
  test('the Windows command-line limit is checked on every host', () {
    checkCommandLine('tool', ['tool', 'x' * 100], windows: true);
    checkCommandLine('tool', ['tool', 'x' * 40000], windows: false);
    expect(
      () => checkCommandLine('tool', ['tool', 'x' * 40000], windows: true),
      throwsA(
        isA<Unrepresentable>()
            .having((e) => e.command, 'command', 'tool')
            .having((e) => e.what, 'what', 'command line'),
      ),
    );
  });

  group('quoteBatchLine', () {
    test('quotes the path and every argument, empty included', () {
      expect(
        quoteBatchLine(r'C:\bin\fake.cmd', ['a b', '', 'x']),
        r'"C:\bin\fake.cmd" "a b" "" "x"',
      );
    });

    test('shell metacharacters stay as they are, never caret-escaped', () {
      expect(
        quoteBatchLine('f.cmd', ['a&b', 'c|d', '<e>', '(f)', 'g^h']),
        '"f.cmd" "a&b" "c|d" "<e>" "(f)" "g^h"',
      );
    });

    test('trailing backslashes are doubled, others are left alone', () {
      expect(
        quoteBatchLine('f.cmd', [r'C:\two words\', r'D:\x\\', r'a\b', r'\']),
        r'"f.cmd" "C:\two words\\" "D:\x\\\\" "a\b" "\\"',
      );
    });

    for (final arg in [
      '%PATH%',
      'a%b',
      '!x!',
      'a!b',
      'a"b',
      'a\rb',
      'a\nb',
      'a\x00b',
    ]) {
      test('refuses ${arg.codeUnits}', () {
        expect(
          () => quoteBatchLine('f.cmd', ['ok', arg]),
          throwsA(isA<UnsafeBatchArgument>()),
        );
      });
    }

    for (final path in [r'C:\tools\%SW_SLOT%\f.cmd', r'C:\a!b\f.cmd']) {
      test('refuses the path $path', () {
        expect(
          () => quoteBatchLine(path, []),
          throwsA(isA<UnsafeBatchArgument>()),
        );
      });
    }

    test('the line limit is 8191 characters, counting the quotes', () {
      const path = 'f.cmd'; // "f.cmd" is 7 characters, then ` "` and `"`
      final fits = 'a' * (batchLineLimit - 7 - 3);
      expect(quoteBatchLine(path, [fits]).length, batchLineLimit);
      expect(
        () => quoteBatchLine(path, ['${fits}a']),
        throwsA(isA<UnsafeBatchArgument>()),
      );
    });

    test('doubling counts toward the limit', () {
      final arg = 'a' * (batchLineLimit - 7 - 3 - 1) + r'\';
      expect(
        () => quoteBatchLine('f.cmd', [arg]),
        throwsA(isA<UnsafeBatchArgument>()),
      );
    });
  });

  group('planLaunch', () {
    test('a Windows batch file runs through cmd.exe with a raw line', () {
      final plan = planLaunch(
        r'C:\bin\fake.cmd',
        ['fake.cmd', 'a b'],
        {'COMSPEC': r'C:\nowhere\cmd.exe', 'SystemRoot': r'C:\Windows'},
        windows: true,
      );
      expect(plan.rawLine, isTrue);
      expect(plan.stdinBytes, isEmpty);
      expect(plan.command[0], r'C:\Windows\System32\cmd.exe');
      expect(
        plan.command[1],
        r'"C:\Windows\System32\cmd.exe" /d /s /c ""C:\bin\fake.cmd" "a b""',
      );
    });

    test('a batch file is not special off Windows', () {
      final plan = planLaunch('/x/f.cmd', ['f.cmd', '%x%'], {}, windows: false);
      expect(plan.rawLine, isFalse);
      expect(plan.command, ['/x/f.cmd', '%x%']);
    });

    test('a native executable starts directly with its arguments', () {
      final plan = planLaunch(
        r'C:\bin\tool.exe',
        ['tool', 'a "b"', '%x%'],
        {},
        windows: true,
      );
      expect(plan.rawLine, isFalse);
      expect(plan.command, [r'C:\bin\tool.exe', 'a "b"', '%x%']);
      expect(plan.stdinBytes, isEmpty);
    });

    test('an unsafe batch argument is refused before a plan exists', () {
      expect(
        () => planLaunch('f.cmd', ['f.cmd', '%x%'], {}, windows: true),
        throwsA(isA<UnsafeBatchArgument>()),
      );
    });
  });

  group('resolveCommand with an empty POSIX PATH entry (#202)', () {
    bool Function(String) files(Set<String> present) => present.contains;

    test('a leading empty entry is the current directory, searched first', () {
      expect(
        resolveCommand(
          'tool',
          {'PATH': ':/usr/bin'},
          windows: false,
          isFile: files({'./tool', '/usr/bin/tool'}),
        ),
        './tool',
      );
    });

    test('a trailing empty entry keeps its position', () {
      expect(
        resolveCommand(
          'tool',
          {'PATH': '/usr/bin:'},
          windows: false,
          isFile: files({'./tool', '/usr/bin/tool'}),
        ),
        '/usr/bin/tool',
      );
    });

    test('an empty entry between two colons is the current directory', () {
      expect(
        resolveCommand(
          'tool',
          {'PATH': '/a::/usr/bin'},
          windows: false,
          isFile: files({'./tool', '/usr/bin/tool'}),
        ),
        './tool',
      );
    });

    test('no empty entry, no current directory', () {
      expect(
        resolveCommand(
          'tool',
          {'PATH': '/usr/bin'},
          windows: false,
          isFile: files({'./tool'}),
        ),
        isNull,
      );
    });

    test('a relative name keeps its `..` after a link on POSIX', () {
      final seen = <String>[];
      final found = resolveCommand(
        'link/../tool',
        {'PATH': '/usr/bin'},
        windows: false,
        workingDirectory: '/work',
        isFile: (path) {
          seen.add(path);
          return true;
        },
      );
      expect(found, '/work/link/../tool');
      expect(seen, ['/work/link/../tool']);
    });

    test('a relative PATH entry keeps its `..`, drops its `.`', () {
      expect(
        resolveCommand(
          'tool',
          {'PATH': './link/..//bin'},
          windows: false,
          workingDirectory: '/work',
          isFile: (path) => true,
        ),
        '/work/link/../bin/tool',
      );
    });

    test('Windows still drops empty entries', () {
      expect(
        resolveCommand(
          'tool',
          {'PATH': r';C:\bin', 'PATHEXT': '.EXE'},
          windows: true,
          isFile: files({r'.\tool.exe', r'C:\bin\tool.exe'}),
        ),
        r'C:\bin\tool.exe',
      );
    });
  });
}
