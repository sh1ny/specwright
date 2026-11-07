import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:specwright_cli/src/finish/walk.dart';
import 'package:specwright_cli/src/vcs/codec.dart';
import 'package:test/test.dart';

import '../vcs/bash_support.dart';

/// The byte-preserving `os.walk` (design D4). Names come from `find -print0`
/// through the transport; the order inside one directory is the file system's,
/// so tests that touch the disk compare sets and the top-down structure, and
/// `groupWalk` is checked with fixed records.
void main() {
  final bash = findBash();
  final skip = bash == null ? 'no bash installed' : false;
  final posixSkip = bash == null
      ? 'no bash installed'
      : Platform.isWindows
      ? 'links need developer mode on Windows; POSIX only'
      : false;
  final linuxSkip = bash == null
      ? 'no bash installed'
      : Platform.isLinux
      ? false
      : 'Linux only: macOS (APFS) refuses names that are not valid UTF-8, '
            'and Windows names are UTF-16';
  final sep = Platform.pathSeparator;

  late Directory root;
  setUp(() {
    root = Directory.systemTemp.createTempSync('claude-ncf-g2-walk-');
  });
  tearDown(() {
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

  group('walkTree on a temporary tree', () {
    test('groups top-down with files and folders told apart', () async {
      file('a.txt');
      file('b/c.txt');
      file('b/d/e.txt');
      file('b/d/f.md');
      Directory(at('empty')).createSync();
      final walk = await walkTree(bash!, root.path);

      expect(walk.first.rel, '');
      expect(walk.first.files.toSet(), {'a.txt'});
      expect(walk.first.dirs.toSet(), {'b', 'empty'});
      expect(find(walk, 'b')!.files, ['c.txt']);
      expect(find(walk, 'b')!.dirs, ['d']);
      expect(find(walk, 'b/d')!.files.toSet(), {'e.txt', 'f.md'});
      expect(find(walk, 'b/d')!.dirs, isEmpty);
      expect(find(walk, 'empty')!.files, isEmpty);
      expect(find(walk, 'empty')!.dirs, isEmpty);
      expect(walk, hasLength(4));

      // os.walk's order: the root, then each folder of `dirs` in turn, with
      // its subfolders after it, depth first.
      final top = walk.first.dirs;
      expect(walk.map((d) => d.rel).toList(), [
        '',
        for (final name in top) ...[name, if (name == 'b') 'b/d'],
      ]);
      expect(find(walk, 'b/d')!.path.endsWith('/b/d'), isTrue);
    }, skip: skip);

    test('a root that is not a folder, or is missing, gives nothing', () async {
      file('plain.txt');
      expect(await walkTree(bash!, at('plain.txt')), isEmpty);
      expect(await walkTree(bash, at('missing')), isEmpty);
    }, skip: skip);

    test('an empty root is one entry with nothing in it', () async {
      final walk = await walkTree(bash!, root.path);
      expect(walk, hasLength(1));
      expect(walk.single.rel, '');
      expect(walk.single.files, isEmpty);
      expect(walk.single.dirs, isEmpty);
    }, skip: skip);

    test('nothing is pruned: .git and .jj are walked', () async {
      file('.git/HEAD');
      file('.jj/repo/x');
      final walk = await walkTree(bash!, root.path);
      expect(walk.first.dirs.toSet(), {'.git', '.jj'});
      expect(find(walk, '.jj/repo')!.files, ['x']);
    }, skip: skip);

    test('a link to a file is a file, a link to a folder is a folder that '
        'is not entered', () async {
      file('real/f.txt');
      file('other/g.txt');
      Link(at('real/filelink')).createSync(at('real/f.txt'));
      Link(at('real/dirlink')).createSync(at('other'));
      Link(at('real/broken')).createSync(at('nowhere'));
      final walk = await walkTree(bash!, at('real'));
      expect(walk, hasLength(1));
      expect(walk.single.files.toSet(), {'f.txt', 'filelink', 'broken'});
      expect(walk.single.dirs, ['dirlink']);
    }, skip: posixSkip);

    test('a root that is a link to a folder is entered', () async {
      file('real/f.txt');
      Link(at('rootlink')).createSync(at('real'));
      final walk = await walkTree(bash!, at('rootlink'));
      expect(walk.single.files, ['f.txt']);
    }, skip: posixSkip);

    test('a name with invalid UTF-8 bytes round-trips', () async {
      final base = encodeEscaped(root.path);
      final raw = Uint8List.fromList([...base, 0x2f, 0x61, 0xff, 0x62]);
      File.fromRawPath(raw).writeAsStringSync('xyz');
      final dirRaw = Uint8List.fromList([...base, 0x2f, 0x64, 0xfe]);
      Directory.fromRawPath(dirRaw).createSync();
      File.fromRawPath(Uint8List.fromList([...dirRaw, 0x2f, 0x6b, 0x80]))
          .writeAsStringSync('k');
      final walk = await walkTree(bash!, root.path);
      expect(walk.first.files, hasLength(1));
      expect(walk.first.files.single.codeUnits, [0x61, 0xdcff, 0x62]);
      expect(encodeEscaped(walk.first.files.single), [0x61, 0xff, 0x62]);
      expect(walk.first.dirs.single.codeUnits, [0x64, 0xdcfe]);
      final inner = walk[1];
      expect(inner.rel.codeUnits, [0x64, 0xdcfe]);
      expect(encodeEscaped(inner.path).sublist(base.length), [
        0x2f,
        0x64,
        0xfe,
      ]);
      expect(inner.files.single.codeUnits, [0x6b, 0xdc80]);
    }, skip: linuxSkip);

    test(
      'a name with a newline is one name',
      () async {
        file('a\nb.txt');
        final walk = await walkTree(bash!, root.path);
        expect(walk.single.files, ['a\nb.txt']);
      },
      skip: Platform.isWindows ? 'a newline cannot be in a Windows name' : skip,
    );
  });

  group('groupWalk', () {
    WalkRecord f(String n) => WalkRecord(n, isDir: false, isLink: false);
    WalkRecord d(String n) => WalkRecord(n, isDir: true, isLink: false);
    WalkRecord dl(String n) => WalkRecord(n, isDir: true, isLink: true);

    test("puts a folder's files, then its subfolders, each in turn", () {
      // find's depth-first listing; the folders' own records are interleaved.
      final walk = groupWalk('/r/', [
        d('/r/x'),
        f('/r/x/1'),
        d('/r/x/y'),
        f('/r/x/y/2'),
        f('/r/x/3'),
        f('/r/top'),
        d('/r/z'),
        f('/r/z/4'),
      ]);
      expect(
        [for (final e in walk) '${e.rel}|${e.files}|${e.dirs}'],
        ['|[top]|[x, z]', 'x|[1, 3]|[y]', 'x/y|[2]|[]', 'z|[4]|[]'],
      );
      expect(walk[2].path, '/r/x/y');
      expect(walk.first.path, '/r');
    });

    test('a linked folder is listed in dirs and not entered', () {
      final walk = groupWalk('/r/', [
        dl('/r/ln'),
        d('/r/real'),
        f('/r/real/q'),
      ]);
      expect(walk.map((e) => e.rel), ['', 'real']);
      expect(walk.first.dirs, ['ln', 'real']);
    });

    test('a record that does not start with the root is dropped', () {
      final walk = groupWalk('/r/', [f('/elsewhere/q'), f('/r/p')]);
      expect(walk.single.files, ['p']);
    });

    test('a last record with no NUL is dropped', () {
      final out = utf8.encode('/r/a\u0000/r/b');
      expect(splitRecords(out), ['/r/a']);
    });
  });
}
