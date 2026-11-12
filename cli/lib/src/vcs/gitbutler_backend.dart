import 'dart:convert';
import 'dart:io';

import '../commands/vcs.dart';
import '../native/libc.dart' as libc;
import 'codec.dart';
import 'document.dart';
import 'git_backend.dart' show requireBranch;
import 'git_common.dart';
import 'scripts.dart';
import 'stop.dart';
import 'tool_runner.dart';

/// The GitButler backend of `vcs.sh` (`but_run` ... `run_gitbutler_operation`),
/// one method per Python function. Every stop keeps its error code, message,
/// field order and exit code.

/// `BUT_STATUS_CAP`: `but status --json` is read up to this many bytes.
const int butStatusCap = 16 * 1024 * 1024;

/// What every step reads from the code work tree.
const String settingsFile = 'openspec/specwright.yaml';

const String _autocrlfHint =
    'hint: core.autocrlf is true; GitButler checkouts can conflict on line '
    'endings';

/// `state` on the GitButler backend (`current_state` returns the GitButler
/// state as it is: no `head` or `branch_matches` is added).
Future<Map<String, Object?>> gitbutlerStateDocument(VcsSession s) =>
    GitButler(s).state();

/// `vcs.sh`'s `run_gitbutler_operation`. [windows] overrides the OS for the
/// commit's command-line size check, [argMax] replaces its `sysconf` read, [environment] is the full environment
/// `but` runs in (the parent's when null).
Future<Map<String, Object?>> runGitbutlerOperation(
  VcsSession s,
  String command, {
  bool? windows,
  Map<String, String>? environment,
  int? Function()? argMax,
}) => GitButler(
  s,
  windows: windows,
  environment: environment,
  argMax: argMax,
).operation(command);

/// Python truthiness of a decoded JSON value.
bool _truthy(Object? v) =>
    !(v == null ||
        v == false ||
        v == 0 ||
        v == '' ||
        (v is List && v.isEmpty) ||
        (v is Map && v.isEmpty));

/// `v or []`.
List<Object?> _list(Object? v) => v is List && v.isNotEmpty ? v : const [];

/// `v or {}`.
Map<String, Object?> _map(Object? v) =>
    v is Map && v.isNotEmpty ? v.cast<String, Object?>() : const {};

/// `str(v or "")`.
String _str(Object? v) => !_truthy(v) ? '' : (v is String ? v : '$v');

String _stripSlashes(String s) {
  var a = 0;
  var b = s.length;
  while (a < b && s[a] == '/') {
    a++;
  }
  while (b > a && s[b - 1] == '/') {
    b--;
  }
  return s.substring(a, b);
}

/// `posixpath.normpath`.
String _normpath(String path) {
  if (path.isEmpty) return '.';
  final rooted = path.startsWith('/');
  final parts = <String>[];
  for (final c in path.split('/')) {
    if (c.isEmpty || c == '.') continue;
    if (c != '..' || (!rooted && parts.isEmpty) || parts.lastOrNull == '..') {
      parts.add(c);
    } else if (parts.isNotEmpty) {
      parts.removeLast();
    }
  }
  final body = parts.join('/');
  if (rooted) return '/$body';
  return body.isEmpty ? '.' : body;
}

bool _pathCovers(String named, String changed) =>
    changed == named || (named.endsWith('/') && changed.startsWith(named));

final _globChars = RegExp(r'[*?\[\]{}]');
final _driveLetter = RegExp(r'^[A-Za-z]:');
final _hexCommit = RegExp(r'^[0-9a-fA-F]{7,40}$');
final _pushRejected = RegExp(r'\[rejected\]|non-fast-forward|fetch first');

/// The argument form `process_arguments` gives a Windows command line.
String _quoteArg(String arg) {
  var a = arg.replaceAllMapped(
    RegExp(r'(\\*)"'),
    (m) => '${'\\' * (2 * m[1]!.length + 1)}"',
  );
  a = a.replaceAllMapped(RegExp(r'(\\+)$'), (m) => m[1]! * 2);
  return '"$a"';
}

class GitButler {
  GitButler(this.s, {this.windows, this.environment, this.argMax});

  final VcsSession s;
  final bool? windows;
  final Map<String, String>? environment;

  /// Replaces the `sysconf(_SC_ARG_MAX)` read of the command-line size check.
  final int? Function()? argMax;

  String get root => s.info.repo;
  VcsScripts get scripts => s.scripts;

  Future<TextResult> _git(List<String> args) => git(scripts, root, args);

  /// `vcs.sh`'s `but_run`: stdout of `but <args>`; with [cap], once more than
  /// that many bytes were read the child is killed and the run stops.
  Future<String> butRun(List<String> args, {int? cap}) async {
    final r = await runToolCapped(
      root,
      ['but', ...args],
      cap: cap ?? 0x7fffffffffffffff,
      environment: environment,
    );
    if (r.outputTooLarge) {
      throw VcsStop(
        'but_output_too_large',
        'but ${args[0]} printed more than $cap bytes; nothing was changed',
      );
    }
    final out = decodeReplacing(r.stdout);
    if (r.exitCode != 0) {
      final stderr = decodeReplacing(r.stderr);
      final said = orElse(stderr, out).trim();
      var message = said.isNotEmpty ? said : 'but ${args.join(' ')} failed';
      if (args[0] != 'status' && args[0] != '--version') {
        message += await _autocrlf();
      }
      throw VcsStop('but_error', message);
    }
    return out;
  }

  /// `autocrlf_hint`: a failed `but` write in a repo whose effective
  /// core.autocrlf is true gets the line-ending hint.
  Future<String> _autocrlf() async {
    final found = await _git([
      'config',
      '--type=bool',
      '--get',
      'core.autocrlf',
    ]);
    return found.code == 0 && found.stdout.trim() == 'true'
        ? '\n$_autocrlfHint'
        : '';
  }

  /// `but_status`: `but status --json`, the only read of the workspace.
  Future<Map<String, Object?>> butStatus() async {
    final Object? status;
    try {
      status = decodeJson(
        await butRun(['status', '--json'], cap: butStatusCap),
      );
    } on FormatException {
      throw VcsStop('but_error', 'but status --json returned invalid JSON');
    }
    if (status is! Map) {
      throw VcsStop(
        'but_error',
        'but status --json returned an unexpected document',
      );
    }
    return status.cast<String, Object?>();
  }

  List<String> _stackNames(Object? stack) => [
    for (final b in _list(_map(stack)['branches'])) _str(_map(b)['name']),
  ];

  String _changeFile(Object? entry) {
    final e = _map(entry);
    final file = _str(e['filePath']);
    return pathText(file.isNotEmpty ? file : _str(e['path']));
  }

  String _target(Map<String, Object?> status) =>
      _str(_map(status['mergeBase'])['commitId']);

  Future<String> _tipOf(String name) async {
    final found = await _git([
      'rev-parse',
      '--verify',
      '-q',
      'refs/heads/$name^{commit}',
    ]);
    return found.code == 0 ? found.stdout.trim() : '';
  }

  /// `gitbutler_state`.
  Future<Map<String, Object?>> state() async {
    final branch = s.request.branch ?? '';
    final status = await butStatus();
    final stacks = _list(status['stacks']);
    final appliedBranches = [for (final stack in stacks) ..._stackNames(stack)];
    final applied = branch.isNotEmpty && appliedBranches.contains(branch);
    final target = _target(status);
    var tip = '';
    if (branch.isNotEmpty) tip = await _tipOf(branch);
    if (applied && tip.isNotEmpty) {
      await requireSettingsPinned(branch, status);
    }
    final owner = <String, int>{}; // path -> index of the stack that holds it
    for (var index = 0; index < stacks.length; index++) {
      for (final entry in _list(_map(stacks[index])['assignedChanges'])) {
        owner.putIfAbsent(_changeFile(entry), () => index);
      }
    }
    final uncommitted = [
      for (final entry in _list(status['uncommittedChanges']))
        _changeFile(entry),
    ];
    var touched = <String>{};
    if (tip.isNotEmpty && target.isNotEmpty) {
      final diff = await _git([
        'diff',
        '--name-only',
        '--no-renames',
        '-z',
        target,
        tip,
      ]);
      touched = {
        for (final name in diff.names('file name').split('\u0000'))
          if (name.isNotEmpty) pathText(name),
      };
    }
    var changeDir = '';
    if (branch.isNotEmpty) {
      final given = s.request.prefix;
      final prefix = _stripSlashes(
        (given != null && given.isNotEmpty ? given : 'openspec').replaceAll(
          r'\',
          '/',
        ),
      );
      final name = branch.contains('/')
          ? branch.substring(branch.indexOf('/') + 1)
          : branch;
      changeDir = '$prefix/changes/$name/';
    }
    final changePaths = <String>[];
    final unassignedPaths = <String>[];
    final otherPaths = <Map<String, Object?>>[];
    owner.forEach((path, index) {
      final names = _stackNames(stacks[index]);
      if (applied && names.contains(branch)) {
        changePaths.add(path);
      } else {
        otherPaths.add({
          'path': path,
          'branch': names.isNotEmpty ? names[0] : '',
        });
      }
    });
    for (final path in uncommitted) {
      if (owner.containsKey(path) ||
          unassignedPaths.contains(path) ||
          changePaths.contains(path)) {
        continue;
      }
      if (branch.isNotEmpty &&
          (path.startsWith(changeDir) || touched.contains(path))) {
        changePaths.add(path); // the change's own
      } else {
        unassignedPaths.add(path);
      }
    }
    final paths = <String>[];
    for (final path in [
      ...changePaths,
      ...unassignedPaths,
      for (final item in otherPaths) item['path']! as String,
    ]) {
      if (!paths.contains(path)) paths.add(path);
    }
    return {
      'ok': true,
      'backend': 'gitbutler',
      'main': s.info.main,
      'branch': applied ? branch : '',
      'on_main': !applied,
      'applied': applied,
      'head': tip,
      'target': target,
      'applied_branches': appliedBranches,
      'change_paths': changePaths,
      'unassigned_paths': unassignedPaths,
      'other_branch_paths': otherPaths,
      'clean': changePaths.isEmpty,
      'dirty_paths': paths,
      'dirty': [
        for (final path in paths) {'status': '', 'path': path},
      ],
      'behind': <Object?>[],
      'behind_truncated': false,
    };
  }

  /// `require_settings_pinned`: the settings every step reads from the shared
  /// work tree must be the change branch's own.
  Future<void> requireSettingsPinned(
    String branch, [
    Map<String, Object?>? known,
  ]) async {
    final status = known ?? await butStatus();
    for (final stack in _list(status['stacks'])) {
      final names = _stackNames(stack);
      if (names.contains(branch)) continue;
      if (_list(_map(stack)['assignedChanges'])
          .any((entry) => _changeFile(entry) == settingsFile)) {
        throw VcsStop(
          'settings_not_pinned',
          '$root holds an uncommitted edit of $settingsFile from branch '
              '${names.isNotEmpty ? names[0] : '?'}; Specwright reads it from '
              'the shared work tree, so unapply that branch or move the edit '
              'first',
        );
      }
    }
    final diff = await _git([
      'diff',
      '--quiet',
      'refs/heads/$branch',
      'HEAD',
      '--',
      settingsFile,
    ]);
    if (diff.code == 1) {
      throw VcsStop(
        'settings_not_pinned',
        'another applied branch changes $settingsFile, so the work tree\'s '
            'settings are not those of $branch; unapply that branch, or bring '
            'the change onto $branch, first',
      );
    }
    if (diff.code != 0) {
      throw VcsStop(
        'git_error',
        'git diff of $settingsFile failed: ${diff.stderr.trim()}',
      );
    }
  }

  /// `require_applied`: the status, or the `branch_not_applied` stop.
  Future<Map<String, Object?>> requireApplied(String branch) async {
    final status = await butStatus();
    final applied = [
      for (final stack in _list(status['stacks'])) ..._stackNames(stack),
    ];
    if (!applied.contains(branch)) {
      throw VcsStop(
        'branch_not_applied',
        'branch $branch is not applied in the GitButler workspace; Specwright '
            'never applies one (it can conflict with the other branches): '
            'apply it yourself, or choose another branch',
        extra: {'branch': branch},
      );
    }
    return status;
  }

  /// `gitbutler_branch_create`.
  Future<Map<String, Object?>> branchCreate() async {
    final branch = requireBranch(s);
    final exists = await _git([
      'show-ref',
      '--verify',
      '--quiet',
      'refs/heads/$branch',
    ]);
    if (exists.code == 0) {
      throw VcsStop(
        'branch_exists',
        'branch $branch already exists (applied or not): resume it, choose '
            'another name, or abort; nothing was changed',
        extra: {'branch': branch},
      );
    }
    await butRun(['branch', 'new', branch, '--json']);
    final status = await butStatus();
    final stack = _list(status['stacks'])
        .where((st) => _stackNames(st).contains(branch))
        .firstOrNull;
    final target = _target(status);
    final tip = await _tipOf(branch);
    final mine = [
      for (final b in _list(_map(stack)['branches']))
        if (_map(b)['name'] == branch) _map(b),
    ];
    if (stack == null ||
        tip.isEmpty ||
        tip != target ||
        (mine.isNotEmpty && _list(mine[0]['commits']).isNotEmpty)) {
      throw VcsStop(
        'branch_create_mismatch',
        'branch $branch was created but is not applied on the target with no '
            'commits (tip ${tip.isNotEmpty ? tip : '-'}, target '
            '${target.isNotEmpty ? target : '-'})',
      );
    }
    return {
      'ok': true,
      'backend': 'gitbutler',
      'branch': branch,
      'commit': tip,
      'applied': true,
    };
  }

  /// `gitbutler_path`: repo-relative, `/` separators, no `./`; a directory
  /// ends in `/`. Globs and escapes stop.
  String gitbutlerPath(String raw) {
    final text = raw.replaceAll(r'\', '/');
    if (_globChars.hasMatch(text)) {
      throw VcsStop(
        'bad_path',
        '$raw contains glob characters; name the file or its directory',
        extra: {'path': raw},
      );
    }
    final norm = _normpath(text);
    if (text.isEmpty ||
        norm == '.' ||
        norm.startsWith('/') ||
        norm == '..' ||
        norm.startsWith('../') ||
        _driveLetter.hasMatch(norm) ||
        norm.split('/').contains('.git')) {
      throw VcsStop(
        'bad_path',
        '$raw is not a path inside the repository',
        extra: {'path': raw},
      );
    }
    final isDir = text.endsWith('/') || _isDirectory('$root/$text');
    return isDir ? '$norm/' : norm;
  }

  bool _isDirectory(String path) {
    try {
      return Directory(path).existsSync();
    } on Object {
      return false;
    }
  }

  /// `jj_commit_argv_check`: the command-line size bound `commit` shares with
  /// Git and jj.
  Future<void> _argvCheck(List<String> filesets, String message) async {
    final argv = ['jj', 'commit', ...filesets, '-m', message];
    int size;
    int limit;
    if (windows ?? Platform.isWindows) {
      size = utf8.encode(argv.map(_quoteArg).join(' ')).length;
      limit = 32000;
    } else {
      final arg = (argMax ?? libc.argMax)();
      var env = 0;
      Platform.environment.forEach((k, v) {
        env += utf8.encode(k).length + utf8.encode(v).length + 2;
      });
      limit = arg == null ? 100000 : arg - env - 4096;
      size = 0;
      for (final a in argv) {
        size += utf8.encode(a).length + 1;
      }
    }
    if (size > limit) {
      throw VcsStop(
        'too_many_paths',
        'named paths and message exceed the command-line limit; name a '
            'containing directory instead',
      );
    }
  }

  /// `gitbutler_commit`: `but commit -b <branch> -F <file> --json <paths>` for
  /// the named paths only, then Git reads verify it.
  Future<Map<String, Object?>> commit() async {
    final branch = requireBranch(s);
    final messageFile = s.request.messageFile ?? '';
    final paths = s.request.paths;
    if (messageFile.isEmpty || paths.isEmpty) {
      throw VcsStop(
        'usage',
        'commit requires --message-file and at least one path after --',
        code: 2,
      );
    }
    final status = await requireApplied(branch);
    final named = <String>[];
    for (final raw in paths) {
      final path = gitbutlerPath(raw);
      if (!named.contains(path)) named.add(path);
    }
    final stacks = _list(status['stacks']);
    final own = [
      for (final st in stacks)
        if (_stackNames(st).contains(branch)) st,
    ];
    final others = [
      for (final st in stacks)
        if (!_stackNames(st).contains(branch)) st,
    ];
    for (final stack in others) {
      // a named path that covers another stack's change would move it silently
      for (final entry in _list(_map(stack)['assignedChanges'])) {
        final file = _changeFile(entry);
        for (final path in named) {
          if (_pathCovers(path, file)) {
            final names = _stackNames(stack);
            final who = names.isNotEmpty ? names[0] : '';
            throw VcsStop(
              'path_owned_elsewhere',
              '$file is assigned to branch $who, not $branch; nothing was '
                  'committed',
              extra: {'path': file, 'branch': who},
            );
          }
        }
      }
    }
    final changed = [
      for (final e in _list(status['uncommittedChanges'])) _changeFile(e),
      for (final st in own)
        for (final e in _list(_map(st)['assignedChanges'])) _changeFile(e),
    ];
    final given = [
      for (final p in named)
        if (changed.any((f) => _pathCovers(p, f))) p,
    ];
    if (given.isEmpty) {
      throw VcsStop(
        'nothing_to_commit',
        'no changes to commit in the named paths',
      );
    }
    await _argvCheck(given, messageFile);
    // Strict UTF-8, as vcs.sh read it: an invalid byte stops before `but commit`.
    final message = utf8.decode(File(messageFile).readAsBytesSync());
    final applied = [for (final st in stacks) ..._stackNames(st)];
    final before = <String, String>{
      for (final name in applied) name: await _tipOf(name),
    };
    await butRun([
      'commit',
      '-b',
      branch,
      '-F',
      messageFile,
      '--json',
      ...given,
    ]);
    final newTip = await _tipOf(branch);
    final old = before[branch]!;
    final problems = <String>[];
    final parent = newTip.isNotEmpty
        ? await _git(['rev-parse', '--verify', '-q', '$newTip^{commit}^'])
        : null;
    if (newTip.isEmpty ||
        parent == null ||
        parent.code != 0 ||
        parent.stdout.trim() != old) {
      problems.add("the new tip's parent is not the old tip");
    }
    var committed = <String>[];
    if (newTip.isNotEmpty) {
      final diff = await _git([
        'diff-tree',
        '--no-commit-id',
        '--name-only',
        '--no-renames',
        '-r',
        '-z',
        newTip,
      ]);
      committed = [
        for (final n in diff.names('file name').split('\u0000'))
          if (n.isNotEmpty) pathText(n),
      ]..sort();
    }
    final extra = [
      for (final f in committed)
        if (!named.any((p) => _pathCovers(p, f))) f,
    ];
    final missing = [
      for (final f in changed)
        if (named.any((p) => _pathCovers(p, f)) && !committed.contains(f)) f,
    ];
    if (extra.isNotEmpty) {
      problems.add(
        'it holds files outside the named paths: ${extra.join(', ')}',
      );
    }
    if (missing.isNotEmpty) {
      problems.add('it lacks named changes: ${missing.join(', ')}');
    }
    final body = newTip.isNotEmpty
        ? (await _git(['log', '-1', '--format=%B', 'refs/heads/$branch']))
              .stdout
        : '';
    if (_rstripNl(body) != _rstripNl(message)) {
      problems.add('its message differs from the message file');
    }
    final moved = <String>[];
    for (final name in applied) {
      if (name != branch && await _tipOf(name) != before[name]) {
        moved.add(name);
      }
    }
    if (moved.isNotEmpty) {
      problems.add("another branch's tip moved: ${moved.join(', ')}");
    }
    if (problems.isNotEmpty) {
      throw VcsStop(
        'commit_mismatch',
        'the GitButler commit on $branch is not what was asked: '
            '${problems.join('; ')}; the commit was left in place (tip '
            '${newTip.isNotEmpty ? newTip : '-'}, was $old); files taken: '
            '${committed.isNotEmpty ? committed.join(', ') : '-'}',
        extra: {'old_tip': old, 'new_tip': newTip, 'files': committed},
      );
    }
    return {
      'ok': true,
      'backend': 'gitbutler',
      'branch': branch,
      'commit': newTip,
      'files': committed,
    };
  }

  String _rstripNl(String t) {
    var end = t.length;
    while (end > 0 && t[end - 1] == '\n') {
      end--;
    }
    return t.substring(0, end);
  }

  String? _login() {
    final given = s.request.login;
    return given != null && given.isNotEmpty ? given : s.info.login;
  }

  /// `bash_command(root, "but", "pull", "--json")`: read as git and jj output
  /// is.
  Future<TextResult> _plainPull() async {
    final r = await runTool(root, [
      'but',
      'pull',
      '--json',
    ], environment: environment);
    return TextResult(r.exitCode, decodeText(r.stdout), decodeText(r.stderr));
  }

  /// `fenced_but_pull`: `as.sh <login> but pull --json` for a GitHub origin;
  /// plain `but pull --json` for any other remote.
  Future<String> fencedButPull(String? login) async {
    final github = isGithubUrl(await remoteUrl(scripts, root));
    final who = await fenceLogin(scripts, root, github: github, login: login);
    final result = github
        ? await runAs(scripts, root, who, ['but', 'pull', '--json'])
        : await _plainPull();
    if (result.code != 0) {
      final said = orElse(result.stderr, result.stdout).trim();
      final message = said.isNotEmpty ? said : 'but pull failed';
      if (github && result.code == 3 && message.startsWith('as.sh:')) {
        throw VcsStop('fence_failed', message, code: 3);
      }
      throw VcsStop(
        'but_error',
        '$message${await _autocrlf()}\nGitButler keeps its own undo '
            '(`but undo`); Specwright runs none',
      );
    }
    return result.stdout;
  }

  /// `linked_worktrees`: every worktree after the main one.
  Future<List<String>> linkedWorktrees() async {
    final listed = await _git(['worktree', 'list', '--porcelain']);
    if (listed.code != 0) {
      final said = orElse(listed.stderr, listed.stdout).trim();
      throw VcsStop(
        'git_error',
        said.isNotEmpty ? said : 'git worktree list failed',
      );
    }
    final paths = [
      for (final line in const LineSplitter().convert(listed.stdout))
        if (line.startsWith('worktree '))
          pathText(line.substring('worktree '.length)),
    ];
    return paths.skip(1).toList();
  }

  /// `gitbutler_pull`: `but pull` rebases every applied branch, so it runs
  /// only when the cleaned-up branch is alone and no linked worktree exists.
  Future<Map<String, Object?>> pull(String? login) async {
    final branch = requireBranch(s);
    final status = await butStatus();
    final others = [
      for (final stack in _list(status['stacks']))
        for (final name in _stackNames(stack))
          if (name != branch) name,
    ];
    final worktrees = await linkedWorktrees();
    if (others.isNotEmpty || worktrees.isNotEmpty) {
      return {
        'ok': true,
        'backend': 'gitbutler',
        'branch': branch,
        'pulled': false,
        'reason': 'pull_skipped',
        'applied_branches': others,
        'worktrees': worktrees,
      };
    }
    final out = await fencedButPull(login);
    final result = <String, Object?>{
      'ok': true,
      'backend': 'gitbutler',
      'branch': branch,
      'pulled': true,
    };
    try {
      final report = decodeJson(out);
      if (report is Map && _truthy(report['status'])) {
        result['status'] = report['status'];
      }
    } on FormatException {
      // not a report
    }
    final after = await butStatus();
    result['target'] = _target(after);
    result['applied_branches'] = [
      for (final stack in _list(after['stacks'])) ..._stackNames(stack),
    ];
    return result;
  }

  /// `gitbutler_push`: the fenced Git push of the branch's own ref; no force,
  /// no -u, no tags, never `but push` or `but pr`.
  Future<Map<String, Object?>> push(String? login) async {
    final branch = requireBranch(s);
    await requireApplied(branch);
    await requireSettingsPinned(branch);
    // the single comparison lives in the settings module; its stop passes through
    await requirePinnedSettings(scripts, s.request.code, branch);
    final refspec = 'refs/heads/$branch:refs/heads/$branch';
    try {
      await networkGit(scripts, root, [
        'push',
        '--no-follow-tags',
        'origin',
        refspec,
      ], login);
    } on VcsStop catch (stop) {
      if (stop.error == 'git_network_error' &&
          _pushRejected.hasMatch(stop.message)) {
        throw VcsStop(
          'push_rejected',
          'the remote rejected the push of $branch as non-fast-forward; '
              'Specwright never forces it: the user decides '
              '(${stop.message.replaceAll('\n', ' ').trim()})',
          extra: {'branch': branch},
        );
      }
      rethrow;
    }
    return {'ok': true, 'backend': 'gitbutler', 'branch': branch};
  }

  /// `jj_fetch_main`, as the GitButler backend uses it: a fenced
  /// `git fetch` of main, then the commit `FETCH_HEAD` names.
  Future<String> _fetchMain(String? login) async {
    await networkGit(scripts, root, [
      'fetch',
      if (s.request.quiet) '-q',
      if (s.request.noTags) '--no-tags',
      '--refmap=',
      'origin',
      'refs/heads/${s.info.main}',
    ], login);
    return (await gitChecked(scripts, root, [
      'rev-parse',
      '--verify',
      'FETCH_HEAD^{commit}',
    ], error: 'fetch_failed')).stdout.trim();
  }

  /// `gitbutler_delete`: delete only a merged branch whose merge the
  /// workspace base already holds; never a Git write.
  Future<Map<String, Object?>> delete(String? login) async {
    final branch = requireBranch(s);
    final mergedCommit = s.request.mergedCommit ?? '';
    if (mergedCommit.isNotEmpty && !_hexCommit.hasMatch(mergedCommit)) {
      throw VcsStop(
        'usage',
        '--merged-commit must be a commit id of 7 to 40 hex digits',
        code: 2,
      );
    }
    final found = await _git([
      'rev-parse',
      '--verify',
      '-q',
      'refs/heads/$branch^{commit}',
    ]);
    if (found.code != 0) {
      return {
        'ok': true,
        'backend': 'gitbutler',
        'branch': branch,
        'deleted': false,
        'reason': 'already_deleted',
      };
    }
    final tip = found.stdout.trim();
    final status = await requireApplied(branch);
    if (!s.request.force) {
      // no caller proved a merged PR: the tip must be in the fetched main
      final fetched = await _fetchMain(login);
      if (!await gitAncestor(scripts, root, tip, fetched)) {
        throw VcsStop(
          'not_merged',
          'branch $branch is not merged into the fetched ${s.info.main}; '
              'nothing was deleted',
          extra: {'branch': branch},
        );
      }
    }
    final base = _target(status);
    final proofs = [tip];
    if (mergedCommit.isNotEmpty) {
      final resolved = await _git([
        'rev-parse',
        '--verify',
        '-q',
        '$mergedCommit^{commit}',
      ]);
      if (resolved.code == 0) proofs.add(resolved.stdout.trim());
    }
    var held = false;
    if (base.isNotEmpty) {
      for (final proof in proofs) {
        if (await gitAncestor(scripts, root, proof, base)) {
          held = true;
          break;
        }
      }
    }
    if (!held) {
      return {
        'ok': true,
        'backend': 'gitbutler',
        'branch': branch,
        'deleted': false,
        'reason': 'left_applied',
        'base': base,
        'message':
            'branch $branch stays applied: the workspace base '
            '${base.isNotEmpty ? base : '(unknown)'} does not hold its merge '
            "yet; the user's next `but pull` removes it",
      };
    }
    await butRun(['branch', 'delete', branch, '--json']);
    return {
      'ok': true,
      'backend': 'gitbutler',
      'branch': branch,
      'deleted': true,
    };
  }

  /// `run_gitbutler_operation`.
  Future<Map<String, Object?>> operation(String command) async {
    switch (command) {
      case 'branch-create':
        return branchCreate();
      case 'switch':
        final branch = requireBranch(s);
        // the workspace is always based on main: only another branch needs
        // to be applied
        if (branch != s.info.main) await requireApplied(branch);
        return {
          'ok': true,
          'backend': 'gitbutler',
          'branch': branch,
          'switched': false,
        };
      case 'commit':
        return commit();
      case 'push':
        return push(_login());
      case 'pull':
        return pull(_login());
      case 'fetch-main':
        final sha = await _fetchMain(_login());
        return {'ok': true, 'backend': 'gitbutler', 'ref': sha, 'commit': sha};
      case 'delete-branch':
        return delete(_login());
      case 'merge' || 'advance':
        throw VcsStop(
          'unsupported_combination',
          '$command has no GitButler meaning: vcs: gitbutler runs only with '
              'finish: pr, where the PR merges on GitHub',
        );
    }
    throw VcsStop(
      'unsupported',
      'the GitButler backend does not implement $command yet',
    );
  }
}
