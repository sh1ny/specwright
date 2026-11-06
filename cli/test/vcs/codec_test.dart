import 'dart:typed_data';

import 'package:specwright_cli/src/vcs/codec.dart';
import 'package:test/test.dart';

/// Expected code points come from CPython 3.14:
/// `bytes.fromhex(h).decode('utf-8', 'surrogateescape' | 'replace')`.
const List<(String, List<int>, List<int>)> _cpython = [
  ('', [], []),
  ('616263', [0x61, 0x62, 0x63], [0x61, 0x62, 0x63]),
  ('c3a9', [0xe9], [0xe9]),
  ('e282ac', [0x20ac], [0x20ac]),
  ('f09f9880', [0x1f600], [0x1f600]),
  ('ff', [0xdcff], [0xfffd]),
  ('80', [0xdc80], [0xfffd]),
  ('c0af', [0xdcc0, 0xdcaf], [0xfffd, 0xfffd]),
  ('c080', [0xdcc0, 0xdc80], [0xfffd, 0xfffd]),
  ('e08080', [0xdce0, 0xdc80, 0xdc80], [0xfffd, 0xfffd, 0xfffd]),
  ('e0a080', [0x800], [0x800]),
  ('eda080', [0xdced, 0xdca0, 0xdc80], [0xfffd, 0xfffd, 0xfffd]),
  ('edbfbf', [0xdced, 0xdcbf, 0xdcbf], [0xfffd, 0xfffd, 0xfffd]),
  (
    'f4908080',
    [0xdcf4, 0xdc90, 0xdc80, 0xdc80],
    [0xfffd, 0xfffd, 0xfffd, 0xfffd],
  ),
  ('f4808080', [0x100000], [0x100000]),
  ('f5', [0xdcf5], [0xfffd]),
  ('c3', [0xdcc3], [0xfffd]),
  ('e282', [0xdce2, 0xdc82], [0xfffd]),
  ('f09f98', [0xdcf0, 0xdc9f, 0xdc98], [0xfffd]),
  ('e28241', [0xdce2, 0xdc82, 0x41], [0xfffd, 0x41]),
  ('f09f41', [0xdcf0, 0xdc9f, 0x41], [0xfffd, 0x41]),
  ('f09f9841', [0xdcf0, 0xdc9f, 0xdc98, 0x41], [0xfffd, 0x41]),
  ('efbfbd', [0xfffd], [0xfffd]),
  ('41ff42', [0x41, 0xdcff, 0x42], [0x41, 0xfffd, 0x42]),
  ('ffff', [0xdcff, 0xdcff], [0xfffd, 0xfffd]),
  ('e228a1', [0xdce2, 0x28, 0xdca1], [0xfffd, 0x28, 0xfffd]),
  ('c2c2a9', [0xdcc2, 0xa9], [0xfffd, 0xa9]),
  ('808080', [0xdc80, 0xdc80, 0xdc80], [0xfffd, 0xfffd, 0xfffd]),
  (
    'f888808080',
    [0xdcf8, 0xdc88, 0xdc80, 0xdc80, 0xdc80],
    [0xfffd, 0xfffd, 0xfffd, 0xfffd, 0xfffd],
  ),
  ('fe', [0xdcfe], [0xfffd]),
  (
    'eda080edb080',
    [0xdced, 0xdca0, 0xdc80, 0xdced, 0xdcb0, 0xdc80],
    [0xfffd, 0xfffd, 0xfffd, 0xfffd, 0xfffd, 0xfffd],
  ),
  ('610062', [0x61, 0x0, 0x62], [0x61, 0x0, 0x62]),
  (
    'f0808080',
    [0xdcf0, 0xdc80, 0xdc80, 0xdc80],
    [0xfffd, 0xfffd, 0xfffd, 0xfffd],
  ),
  ('f0908041', [0xdcf0, 0xdc90, 0xdc80, 0x41], [0xfffd, 0x41]),
  ('f18080', [0xdcf1, 0xdc80, 0xdc80], [0xfffd]),
  ('e180e18080', [0xdce1, 0xdc80, 0x1000], [0xfffd, 0x1000]),
  ('c1bf', [0xdcc1, 0xdcbf], [0xfffd, 0xfffd]),
  ('f48fbfbf', [0x10ffff], [0x10ffff]),
  ('f490', [0xdcf4, 0xdc90], [0xfffd, 0xfffd]),
  ('e0', [0xdce0], [0xfffd]),
  ('e0a0', [0xdce0, 0xdca0], [0xfffd]),
  ('c3a9ff', [0xe9, 0xdcff], [0xe9, 0xfffd]),
  ('ffc3a9', [0xdcff, 0xe9], [0xfffd, 0xe9]),
  ('dfbf', [0x7ff], [0x7ff]),
  ('e09fbf', [0xdce0, 0xdc9f, 0xdcbf], [0xfffd, 0xfffd, 0xfffd]),
  (
    'f08fbfbf',
    [0xdcf0, 0xdc8f, 0xdcbf, 0xdcbf],
    [0xfffd, 0xfffd, 0xfffd, 0xfffd],
  ),
  ('ed9fbf', [0xd7ff], [0xd7ff]),
  ('eda0', [0xdced, 0xdca0], [0xfffd, 0xfffd]),
];

Uint8List _bytes(String hex) => Uint8List.fromList([
  for (var i = 0; i < hex.length; i += 2)
    int.parse(hex.substring(i, i + 2), radix: 16),
]);

void main() {
  group('decodeEscaped (surrogateescape)', () {
    for (final (hex, escaped, _) in _cpython) {
      test('matches CPython for "$hex"', () {
        expect(decodeEscaped(_bytes(hex)).runes.toList(), escaped);
      });
    }
  });

  group('encodeEscaped', () {
    for (final (hex, _, _) in _cpython) {
      test('round-trips the bytes "$hex"', () {
        final bytes = _bytes(hex);
        expect(encodeEscaped(decodeEscaped(bytes)), bytes);
      });
    }

    test('encodes a valid U+FFFD as its own three bytes', () {
      expect(encodeEscaped('\u{fffd}'), [0xef, 0xbf, 0xbd]);
    });

    test('encodes non-BMP text as four bytes', () {
      expect(encodeEscaped('\u{1f600}'), [0xf0, 0x9f, 0x98, 0x80]);
    });

    test('rejects a lone surrogate outside U+DC80..U+DCFF', () {
      expect(() => encodeEscaped('\ud800'), throwsFormatException);
      expect(() => encodeEscaped('\udc7f'), throwsFormatException);
      expect(() => encodeEscaped('\udd00'), throwsFormatException);
    });

    test('keeps an escaped byte after a valid pair', () {
      expect(encodeEscaped('\u{1f600}\udcff'), [0xf0, 0x9f, 0x98, 0x80, 0xff]);
    });
  });

  group('decodeText (git and jj output)', () {
    test('turns CRLF and lone CR into LF, as Python universal newlines', () {
      final text = decodeText(
        _bytes('610d0a62 0d63 0a64 0d0d0a'.replaceAll(' ', '')),
      );
      expect(text, 'a\nb\nc\nd\n\n');
    });

    test('a trailing lone CR becomes LF', () {
      expect(decodeText(_bytes('610d')), 'a\n');
    });

    test('escapes invalid bytes before the newline pass', () {
      expect(decodeText(_bytes('ff0d0a')).codeUnits, [0xdcff, 0x0a]);
    });
  });

  group('decodeReplacing (but output)', () {
    for (final (hex, _, replaced) in _cpython) {
      test('matches CPython errors=replace for "$hex"', () {
        expect(decodeReplacing(_bytes(hex)).runes.toList(), replaced);
      });
    }

    test('leaves CRLF alone', () {
      expect(decodeReplacing(_bytes('610d0a')), 'a\r\n');
    });
  });
}
