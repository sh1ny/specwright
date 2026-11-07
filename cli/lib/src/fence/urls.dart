/// Constraint C8: `sw as` lower-cases a URL with ASCII folding only, A-Z to
/// a-z, as `tr 'A-Z' 'a-z'` did. A non-ASCII capital is not folded (Dart's
/// `toLowerCase` would fold it), so a lookalike host never becomes `github.com`.
String lowerAscii(String text) {
  final out = StringBuffer();
  for (final unit in text.codeUnits) {
    out.writeCharCode(unit >= 0x41 && unit <= 0x5a ? unit + 0x20 : unit);
  }
  return out.toString();
}

/// bash's command substitution drops every trailing newline.
String _dropNewlines(String text) {
  var end = text.length;
  while (end > 0 && text.codeUnitAt(end - 1) == 0x0a) {
    end--;
  }
  return text.substring(0, end);
}

// The three patterns of as.sh, over the decoded text: a byte that is not UTF-8
// is a lone surrogate there, so it cannot match a pattern character. `.` and
// `[^/]` cross a newline, as in bash's `[[ =~ ]]`.
final RegExp _githubUrl = RegExp(
  r'^[a-z][a-z0-9+.-]*://([^/]*@)?github\.com\.?([:/]|$)',
  dotAll: true,
);
final RegExp _githubUserinfo = RegExp(
  r'^[a-z][a-z0-9+.-]*://[^/]*@github\.com\.?([:/]|$)',
  dotAll: true,
);
final RegExp _anyUserinfo = RegExp(
  r'^[A-Za-z][A-Za-z0-9+.-]*://[^/]*@',
  dotAll: true,
);
final RegExp _maskScheme = RegExp(r'^([A-Za-z][A-Za-z0-9+.-]*://)[^/]*@');

/// `gh_url`: a github.com URL, with or without userinfo.
bool ghUrl(String text) => _githubUrl.hasMatch(_dropNewlines(lowerAscii(text)));

/// `gh_userinfo`: a github.com URL that carries userinfo.
bool ghUserinfo(String text) =>
    _githubUserinfo.hasMatch(_dropNewlines(lowerAscii(text)));

/// `has_userinfo`: a URL of any host that carries userinfo.
bool hasUserinfo(String text) => _anyUserinfo.hasMatch(text);

/// `mask`: the URL with its userinfo replaced by `***`, the scheme kept. `sed`
/// works line by line, so each line is masked on its own.
String mask(String text) => _dropNewlines(
  text
      .split('\n')
      .map((line) => line.replaceFirstMapped(_maskScheme, (m) => '${m[1]}***@'))
      .join('\n'),
);
