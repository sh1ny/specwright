import 'dart:io';
import 'dart:typed_data';

import '../pr/gh.dart';
import '../vcs/codec.dart';
import '../vcs/tool_runner.dart';
import 'urls.dart';

/// A refusal or a stop of the fence: [message] is the whole line for stderr
/// (it starts with `as.sh: `), [code] the exit status (3 unless said).
class FenceStop implements Exception {
  FenceStop(this.message, [this.code = 3]);

  final String message;
  final int code;

  @override
  String toString() => message;
}

/// One `gh` call of the fence, with the whole environment it gets.
typedef GhCall = Future<GhResult> Function(
  List<String> args,
  Map<String, String> env,
);

/// One read of the fence's own `git` (never bounded, C13), with the whole
/// environment it gets.
typedef GitCall = Future<ToolResult> Function(
  List<String> command,
  Map<String, String> env,
);

/// Runs the fenced command with the final environment; its exit status.
typedef Launch = Future<int> Function(
  List<String> command,
  Map<String, String> env,
);

const String usageLine =
    'as.sh: line 47: 1: usage: as.sh <login> <command> [args...] | as.sh --resolve';

const _tokenVariables = [
  'GH_TOKEN',
  'GITHUB_TOKEN',
  'GH_HOST',
  'GH_ENTERPRISE_TOKEN',
  'GITHUB_ENTERPRISE_TOKEN',
];

const _savedVariables = [
  'GH_HOST',
  'GH_ENTERPRISE_TOKEN',
  'GITHUB_ENTERPRISE_TOKEN',
  'GIT_SSH_COMMAND',
  'GIT_TERMINAL_PROMPT',
  'GCM_INTERACTIVE',
  'GIT_ASKPASS',
  'SSH_ASKPASS',
  'GIT_CONFIG_COUNT',
];

final RegExp _gitConfigName = RegExp(r'^GIT_CONFIG_(KEY|VALUE)_[0-9]+$');

const String _sshCommand =
    'sh -c "echo as.sh: SSH is disabled - push over https://github.com so the identity can be pinned >&2; exit 1"';

const String _credentialHelper =
    r'''!f() { [ "$1" = get ] || exit 0; h= p=; while IFS= read -r l && [ -n "$l" ]; do case $l in host=*) h=${l#host=} ;; protocol=*) p=${l#protocol=} ;; esac; done; h=$(printf %s "$h" | tr A-Z a-z); h=${h%:*}; h=${h%.}; [ "$h" = github.com ] && [ "$p" = https ] || exit 0; echo username=x-access-token; echo "password=$GH_TOKEN"; }; f''';

/// The key of [name] in [env]: on Windows names are compared without case.
String? _keyOf(Map<String, String> env, String name, bool windows) {
  if (env.containsKey(name)) return name;
  if (!windows) return null;
  final lower = name.toLowerCase();
  for (final key in env.keys) {
    if (key.toLowerCase() == lower) return key;
  }
  return null;
}

int _compareBytes(Uint8List a, Uint8List b) {
  final n = a.length < b.length ? a.length : b.length;
  for (var i = 0; i < n; i++) {
    if (a[i] != b[i]) return a[i] - b[i];
  }
  return a.length - b.length;
}

/// The lines `while IFS= read -r line` sees in [output]: split on newline, and
/// a last line with no newline is dropped, as `read` fails on it.
List<Uint8List> _readLines(List<int> output) {
  final bytes = Uint8List.fromList(output);
  final lines = <Uint8List>[];
  var start = 0;
  for (var i = 0; i < bytes.length; i++) {
    if (bytes[i] == 0x0a) {
      lines.add(Uint8List.sublistView(bytes, start, i));
      start = i + 1;
    }
  }
  return lines;
}

List<String> _lines(List<int> output) => [
  for (final line in _readLines(output)) decodeEscaped(line),
];

/// The caller's values of what the fence overrides, saved once: `sw as` started
/// inside another keeps the outer originals. Only variables that were set are
/// saved, as `AS_SH_ORIG_<name>` with `AS_SH_ORIG_SET` listing them, each with
/// a space in front. `GH_TOKEN` and `GITHUB_TOKEN` are never saved. Returns a
/// new map; [env] itself is not changed.
Map<String, String> saveOriginals(Map<String, String> env, {bool? windows}) {
  final win = windows ?? Platform.isWindows;
  final out = {...env};
  if (_keyOf(env, 'AS_SH_ORIG_SET', win) != null) return out;
  final configNames = [
    for (final key in env.keys)
      if (_gitConfigName.hasMatch(key)) key,
  ]..sort((a, b) => _compareBytes(encodeEscaped(a), encodeEscaped(b)));
  var listed = '';
  for (final name in [..._savedVariables, ...configNames]) {
    final key = _keyOf(env, name, win);
    if (key == null) continue;
    out['AS_SH_ORIG_$name'] = env[key]!;
    listed = '$listed $name';
  }
  out['AS_SH_ORIG_SET'] = listed;
  return out;
}

/// What discovery runs with: [env] without the gh token and host variables
/// (an empty `GH_HOST` counts as set, so it goes too).
Map<String, String> discoveryEnvironment(
  Map<String, String> env, {
  bool? windows,
}) {
  final win = windows ?? Platform.isWindows;
  final out = {...env};
  for (final name in _tokenVariables) {
    final key = _keyOf(out, name, win);
    if (key != null) out.remove(key);
  }
  return out;
}

/// `limit_stop`: a lookup that ended in 124 (deadline), 125 (too large) or 126
/// (argument transport) stops the fence with exit 3 naming the lookup, before
/// the message for "no credential". The status alone decides, as in `as.sh`.
void _limitStop(GhResult r, String command) {
  final what = switch (r.exitCode) {
    124 => 'deadline_exceeded',
    125 => 'response_too_large',
    126 => 'argument transport failed',
    _ => null,
  };
  if (what != null) throw FenceStop('as.sh: $what: $command');
}

String _stripNewlines(String text) {
  var end = text.length;
  while (end > 0 && text.codeUnitAt(end - 1) == 0x0a) {
    end--;
  }
  return text.substring(0, end);
}

/// `gh auth token --help` must name `--user`: without it the only per-account
/// lookup is a shared `gh auth switch`, which other agents race on, so the
/// fence refuses rather than fall back.
Future<void> checkGhVersion(GhCall gh, Map<String, String> env) async {
  final help = await gh(['auth', 'token', '--help'], env);
  _limitStop(help, 'gh auth token --help');
  final text = decodeEscaped([...help.stdout, ...help.stderr]);
  if (text.contains('--user')) return;
  // `$(gh --version | head -n 1 || echo 'gh not found')` under pipefail: a gh
  // that fails adds the second line after whatever it printed.
  final version = await gh(['--version'], env);
  var first = _firstLine(version.stdout);
  if (version.exitCode != 0) {
    first = first.isEmpty ? 'gh not found' : '$first\ngh not found';
  }
  throw FenceStop(
    'as.sh: ${_stripNewlines(first)} cannot look up a token per account '
    '(gh auth token --user, gh 2.48+); upgrade gh',
  );
}

String _firstLine(List<int> output) {
  final bytes = Uint8List.fromList(output);
  final end = bytes.indexOf(0x0a);
  return decodeEscaped(end < 0 ? bytes : Uint8List.sublistView(bytes, 0, end));
}

/// `--resolve`: the active github.com account, once, when gh holds its token.
/// Both lookups run with no token in [env]: the active account is what is asked
/// (C10).
Future<String> resolveLogin(GhCall gh, Map<String, String> env) async {
  final r = await gh([
    'api',
    '--hostname',
    'github.com',
    'user',
    '--jq',
    '.login',
  ], env);
  _limitStop(r, 'gh api user');
  final login = r.exitCode == 0 ? _stripNewlines(decodeEscaped(r.stdout)) : '';
  const how =
      "run 'gh auth login' or set github.login in openspec/specwright.yaml "
      '(GH_TOKEN and GITHUB_TOKEN are not used to pick the login)';
  if (login.isEmpty) {
    throw FenceStop('as.sh: no active gh account for github.com; $how');
  }
  final token = await gh([
    'auth',
    'token',
    '--hostname',
    'github.com',
    '--user',
    login,
  ], env);
  _limitStop(token, 'gh auth token --user $login');
  if (token.exitCode != 0) {
    throw FenceStop(
      "as.sh: no gh credential for the active account '$login'; $how",
    );
  }
  return login;
}

/// Constraint C10: identity verification, `gh api user`, runs with `GH_TOKEN`
/// set to the token just read for [login], so it checks that token and not the
/// active account. The read itself, like every discovery call, runs with no
/// token in [env]. A configured account that is not the active one passes, and
/// a token that belongs to another login is refused. Returns the environment
/// with `GH_TOKEN` set, which the fenced command gets too.
Future<Map<String, String>> verifyIdentity(
  String login,
  GhCall gh,
  Map<String, String> env,
) async {
  final read = await gh([
    'auth',
    'token',
    '--hostname',
    'github.com',
    '--user',
    login,
  ], env);
  _limitStop(read, 'gh auth token --user $login');
  final token = read.exitCode == 0
      ? _stripNewlines(decodeEscaped(read.stdout))
      : '';
  if (token.isEmpty) {
    throw FenceStop("as.sh: no gh credential for '$login' (gh auth login)");
  }
  final withToken = {...env, 'GH_TOKEN': token};
  final who = await gh([
    'api',
    '--hostname',
    'github.com',
    'user',
    '--jq',
    '.login',
  ], withToken);
  _limitStop(who, 'gh api user');
  final actual = who.exitCode == 0
      ? _stripNewlines(decodeEscaped(who.stdout))
      : '';
  if (actual != login) {
    throw FenceStop(
      "as.sh: token resolves to '$actual', expected '$login'; refusing",
    );
  }
  return withToken;
}

FenceStop _refuse(String what, String maskedUrl) => FenceStop(
  'as.sh: $what has credentials in a github.com URL ($maskedUrl); remove the '
  'userinfo, the fence supplies the credential; refusing',
);

void _checkRule(String base, String prefix, String what) {
  if (!hasUserinfo(base)) return;
  if (ghUrl(base) || ghUrl(prefix)) throw _refuse(what, mask(base));
}

final RegExp _insteadOf = RegExp(
  r'^url\.(.+)\.(pushinsteadof|insteadof)=(.*)$',
  dotAll: true,
);

/// Every argument of the command, `git -c key=value` included: a github.com URL
/// with userinfo, in the argument or in its value, or a rewrite rule that adds
/// it, is refused before anything runs.
void checkArguments(List<String> command) {
  for (final a in command) {
    if (ghUserinfo(a)) throw _refuse('argument', mask(a));
    final eq = a.indexOf('=');
    final v = eq < 0 ? a : a.substring(eq + 1);
    if (eq >= 0 && ghUserinfo(v)) throw _refuse('argument', mask(v));
    if (_insteadOf.hasMatch(lowerAscii(a))) {
      var k = a.substring(0, eq < 0 ? a.length : eq);
      if (k.length >= 4 && lowerAscii(k.substring(0, 4)) == 'url.') {
        k = k.substring(4);
      }
      final dot = k.lastIndexOf('.');
      if (dot >= 0) k = k.substring(0, dot);
      _checkRule(k, v, 'argument');
    }
  }
}

String _base(String command) {
  final slash = command.lastIndexOf('/');
  return slash < 0 ? command : command.substring(slash + 1);
}

/// The options the fence reads before the subcommand of `git`, `but` and `jj`:
/// one that selects another repository or config would escape the checks that
/// read the repository `sw as` starts in, so it is refused, and `but` and `jj`
/// run only the subcommands that fetch or push.
void checkOptions(List<String> command) {
  switch (_base(command.first)) {
    case 'git' || 'git.exe':
      _checkGit(command);
    case 'but' || 'but.exe':
      _checkBut(command);
    case 'jj' || 'jj.exe':
      _checkJj(command);
  }
}

void _checkGit(List<String> command) {
  var i = 1;
  while (i < command.length) {
    final a = command[i];
    if (a == '-C' ||
        a.startsWith('-C') ||
        a == '--git-dir' ||
        a.startsWith('--git-dir=') ||
        a == '--work-tree' ||
        a.startsWith('--work-tree=')) {
      throw FenceStop(
        'as.sh: git $a selects another repository; run as.sh from inside it; refusing',
      );
    } else if (a == '-c' || a == '--namespace' || a == '--super-prefix') {
      i += 2;
    } else if (a.startsWith('-')) {
      i += 1;
    } else {
      break;
    }
  }
}

void _checkBut(List<String> command) {
  for (final a in command.skip(1)) {
    if (a == '--') break;
    if (a == '-C' ||
        (a.startsWith('-C') && a.length > 2) ||
        a == '--current-dir' ||
        a.startsWith('--current-dir=')) {
      throw FenceStop(
        'as.sh: but $a selects another repository; run as.sh from inside it; refusing',
      );
    }
  }
  var w1 = '';
  var i = 1;
  while (i < command.length) {
    final a = command[i];
    if (a == '--') break;
    if (a.startsWith('-')) {
      i += 1;
    } else {
      w1 = a;
      break;
    }
  }
  if (w1 != 'pull') {
    throw FenceStop(
      "as.sh: only 'but pull' is fenced; refusing 'but${w1.isEmpty ? '' : ' $w1'}'",
    );
  }
}

void _checkJj(List<String> command) {
  for (final a in command.skip(1)) {
    if (a == '--') break;
    if (a == '-R' ||
        (a.startsWith('-R') && a.length > 2) ||
        a == '--repository' ||
        a.startsWith('--repository=')) {
      throw FenceStop(
        'as.sh: jj $a selects another repository; run as.sh from inside it; refusing',
      );
    }
    if (a == '--config' ||
        a.startsWith('--config=') ||
        a == '--config-file' ||
        a.startsWith('--config-file=')) {
      throw FenceStop('as.sh: jj $a selects another config; refusing');
    }
  }
  var w1 = '';
  var w2 = '';
  var i = 1;
  while (i < command.length) {
    final a = command[i];
    if (a == '--') break;
    if (a == '--color' || a == '--at-op' || a == '--at-operation') {
      i += 2;
    } else if (a.startsWith('-')) {
      i += 1;
    } else {
      if (w1.isEmpty) {
        w1 = a;
      } else {
        w2 = a;
        break;
      }
      i += 1;
    }
  }
  if (w1 != 'git' || (w2 != 'push' && w2 != 'fetch')) {
    throw FenceStop(
      "as.sh: only 'jj git push' and 'jj git fetch' are fenced; "
      "refusing 'jj $w1${w2.isEmpty ? '' : ' $w2'}'",
    );
  }
}

/// Constraint C13: the fence's own git reads (`git rev-parse`, `git remote`,
/// `git remote get-url`, `git config`) and the fenced command run with no
/// deadline and no size bound, as in `as.sh`. Only the gh lookups are bounded.
///
/// In a git work tree, no remote's fetch or push URL, and no
/// `url.<base>.insteadOf` or `pushInsteadOf` rule, may add userinfo to a
/// github.com URL.
Future<void> checkRemotes(GitCall git, Map<String, String> env) async {
  final inside = await git(['git', 'rev-parse', '--is-inside-work-tree'], env);
  if (_stripNewlines(decodeEscaped(inside.stdout)) != 'true') return;
  final remotes = await git(['git', 'remote'], env);
  for (final r in _lines(remotes.stdout)) {
    if (r.isEmpty) continue;
    for (final (flags, kind) in [
      (const <String>[], 'fetch'),
      (const ['--push'], 'push'),
    ]) {
      final urls = await git([
        'git',
        'remote',
        'get-url',
        ...flags,
        '--all',
        r,
      ], env);
      for (final u in _lines(urls.stdout)) {
        if (ghUserinfo(u)) throw _refuse("remote '$r' $kind URL", mask(u));
      }
    }
  }
  final rules = await git([
    'git',
    'config',
    '--get-regexp',
    r'^url\..*\.(insteadof|pushinsteadof)$',
  ], env);
  for (final line in _lines(rules.stdout)) {
    if (line.isEmpty) continue;
    final space = line.indexOf(' ');
    final key = space < 0 ? line : line.substring(0, space);
    final val = space < 0 ? '' : line.substring(space + 1);
    var base = key.startsWith('url.') ? key.substring(4) : key;
    final dot = base.lastIndexOf('.');
    if (dot >= 0) base = base.substring(0, dot);
    final last = key.substring(key.lastIndexOf('.') + 1);
    _checkRule(base, val, 'rewrite rule url.${mask(base)}.$last');
  }
}

/// The environment the fenced command gets: [env] (with the token) plus the
/// transport settings and the command-scoped git config, which is never
/// written to a config file. SSH is disabled (`GIT_SSH_COMMAND` outranks
/// `core.sshCommand`), nothing may prompt, every inherited `http.extraHeader`
/// is emptied (an empty value resets only its own key, so each
/// `http.<url>.extraheader` key in effect is reset by name, sorted and without
/// repeats in byte order as `sort -u` does in the C locale), the inherited
/// credential helpers are dropped, and one helper answers github.com over
/// https with `GH_TOKEN`.
Future<Map<String, String>> fencedEnvironment(
  Map<String, String> env,
  GitCall git,
) async {
  final out = {...env};
  var n = 0;
  void cfg(String key, String value) {
    out['GIT_CONFIG_KEY_$n'] = key;
    out['GIT_CONFIG_VALUE_$n'] = value;
    n++;
  }

  out
    ..['GIT_SSH_COMMAND'] = _sshCommand
    ..['GIT_TERMINAL_PROMPT'] = '0'
    ..['GCM_INTERACTIVE'] = 'never'
    ..['GIT_ASKPASS'] = ''
    ..['SSH_ASKPASS'] = '';
  cfg('http.extraHeader', '');
  final found = await git([
    'git',
    'config',
    '--name-only',
    '--get-regexp',
    r'^http\..+\.extraheader$',
  ], env);
  final keys = _readLines(found.stdout)..sort(_compareBytes);
  Uint8List? previous;
  for (final key in keys) {
    if (previous != null && _compareBytes(previous, key) == 0) continue;
    previous = key;
    cfg(decodeEscaped(key), '');
  }
  cfg('credential.helper', '');
  cfg('credential.helper', _credentialHelper);
  out['GIT_CONFIG_COUNT'] = '$n';
  return out;
}

/// `as.sh`'s whole run after the handoff: [argv] is its argument list. Returns
/// the exit status (3 for any refusal or limit, the command's own otherwise);
/// messages go to [err] and `--resolve`'s login to [out].
Future<int> runFence(
  List<String> argv, {
  required Map<String, String> environment,
  required GhCall gh,
  required GitCall git,
  required Launch launch,
  required void Function(String text) out,
  required void Function(String text) err,
}) async {
  try {
    if (argv.isNotEmpty && argv.first == '--resolve') {
      if (argv.length != 1) {
        err('as.sh: --resolve takes no other arguments\n');
        return 2;
      }
    } else {
      if (argv.isEmpty || argv.first.isEmpty) {
        err('$usageLine\n');
        return 1;
      }
      if (argv.length < 2) {
        err('as.sh: no command given\n');
        return 2;
      }
    }
    final discovery = discoveryEnvironment(saveOriginals(environment));
    await checkGhVersion(gh, discovery);
    if (argv.first == '--resolve') {
      out('${await resolveLogin(gh, discovery)}\n');
      return 0;
    }
    final withToken = await verifyIdentity(argv.first, gh, discovery);
    final command = argv.sublist(1);
    checkArguments(command);
    checkOptions(command);
    await checkRemotes(git, withToken);
    return await launch(command, await fencedEnvironment(withToken, git));
  } on FenceStop catch (stop) {
    err('${stop.message}\n');
    return stop.code;
  }
}
