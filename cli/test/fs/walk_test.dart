import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:specwright_cli/src/fs/walk.dart';
import 'package:specwright_cli/src/vcs/codec.dart';
import 'package:test/test.dart';

/// The native directory walk (design D6): UTF-8 byte order on every OS, the
/// caller's link policy, and the U+FFFD existence and duplicate checks.
void main() {
  const posixOnly = 'POSIX only: links need developer mode on Windows';
  final posixSkip = Platform.isWindows ? posixOnly : false;
  final linuxSkip = Platform.isLinux
      ? false
      : 'Linux only: macOS (APFS) refuses names that are not valid UTF-8, '
            'and Windows names are UTF-16';
  final sep = Platform.pathSeparator;

  late Directory root;
  setUp(() {
    root = Directory.systemTemp.createTempSync('claude-ncl-g3-walk-');
  });
  tearDown(() {
    if (!Platform.isWindows) {
      Process.runSync('chmod', ['-R', 'u+rwx', root.path]);
    }
    root.deleteSync(recursive: true);
  });

  String at(String rel) => '${root.path}$sep${rel.replaceAll('/', sep)}';
  void file(String rel, [String content = 'x']) {
    final f = File(at(rel));
    f.parent.createSync(recursive: true);
    f.writeAsStringSync(content);
  }

  WalkDirectory? find(List<WalkDirectory> walk, String rel) {
    for (final d in walk) {
      if (d.rel == rel) return d;
    }
    return null;
  }

  Uint8List raw(String rel, List<int> name) =>
      Uint8List.fromList([...utf8.encode('${root.path}$sep$rel'), ...name]);

  group('the VCS policy', () {
    test('the walk lists files in UTF-8 byte order', () {
      file('b.txt');
      file('A.txt');
      file('a/z.txt');
      file('é.txt');
      expect(
        [for (final f in walkFiles(root.path)) f.name],
        ['A.txt', 'a/z.txt', 'b.txt', 'é.txt'],
      );
    });

    test('code points above U+FFFF sort after U+E000..U+FFFF by bytes', () {
      // UTF-16 code unit order would put U+1F600 (D83D DE00) before U+FF5E.
      file('\u{1f600}.txt');
      file('～.txt');
      expect(
        [for (final f in walkFiles(root.path)) f.name],
        ['～.txt', '\u{1f600}.txt'],
      );
    });

    test('whole paths sort by bytes, not directory by directory', () {
      file('a.txt');
      file('a/z.txt');
      file('a-b/y.txt');
      // '-' 0x2D < '.' 0x2E < '/' 0x2F
      expect(
        [for (final f in walkFiles(root.path)) f.name],
        ['a-b/y.txt', 'a.txt', 'a/z.txt'],
      );
    });

    test('a prefix goes in front of each name', () {
      file('sub/a.txt');
      expect(
        [for (final f in walkFiles(root.path, prefix: 'work')) f.name],
        ['work/sub/a.txt'],
      );
    });

    test('sizes come from the listed entity', () {
      file('a.txt', '12345');
      file('sub/b.txt', '12');
      expect(
        [for (final f in walkFiles(root.path)) (f.name, f.size)],
        [('a.txt', 5), ('sub/b.txt', 2)],
      );
    });

    test('directories are not listed as files', () {
      Directory(at('empty/inner')).createSync(recursive: true);
      file('real/f.txt');
      expect([for (final f in walkFiles(root.path)) f.name], ['real/f.txt']);
    });

    test('.git and .jj directories are skipped, a file named .git is not', () {
      file('work/.git', 'gitdir: ../x');
      file('work/.git2/keep');
      file('work/.jj/repo/r');
      file('work/sub/.git/objects/o');
      file('work/sub/deeper/.jj/store/s');
      file('work/sub/deeper/ok.txt');
      expect(
        [for (final f in walkFiles(at('work'))) f.name],
        ['.git', '.git2/keep', 'sub/deeper/ok.txt'],
      );
    });

    test('a root named .jj or .git is walked', () {
      file('.jj/f.txt');
      file('.jj/.git/h');
      final inner = at('.jj');
      expect([for (final f in walkFiles(inner)) f.name], ['f.txt']);
    });

    test('links are skipped, a link root is entered', () {
      file('real/f.txt');
      file('other/g.txt');
      Link(at('real/dirlink')).createSync(at('other'));
      Link(at('real/filelink')).createSync(at('real/f.txt'));
      Link(at('real/broken')).createSync(at('nowhere'));
      Link(at('rootlink')).createSync(at('real'));
      expect([for (final f in walkFiles(at('real'))) f.name], ['f.txt']);
      expect([for (final f in walkFiles(at('rootlink'))) f.name], ['f.txt']);
      final dir = walkTree(at('real')).single;
      expect(dir.dirs, isEmpty);
    }, skip: posixSkip);

    test('an unreadable directory is skipped', () {
      file('a.txt');
      file('locked/hidden.txt');
      file('open/b.txt');
      Process.runSync('chmod', ['000', at('locked')]);
      var reallyLocked = true;
      try {
        // A user for whom mode 000 does not stop listing (root)?
        reallyLocked = Directory(at('locked')).listSync().isEmpty;
      } on FileSystemException {
        // Listing threw: the directory really is locked.
      }
      if (!reallyLocked) {
        Process.runSync('chmod', ['755', at('locked')]);
        markTestSkipped('mode 000 does not stop listing for this user');
        return;
      }
      expect(
        [for (final f in walkFiles(root.path)) f.name],
        ['a.txt', 'open/b.txt'],
      );
    }, skip: posixSkip);

    test('a root that is a file or missing gives nothing', () {
      file('plain.txt');
      expect(walkTree(at('plain.txt')), isEmpty);
      expect(walkTree(at('missing')), isEmpty);
    });
  });

  group('the finish policy', () {
    test('groups top-down, each directory with its sorted names', () {
      file('b.md');
      file('a.md');
      file('a/z.md');
      file('sub/c.md');
      file('sub/deep/d.md');
      Directory(at('empty')).createSync();
      final walk = walkTree(root.path, policy: WalkPolicy.finish);
      expect(walk.map((d) => d.rel), ['', 'a', 'empty', 'sub', 'sub/deep']);
      expect(walk.first.files, ['a.md', 'b.md']);
      expect(walk.first.dirs, ['a', 'empty', 'sub']);
      expect(find(walk, 'sub')!.files, ['c.md']);
      expect(find(walk, 'sub')!.dirs, ['deep']);
      expect(find(walk, 'empty')!.files, isEmpty);
    });

    test('nothing is pruned: .git and .jj are walked', () {
      file('.git/HEAD');
      file('.jj/repo/x');
      final walk = walkTree(root.path, policy: WalkPolicy.finish);
      expect(walk.first.dirs, ['.git', '.jj']);
      expect(find(walk, '.jj/repo')!.files, ['x']);
    });

    test('a link to a file is a file, a link to a directory is a directory '
        'that is not entered', () {
      file('real/f.txt');
      file('other/g.txt');
      Link(at('real/filelink')).createSync(at('real/f.txt'));
      Link(at('real/dirlink')).createSync(at('other'));
      Link(at('real/broken')).createSync(at('nowhere'));
      final walk = walkTree(at('real'), policy: WalkPolicy.finish);
      expect(walk, hasLength(1));
      expect(walk.single.files, ['broken', 'f.txt', 'filelink']);
      expect(walk.single.dirs, ['dirlink']);
    }, skip: posixSkip);

    test('a root that is a link to a directory is entered', () {
      file('real/f.txt');
      Link(at('rootlink')).createSync(at('real'));
      final walk = walkTree(at('rootlink'), policy: WalkPolicy.finish);
      expect(walk.single.files, ['f.txt']);
    }, skip: posixSkip);

    test('an empty root is one entry with nothing in it', () {
      final walk = walkTree(root.path, policy: WalkPolicy.finish);
      expect(walk, hasLength(1));
      expect(walk.single.rel, '');
      expect(walk.single.files, isEmpty);
      expect(walk.single.dirs, isEmpty);
    });
  });

  group('names with U+FFFD', () {
    test('a valid U+FFFD name alone is listed', () {
      file('a\u{fffd}.txt', 'abc');
      final found = walkFiles(root.path);
      expect([for (final f in found) (f.name, f.size)], [('a\u{fffd}.txt', 3)]);
    });

    test('a raw 0xFF name throws NotUtf8 naming the file with U+FFFD', () {
      File.fromRawPath(raw('', [0x61, 0xff, 0x2e, 0x74, 0x78, 0x74]))
          .writeAsStringSync('xyz');
      expect(
        () => walkFiles(root.path),
        throwsA(
          isA<NotUtf8>().having((e) => e.shown, 'shown', 'a\u{fffd}.txt'),
        ),
      );
    }, skip: linuxSkip);

    test('the shown name carries the directory and the prefix', () {
      Directory.fromRawPath(raw('', [0x64])).createSync();
      File.fromRawPath(raw('d$sep', [0x61, 0xff])).writeAsStringSync('x');
      expect(
        () => walkTree(root.path, prefix: 'work'),
        throwsA(
          isA<NotUtf8>().having((e) => e.shown, 'shown', 'work/d/a\u{fffd}'),
        ),
      );
    }, skip: linuxSkip);

    test('a raw a<0xFF>.txt beside a valid a<U+FFFD>.txt throws NotUtf8', () {
      File.fromRawPath(raw('', [0x61, 0xff, 0x2e, 0x74, 0x78, 0x74]))
          .writeAsStringSync('large');
      file('a\u{fffd}.txt', 's');
      expect(() => walkFiles(root.path), throwsA(isA<NotUtf8>()));
    }, skip: linuxSkip);

    test('a raw directory name throws too, under both policies', () {
      Directory.fromRawPath(raw('', [0x64, 0xfe])).createSync();
      for (final policy in WalkPolicy.values) {
        expect(
          () => walkTree(root.path, policy: policy),
          throwsA(isA<NotUtf8>()),
        );
      }
    }, skip: linuxSkip);
  });
}
