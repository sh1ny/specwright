import 'package:path/path.dart' as p;
import 'package:specwright_cli/src/vcs/walk.dart';
import 'package:test/test.dart';

/// The path helpers of the VCS walk: `os.path.join` (`walkRoot`) and the
/// relative path (`relpathText`). The directory walk itself is in
/// `test/fs/walk_test.dart`.
void main() {
  group('walkRoot (os.path.join)', () {
    test('POSIX', () {
      String j(String a, String b) => walkRoot(a, b, windows: false);
      expect(j('/r', 'work'), '/r/work');
      expect(j('/r/', 'work'), '/r/work');
      expect(j('/r', '/abs/x'), '/abs/x');
      expect(j('/r', '.'), '/r/.');
      expect(j('/r', ''), '/r/');
    });

    test('Windows', () {
      String j(String a, String b) => walkRoot(a, b, windows: true);
      expect(j(r'C:\r', 'work'), r'C:\r\work');
      expect(j(r'C:\r', r'D:\x'), r'D:\x');
      expect(j(r'C:\r', r'\x'), r'C:\x');
      expect(j(r'C:\r', r'C:\r\w'), r'C:\r\w');
      expect(j(r'C:\r', 'a/b'), r'C:\r\a/b');
    });
  });

  group('relpathText: the relative path produced for each OS style', () {
    test('POSIX', () {
      String rel(String f, String r) => relpathText(f, r, windows: false);
      expect(rel('/r/work/a.txt', '/r'), 'work/a.txt');
      expect(rel('/r/work/../work/a.txt', '/r'), 'work/a.txt');
      expect(rel('/r//work/./a.txt', '/r/'), 'work/a.txt');
      expect(rel('/o/x', '/r'), '../o/x');
      expect(rel('/r', '/r'), '.');
      expect(rel(r'/r/a\b', '/r'), 'a/b');
    });

    test('Windows treats both separators alike and ignores case', () {
      String rel(String f, String r) => relpathText(f, r, windows: true);
      expect(rel(r'C:\r\work/a.txt', r'C:\r'), 'work/a.txt');
      expect(rel(r'c:/R/Work/../Work/a.txt', r'C:\r'), 'Work/a.txt');
      expect(rel(r'C:/r', r'C:\r'), '.');
      expect(rel(r'C:\o\x', r'C:\r'), '../o/x');
    });

    test('Windows: another drive is a StateError', () {
      expect(
        () => relpathText(r'D:\x', r'C:\r', windows: true),
        throwsA(isA<StateError>()),
      );
    });

    test('a lone surrogate (an escaped raw byte) survives', () {
      expect(relpathText('/r/a\udcffb', '/r', windows: false), 'a\udcffb');
      expect(
        relpathText('C:${r'\r\a'}\udcffb', r'C:\r', windows: true),
        'a\udcffb',
      );
    });
  });

  // A4, run on package:path 1.9 with the windows style (Dart 3.13):
  //  - mixed case: relative('c:/R/Work/../Work/a.txt', from: r'C:\r') is
  //    r'Work\a.txt': the roots and components match case-insensitively and
  //    the remainder keeps the path's own case.
  //  - another drive: relative(r'D:\x', from: r'C:\r') is r'D:\x', an
  //    absolute path, never a '..' chain; callers refuse it by isAbsolute.
  //  - lone surrogates: U+DCFF in a name passes through normalize, relative
  //    and dirname unchanged.
  group('A4: package:path in the windows style', () {
    final win = p.Context(style: p.Style.windows, current: r'C:\r');
    test('compares case-insensitively', () {
      expect(
        win.relative(r'c:/R/Work/../Work/a.txt', from: r'C:\r'),
        r'Work\a.txt',
      );
      expect(win.relative(r'C:\R', from: r'c:\r'), '.');
    });
    test('another drive comes back absolute', () {
      final rel = win.relative(r'D:\x', from: r'C:\r');
      expect(rel, r'D:\x');
      expect(win.isAbsolute(rel), isTrue);
    });
    test('lone surrogates pass through', () {
      const lone = '\udcff';
      expect(win.relative('C:\\r\\a${lone}b', from: r'C:\r'), 'a${lone}b');
      expect(win.dirname('C:\\r\\a${lone}b\\c'), 'C:\\r\\a${lone}b');
      expect(win.normalize('C:\\r\\.\\a${lone}b\\..\\c'), r'C:\r\c');
    });
  });
}
