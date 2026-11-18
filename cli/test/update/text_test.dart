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
