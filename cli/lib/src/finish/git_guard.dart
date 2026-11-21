import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:path/path.dart' as p;

import '../entry/regular_file.dart';
import '../vcs/codec.dart';
import '../vcs/git_backend.dart';
import '../vcs/stop.dart';
import '../vcs/tool_runner.dart';

/// The global options of every Git command the undo planner runs or emits: a
/// pathspec is a literal path, and a replace ref never changes what an object
/// is.
const List<String> gitSafety = ['--literal-pathspecs', '--no-replace-objects'];

/// Runs `git <args>` where the guard runs; the caller adds [gitSafety].
typedef GitRun = Future<ToolResult> Function(List<String> args);

/// The paths Git resolved for a checkout: its work tree, Git directory, common
/// directory, index file and object directory.
class GitView {
  GitView({
    required this.top,
    required this.gitDir,
    required this.commonDir,
    required this.index,
    required this.objects,
  });

  final String top;
  final String gitDir;
  final String commonDir;
  final String index;
  final String objects;

  /// The fields with the name a refusal uses for each.
  List<(String, String)> get fields => [
    ('work tree', top),
    ('git directory', gitDir),
    ('common directory', commonDir),
    ('index', index),
    ('object directory', objects),
  ];
}

/// Git's reading of a boolean environment value: `1`, `true`, `yes`, `on` or a
/// non-zero number is true. Anything that is not clearly false counts, so a
/// value Git would reject beside the option is refused too.
bool gitTruthy(String? value) {
  if (value == null) return false;
  final v = value.trim().toLowerCase();
  return !(v.isEmpty ||
      v == 'false' ||
      v == 'no' ||
      v == 'off' ||
      (int.tryParse(v) ?? 1) == 0);
}

/// Refuses, with `git_env`, an environment the steps do not support: a true
/// pathspec mode variable, or a non-empty `GIT_NAMESPACE` or
/// `GIT_ALTERNATE_OBJECT_DIRECTORIES`.
void refuseGitEnvironment(Map<String, String> env) {
  for (final name in const [
    'GIT_GLOB_PATHSPECS',
    'GIT_NOGLOB_PATHSPECS',
    'GIT_ICASE_PATHSPECS',
  ]) {
    if (gitTruthy(env[name])) {
      throw VcsStop(
        'git_env',
        '$name is set, so Git would read the plan\'s literal paths as '
            'patterns; unset it, then plan again',
      );
    }
  }
  for (final name in const [
    'GIT_NAMESPACE',
    'GIT_ALTERNATE_OBJECT_DIRECTORIES',
  ]) {
    if ((env[name] ?? '').isNotEmpty) {
      throw VcsStop(
        'git_env',
        '$name is set, so Git would read other refs or objects than the plan '
            'did; unset it, then plan again',
      );
    }
  }
}

String _real(String path) {
  final s = path.replaceAll(r'\', '/');
  try {
    return File(s).resolveSymbolicLinksSync();
  } on FileSystemException {
    try {
      return '${File(s).parent.resolveSymbolicLinksSync()}/${p.basename(s)}';
    } on FileSystemException {
      return s;
    }
  }
}

/// Whether two spellings name one path (links resolved, case folded on
/// Windows).
bool samePath(String a, String b) =>
    p.canonicalize(_real(a)) == p.canonicalize(_real(b));

String? _readText(String path) {
  try {
    final bytes = readRegularFile(path);
    return bytes == null ? null : utf8.decode(bytes).trim();
  } on NotRegularFile {
    return null;
  } on FileSystemException {
    return null;
  } on FormatException {
    return null;
  }
}

/// The paths of [top], derived from its `.git` entry alone (a directory, or a
/// file that names the Git directory), or null when it has none. It reads no
/// Git configuration and no environment, so it is independent of what could
/// reroute Git.
GitView? derivedView(String top) {
  final dotGit = '$top/.git';
  final String gitDir;
  switch (FileSystemEntity.typeSync(dotGit)) {
    case FileSystemEntityType.directory:
      gitDir = dotGit;
    case FileSystemEntityType.file:
      final text = _readText(dotGit);
      if (text == null || !text.startsWith('gitdir:')) return null;
      final named = text.substring('gitdir:'.length).trim();
      gitDir = p.isAbsolute(named) ? named : p.join(top, named);
    default:
      return null;
  }
  final common = _readText('$gitDir/commondir');
  final commonDir = common == null || common.isEmpty
      ? gitDir
      : (p.isAbsolute(common) ? common : p.join(gitDir, common));
  return GitView(
    top: top,
    gitDir: gitDir,
    commonDir: commonDir,
    index: '$gitDir/index',
    objects: '$commonDir/objects',
  );
}

/// The paths Git resolves now, in the caller's environment and configuration.
Future<GitView> effectiveView(GitRun run) async {
  final r = await run([
    'rev-parse',
    '--path-format=absolute',
    '--show-toplevel',
    '--absolute-git-dir',
    '--git-common-dir',
    '--git-path',
    'index',
    '--git-path',
    'objects',
  ]);
  checkRead(r, 'git rev-parse');
  final lines = decodeStrict(
    r.stdout,
    'repository path',
  ).split('\n').where((l) => l.isNotEmpty).toList();
  if (lines.length != 5) {
    throw failedRead('git rev-parse', why: 'it printed ${lines.length} paths');
  }
  return GitView(
    top: lines[0],
    gitDir: lines[1],
    commonDir: lines[2],
    index: lines[3],
    objects: lines[4],
  );
}

bool _exists(String path) =>
    FileSystemEntity.typeSync(path, followLinks: false) !=
    FileSystemEntityType.notFound;

/// The name of the merge, cherry-pick, revert, rebase or sequencer state under
/// [gitDir], or null when none is in progress.
String? operationInProgress(String gitDir) {
  for (final name in const [
    'MERGE_HEAD',
    'CHERRY_PICK_HEAD',
    'REVERT_HEAD',
    'rebase-merge',
    'rebase-apply',
    'sequencer',
  ]) {
    if (_exists('$gitDir/$name')) return name;
  }
  return null;
}

/// The stop for an operation in progress under [gitDir].
VcsStop operationStop(String name) => VcsStop(
  'operation_in_progress',
  'A merge, cherry-pick, revert or rebase is in progress ($name); finish or '
      'abort it, then plan again',
);

/// Refuses a grafts file under [commonDir]: commits would not be what their
/// objects say (`git_env`).
void refuseGrafts(String commonDir) {
  if (_exists('$commonDir/info/grafts')) {
    throw VcsStop(
      'git_env',
      'The repository has a grafts file ($commonDir/info/grafts), so commits '
          'are not what their objects say; remove it, then plan again',
    );
  }
}

/// The shared first guard of a Git undo, in this order: the environment
/// ([refuseGitEnvironment]), Git's effective view against the one derived from
/// the `.git` entry and against [recorded] when the plan recorded one, the
/// grafts, partial-clone and sparse refusals (`git_env`), GitButler's metadata
/// directory (`gitbutler_workspace`) and an operation in progress
/// (`operation_in_progress`). Returns the effective view.
Future<GitView> gitPreflight(
  GitRun run,
  Map<String, String> env,
  String top, {
  GitView? recorded,
}) async {
  refuseGitEnvironment(env);
  final effective = await effectiveView(run);
  final derived = derivedView(top);
  final now = effective.fields;
  final fromGit = derived?.fields;
  final fromPlan = recorded?.fields;
  for (var i = 0; i < now.length; i++) {
    final (label, value) = now[i];
    if (fromGit != null && !samePath(value, fromGit[i].$2)) {
      throw VcsStop(
        'git_env',
        "Git's $label is $value, but the checkout's .git entry gives "
            '${fromGit[i].$2}; something reroutes Git, so the steps are not '
            'supported here',
      );
    }
    if (fromPlan != null && !samePath(value, fromPlan[i].$2)) {
      throw VcsStop(
        'git_env',
        "Git's $label is $value, not ${fromPlan[i].$2} the plan was made for",
      );
    }
  }
  refuseGrafts(effective.commonDir);
  await _refuseConfigured(run);
  _refusePromisorPack(effective.commonDir);
  for (final dir in {effective.gitDir, effective.commonDir}) {
    if (_exists('$dir/gitbutler')) {
      throw VcsStop(
        'gitbutler_workspace',
        'The repository holds GitButler metadata ($dir/gitbutler); a Git undo '
            'does not run in a GitButler workspace',
      );
    }
  }
  final operation = operationInProgress(effective.gitDir);
  if (operation != null) throw operationStop(operation);
  return effective;
}

Future<void> _refuseConfigured(GitRun run) async {
  final r = await run([
    'config',
    '-z',
    '--get-regexp',
    r'^(extensions\.partialclone|core\.sparsecheckout|remote\..*\.promisor)$',
  ]);
  if (r.exitCode == 1 && r.stderr.isEmpty && r.stdout.isEmpty) return;
  checkRead(r, 'git config');
  for (final record in decodeReplacing(r.stdout).split('\u0000')) {
    if (record.isEmpty) continue;
    final at = record.indexOf('\n');
    final key = (at < 0 ? record : record.substring(0, at)).toLowerCase();
    final value = at < 0 ? 'true' : record.substring(at + 1);
    if (key == 'extensions.partialclone' && value.isNotEmpty) {
      throw VcsStop(
        'git_env',
        'The repository is a partial clone (extensions.partialClone), so an '
            'object the plan reads may be fetched or missing; a Git undo is '
            'not supported in one',
      );
    }
    if (key.endsWith('.promisor') && gitTruthy(value)) {
      throw VcsStop(
        'git_env',
        'The repository is a partial clone ($key is true), so an object the '
            'plan reads may be fetched or missing; a Git undo is not '
            'supported in one',
      );
    }
    if (key == 'core.sparsecheckout' && gitTruthy(value)) {
      throw VcsStop(
        'git_env',
        'The repository uses a sparse checkout (core.sparseCheckout), so a '
            'path may be absent from the work tree by design; a Git undo is '
            'not supported in one',
      );
    }
  }
}

void _refusePromisorPack(String commonDir) {
  try {
    for (final e in Directory('$commonDir/objects/pack').listSync()) {
      if (e.path.endsWith('.promisor')) {
        throw VcsStop(
          'git_env',
          'The repository is a partial clone (${p.basename(e.path)}), so an '
              'object the plan reads may be fetched or missing; a Git undo is '
              'not supported in one',
        );
      }
    }
  } on FileSystemException {
    // no pack directory: nothing promised
  }
}

/// The tip of the branch ref [ref] (`refs/heads/<name>`): the exact ref in a
/// `for-each-ref` listing, which no tag or abbreviation can stand in for, or
/// the empty string when the listing does not hold it. A failed listing is a
/// `vcs_error`.
Future<String> branchTip(GitRun run, String ref) async {
  final r = await run([
    'for-each-ref',
    '--format=%(objectname) %(refname)',
    ref,
  ]);
  for (final line in readInventory(
    r,
    'git for-each-ref',
    framing: Framing.lf,
  )) {
    final text = decodeStrict(line.single, 'ref name');
    final space = text.indexOf(' ');
    if (space > 0 && text.substring(space + 1) == ref) {
      return text.substring(0, space);
    }
  }
  return '';
}

/// The first index entry flagged assume-unchanged or skip-worktree, as its
/// path, or null when none is (under [paths] when given).
///
/// `git ls-files -v -z` is read as it arrives, one NUL-ended record at a time;
/// no path list is kept, and the read stops, and the child is ended, at the
/// first flagged entry. A lowercase tag is assume-unchanged; `S` is
/// skip-worktree. A failed read is a `vcs_error`.
Future<String?> firstFlaggedEntry({
  required String cwd,
  required Map<String, String> environment,
  List<String> paths = const [],
}) async {
  final Process process;
  try {
    process = await Process.start(
      'git',
      [
        ...gitSafety,
        '-c',
        'core.fsmonitor=false',
        '--no-optional-locks',
        'ls-files',
        '-v',
        '-z',
        if (paths.isNotEmpty) '--',
        ...paths,
      ],
      workingDirectory: cwd,
      environment: {...environment, 'GIT_OPTIONAL_LOCKS': '0'},
      includeParentEnvironment: false,
    );
  } on ProcessException catch (e) {
    throw VcsStop('vcs_error', 'git ls-files -v could not run: ${e.message}');
  }
  final said = <int>[];
  final err = process.stderr.forEach(said.addAll);
  final record = BytesBuilder(copy: false);
  String? found;
  Object? streamError;
  try {
    scan:
    await for (final chunk in process.stdout) {
      for (final b in chunk) {
        if (b != 0) {
          record.addByte(b);
          continue;
        }
        final bytes = record.takeBytes();
        if (bytes.length > 2) {
          final tag = bytes[0];
          if ((tag >= 0x61 && tag <= 0x7a) || tag == 0x53) {
            found = decodeReplacing(Uint8List.sublistView(bytes, 2));
            break scan;
          }
        }
      }
    }
  } catch (e) {
    streamError = e;
  }
  if (found != null) {
    process.kill();
    await process.exitCode;
    await err;
    return found;
  }
  final code = await process.exitCode;
  await err;
  if (code != 0 || said.isNotEmpty || streamError != null) {
    throw failedRead(
      'git ls-files -v',
      exitCode: code,
      stderr: said,
      streamError: streamError,
    );
  }
  return null;
}
