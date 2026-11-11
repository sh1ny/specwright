// Verifies assumptions A1 and A3 of the native-cli-launcher design on POSIX.
//
// A1: `Directory.listSync` yields an entity whose `path` holds U+FFFD for a
// byte that is not UTF-8, while the entity keeps the raw bytes so its own
// `existsSync` and `lengthSync` still see the file, and a path built from the
// decoded name does not exist.
//
// A3 (disproved): `Platform.environment` of a Dart child drops a variable
// whose value is not UTF-8; it does not show U+FFFD in its place.
@TestOn('linux || mac-os')
library;

import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:test/test.dart';

void main() {
  late Directory temp;

  setUp(() {
    temp = Directory.systemTemp.createTempSync('sw-listing-assumption-');
  });

  tearDown(() {
    temp.deleteSync(recursive: true);
  });

  test(
    'A1: a listed non-UTF-8 name holds U+FFFD but the entity sees the file',
    () {
      final raw = Uint8List.fromList([
        ...utf8.encode('${temp.path}/a'),
        0xFF,
        ...utf8.encode('.txt'),
      ]);
      final file = File.fromRawPath(raw);
      try {
        file.writeAsStringSync('hello');
      } on FileSystemException catch (e) {
        // APFS refuses a name that is not valid UTF-8. Linux must accept it.
        if (Platform.isMacOS) {
          markTestSkipped('macOS refused to create the file: $e');
          return;
        }
        rethrow;
      }

      final entities = temp.listSync(followLinks: false);
      expect(entities, hasLength(1));
      final entity = entities.single;
      expect(entity.path, contains('�'));
      expect(File(entity.path).existsSync(), isFalse);
      expect(entity.existsSync(), isTrue);
      expect((entity as File).lengthSync(), 5);
    },
  );

  test(
    'A3: a child does not see a non-UTF-8 environment variable',
    testOn: 'linux',
    () async {
      final script = File('${temp.path}/child.dart')
        ..writeAsStringSync(r'''
import 'dart:io';

void main() {
  final value = Platform.environment['SW_RAW_VALUE'];
  stdout.write(value == null ? 'MISSING' : 'VALUE:' + value.codeUnits.join(','));
}
''');
      final result = await Process.run('/bin/sh', [
        '-c',
        r'''SW_RAW_VALUE="x$(printf '\377')y" "$0" "$1"''',
        Platform.resolvedExecutable,
        script.path,
      ]);
      expect(result.exitCode, 0, reason: '${result.stderr}');
      // A3 was disproved on Linux CI: Dart drops the variable instead of
      // showing U+FFFD, so feedback reads these values through getenv (D10).
      expect(result.stdout, 'MISSING');
    },
  );
}
