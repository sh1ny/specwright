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

const defaultGitHubHost = 'github.com';

String canonicalHost(String host) {
  final lower = lowerAscii(host);
  return lower.endsWith('.') ? lower.substring(0, lower.length - 1) : lower;
}

String githubTokenVariable(String host) =>
    host == defaultGitHubHost ||
        host == 'github.localhost' ||
        host.endsWith('.github.localhost') ||
        host.endsWith('.ghe.com')
    ? 'GH_TOKEN'
    : 'GH_ENTERPRISE_TOKEN';

final _urlHost = RegExp(
  r'^[a-zA-Z][a-zA-Z0-9+.-]*://(?:[^/]*@)?(\[[^\]]+\]|[^:/?#@\s]+)(?=[:/?#]|$)',
);
final _scpHost = RegExp(r'^(?:[^@/:\s]+@)?([^/\\:@\s]+):[^\r\n]+$');

/// Host from Git URL or scp syntax, not a local path or opaque helper syntax.
String? gitUrlHost(String text) {
  final url = _urlHost.firstMatch(text);
  if (url != null) return canonicalHost(url[1]!);
  if (text.contains('://') || text.contains('::')) return null;
  final scp = _scpHost.firstMatch(text);
  if (scp == null || scp[1]!.length == 1) return null;
  return canonicalHost(scp[1]!);
}

bool githubHostMatches(String? actual, String configured) =>
    actual == configured ||
    (configured == defaultGitHubHost && actual == 'ssh.github.com');

final RegExp _anyUserinfo = RegExp(
  r'^[A-Za-z][A-Za-z0-9+.-]*://[^/]*@',
  dotAll: true,
);
final RegExp _maskScheme = RegExp(r'^([A-Za-z][A-Za-z0-9+.-]*://)[^/]*@');

/// Whether a Git URL addresses this GitHub host, regardless of transport.
bool ghUrl(String text, {String host = defaultGitHubHost}) =>
    githubHostMatches(gitUrlHost(_dropNewlines(text)), host);

/// URL-form userinfo addressing this GitHub host, including a bare username.
bool ghUserinfo(String text, {String host = defaultGitHubHost}) =>
    hasUserinfo(text) && ghUrl(text, host: host);

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
