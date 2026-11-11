import 'dart:typed_data';

/// Decodes [bytes] as UTF-8 with Python's `surrogateescape` rule: each byte
/// that is not part of a valid UTF-8 sequence becomes the lone surrogate
/// U+DC00 plus the byte (0xFF becomes U+DCFF), one surrogate per byte. A valid
/// U+FFFD in the input stays a character. What counts as invalid is CPython's
/// decoder: overlong forms, encoded surrogates (ED A0..ED BF), code points
/// above U+10FFFF and truncated sequences.
///
/// Constraint C6: `sw vcs` never reads a name through Dart's argv or a
/// directory entry's `path` string, and never passes one as `Process.start`'s
/// working directory, because those string forms lose bytes that are not valid
/// UTF-8. Arguments come from stdin, directory entries from `find -print0`
/// output through the transport, and the working directory goes in the
/// transport too.
String decodeEscaped(List<int> bytes) => _decode(bytes, (units, run) {
  for (final b in run) {
    units.add(0xdc00 + b);
  }
});

/// Whether [text] holds a byte [decodeEscaped] escaped: a name that is not UTF-8.
bool hasEscapedBytes(String text) =>
    text.codeUnits.any((u) => u >= 0xdc80 && u <= 0xdcff);

/// Encodes [text] back to the bytes [decodeEscaped] read: U+DC80..U+DCFF
/// become the single bytes 0x80..0xFF, everything else is UTF-8. Any other
/// lone surrogate is a [FormatException], as Python's `surrogateescape`
/// encoder raises `UnicodeEncodeError` on it.
Uint8List encodeEscaped(String text) {
  final out = BytesBuilder(copy: false);
  final units = text.codeUnits;
  for (var i = 0; i < units.length; i++) {
    final u = units[i];
    if (u < 0x80) {
      out.addByte(u);
    } else if (u < 0x800) {
      out
        ..addByte(0xc0 | (u >> 6))
        ..addByte(0x80 | (u & 0x3f));
    } else if (u >= 0xd800 && u <= 0xdbff) {
      final next = i + 1 < units.length ? units[i + 1] : 0;
      if (next < 0xdc00 || next > 0xdfff) {
        throw FormatException('lone surrogate U+${u.toRadixString(16)}');
      }
      final cp = 0x10000 + ((u - 0xd800) << 10) + (next - 0xdc00);
      out
        ..addByte(0xf0 | (cp >> 18))
        ..addByte(0x80 | ((cp >> 12) & 0x3f))
        ..addByte(0x80 | ((cp >> 6) & 0x3f))
        ..addByte(0x80 | (cp & 0x3f));
      i++;
    } else if (u >= 0xdc80 && u <= 0xdcff) {
      out.addByte(u - 0xdc00);
    } else if (u >= 0xd800 && u <= 0xdfff) {
      throw FormatException('lone surrogate U+${u.toRadixString(16)}');
    } else {
      out
        ..addByte(0xe0 | (u >> 12))
        ..addByte(0x80 | ((u >> 6) & 0x3f))
        ..addByte(0x80 | (u & 0x3f));
    }
  }
  return out.takeBytes();
}

/// Display text from a tool: [decodeReplacing], then `\r\n` and a lone `\r`
/// become `\n` (Python's universal newlines).
String decodeText(List<int> bytes) =>
    decodeReplacing(bytes).replaceAll('\r\n', '\n').replaceAll('\r', '\n');

/// Output of `but`, as `vcs.sh` reads it: invalid bytes become U+FFFD, one per
/// maximal invalid subpart as Python's `errors='replace'` does, and newlines
/// are left alone.
String decodeReplacing(List<int> bytes) =>
    _decode(bytes, (units, run) => units.add(0xfffd));

/// A name or path that `sw` acts on or reports as a path was not valid UTF-8.
/// [what] says which name it was; [shown] is the name as it is reported: each
/// invalid byte as `\xHH`, or already rendered by the caller (a directory walk
/// shows U+FFFD).
class NotUtf8 implements Exception {
  NotUtf8(this.what, this.shown);

  final String what;
  final String shown;

  /// For a JSON document's `message` field and for the terminal.
  String get message => '$what is not valid UTF-8: $shown';

  @override
  String toString() => 'NotUtf8: $message';
}

/// A name or path that `sw` acts on or reports as a path is decoded strictly.
/// Display text is decoded with replacement.
///
/// Returns the decoded string, or throws [NotUtf8] naming [what] and showing
/// each invalid byte as `\xHH` in uppercase hex.
String decodeStrict(List<int> bytes, String what) {
  var valid = true;
  final shown = _decode(bytes, (units, run) {
    valid = false;
    for (final b in run) {
      final hex = b.toRadixString(16).toUpperCase().padLeft(2, '0');
      units.addAll('\\x$hex'.codeUnits);
    }
  });
  if (!valid) throw NotUtf8(what, shown);
  return shown;
}

String _decode(
  List<int> b,
  void Function(List<int> units, List<int> invalidRun) onInvalid,
) {
  final units = <int>[];
  final n = b.length;
  var i = 0;
  while (i < n) {
    final b0 = b[i];
    if (b0 < 0x80) {
      units.add(b0);
      i++;
      continue;
    }
    int need;
    var lo = 0x80;
    var hi = 0xbf;
    if (b0 >= 0xc2 && b0 <= 0xdf) {
      need = 1;
    } else if (b0 >= 0xe0 && b0 <= 0xef) {
      need = 2;
      if (b0 == 0xe0) lo = 0xa0;
      if (b0 == 0xed) hi = 0x9f;
    } else if (b0 >= 0xf0 && b0 <= 0xf4) {
      need = 3;
      if (b0 == 0xf0) lo = 0x90;
      if (b0 == 0xf4) hi = 0x8f;
    } else {
      onInvalid(units, [b0]);
      i++;
      continue;
    }
    var cp = b0 & (0x3f >> need);
    var k = 1;
    for (; k <= need; k++) {
      if (i + k >= n) break;
      final c = b[i + k];
      if (c < (k == 1 ? lo : 0x80) || c > (k == 1 ? hi : 0xbf)) break;
      cp = (cp << 6) | (c & 0x3f);
    }
    if (k <= need) {
      onInvalid(units, b.sublist(i, i + k));
      i += k;
      continue;
    }
    if (cp >= 0x10000) {
      units
        ..add(0xd800 + ((cp - 0x10000) >> 10))
        ..add(0xdc00 + ((cp - 0x10000) & 0x3ff));
    } else {
      units.add(cp);
    }
    i += need + 1;
  }
  return String.fromCharCodes(units);
}
