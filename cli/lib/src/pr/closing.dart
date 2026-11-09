import 'package:html/dom.dart';
import 'package:html/parser.dart' show parseFragment;

const _blocks = {
  'p',
  'pre',
  'ul',
  'ol',
  'li',
  'h1',
  'h2',
  'h3',
  'h4',
  'h5',
  'h6',
  'blockquote',
  'div',
  'table',
  'tr',
  'td',
  'th',
  'dl',
  'dt',
  'dd',
  'details',
  'summary',
  'hr',
  'br',
};
const _code = {'pre', 'code'};

/// C12: HTML parsing and entity decoding belong to package:html's public
/// parser. This adapter only extracts closing prose and code/block boundaries.
/// It authors no tokenizer or entity table. DOM traversal is iterative.
/// Owner-approved difference: HTML5 foster parenting reads the malformed
/// `Fixes <table>#1</table>` as `Fixes #1`. The focused test named 'raw table
/// follows standard HTML5 interpretation' records that product decision.
List<String> renderedLines(String html) {
  final root = parseFragment(html);
  final lines = <String>[''];
  void newline() {
    if (lines.last.isNotEmpty) lines.add('');
  }

  final stack = <({Node node, bool end})>[(node: root, end: false)];
  while (stack.isNotEmpty) {
    final entry = stack.removeLast(), node = entry.node;
    if (node is Text) {
      final parts = node.data.split('\n');
      lines[lines.length - 1] += parts.first;
      for (final part in parts.skip(1)) {
        newline();
        lines[lines.length - 1] += part;
      }
      continue;
    }
    if (node is Comment) continue;
    final tag = node is Element ? node.localName : null;
    if (tag != null && _blocks.contains(tag)) newline();
    if (entry.end) continue;
    if (tag != null && _code.contains(tag)) {
      lines[lines.length - 1] += '\ufffc';
      newlineIfBlock(tag, newline);
      continue;
    }
    stack.add((node: node, end: true));
    for (final child in node.nodes.reversed) {
      stack.add((node: child, end: false));
    }
  }
  return lines;
}

void newlineIfBlock(String tag, void Function() newline) {
  if (_blocks.contains(tag)) newline();
}

const _keyword =
    r'(?<![\p{L}\p{N}_])(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)(?![\p{L}\p{N}_]):?';
final _keywords = RegExp(_keyword, caseSensitive: false, unicode: true);
final _lead = RegExp(
  r'^(?:[\s>*+\-]|\d{1,9}[.)](?=\s))*' + _keyword,
  caseSensitive: false,
  unicode: true,
);
final _gaps = RegExp(
  r'^(?:[\s,;]|\band\b|' + _keyword + r')*$',
  caseSensitive: false,
  unicode: true,
);
final _refs = RegExp(
  r'https?://github\.com/([\w.-]+/[\w.-]+)/issues/(\d+)\b|(?<![\w/.-])([\w.-]+/[\w.-]+)#(\d+)\b|(?<![\w/&])#(\d+)\b',
);

List<String> intendedReferences(String html, String repo) {
  final found = <String>[];
  String key(RegExpMatch m) => m[1] != null
      ? '${m[1]}#${BigInt.parse(m[2]!)}'
      : m[3] != null
      ? '${m[3]}#${BigInt.parse(m[4]!)}'
      : '$repo#${BigInt.parse(m[5]!)}';
  for (final line in renderedLines(html)) {
    final refs = _refs.allMatches(line).toList();
    final lead = _lead.firstMatch(line);
    if (lead != null) {
      var previous = lead.end, first = true;
      for (final ref in refs) {
        if (ref.start < lead.end) continue;
        final gap = line.substring(previous, ref.start);
        if (first ? gap.trim().isNotEmpty : !_gaps.hasMatch(gap)) break;
        found.add(key(ref));
        previous = ref.end;
        first = false;
      }
    }
    for (final kw in _keywords.allMatches(line)) {
      for (final ref in refs) {
        if (ref.start >= kw.end &&
            line.substring(kw.end, ref.start).trim().isEmpty) {
          found.add(key(ref));
          break;
        }
      }
    }
  }
  final seen = <String>{};
  return found.where((k) => seen.add(k.toLowerCase())).toList();
}
