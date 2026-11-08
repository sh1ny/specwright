import 'dart:convert';
import 'dart:io';

import 'yaml.dart' show pyIntNormal;

// A JSON reader that accepts what Python's `json.loads` accepts and refuses what it refuses (design D4): `NaN`,
// `Infinity` and `-Infinity` are numbers, integers of any size stay `int` or `BigInt`, the last of two duplicate keys
// wins (and a trailing comma is refused as CPython 3.13 and later refuse it), a lone surrogate escape stays a lone surrogate, and a control character below U+0020 inside a string is
// refused. Dart's `jsonDecode` refuses the first and mangles the second, so material the script evaluated would stop
// the snapshot. The reader follows CPython's C scanner (`_json.c`) step for step, so a refused input has the same
// position; the words of the message are ours (D11).

/// A refused input. [message] is `<file>: <what>: line L column C (char P)` (no `<file>: ` when there is no file).
/// [position] is the character offset `json.JSONDecodeError.pos` gives; [line] and [column] count from 1.
class PyJsonException extends FormatException {
  PyJsonException(
    String message, {
    this.file,
    this.position,
    this.line,
    this.column,
  }) : super(message, null, position);

  final String? file;
  final int? position;
  final int? line;
  final int? column;
}

/// The nesting the reader follows. CPython 3.14 stops near 17,000 levels; a bounded (and shallower) recursion here keeps a hostile
/// file from exhausting the stack.
const int _maxNesting = 2000;

/// `json.loads(text)`. [file] names the source in a refusal's message.
Object? pyJsonDecode(String text, {String file = ''}) =>
    _Reader(text, file).decode();

/// Reads [path] as UTF-8 and decodes it. A file that cannot be read is `<path>: cannot read: <OS error>`, bytes that are
/// not UTF-8 are `<path>: not valid UTF-8`, and a refused document names the path and the position.
Object? pyJsonReadFile(String path) {
  final List<int> bytes;
  try {
    bytes = File(path).readAsBytesSync();
  } on FileSystemException catch (e) {
    final os = e.osError?.message.trim();
    throw PyJsonException(
      '$path: cannot read: ${os == null || os.isEmpty ? e.message : os}',
      file: path,
    );
  }
  final String text;
  try {
    final bom =
        bytes.length >= 3 &&
        bytes[0] == 0xef &&
        bytes[1] == 0xbb &&
        bytes[2] == 0xbf;
    // strict decoding; the byte-order mark Dart's decoder would drop is put back, so it is refused as Python refuses it
    final body = utf8.decode(bom ? bytes.sublist(3) : bytes);
    text = bom ? '\u{feff}$body' : body;
  } on FormatException catch (e) {
    throw PyJsonException('$path: not valid UTF-8: ${e.message}', file: path);
  }
  return pyJsonDecode(text, file: path);
}

class _Reader {
  _Reader(this.s, this.file);

  final String s;
  final String file;
  int depth = 0;

  /// Where the value just read ended (`scan_once`'s second result).
  int end = 0;

  Never fail(String what, int unit) {
    final position = _points(0, unit);
    var line = 1;
    var lastBreak = -1;
    for (var i = 0; i < unit; i++) {
      if (s.codeUnitAt(i) == 0x0a) {
        line++;
        lastBreak = i;
      }
    }
    final column = _points(lastBreak + 1, unit) + 1;
    final where = 'line $line column $column (char $position)';
    throw PyJsonException(
      file.isEmpty ? '$what: $where' : '$file: $what: $where',
      file: file.isEmpty ? null : file,
      position: position,
      line: line,
      column: column,
    );
  }

  /// The number of code points in `s[from:to]`.
  int _points(int from, int to) {
    var n = 0;
    for (var i = from; i < to; i++) {
      final c = s.codeUnitAt(i);
      if (c >= 0xd800 && c <= 0xdbff && i + 1 < to) {
        final d = s.codeUnitAt(i + 1);
        if (d >= 0xdc00 && d <= 0xdfff) i++;
      }
      n++;
    }
    return n;
  }

  bool _ws(int c) => c == 0x20 || c == 0x09 || c == 0x0a || c == 0x0d;

  int skipWs(int i) {
    while (i < s.length && _ws(s.codeUnitAt(i))) {
      i++;
    }
    return i;
  }

  Object? decode() {
    if (s.startsWith('\u{feff}')) {
      fail('Unexpected UTF-8 BOM (decode using utf-8-sig)', 0);
    }
    final v = value(skipWs(0));
    final after = skipWs(end);
    if (after != s.length) fail('Extra data', after);
    return v;
  }

  /// `scan_once`: the value at [idx]; sets [end].
  Object? value(int idx) {
    if (idx >= s.length) fail('Expecting value', idx);
    switch (s[idx]) {
      case '"':
        return string(idx + 1);
      case '{':
        return object(idx + 1);
      case '[':
        return array(idx + 1);
      case 'n':
        if (s.startsWith('null', idx)) {
          end = idx + 4;
          return null;
        }
      case 't':
        if (s.startsWith('true', idx)) {
          end = idx + 4;
          return true;
        }
      case 'f':
        if (s.startsWith('false', idx)) {
          end = idx + 5;
          return false;
        }
      case 'N':
        if (s.startsWith('NaN', idx)) {
          end = idx + 3;
          return double.nan;
        }
      case 'I':
        if (s.startsWith('Infinity', idx)) {
          end = idx + 8;
          return double.infinity;
        }
      case '-':
        if (s.startsWith('-Infinity', idx)) {
          end = idx + 9;
          return double.negativeInfinity;
        }
    }
    return number(idx);
  }

  bool _digit(int i) {
    if (i >= s.length) return false;
    final c = s.codeUnitAt(i);
    return c >= 0x30 && c <= 0x39;
  }

  /// `_match_number_unicode`: `-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][-+]?[0-9]+)?`, longest prefix.
  Object? number(int start) {
    var i = start;
    if (s[i] == '-') {
      i++;
      if (i >= s.length) fail('Expecting value', start);
    }
    final c = s.codeUnitAt(i);
    if (c >= 0x31 && c <= 0x39) {
      i++;
      while (_digit(i)) {
        i++;
      }
    } else if (c == 0x30) {
      i++;
    } else {
      fail('Expecting value', start);
    }
    var isFloat = false;
    if (i + 1 < s.length && s[i] == '.' && _digit(i + 1)) {
      isFloat = true;
      i += 2;
      while (_digit(i)) {
        i++;
      }
    }
    if (i + 1 < s.length && (s[i] == 'e' || s[i] == 'E')) {
      final backtrack = i;
      i++;
      if (i + 1 < s.length && (s[i] == '-' || s[i] == '+')) i++;
      while (_digit(i)) {
        i++;
      }
      if (_digit(i - 1)) {
        isFloat = true;
      } else {
        i = backtrack;
      }
    }
    end = i;
    final text = s.substring(start, i);
    if (isFloat) return double.parse(text);
    final digits = text.startsWith('-') ? text.length - 1 : text.length;
    if (digits > 4300) {
      fail(
        'Exceeds the limit (4300 digits) for integer string conversion',
        start,
      );
    }
    return pyIntNormal(BigInt.parse(text));
  }

  /// `scanstring_unicode` from [idx], just past the opening quote; sets [end] past the closing quote.
  String string(int idx) {
    final begin = idx - 1;
    final out = StringBuffer();
    var at = idx;
    final len = s.length;
    while (true) {
      var next = at;
      var c = 0;
      for (; next < len; next++) {
        c = s.codeUnitAt(next);
        if (c == 0x22 || c == 0x5c) break;
        if (c <= 0x1f) fail('Invalid control character at', next);
      }
      if (next >= len || !(c == 0x22 || c == 0x5c)) {
        fail('Unterminated string starting at', begin);
      }
      out.write(s.substring(at, next));
      next++;
      if (c == 0x22) {
        end = next;
        return out.toString();
      }
      if (next == len) fail('Unterminated string starting at', begin);
      final e = s[next];
      if (e != 'u') {
        at = next + 1;
        switch (e) {
          case '"':
            out.write('"');
          case r'\':
            out.write(r'\');
          case '/':
            out.write('/');
          case 'b':
            out.write('\b');
          case 'f':
            out.write('\f');
          case 'n':
            out.write('\n');
          case 'r':
            out.write('\r');
          case 't':
            out.write('\t');
          default:
            fail('Invalid \\escape', at - 2);
        }
        continue;
      }
      next++;
      var stop = next + 4;
      if (stop >= len) fail('Invalid \\uXXXX escape', next - 1);
      var code = _hex4(next, stop - 5);
      next = stop;
      if (code >= 0xd800 &&
          code <= 0xdbff &&
          stop + 6 < len &&
          s[next] == r'\' &&
          s[next + 1] == 'u') {
        next += 2;
        stop += 6;
        final low = _hex4(next, stop - 5);
        next = stop;
        if (low >= 0xdc00 && low <= 0xdfff) {
          code = 0x10000 + ((code - 0xd800) << 10) + (low - 0xdc00);
        } else {
          stop -= 6;
        }
      }
      out.writeCharCode(code);
      at = stop;
    }
  }

  /// Four hex digits at [from]; a bad one is `Invalid \uXXXX escape` at [errorAt].
  int _hex4(int from, int errorAt) {
    var v = 0;
    for (var i = from; i < from + 4; i++) {
      final c = s.codeUnitAt(i);
      final int d;
      if (c >= 0x30 && c <= 0x39) {
        d = c - 0x30;
      } else if (c >= 0x61 && c <= 0x66) {
        d = c - 0x61 + 10;
      } else if (c >= 0x41 && c <= 0x46) {
        d = c - 0x41 + 10;
      } else {
        fail('Invalid \\uXXXX escape', errorAt);
      }
      v = (v << 4) | d;
    }
    return v;
  }

  void _enter(int at) {
    if (++depth > _maxNesting) fail('Nesting is too deep', at);
  }

  /// `_parse_object_unicode` from [idx], just past the `{`.
  Map<String, Object?> object(int idx) {
    _enter(idx - 1);
    final out = <String, Object?>{};
    var at = skipWs(idx);
    if (at >= s.length || s[at] != '}') {
      while (true) {
        if (at >= s.length || s[at] != '"') {
          fail('Expecting property name enclosed in double quotes', at);
        }
        final key = string(at + 1);
        at = skipWs(end);
        if (at >= s.length || s[at] != ':') fail("Expecting ':' delimiter", at);
        at = skipWs(at + 1);
        out[key] = value(at);
        at = skipWs(end);
        if (at < s.length && s[at] == '}') break;
        if (at >= s.length || s[at] != ',') fail("Expecting ',' delimiter", at);
        final comma = at;
        at = skipWs(at + 1);
        if (at < s.length && s[at] == '}') {
          fail('Illegal trailing comma before end of object', comma);
        }
      }
    }
    depth--;
    end = at + 1;
    return out;
  }

  /// `_parse_array_unicode` from [idx], just past the `[`.
  List<Object?> array(int idx) {
    _enter(idx - 1);
    final out = <Object?>[];
    var at = skipWs(idx);
    if (at >= s.length || s[at] != ']') {
      while (true) {
        out.add(value(at));
        at = skipWs(end);
        if (at < s.length && s[at] == ']') break;
        if (at >= s.length || s[at] != ',') fail("Expecting ',' delimiter", at);
        final comma = at;
        at = skipWs(at + 1);
        if (at < s.length && s[at] == ']') {
          fail('Illegal trailing comma before end of array', comma);
        }
      }
    }
    depth--;
    end = at + 1;
    return out;
  }
}
