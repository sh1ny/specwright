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
/// pathspec mode variable, or a non-empty `GIT_NAMESPACE`,
/// `GIT_ALTERNATE_OBJECT_DIRECTORIES` or `GIT_ATTR_SOURCE`.
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
  if ((env['GIT_ATTR_SOURCE'] ?? '').isNotEmpty) {
    throw VcsStop(
      'git_env',
      'GIT_ATTR_SOURCE is set, so Git would read attributes from another '
          'tree than the plan did; unset it, then plan again',
    );
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

/// The checkout that holds [dir]: the nearest directory on its path with a
/// `.git` entry, or null when there is none. It reads no Git configuration and
/// no environment, so `GIT_DIR` and `GIT_WORK_TREE` cannot change the answer.
String? checkoutOf(String dir) {
  var at = p.absolute(dir);
  while (true) {
    if (FileSystemEntity.typeSync('$at/.git', followLinks: false) !=
        FileSystemEntityType.notFound) {
      return at;
    }
    final up = p.dirname(at);
    if (up == at) return null;
    at = up;
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
    r'^(extensions\.partialclone|core\.sparsecheckout|remote\..*\.promisor|attr\.tree)$',
  ]);
  if (r.exitCode == 1 && r.stderr.isEmpty && r.stdout.isEmpty) return;
  checkRead(r, 'git config');
  for (final record in decodeReplacing(r.stdout).split('\u0000')) {
    if (record.isEmpty) continue;
    final at = record.indexOf('\n');
    final key = (at < 0 ? record : record.substring(0, at)).toLowerCase();
    final value = at < 0 ? 'true' : record.substring(at + 1);
    if (key == 'attr.tree') {
      throw VcsStop(
        'git_env',
        'The repository sets attr.tree, so Git would read attributes from '
            'another tree than the plan did; unset it, then plan again',
      );
    }
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

/// Refuses, with `unsupported_filter`, a path of [paths] that has a `filter` or
/// `working-tree-encoding` attribute at [source] (named [label] in the
/// message): an unset or an `unspecified` value included, since only the
/// attribute's name matters. Git reads the attributes of the tree named
/// [source] with `check-attr --source` (Git 2.40 or later), under the
/// environment and configuration [run] gives it; no filter command runs.
Future<void> refuseConversion(
  GitRun run,
  String source,
  String label,
  List<String> paths,
) async {
  final r = await run([
    'check-attr',
    '-z',
    '--all',
    '--source=$source',
    '--',
    ...paths,
  ]);
  for (final f in readInventory(r, 'git check-attr', fields: 3)) {
    final attr = decodeStrict(f[1], 'attribute name');
    if (attr != 'filter' && attr != 'working-tree-encoding') continue;
    final path = decodeReplacing(f[0]);
    final value = decodeReplacing(f[2]);
    throw VcsStop(
      'unsupported_filter',
      '$path has the $attr attribute ($value) at $label, so a checkout would '
          'convert it and the restored bytes would not be the ones the plan '
          'read; a Git undo does not support that',
    );
  }
}

/// [refuseConversion] for the tip of the archive branch and for HEAD: the
/// attributes a resume's checkout applies are the tip's, and the ones it keeps
/// are HEAD's.
Future<void> refuseConversions(
  GitRun run,
  String tip,
  List<String> paths,
) async {
  await refuseConversion(run, tip, 'tip', paths);
  await refuseConversion(run, 'HEAD', 'HEAD', paths);
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
  final found = await _scanListing(
    cwd: cwd,
    environment: environment,
    label: 'git ls-files -v',
    args: ['ls-files', '-v', '-z', if (paths.isNotEmpty) '--', ...paths],
    keep: 1,
    pick: (bytes) {
      if (bytes.length <= 2) return null;
      final tag = bytes[0];
      if ((tag >= 0x61 && tag <= 0x7a) || tag == 0x53) {
        return decodeReplacing(Uint8List.sublistView(bytes, 2));
      }
      return null;
    },
  );
  return found.isEmpty ? null : found.first;
}

/// The files under [dir] that Git does not track, ignored ones included (no
/// exclude option is passed), at most [keep] of them: empty when every file
/// there is tracked.
///
/// `git ls-files -z --others` is read as it arrives and the read ends, with
/// the child, once [keep] records were kept, so a tree of untracked files
/// never fills memory. A failed read is a `vcs_error`.
Future<List<String>> untrackedUnder({
  required String cwd,
  required Map<String, String> environment,
  required String dir,
  int keep = 20,
}) => _scanListing(
  cwd: cwd,
  environment: environment,
  label: 'git ls-files --others',
  args: ['ls-files', '-z', '--others', '--', dir],
  keep: keep,
  pick: (bytes) =>
      bytes.isEmpty ? null : decodeReplacing(Uint8List.sublistView(bytes)),
);

/// Starts `git` with the safety options and [args] in [cwd], reads its stdout
/// one NUL-ended record at a time, and returns what [pick] keeps of them, at
/// most [keep]; the child is ended as soon as that many were kept. A non-zero
/// exit, any stderr output or a stream error when nothing stopped the read
/// early is a failed read (`vcs_error` naming [label]).
///
/// This is the one place a guard starts an incremental `git` reader.
Future<List<String>> _scanListing({
  required String cwd,
  required Map<String, String> environment,
  required String label,
  required List<String> args,
  required int keep,
  required String? Function(Uint8List record) pick,
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
        ...args,
      ],
      workingDirectory: cwd,
      environment: {...environment, 'GIT_OPTIONAL_LOCKS': '0'},
      includeParentEnvironment: false,
    );
  } on ProcessException catch (e) {
    throw VcsStop('vcs_error', '$label could not run: ${e.message}');
  }
  final said = <int>[];
  final err = process.stderr.forEach(said.addAll);
  final record = BytesBuilder(copy: false);
  final found = <String>[];
  Object? streamError;
  try {
    scan:
    await for (final chunk in process.stdout) {
      for (final b in chunk) {
        if (b != 0) {
          record.addByte(b);
          continue;
        }
        final kept = pick(record.takeBytes());
        if (kept != null) {
          found.add(kept);
          if (found.length >= keep) break scan;
        }
      }
    }
  } catch (e) {
    streamError = e;
  }
  if (found.length >= keep) {
    process.kill();
    await process.exitCode;
    await err;
    return found;
  }
  final code = await process.exitCode;
  await err;
  if (code != 0 || said.isNotEmpty || streamError != null) {
    throw failedRead(
      label,
      exitCode: code,
      stderr: said,
      streamError: streamError,
    );
  }
  return found;
}

VcsStop _unsupportedEntry(String message) =>
    VcsStop('unsupported_entry', message);

/// The paths [raw] names, as components with no empty ones.
List<String> _components(String raw) => [
  for (final c in raw.replaceAll(r'\', '/').split('/'))
    if (c.isNotEmpty) c,
];

/// Refuses, with `unsupported_entry` naming both, two of [paths] that are
/// equal, or one under the other as a directory prefix, once case is folded
/// with `toLowerCase()` or with `toUpperCase()`, so that no path has to be
/// both a file and a directory (C46). Equal strings are one path. The check is
/// on every file system, since the plan cannot know where the checkout is used.
void refuseCollidingPaths(Iterable<String> paths) {
  final unique = <String>{...paths}.toList();
  for (final fold in <String Function(String)>[
    (s) => s.toLowerCase(),
    (s) => s.toUpperCase(),
  ]) {
    final exact = <String, String>{};
    final above = <String, String>{};
    for (final path in unique) {
      final parts = [for (final c in _components(path)) fold(c)];
      final key = parts.join('/');
      final clash = exact[key] ?? above[key];
      if (clash != null) throw _collision(clash, path);
      for (var n = 1; n < parts.length; n++) {
        final owner = exact[parts.sublist(0, n).join('/')];
        if (owner != null) throw _collision(owner, path);
      }
      exact[key] = path;
      for (var n = 1; n < parts.length; n++) {
        above.putIfAbsent(parts.sublist(0, n).join('/'), () => path);
      }
    }
  }
}

/// Refuses, with `path_owned_elsewhere`, a path another applied GitButler
/// branch has an assigned, uncommitted edit at ([foreign]: path and branch,
/// each path exactly as `but` spells it) that the undo would write: a path
/// equal to one of [files] or equal to, or under, one of [dirs] (the archived
/// member directories it moves and the directories it restores them to), case
/// folded as [refuseCollidingPaths] folds. Nothing is rewritten, so a backslash
/// in a name stays a backslash.
void refuseForeignAssignments(
  List<(String, String)> foreign, {
  required String branch,
  required List<String> files,
  required List<String> dirs,
}) {
  for (final (path, owner) in foreign) {
    final key = path.toLowerCase();
    String? hit;
    for (final f in files) {
      if (f.toLowerCase() == key) hit = f;
    }
    for (final d in dirs) {
      final dir = d.toLowerCase();
      if (key == dir || key.startsWith('$dir/')) hit = d;
    }
    if (hit != null) {
      throw VcsStop(
        'path_owned_elsewhere',
        '$path is assigned to branch $owner, not $branch, and the undo '
            'writes $hit; unassign the edit or finish it on $owner first, '
            'then plan again',
        extra: {'path': path, 'branch': owner},
      );
    }
  }
}

VcsStop _collision(String a, String b) => _unsupportedEntry(
  '$a and $b are the same path, or one lies under the other, once case is '
  'folded; the undo would write both, so it stops before it writes either',
);

/// Whether [name] is one of the spellings Windows and a case-insensitive volume
/// resolve as `.git`: case folded, trailing dots and spaces removed.
bool namesDotGit(String name) =>
    name.replaceFirst(RegExp(r'[. ]+$'), '').toLowerCase() == '.git';

/// The one walk of the destination list (C46): below [root], every existing
/// component of each path in [files], [dirs] and [members] must be a real
/// directory (no symbolic link, junction or file), spelled as the disk spells
/// it; an existing leaf of [files] must be a regular file, and one of [dirs]
/// and [members] a real directory; no component may hold a `.git` entry; and
/// each [members] directory is searched, without following a link, for an
/// entry of any type that is named like `.git`, anywhere below it. Anything
/// else is `unsupported_entry` naming the path.
void walkDestinations(
  String root, {
  List<String> files = const [],
  List<String> dirs = const [],
  List<String> members = const [],
}) {
  String at(String rel) => rel.isEmpty ? root : '$root/$rel';
  FileSystemEntityType typeOf(String rel) =>
      FileSystemEntity.typeSync(at(rel), followLinks: false);
  final listings = <String, Map<String, List<String>>>{};
  Map<String, List<String>> namesIn(
    String rel,
  ) => listings.putIfAbsent(rel, () {
    final byFold = <String, List<String>>{};
    try {
      for (final e in Directory(at(rel)).listSync(followLinks: false)) {
        final name = e.path.replaceAll(r'\', '/').split('/').last;
        byFold.putIfAbsent(name.toLowerCase(), () => []).add(name);
      }
    } on FileSystemException catch (e) {
      throw VcsStop(
        'vcs_error',
        'cannot list ${rel.isEmpty ? '.' : rel}: ${e.osError?.message ?? e.message}',
      );
    }
    return byFold;
  });

  void walk(String path, {required bool leafIsDir}) {
    final parts = _components(path);
    var rel = '';
    for (var i = 0; i < parts.length; i++) {
      final parent = rel;
      rel = rel.isEmpty ? parts[i] : '$rel/${parts[i]}';
      final leaf = i == parts.length - 1;
      final type = typeOf(rel);
      if (type == FileSystemEntityType.notFound) return;
      for (final name in namesIn(parent)[parts[i].toLowerCase()] ?? const []) {
        if (name != parts[i]) {
          throw _unsupportedEntry(
            '$rel is spelled $name on disk; the undo would write another '
            'spelling of the same path',
          );
        }
      }
      if (type == FileSystemEntityType.directory) {
        if (leaf && !leafIsDir) {
          throw _unsupportedEntry(
            '$rel is a directory where the undo needs a file',
          );
        }
        if (typeOf('$rel/.git') != FileSystemEntityType.notFound) {
          throw _unsupportedEntry(
            '$rel holds a .git entry, so it is a nested repository; an undo '
            'never writes inside one',
          );
        }
      } else if (type == FileSystemEntityType.file) {
        if (!leaf || leafIsDir) {
          throw _unsupportedEntry(
            '$rel is a file where the undo needs a directory'
            '${rel == path ? '' : ' (on the way to $path)'}',
          );
        }
      } else {
        throw _unsupportedEntry(
          '$rel is a link or a special file; the undo never writes through '
          'one${rel == path ? '' : ' (it is on the way to $path)'}',
        );
      }
    }
  }

  for (final path in files) {
    walk(path, leafIsDir: false);
  }
  for (final path in [...dirs, ...members]) {
    walk(path, leafIsDir: true);
  }
  for (final member in members) {
    _refuseDotGitBelow(at(member), _components(member).join('/'));
  }
}

/// Throws when an entry named like `.git` lies anywhere below [dir]; a link is
/// listed, never followed. [shown] is [dir] as the message names it.
void _refuseDotGitBelow(String dir, String shown) {
  if (FileSystemEntity.typeSync(dir, followLinks: false) !=
      FileSystemEntityType.directory) {
    return;
  }
  final List<FileSystemEntity> entries;
  try {
    entries = Directory(dir).listSync(followLinks: false);
  } on FileSystemException catch (e) {
    throw VcsStop(
      'vcs_error',
      'cannot list $shown: ${e.osError?.message ?? e.message}',
    );
  }
  for (final e in entries) {
    final name = e.path.replaceAll(r'\', '/').split('/').last;
    if (namesDotGit(name)) {
      throw _unsupportedEntry(
        '$shown/$name is a nested repository marker, and an undo moves the '
        'whole directory; move it out, then plan again',
      );
    }
    if (e is Directory) _refuseDotGitBelow(e.path, '$shown/$name');
  }
}

/// The directories [paths] lie in, each one's ancestors included (the path
/// itself too for each of [dirs]), shortest first: where a gitlink would stop
/// a write.
List<String> ancestorDirectories(
  Iterable<String> paths, [
  Iterable<String> dirs = const [],
]) {
  final out = <String>{};
  for (final path in paths) {
    final parts = _components(path);
    for (var n = 1; n < parts.length; n++) {
      out.add(parts.sublist(0, n).join('/'));
    }
  }
  for (final path in dirs) {
    final parts = _components(path);
    for (var n = 1; n <= parts.length; n++) {
      out.add(parts.sublist(0, n).join('/'));
    }
  }
  return out.toList()..sort();
}

/// Refuses, with `unsupported_entry`, an ancestor in [ancestors] that [tree]
/// records as a gitlink. `git ls-tree -z <tree> -- <ancestors>` is not
/// recursive, so it prints the entry of each ancestor itself; the lookups run
/// in batches that fit a command line.
Future<void> refuseGitlinkAncestors(
  GitRun run,
  String tree,
  List<String> ancestors,
) async {
  var batch = <String>[];
  var size = 0;
  Future<void> flush() async {
    if (batch.isEmpty) return;
    final r = await run(['ls-tree', '-z', tree, '--', ...batch]);
    for (final record in readInventory(r, 'git ls-tree')) {
      final text = decodeStrict(record.single, 'file name');
      final tab = text.indexOf('\t');
      if (text.startsWith('160000 ')) {
        throw _unsupportedEntry(
          '${tab < 0 ? text : text.substring(tab + 1)} is a submodule '
          '(a gitlink); an undo never writes inside a nested repository',
        );
      }
    }
    batch = [];
    size = 0;
  }

  for (final a in ancestors) {
    if (size + a.length + 1 > 6000) await flush();
    batch.add(a);
    size += a.length + 1;
  }
  await flush();
}
