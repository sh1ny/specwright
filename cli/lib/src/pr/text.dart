/// The text tools `pr-snapshot.sh` pipes its output through (`grep -q`, `paste`, `tr`, `head`, `tail -n 80`) as Dart
/// functions with the same results on the same input (design D7). Every pattern is ASCII. The documents `sw pr snapshot`
/// reads are not read here: it parses them (native-cli-internal-calls D4, C12).
library;

/// bash's command substitution `$(...)`: the output without its trailing newlines.
String dropTrailingNewlines(String text) {
  var end = text.length;
  while (end > 0 && text.codeUnitAt(end - 1) == 0x0a) {
    end--;
  }
  return text.substring(0, end);
}

/// `grep -Eq <pattern>`: does any line of [text] match?
bool grepQuiet(RegExp pattern, String text) =>
    text.split('\n').any(pattern.hasMatch);

/// `tr -d '\r'`.
String removeCr(String text) => text.replaceAll('\r', '');

/// `paste -d, - - ...` with [columns] dashes: [columns] lines joined by `,` per row; the last row is padded with empty
/// fields, as paste does.
List<String> paste(List<String> lines, int columns) => [
  for (var i = 0; i < lines.length; i += columns)
    [for (var j = i; j < i + columns; j++) j < lines.length ? lines[j] : '']
        .join(','),
];

/// `sed 's/,*$//'`.
String stripTrailingCommas(String line) =>
    line.replaceFirst(RegExp(r',*$'), '');

/// The reaction re-check's batches, `snapshot()`'s pipeline: [ids] quoted, 25 to a line, four lines to a batch, so 100
/// ids at most to a query. A batch is the quoted ids joined by `,`. Each id must be one that needs no escaping in a query
/// text (the caller keeps only node ids).
List<String> recheckBatches(Iterable<String> ids) {
  final quoted = [for (final id in ids) '"$id"'];
  return [
    for (final row in paste(paste(quoted, 25), 4))
      if (stripTrailingCommas(row).isNotEmpty) stripTrailingCommas(row),
  ];
}

/// `tr -d '\r' | sed -n 's/^[Dd]ate: //p' | head -n 1`: the value of the first `Date:` header line.
String dateHeaderOf(String headers) {
  for (final line in removeCr(headers).split('\n')) {
    if (RegExp(r'^[Dd]ate: ').hasMatch(line)) {
      return line.replaceFirst(RegExp(r'^[Dd]ate: '), '');
    }
  }
  return '';
}

/// `head -n 1 | tr -d '\r'`: the first line of [text].
String firstLine(String text) {
  final end = text.indexOf('\n');
  return removeCr(end < 0 ? text : text.substring(0, end));
}

/// `tail -n [n]` on bytes: the last [n] lines, the final newline kept as it is.
List<int> tailLines(List<int> bytes, int n) {
  var i = bytes.length;
  if (i > 0 && bytes[i - 1] == 0x0a) i--;
  var seen = 0;
  while (i > 0) {
    i--;
    if (bytes[i] == 0x0a && ++seen == n) return bytes.sublist(i + 1);
  }
  return bytes;
}
