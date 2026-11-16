import 'package:yaml/yaml.dart' as y;

import 'values.dart' show YamlMap, pyIntNormal;

// The settings reader of `native-cli-yaml-settings` (design D1-D3, ADR 0038): `package:yaml` loads the text and this
// file applies every refusal. Nothing else in `cli/` imports `package:yaml`.

/// A settings file the reader refuses: the 1-based [line] it found and [why].
class SettingsRefused implements Exception {
  const SettingsRefused(this.line, this.why);

  final int line;
  final String why;

  @override
  String toString() => 'line $line: $why';
}

/// The most flow collections (`[` and `{`) that may be open at once.
const int _maxFlowDepth = 64;

/// Reads the text of `openspec/specwright.yaml` as one YAML mapping, or throws [SettingsRefused] naming the line and
/// why. The text is expected with `\n` newlines.
///
/// A mapping is a [YamlMap] that keeps each plain scalar's text as written (`settingText` reads it), a sequence is a
/// `List<Object?>`, and a scalar is a `String`, `int`, [BigInt], `double`, `bool` or null. An empty, blank or
/// comment-only document is an empty mapping; any other top level that is not a mapping is refused. Also refused: a
/// second document, a key that is not text, a duplicate key, an anchor, an alias or a tag, a plain `yes` or `no` in
/// any letter case as a value (write `true` or `false`, or quote it), and flow collections nested more than 64 deep.
///
/// Constraint C3: the flow-depth cap is 64 and the reader catches a stack overflow from the package as a refused
/// file; removing either needs the package to load without recursion first. The cap is checked by a scan before the
/// package runs, because the package overflows its stack on deep nesting and cannot name a line when it does.
///
/// Constraint C4: a plain decimal integer is read from its text, not from the package's value, so a 65-bit value is
/// never rounded to a `double`.
///
/// Constraint C5: a walk of the package's private parser events (`package:yaml/src`) with an iterative builder was
/// rejected (design D2), because private API can change in any upgrade.
YamlMap readSettingsYaml(String text) {
  final deep = _flowTooDeep(text);
  if (deep != null) {
    throw SettingsRefused(
      deep,
      'flow collections are nested more than $_maxFlowDepth deep',
    );
  }
  try {
    return _root(y.loadYamlNode(text), text);
  } on y.YamlException catch (e) {
    throw SettingsRefused((e.span?.start.line ?? 0) + 1, e.message);
  } on StackOverflowError {
    throw const SettingsRefused(1, 'nested too deeply');
  }
}

// ---- the walk over the package's nodes ----------------------------------------------------------------------------

final RegExp _decimalInt = RegExp(r'^[+-]?[0-9]+$');
final RegExp _yesNo = RegExp(r'^(yes|no)$', caseSensitive: false);

int _lineOf(y.YamlNode n) => n.span.start.line + 1;

YamlMap _root(y.YamlNode node, String text) {
  // The package loads an empty document as a null scalar whose span holds only whitespace and comments; an explicit
  // `null` or `~` has its text in the span and is refused with the other scalars.
  if (node is y.YamlScalar &&
      node.value == null &&
      node.span.text.replaceAll(RegExp(r'#[^\n]*'), '').trim().isEmpty) {
    return YamlMap();
  }
  final seen = Set<Object>.identity();
  _check(node, text, seen);
  if (node is! y.YamlMap) {
    throw SettingsRefused(_lineOf(node), 'the top level must be a mapping');
  }
  return _map(node, text, seen);
}

/// Refuses an anchor or a tag (the node's span starts with `&` or `!`) and an alias (the package returns the anchored
/// node itself, so it is met a second time).
void _check(y.YamlNode node, String text, Set<Object> seen) {
  final at = node.span.start.offset;
  final c = at < text.length ? text.codeUnitAt(at) : 0;
  if (c == 0x26 || c == 0x21) {
    throw SettingsRefused(
      _lineOf(node),
      'anchors, aliases and tags are not read',
    );
  }
  if (!seen.add(node)) {
    throw SettingsRefused(_lineOf(node), 'aliases are not read');
  }
}

YamlMap _map(y.YamlMap node, String text, Set<Object> seen) {
  final out = YamlMap();
  for (final e in node.nodes.entries) {
    final k = e.key as y.YamlNode;
    _check(k, text, seen);
    if (k is! y.YamlScalar || k.value is! String) {
      throw SettingsRefused(_lineOf(k), 'a mapping key must be text');
    }
    final key = k.value as String;
    final v = e.value;
    out[key] = _node(v, text, seen);
    // The text as written, for messages (`settingText`): plain and quoted scalars (quotes kept, so `''` shows as
    // `''`) and flow collections, as the old reader kept them; block scalars and block collections keep none.
    if ((v is y.YamlScalar &&
            (v.style == y.ScalarStyle.PLAIN ||
                v.style == y.ScalarStyle.SINGLE_QUOTED ||
                v.style == y.ScalarStyle.DOUBLE_QUOTED)) ||
        (v is y.YamlMap && v.style == y.CollectionStyle.FLOW) ||
        (v is y.YamlList && v.style == y.CollectionStyle.FLOW)) {
      final t = v.span.text.trim();
      if (t.isNotEmpty) out.text[key] = t;
    }
  }
  return out;
}

Object? _node(y.YamlNode n, String text, Set<Object> seen) {
  _check(n, text, seen);
  if (n is y.YamlMap) return _map(n, text, seen);
  if (n is y.YamlList) return [for (final e in n.nodes) _node(e, text, seen)];
  return _scalar(n as y.YamlScalar);
}

Object? _scalar(y.YamlScalar n) {
  final v = n.value;
  if (n.style != y.ScalarStyle.PLAIN) return v;
  if (v is String) {
    if (_yesNo.hasMatch(v)) {
      throw SettingsRefused(
        _lineOf(n),
        '`$v` is a boolean in some YAML readers and text in others; write true or false (or quote it to keep the text)',
      );
    }
    return v;
  }
  if (v is int || v is double) {
    final src = n.span.text.trim();
    if (_decimalInt.hasMatch(src)) return pyIntNormal(BigInt.parse(src));
  }
  // D8: a NaN or infinity cannot reach a JSON document (`documentText` refuses it), and no setting needs one.
  if (v is double && !v.isFinite) {
    throw SettingsRefused(
      _lineOf(n),
      '`${n.span.text.trim()}` is not a finite number',
    );
  }
  return v;
}

// ---- the flow-depth scan ------------------------------------------------------------------------------------------

/// The 1-based line where more than [_maxFlowDepth] flow collections are open, or null.
///
/// A `[` or `{` opens a collection only where one can start: at the start of a block value (after `key:`, after `- `,
/// as the first character of a line's content) or anywhere inside an open collection, where YAML forbids those
/// characters in plain scalars. Nothing is counted inside quoted scalars, comments, the body of a `|` or `>` block
/// scalar, or plain scalar text in block context.
int? _flowTooDeep(String text) {
  final scan = _FlowScan();
  // YAML breaks lines at CRLF, CR and LF alike; so does the scan, or a CR-only file would hide its nesting.
  final lines = text.split(_lineBreak);
  for (var n = 0; n < lines.length; n++) {
    final line = n == 0 && lines[0].startsWith('﻿')
        ? lines[0].substring(1)
        : lines[n];
    if (scan.line(line)) return n + 1;
  }
  return null;
}

final RegExp _lineBreak = RegExp('\r\n|\r|\n');

final RegExp _blockHeader = RegExp(r'^[|>][+\-0-9]*[ \t\r]*(#.*)?$');

bool _ws(String c) => c == ' ' || c == '\t' || c == '\r';

class _FlowScan {
  int depth = 0;

  /// The quote character of a quoted scalar that is still open.
  String? quote;

  /// While inside a `|` or `>` body: the indentation of the line that holds its header; body lines are blank or
  /// indented deeper.
  int? blockIndent;

  /// The last token on this line in block context is a plain scalar, which may go on over the next lines.
  bool plain = false;

  /// After a line that ends inside a block-context plain scalar: the indentation of that line. Lines indented deeper
  /// continue the scalar's text, so nothing on them opens a collection; blank lines keep it open.
  int? plainIndent;

  /// A node (a quoted scalar, a flow collection or a block scalar) may start at the next character.
  bool start = false;

  /// The last token was a quoted scalar or a closed flow collection, so an adjacent `:` is a value indicator.
  bool adjacent = false;

  /// Index after the closing quote of the open quoted scalar, scanning from [from], or the line's end when it stays
  /// open on the next line.
  int _endQuote(String s, int from) {
    final q = quote!;
    var i = from;
    while (i < s.length) {
      final c = s[i];
      if (q == '"' && c == r'\') {
        i += 2;
        continue;
      }
      if (c == q) {
        if (q == "'" && i + 1 < s.length && s[i + 1] == "'") {
          i += 2;
          continue;
        }
        quote = null;
        return i + 1;
      }
      i++;
    }
    return s.length;
  }

  /// Scans one line; true when it opens the collection that makes the depth exceed the cap.
  bool line(String s) {
    var i = 0;
    var lineIndent = 0;
    if (quote != null) {
      i = _endQuote(s, 0);
      if (quote != null) return false;
      start = false;
      adjacent = true;
    } else if (depth == 0) {
      while (i < s.length && s[i] == ' ') {
        i++;
      }
      if (blockIndent != null) {
        if (i >= s.length ||
            s.substring(i).trim().isEmpty ||
            i > blockIndent!) {
          return false;
        }
        blockIndent = null;
      }
      if (plainIndent != null) {
        if (i >= s.length ||
            s.substring(i).trim().isEmpty ||
            i > plainIndent!) {
          return false;
        }
        plainIndent = null;
      }
      lineIndent = i;
      if (s.startsWith('---') && (s.length == 3 || _ws(s[3]))) i = 3;
      while (i < s.length && _ws(s[i])) {
        i++;
      }
      while (i < s.length &&
          s[i] == '-' &&
          (i + 1 == s.length || _ws(s[i + 1]))) {
        i++;
        while (i < s.length && _ws(s[i])) {
          i++;
        }
      }
      start = true;
      adjacent = false;
      plain = false;
    }
    while (i < s.length) {
      final c = s[i];
      if (_ws(c)) {
        i++;
        continue;
      }
      if (c == '#' && (i == 0 || _ws(s[i - 1]))) {
        plain = false;
        return false;
      }
      if (depth > 0) {
        final next = i + 1 < s.length ? s[i + 1] : '';
        switch (c) {
          case '[' || '{':
            depth++;
            if (depth > _maxFlowDepth) return true;
            start = true;
            adjacent = false;
          case ']' || '}':
            depth--;
            start = false;
            adjacent = true;
          case ',':
            start = true;
            adjacent = false;
          case '"' || "'":
            if (start) {
              quote = c;
              i = _endQuote(s, i + 1);
              if (quote != null) return false;
              start = false;
              adjacent = true;
              continue;
            }
            adjacent = false;
          case ':':
            start =
                adjacent || next.isEmpty || _ws(next) || ',[]{}'.contains(next);
            adjacent = false;
          default:
            start = false;
            adjacent = false;
        }
        i++;
        continue;
      }
      // Block context.
      if (start) {
        switch (c) {
          case '[' || '{':
            depth++;
            adjacent = false;
            i++;
            continue;
          case '"' || "'":
            quote = c;
            i = _endQuote(s, i + 1);
            if (quote != null) return false;
            start = false;
            adjacent = true;
            continue;
          case '|' || '>':
            if (_blockHeader.hasMatch(s.substring(i))) {
              blockIndent = lineIndent;
              return false;
            }
            start = false;
          case '&' || '!':
            while (i < s.length && !_ws(s[i])) {
              i++;
            }
            continue;
          default:
            start = false;
        }
      }
      if (c == ':' && (i + 1 == s.length || _ws(s[i + 1]))) {
        start = true;
        adjacent = false;
        plain = false;
      } else {
        plain = true;
      }
      i++;
    }
    if (depth == 0 && quote == null && plain) plainIndent = lineIndent;
    return false;
  }
}
