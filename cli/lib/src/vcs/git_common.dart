import 'scripts.dart';
import 'stop.dart';

/// Git helpers every backend of `vcs.sh` uses (Git reads on a jj or GitButler
/// repo too): `path_text`, `git_checked`, `remote_url`, `is_github_url`,
/// `network_git` and `git_ancestor`.

/// `vcs.sh`'s `path_text`: `\` becomes `/`.
String pathText(String path) => path.replaceAll(r'\', '/');

/// Python's `a or b` on two strings.
String orElse(String a, String b) => a.isNotEmpty ? a : b;

/// `vcs.sh`'s `git(repo, *args)`.
Future<TextResult> git(VcsScripts scripts, String repo, List<String> args) =>
    runText(scripts.bash, repo, ['git', ...args]);

/// `vcs.sh`'s `git_checked`: a non-zero exit is the stop [error] with git's
/// stderr (else stdout), or `git <args> failed`.
Future<TextResult> gitChecked(
  VcsScripts scripts,
  String repo,
  List<String> args, {
  String error = 'git_error',
}) async {
  final result = await git(scripts, repo, args);
  if (result.code != 0) {
    final said = orElse(result.stderr, result.stdout).trim();
    throw VcsStop(
      error,
      said.isNotEmpty ? said : 'git ${args.join(' ')} failed',
    );
  }
  return result;
}

/// `vcs.sh`'s `remote_url`: the remote's URL, or empty when it has none.
Future<String> remoteUrl(
  VcsScripts scripts,
  String repo, [
  String remote = 'origin',
]) async {
  final r = await git(scripts, repo, ['remote', 'get-url', remote]);
  return r.code == 0 ? r.stdout.trim() : '';
}

final _windowsDrive = RegExp(r'^[A-Za-z]:[\\/]');
final _scpHost = RegExp(r'^(?:[^@/]+@)?([^/:]+):');
final _schemeChars = RegExp(r'^[A-Za-z][A-Za-z0-9+.\-]*$');

/// `urlsplit(url).hostname`: the host of a URL with a scheme and `//`
/// authority, lower-cased; null when there is none.
String? _urlHostname(String url) {
  final colon = url.indexOf(':');
  if (colon <= 0 || !_schemeChars.hasMatch(url.substring(0, colon))) {
    return null;
  }
  final rest = url.substring(colon + 1);
  if (!rest.startsWith('//')) return null;
  var end = rest.length;
  for (final c in const ['/', '?', '#']) {
    final i = rest.indexOf(c, 2);
    if (i != -1 && i < end) end = i;
  }
  var netloc = rest.substring(2, end);
  final at = netloc.lastIndexOf('@');
  if (at != -1) netloc = netloc.substring(at + 1);
  String host;
  if (netloc.startsWith('[') && netloc.contains(']')) {
    host = netloc.substring(1, netloc.indexOf(']'));
  } else {
    final p = netloc.indexOf(':');
    host = p == -1 ? netloc : netloc.substring(0, p);
  }
  return host.isEmpty ? null : host.toLowerCase();
}

/// `vcs.sh`'s `is_github_url`.
bool isGithubUrl(String url) {
  if (_windowsDrive.hasMatch(url)) return false;
  final String? host;
  if (url.contains('://')) {
    host = _urlHostname(url);
  } else {
    host = _scpHost.firstMatch(url)?.group(1);
  }
  if (host == null) return false;
  var h = host.toLowerCase();
  while (h.endsWith('.')) {
    h = h.substring(0, h.length - 1);
  }
  return h == 'github.com' || h == 'ssh.github.com';
}

final _notFastForward = RegExp(
  r'not possible to fast-forward|divergent branches',
  caseSensitive: false,
);

/// `vcs.sh`'s `network_git`: runs `git <args>` in [repo], through the identity
/// fence in this process ([runAs]) when `origin` is on GitHub. A failure is the
/// `not_fast_forward` stop (a `pull` that cannot fast-forward, exit 1), else
/// `fence_failed` (a refused fence on GitHub) or `git_network_error`, exit 3.
///
/// Constraint C4: on Git and jj a fenced command's own exit 3 on a GitHub
/// remote is still reported as `fence_failed` (D2); this is a deliberate gap,
/// since a refusal and the command's own exit 3 cannot be told apart by status.
Future<TextResult> networkGit(
  VcsScripts scripts,
  String repo,
  List<String> args,
  String? login,
) async {
  final github = isGithubUrl(await remoteUrl(scripts, repo));
  final who = await fenceLogin(scripts, repo, github: github, login: login);
  final result = github
      ? await runAs(scripts, repo, who, ['git', ...args])
      : await git(scripts, repo, args);
  if (result.code != 0) {
    final said = orElse(result.stderr, result.stdout).trim();
    final message = said.isNotEmpty ? said : 'Git network operation failed';
    if (args[0] == 'pull' && _notFastForward.hasMatch(message)) {
      throw VcsStop('not_fast_forward', message);
    }
    throw VcsStop(
      github && result.code == 3 ? 'fence_failed' : 'git_network_error',
      message,
      code: 3,
    );
  }
  return result;
}

/// `vcs.sh`'s `git_ancestor`: `git merge-base --is-ancestor`; an exit other
/// than 0 or 1 is `git_error`.
Future<bool> gitAncestor(
  VcsScripts scripts,
  String repo,
  String ancestor,
  String descendant,
) async {
  final r = await git(scripts, repo, [
    'merge-base',
    '--is-ancestor',
    ancestor,
    descendant,
  ]);
  if (r.code != 0 && r.code != 1) {
    final said = orElse(r.stderr, r.stdout).trim();
    throw VcsStop(
      'git_error',
      said.isNotEmpty ? said : 'git merge-base --is-ancestor failed',
    );
  }
  return r.code == 0;
}
