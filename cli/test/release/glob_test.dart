// Tests of the release version-file glob (cli/lib/src/release/glob.dart).
//
// Assumption A2 of native-cli-release, checked with Python 3.14.4 in a scratch
// directory holding `.hidden/VERSION`, `a/.VERSION` and `a/VERSION`:
//
//   glob.glob('**/*', recursive=True) -> ['a', 'a/VERSION']
//   glob.glob('*')                    -> ['a']
//   glob.glob('**/VERSION', recursive=True) -> ['a/VERSION']
//   glob.glob('*/VERSION')            -> ['a/VERSION']
//   glob.glob('.hidden/VERSION')      -> ['.hidden/VERSION']
//   glob.glob('a/*')                  -> ['a/VERSION']
//
// So in the work tree a wildcard segment (`*`, `?`, `[...]`, and every
// directory `**` spans) never matches a name starting with `.`, while a
// literal segment does. The commit-tree glob over `git ls-tree` names matches
// dot-names (constraint C4). The tests below pin the same rule.
import 'dart:io';

import 'package:path/path.dart' as p;
import 'package:specwright_cli/src/release/glob.dart';
import 'package:specwright_cli/src/release/stop.dart';
import 'package:test/test.dart';

Matcher stops(String error, List<String> parts) => throwsA(
  isA<ReleaseStop>()
      .having((e) => e.error, 'error', error)
      .having((e) => e.message, 'message', allOf(parts.map(contains).toList())),
);

void main() {
  group('the glob rules', () {
    test('star and question mark stop at a slash', () {
      final star = VersionGlob('skills/*/SKILL.md');
      expect(star.matches('skills/a/SKILL.md'), isTrue);
      expect(star.matches('skills/a/b/SKILL.md'), isFalse);
      expect(VersionGlob('a?c').matches('abc'), isTrue);
      expect(VersionGlob('a?c').matches('a/c'), isFalse);
      expect(VersionGlob('*.md').matches('dir/a.md'), isFalse);
    });

    test('a double star slash spans directories, also none', () {
      final deep = VersionGlob('**/VERSION');
      expect(deep.matches('VERSION'), isTrue);
      expect(deep.matches('a/VERSION'), isTrue);
      expect(deep.matches('a/b/c/VERSION'), isTrue);
      expect(deep.matches('a/b/NOTVERSION'), isFalse);
      expect(VersionGlob('a/**/b').matches('a/b'), isTrue);
      expect(VersionGlob('a/**/b').matches('a/x/y/b'), isTrue);
    });

    test('classes, negated classes and literals', () {
      final cls = VersionGlob('v[0-9].txt');
      expect(cls.matches('v7.txt'), isTrue);
      expect(cls.matches('vx.txt'), isFalse);
      expect(VersionGlob('v[!0-9].txt').matches('vx.txt'), isTrue);
      expect(VersionGlob('v[^0-9].txt').matches('v7.txt'), isFalse);
      expect(VersionGlob('a.b+c').matches('a.b+c'), isTrue);
      expect(VersionGlob('a.b+c').matches('aXb+c'), isFalse);
      expect(VersionGlob('a[b').matches('a[b'), isTrue);
    });

    test('the whole path must match', () {
      expect(VersionGlob('VERSION').matches('x/VERSION'), isFalse);
      expect(VersionGlob('VERSION').matches('VERSION.bak'), isFalse);
    });

    test('hasGlob', () {
      expect(VersionGlob.hasGlob('a/b'), isFalse);
      expect(VersionGlob.hasGlob('a/*'), isTrue);
      expect(VersionGlob.hasGlob('a?'), isTrue);
      expect(VersionGlob.hasGlob('a[b]'), isTrue);
    });
  });

  group('commit tree names', () {
    final names = [
      '.hidden/VERSION',
      'a/.VERSION',
      'a/VERSION',
      'b/c/VERSION',
      'link/VERSION',
    ];

    test('wildcards match dot-names (C4)', () {
      expect(commitFiles('**/*', names, {}, 'x'), [
        '.hidden/VERSION',
        'a/.VERSION',
        'a/VERSION',
        'b/c/VERSION',
        'link/VERSION',
      ]);
      expect(commitFiles('*/VERSION', names, {}, 'x'), [
        '.hidden/VERSION',
        'a/VERSION',
        'link/VERSION',
      ]);
    });

    test('a literal path is matched exactly, sorted hits otherwise', () {
      expect(commitFiles('a/VERSION', names, {}, 'x'), ['a/VERSION']);
      expect(commitFiles('a/NOPE', names, {}, 'x'), isEmpty);
      expect(commitFiles('a/*', names, {}, 'x'), ['a/.VERSION', 'a/VERSION']);
    });

    test('a symlink entry is refused naming the entry and the label', () {
      expect(
        () => commitFiles('link/*', names, {'link/VERSION'}, 'commit abc'),
        stops('bad_version_files', ['link/VERSION', 'a symlink at commit abc']),
      );
    });
  });

  group('work tree', () {
    late Directory root;
    setUp(() {
      root = Directory.systemTemp.createTempSync('sw-glob-');
      for (final f in [
        '.hidden/VERSION',
        'a/.VERSION',
        'a/VERSION',
        'b/c/VERSION',
        'b/c/.git/VERSION',
        'top.md',
        '.dot.md',
      ]) {
        final file = File(p.join(root.path, f));
        file.parent.createSync(recursive: true);
        file.writeAsStringSync('0.1.0\n');
      }
    });
    tearDown(() => root.deleteSync(recursive: true));

    List<String> files(String pattern) => workTreeFiles(root.path, pattern);

    test('wildcard segments skip dot-names, literal segments match them', () {
      expect(files('**/*'), ['a/VERSION', 'b/c/VERSION', 'top.md']);
      expect(files('*'), ['top.md']);
      expect(files('**/VERSION'), ['a/VERSION', 'b/c/VERSION']);
      expect(files('*/VERSION'), ['a/VERSION']);
      expect(files('.hidden/VERSION'), ['.hidden/VERSION']);
      expect(files('a/*'), ['a/VERSION']);
      expect(files('a/.VERSION'), ['a/.VERSION']);
    });

    test('a wildcard segment that starts with a dot matches dot-names', () {
      expect(files('.*.md'), ['.dot.md']);
      expect(files('a/.*'), ['a/.VERSION']);
    });

    test('a double star also matches no directory; results are sorted', () {
      expect(files('**/top.md'), ['top.md']);
      expect(files('b/**/VERSION'), ['b/c/VERSION']);
      expect(files('*/*/VERSION'), ['b/c/VERSION']);
    });

    test('a missing path or a directory matches nothing', () {
      expect(files('nope/*'), isEmpty);
      expect(files('NOPE'), isEmpty);
      expect(files('a'), isEmpty);
    });

    test('a link at any path segment is refused', () {
      final outside = Directory.systemTemp.createTempSync('sw-glob-out-');
      addTearDown(() => outside.deleteSync(recursive: true));
      File(p.join(outside.path, 'VERSION')).writeAsStringSync('0.1.0\n');
      try {
        Link(p.join(root.path, 'linked')).createSync(outside.path);
      } on FileSystemException {
        markTestSkipped('no symlinks here');
        return;
      }
      expect(
        () => files('*/VERSION'),
        stops('bad_version_files', [
          'linked/VERSION',
          'outside the repository',
        ]),
      );

      Link(p.join(root.path, 'inner')).createSync(p.join(root.path, 'a'));
      expect(
        () => files('inner/VERSION'),
        stops('bad_version_files', [
          'through a symlink;',
          'List the file the link points to',
        ]),
      );
    });

    test('a link to a file is refused too', () {
      try {
        Link(p.join(root.path, 'LINK')).createSync(p.join(root.path, 'top.md'));
      } on FileSystemException {
        markTestSkipped('no symlinks here');
        return;
      }
      expect(() => files('LINK'), stops('bad_version_files', ['LINK']));
    });
  });
}
