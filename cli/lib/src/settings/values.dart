import 'dart:collection';
import 'dart:convert';

import '../commit/task_cover.dart' show isPySpace;

// The value rules the settings consumers still share (design D1, ADR 0038): the mapping type the reader returns and
// the Python text and number rules a setting's message depends on (`str(v)`, truthiness, `\d`, `\s`, UTF-8 decoding
// with replacement). The YAML reading itself is `reader.dart`. Text is held as UTF-16 code units.

/// A YAML mapping that also keeps each scalar's text as written (`yes` stays `yes` in messages).
class YamlMap extends MapBase<String, Object?> {
  /// The text of every key whose value was a plain or quoted scalar or a flow collection, trimmed, as written.
  final Map<String, String> text = {};
  final Map<String, Object?> _m = {};

  @override
  Object? operator [](Object? key) => _m[key];

  @override
  void operator []=(String key, Object? value) => _m[key] = value;

  @override
  void clear() => _m.clear();

  @override
  Iterable<String> get keys => _m.keys;

  @override
  Object? remove(Object? key) => _m.remove(key);
}

// ---- Python's text and number rules -----------------------------------------------------------------------------

final RegExp _nd = RegExp(r'^\p{Nd}$', unicode: true);

bool _isNd(int rune) => _nd.hasMatch(String.fromCharCode(rune));

/// The value of a Unicode decimal digit, or null. The digits of a script are ten contiguous code points from the zero
/// (the mathematical digits are five such runs end to end), so the value is the distance from the start of the run
/// of decimal digits, modulo ten.
int? _digit(int rune) {
  if (rune >= 0x30 && rune <= 0x39) return rune - 0x30;
  if (rune < 0x80 || !_isNd(rune)) return null;
  var start = rune;
  while (start > 0 && _isNd(start - 1)) {
    start--;
  }
  return (rune - start) % 10;
}

/// `int(digits)` for a non-empty string of Unicode decimal digits (Python's `\d+`), else null.
BigInt? pyDecimalValue(String digits) {
  if (digits.isEmpty) return null;
  final out = StringBuffer();
  for (final r in digits.runes) {
    final d = _digit(r);
    if (d == null) return null;
    out.write(d);
  }
  return BigInt.parse(out.toString());
}

/// A Python integer as the narrowest Dart value: `int` when it fits 64 bits, else [BigInt].
Object pyIntNormal(BigInt n) => n.isValidInt ? n.toInt() : n;

/// Python's `str(v)` for what the reader produces: `None`, `True`, `False`, integers, text, lists and dicts. The `repr`
/// of a string inside a list or dict is the common form (single quotes unless it holds one and no double quote,
/// `\\`, `\n`, `\r`, `\t` and control characters escaped); a non-ASCII character is written as it is unless it is a
/// control or a space.
String pyStr(Object? v) => v is String ? v : pyRepr(v);

/// Python's `repr(v)` for the same values.
String pyRepr(Object? v) => switch (v) {
  null => 'None',
  true => 'True',
  false => 'False',
  int() || BigInt() => '$v',
  String() => _strRepr(v),
  List() => '[${v.map(pyRepr).join(', ')}]',
  Map() =>
    '{${v.entries.map((e) => '${pyRepr(e.key)}: ${pyRepr(e.value)}').join(', ')}}',
  _ => '$v',
};

String _strRepr(String s) {
  final quote = s.contains("'") && !s.contains('"') ? '"' : "'";
  final out = StringBuffer(quote);
  for (final r in s.runes) {
    if (String.fromCharCode(r) == quote || r == 0x5c) {
      out
        ..write('\\')
        ..writeCharCode(r);
    } else if (r == 0x0a) {
      out.write(r'\n');
    } else if (r == 0x0d) {
      out.write(r'\r');
    } else if (r == 0x09) {
      out.write(r'\t');
    } else if (r < 0x20 || (r >= 0x7f && r <= 0xa0) || r == 0xad) {
      out.write('\\x${r.toRadixString(16).padLeft(2, '0')}');
    } else if (r > 0xff && r < 0x10000 && isPySpace(r)) {
      out.write('\\u${r.toRadixString(16).padLeft(4, '0')}');
    } else {
      out.writeCharCode(r);
    }
  }
  return (out..write(quote)).toString();
}

/// Python truthiness: `None`, `False`, zero, and empty text, lists and dicts are false.
bool pyTruthy(Object? v) => switch (v) {
  null => false,
  bool() => v,
  int() => v != 0,
  BigInt() => v != BigInt.zero,
  String() => v.isNotEmpty,
  List() => v.isNotEmpty,
  Map() => v.isNotEmpty,
  _ => true,
};

/// `setting_text`: the setting as the user wrote it, for messages; the parsed value when the text is not kept (a
/// boolean is `str(bool).lower()`).
String settingText(Object? m, String key) {
  if (m is YamlMap) {
    final t = m.text[key];
    if (t != null) return t;
  }
  final Object? v = m is Map ? m[key] : null;
  return v is bool ? (v ? 'true' : 'false') : pyStr(v);
}

/// Decodes UTF-8 as Python's `bytes.decode('utf-8', errors='replace')` does: a bad sequence is U+FFFD and a leading
/// byte-order mark stays U+FEFF (Dart's decoder drops it).
String pyUtf8Decode(List<int> bytes) {
  final bom =
      bytes.length >= 3 &&
      bytes[0] == 0xef &&
      bytes[1] == 0xbb &&
      bytes[2] == 0xbf;
  final text = utf8.decode(
    bom ? bytes.sublist(3) : bytes,
    allowMalformed: true,
  );
  return bom ? '﻿$text' : text;
}

/// Python's `\s` class, written out: the characters `str.isspace` takes (the body of a regex character class).
const String pySpaceClass = r'\t-\r\x1c-\x20\x85\xa0  -     　';
