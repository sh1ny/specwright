import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:path/path.dart' as pth;

import '../commands/vcs.dart';
import '../commands/version.dart' show buildVersion;
import '../commit/task_cover.dart' show isPySpace, pyStrip;
import '../entry/project_version.dart';
import '../entry/regular_file.dart';
import '../fs/walk.dart';
import '../process/command_line.dart' show commandLineUnits;
import '../vcs/args.dart';
import '../vcs/codec.dart';
import '../vcs/git_backend.dart';
import '../vcs/stop.dart';
import '../vcs/tool_runner.dart';
import 'git_guard.dart';
import 'script_text.dart';
import 'settings_guard.dart';

/// What `sw finish undo-archive-plan` was asked, as `finish.sh` parsed it:
/// [dir] is the planning repo (`--dir`, the current directory when absent or
/// empty); every other field is the option's last value, null when not given.
class UndoRequest {
  UndoRequest({
    required this.dir,
    this.change,
    this.archived,
    this.prefix,
    this.main,
    this.branch,
    this.type,
    this.code,
    this.project,
  });

  final String dir;
  final String? change;

  /// `--archived-name`.
  final String? archived;
  final String? prefix;
  final String? main;
  final String? branch;
  final String? type;
  final String? code;

  /// The call's leading `--project`, which chooses only the `VERSION` checked;
  /// null when the call gave none.
  final String? project;
}

/// What a planner runs with: the environment and the test seams.
class FinishContext {
  FinishContext({
    this.environment,
    this.windows,
    this.stateReader,
    this.sw,
    this.runner,
    this.lineLimit,
  });

  /// The most command-line units one printed step may take (null: the
  /// launcher's own limit for the host). Tests only.
  final int? lineLimit;

  /// The `sw` the printed steps start; null is the running binary. Tests only.
  final String? sw;

  /// The environment `git` runs with; null is the parent's. Tests
  /// put stubs first on `PATH`.
  final Map<String, String>? environment;

  /// Treat the host as Windows (null: this OS). Tests only.
  final bool? windows;

  /// Answers the state read (the document `vcs.sh state` prints) instead of
  /// the in-process state operation, so that a test can plan for a jj or
  /// GitButler backend without that tool. Tests only.
  final Future<Map<String, Object?>> Function(
    String top,
    String? code,
    String? branch,
  )?
  stateReader;

  /// Runs every `git` the planner starts itself (not the state read) instead of
  /// the process launcher, so that a test answers one read and passes the rest
  /// through. Tests only.
  final Future<ToolResult> Function(
    String cwd,
    List<String> command,
    Map<String, String> environment,
  )?
  runner;
}

/// Builds the undo plan: returns the document to print (exit 0) or throws a
/// [VcsStop] (its own exit code).
typedef UndoPlanner = Future<Map<String, Object?>> Function(
  UndoRequest request,
  FinishContext ctx,
);

/// `undo-archive-plan` of `finish.sh`: the plan to undo the archive of a
/// change, as one document (the caller prints it and exits 0) or a [VcsStop].
/// It only reads the repository; the scripts it prints are for the user to run.
///
/// #232's non-resumable undo after a failed archive stays open by decision, for
/// the same reason as the gate-unlock race (`gateUnlock`): each fix found so far
/// adds a race of its own.
///
/// C2: `sw finish` runs `git` with no deadline and no byte bound, as `finish.sh` did
/// (ADR 0012 exception, #111). Adding bounds is a behaviour change for its own
/// change.
///
/// C4: Line-anchored patterns anchor at `\n` only, `sorted()` order is by code
/// point, the walk is `os.walk`'s top-down order with names that keep their
/// original bytes from listing through reads to output (never `Directory.list()`),
/// and filesystem checks follow links. A Dart default changes members, waiting
/// tasks or printed lines.
///
/// C8: GitButler parity of the undo plan is checked only on Linux, because `but`
/// has no standalone build for macOS and Windows (#154).
///
/// C3: the printed `steps` and `after_rerun_steps` are `{cwd, argv}` objects (D7):
/// Specwright's own work starts with the running `sw` and `--project`, never a
/// script or `bash`. C1: ids and date prefixes match ASCII digits only.
///
/// C10: the planner is read-only, so every `git status` it causes, its own
/// reads and the one inside the `vcsState` read, runs with `GIT_OPTIONAL_LOCKS=0`
/// and `-c core.fsmonitor=false`; it never rewrites the index. The option reaches
/// the state read through a planner-only context option, so standalone
/// `sw vcs state` is unchanged. That read drains and discards the status output
/// without decoding it and checks only the result, so a failed status is still
/// `git_error`. The planner decodes strictly only the records it uses, so an
/// unrelated non-UTF-8 name never stops a plan. The `rev-parse` and `config`
/// calls keep the caller's environment.
///
/// ADR 0043: the CLI skips its entry check for this subcommand, so the version
/// check runs once, here, after option validation and before any Git read, on
/// the existing, anchored code checkout the plan uses; every emitted step
/// carries that root as its `--project`.
///
/// C36: a resume plan does not prove that the project's `VERSION` stamp survives
/// its own checkout. It refuses early only a tip stamp that is a regular blob of
/// another version, or one the checkout would delete; any other change (links,
/// case aliases, conversions, size) is caught by the next `sw` step's entry
/// check, which refuses a non-regular stamp without opening it and stops after
/// only the branch switch and before any backup or undo write, as the
/// post-checkout `check branch` stop does. The early check reads the tip blob
/// only when `git cat-file -s` reports at most 4,096 bytes. After such a stop
/// the warning tells the user to check Git's effective work tree and index
/// before switching back, never to switch blindly. Rejected: proving survival
/// from tree and disk shapes, which four review rounds each found another case
/// for.
///
/// C28: `check clean` is emitted only for a committed archive (on Git when the
/// plan switches branches); an uncommitted undo gets none, because it moves the
/// archive copy with its edits and backs up amended main specs, and a
/// cleanliness guard would block that recovery.
///
/// C44: the archive-branch tip lookup treats a successful `for-each-ref`
/// listing without the exact ref as a missing branch, and `for-each-ref` leaves
/// out a broken ref, so a `refs/heads/<branch>` that exists as a symbolic ref to
/// a deleted target reports `no_archive` rather than `vcs_error`. Such a ref is
/// made only by hand (`git symbolic-ref`); no Specwright or Git workflow
/// creates one, and telling it apart needs a second read for one case.
///
/// C45: an undo resume scans the whole index for assume-unchanged and
/// skip-worktree entries, at planning and in the emitted `check clean`; a plan
/// that does not switch branches scans only the member directories and touched
/// main specs. The scan reads `ls-files -v -z` incrementally, one NUL record at
/// a time, keeps no path list, and stops at the first flagged entry, naming it
/// in its message; it never collects the whole output through the uncapped
/// runner (`runTool`).
///
/// C39: a resume refuses a decision file with any explicit `filter` or
/// `working-tree-encoding` assignment on the tip or `HEAD`, an unset
/// (`-filter`) included, though an unset applies no conversion: `git
/// check-attr --all` prints an unset as `unset`, the same as the literal value
/// `filter=unset`, so the two cannot be told apart without parsing attribute
/// files. Rejected: allowing the rendered value `unset`.
///
/// C41: the resume refusals for a non-regular or attribute-converted
/// `review.md` or `tasks.md` (`unsupported_filter`), and the Git 2.40 floor
/// they need, apply to Git resumes only; a jj resume keeps today's behaviour,
/// reading the stored blob, so a stored symlink is read as its link text.
///
/// C32: a marker the undo removes is either copied to the backup directory,
/// when the steps' guards pass, or left untouched, when a guard refuses; the
/// copy is made after any checkout and guards and before the undo's first index
/// change or removal (a resume's checkout writes the index first); it is never
/// deleted without a copy; a marker already absent when the steps run is
/// skipped (`copy --if-present`).
///
/// C51: the nested-repository refusal covers C46's whole destination inventory
/// and the moved member subtrees, whichever executable writes them (`sw` steps,
/// `git restore`, `git rm`, `jj restore`, the rerun's `openspec archive`); only
/// the resume branch switch is excluded, and with it every path that switch
/// alone changes. The backup and message files the steps write under the Git
/// directory (`<git-dir>/specwright-undo/<archived-name>`) are Specwright's own
/// state outside the work tree and are not checked for markers; a `.git` entry
/// planted inside the Git directory needs local write access there, which is
/// outside this change's threat model. The emitted checkout is a plain branch
/// switch with `--no-overwrite-ignore` and `--no-recurse-submodules`, and it
/// writes what any `git switch` to that branch would write; a repository the
/// user initialized by hand over files the outer repository also tracks (not a
/// gitlink) is the user's own layout, and Git's checkout treats those files as
/// the outer repository's. Rejected: diffing the whole branch switch and
/// walking every changed path's ancestors for `.git` markers before checkout,
/// which adds a tree-wide scan to every resume for a layout Git itself does not
/// support as nested.
Future<Map<String, Object?>> undoArchivePlan(
  UndoRequest request,
  FinishContext ctx,
) async {
  try {
    return await _Planner(request, ctx).run();
  } on NotUtf8 catch (e) {
    // a name from a tool listing (`ls-files -z`, `status -z`) that is not UTF-8
    throw VcsStop.notUtf8(e);
  }
}

VcsStop _usage(String message) => VcsStop('usage', message, code: 2);

String _joinAll(List<String> parts) =>
    parts.where((p) => p.isNotEmpty).join('/');

/// `os.path.join(top, path)` for a relative [path].
String _under(String top, String path) =>
    top.endsWith('/') ? '$top$path' : '$top/$path';

bool _isDir(String path) => Directory(path).existsSync();

bool _isFile(String path) => File(path).existsSync();

bool _exists(String path) => _isFile(path) || _isDir(path);

/// The tree under [rel] (relative to [top]) with the finish link policy: a link
/// to a directory is listed under `dirs` and not entered, any other link under
/// `files`. A name that is not UTF-8 stops the plan with `not_utf8`.
List<WalkDirectory> _walkArchive(String top, String rel) {
  try {
    return walkTree(
      _under(top, rel),
      policy: WalkPolicy.finish,
      prefix: rel,
      strictListing: true,
    );
  } on NotUtf8 catch (e) {
    throw VcsStop.notUtf8(e);
  } on FileSystemException catch (e) {
    throw VcsStop(
      'vcs_error',
      'cannot list ${e.path ?? rel}: ${e.osError?.message ?? e.message}',
    );
  }
}

/// A work-tree file's bytes, or null when it is not there or cannot be read
/// (`wd_bytes`). It goes through [readRegularFile] (C38), so a target that is
/// not a regular file, such as a FIFO a branch or a link put in its place, is
/// a `vcs_error` naming the path and is never opened.
Uint8List? _readFile(String path) {
  try {
    return readRegularFile(path);
  } on NotRegularFile catch (e) {
    throw notRegularStop(e);
  } on FileSystemException {
    return null;
  }
}

/// The planner.
///
/// C34: the planner never asks Git for a filtered read it did not make before
/// this change, and runs no filter to decide a rerun; Git itself may still run
/// a clean filter the user configured inside the planner's `git status` reads
/// (a tracked file with stale stat data), and the current-branch amended-spec
/// comparison keeps today's `cat-file --filters`, as any `git status` or `git
/// diff` the user runs does. The read-only contract is about the index and work
/// tree, which `GIT_OPTIONAL_LOCKS=0` keeps unwritten; a user's own filter
/// driver is their code. The planner uses no conversion to obtain rerun
/// evidence: the existing filtered comparisons, the amended-spec one and the
/// uncommitted carried-edits one, keep today's `cat-file --filters` and are not
/// rerun evidence. Rejected: refusing every repository with a filter driver
/// configured, which would refuse every Git LFS user.
class _Planner {
  _Planner(this.request, this.ctx)
    : windows = ctx.windows ?? Platform.isWindows,
      env = {...(ctx.environment ?? Platform.environment)}
        ..putIfAbsent('GIT_TERMINAL_PROMPT', () => '0');

  final UndoRequest request;
  final FinishContext ctx;
  final bool windows;
  final Map<String, String> env;

  Future<ToolResult> git(
    String cwd,
    List<String> args, {
    Map<String, String>? environment,
    List<int>? input,
  }) async {
    try {
      final run = ctx.runner;
      final command = ['git', ...gitSafety, ...args];
      final callEnv = environment ?? env;
      return run != null
          ? await run(cwd, command, callEnv)
          : await runTool(cwd, command, input: input, environment: callEnv);
    } on Unrepresentable catch (e) {
      throw VcsStop.unrepresentable(e);
    }
  }

  /// The planner's own `git status` (C10): read-only, with
  /// `GIT_OPTIONAL_LOCKS=0`, `--no-optional-locks` and `-c core.fsmonitor=false`
  /// so the plan never rewrites the index or starts a monitor, and every
  /// untracked file listed whatever `status.showUntrackedFiles` says, in `-z`
  /// records that [readPorcelain] reads whole. [paths] limits the read.
  Future<ToolResult> gitStatus(String top, [List<String> paths = const []]) =>
      git(
        top,
        [
          '-c',
          'core.fsmonitor=false',
          '--no-optional-locks',
          'status',
          '--porcelain=v1',
          '-z',
          '--untracked-files=all',
          '--ignore-submodules=none',
          if (paths.isNotEmpty) '--',
          ...paths,
        ],
        environment: {...env, 'GIT_OPTIONAL_LOCKS': '0'},
      );

  String textOf(ToolResult r) => pyStrip(decodeReplacing(r.stdout));

  /// A path the tool printed (D4): decoded strictly, so one that is not UTF-8
  /// is [NotUtf8] naming [what], not a look-alike.
  String pathOf(ToolResult r, String what) =>
      pyStrip(decodeStrict(r.stdout, what));

  /// The NUL-ended names of a finished read; the read must be whole ([label]
  /// names it when it is not).
  List<String> nulList(ToolResult r, String label) {
    checkRead(r, label);
    final out = <String>[];
    var start = 0;
    final bytes = r.stdout;
    for (var i = 0; i <= bytes.length; i++) {
      if (i == bytes.length || bytes[i] == 0) {
        if (i > start) {
          out.add(decodeStrict(bytes.sublist(start, i), 'file name'));
        }
        start = i + 1;
      }
    }
    return out;
  }

  /// `--code` as a path the state read can use: a relative one is joined to
  /// [top], the directory `finish.sh` ran `vcs.sh` in (D2).
  String codeFor(String top, String code) {
    final absolute =
        code.startsWith('/') ||
        (windows &&
            (code.startsWith(r'\') || RegExp(r'^[A-Za-z]:').hasMatch(code)));
    return absolute ? code : _under(top, code);
  }

  /// `vcs_state`: the branch and working-copy changes, read through the state
  /// operation of `vcs.sh` (in-process, D2).
  Future<Map<String, Object?>> vcsState(
    String top,
    String? code,
    String? branch,
  ) async {
    final role = code != null && code.isNotEmpty
        ? ['--role', 'store', '--code', codeFor(top, code)]
        : ['--role', 'code'];
    if (branch != null && branch.isNotEmpty) role.addAll(['--branch', branch]);
    try {
      // the strict settings read: a settings file that is no regular file is
      // refused before the shared reader can open it
      requireRegularSettings([
        if (code != null && code.isNotEmpty) codeFor(top, code),
        top,
      ]);
      final reader = ctx.stateReader;
      if (reader != null) {
        return (await reader(top, code, branch)).cast();
      }
      final parsed = parseVcsArguments(['state', '--repo', top, ...role]);
      final session = await openSession(
        VcsContext(parsed, readOnlyStatus: true),
      );
      return (await stateDocument(session)).cast();
    } on VcsStop catch (stop) {
      throw VcsStop(
        stop.error.isEmpty ? 'vcs_error' : stop.error,
        stop.message.isEmpty ? 'vcs.sh state failed' : stop.message,
        // only a usage error exits 2; `bad_setting` and every other stop is 1
        code: stop.error == 'usage' ? 2 : 1,
      );
    }
  }

  /// Stops with `tool_too_old` unless `git` is 2.40 or later: a Git resume reads
  /// the attributes of the archive branch's tree with `git check-attr
  /// --source`, which older versions lack. Only a plan that resumes asks.
  Future<void> requireAttrSource(String top) async {
    final r = await git(top, ['version']);
    checkRead(r, 'git version');
    final text = textOf(r);
    final found = RegExp(r'(\d+)\.(\d+)(?:\.(\d+))?').firstMatch(text);
    if (found == null) {
      throw VcsStop('vcs_error', 'git version printed no version: $text');
    }
    final major = int.parse(found[1]!);
    final minor = int.parse(found[2]!);
    if (major < 2 || (major == 2 && minor < 40)) {
      throw VcsStop(
        'tool_too_old',
        'git check-attr --source needs Git 2.40 or later to read the '
            'archive branch\'s attributes, and this is Git ${found[0]}; '
            'update Git, then plan again',
      );
    }
  }

  /// The early `sw_mismatch` of a resume (C36). When `openspec/.specwright/
  /// VERSION` is a regular blob at [tip] that is over the reader's limit or
  /// whose raw bytes are not the running version, or it is tracked at [head]
  /// and absent at [tip], the plan stops before it prints a script. Any other
  /// shape is left to the next step's own check. The blob is read only when
  /// `git cat-file -s` says it fits the reader's limit.
  Future<void> refuseTipStamp(String top, String head, String tip) async {
    const path = 'openspec/.specwright/VERSION';
    Never mismatch({String? found, String? problem}) {
      final doc = mismatchDocument(
        found: found,
        problem: problem,
        environment: ctx.environment,
      );
      throw VcsStop('sw_mismatch', doc['message']! as String);
    }

    Future<String?> entry(String rev) async {
      final r = await git(top, ['ls-tree', '-z', rev, '--', path]);
      if (r.exitCode != 0) {
        throw VcsStop('vcs_error', 'cannot list $path at $rev');
      }
      final text = decodeStrict(r.stdout, 'file name');
      final end = text.indexOf(String.fromCharCode(0));
      return end <= 0 ? null : text.substring(0, end);
    }

    final listed = await entry(tip);
    if (listed == null) {
      if (await entry(head) != null) {
        mismatch(problem: '$path is absent on the archive branch');
      }
      return;
    }
    final tab = listed.indexOf(String.fromCharCode(9));
    final fields = (tab < 0 ? listed : listed.substring(0, tab)).split(' ');
    // only a regular blob (mode 100644 or 100755); a link or other shape is the
    // step's to refuse
    if (fields.length != 3 ||
        fields[1] != 'blob' ||
        !fields[0].startsWith('100')) {
      return;
    }
    final oid = fields[2];
    final size = await git(top, ['cat-file', '-s', oid]);
    final bytes = int.tryParse(textOf(size));
    if (size.exitCode != 0 || bytes == null) {
      throw VcsStop('vcs_error', 'cannot read the size of $path at $tip');
    }
    if (bytes > maxVersionBytes) {
      mismatch(
        problem: '$path on the archive branch is over $maxVersionBytes bytes',
      );
    }
    final blob = await git(top, ['cat-file', 'blob', oid]);
    if (blob.exitCode != 0) {
      throw VcsStop('vcs_error', 'cannot read $path at $tip');
    }
    String text;
    try {
      text = const Utf8Decoder(allowMalformed: false)
          .convert(blob.stdout)
          .trim();
    } on FormatException {
      text = '';
    }
    if (!isVersionText(text)) {
      mismatch(problem: '$path on the archive branch is not a version');
    }
    if (text != buildVersion) mismatch(found: text);
  }

  Future<Map<String, Object?>> run() async {
    if (request.change == null) {
      throw _usage('undo-archive-plan needs --change');
    }
    if (request.archived == null) {
      throw _usage('undo-archive-plan needs --archived-name');
    }
    if (request.prefix == null) {
      throw _usage('undo-archive-plan needs --prefix');
    }
    if (request.main == null) throw _usage('undo-archive-plan needs --main');
    final change = request.change!;
    final archived = request.archived!;
    final main = request.main!;
    final d = request.dir;
    var prefix = request.prefix!.replaceAll(RegExp(r'^/+|/+$'), '');
    if (prefix == '.') prefix = '';

    // ADR 0043, in this order: the planning directory exists (no version
    // check for one that does not), `--code` is anchored at the planning root
    // and names a directory, then the one version check, before any Git read.
    if (!_isDir(d)) {
      throw VcsStop('not_a_repo', '$d is not inside a git work tree');
    }
    final code = request.code;
    String? codeDir;
    if (code != null) {
      codeDir = code.isEmpty ? '' : codeFor(projectRoot(d), code);
      if (codeDir.isEmpty || !_isDir(codeDir)) {
        throw VcsStop(
          'not_repository',
          '--repo and --code must name existing directories',
        );
      }
    }
    final checkedRoot = projectRoot(request.project ?? codeDir ?? d);
    final mismatch = versionMismatch(checkedRoot, environment: ctx.environment);
    if (mismatch != null) {
      throw VcsStop('sw_mismatch', mismatch['message']! as String);
    }

    refuseGitEnvironment(env);
    var r = await git(d, ['rev-parse', '--show-toplevel']);
    if (r.exitCode != 0 || textOf(r).isEmpty) {
      throw VcsStop('not_a_repo', '$d is not inside a git work tree');
    }
    final top = pathOf(r, 'repository path');
    final gitdir = pathOf(
      await git(top, ['rev-parse', '--absolute-git-dir']),
      'git directory',
    );
    // Git itself writes a hint about a grafts file, which a later read would
    // report as its own failure: say what is wrong first
    refuseGrafts(derivedView(top)?.commonDir ?? gitdir);
    r = await git(top, ['rev-parse', '--verify', '-q', 'HEAD^{commit}']);
    if (r.exitCode != 0) {
      throw VcsStop('not_a_repo', 'the repository has no commit');
    }
    var head = textOf(r);
    final vs = await vcsState(top, code, request.branch);
    final jj = vs['backend'] == 'jj';
    final gb = vs['backend'] == 'gitbutler';
    // a Git undo's first guard, run now as the first step runs it later
    final GitView? view = jj || gb
        ? null
        : await gitPreflight((args) => git(top, args), env, top);
    var headref = 'HEAD';
    final given = request.branch != null && request.branch!.isNotEmpty
        ? request.branch
        : null;
    if (gb) {
      // HEAD is the workspace commit: the head every guard checks is the
      // branch's tip
      if (given == null) {
        throw _usage(
          '--branch is required on GitButler: HEAD is the workspace commit, '
          'not the change branch',
        );
      }
      if (!_truthy(vs['applied'])) {
        throw VcsStop(
          'branch_not_applied',
          '$given is not applied in the GitButler workspace; Specwright never '
              'applies one (it can conflict with the other branches): apply it '
              'yourself, then plan again',
          extra: {'branch': given},
        );
      }
      headref = 'refs/heads/$given';
      r = await git(top, ['rev-parse', '--verify', '-q', '$headref^{commit}']);
      if (r.exitCode != 0) {
        throw VcsStop('bad_ref', '$given is not a local branch');
      }
      head = textOf(r);
    }
    final cb = vs['branch']! as String;
    final branch = given ?? cb;
    if (branch.isEmpty) throw _usage('--branch is required on a detached HEAD');
    r = await git(top, ['rev-parse', '--verify', '-q', '$main^{commit}']);
    if (r.exitCode != 0) throw VcsStop('bad_ref', '$main is not a commit');

    final chg = _joinAll([prefix, 'changes']);
    final archiveBase = _joinAll([prefix, 'changes', 'archive']);
    final ad = _joinAll([archiveBase, archived]);
    final adInWd = _isDir(_under(top, ad));
    final listed = await git(top, [
      'ls-tree',
      '-r',
      '--name-only',
      head,
      '--',
      ad,
    ]);
    checkRead(listed, 'git ls-tree');
    final adInHead = listed.stdout.any((b) => !_asciiSpace(b));
    final uncommitted = adInWd && !adInHead;
    final typ = request.type != null && request.type!.isNotEmpty
        ? request.type!
        : _typeOf(branch);
    final backupDir = '$gitdir/specwright-undo/$archived';

    // `<mode> <type> <oid>` of [path] in [tree], or null when it is not there;
    // a failed listing is a `vcs_error`, never a missing entry
    // Lookups are cached, and a bulk archive's paths are primed in a few
    // batched listings, so the plan starts a number of Git processes that does
    // not grow with the number of specs
    final entryCache = <String, List<String>?>{};
    Future<List<String>?> entry(String tree, String path) async {
      final key = '$tree\u0000$path';
      if (entryCache.containsKey(key)) return entryCache[key];
      final r = await git(top, ['ls-tree', '-z', tree, '--', path]);
      final records = readInventory(r, 'git ls-tree');
      List<String>? found;
      if (records.isNotEmpty) {
        final text = decodeStrict(records.first.single, 'file name');
        final tab = text.indexOf('\t');
        final fields = (tab < 0 ? text : text.substring(0, tab)).split(' ');
        found = fields.length == 3 ? fields : null;
      }
      return entryCache[key] = found;
    }

    // `entry` for every one of [paths] in [tree], in listings that fit a
    // command line
    Future<void> prime(String tree, Iterable<String> paths) async {
      var chunk = <String>[];
      var size = 0;
      Future<void> flush() async {
        if (chunk.isEmpty) return;
        final r = await git(top, ['ls-tree', '-z', tree, '--', ...chunk]);
        final found = <String, List<String>>{};
        for (final record in readInventory(r, 'git ls-tree')) {
          final text = decodeStrict(record.single, 'file name');
          final tab = text.indexOf('\t');
          if (tab < 0) continue;
          final fields = text.substring(0, tab).split(' ');
          if (fields.length == 3) found[text.substring(tab + 1)] = fields;
        }
        for (final p in chunk) {
          entryCache['$tree\u0000$p'] = found[p];
        }
        chunk = [];
        size = 0;
      }

      for (final p in paths) {
        if (entryCache.containsKey('$tree\u0000$p')) continue;
        final n = utf8.encode(p).length + 1;
        if (chunk.isNotEmpty && size + n > 16000) await flush();
        chunk.add(p);
        size += n;
      }
      await flush();
    }

    Future<bool> has(String tree, String path) async =>
        await entry(tree, path) != null;

    Future<Uint8List?> blob(String tree, String path) async {
      final e = await entry(tree, path);
      if (e == null || e[1] != 'blob') return null;
      final r = await git(top, ['cat-file', 'blob', '$tree:$path']);
      checkRead(r, 'git cat-file blob');
      return r.stdout;
    }

    // The blob as a checkout writes it (eol and filter attributes,
    // core.autocrlf), to compare with working-tree bytes.
    Future<Uint8List?> blobWd(String tree, String path) async {
      if (!await has(tree, path)) return null;
      final r = await git(top, ['cat-file', '--filters', '$tree:$path']);
      checkRead(r, 'git cat-file --filters');
      return r.stdout;
    }

    // `blobWd` of each of [paths]: one `git cat-file --batch --filters` for
    // them all; the path-at-a-time read stays for a path with a newline and
    // for a test runner
    Future<Map<String, Uint8List?>> filteredBlobs(
      String tree,
      List<String> paths,
    ) async {
      await prime(tree, paths);
      final out = <String, Uint8List?>{};
      final have = <String>[];
      final oids = <String, String>{};
      for (final p in paths) {
        final e = await entry(tree, p);
        if (e == null) {
          out[p] = null;
        } else {
          have.add(p);
          oids[p] = e[2];
        }
      }
      if (ctx.runner != null || have.any((p) => p.contains('\n'))) {
        for (final p in have) {
          out[p] = await blobWd(tree, p);
        }
        return out;
      }
      if (have.isEmpty) return out;
      final r = await git(top, [
        'cat-file',
        '--batch',
        '--filters',
      ], input: utf8.encode([for (final p in have) '${oids[p]} $p\n'].join()));
      checkRead(r, 'git cat-file --batch --filters');
      // With `--filters` the header's size is the blob's own, not the
      // converted content's, so it cannot delimit a record. A record ends at
      // the newline before the next header, `<oid> blob <size>`, whose object
      // id is known; the last one ends with the output. Anything that does not
      // fit that is read again path by path.
      final bytes = r.stdout;
      int find(List<int> pattern, int from) {
        for (var i = from; i + pattern.length <= bytes.length; i++) {
          if (bytes[i] != pattern[0]) continue;
          var k = 1;
          while (k < pattern.length && bytes[i + k] == pattern[k]) {
            k++;
          }
          if (k == pattern.length) return i;
        }
        return -1;
      }

      final parsed = <String, Uint8List>{};
      var pos = 0;
      var fits = true;
      for (var n = 0; n < have.length && fits; n++) {
        final lead = '${oids[have[n]]} blob '.codeUnits;
        final eol = bytes.indexOf(0x0a, pos);
        fits =
            eol > pos &&
            eol - pos > lead.length &&
            [for (var k = 0; k < lead.length; k++) bytes[pos + k]].join(',') ==
                lead.join(',');
        if (!fits) break;
        final int end;
        if (n + 1 < have.length) {
          end = find('\n${oids[have[n + 1]]} blob '.codeUnits, eol + 1);
        } else {
          end = bytes.length - 1;
        }
        fits = end >= eol + 1 && bytes[end] == 0x0a;
        if (!fits) break;
        parsed[have[n]] = Uint8List.fromList(bytes.sublist(eol + 1, end));
        pos = end + 1;
      }
      if (fits && pos == bytes.length) {
        out.addAll(parsed);
      } else {
        for (final p in have) {
          out[p] = await blobWd(tree, p);
        }
      }
      return out;
    }

    Uint8List? wdBytes(String path) => _readFile(_under(top, path));

    // A decision file (`review.md`, `tasks.md`) as the work tree holds it:
    // absent by `lstat` alone, never by a failed read. A link that leads
    // nowhere, a file that cannot be read and a target that is no regular file
    // are a `vcs_error` naming the path, so nothing falls back to a copy the
    // undo does not restore.
    Uint8List? decisionBytes(String path) {
      final at = _under(top, path);
      if (FileSystemEntity.typeSync(at, followLinks: false) ==
          FileSystemEntityType.notFound) {
        return null;
      }
      try {
        return readRegularFile(at) ??
            (throw VcsStop(
              'vcs_error',
              'cannot read $path: it is a link to nothing',
            ));
      } on NotRegularFile catch (e) {
        throw notRegularStop(e);
      } on FileSystemException catch (e) {
        throw VcsStop(
          'vcs_error',
          'cannot read $path: ${e.osError?.message ?? e.message}',
        );
      }
    }

    // no index on jj; GitButler never stages
    Future<List<String>> staged() async {
      if (jj || gb) return <String>[];
      final r = await git(top, [
        'diff-index',
        '--cached',
        '--ignore-submodules=none',
        '--name-only',
        '-z',
        'HEAD',
        '--',
      ]);
      return [
        for (final record in readInventory(r, 'git diff-index --cached'))
          decodeStrict(record.single, 'file name'),
      ];
    }

    /// Two archive directories that restore to one `changes/<name>/` would nest
    /// one inside the other.
    ///
    /// C40: the undo planner refuses bulk members whose restore names are equal
    /// after `toUpperCase()` or after `toLowerCase()` with
    /// `duplicate_member` on every file system, case-sensitive ones included,
    /// since the plan cannot know where the checkout will be used; names that
    /// differ only by Unicode normalization are not compared (Dart has no
    /// normalizer, and Git on macOS stores precomposed names by default).
    void uniqueMembers(List<(String, String)> order) {
      final seen = <String, String>{};
      for (final (dname, nm) in order) {
        final up = seen['u${nm.toUpperCase()}'];
        final low = seen['l${nm.toLowerCase()}'];
        final first = up ?? low;
        if (first != null) {
          final tgt = _joinAll([prefix, 'changes', nm]);
          throw VcsStop(
            'duplicate_member',
            '$first and $dname both restore to $tgt; move one out of '
                '${_joinAll([prefix, 'changes', 'archive'])}/, then plan again',
            extra: {
              'path': tgt,
              'archived_names': [first, dname],
            },
          );
        }
        seen['u${nm.toUpperCase()}'] = dname;
        seen['l${nm.toLowerCase()}'] = dname;
      }
    }

    // The script copies each synced main spec and moves each archive
    // directory: one deleted from the working tree would stop it halfway.
    void missingInWd(List<String> paths) {
      final gone = [
        for (final p in paths)
          if (!_exists(_under(top, p))) p,
      ];
      if (gone.isNotEmpty) {
        throw VcsStop(
          'dirty_tree',
          'Deleted in the working tree: ${gone.join(', ')}. Restore them with '
              '`git restore -- ${gone.join(' ')}` (or commit the deletion), '
              'then plan again.',
          extra: {'files': gone},
        );
      }
    }

    // C46: the one destination list, checked when planning (Git; the jj and
    // GitButler checks are group 13's): collisions across the whole list, the
    // path-type walk, and gitlinks above a destination in each tree the undo
    // writes into
    Future<void> checkDestinations({
      required List<String> files,
      required List<String> dirs,
      required List<String> memberDirs,
      required List<String> trees,
    }) async {
      refuseCollidingPaths([...files, ...dirs, ...memberDirs]);
      walkDestinations(top, files: files, dirs: dirs, members: memberDirs);
      final ancestors = ancestorDirectories(files, [...dirs, ...memberDirs]);
      for (final tree in trees) {
        await refuseGitlinkAncestors((args) => git(top, args), tree, ancestors);
      }
    }

    final warnings = <String>[];
    final members = <_Member>[];
    var mainMod = <String>[];
    var mainNew = <String>[];
    // the main specs the rerun's `openspec archive` writes (committed only)
    final syncedByRerun = <String>{};
    var goneSpecs = <String>[];
    var amended = <String>[];
    var carried = <String>[];
    var markerDirs = <String, bool>{};
    final String mode;
    final String? a; // the archive commit (committed mode)
    final String t; // the head every guard checks
    final String planBranch;
    List<String> backupFiles;

    if (uncommitted) {
      mode = 'uncommitted';
      a = null;
      t = head;
      planBranch = cb;
      final names = <String, String>{};
      final checked = <String>{};
      final List<String> others;
      if (jj) {
        // Git's index does not follow the jj working copy: the added files
        // are @'s changes
        others = [
          for (final e in (vs['dirty']! as List).cast<Map<String, Object?>>())
            if (e['status'] == 'A' &&
                (e['path']! as String).startsWith('$archiveBase/'))
              e['path']! as String,
        ];
      } else {
        others = nulList(
          await git(top, [
            'ls-files',
            '-z',
            '--others',
            '--exclude-standard',
            '--',
            '$archiveBase/',
          ]),
          'git ls-files',
        );
        // an ignored directory under the archive root would be moved with the
        // archive or hide a member the plan cannot see
        final ignored = nulList(
          await git(top, [
            'ls-files',
            '-z',
            '--others',
            '--ignored',
            '--exclude-standard',
            '--directory',
            '--',
            '$archiveBase/',
          ]),
          'git ls-files --ignored',
        );
        final under = '$archiveBase/';
        for (final path in ignored) {
          final rest = path.startsWith(under)
              ? path.substring(under.length)
              : '';
          if (rest.endsWith('/') && rest.indexOf('/') == rest.length - 1) {
            throw VcsStop(
              'git_env',
              '$path is ignored by Git, so the plan cannot see what it '
                  'holds; remove or move it, or stop ignoring it, then plan '
                  'again',
            );
          }
        }
      }
      final base = '$archiveBase/';
      for (final path in others) {
        final rest = path.startsWith(base) ? path.substring(base.length) : '';
        final dname = _before(rest, '/');
        if (dname.isEmpty || !rest.contains('/')) continue;
        if (dname == archived) continue;
        if (!checked.add(dname)) continue;
        // a change named with a date is archived under that name
        for (final nm in [dname, stripDatePrefix(dname)]) {
          final tgt = _joinAll([prefix, 'changes', nm]);
          if (await has(head, tgt) && !_exists(_under(top, tgt))) {
            names[dname] = nm;
            break;
          }
        }
      }
      final order = <(String, String)>[
        (archived, change),
        for (final k in sortedByCodePoint(names.keys)) (k, names[k]!),
      ];
      uniqueMembers(order);
      for (final (dname, nm) in order) {
        final mdir = _joinAll([archiveBase, dname]);
        final rv = decisionBytes(_joinAll([mdir, 'review.md']));
        members.add(
          _Member(
            nm,
            dname,
            isDeferredVerdict(decodeReplacing(rv ?? Uint8List(0))),
            waitingOnUser(decisionBytes(_joinAll([mdir, 'tasks.md']))),
            mdir,
          ),
        );
      }
      if (cb != branch) {
        warnings.add(
          'The archive is uncommitted, so the plan guards the current branch '
          '${cb.isEmpty ? '(detached)' : cb}, not $branch.',
        );
      }
      final stagedNow = await staged();
      if (stagedNow.isNotEmpty) {
        throw VcsStop(
          'staged_changes',
          'The index differs from HEAD: ${stagedNow.join(', ')}. Unstage or '
              'commit them first.',
        );
      }
      // main specs: the capabilities each member's delta names
      final caps = <String>[];
      for (final m in members) {
        final sp = _joinAll([m.dir, 'specs']);
        // nested capabilities: specs/<area>/<id>/spec.md
        for (final w in _walkArchive(top, sp)) {
          if (w.files.contains('spec.md') && w.rel.isNotEmpty) {
            final cap = _joinAll([prefix, 'specs', w.rel, 'spec.md']);
            if (!caps.contains(cap)) caps.add(cap);
          }
        }
      }
      await prime(head, caps);
      for (final f in sortedByCodePoint(caps)) {
        if (await has(head, f)) {
          mainMod.add(f);
        } else if (_isFile(_under(top, f))) {
          mainNew.add(f);
        }
      }
      missingInWd(mainMod);
      for (final m in members) {
        final tgt = _joinAll([prefix, 'changes', m.name]);
        if (_exists(_under(top, tgt))) {
          throw VcsStop(
            'target_exists',
            '$tgt already exists; merge or move it first',
            extra: {'path': tgt},
          );
        }
      }
      if (!jj && !gb) {
        await checkDestinations(
          files: [...mainMod, ...mainNew],
          dirs: [
            for (final m in members) _joinAll([prefix, 'changes', m.name]),
          ],
          memberDirs: [for (final m in members) m.dir],
          trees: [head],
        );
      }
      // carried edits: archive-copy files that differ from the change
      // directory at HEAD
      for (final m in members) {
        for (final w in _walkArchive(top, m.dir)) {
          for (final fn in w.files) {
            final rel = w.rel.isEmpty ? fn : '${w.rel}/$fn';
            final old = await blobWd(
              head,
              _joinAll([prefix, 'changes', m.name, rel]),
            );
            final at = _under(top, '${m.dir}/$rel');
            final cur =
                _readFile(at) ??
                (throw VcsStop('vcs_error', 'cannot read $at'));
            if (old == null || !_sameBytes(cur, old)) {
              carried.add(_joinAll([m.dir, rel]));
            }
          }
        }
      }
      // a directory's files are emitted together, so a root `b.md` would follow
      // `a/z.md`: sort the finished list by the bytes of each whole path
      carried.sort(compareUtf8);
      for (final m in members) {
        final mk = _joinAll([m.dir, 'specwright-change.yaml']);
        markerDirs[m.name] =
            _isFile(_under(top, mk)) &&
            !await has(
              head,
              _joinAll([prefix, 'changes', m.name, 'specwright-change.yaml']),
            );
      }
      if (_exists(backupDir)) {
        throw VcsStop(
          'backup_exists',
          '$backupDir exists; move or delete it, then plan again',
          extra: {'path': backupDir},
        );
      }
      backupFiles = [...mainMod, ...mainNew];
      if (backupFiles.isNotEmpty) {
        warnings.add(
          'The synced main specs are copied to $backupDir/amended/ before they '
          'are restored or removed; a sync and your own edit in one file '
          'cannot be told apart, so that copy is the only one of your edit.',
        );
      }
    } else {
      mode = 'committed';
      planBranch = branch;
      t = await branchTip((args) => git(top, args), 'refs/heads/$branch');
      var adds = <String>[];
      if (t.isNotEmpty) {
        r = await git(top, [
          'log',
          '--no-renames',
          '--diff-filter=A',
          '--format=%H',
          '$main..$branch',
          '--',
          _joinAll([ad, 'review.md']),
        ]);
        checkRead(r, 'git log');
        adds = _pySplit(textOf(r));
      }
      if (adds.isEmpty) {
        throw VcsStop(
          'no_archive',
          'No archive of $change ($ad) found in the working tree or on $branch',
          extra: {'commits': <String>[]},
        );
      }
      final arch = adds.first;
      a = arch;
      if (!await has(t, ad)) {
        throw VcsStop(
          'no_archive',
          'The archive commit(s) ${adds.map((x) => prefixOf(x, 9)).join(', ')} '
              'of $change were reverted: $ad is not on $branch',
          extra: {'commits': adds},
        );
      }
      if (branch != cb && jj) {
        final dirtyPaths = (vs['dirty_paths']! as List).cast<String>();
        if (dirtyPaths.isNotEmpty) {
          throw VcsStop(
            'dirty_tree',
            'The working copy @ is not empty, so it cannot move onto $branch '
                'with jj new: ${dirtyPaths.join(', ')}',
            extra: {'files': dirtyPaths},
          );
        }
      } else if (branch != cb) {
        final dirty = [
          for (final record in readPorcelain(
            await gitStatus(top),
            'git status',
          ))
            record.decode(),
        ];
        if (dirty.isNotEmpty) {
          throw VcsStop(
            'dirty_tree',
            'The working tree is dirty, so the branch cannot be checked out: '
                '${dirty.map(_dirtyLine).join('; ')}',
            extra: {
              'files': [
                for (final e in dirty) ...[
                  e.path,
                  if (e.source != null) e.source!,
                ],
              ],
            },
          );
        }
      } else {
        final stagedNow = await staged();
        if (stagedNow.isNotEmpty) {
          throw VcsStop(
            'staged_changes',
            'The index differs from HEAD: ${stagedNow.join(', ')}. Unstage or '
                'commit them first.',
          );
        }
      }
      r = await git(top, [
        'diff-tree',
        '-r',
        '--no-renames',
        '--root',
        '--no-commit-id',
        '--name-status',
        '-z',
        arch,
      ]);
      final changes = nulList(r, 'git diff-tree');
      final added = <String>[];
      final mod = <String>[];
      final created = <String>[];
      final deleted = <String>[];
      final specsBase = '${_joinAll([prefix, 'specs'])}/';
      for (var i = 0; i < changes.length - 1; i += 2) {
        final st = changes[i];
        final path = changes[i + 1];
        if (st == 'A') {
          added.add(path);
        } else if (st == 'D') {
          deleted.add(path);
        }
        if (path.startsWith(specsBase)) {
          if (st == 'M') {
            mod.add(path);
          } else if (st == 'A') {
            created.add(path);
          }
        }
      }
      final abase = '$archiveBase/';
      final dnames = <String>[];
      for (final path in added) {
        if (path.startsWith(abase)) {
          final rest = path.substring(abase.length);
          final dn = _before(rest, '/');
          // a plain file under archive/ is no member
          if (dn.isNotEmpty && rest.contains('/') && !dnames.contains(dn)) {
            dnames.add(dn);
          }
        }
      }
      dnames.remove(archived);
      final cbase = '$chg/';
      final moved = <String>{
        for (final p in deleted)
          if (p.startsWith(cbase) && !p.startsWith(abase))
            _before(p.substring(cbase.length), '/'),
      };
      final goneDirs = <String>[];
      for (final dn in dnames) {
        final dir = _joinAll([archiveBase, dn]);
        final held = await entry(t, dir);
        if (held == null) {
          goneDirs.add(dir);
        } else if (held[1] != 'tree') {
          throw VcsStop(
            'vcs_error',
            '$dir is not a directory on $branch (a later commit replaced it '
                'with a ${held[1]}); restore it, then plan again',
            extra: {'path': dir},
          );
        }
      }
      if (goneDirs.isNotEmpty) {
        // restoring the synced specs would drop those members' requirements
        // with nothing to rerun
        throw VcsStop(
          'member_missing',
          'Archive directories of this archive were deleted on $branch after '
              'it: ${goneDirs.join(', ')}. Restore them (or undo the archive by '
              'hand), then plan again.',
          extra: {'paths': goneDirs},
        );
      }
      if (branch != cb && !jj && !gb) {
        // a Git resume classifies a member from the raw blobs of the tip, which
        // the checkout writes back unchanged only when no conversion applies
        await requireAttrSource(top);
        final decisions = [
          for (final dn in [archived, ...dnames])
            for (final f in const ['review.md', 'tasks.md'])
              _joinAll([archiveBase, dn, f]),
        ];
        await refuseConversions((args) => git(top, args), t, decisions);
        for (final path in decisions) {
          final held = await entry(t, path);
          if (held == null) continue;
          if (held[0] == '120000') {
            throw VcsStop(
              'unsupported_filter',
              '$path is committed as a symlink at tip, so the '
                  'plan cannot read what a checkout restores; a Git undo '
                  'does not support that',
            );
          }
          if (held[1] != 'blob') {
            throw VcsStop(
              'unsupported_entry',
              '$path is not a regular file at tip (${held[1]}); a Git undo '
                  'does not support that',
            );
          }
        }
        // a `.gitattributes` the work tree has and HEAD does not track would
        // convert the restored files, and no tree read shows it
        final dirsOnPath = <String>{
          '',
          for (final path in decisions)
            for (
              var i = path.indexOf('/');
              i >= 0;
              i = path.indexOf('/', i + 1)
            )
              path.substring(0, i),
        };
        for (final dir in sortedByCodePoint(dirsOnPath)) {
          final file = dir.isEmpty ? '.gitattributes' : '$dir/.gitattributes';
          if (FileSystemEntity.typeSync(
                    _under(top, file),
                    followLinks: false,
                  ) !=
                  FileSystemEntityType.notFound &&
              !await has(head, file)) {
            throw VcsStop(
              'unsupported_filter',
              '$file is in the work tree but HEAD does not track it, so Git '
                  'would apply it to the files the checkout restores; remove '
                  'it or commit it, then plan again',
            );
          }
        }
      }
      for (final dn in [archived, ...dnames]) {
        final mdir = _joinAll([archiveBase, dn]);
        // a dated name is archived as it is
        final nm = dn == archived
            ? change
            : moved.contains(dn)
            ? dn
            : stripDatePrefix(dn);
        // rerun reads the copy the undo restores: on the current branch the
        // work tree's folder (absent by `lstat` alone, no fallback to the
        // committed blob), on a resume the tip's raw blob
        final review = _joinAll([mdir, 'review.md']);
        final tasks = _joinAll([mdir, 'tasks.md']);
        final rv = branch == cb ? decisionBytes(review) : await blob(t, review);
        final tk = branch == cb ? decisionBytes(tasks) : await blob(t, tasks);
        members.add(
          _Member(
            nm,
            dn,
            isDeferredVerdict(decodeReplacing(rv ?? Uint8List(0))),
            waitingOnUser(tk),
            mdir,
          ),
        );
      }
      uniqueMembers([for (final m in members) (m.archivedName, m.name)]);
      if (!jj && !gb) {
        // a submodule under a member would not come back with its contents
        for (final m in members) {
          final listing = await git(top, [
            'ls-tree',
            '-r',
            '-z',
            t,
            '--',
            m.dir,
          ]);
          for (final record in readInventory(listing, 'git ls-tree')) {
            final text = decodeStrict(record.single, 'file name');
            if (text.startsWith('160000 ')) {
              final tab = text.indexOf('\t');
              throw VcsStop(
                'unsupported_entry',
                '${tab < 0 ? text : text.substring(tab + 1)} is a submodule '
                    'at the tip, which a Git undo does not restore',
              );
            }
          }
        }
      }
      for (final m in members) {
        final tgt = _joinAll([prefix, 'changes', m.name]);
        if (await has(t, tgt) || (branch == cb && _exists(_under(top, tgt)))) {
          throw VcsStop(
            'target_exists',
            '$tgt already exists; merge or move it first',
            extra: {'path': tgt},
          );
        }
      }
      // the main specs the rerun writes, read once, at planning (C33)
      final rerunFirst = [
        for (final m in members)
          if (!m.deferred && m.waiting.isEmpty) m,
      ];
      for (final m in rerunFirst) {
        if (branch == cb) {
          // the undo moves the work-tree folder back, so its delta specs are
          // the ones a rerun syncs
          for (final w in _walkArchive(top, _joinAll([m.dir, 'specs']))) {
            if (w.files.contains('spec.md')) {
              syncedByRerun.add(_joinAll([prefix, 'specs', w.rel, 'spec.md']));
            }
          }
          continue;
        }
        final listing = nulList(
          await git(top, [
            'ls-tree',
            '-r',
            '--name-only',
            '-z',
            t,
            '--',
            _joinAll([m.dir, 'specs']),
          ]),
          'git ls-tree',
        );
        for (final p in listing) {
          final rel = _dropPoints(p, m.dir.runes.length + 1);
          if (rel.endsWith('/spec.md')) {
            syncedByRerun.add(_joinAll([prefix, rel]));
          }
        }
      }
      if (!jj && !gb) {
        await checkDestinations(
          files: [...mod, ...created, ...syncedByRerun],
          dirs: [
            for (final m in members) _joinAll([prefix, 'changes', m.name]),
          ],
          memberDirs: [for (final m in members) m.dir],
          trees: [head, if (branch != cb) t],
        );
      }
      if (_exists(backupDir)) {
        throw VcsStop(
          'backup_exists',
          '$backupDir exists; move or delete it, then plan again',
          extra: {'path': backupDir},
        );
      }
      await prime(t, [...mod, ...created]);
      for (final f in mod) {
        if (await has(t, f)) mainMod.add(f);
      }
      for (final f in created) {
        if (await has(t, f)) mainNew.add(f);
      }
      // a later deletion is an amendment: keep it
      for (final f in [...mod, ...created]) {
        if (!await has(t, f)) goneSpecs.add(f);
      }
      for (final m in members) {
        final mk = _joinAll([m.dir, 'specwright-change.yaml']);
        markerDirs[m.name] = added.contains(mk) && await has(t, mk);
      }
      if (branch == cb && jj) {
        carried = [
          for (final p in (vs['dirty_paths']! as List).cast<String>())
            if (members.any((m) => p.startsWith('${m.dir}/'))) p,
        ];
      } else if (branch == cb) {
        final out = await gitStatus(top, [archiveBase]);
        // the records outside the members go first, undecoded: an unrelated
        // name that is not UTF-8 never stops the plan
        final prefixes = [for (final m in members) utf8.encode('${m.dir}/')];
        bool under(List<int> path) => prefixes.any(
          (p) =>
              path.length >= p.length &&
              _sameBytes(path.sublist(0, p.length), p),
        );
        for (final record in readPorcelain(out, 'git status')) {
          final source = record.source;
          if (!under(record.path) && !(source != null && under(source))) {
            continue;
          }
          final e = record.decode();
          carried.add(e.path);
          if (e.source != null) carried.add(e.source!);
        }
        // UTF-8 byte order of the finished list, a rename's source included
        carried.sort(compareUtf8);
      }
      backupFiles = [
        for (final f in [...mainMod, ...mainNew])
          if (await has(t, f)) f,
      ];
      // a resume from another branch checks out a clean tree, where nothing is
      // missing
      if (branch == cb) {
        missingInWd([for (final m in members) m.dir, ...backupFiles]);
      }
      await prime(arch, backupFiles);
      final syncedWd = branch == cb
          ? await filteredBlobs(arch, backupFiles)
          : const <String, Uint8List?>{};
      for (final f in backupFiles) {
        final cur = branch == cb ? wdBytes(f) : null;
        if (cur == null) {
          // two blobs are the same bytes exactly when their object ids are
          String? oid(List<String>? e) =>
              e != null && e[1] == 'blob' ? e[2] : null;
          if (oid(await entry(t, f)) != oid(await entry(arch, f))) {
            amended.add(f);
          }
        } else if (!_sameOptional(cur, syncedWd[f])) {
          amended.add(f);
        }
      }
    }

    // an assume-unchanged or skip-worktree entry hides an edit from every Git
    // guard: a resume that switches branches scans the whole index, any other
    // plan what it touches (C45)
    if (!jj && !gb) {
      final switching = mode == 'committed' && branch != cb;
      final flagged = await firstFlaggedEntry(
        cwd: top,
        environment: env,
        paths: switching
            ? const []
            : [
                chg,
                _joinAll([prefix, 'specs']),
              ],
      );
      if (flagged != null) {
        throw VcsStop(
          'git_env',
          '$flagged is flagged assume-unchanged or skip-worktree, so Git does '
              'not report its edits and no guard can see them; clear the flag, '
              'then plan again',
        );
      }
    }

    final namesAll = [for (final m in members) m.name];
    if (members.length > 1) {
      warnings.add(
        'This archive holds ${namesAll.join(', ')}. The whole archive is '
        "undone, never only the deferred change's files; run the archive "
        'again without the deferred change.',
      );
    }
    if (jj || gb) {
      warnings.add('Do not edit files after this plan is printed.');
    } else {
      warnings.add(
        'Do not edit files after this plan is printed, and do not start a '
        'merge, cherry-pick, revert or rebase while the steps run.',
      );
      warnings.add(
        'The index must not be changed by other commands or hooks while the '
        'steps run.',
      );
    }

    // a resume that switches the checkout holding the project root may change
    // the stamp the later steps read: one cheap early refusal (C36)
    if (mode == 'committed' && branch != cb && !jj && !gb) {
      if (pth.equals(checkedRoot, top)) await refuseTipStamp(top, head, t);
    }

    // ---- the steps --------------------------------------------------------
    // Each step runs in `top`, where the old script `cd`-ed, so the plan runs
    // from any directory. A step that runs Specwright's own work starts with
    // the running `sw` and carries `--project`, so the version check passes
    // from anywhere (D4, D7).
    final sw = (ctx.sw ?? Platform.resolvedExecutable);
    // the checked root, in Git's spelling when it is the planned checkout
    final project = pth.equals(checkedRoot, top)
        ? top
        : checkedRoot.replaceAll(r'\', '/');
    Map<String, Object?> mk(List<String> argv) => {'cwd': top, 'argv': argv};
    List<String> swArgv(List<String> rest) => [
      sw,
      '--project',
      project,
      ...rest,
    ];
    List<String> undoArgv(List<String> rest) =>
        swArgv(['finish', 'undo-step', ...rest]);
    final steps = <Map<String, Object?>>[];
    void step(List<String> argv) => steps.add(mk(argv));
    void undo(List<String> rest) => step(undoArgv(rest));
    // C46's line sizing: a line counts what the launcher counts, with its
    // terminator, against 32,767 (32,766 visible units); a step that repeats
    // one operation per path is split into runs that fit
    final lineLimit = ctx.lineLimit ?? 32767;
    int cost(String a) =>
        windows ? commandLineUnits([a]) + 1 : utf8.encode(a).length + 1;
    int measure(List<String> argv) =>
        argv.fold(windows ? 0 : 1, (n, a) => n + cost(a));
    void perPath(
      List<String> head,
      List<String> items,
      void Function(List<String> argv) emit,
    ) {
      var chunk = <String>[];
      var used = measure(head);
      for (final item in items) {
        if (chunk.isNotEmpty && used + cost(item) > lineLimit) {
          emit([...head, ...chunk]);
          chunk = [];
          used = measure(head);
        }
        chunk.add(item);
        used += cost(item);
      }
      if (chunk.isNotEmpty) emit([...head, ...chunk]);
    }

    // the subject names the members while it stays within 1,000 characters
    final fullSubject = '$typ($change): undo archive of ${namesAll.join(', ')}';
    final commitSubject = fullSubject.length <= 1000
        ? fullSubject
        : '$typ($change): undo archive of $change (${namesAll.length} changes)';
    void destinationSteps() {
      for (final m in members) {
        undo([
          'check',
          'destinations',
          '--member',
          m.dir,
          '--dir',
          _joinAll([prefix, 'changes', m.name]),
        ]);
      }
      perPath(
        undoArgv(['check', 'destinations', '--']),
        sortedByCodePoint({...mainMod, ...mainNew}),
        step,
      );
      // each restore destination is absent: an ignored directory there
      // would make the final move fail after the undo commit
      for (final m in members) {
        undo([
          'check',
          'absent',
          _joinAll([prefix, 'changes', m.name]),
        ]);
      }
    }

    final touchedAll = [
      for (final m in members) m.dir,
      for (final m in members) _joinAll([prefix, 'changes', m.name]),
      ...mainMod,
      ...mainNew,
    ];
    final committed = mode == 'committed';
    List<String> gitArgv(List<String> rest) => ['git', ...gitSafety, ...rest];
    // the archive commit's parent, named by its OID in the emitted steps
    String parent = '';
    if (committed && !jj && !gb) {
      final pr = await git(top, ['rev-parse', '--verify', '-q', '$a^']);
      parent = pr.exitCode == 0 ? textOf(pr) : '';
      if (parent.isEmpty) {
        throw VcsStop(
          'vcs_error',
          'the archive commit $a has no parent commit to restore from',
        );
      }
    }
    String rev = '';
    List<String> fileset = [];
    if (gb) {
      // the guard reads: the branch is applied at the planned tip and the
      // touched paths have no uncommitted change
      undo(['check', 'branch', planBranch, '--backend', 'gitbutler']);
      undo(['check', 'tip', headref, t]);
      // HEAD is the workspace commit: a touched path that differs from the
      // tip there is another applied branch's, and restoring the file would
      // undo that branch's committed change
      undo([
        'check',
        'unchanged',
        t,
        '--message',
        'another applied branch changes a path the undo restores',
        '--',
        ...touchedAll,
      ]);
      if (committed) undo(['check', 'clean', '--', ...touchedAll]);
      undo(['check', 'absent', backupDir]);
    } else if (jj) {
      // a revset symbol or string
      rev = RegExp(r'^[A-Za-z0-9._/]+(-[A-Za-z0-9._/]+)*$').hasMatch(branch)
          ? branch
          : jjString(branch);
      fileset = [for (final f in touchedAll) 'root:${jjString(f)}'];
      if (committed && branch != cb) {
        undo(['check', 'clean', '--jj']);
        undo(['check', 'tip', 'refs/heads/$branch', t]);
        step(['jj', 'new', rev]);
      }
      undo([
        'check',
        'branch',
        planBranch,
        '--backend',
        'jj',
        if (code != null && code.isNotEmpty) ...['--code', code],
      ]);
      undo(['check', 'tip', headref, t]);
      if (committed) undo(['check', 'clean', '--jj', '--', ...fileset]);
      undo(['check', 'absent', backupDir]);
    } else {
      final v = view!;
      undo([
        'check',
        'preflight',
        '--git-dir',
        v.gitDir,
        '--common-dir',
        v.commonDir,
        '--index',
        v.index,
        '--objects',
        v.objects,
      ]);
      if (committed && branch != cb) {
        undo(['check', 'clean']);
        undo(['check', 'tip', 'refs/heads/$branch', t]);
        // the same attribute reads the plan made, under the environment these
        // steps run in, right before the checkout would apply them
        for (final m in members) {
          undo([
            'check',
            'attributes',
            t,
            '--',
            _joinAll([m.dir, 'review.md']),
            _joinAll([m.dir, 'tasks.md']),
          ]);
        }
        step(
          gitArgv([
            'checkout',
            '-q',
            '--no-overwrite-ignore',
            '--no-recurse-submodules',
            branch,
            '--',
          ]),
        );
      }
      undo(['check', 'branch', planBranch]);
      undo(['check', 'tip', headref, t]);
      final resumed = committed && branch != cb;
      if (resumed) {
        // the checkout wrote the archive branch's files: check them, and what
        // the undo would write, before any backup or index change
        destinationSteps();
        for (final m in members) {
          undo(['check', 'tracked', m.dir]);
        }
        for (final m in members) {
          final review = await entry(t, _joinAll([m.dir, 'review.md']));
          final tasks = await entry(t, _joinAll([m.dir, 'tasks.md']));
          undo(['check', 'inputs', m.dir, review?[2] ?? '-', tasks?[2] ?? '-']);
        }
      }
      undo(['check', 'index']);
      if (!resumed) {
        destinationSteps();
      }
      undo(['check', 'absent', backupDir]);
    }
    // the fileset as the plan's recovery text quotes it
    final fsets = fileset.map(shellQuote).join(' ');

    // ---- the backups ------------------------------------------------------
    final dirs = sortedByCodePoint({
      for (final f in backupFiles) '$backupDir/amended/${_dirname(f)}',
      if (committed)
        for (final f in backupFiles) '$backupDir/base/${_dirname(f)}',
    });
    if (backupFiles.isNotEmpty) perPath(undoArgv(['mkdir']), dirs, step);
    for (final f in backupFiles) {
      if (committed) undo(['write-blob', a!, f, '$backupDir/base/$f']);
      undo(['copy', f, '$backupDir/amended/$f']);
    }
    if (backupFiles.isEmpty) undo(['mkdir', backupDir]);
    // C32: a marker the undo removes is copied before the first index change
    if (!jj && !gb) {
      for (final m in members) {
        if (!markerDirs[m.name]!) {
          continue;
        }
        undo(['mkdir', '$backupDir/markers/${m.name}']);
        undo([
          'copy',
          '--if-present',
          _joinAll([m.dir, 'specwright-change.yaml']),
          '$backupDir/markers/${m.name}/specwright-change.yaml',
        ]);
      }
    }

    if (committed && !jj && !gb) {
      for (final m in members) {
        final changeDir = _joinAll([prefix, 'changes', m.name]);
        step(gitArgv(['rm', '-r', '-q', '--cached', '--', m.dir]));
        step(gitArgv(['read-tree', '--prefix=$changeDir/', '$t:${m.dir}']));
        if (markerDirs[m.name]!) {
          step(
            gitArgv([
              'rm',
              '-q',
              '--cached',
              '--',
              '$changeDir/specwright-change.yaml',
            ]),
          );
        }
      }
      perPath(
        gitArgv(['restore', '--source=$parent', '--staged', '--']),
        mainMod,
        step,
      );
      perPath(gitArgv(['rm', '-q', '--cached', '--']), mainNew, step);
      final subject = commitSubject;
      step(gitArgv(['commit', '-q', '-m', subject]));
    }
    for (final m in members) {
      final changeDir = _joinAll([prefix, 'changes', m.name]);
      undo(['move', m.dir, changeDir]);
      if (markerDirs[m.name]!) {
        undo(['remove', '$changeDir/specwright-change.yaml']);
      }
    }
    if (mainMod.isNotEmpty && jj) {
      step([
        'jj',
        'restore',
        '--from',
        committed ? '$a-' : t,
        for (final f in mainMod) 'root:${jjString(f)}',
      ]);
    } else if (mainMod.isNotEmpty && gb) {
      // a file write from a Git read: `git restore` would be a Git write to
      // the shared work tree
      final baseRev = committed ? '$a^' : t;
      for (final f in mainMod) {
        undo(['write-blob', baseRev, f, f]);
      }
    } else if (mainMod.isNotEmpty) {
      perPath(
        gitArgv([
          'restore',
          committed ? '--source=$parent' : '--source=$t',
          '--worktree',
          '--',
        ]),
        mainMod,
        step,
      );
    }
    if (mainNew.isNotEmpty) {
      perPath(undoArgv(['remove']), mainNew, step);
      for (final dn in sortedByCodePoint({
        for (final f in mainNew) _dirname(f),
      })) {
        undo(['rmdir-if-empty', dn]);
      }
    }
    if (jj && committed) {
      final subject = commitSubject;
      step(['jj', 'commit', '-m', subject, ...fileset]);
      step(['jj', 'bookmark', 'set', rev, '-r', '@-']);
    }
    if (gb && committed) {
      final subject = commitSubject;
      final msgfile = '$backupDir/commit-message.txt';
      undo(['write-text', msgfile, subject]);
      // a directory ends in `/` so the commit covers the files that left it
      final cpaths = [
        for (final d in [
          for (final m in members) m.dir,
          for (final m in members) _joinAll([prefix, 'changes', m.name]),
        ])
          '$d/',
        ...mainMod,
        ...mainNew,
      ];
      step(
        swArgv([
          'vcs',
          'commit',
          '--repo',
          top,
          '--role',
          'code',
          '--branch',
          branch,
          '--message-file',
          msgfile,
          '--',
          ...cpaths,
        ]),
      );
    }

    if (committed && jj) {
      warnings.add(
        'If a step fails after the steps began changing the working copy and '
        'before it commits, run `jj restore $fsets` and plan again. Unlike '
        'the Git steps, the working tree is NOT untouched until the commit '
        'on jj: the moves and restores happen in @ first.',
      );
      final dirtyPaths = (vs['dirty_paths']! as List).cast<String>();
      if (dirtyPaths.isNotEmpty &&
          branch == cb &&
          dirtyPaths.any(
            (p) =>
                touchedAll.any((f) => p.startsWith('$f/')) ||
                touchedAll.contains(p),
          )) {
        warnings.add(
          '@ already holds changes under the touched paths, so the script\'s '
          'guard stops before it moves anything. Commit them elsewhere or set '
          'them aside, then plan again.',
        );
      }
    } else if (committed && gb) {
      warnings.add(
        'The steps move and rewrite files in the shared GitButler work '
        'tree first and commits them last, with `sw vcs commit` (`but commit '
        '-b $branch`), naming only the touched paths; no Git write runs. If '
        'it fails before the commit, those files are uncommitted changes: '
        'move the archived directories back by hand, write each main spec '
        'again with `git cat-file --filters <archive commit>^:<path>`, and '
        'plan again.',
      );
    } else if (committed) {
      // no command: a reset could follow GIT_INDEX_FILE into another index
      warnings.add(
        'If a step fails after the steps began changing the index and before '
        'they commit, the index entries of ${touchedAll.join(' ')} may be '
        "partly changed, and a resume plan's checkout may already have "
        'happened. Unstage those paths yourself and move or delete the backup '
        'directory $backupDir, then plan again; the working tree is untouched '
        'until the commit.',
      );
      if (branch != cb) {
        warnings.add(
          "If a step stops after the checkout, check Git's effective work "
          'tree and index before switching back to '
          '${cb.isEmpty ? 'the previous HEAD' : cb}, never switch blindly.',
        );
      }
    }
    if (backupFiles.isNotEmpty && committed) {
      warnings.add(
        'Base and amended copies of the synced main specs are saved in '
        '$backupDir; no step reads or deletes them.',
      );
    }
    if (!jj && !gb && markerDirs.values.any((v) => v)) {
      warnings.add(
        'A change marker the undo removes is copied to $backupDir/markers/ '
        'first, and no step deletes that copy.',
      );
    }

    // ---- after_rerun ------------------------------------------------------
    /// C33: the rerun decision (eligibility and delta inventory) is made once,
    /// at planning, from the copy the undo restores; edits to the archive after
    /// the plan is printed, including a relative link that resolves differently
    /// once moved, are outside the contract and are not guarded, and the plan's
    /// warning says not to edit files after it is printed. Rejected: a
    /// per-member digest guard, which needed a pinned-tree variant before a
    /// resume checkout, a post-undo variant without the removed marker, and a
    /// recovery path the CLI cannot plan once the undo is committed.
    ///
    /// Every bulk member but the deferred ones and those waiting on the user,
    /// the named one included.
    final rerun = [
      for (final m in members)
        if (!m.deferred && m.waiting.isEmpty) m,
    ];
    var merge = <String>[];
    var left = committed ? [...amended] : <String>[];
    var redelete = <String>[];
    var names = '';
    if (committed && rerun.isNotEmpty) {
      merge = [
        for (final f in amended)
          if (syncedByRerun.contains(f)) f,
      ];
      left = [
        for (final f in amended)
          if (!syncedByRerun.contains(f)) f,
      ];
      // the rerun archive would bring them back
      redelete = [
        for (final f in goneSpecs)
          if (syncedByRerun.contains(f)) f,
      ];
    }
    final afterSteps = <Map<String, Object?>>[];
    if (rerun.isNotEmpty) {
      names = rerun.map((m) => m.name).join(', ');
      // stop before any archive when the user made a new spec of the same name
      // C46: the rerun's destinations are checked again before it writes any
      if (!jj && !gb) {
        perPath(
          undoArgv(['check', 'destinations', '--']),
          sortedByCodePoint(syncedByRerun),
          (argv) => afterSteps.add(mk(argv)),
        );
      }
      for (final f in redelete) {
        afterSteps.add(
          mk(
            undoArgv([
              'check',
              'absent',
              f,
              '--message',
              '$f exists; after_rerun_steps would delete it. Move it '
                  'away, then run again.',
            ]),
          ),
        );
      }
      // the rerun archives in the selected OpenSpec root, the parent of the
      // prefix, so a nested planning root (`planning/openspec`) never
      // archives a same-named change of the top-level project
      final slash = prefix.lastIndexOf('/');
      final rerunCwd = slash < 0
          ? top
          : _under(top, prefix.substring(0, slash));
      for (final m in rerun) {
        afterSteps.add({
          'cwd': rerunCwd,
          'argv': ['openspec', 'archive', m.name, '--yes'],
        });
      }
      for (final f in merge) {
        afterSteps.add(
          mk(
            undoArgv([
              'merge-back',
              f,
              '$backupDir/base/$f',
              '$backupDir/amended/$f',
            ]),
          ),
        );
      }
      for (final f in redelete) {
        afterSteps.add(mk(undoArgv(['remove', f])));
      }
      // C48: the pinned OpenSpec CLI updates an existing spec in place
      warnings.add(
        'after_rerun_steps write an existing main spec in place, as '
        '`openspec archive` does, so a second hard link to one of them, made '
        'outside Specwright, sees the update; the undo\'s own restore replaces '
        'the file instead.',
      );
      warnings.add(
        'Run after_rerun_steps after steps: they archive $names again'
        '${merge.isNotEmpty ? ' and merges the saved amendments into ${merge.join(', ')}. '
                  'On a conflict it stops with markers in the file; both copies stay in $backupDir.' : '.'}',
      );
    }
    for (final f in goneSpecs) {
      if (redelete.contains(f)) {
        warnings.add(
          '$f was deleted on $branch after the archive; the undo leaves it '
          'deleted; after_rerun_steps archive $names again, and a later step '
          'deletes it again.',
        );
      } else {
        warnings.add(
          '$f was deleted on $branch after the archive; the undo leaves it '
          'deleted.',
        );
      }
    }
    if (left.isNotEmpty) {
      warnings.add(
        'Amendments to ${left.join(', ')} were made on top of the deferred '
        "change's synced content, so they are saved in $backupDir/amended/ "
        'and never merged automatically; review them by hand.',
      );
    }

    // a line that cannot be split and still does not fit would fail to start
    // after the steps began: stop before printing any
    for (final printed in [...steps, ...afterSteps]) {
      final argv = (printed['argv']! as List).cast<String>();
      if (measure(argv) > lineLimit) {
        throw VcsStop(
          'plan_too_large',
          'A step of this undo cannot be split under the command-line limit '
              '(${measure(argv)} units, limit $lineLimit): '
              '${argv.take(8).join(' ')} ...; nothing was changed',
        );
      }
    }

    return {
      'ok': true,
      'mode': mode,
      'archive_commit': a,
      'branch': planBranch,
      'head': t,
      'members': [
        for (final m in members)
          {
            'name': m.name,
            'archived_name': m.archivedName,
            'deferred': m.deferred,
            'waiting_on_user': m.waiting,
          },
      ],
      'main_specs': {'modified': mainMod, 'created': mainNew},
      'amended': amended,
      'carried_edits': carried,
      'backup_dir': backupDir,
      'steps': steps,
      'after_rerun_steps': afterSteps,
      'warnings': warnings,
    };
  }
}

/// One change the plan undoes: its [name] (the `changes/<name>/` it returns
/// to), its [archivedName], whether its review is DEFERRED, the ids of its
/// unticked `[user]` tasks and its archive directory [dir].
class _Member {
  _Member(this.name, this.archivedName, this.deferred, this.waiting, this.dir);

  final String name;
  final String archivedName;
  final bool deferred;
  final List<String> waiting;
  final String dir;
}

/// One dirty record of the resume `dirty_tree` message: the status with its
/// spaces trimmed, a space and the path (`<source> -> <path>` for a rename or
/// copy). A newline, carriage return or tab in a name shows as `\n`, `\r` or
/// `\t`, so the message stays one line; `files` keeps the bytes.
String _dirtyLine(ZEntry e) {
  String shown(String name) => name
      .replaceAll('\n', r'\n')
      .replaceAll('\r', r'\r')
      .replaceAll('\t', r'\t');
  final status = e.status.replaceAll(' ', '');
  final source = e.source;
  return source == null
      ? '$status ${shown(e.path)}'
      : '$status ${shown(source)} -> ${shown(e.path)}';
}

/// `_type_of`: the commit type of the undo commit from the branch prefix.
String _typeOf(String branch) {
  if (!branch.contains('/')) return 'chore';
  final pre = _before(branch, '/');
  return pre == 'bugfix' ? 'fix' : pre;
}

/// `text.split(sep, 1)[0]`.
String _before(String text, String sep) {
  final i = text.indexOf(sep);
  return i < 0 ? text : text.substring(0, i);
}

/// `os.path.dirname` of a `/` path.
String _dirname(String path) {
  final i = path.lastIndexOf('/') + 1;
  var head = path.substring(0, i);
  if (head.isNotEmpty && head.replaceAll('/', '').isNotEmpty) {
    head = head.replaceFirst(RegExp(r'/+$'), '');
  }
  return head;
}

/// `s[n:]` in Python: by code point, so a lone surrogate (an escaped byte)
/// counts as one and a pair as one.
String _dropPoints(String s, int n) => String.fromCharCodes(s.runes.skip(n));

/// `s[:n]` in Python: by code point, never half a surrogate pair (`sw pr reviewers` cuts its excerpts with it).
String prefixOf(String s, int n) => String.fromCharCodes(s.runes.take(n));

/// Python's `str.split()`: runs of whitespace separate the pieces.
List<String> _pySplit(String s) {
  final out = <String>[];
  final buf = StringBuffer();
  for (final u in s.codeUnits) {
    if (isPySpace(u)) {
      if (buf.isNotEmpty) out.add(buf.toString());
      buf.clear();
    } else {
      buf.writeCharCode(u);
    }
  }
  if (buf.isNotEmpty) out.add(buf.toString());
  return out;
}

/// The ASCII whitespace `bytes.strip()` removes.
bool _asciiSpace(int b) => b == 0x20 || (b >= 0x09 && b <= 0x0d);

bool _sameBytes(List<int> x, List<int> y) {
  if (x.length != y.length) return false;
  for (var i = 0; i < x.length; i++) {
    if (x[i] != y[i]) return false;
  }
  return true;
}

bool _sameOptional(List<int>? x, List<int>? y) =>
    x == null || y == null ? x == null && y == null : _sameBytes(x, y);

bool _truthy(Object? v) =>
    !(v == null ||
        v == false ||
        v == 0 ||
        v == '' ||
        (v is List && v.isEmpty) ||
        (v is Map && v.isEmpty));

final RegExp _deferredLine = RegExp(r'^VERDICT: DEFERRED[ \t]*\r?$');
final RegExp _userTaskLine = RegExp(
  r'^[ \t]*-[ \t]+\[([^\]\r\n]*)\][ \t]+([0-9]+\.[0-9]+)[ \t]+\[user\]'
  r'(?=[ \t]|\r?$)',
);
final RegExp _datePrefix = RegExp(r'^[0-9]{4}-[0-9]{2}-[0-9]{2}-');

/// `DEFERRED_RX.search(text)` of `finish.sh` (`(?m)^VERDICT: DEFERRED[ \t]*\r?$`).
/// The text is split on `\n` only and each piece is matched whole, so `^` and
/// `$` anchor where Python's `(?m)` does and not at `\r`, U+2028 or U+2029
/// (constraint C4).
bool isDeferredVerdict(String text) =>
    text.split('\n').any(_deferredLine.hasMatch);

/// `waiting_on_user` of `finish.sh`: the ids of the unticked `[user]` tasks in
/// a `tasks.md` ([tasks] is its bytes, null when absent), in file order. The
/// text is decoded with replacement and split on `\n` only (C4); ids are ASCII
/// digits (C1); a box is done only when it holds `x` or `X` after a Python
/// `strip`.
List<String> waitingOnUser(List<int>? tasks) {
  final text = decodeReplacing(tasks ?? const <int>[]);
  final ids = <String>[];
  for (final line in text.split('\n')) {
    final m = _userTaskLine.firstMatch(line);
    if (m == null) continue;
    final box = pyStrip(m.group(1)!);
    if (box != 'x' && box != 'X') ids.add(m.group(2)!);
  }
  return ids;
}

/// `DATE_RX.sub("", name)`: one leading `YYYY-MM-DD-` of ASCII digits.
String stripDatePrefix(String name) => name.replaceFirst(_datePrefix, '');

/// Python's string order: by code point, not by UTF-16 unit. A lone surrogate
/// (an escaped byte) is the code point it is.
int compareCodePoints(String a, String b) {
  final x = a.runes.iterator;
  final y = b.runes.iterator;
  while (true) {
    final hasX = x.moveNext();
    final hasY = y.moveNext();
    if (!hasX || !hasY) {
      return hasX == hasY ? 0 : (hasX ? 1 : -1);
    }
    if (x.current != y.current) return x.current < y.current ? -1 : 1;
  }
}

/// `sorted(items)` on strings.
List<String> sortedByCodePoint(Iterable<String> items) =>
    items.toList()..sort(compareCodePoints);
