import 'dart:convert';
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
  for (final line in _readLines(output)) decodeReplacing(line),
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
  ]..sort((a, b) => _compareBytes(utf8.encode(a), utf8.encode(b)));
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
  final text = decodeReplacing([...help.stdout, ...help.stderr]);
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
  return decodeReplacing(
    end < 0 ? bytes : Uint8List.sublistView(bytes, 0, end),
  );
}

/// `--resolve`: the active account on the selected host, without ambient tokens.
Future<String> resolveLogin(
  GhCall gh,
  Map<String, String> env, {
  String host = defaultGitHubHost,
}) async {
  final r = await gh([
    'api',
    '--hostname',
    host,
    'user',
    '--jq',
    '.login',
  ], env);
  _limitStop(r, 'gh api user');
  final login = r.exitCode == 0
      ? _stripNewlines(decodeReplacing(r.stdout))
      : '';
  const how =
      "run 'gh auth login' or set github.login in openspec/specwright.yaml "
      '(GH_TOKEN, GITHUB_TOKEN and Enterprise tokens are not used to pick the login)';
  if (login.isEmpty) {
    throw FenceStop('as.sh: no active gh account for $host; $how');
  }
  final token = await gh([
    'auth',
    'token',
    '--hostname',
    host,
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

/// Verify the stored account's own token in the selected host's credential slot.
/// Discovery starts with no token; the returned environment has only the verified one.
Future<Map<String, String>> verifyIdentity(
  String login,
  GhCall gh,
  Map<String, String> env, {
  String host = defaultGitHubHost,
}) async {
  final read = await gh([
    'auth',
    'token',
    '--hostname',
    host,
    '--user',
    login,
  ], env);
  _limitStop(read, 'gh auth token --user $login');
  final token = read.exitCode == 0
      ? _stripNewlines(decodeReplacing(read.stdout))
      : '';
  if (token.isEmpty) {
    throw FenceStop("as.sh: no gh credential for '$login' (gh auth login)");
  }
  final withToken = {
    ...env,
    githubTokenVariable(host): token,
    if (host != defaultGitHubHost) 'GH_HOST': host,
  };
  final who = await gh([
    'api',
    '--hostname',
    host,
    'user',
    '--jq',
    '.login',
  ], withToken);
  _limitStop(who, 'gh api user');
  final actual = who.exitCode == 0
      ? _stripNewlines(decodeReplacing(who.stdout))
      : '';
  if (actual != login) {
    throw FenceStop(
      "as.sh: token resolves to '$actual', expected '$login'; refusing",
    );
  }
  return withToken;
}

FenceStop _refuse(String what, String maskedUrl, String host) => FenceStop(
  'as.sh: $what has credentials in a $host URL ($maskedUrl); remove the '
  'userinfo, the fence supplies the credential; refusing',
);

void _checkRule(String base, String prefix, String what, String host) {
  if (!hasUserinfo(base)) return;
  if (ghUrl(base, host: host) || ghUrl(prefix, host: host)) {
    throw _refuse(what, mask(base), host);
  }
}

final RegExp _insteadOf = RegExp(
  r'^url\.(.+)\.(pushinsteadof|insteadof)=(.*)$',
  dotAll: true,
);

/// Every argument of the command, `git -c key=value` included: a github.com URL
/// with userinfo, in the argument or in its value, or a rewrite rule that adds
/// it, is refused before anything runs.
void checkArguments(List<String> command, {String host = defaultGitHubHost}) {
  for (final a in command) {
    if (ghUserinfo(a, host: host)) throw _refuse('argument', mask(a), host);
    final eq = a.indexOf('=');
    final v = eq < 0 ? a : a.substring(eq + 1);
    if (eq >= 0 && ghUserinfo(v, host: host)) {
      throw _refuse('argument', mask(v), host);
    }
    if (_insteadOf.hasMatch(lowerAscii(a))) {
      var k = a.substring(0, eq < 0 ? a.length : eq);
      if (k.length >= 4 && lowerAscii(k.substring(0, 4)) == 'url.') {
        k = k.substring(4);
      }
      final dot = k.lastIndexOf('.');
      if (dot >= 0) k = k.substring(0, dot);
      _checkRule(k, v, 'argument', host);
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
/// In a work tree, neither effective remotes nor rewrite rules may put
/// URL userinfo on the selected host. The optional map records effective
/// fetch/push vectors so dispatch can detect an environment-induced change.
Future<void> checkRemotes(
  GitCall git,
  Map<String, String> env, {
  String host = defaultGitHubHost,
  Map<(String, String), List<String>>? targets,
}) async {
  final inside = await git(['git', 'rev-parse', '--is-inside-work-tree'], env);
  if (_stripNewlines(decodeReplacing(inside.stdout)) != 'true') return;
  final remotes = await git(['git', 'remote'], env);
  if (remotes.exitCode != 0) {
    throw FenceStop('as.sh: cannot read configured remotes; refusing');
  }
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
      if (urls.exitCode != 0) {
        throw FenceStop("as.sh: cannot read remote '$r' $kind URLs; refusing");
      }
      final listed = _lines(urls.stdout);
      for (final u in listed) {
        if (ghUserinfo(u, host: host)) {
          throw _refuse("remote '$r' $kind URL", mask(u), host);
        }
      }
      if (targets != null) targets[(r, kind)] = listed;
    }
  }
  final rules = await git([
    'git',
    'config',
    '--get-regexp',
    r'^url\..*\.(insteadof|pushinsteadof)$',
  ], env);
  if (rules.exitCode != 0 && rules.exitCode != 1) {
    throw FenceStop('as.sh: cannot read Git URL rewrite rules; refusing');
  }
  for (final line in _lines(rules.stdout)) {
    if (line.isEmpty) continue;
    final space = line.indexOf(' ');
    final key = space < 0 ? line : line.substring(0, space);
    final val = space < 0 ? '' : line.substring(space + 1);
    var base = key.startsWith('url.') ? key.substring(4) : key;
    final dot = base.lastIndexOf('.');
    if (dot >= 0) base = base.substring(0, dot);
    final last = key.substring(key.lastIndexOf('.') + 1);
    _checkRule(base, val, 'rewrite rule url.${mask(base)}.$last', host);
  }
}

/// The environment the fenced command gets: [env] (with the token) plus the
/// transport settings and the command-scoped git config, which is never
/// written to a config file. SSH is disabled (`GIT_SSH_COMMAND` outranks
/// `core.sshCommand`), nothing may prompt, every inherited `http.extraHeader`
/// is emptied (an empty value resets only its own key, so each
/// `http.<url>.extraheader` key in effect is reset by name, sorted and without
/// repeats in byte order as `sort -u` does in the C locale), the inherited
/// credential helpers are dropped, and one helper answers over HTTPS only.
Future<Map<String, String>> fencedEnvironment(
  Map<String, String> env,
  GitCall git, {
  String host = defaultGitHubHost,
}) async {
  final out = {...env};
  final windows = Platform.isWindows;
  final countKey = _keyOf(env, 'GIT_CONFIG_COUNT', windows);
  final count = countKey == null ? 0 : int.tryParse(env[countKey]!) ?? -1;
  if (count < 0 || count > env.length ~/ 2) {
    throw FenceStop('as.sh: invalid indexed Git config; refusing');
  }
  out.removeWhere((key, _) {
    final name = windows ? key.toUpperCase() : key;
    return name == 'GIT_CONFIG_COUNT' || _gitConfigName.hasMatch(name);
  });
  var n = 0;
  void cfg(String key, String value) {
    out['GIT_CONFIG_KEY_$n'] = key;
    out['GIT_CONFIG_VALUE_$n'] = value;
    n++;
  }

  for (var i = 0; i < count; i++) {
    final key = _keyOf(env, 'GIT_CONFIG_KEY_$i', windows);
    final value = _keyOf(env, 'GIT_CONFIG_VALUE_$i', windows);
    if (key == null || value == null) {
      throw FenceStop('as.sh: incomplete indexed Git config; refusing');
    }
    final k = env[key]!;
    final folded = lowerAscii(k);
    if (!folded.startsWith('url.') ||
        !(folded.endsWith('.insteadof') || folded.endsWith('.pushinsteadof'))) {
      continue;
    }
    final base = k.substring(4, k.lastIndexOf('.'));
    final prefix = env[value]!;
    _checkRule(base, prefix, 'indexed rewrite rule', host);
    cfg(k, prefix);
  }

  out
    ..['GIT_SSH_COMMAND'] =
        'sh -c "echo as.sh: SSH is disabled - push over https://$host so the identity can be pinned >&2; exit 1"'
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
  if (found.exitCode != 0 && found.exitCode != 1) {
    throw FenceStop('as.sh: cannot read inherited Git HTTP headers; refusing');
  }
  final keys = _readLines(found.stdout)..sort(_compareBytes);
  Uint8List? previous;
  for (final key in keys) {
    if (previous != null && _compareBytes(previous, key) == 0) continue;
    previous = key;
    cfg(decodeStrict(key, 'git config name'), '');
  }
  cfg('credential.helper', '');
  cfg(
    'credential.helper',
    host == defaultGitHubHost
        ? _credentialHelper
        : _credentialHelper
              .replaceFirst('= github.com ]', '= $host ]')
              .replaceFirst(r'$GH_TOKEN', '\$${githubTokenVariable(host)}'),
  );
  out['GIT_CONFIG_COUNT'] = '$n';
  return out;
}

/// Check the actual command environment. Indexed entries may change routing
/// when unsafe overrides are stripped; never accept a different destination
/// just because it still names the same host.
Future<Map<String, String>> prepareFencedCommand(
  List<String> command,
  Map<String, String> env,
  GitCall git, {
  String host = defaultGitHubHost,
}) async {
  checkArguments(command, host: host);
  checkOptions(command);
  final countKey = _keyOf(env, 'GIT_CONFIG_COUNT', Platform.isWindows);
  final compare = countKey != null && env[countKey] != '0';
  final before = compare ? <(String, String), List<String>>{} : null;
  if (before != null) await checkRemotes(git, env, host: host, targets: before);
  final execution = await fencedEnvironment(env, git, host: host);
  final after = compare ? <(String, String), List<String>>{} : null;
  await checkRemotes(git, execution, host: host, targets: after);
  if (before != null && after != null) {
    if (before.length != after.length) {
      throw FenceStop(
        'as.sh: Git destinations changed in the fenced environment; refusing',
      );
    }
    for (final entry in before.entries) {
      final (remote, kind) = entry.key;
      final actual = after[entry.key];
      if (actual == null || !_sameUrls(actual, entry.value)) {
        throw FenceStop(
          "as.sh: remote '$remote' $kind destinations changed in the fenced environment; refusing",
        );
      }
    }
  }
  return execution;
}

bool _sameUrls(List<String> a, List<String> b) {
  if (a.length != b.length) return false;
  for (var i = 0; i < a.length; i++) {
    if (a[i] != b[i]) return false;
  }
  return true;
}

/// `as.sh`'s whole run: [argv] is its argument list. Returns
/// the exit status (3 for any refusal or limit, 2 for input the launcher cannot
/// represent, the command's own otherwise);
/// messages go to [err] and `--resolve`'s login to [out].
Future<int> runFence(
  List<String> argv, {
  required Map<String, String> environment,
  String host = defaultGitHubHost,
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
      out('${await resolveLogin(gh, discovery, host: host)}\n');
      return 0;
    }
    final withToken = await verifyIdentity(
      argv.first,
      gh,
      discovery,
      host: host,
    );
    final command = argv.sublist(1);
    final execution = await prepareFencedCommand(
      command,
      withToken,
      git,
      host: host,
    );
    return await launch(command, execution);
  } on FenceStop catch (stop) {
    err('${stop.message}\n');
    return stop.code;
  } on NotUtf8 catch (e) {
    // D4: a git config name is copied into the environment of the command, so it is read strictly
    err('as.sh: ${e.message}; rename it and run again\n');
    return 2;
  } on Unrepresentable catch (e) {
    // D5: input the launcher cannot hand to a tool is refused by name, exit 2
    err('as.sh: unrepresentable ${e.what}: ${e.command}\n');
    return 2;
  }
}
