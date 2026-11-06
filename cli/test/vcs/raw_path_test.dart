import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:specwright_cli/src/vcs/codec.dart';
import 'package:specwright_cli/src/vcs/walk.dart';
import 'package:test/test.dart';

import 'bash_support.dart';

/// A5 and the D4 directory walk. The walk lists names with `find -print0`
/// through the transport, because a listed entry's raw bytes are private in
/// Dart 3.13 and its `path` is lossy.
void main() {
  final bash = findBash();
  final skip = bash == null ? 'no bash installed' : false;
  const posixOnly = 'POSIX only';
  final posixSkip = bash == null
      ? 'no bash installed'
      : Platform.isWindows
      ? posixOnly
      : false;
  final linuxSkip = bash == null
      ? 'no bash installed'
      : Platform.isLinux
      ? false
      : 'Linux only: macOS (APFS) refuses names that are not valid UTF-8, '
            'and Windows names are UTF-16';
  final sep = Platform.pathSeparator;

  late Directory repo;
  setUp(() {
    repo = Directory.systemTemp.createTempSync('claude-ncv-g2-walk-');
  });
  tearDown(() {
    if (!Platform.isWindows) {
      Process.runSync('chmod', ['-R', 'u+rwx', repo.path]);
    }
    repo.deleteSync(recursive: true);
  });

  String at(String rel) => '${repo.path}$sep${rel.replaceAll('/', sep)}';
  void file(String rel, [String content = 'x']) {
    final f = File(at(rel));
    f.parent.createSync(recursive: true);
    f.writeAsStringSync(content);
  }

  void dir(String rel) => Directory(at(rel)).createSync(recursive: true);

  Future<List<String>> names(String path) async => [
    for (final f in await walkFiles(bash!, repo.path, path)) f.name,
  ];

  group('walk against the file system', () {
    test(
      'A5: a name holding byte 0xFF is reported with its bytes and size',
      () async {
        final raw = Uint8List.fromList([
          ...utf8.encode(repo.path),
          0x2f,
          0x61,
          0xff,
          0x62,
        ]);
        File.fromRawPath(raw).writeAsStringSync('xyz');
        final found = await walkFiles(bash!, repo.path, '.');
        expect(found, hasLength(1));
        expect(found.single.name.codeUnits, [0x61, 0xdcff, 0x62]);
        expect(encodeEscaped(found.single.name), [0x61, 0xff, 0x62]);
        expect(found.single.size, 3);
      },
      skip: linuxSkip,
    );

    test('lists regular files with their sizes', () async {
      file('a.txt', '12345');
      file('sub/b.txt', '12');
      final found = await walkFiles(bash!, repo.path, '.');
      expect(
        [for (final f in found) (f.name, f.size)],
        [('a.txt', 5), ('sub/b.txt', 2)],
      );
    }, skip: skip);

    test('a regular file named .git is listed, .git and .jj directories are pruned', () async {
      file('work/.git', 'gitdir: ../x');
      file('work/.git2/keep');
      file('work/a.txt');
      file('work/.jj/repo/r');
      file('work/sub/.git/objects/o');
      file('work/sub/deeper/.jj/store/s');
      file('work/sub/deeper/ok.txt');
      final got = await names('work');
      expect(got.toSet(), {
        'work/.git',
        'work/.git2/keep',
        'work/a.txt',
        'work/sub/deeper/ok.txt',
      });
    }, skip: skip);

    test('a root named .jj is walked, its pruned children are not', () async {
      file('.jj/f.txt');
      file('.jj/.git/h');
      file('.jj/.jj/g');
      file('.jj/sub/k.txt');
      expect((await names('.jj')).toSet(), {'.jj/f.txt', '.jj/sub/k.txt'});
    }, skip: skip);

    test('a root named .git is walked too', () async {
      file('.git/f.txt');
      expect(await names('.git'), ['.git/f.txt']);
    }, skip: skip);

    test('directories are not listed', () async {
      dir('empty/inner');
      file('real/f.txt');
      expect(await names('.'), ['real/f.txt']);
    }, skip: skip);

    test(
      'symlinks are not listed, a symlinked root is entered, one below is not',
      () async {
        file('real/f.txt');
        file('other/g.txt');
        Link(at('real/dirlink')).createSync(at('other'));
        Link(at('real/filelink')).createSync(at('real/f.txt'));
        Link(at('rootlink')).createSync(at('real'));
        expect((await names('real')).toSet(), {'real/f.txt'});
        expect((await names('rootlink')).toSet(), {'rootlink/f.txt'});
      },
      skip: posixSkip,
    );

    test('equivalent path spellings give the same reported names', () async {
      file('work/a.txt');
      file('work/s/b.txt');
      final want = ['work/a.txt', 'work/s/b.txt'];
      for (final spelling in [
        '.',
        './',
        'work',
        'work/',
        'work/../work/',
        at('work'),
        at('work/../work/'),
      ]) {
        expect(await names(spelling), want, reason: spelling);
      }
    }, skip: skip);

    test('a find or bash first on PATH is never run', () async {
      file('a.txt');
      final fake = Directory.systemTemp.createTempSync('claude-ncv-g2-fake-');
      addTearDown(() => fake.deleteSync(recursive: true));
      final marker = File('${fake.path}${sep}ran');
      File('${fake.path}${sep}find').writeAsStringSync(
        '#!/bin/sh\ntouch "\$(dirname "\$0")/ran"\nprintf "bogus\\0"\n',
      );
      // A stand-in for System32's bash.exe (the WSL launcher): a nested
      // `bash` looked up on PATH would run this instead of the bash handed in.
      File(
        '${fake.path}${sep}bash',
      ).writeAsStringSync('#!/bin/sh\ntouch "\$(dirname "\$0")/ran"\nexit 1\n');
      if (!Platform.isWindows) {
        for (final n in ['find', 'bash']) {
          Process.runSync('chmod', ['+x', '${fake.path}$sep$n']);
        }
      }
      final env = Map<String, String>.of(Platform.environment);
      final key = env.keys.firstWhere(
        (k) => k.toLowerCase() == 'path',
        orElse: () => 'PATH',
      );
      final system32 = Platform.isWindows
          ? '${Platform.environment['SystemRoot'] ?? r'C:\Windows'}\\System32;'
          : '';
      final pathSep = Platform.isWindows ? ';' : ':';
      env[key] = '${fake.path}$pathSep$system32${env[key] ?? ''}';
      final found = await walkFiles(bash!, repo.path, '.', environment: env);
      expect([for (final f in found) f.name], ['a.txt']);
      expect(marker.existsSync(), isFalse);
    }, skip: skip);

    test(
      'a subdirectory that cannot be listed is skipped, other names kept',
      () async {
        file('a.txt');
        file('locked/hidden.txt');
        file('open/b.txt');
        Process.runSync('chmod', ['000', at('locked')]);
        var reallyLocked = true;
        try {
          // Running as a user for whom mode 000 does not stop listing (root)?
          reallyLocked = Directory(at('locked')).listSync().isEmpty;
        } on FileSystemException {
          // Listing threw: the directory really is locked.
        }
        if (!reallyLocked) {
          Process.runSync('chmod', ['755', at('locked')]);
          return;
        }
        expect((await names('.')).toSet(), {'a.txt', 'open/b.txt'});
      },
      skip: posixSkip,
    );
  });

  group('statRecords', () {
    test('skips names that are gone, directories and (POSIX) links', () {
      file('real.txt', 'abc');
      dir('adir');
      final records = [at('real.txt'), at('gone.txt'), at('adir')];
      if (!Platform.isWindows) {
        Link(at('lnk')).createSync(at('real.txt'));
        records.add(at('lnk'));
      }
      final found = statRecords(records, repo.path);
      expect([for (final f in found) (f.name, f.size)], [('real.txt', 3)]);
    });
  });

  group('statRecords on special files', () {
    test('a directory is skipped', () {
      dir('adir');
      expect(statRecords([at('adir')], repo.path), isEmpty);
    }, skip: posixSkip);

    test('a broken link and a directory link are skipped', () {
      dir('adir');
      Link(at('broken')).createSync(at('nowhere'));
      Link(at('dlink')).createSync(at('adir'));
      expect(statRecords([at('broken'), at('dlink')], repo.path), isEmpty);
    }, skip: posixSkip);
  });

  group('walkOrder', () {
    const root = '/r/work/';
    test("puts a directory's own files before its child directories", () {
      final got = walkOrder(root, [
        '/r/work/deep/big.bin',
        '/r/work/big.bin',
        '/r/work/deep/x/y',
        '/r/work/z',
      ]);
      expect(got, [
        '/r/work/big.bin',
        '/r/work/z',
        '/r/work/deep/big.bin',
        '/r/work/deep/x/y',
      ]);
    });

    test('keeps find\'s order inside a directory and between children', () {
      final got = walkOrder(root, [
        '/r/work/b/1',
        '/r/work/a/1',
        '/r/work/b/2',
        '/r/work/b/c/3',
        '/r/work/a/0',
      ]);
      expect(got, [
        '/r/work/b/1',
        '/r/work/b/2',
        '/r/work/b/c/3',
        '/r/work/a/1',
        '/r/work/a/0',
      ]);
    });

    test('a record outside the root prefix is kept', () {
      expect(walkOrder(root, ['/x/y']), ['/x/y']);
    });
  });

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

  group('relpathText (os.path.relpath then path_text)', () {
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
      expect(() => rel(r'D:\x', r'C:\r'), throwsA(isA<StateError>()));
    });
  });
}
