// The text tools `pr-snapshot.sh` pipes its output through (`grep -o`, `sed -n`, `paste`, `tr`, `head`, `tail -n 80`) as
// Dart functions with the same results on the same input (design D7). Every pattern is ASCII.

/// bash's command substitution `$(...)`: the output without its trailing newlines.
String dropTrailingNewlines(String text) {
  var end = text.length;
  while (end > 0 && text.codeUnitAt(end - 1) == 0x0a) {
    end--;
  }
  return text.substring(0, end);
}

/// `grep -o <pattern>`: every non-empty match of [pattern], one per output line, line by line.
List<String> grepOnly(RegExp pattern, String text) => [
  for (final line in text.split('\n'))
    for (final m in pattern.allMatches(line))
      if (m.end > m.start) m[0]!,
];

/// `grep -Eq <pattern>`: does any line of [text] match?
bool grepQuiet(RegExp pattern, String text) =>
    text.split('\n').any(pattern.hasMatch);

/// `tr -d '\r'`.
String removeCr(String text) => text.replaceAll('\r', '');

/// `printf '%s' "$1" | grep -o '"head_oid":"[0-9a-f]*"' | sed -n '1s/.*:"\(.*\)"/\1/p'`: the first head oid, or '' when
/// there is none.
String headOidOf(String snapshot) {
  final found = grepOnly(RegExp(r'"head_oid":"[0-9a-f]*"'), snapshot);
  if (found.isEmpty) return '';
  final m = RegExp(r'^.*:"(.*)"$').firstMatch(found.first);
  return m == null ? found.first : m[1]!;
}

/// `sed -n 's/.*"logins":\[\([^]]*\)\].*/\1/p'`: the body of the last `"logins":[...]` of each line that has one.
String loginsOf(String check) => dropTrailingNewlines(
  [
    for (final line in check.split('\n'))
      if (RegExp(r'^.*"logins":\[([^\]]*)\].*$').firstMatch(line) case final m?)
        m[1]!,
  ].join('\n'),
);

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

/// The reaction re-check's batches, `snapshot()`'s pipeline: the ids of the `"recheck":[...]` list, 25 to a line, four
/// lines to a batch, so 100 ids at most to a query. A batch is the quoted ids joined by `,`.
List<String> recheckBatches(String snapshot) {
  final ids = [
    for (final list in grepOnly(RegExp(r'"recheck":\[[^\]]*\]'), snapshot))
      ...grepOnly(
        RegExp(r'"[A-Za-z0-9_=-]+"'),
        list.replaceFirst(RegExp(r'^"recheck":'), ''),
      ),
  ];
  return [
    for (final row in paste(paste(ids, 25), 4))
      if (stripTrailingCommas(row).isNotEmpty) stripTrailingCommas(row),
  ];
}

/// `grep -o '"<key>":"[^"]*"'` on a snapshot, as `sig_of` and `attn_of` print it (matches joined by newlines).
String memberOf(String snapshot, String key) => dropTrailingNewlines(
  grepOnly(RegExp('"$key":"[^"]*"'), snapshot).join('\n'),
);

/// `fails_of`: the failing check names (base64), one quoted string per line.
List<String> failNamesOf(String snapshot) => [
  for (final list in grepOnly(RegExp(r'"fail_names":\[[^\]]*\]'), snapshot))
    ...grepOnly(RegExp(r'"[A-Za-z0-9+/=]+"'), list),
];

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

/// The numbers of `grep -o '"fail_run_ids":\[[0-9,]*\]' | grep -o '[0-9][0-9]*'`.
List<String> failRunIdsOf(String snapshot) => [
  for (final list in grepOnly(RegExp(r'"fail_run_ids":\[[0-9,]*\]'), snapshot))
    ...grepOnly(RegExp(r'[0-9]+'), list),
];

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
