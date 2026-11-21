import 'dart:convert';
import 'dart:io';

import 'package:path/path.dart' as p;

import '../commands/vcs.dart';
import '../entry/regular_file.dart';
import '../settings/rules.dart';
import '../vcs/args.dart';
import '../vcs/codec.dart';
import '../vcs/document.dart';
import '../vcs/git_backend.dart';
import '../vcs/stop.dart';
import '../vcs/tool_runner.dart';
import 'git_guard.dart';
import 'settings_guard.dart';

/// Answers the state read of a `check branch` step instead of the in-process
/// state operation, so that a test can check a jj or GitButler branch without
/// that tool. Tests only.
typedef UndoStateReader = Future<Map<String, Object?>> Function(
  String repo,
  String? code,
  String? branch,
);

VcsStop _usage(String message) => VcsStop('usage', message, code: 2);

VcsStop _failed(String message) => VcsStop('undo_step_failed', message);

/// `sw finish undo-step <kind> ...`: one primitive of an undo plan, run in
/// [cwd] (default: the current directory), which prints nothing and exits 0 on
/// success. A failure prints one stop document and exits 1 (a bad call, 2), so
/// the runner stops at the step.
///
/// C5: The undo primitives exist so a plan stays something the user runs step
/// by step; no command may run a whole undo. Only the kinds below exist (a new
/// kind needs a design change): `check` (`branch`, `tip`, `index`, `clean`,
/// `unchanged`, `absent`), `mkdir`, `copy`, `move`, `remove`, `rmdir-if-empty`, `write-blob`,
/// `write-text` and `merge-back`. A whole-undo command was rejected because it
/// would turn a plan the user reviews into an action the agent runs.
Future<int> runUndoStep(
  List<String> args, {
  required void Function(List<int> bytes) writeOut,
  String? cwd,
  UndoStateReader? stateReader,
  void Function(String line)? writeErr,
  Map<String, String>? environment,
}) async {
  // the old script's guards said why on stderr; the stop document goes to
  // stdout as every `sw` stop does
  final say = writeErr ?? stderr.writeln;
  try {
    await _UndoStep(
      cwd ?? Directory.current.path,
      stateReader,
      environment,
    ).run(args);
    return 0;
  } on VcsStop catch (stop) {
    writeOut(documentBytes(stop.object()));
    say(stop.message);
    return stop.code;
  } on NotUtf8 catch (e) {
    final stop = VcsStop.notUtf8(e);
    writeOut(documentBytes(stop.object()));
    say(stop.message);
    return stop.code;
  } on FileSystemException catch (e) {
    final stop = _failed('${e.message}: ${e.path ?? ''}'.trim());
    writeOut(documentBytes(stop.object()));
    say(stop.message);
    return 1;
  }
}

class _UndoStep {
  _UndoStep(this.cwd, this.stateReader, this.environment);

  final String cwd;
  final UndoStateReader? stateReader;

  /// The environment every started tool runs in; null is the parent's. Tests
  /// only: a printed step runs in the caller's environment.
  final Map<String, String>? environment;

  String at(String path) => p.isAbsolute(path) ? path : p.join(cwd, path);

  Map<String, String> get _env =>
      {...(environment ?? Platform.environment)}
        ..putIfAbsent('GIT_TERMINAL_PROMPT', () => '0');

  /// Runs [command] in [cwd]; every `git` carries [gitSafety] (literal
  /// pathspecs, no replace objects) after its name.
  Future<ToolResult> _spawn(List<String> command) => runTool(
    cwd,
    command.first == 'git'
        ? ['git', ...gitSafety, ...command.sublist(1)]
        : command,
    environment: _env,
  );

  Future<void> run(List<String> args) async {
    if (args.isEmpty) throw _usage('undo-step needs a kind');
    final kind = args.first;
    final rest = args.sublist(1);
    switch (kind) {
      case 'check':
        return check(rest);
      case 'mkdir':
        for (final d in rest) {
          Directory(at(d)).createSync(recursive: true);
        }
      case 'copy':
        _count(kind, rest, 2);
        // the source is a work-tree file: it is opened only when it is a
        // regular file (C38), so a FIFO in its place is refused, not waited on
        try {
          copyRegularFile(at(rest[0]), at(rest[1]));
        } on NotRegularFile catch (e) {
          throw notRegularStop(e);
        }
      case 'move':
        _count(kind, rest, 2);
        final from = at(rest[0]);
        if (FileSystemEntity.isDirectorySync(from)) {
          Directory(from).renameSync(at(rest[1]));
        } else {
          File(from).renameSync(at(rest[1]));
        }
      case 'remove':
        for (final f in rest) {
          if (FileSystemEntity.typeSync(at(f), followLinks: false) !=
              FileSystemEntityType.notFound) {
            File(at(f)).deleteSync();
          }
        }
      case 'rmdir-if-empty':
        for (final d in rest) {
          try {
            Directory(at(d)).deleteSync();
          } on FileSystemException {
            // never fails: the directory may be missing or still hold a file
          }
        }
      case 'write-blob':
        _count(kind, rest, 3);
        final r = await _spawn([
          'git',
          'cat-file',
          '--filters',
          '${rest[0]}:${rest[1]}',
        ]);
        if (r.exitCode != 0) {
          throw _failed(
            'cannot read ${rest[0]}:${rest[1]}: ${decodeText(r.stderr).trim()}',
          );
        }
        File(at(rest[2])).writeAsBytesSync(r.stdout);
      case 'write-text':
        _count(kind, rest, 2);
        File(at(rest[0])).writeAsBytesSync(utf8.encode('${rest[1]}\n'));
      case 'merge-back':
        _count(kind, rest, 3);
        final r = await _spawn([
          'git',
          'merge-file',
          '-L',
          'rerun',
          '-L',
          'archived',
          '-L',
          'amended',
          rest[0],
          rest[1],
          rest[2],
        ]);
        if (r.exitCode != 0) {
          throw _failed(
            'merging ${rest[2]} into ${rest[0]} stopped (exit ${r.exitCode}); '
            'conflict markers are in the file and both copies stay saved',
          );
        }
      default:
        throw _usage('unknown undo-step kind $kind');
    }
  }

  void _count(String kind, List<String> rest, int n) {
    if (rest.length != n) throw _usage('undo-step $kind takes $n arguments');
  }

  Future<void> check(List<String> args) async {
    if (args.isEmpty) throw _usage('undo-step check needs a kind');
    final positional = <String>[];
    final paths = <String>[];
    final options = <String, String>{};
    var jj = false;
    for (var i = 1; i < args.length; i++) {
      final a = args[i];
      if (a == '--') {
        paths.addAll(args.sublist(i + 1));
        break;
      } else if (a == '--jj') {
        jj = true;
      } else if (const [
            '--backend',
            '--code',
            '--message',
            '--git-dir',
            '--common-dir',
            '--index',
            '--objects',
          ].contains(a) &&
          i + 1 < args.length) {
        options[a] = args[++i];
      } else {
        positional.add(a);
      }
    }
    switch (args.first) {
      case 'branch':
        _count('check branch', positional, 1);
        return checkBranch(
          positional[0],
          options['--backend'] ?? 'git',
          options['--code'],
        );
      case 'tip':
        _count('check tip', positional, 2);
        final now = await _tipOf(positional[0]);
        if (now != positional[1]) {
          throw _failed(
            '${positional[0]} is at ${now.isEmpty ? '(nothing)' : now}, not '
            'at ${positional[1]} the plan was made for',
          );
        }
      case 'preflight':
        _count('check preflight', positional, 0);
        for (final name in const [
          '--git-dir',
          '--common-dir',
          '--index',
          '--objects',
        ]) {
          if (options[name] == null) {
            throw _usage('undo-step check preflight needs $name');
          }
        }
        await gitPreflight(
          (args) => _spawn(['git', ...args]),
          _env,
          cwd,
          recorded: GitView(
            top: cwd,
            gitDir: options['--git-dir']!,
            commonDir: options['--common-dir']!,
            index: options['--index']!,
            objects: options['--objects']!,
          ),
        );
      case 'index':
        await checkIndex();
      case 'clean':
        final r = jj
            ? await _spawn(['jj', 'diff', '-r', '@', '--name-only', ...paths])
            : await _spawn([
                'git',
                '-c',
                'core.fsmonitor=false',
                '--no-optional-locks',
                'status',
                '--porcelain',
                '--untracked-files=all',
                '--ignore-submodules=none',
                if (paths.isNotEmpty) '--',
                ...paths,
              ]);
        if (!jj) checkRead(r, 'git status');
        final dirty = decodeText(r.stdout).trim();
        if (r.exitCode != 0 || dirty.isNotEmpty) {
          throw _failed(
            'Not clean${paths.isEmpty ? '' : ' under ${paths.join(' ')}'}: $dirty',
          );
        }
        if (!jj) {
          // an assume-unchanged or skip-worktree edit is invisible to status
          final flagged = await firstFlaggedEntry(
            cwd: cwd,
            environment: _env,
            paths: paths,
          );
          if (flagged != null) {
            throw VcsStop(
              'git_env',
              '$flagged is flagged assume-unchanged or skip-worktree, so '
                  'Git does not report its edits; clear the flag, then plan '
                  'again',
            );
          }
        }
      case 'unchanged':
        _count('check unchanged', positional, 1);
        final r = await _spawn([
          'git',
          'diff-tree',
          '-r',
          '--quiet',
          positional[0],
          'HEAD',
          if (paths.isNotEmpty) '--',
          ...paths,
        ]);
        if (r.exitCode > 1 || r.stderr.isNotEmpty) {
          throw failedRead(
            'git diff-tree',
            exitCode: r.exitCode,
            stderr: r.stderr,
            streamError: r.streamError,
          );
        }
        if (r.exitCode != 0) {
          throw _failed(
            options['--message'] ??
                'HEAD differs from ${positional[0]} under ${paths.join(' ')}',
          );
        }
      case 'absent':
        _count('check absent', positional, 1);
        final path = positional[0];
        if (FileSystemEntity.typeSync(at(path), followLinks: false) !=
            FileSystemEntityType.notFound) {
          throw _failed(options['--message'] ?? '$path exists');
        }
      default:
        throw _usage('unknown undo-step check ${args.first}');
    }
  }

  /// `check index`.
  ///
  /// C19: every index-vs-HEAD check in the undo planner and its steps uses
  /// `git diff-index --cached` and the tree check `check unchanged` uses
  /// `git diff-tree` (plumbing, so no diff helper decides them); every Git
  /// command the planner runs or emits passes `--literal-pathspecs` and
  /// `--no-replace-objects` and names the archive parent by its planned OID;
  /// the planner and every Git guard refuse, with `git_env`, a true
  /// `GIT_GLOB_PATHSPECS`, `GIT_NOGLOB_PATHSPECS` or `GIT_ICASE_PATHSPECS`, a
  /// non-empty `GIT_NAMESPACE` or `GIT_ALTERNATE_OBJECT_DIRECTORIES`, and Git's
  /// effective paths differing from the planned view, which `check preflight`
  /// checks as the plan's first step; every index and cleanliness check passes
  /// `--ignore-submodules=none`, because the undo commit takes the whole index
  /// and the checkout must start from a clean tree. The checks are
  /// point-in-time: a `git add` or a hook that stages a path after `check
  /// index` and before the commit is not caught, and the plan warns that the
  /// index must not change while the steps run; no lock is added.
  ///
  /// C31: a Git undo never runs while a merge, cherry-pick, revert, rebase or
  /// sequencer is in progress (checked when planning, by the first guard when
  /// the steps run, before any checkout, and again by `check index`), and after
  /// a failed step it prints no recovery command: its warning names the paths
  /// whose index entries may be partly changed and the backup directory, and
  /// the user cleans up; `check index` keeps a partial index from being
  /// committed by a later undo. The operation check is point-in-time: an
  /// operation started after the last guard is not detected, and the plan's
  /// warning says not to start one while the steps run. Rejected: printing an
  /// executable recovery command, as the old interpolated `git restore
  /// --staged` warning did, or a path reset: a reset can follow
  /// `GIT_INDEX_FILE` into another index, and because the plan keeps no record
  /// of how far an attempt got, it cannot tell an attempt that changed the
  /// index from one a guard stopped before the first write, so the command
  /// could discard staging the user added afterwards.
  Future<void> checkIndex() async {
    final dir = await _spawn(['git', 'rev-parse', '--absolute-git-dir']);
    checkRead(dir, 'git rev-parse --absolute-git-dir');
    final operation = operationInProgress(
      decodeStrict(dir.stdout, 'git directory').trim(),
    );
    if (operation != null) throw operationStop(operation);
    final r = await _spawn([
      'git',
      'diff-index',
      '--cached',
      '--ignore-submodules=none',
      '--quiet',
      'HEAD',
      '--',
    ]);
    if (r.exitCode > 1 || r.stderr.isNotEmpty) {
      throw failedRead(
        'git diff-index --cached',
        exitCode: r.exitCode,
        stderr: r.stderr,
        streamError: r.streamError,
      );
    }
    if (r.exitCode != 0) {
      throw _failed('The index differs from HEAD; unstage or commit it');
    }
  }

  /// The tip a lookup finds: for `refs/heads/<name>` the exact ref in a
  /// `for-each-ref` listing, which no tag or abbreviation can stand in for;
  /// otherwise what `rev-parse` says. Empty when there is none.
  Future<String> _tipOf(String ref) async {
    if (ref.startsWith('refs/heads/')) {
      return branchTip((args) => _spawn(['git', ...args]), ref);
    }
    final r = await _spawn(['git', 'rev-parse', ref]);
    return r.exitCode == 0 ? decodeText(r.stdout).trim() : '';
  }

  /// The settings must select Git for the role [code] picks (the store role
  /// with a code operand, else the code role); another backend is `git_env`.
  void _requireGitRole(String? code) {
    final String chosen;
    try {
      final settings = loadSettings(
        readSettingsText([if (code != null) at(code), cwd]),
      );
      final choices = vcsChoices(settings);
      chosen = code != null ? choices.store : choices.code;
    } on SettingsStop catch (e) {
      throw VcsStop(e.error, e.message, code: e.code);
    }
    if (chosen != 'git') {
      throw VcsStop(
        'git_env',
        'The plan checks the branch with git, but the settings select '
            '$chosen for this role; plan again',
      );
    }
  }

  /// The backend's own branch value, read in process: git's current branch,
  /// jj's role branch, or the named GitButler branch when it is applied.
  Future<void> checkBranch(
    String expected,
    String backend,
    String? code,
  ) async {
    // the strict settings read of the guard (C38): a settings file that is no
    // regular file is refused before anything reads it
    requireRegularSettings([if (code != null) at(code), cwd]);
    final String now;
    if (backend == 'git') {
      _requireGitRole(code);
      final r = await _spawn(['git', 'branch', '--show-current']);
      checkRead(r, 'git branch --show-current');
      try {
        now = decodeStrict(r.stdout, 'branch name').trim();
      } on NotUtf8 catch (e) {
        throw VcsStop.notUtf8(e);
      }
    } else {
      final repo = cwd;
      final branch = backend == 'gitbutler' ? expected : null;
      final reader = stateReader;
      final Map<String, Object?> state;
      if (reader != null) {
        state = await reader(repo, code, branch);
      } else {
        final role = code != null
            ? ['--role', 'store', '--code', at(code)]
            : ['--role', 'code'];
        if (branch != null) role.addAll(['--branch', branch]);
        final parsed = parseVcsArguments(['state', '--repo', repo, ...role]);
        state = (await stateDocument(await openSession(VcsContext(parsed))))
            .cast();
      }
      now = '${state['branch'] ?? ''}';
    }
    if (now != expected) {
      throw _failed(
        'On branch ${now.isEmpty ? '(none)' : now}, but the plan is for '
        '$expected',
      );
    }
  }
}
