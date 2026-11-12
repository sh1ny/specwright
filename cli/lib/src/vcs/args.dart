import 'dart:io';
import 'dart:typed_data';

import '../options.dart';
import 'codec.dart';
import 'stop.dart';

/// What `sw vcs --args-stdin` read from stdin (design D2): the scripts
/// directory, the bash running the shim, and the operation (`<sub>` and every
/// argument) in `vcs.sh`'s own argument form.
class Handoff {
  Handoff(this.scriptsDir, this.bash, this.argv);

  final String scriptsDir;
  final String bash;
  final List<String> argv;
}

const String handoffUsage =
    'usage: sw vcs --args-stdin (stdin: scripts dir, bash path, subcommand and '
    'arguments, each record ending in a NUL byte)';

/// Splits the stdin of `sw <command> --args-stdin` into NUL-terminated
/// records, each decoded strictly ([decodeHandoffRecords]). Fewer than three records, or a last
/// record with no NUL, is a usage stop (exit 2) whose message is [usage], so
/// each command names itself (`sw vcs` passes [handoffUsage]).
Handoff parseHandoff(List<int> stdin, String usage) {
  if (stdin.isNotEmpty && stdin.last != 0) {
    throw VcsStop('usage', usage, code: 2);
  }
  final records = decodeHandoffRecords(Uint8List.fromList(stdin));
  if (records.length < 3) {
    throw VcsStop('usage', usage, code: 2);
  }
  return Handoff(records[0], records[1], records.sublist(2));
}

/// The subcommand, options and paths of one `sw vcs` call, parsed as
/// `vcs.sh`'s `context()` did. Option values are kept as given, an empty one
/// included: callers treat an empty string as unset, as `vcs.sh` does.
class VcsRequest {
  VcsRequest({
    required this.command,
    required this.repo,
    required this.role,
    required this.code,
    this.branch,
    this.messageFile,
    this.scope,
    this.operation,
    this.login,
    this.main,
    this.prefix,
    this.mergedCommit,
    this.force = false,
    this.noTags = false,
    this.quiet = false,
    this.remoteBranch = false,
    this.paths = const [],
  });

  final String command;
  final String repo;

  /// `code` or `store`.
  final String role;

  /// `--code`, defaulting to [repo] for the code role.
  final String code;
  final String? branch;
  final String? messageFile;
  final String? scope;
  final String? operation;
  final String? login;
  final String? main;
  final String? prefix;
  final String? mergedCommit;
  final bool force;
  final bool noTags;
  final bool quiet;
  final bool remoteBranch;

  /// What followed `--`.
  final List<String> paths;
}

const _valueOptions = [
  'repo',
  'role',
  'code',
  'branch',
  'message-file',
  'scope',
  'operation',
  'login',
  'main',
  'prefix',
  'merged-commit',
];

const _flagOptions = ['force', 'no-tags', 'quiet', 'remote-branch'];

const knownCommands = {
  'probe',
  'state',
  'branch-create',
  'switch',
  'commit',
  'merge',
  'delete-branch',
  'fetch-main',
  'pull',
  'push',
  'advance',
  'plan',
};

const _usageLine =
    'usage: vcs.sh <command> --repo <dir> --role code|store [--code <dir>] '
    '[options] [-- paths...]';

VcsStop _usage(String message) => VcsStop('usage', message, code: 2);

/// Parses `<command> [options] [-- paths...]` in the order `vcs.sh:233-272`
/// checks it: options first (an unknown one, or a missing value, is a usage
/// stop), then the command name, `--repo` and `--role`, then `--code`
/// (required for `store`, defaulting to `--repo` for `code`), then that both
/// name existing directories (`not_repository`, exit 1).
///
/// Options follow the one rule of `options.dart`: `--name value` or
/// `--name=value`, the next word is the value whatever it looks like, and no
/// abbreviations.
///
/// Constraint C7: `sw vcs` treats words before `--` as an error, so a stray
/// word never becomes a path to commit. Paths are accepted only as the tail of
/// the arguments that follows a `--` token; any other word that is not an
/// option or an option's value is a usage stop (exit 2) and nothing is
/// committed.
VcsRequest parseVcsArguments(List<String> argv) {
  if (argv.isEmpty) throw _usage('missing command');
  final command = argv.first;
  final args = argv.sublist(1);
  final parsed = parseOptions(
    args,
    values: _valueOptions,
    flags: _flagOptions,
    usage: (message) => throw _usage(message),
  );
  // `rest` is the words that are not options with the first separating `--` dropped: it is paths only when it is the tail
  // of `args` that directly follows that `--`, and that `--` is not the value of the option before it.
  final paths = parsed.rest;
  if (paths.isNotEmpty && args.length - paths.length != _separator(args) + 1) {
    throw _usage('unexpected argument: ${paths.first}');
  }
  final opts = {
    for (final name in _valueOptions)
      if (parsed.wasParsed(name)) '--$name': parsed.option(name)!,
  };
  final flags = {
    for (final name in _flagOptions)
      if (parsed.flag(name)) '--$name',
  };
  if (!knownCommands.contains(command)) {
    throw _usage('unknown command: $command');
  }
  final repo = opts['--repo'] ?? '';
  final role = opts['--role'];
  if (repo.isEmpty || (role != 'code' && role != 'store')) {
    throw _usage(_usageLine);
  }
  var code = opts['--code'] ?? '';
  if (role == 'store' && code.isEmpty) {
    throw _usage('--code is required when --role store');
  }
  if (role == 'code' && code.isEmpty) code = repo;
  if (!_isDirectory(repo) || !_isDirectory(code)) {
    throw VcsStop(
      'not_repository',
      '--repo and --code must name existing directories',
    );
  }
  return VcsRequest(
    command: command,
    repo: repo,
    role: role!,
    code: code,
    branch: opts['--branch'],
    messageFile: opts['--message-file'],
    scope: opts['--scope'],
    operation: opts['--operation'],
    login: opts['--login'],
    main: opts['--main'],
    prefix: opts['--prefix'],
    mergedCommit: opts['--merged-commit'],
    force: flags.contains('--force'),
    noTags: flags.contains('--no-tags'),
    quiet: flags.contains('--quiet'),
    remoteBranch: flags.contains('--remote-branch'),
    paths: paths,
  );
}

/// The index of the `--` that ends the options in [args], skipping the word after each value-taking option written
/// without `=`, since that word is its value; -1 when there is none.
int _separator(List<String> args) {
  for (var i = 0; i < args.length; i++) {
    if (args[i] == '--') return i;
    if (args[i].startsWith('--') &&
        _valueOptions.contains(args[i].substring(2))) {
      i++;
    }
  }
  return -1;
}

bool _isDirectory(String path) {
  try {
    return Directory(path).existsSync();
  } on Object {
    return false;
  }
}
