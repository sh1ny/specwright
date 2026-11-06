import 'dart:io' show Platform;
import 'dart:typed_data';

import 'codec.dart';

/// The text `json.dumps(value, ensure_ascii=False)` gives, with U+2028 and
/// U+2029 written as the six-character escapes \u2028 and \u2029
/// (`vcs.sh:43-45`).
///
/// Separators are `", "` and `": "`, keys keep their insertion order (use a
/// `LinkedHashMap`, Dart's default map), non-ASCII text stays raw, and only
/// `"`, `\` and the controls below U+0020 are escaped. A lone surrogate is
/// written as it is; [documentBytes] turns U+DC80..U+DCFF back into bytes.
/// Supported values are `null`, `bool`, `int`, `BigInt`, `String`, `List` and
/// `Map<String, _>`; anything else is an [ArgumentError].
String documentText(Object? value) {
  final out = StringBuffer();
  _write(out, value);
  return out
      .toString()
      .replaceAll(_lineSeparator, r'\u2028')
      .replaceAll(_paragraphSeparator, r'\u2029');
}

final String _lineSeparator = String.fromCharCode(0x2028);
final String _paragraphSeparator = String.fromCharCode(0x2029);

/// What `print()` ends a document with: `\r\n` on Windows (Python translates
/// `\n` there, even into a pipe), `\n` elsewhere.
String documentLineEnd({bool? windows}) =>
    (windows ?? Platform.isWindows) ? '\r\n' : '\n';

/// The bytes `vcs.sh` writes to stdout for [value]: [documentText], encoded
/// with surrogateescape (Python's `-X utf8` mode), then [lineEnd] (default
/// [documentLineEnd]).
Uint8List documentBytes(Object? value, {String? lineEnd}) =>
    encodeEscaped('${documentText(value)}${lineEnd ?? documentLineEnd()}');

void _write(StringBuffer out, Object? v) {
  switch (v) {
    case null:
      out.write('null');
    case bool():
      out.write(v ? 'true' : 'false');
    case int() || BigInt():
      out.write(v.toString());
    case String():
      _string(out, v);
    case List():
      out.write('[');
      for (var i = 0; i < v.length; i++) {
        if (i > 0) out.write(', ');
        _write(out, v[i]);
      }
      out.write(']');
    case Map():
      out.write('{');
      var first = true;
      for (final e in v.entries) {
        if (e.key is! String) {
          throw ArgumentError('document key is not a string: ${e.key}');
        }
        if (!first) out.write(', ');
        first = false;
        _string(out, e.key as String);
        out.write(': ');
        _write(out, e.value);
      }
      out.write('}');
    default:
      throw ArgumentError('cannot write ${v.runtimeType} in a document');
  }
}

void _string(StringBuffer out, String s) {
  out.write('"');
  for (final u in s.codeUnits) {
    switch (u) {
      case 0x22:
        out.write(r'\"');
      case 0x5c:
        out.write(r'\\');
      case 0x0a:
        out.write(r'\n');
      case 0x0d:
        out.write(r'\r');
      case 0x09:
        out.write(r'\t');
      case 0x08:
        out.write(r'\b');
      case 0x0c:
        out.write(r'\f');
      case < 0x20:
        out.write('\\u${u.toRadixString(16).padLeft(4, '0')}');
      default:
        out.writeCharCode(u);
    }
  }
  out.write('"');
}
