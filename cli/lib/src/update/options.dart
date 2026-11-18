import 'dart:io';

/// The number `sw update interface` and `plan` report: the contract the
/// install prompt reads. It changes together with the prompt (design D2, D11).
const int updateInterface = 3;

/// Every subcommand of `sw update`, in the order the usage text names them.
const List<String> updateSubcommands = [
  'plan',
  'stage',
  'swap',
  'note-config',
  'finish',
  'recover',
  'pack-check',
  'pack-verify',
  'pack-docs',
  'sw-install',
  'interface',
];

/// A usage error of `sw update`: one JSON document, exit 2.
class UpdateUsage implements Exception {
  UpdateUsage(this.message);

  final String message;

  Map<String, Object?> document() => {
    'ok': false,
    'error': 'usage',
    'message': message,
  };

  @override
  String toString() => message;
}

/// What the command line of `sw update` says. The options are those of
/// `scripts/update.sh` (design D9: the same names and messages); `--build`
/// is new and belongs to `sw-install` (design D7). Any option may come before
/// or after the subcommand and is accepted with any subcommand, as in
/// `update.sh`; only `--rollback` is tied to `recover`.
///
/// Paths are as `update.sh` makes them: absolute (a relative one is taken
/// from the current directory), with forward slashes and no trailing slash.
class UpdateOptions {
  UpdateOptions({
    required this.subcommand,
    required this.code,
    required this.root,
    this.download,
    this.ref,
    this.releaseUrl,
    this.build,
    this.skills = const [],
    this.agents = const [],
    this.packs = const [],
    this.packDocs = const [],
    this.previous = const [],
    this.rollback = false,
  });

  final String subcommand;

  /// `--code DIR`: the code checkout (default: the current directory).
  final String code;

  /// `--root DIR`: the planning root (default: [code]).
  final String root;

  /// `--download DIR`: the download tree. Null when not given: the caller
  /// that needs one decides (there is no script to take it from).
  final String? download;

  /// `--ref REF`: the ref the download came from.
  final String? ref;

  /// `--release-url URL`: `sw-install` only.
  final String? releaseUrl;

  /// `--build FILE`: `sw-install` only, a binary to place instead of a
  /// download.
  final String? build;

  /// `--skills DIR`, each one, as paths.
  final List<String> skills;

  /// `--agents KIND=DIR`, each one, with DIR as a path: `KIND=DIR`.
  final List<String> agents;

  /// `--pack NAME`, each one.
  final List<String> packs;

  /// `--pack-doc P.ID=PATH`, each one as given.
  final List<String> packDocs;

  /// `--previous NAME`, each one.
  final List<String> previous;

  /// `--rollback`: `recover` only.
  final bool rollback;
}

/// The options that take a value, as `update.sh` lists them, plus `--build`.
const Set<String> _valueOptions = {
  '--code',
  '--root',
  '--download',
  '--ref',
  '--release-url',
  '--skills',
  '--agents',
  '--pack',
  '--pack-doc',
  '--previous',
  '--build',
};

/// Parses [args] (everything after `sw update`) as `update.sh` reads its
/// command line: an option's value is the next word whatever it looks like,
/// there is no `--name=value` form, any other word starting with `-` is an
/// unknown option, and a second word is a second subcommand. [cwd] is the
/// directory relative paths are taken from (default: the current directory).
///
/// Throws [UpdateUsage].
UpdateOptions parseUpdateOptions(List<String> args, {String? cwd}) {
  final base = cwd ?? Directory.current.path;
  String? code, root, download, ref, releaseUrl, build, sub;
  final skills = <String>[];
  final agents = <String>[];
  final packs = <String>[];
  final packDocs = <String>[];
  final previous = <String>[];
  var rollback = false;
  var i = 0;
  while (i < args.length) {
    final word = args[i];
    if (_valueOptions.contains(word)) {
      if (i + 1 >= args.length) throw UpdateUsage('$word needs a value');
      final value = args[i + 1];
      switch (word) {
        case '--code':
          code = nativePath(value, base);
        case '--root':
          root = nativePath(value, base);
        case '--download':
          download = nativePath(value, base);
        case '--ref':
          ref = value;
        case '--release-url':
          releaseUrl = value;
        case '--build':
          build = nativePath(value, base);
        case '--pack':
          packs.add(value);
        case '--pack-doc':
          packDocs.add(value);
        case '--previous':
          previous.add(value);
        case '--skills':
          skills.add(nativePath(value, base));
        case '--agents':
          final at = value.indexOf('=');
          if (at < 0) throw UpdateUsage('--agents needs KIND=DIR');
          agents.add(
            '${value.substring(0, at)}=${nativePath(value.substring(at + 1), base)}',
          );
      }
      i += 2;
    } else if (word == '--rollback') {
      rollback = true;
      i++;
    } else if (word.startsWith('-')) {
      throw UpdateUsage('unknown option $word');
    } else {
      if (sub != null) throw UpdateUsage('one subcommand only');
      sub = word;
      i++;
    }
  }
  if (sub == null) {
    throw UpdateUsage(
      'a subcommand is required: plan, stage, swap, note-config, finish, '
      'recover, pack-check, pack-verify, pack-docs, sw-install or interface',
    );
  }
  if (rollback && sub != 'recover') {
    throw UpdateUsage('--rollback belongs to the recover subcommand');
  }
  if (!updateSubcommands.contains(sub)) {
    throw UpdateUsage(
      'unknown subcommand $sub (${updateSubcommands.join(', ')})',
    );
  }
  final codeDir = code ?? nativePath(base, base);
  return UpdateOptions(
    subcommand: sub,
    code: codeDir,
    root: root ?? codeDir,
    download: download,
    ref: ref,
    releaseUrl: releaseUrl,
    build: build,
    skills: skills,
    agents: agents,
    packs: packs,
    packDocs: packDocs,
    previous: previous,
    rollback: rollback,
  );
}

/// [path] as `update.sh`'s `native` makes it: absolute (taken from [base]
/// when relative), forward slashes, no trailing slash (a root stays).
String nativePath(String path, String base) {
  // a backslash is a separator on Windows only; a POSIX name may hold one
  final slashes = Platform.isWindows || RegExp(r'^[A-Za-z]:').hasMatch(path);
  String forward(String s) => slashes ? s.replaceAll(r'\', '/') : s;
  var p = forward(path);
  if (!RegExp(r'^[A-Za-z]:').hasMatch(p) && !p.startsWith('/')) {
    p = '${forward(base)}/$p';
  }
  final root = RegExp(r'^[A-Za-z]:/$');
  while (p.length > 1 && p.endsWith('/') && !root.hasMatch(p)) {
    p = p.substring(0, p.length - 1);
  }
  return p;
}
