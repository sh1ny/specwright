import 'dart:io';

import 'package:specwright_cli/src/update/packs.dart' show sameTree;
import 'package:specwright_cli/src/update/text.dart';
import 'package:test/test.dart';

void main() {
  late String tmp;

  setUp(() {
    tmp = posixPath(
      Directory.systemTemp
          .createTempSync('sw-text-')
          .resolveSymbolicLinksSync(),
    );
  });
  tearDown(() => Directory(tmp).deleteSync(recursive: true));

  group('resolvePosix', () {
    test('a missing path under a linked directory resolves the link', () {
      Directory('$tmp/real').createSync();
      // a directory link (a junction on Windows, which needs no privilege)
      Link('$tmp/alias').createSync('$tmp/real');
      expect(resolvePosix('$tmp/alias/openspec/x'), '$tmp/real/openspec/x');
      expect(resolvePosix('$tmp/alias'), '$tmp/real');
    });

    test(
      'a .. after a link climbs from the link target',
      () {
        Directory('$tmp/other/sub').createSync(recursive: true);
        Link('$tmp/link').createSync('$tmp/other/sub');
        expect(resolvePosix('$tmp/link/../openspec'), '$tmp/other/openspec');
        expect(resolvePosix('$tmp/link/..'), '$tmp/other');
      },
      // Windows folds .. as text before it follows a link
      skip: Platform.isWindows ? 'POSIX path semantics' : false,
    );

    test('a path with nothing existing is made absolute and normalised', () {
      expect(resolvePosix('$tmp/none/a/../b'), '$tmp/none/b');
    });
  });

  group('sameTree', () {
    void file(String path, String text) => File(path)
      ..createSync(recursive: true)
      ..writeAsStringSync(text);

    test('the same files with the same bytes are the same', () {
      file('$tmp/a/SKILL.md', 'x\n');
      file('$tmp/b/SKILL.md', 'x\n');
      expect(sameTree('$tmp/a', '$tmp/b'), isTrue);
    });

    test('a link in either tree is never the same', () {
      file('$tmp/a/SKILL.md', 'x\n');
      file('$tmp/b/SKILL.md', 'x\n');
      Directory('$tmp/elsewhere').createSync();
      Link('$tmp/a/extra').createSync('$tmp/elsewhere');
      expect(sameTree('$tmp/a', '$tmp/b'), isFalse);
      expect(sameTree('$tmp/b', '$tmp/a'), isFalse);
    });
  });
}
