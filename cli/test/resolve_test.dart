import 'package:specwright_cli/src/process/resolve.dart';
import 'package:test/test.dart';

/// POSIX `PATH` lookup takes a file only when the process can execute it
/// (D6, C22). The regular-file check and the access check are injected.
void main() {
  bool Function(String) set(Set<String> present) => present.contains;

  group('POSIX lookup with an execute check', () {
    test('a candidate the user cannot execute is skipped', () {
      expect(
        resolveCommand(
          'tool',
          {'PATH': '/a:/b'},
          windows: false,
          isFile: set({'/a/tool', '/b/tool'}),
          canExecute: set({'/b/tool'}),
        ),
        '/b/tool',
      );
    });

    test('an executable first candidate wins over a later one', () {
      expect(
        resolveCommand(
          'tool',
          {'PATH': '/a:/b'},
          windows: false,
          isFile: set({'/a/tool', '/b/tool'}),
          canExecute: set({'/a/tool', '/b/tool'}),
        ),
        '/a/tool',
      );
    });

    test('no executable candidate is command not found', () {
      expect(
        resolveCommand(
          'tool',
          {'PATH': '/a:/b'},
          windows: false,
          isFile: set({'/a/tool', '/b/tool'}),
          canExecute: set({}),
        ),
        isNull,
      );
    });

    test('the access check sees only what the file check accepted', () {
      final asked = <String>[];
      resolveCommand(
        'tool',
        {'PATH': '/a:/b'},
        windows: false,
        isFile: set({'/b/tool'}),
        canExecute: (path) {
          asked.add(path);
          return true;
        },
      );
      expect(asked, ['/b/tool']);
    });

    test('a relative PATH entry is checked under the working directory', () {
      final asked = <String>[];
      final found = resolveCommand(
        'tool',
        {'PATH': 'bin'},
        windows: false,
        workingDirectory: '/work',
        isFile: set({'/work/bin/tool'}),
        canExecute: (path) {
          asked.add(path);
          return true;
        },
      );
      expect(found, '/work/bin/tool');
      expect(asked, ['/work/bin/tool']);
    });

    test('a name with a separator keeps the file check alone', () {
      var asked = false;
      final found = resolveCommand(
        './tool',
        {'PATH': '/a'},
        windows: false,
        isFile: set({'./tool'}),
        canExecute: (_) {
          asked = true;
          return false;
        },
      );
      expect(found, './tool');
      expect(asked, isFalse);
    });

    test('Windows does not use the access check', () {
      var asked = false;
      final found = resolveCommand(
        'tool',
        {'PATH': r'C:\a'},
        windows: true,
        isFile: set({r'C:\a\tool.exe'}),
        canExecute: (_) {
          asked = true;
          return false;
        },
      );
      expect(found, r'C:\a\tool.exe');
      expect(asked, isFalse);
    });
  });
}
