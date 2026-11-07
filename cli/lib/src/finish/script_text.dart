// Text for the scripts `sw finish` prints.

final RegExp _safe = RegExp(r'^[A-Za-z0-9_@%+=:,./-]+$');

/// `shellQuote` and `jjString` produce exactly `shlex.quote`'s and `dq`'s text.
/// The printed scripts are run by users, so a quoting change is a safety
/// change.
///
/// `''` for an empty string; the text unchanged when every character is in
/// `[A-Za-z0-9_@%+=:,./-]` (ASCII only: non-ASCII text is quoted); otherwise
/// the text in single quotes with each `'` written as `'"'"'`.
String shellQuote(String text) {
  if (text.isEmpty) return "''";
  if (_safe.hasMatch(text)) return text;
  return "'${text.replaceAll("'", "'\"'\"'")}'";
}

/// A jj string literal (fileset `root:"<path>"` and revset `"<name>"`): `"`
/// around the text, with `\` and `"` escaped by a backslash (`dq` in
/// finish.sh).
String jjString(String text) =>
    '"${text.replaceAll(r'\', r'\\').replaceAll('"', r'\"')}"';
