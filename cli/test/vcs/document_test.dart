import 'dart:typed_data';

import 'package:specwright_cli/src/vcs/document.dart';
import 'package:test/test.dart';

/// Expected bytes come from CPython 3.14:
/// `json.dumps(obj, ensure_ascii=False)` with U+2028 and U+2029 replaced by
/// their six-character escapes, encoded with `utf-8` and `surrogateescape`
/// (vcs.sh:43-45, and `-X utf8` makes stdout use surrogateescape).
Uint8List _hex(String hex) => Uint8List.fromList([
  for (var i = 0; i < hex.length; i += 2)
    int.parse(hex.substring(i, i + 2), radix: 16),
]);

void main() {
  group('documentText', () {
    test('uses ", " and ": " separators and keeps key order', () {
      final doc = <String, Object?>{
        'ok': true,
        'n': 3,
        'neg': -12,
        'none': null,
        'no': false,
        'list': [1, 'a', null],
        'nested': {'x': <String, Object?>{}, 'y': <Object?>[]},
      };
      expect(
        documentText(doc),
        '{"ok": true, "n": 3, "neg": -12, "none": null, "no": false, '
        '"list": [1, "a", null], "nested": {"x": {}, "y": []}}',
      );
    });

    test('writes empty containers', () {
      expect(documentText(<String, Object?>{}), '{}');
      expect(documentText(<Object?>[]), '[]');
    });

    test('writes ints beyond 64 bits as digits', () {
      expect(
        documentText(BigInt.parse('12345678901234567890')),
        '12345678901234567890',
      );
    });

    test('rejects values json.dumps would not write here', () {
      expect(() => documentText(1.5), throwsArgumentError);
      expect(() => documentText(Object()), throwsArgumentError);
      expect(() => documentText({1: 'a'}), throwsArgumentError);
    });
  });

  group('documentBytes', () {
    const lf = '\n';
    const crlf = '\r\n';

    test('escapes controls as Python does and leaves DEL and "/" raw', () {
      final text = 'a\n\r\t\b\f"\\\u0001\u001f\u007f/\u0000';
      expect(
        documentBytes({'s': text}, lineEnd: ''),
        _hex(
          '7b2273223a2022615c6e5c725c745c625c665c225c5c5c75303030315c7530303'
          '1667f2f5c7530303030227d',
        ),
      );
    });

    test('keeps non-ASCII raw and escapes U+2028 and U+2029', () {
      final text = '\u00e9\u20ac\u{1f600}\u2028\u2029\ufffd';
      expect(
        documentBytes({'s': text}, lineEnd: ''),
        _hex(
          '7b2273223a2022c3a9e282acf09f98805c75323032385c7532303239efbfbd227d',
        ),
      );
    });

    test('writes lone U+DC80..U+DCFF back as the original bytes', () {
      expect(
        documentBytes({
          'p\udcff': ['a\udc80b', '\udcff'],
        }, lineEnd: ''),
        _hex('7b2270ff223a205b22618062222c2022ff225d7d'),
      );
    });

    test('rejects another lone surrogate, as Python fails to encode it', () {
      expect(
        () => documentBytes({'s': '\ud800'}, lineEnd: ''),
        throwsFormatException,
      );
    });

    test('ends with the given line ending', () {
      expect(documentBytes(<Object?>[], lineEnd: lf), [0x5b, 0x5d, 0x0a]);
      expect(documentBytes(<Object?>[], lineEnd: crlf), [
        0x5b,
        0x5d,
        0x0d,
        0x0a,
      ]);
    });

    test('defaults to the line ending Python prints on this OS', () {
      expect(
        documentLineEnd(windows: true),
        '\r\n',
        reason: 'print() on Windows translates \\n to \\r\\n',
      );
      expect(documentLineEnd(windows: false), '\n');
    });
  });
}
