import 'dart:typed_data';

import 'package:specwright_cli/src/vcs/codec.dart';
import 'package:specwright_cli/src/vcs/document.dart';
import 'package:test/test.dart';

/// Assumption A3 of native-cli-commit: `json.dumps(value, ensure_ascii=False)`
/// writes a code point above U+FFFF (and U+2028) as raw UTF-8, and
/// `documentText` writes the same bytes.
///
/// Expected bytes come from CPython (`python -X utf8`):
/// `json.dumps('a\U0001F600\u2028\x01"b', ensure_ascii=False).encode()`.
void main() {
  test('writes the bytes json.dumps(ensure_ascii=False) writes', () {
    final value = 'a\u{1F600}\u2028\x01"b';
    final expected = Uint8List.fromList([
      0x22, 0x61, // "a
      0xf0, 0x9f, 0x98, 0x80, // U+1F600 raw
      0xe2, 0x80, 0xa8, // U+2028 raw
      0x5c, 0x75, 0x30, 0x30, 0x30, 0x31, // \u0001
      0x5c, 0x22, // \"
      0x62, 0x22, // b"
    ]);
    expect(encodeEscaped(documentText(value)), expected);
    expect(documentBytes(value), [...expected, 0x0a]);
  });
}
