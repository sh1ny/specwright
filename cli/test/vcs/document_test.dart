import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:specwright_cli/src/commands/vcs.dart';
import 'package:specwright_cli/src/process/limits.dart';
import 'package:specwright_cli/src/vcs/document.dart';
import 'package:test/test.dart';

// Assumptions A1, A2 and A3 of native-cli-library-foundations, run on the Dart SDK pinned by mise.toml (task 2.1):
//
// A1 holds. `jsonDecode` reads 100,000 nested arrays and 100,000 nested objects whole, and 1,000,000 too, with no crash:
//    the parser keeps its own stack, so no depth limit is needed and the 32 MiB file bound is the only protection. The
//    wrapper still maps a StackOverflowError to the same stop in case a future SDK recurses.
// A2 holds. An integer past signed 64 bits decodes to a `double` (9223372036854775808 becomes 9.223372036854776e18),
//    so an `is int` check refuses it; 9223372036854775807 stays an `int`.
// A3 is DISPROVED. `jsonDecode` keeps a lone surrogate escape (`"\ud800"`) as a lone surrogate, but `JsonEncoder` writes
//    it back as the six-character escape `\ud800` (a valid pair is written raw). `reviewerConfigBytes` would therefore no
//    longer replace the surrogate by `?`. The owner-approved D1 fallback applies: `documentText` is `JsonEncoder` plus a scan that turns the encoder's own
//    lone-surrogate escapes back into the raw unit.

Uint8List _hex(String hex) => Uint8List.fromList([
  for (var i = 0; i < hex.length; i += 2)
    int.parse(hex.substring(i, i + 2), radix: 16),
]);

void main() {
  group('documentText', () {
    test('is compact, keeps key order and writes JSON numbers', () {
      final doc = <String, Object?>{
        'ok': true,
        'n': 3,
        'neg': -12,
        'none': null,
        'list': [1, 'a', null, 1.5],
        'nested': {'x': <String, Object?>{}, 'y': <Object?>[]},
      };
      expect(
        documentText(doc),
        '{"ok":true,"n":3,"neg":-12,"none":null,"list":[1,"a",null,1.5],'
        '"nested":{"x":{},"y":[]}}',
      );
    });

    test('U+2028 and U+2029 parse back', () {
      const text = 'a b c';
      final written = documentText({'k': text});
      expect(jsonDecode(written), {'k': text});
      // the encoder leaves both raw; consumers parse documents, never match them
      expect(written, contains(' '));
    });

    test('a line separator in a document reads back through documentBytes', () {
      final bytes = documentBytes({'k': 'a b'});
      expect(jsonDecode(utf8.decode(bytes)), {'k': 'a b'});
    });

    test('A3: a lone surrogate is written raw, a valid pair stays whole', () {
      final lone = String.fromCharCode(0xd800);
      expect(documentText(lone), '"$lone"');
      expect(documentText('\u{1f600}'), '"\u{1f600}"');
      // an escape the caller wrote is data, and keeps its backslash
      expect(documentText(r'\ud800'), r'"\\ud800"');
    });
  });

  group('documentBytes', () {
    test('ends with exactly one LF and no CR', () {
      expect(documentBytes(<Object?>[]), [0x5b, 0x5d, 0x0a]);
      final bytes = documentBytes({'a': 'x\ny'});
      expect(bytes.last, 0x0a);
      expect(bytes.where((b) => b == 0x0d), isEmpty);
      expect(utf8.decode(bytes).split('\n'), hasLength(2));
    });

    test('escapes controls and leaves DEL and "/" raw', () {
      final text = 'a\n\r\t\b\f"\\\u0001\u001f\u007f/\u0000';
      expect(jsonDecode(utf8.decode(documentBytes({'s': text}))), {'s': text});
      expect(utf8.decode(documentBytes(text)), contains('\u007f/'));
    });

    test('keeps non-ASCII raw', () {
      expect(
        documentBytes({'s': 'é€\u{1f600}�'}),
        _hex('7b2273223a22c3a9e282acf09f9880efbfbd227d0a'),
      );
    });

    // Constraint C3: a name that is not UTF-8 never reaches a document (D4), so
    // every lone surrogate is refused, as Python fails to encode it.
    test('rejects a lone surrogate, as Python fails to encode it', () {
      expect(() => documentBytes({'s': '\ud800'}), throwsFormatException);
      expect(() => documentBytes({'s': '\udcff'}), throwsFormatException);
      expect(() => documentBytes({'p\udc80': 1}), throwsFormatException);
    });

    test('a value JSON cannot hold is internal_error', () async {
      final repo = Directory.systemTemp.createTempSync('sw-doc-repo-');
      addTearDown(() => repo.deleteSync(recursive: true));
      for (final value in <Object?>[
        double.nan,
        double.infinity,
        BigInt.two.pow(70),
        Object(),
      ]) {
        final out = <int>[];
        final code = await runVcsCommand(
          ['--args-stdin'],
          writeOut: out.addAll,
          readStdin: () async => [
            for (final r in [
              '/s',
              '/b',
              'state',
              '--repo',
              repo.path,
              '--role',
              'code',
            ]) ...[...utf8.encode(r), 0],
          ],
          handlers: {
            'state': (_) async => {'ok': true, 'x': value},
          },
        );
        expect(code, 1, reason: '$value');
        final text = utf8.decode(out);
        expect(text.endsWith('\n'), true);
        final doc = jsonDecode(text) as Map<String, Object?>;
        expect(doc['ok'], false, reason: '$value');
        expect(doc['error'], 'internal_error', reason: '$value');
        expect(text, isNot(contains('#0')), reason: 'no stack trace');
      }
    });

    test('a value JSON cannot hold is refused by the writer itself', () {
      expect(() => documentText(double.nan), throwsA(isA<Object>()));
      expect(() => documentText(BigInt.two.pow(70)), throwsA(isA<Object>()));
      expect(() => documentText({1: 'a'}), throwsA(isA<Object>()));
    });
  });

  group('decodeJson', () {
    test('reads standard JSON', () {
      expect(decodeJson('{"a":[1,2.5,"x",null,true]}'), {
        'a': [1, 2.5, 'x', null, true],
      });
    });

    test('refuses NaN and Infinity, naming the file', () {
      for (final text in ['[NaN]', '[Infinity]', '[-Infinity]']) {
        expect(
          () => decodeJson(text, file: 'm.json'),
          throwsA(
            isA<JsonInputException>().having(
              (e) => e.message,
              'message',
              startsWith('m.json: '),
            ),
          ),
          reason: text,
        );
      }
    });

    test('A2: an integer past 64 bits is a double, never an int', () {
      expect(decodeJson('9223372036854775807'), isA<int>());
      for (final text in [
        '9223372036854775808',
        '-9223372036854775809',
        '123456789012345678901234567890',
      ]) {
        expect(decodeJson(text), isA<double>(), reason: text);
        expect(decodeJson(text), isNot(isA<int>()), reason: text);
      }
    });

    test('100,000 levels never crash', () {
      const n = 100000;
      for (final text in [
        '${'[' * n}${']' * n}',
        '${'{"a":' * n}1${'}' * n}',
      ]) {
        try {
          final value = decodeJson(text, file: 'deep.json');
          expect(value, isNotNull);
        } on JsonInputException catch (e) {
          expect(e.message, startsWith('deep.json: '));
        }
      }
    });

    test('a lone surrogate escape stays a lone surrogate', () {
      expect(decodeJson(r'"\ud800"'), String.fromCharCode(0xd800));
    });
  });

  group('readJsonFile', () {
    late Directory dir;
    setUp(() => dir = Directory.systemTemp.createTempSync('sw-json-file-'));
    tearDown(() => dir.deleteSync(recursive: true));

    test('reads a file through its raw path', () {
      final f = File('${dir.path}/m.json')..writeAsStringSync('{"v":"é"}');
      expect(readJsonFile(f.path), {'v': 'é'});
    });

    test('a missing file stops naming it', () {
      final path = '${dir.path}/none.json';
      expect(
        () => readJsonFile(path),
        throwsA(
          isA<JsonInputException>().having(
            (e) => e.message,
            'message',
            startsWith('$path: cannot read: '),
          ),
        ),
      );
    });

    test('bytes that are not UTF-8 stop naming the file', () {
      final f = File('${dir.path}/b.json')
        ..writeAsBytesSync([0x22, 0xff, 0x22]);
      expect(
        () => readJsonFile(f.path),
        throwsA(
          isA<JsonInputException>().having(
            (e) => e.message,
            'message',
            startsWith('${f.path}: not valid UTF-8'),
          ),
        ),
      );
    });

    test('a byte-order mark is refused', () {
      final f = File('${dir.path}/bom.json')
        ..writeAsBytesSync([0xef, 0xbb, 0xbf, 0x7b, 0x7d]);
      expect(() => readJsonFile(f.path), throwsA(isA<JsonInputException>()));
    });

    test('a file over 32 MiB stops naming the file', () {
      final f = File('${dir.path}/big.json');
      final out = f.openSync(mode: FileMode.write);
      // `["` then 32 MiB - 3 padding bytes then `"]` is exactly the cap plus one
      out.writeStringSync('["');
      final chunk = Uint8List(1024 * 1024)..fillRange(0, 1024 * 1024, 0x78);
      var left = defaultMaxBytes + 1 - 4;
      while (left > 0) {
        final n = left < chunk.length ? left : chunk.length;
        out.writeFromSync(chunk, 0, n);
        left -= n;
      }
      out.writeStringSync('"]');
      out.closeSync();
      expect(f.lengthSync(), defaultMaxBytes + 1);
      expect(
        () => readJsonFile(f.path),
        throwsA(
          isA<JsonInputException>().having(
            (e) => e.message,
            'message',
            allOf(startsWith('${f.path}: '), contains('32 MiB')),
          ),
        ),
      );
    });

    test('a file of exactly 32 MiB is read', () {
      final f = File('${dir.path}/edge.json');
      final out = f.openSync(mode: FileMode.write);
      out.writeStringSync('["');
      final chunk = Uint8List(1024 * 1024)..fillRange(0, 1024 * 1024, 0x78);
      var left = defaultMaxBytes - 4;
      while (left > 0) {
        final n = left < chunk.length ? left : chunk.length;
        out.writeFromSync(chunk, 0, n);
        left -= n;
      }
      out.writeStringSync('"]');
      out.closeSync();
      expect(f.lengthSync(), defaultMaxBytes);
      expect(readJsonFile(f.path), isA<List<Object?>>());
    });
  });
}
