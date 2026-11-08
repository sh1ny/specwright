import 'dart:collection';
import 'dart:convert';

import '../commit/task_cover.dart' show isPySpace, pySplitLines, pyStrip;

// The settings reader of `pr-pair.sh` (`parse_yaml`, `scalar`, `unquote`, `block_scalar` and the strict check
// `yaml_problem`, pr-pair.sh:375-785), ported value for value (design D3). It reads `openspec/specwright.yaml`
// leniently for local settings; `policy` runs the strict check on a remote file first, because a file the lenient
// reader would skip, drop or misread must not authorize a merge. Python's text rules are kept where a value depends on
// them: `str.splitlines`, `str.strip`, `\s` as `str.isspace`, `\d` as any Unicode decimal digit with `int()`'s
// conversion of it. Text is held as UTF-16 code units; the places where Python counts code points (a key's length,
// a code point in a message) count them.

/// A YAML mapping that also keeps each plain scalar's text as written (`yes` stays `yes` in messages), as the
/// script's `Map` does.
class YamlMap extends MapBase<String, Object?> {
  /// The text of every key that took the plain-scalar branch, trimmed, as written. A later duplicate that is a block
  /// scalar or a nested map does not clear it.
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

String _rstrip(String s) {
  var hi = s.length;
  while (hi > 0 && isPySpace(s.codeUnitAt(hi - 1))) {
    hi--;
  }
  return s.substring(0, hi);
}

int _leadSpaces(String s) {
  var i = 0;
  while (i < s.length && s.codeUnitAt(i) == 0x20) {
    i++;
  }
  return i;
}

/// The length of the leading run of [isPySpace] characters.
int _leadSpace(String s) {
  var i = 0;
  while (i < s.length && isPySpace(s.codeUnitAt(i))) {
    i++;
  }
  return i;
}

bool _blank(String s) => _leadSpace(s) == s.length;

/// `s[n:]` in Python: by code point.
String _dropPoints(String s, int n) => String.fromCharCodes(s.runes.skip(n));

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
  return bom ? '\uFEFF$text' : text;
}

// ---- the lenient reader -------------------------------------------------------------------------------------------

String _stripComment(String s) {
  String? q;
  var esc = false;
  for (var i = 0; i < s.length; i++) {
    final ch = s[i];
    if (esc) {
      esc = false;
    } else if (q != null) {
      if (q == '"' && ch == r'\') {
        esc = true;
      } else if (ch == q) {
        q = null;
      }
    } else if (ch == '"' || ch == "'") {
      q = ch;
    } else if (ch == '#' && (i == 0 || s[i - 1] == ' ' || s[i - 1] == '\t')) {
      return s.substring(0, i);
    }
  }
  return s;
}

List<String> _splitTop(String s) {
  final parts = <String>[];
  var depth = 0;
  String? q;
  var esc = false;
  final cur = StringBuffer();
  for (var i = 0; i < s.length; i++) {
    final ch = s[i];
    if (esc) {
      esc = false;
    } else if (q != null) {
      if (q == '"' && ch == r'\') {
        esc = true;
      } else if (ch == q) {
        q = null;
      }
    } else if (ch == '"' || ch == "'") {
      q = ch;
    } else if (ch == '{' || ch == '[') {
      depth++;
    } else if (ch == '}' || ch == ']') {
      depth--;
    } else if (ch == ',' && depth == 0) {
      parts.add(cur.toString());
      cur.clear();
      continue;
    }
    cur.write(ch);
  }
  final last = cur.toString();
  if (!_blank(last)) parts.add(last);
  return parts;
}

/// `scalar`: one value of the reader. Flow maps are plain maps and flow lists lists; `true`/`yes`/`false`/`no` in any
/// case are booleans, `null` and `~` (exactly) are null, `-?\d+` is an integer, and the rest is text.
Object? yamlScalar(String raw) {
  final v = pyStrip(raw);
  if (v.isEmpty) return null;
  final first = v[0];
  final last = v[v.length - 1];
  if (first == '{' && last == '}') {
    final out = <String, Object?>{};
    for (final part in _splitTop(v.substring(1, v.length - 1))) {
      final c = part.indexOf(':');
      final k = c < 0 ? part : part.substring(0, c);
      final val = c < 0 ? '' : part.substring(c + 1);
      out[yamlUnquote(pyStrip(k))] = yamlScalar(val);
    }
    return out;
  }
  if (first == '[' && last == ']') {
    return [
      for (final p in _splitTop(v.substring(1, v.length - 1))) yamlScalar(p),
    ];
  }
  if ((first == '"' || first == "'") && last == first && v.length >= 2) {
    return yamlUnquote(v);
  }
  final lower = v.toLowerCase();
  if (lower == 'true' || lower == 'yes') return true;
  if (lower == 'false' || lower == 'no') return false;
  if (v == 'null' || v == '~') return null;
  final neg = first == '-';
  final n = pyDecimalValue(neg ? v.substring(1) : v);
  if (n != null) return pyIntNormal(neg ? -n : n);
  return v;
}

const Map<String, String> _escapes = {
  '0': '\x00',
  'a': '\x07',
  'b': '\x08',
  't': '\t',
  '\t': '\t',
  'n': '\n',
  'v': '\x0b',
  'f': '\x0c',
  'r': '\r',
  'e': '\x1b',
  ' ': ' ',
  '"': '"',
  '/': '/',
  r'\': r'\',
  'N': '\u0085',
  '_': '\u{a0}',
  'L': '\u{2028}',
  'P': '\u{2029}',
};

final RegExp _escapeRe = RegExp(
  r'\\(x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4}|U[0-9a-fA-F]{8}|.)',
  dotAll: true,
);

/// `unquote`: strips a scalar's quotes and decodes them as YAML does: `''` in single quotes, backslash escapes in
/// double.
String yamlUnquote(String k) {
  if (k.length < 2 || (k[0] != '"' && k[0] != "'") || k[k.length - 1] != k[0]) {
    return k;
  }
  final body = k.substring(1, k.length - 1);
  if (k[0] == "'") return body.replaceAll("''", "'");
  return body.replaceAllMapped(_escapeRe, (m) {
    final e = m.group(1)!;
    if (e.length > 1) {
      return String.fromCharCode(int.parse(e.substring(1), radix: 16));
    }
    return _escapes[e] ?? m.group(0)!;
  });
}

final RegExp _blockHeader = RegExp(r'^([|>])([+-]?)\p{Nd}*$', unicode: true);

/// Python's `\s` class, written out: the characters `str.isspace` takes.
const String _sp =
    r'\t-\r\x1c-\x20\x85\xa0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000';

/// [_sp] for the other readers of the settings (the body of a regex character class).
const String pySpaceClass = _sp;

/// The `key: value` line: a quoted key or a plain one, then a colon and, after Python-space, the value.
final RegExp _keyRe = RegExp(
  r'''^((?:"(?:[^"\\]|\\.)*"|'(?:[^']|'')*'|[^:''' +
      _sp +
      r'''][^:]*?)):(?:[''' +
      _sp +
      r''']+(.*))?$''',
  dotAll: true,
);

class _Line {
  _Line(this.indent, this.body, this.row);
  final int indent;
  final String body;
  final int row;
}

/// `block_scalar`: a `|` or `>` block after a key at [indent], read from [raw] lines from [start]; returns the value
/// and the index of the next raw line.
(String, int) _blockScalar(
  List<String> raw,
  int start,
  int indent,
  String style,
  String chomp,
) {
  var end = start;
  while (end < raw.length &&
      (_blank(raw[end]) || _leadSpaces(raw[end]) > indent)) {
    end++;
  }
  final body = raw.sublist(start, end);
  final filled = [
    for (final l in body)
      if (!_blank(l)) l,
  ];
  final pad = filled.isEmpty ? 0 : _leadSpaces(filled.first);
  final lines = [for (final l in body) _blank(l) ? '' : _dropPoints(l, pad)];
  var trailing = 0;
  while (lines.isNotEmpty && lines.last.isEmpty) {
    lines.removeLast();
    trailing++;
  }
  String text;
  if (style == '|') {
    text = lines.join('\n');
  } else {
    final b = StringBuffer();
    var prev = false;
    var first = true;
    for (final l in lines) {
      if (l.isEmpty) {
        b.write('\n');
      } else {
        b.write(!first && prev ? ' $l' : l);
      }
      prev = l.isNotEmpty;
      first = false;
    }
    text = b.toString();
  }
  if (lines.isEmpty || chomp == '-') return (text, end);
  return ('$text\n${chomp == '+' ? '\n' * trailing : ''}', end);
}

/// `parse_yaml`: the lenient read. Lines it cannot read are skipped.
YamlMap parseYaml(String text) {
  final raw = pySplitLines(text);
  final lines = <_Line>[];
  for (var n = 0; n < raw.length; n++) {
    final s = _rstrip(_stripComment(raw[n]));
    if (!_blank(s)) lines.add(_Line(_leadSpaces(s), pyStrip(s), n));
  }
  if (lines.isEmpty) return YamlMap();
  return _block(raw, lines, 0, lines[0].indent).$1;
}

(YamlMap, int) _block(
  List<String> raw,
  List<_Line> lines,
  int start,
  int indent,
) {
  var i = start;
  final d = YamlMap();
  while (i < lines.length && lines[i].indent == indent) {
    final m = _keyRe.firstMatch(lines[i].body);
    if (m == null) {
      i++;
      continue;
    }
    final key = yamlUnquote(pyStrip(m.group(1)!));
    final val = m.group(2);
    final row = lines[i].row;
    i++;
    final header = val == null || val.isEmpty
        ? null
        : _blockHeader.firstMatch(pyStrip(val));
    if (header != null) {
      final (value, end) = _blockScalar(
        raw,
        row + 1,
        indent,
        header.group(1)!,
        header.group(2)!,
      );
      d[key] = value;
      while (i < lines.length && lines[i].row < end) {
        i++;
      }
    } else if (val == null || _blank(val)) {
      if (i < lines.length && lines[i].indent > indent) {
        final (nested, next) = _block(raw, lines, i, lines[i].indent);
        d[key] = nested;
        i = next;
      } else {
        d[key] = null;
      }
    } else {
      d[key] = yamlScalar(val);
      d.text[key] = pyStrip(val);
    }
  }
  return (d, i);
}

// ---- the strict check ---------------------------------------------------------------------------------------------

/// What the strict check found: the message, with the `line N:` prefix when it has a line.
class _YamlBad implements Exception {
  _YamlBad(this.why);
  final String why;
}

const int _maxDepth = 32;
const String _plainStartBad = '[]{},#&*!|>\'"%@`';
const String _flowChars = ',[]{}';
const String _escapeKeys = '0abt\tnvfre "/\\N_LP';

Never _fail(String why) => throw _YamlBad(why);

/// Length of the double-quoted escape at `s[i]` (a backslash) as YAML defines it, or 0 when YAML has no such escape.
int _escapeLen(String s, int i) {
  final c = i + 1 < s.length ? s[i + 1] : '';
  if (c == 'x' || c == 'u' || c == 'U') {
    final n = c == 'x' ? 2 : (c == 'u' ? 4 : 8);
    final end = i + 2 + n;
    if (end > s.length) return 0;
    final h = s.substring(i + 2, end);
    if (!RegExp('^[0-9a-fA-F]{$n}\$').hasMatch(h)) return 0;
    final v = int.parse(h, radix: 16);
    return (v >= 0xd800 && v <= 0xdfff) || v > 0x10ffff ? 0 : 2 + n;
  }
  return c.isNotEmpty && _escapeKeys.contains(c) ? 2 : 0;
}

/// Index after the quoted scalar starting at `v[i]`.
int _quotedEnd(String v, int i) {
  final q = v[i];
  var j = i + 1;
  while (j < v.length) {
    if (q == '"' && v[j] == r'\') {
      final n = _escapeLen(v, j);
      if (n == 0) {
        _fail(
          'unknown escape `${v.substring(j, j + 2 > v.length ? v.length : j + 2)}`',
        );
      }
      j += n;
      continue;
    }
    if (v[j] == q) {
      if (q == "'" && j + 1 < v.length && v[j + 1] == "'") {
        j += 2;
        continue;
      }
      return j + 1;
    }
    j++;
  }
  _fail('unterminated quote');
}

/// YAML ends a simple (implicit) key within 1024 characters; the reader has no limit.
String? _keyTooLong(String k) => pyStrip(k).runes.length >= 1024
    ? "a key of 1024 characters or more (YAML's simple-key limit)"
    : null;

int _skipWs(String v, int i) {
  while (i < v.length && (v[i] == ' ' || v[i] == '\t')) {
    i++;
  }
  return i;
}

/// Throws unless [v] is a plain scalar the lenient reader reads as YAML does.
void _plainOk(String v, bool flow, [bool key = false]) {
  if (v.isEmpty) _fail('an empty entry');
  final c = v[0];
  if (_plainStartBad.contains(c) ||
      ('-?:'.contains(c) &&
          (v.length == 1 ||
              ' \t'.contains(v[1]) ||
              (flow && _flowChars.contains(v[1])))) ||
      (flow && '?:'.contains(c))) {
    _fail(
      '`$c` cannot start a plain value (anchors, tags, aliases and directives are not read)',
    );
  }
  if (v.contains(' #') || v.contains('\t#')) {
    _fail('a comment the reader would keep as text');
  }
  if (v.contains(': ') || v.contains(':\t') || v.endsWith(':')) {
    _fail('a plain value holds `:` before a space or tab');
  }
  if (flow &&
      v
          .split('')
          .any((ch) => _flowChars.contains(ch) || ch == "'" || ch == '"')) {
    _fail('a flow entry holds `,`, a bracket or a quote outside quotes');
  }
  if (key && v.contains(':')) {
    _fail('a flow key holds `:` (the reader splits at the first one)');
  }
}

/// Index after one flow node at `v[i]` (already past spaces): a collection, a quoted or a plain scalar.
int _flowNode(String v, int i, {bool key = false, int depth = 0}) {
  if (i >= v.length) _fail('an empty entry');
  final c = v[i];
  if (key && (c == '[' || c == '{')) _fail('a flow key that is a collection');
  if (c == '[' || c == '{') {
    if (depth >= _maxDepth) {
      _fail('flow collections nested more than $_maxDepth deep');
    }
    final close = c == '[' ? ']' : '}';
    var j = i + 1;
    final keys = <String>{};
    while (true) {
      j = _skipWs(v, j);
      if (j >= v.length) _fail('unterminated `$c`');
      if (v[j] == close) return j + 1;
      if (v[j] == ',') _fail('an empty entry');
      final start = j;
      j = _flowNode(v, j, key: c == '{', depth: depth + 1);
      j = _skipWs(v, j);
      if (c == '{') {
        final entry = pyStrip(v.substring(start, j));
        final why = _keyTooLong(entry);
        if (why != null) _fail(why);
        final k = yamlUnquote(entry);
        if (entry == '<<') {
          _fail('a `<<` merge key (YAML merges it in, the reader does not)');
        }
        if (keys.contains(k)) _fail('duplicate key `$k`');
        keys.add(k);
        if (j < v.length && v[j] == ':') {
          if (!(j + 1 < v.length && (v[j + 1] == ' ' || v[j + 1] == '\t'))) {
            _fail("a flow key's `:` not followed by a space");
          }
          j = _skipWs(v, j + 1);
          if (j < v.length && v[j] != ',' && v[j] != '}') {
            j = _skipWs(v, _flowNode(v, j, depth: depth + 1));
          }
        }
      } else if (j < v.length && v[j] == ':') {
        _fail('a `key: value` pair inside `[...]` is read as text');
      }
      if (j >= v.length) _fail('unterminated `$c`');
      if (v[j] == ',') {
        j = _skipWs(v, j + 1);
        if (j < v.length && v[j] == close) {
          _fail('a trailing comma (the reader keeps it as an empty entry)');
        }
      } else if (v[j] != close) {
        _fail('`${v[j]}` where `,` or `$close` belongs');
      }
    }
  }
  if (c == ']' || c == '}') _fail('unbalanced `$c`');
  if (c == '"' || c == "'") return _quotedEnd(v, i);
  var j = i;
  // libyaml ends a flow plain scalar at `:` before a space or any of `,?[]{}`
  while (j < v.length &&
      !_flowChars.contains(v[j]) &&
      !(v[j] == ':' && (j + 1 == v.length || ' \t,?[]{}'.contains(v[j + 1])))) {
    j++;
  }
  _plainOk(_rstrip(v.substring(i, j)), true, key);
  return j;
}

/// Why a value (or a quoted key) is not YAML the lenient reader reads as written, or null.
String? _valueProblem(String raw) {
  final v = pyStrip(raw);
  try {
    final c = v[0];
    if (c == '[' || c == '{' || c == '"' || c == "'") {
      final j = (c == '[' || c == '{') ? _flowNode(v, 0) : _quotedEnd(v, 0);
      if (!_blank(v.substring(j))) {
        _fail(
          'text after the closing ${c == '[' || c == '{' ? 'bracket' : 'quote'}',
        );
      }
    } else {
      _plainOk(v, false);
    }
  } on _YamlBad catch (e) {
    return e.why;
  }
  return null;
}

int _rowAt(String text, int offset) {
  var row = 1;
  for (var i = 0; i < offset; i++) {
    final c = text.codeUnitAt(i);
    if (c == 0x0d) {
      if (i + 1 < offset && text.codeUnitAt(i + 1) == 0x0a) i++;
      row++;
    } else if (c == 0x0a) {
      row++;
    }
  }
  return row;
}

String _hex(int cp) => cp.toRadixString(16).toUpperCase().padLeft(4, '0');

/// YAML allows tab, LF, CR and printable characters; U+0085, U+2028, U+2029 and U+FEFF are excluded too.
bool _yamlChar(int c) =>
    c == 0x09 ||
    c == 0x0a ||
    c == 0x0d ||
    (c >= 0x20 && c <= 0x7e) ||
    (c >= 0xa0 && c <= 0xd7ff && c != 0x2028 && c != 0x2029) ||
    (c >= 0xe000 && c <= 0xfffd && c != 0xfeff) ||
    (c >= 0x10000 && c <= 0x10ffff);

/// `yaml_problem`: the first line the lenient reader would skip, drop or misread, as `line N: why`, or null.
///
/// The lenient reader is for local settings; `policy` authorizes a merge from a remote file, so a file it cannot read
/// whole is unknown there (ADR 0020 D4). This checks the YAML subset the reader reads as YAML does: block mappings,
/// flow collections, quoted and plain scalars, `|`/`>` blocks. What it would read otherwise (block sequences,
/// anchors, tags, aliases, tabs in indentation, duplicate keys, explicit indentation indicators) is a problem too, so
/// it fails closed.
String? yamlProblem(String text) {
  for (var i = 0; i < text.length; i++) {
    var c = text.codeUnitAt(i);
    if (c >= 0xd800 && c <= 0xdbff && i + 1 < text.length) {
      final d = text.codeUnitAt(i + 1);
      if (d >= 0xdc00 && d <= 0xdfff) {
        c = 0x10000 + ((c - 0xd800) << 10) + (d - 0xdc00);
      }
    }
    if (!_yamlChar(c)) {
      return 'line ${_rowAt(text, i)}: a control character or line separator (U+${_hex(c)})';
    }
    if (c >= 0x10000) i++;
  }
  for (var i = 0; i < text.length; i++) {
    final c = text.codeUnitAt(i);
    if (isPySpace(c) && c != 0x20 && c != 0x09 && c != 0x0d && c != 0x0a) {
      return 'line ${_rowAt(text, i)}: a space character YAML does not separate with (U+${_hex(c)})';
    }
  }
  final raw = pySplitLines(text);
  final lines = <_Line>[];
  var marker = false; // the one `---` allowed, before any key
  int? block; // the key's indentation while inside a `|`/`>` block
  for (var n = 0; n < raw.length; n++) {
    final r = raw[n];
    if (_blank(r) && r.contains('\t')) {
      return 'line ${n + 1}: a tab in the indentation';
    }
    if (block != null && (_blank(r) || _leadSpaces(r) > block)) {
      continue; // block text: a tab after its space indentation is text
    }
    block = null;
    if (r.substring(0, _leadSpace(r)).contains('\t')) {
      return 'line ${n + 1}: a tab in the indentation';
    }
    final s = _rstrip(_stripComment(r));
    if (!_blank(s)) {
      final lead = _leadSpace(s);
      if (lead == 0 &&
          (s.startsWith('---') || s.startsWith('...')) &&
          (s.length == 3 || isPySpace(s.codeUnitAt(3)))) {
        if (marker || lines.isNotEmpty || s != '---') {
          return 'line ${n + 1}: a document marker the reader does not read (only `---` alone, first, at column 0)';
        }
        marker = true;
        continue;
      }
      final body = pyStrip(s);
      lines.add(_Line(lead, body, n));
      final m = _keyRe.firstMatch(body);
      final v = m?.group(2);
      if (v != null && v.isNotEmpty) {
        final t = pyStrip(v);
        if (t.isNotEmpty && (t[0] == '|' || t[0] == '>')) block = lead;
      }
    }
  }
  if (lines.isEmpty) return null;
  try {
    final i = _Strict(raw, lines).mapping(0, lines[0].indent, 0);
    if (i < lines.length) {
      _fail('line ${lines[i].row + 1}: unexpected indentation');
    }
  } on _YamlBad catch (e) {
    return e.why;
  }
  return null;
}

class _Strict {
  _Strict(this.raw, this.lines);
  final List<String> raw;
  final List<_Line> lines;

  Never bad(int i, String why) => _fail('line ${lines[i].row + 1}: $why');

  int mapping(int start, int indent, int depth) {
    var i = start;
    if (depth >= _maxDepth) {
      bad(i, 'mappings nested more than $_maxDepth deep');
    }
    final keys = <String>{};
    while (i < lines.length && lines[i].indent == indent) {
      final body = lines[i].body;
      final row = lines[i].row;
      if (body == '-' || body.startsWith('- ')) {
        bad(i, 'a block sequence (`- item`) is not read; write it as `[a, b]`');
      }
      final m = _keyRe.firstMatch(body);
      if (m == null) bad(i, 'not a `key: value` line');
      final k = m.group(1)!;
      final why = _valueProblem(k) ?? _keyTooLong(k);
      if (why != null) bad(i, why);
      final key = yamlUnquote(pyStrip(k));
      if (pyStrip(k) == '<<') {
        bad(i, 'a `<<` merge key (YAML merges it in, the reader does not)');
      }
      if (keys.contains(key)) bad(i, 'duplicate key `$key`');
      keys.add(key);
      final val = m.group(2);
      final t = val == null ? '' : pyStrip(val);
      if (t.isNotEmpty && (t[0] == '|' || t[0] == '>')) {
        if (!_blockHeader.hasMatch(t) || val!.runes.any(_isNd)) {
          bad(
            i,
            'a block scalar header the reader does not read (only |, >, with + or -)',
          );
        }
        final end = _blockScalar(raw, row + 1, indent, '|', '').$2;
        final bodyRows = [
          for (final r in raw.sublist(row + 1, end))
            if (!_blank(r)) r,
        ];
        if (bodyRows.isNotEmpty) {
          final pad = _leadSpaces(bodyRows.first);
          for (final r in raw.sublist(row + 1, end)) {
            if (!_blank(r)) break;
            if (r.length > pad) {
              bad(
                i,
                "a blank line before a block scalar's text with more spaces than the text",
              );
            }
          }
          if (bodyRows.any((r) => _leadSpaces(r) < pad)) {
            bad(i, "a block scalar line indented less than its first line");
          }
          if (t[0] == '>' &&
              bodyRows.any(
                (r) => _leadSpaces(r) > pad || r.codeUnitAt(pad) == 0x09,
              )) {
            bad(
              i,
              'a more-indented or tab-led line in a `>` block (YAML keeps its line breaks, the reader folds them)',
            );
          }
        }
        i++;
        while (i < lines.length && lines[i].row < end) {
          i++;
        }
      } else if (t.isEmpty) {
        i++;
        if (i < lines.length && lines[i].indent > indent) {
          i = mapping(i, lines[i].indent, depth + 1);
        }
      } else {
        final why = _valueProblem(val!);
        if (why != null) bad(i, why);
        i++;
      }
    }
    return i;
  }
}
