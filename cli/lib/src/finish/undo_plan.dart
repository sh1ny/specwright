import 'dart:io';
import 'dart:typed_data';

import '../commands/vcs.dart';
import '../commit/paths.dart';
import '../commit/task_cover.dart' show isPySpace, pyStrip, pySplitLines;
import '../fs/walk.dart';
import '../vcs/args.dart';
import '../vcs/codec.dart';
import '../vcs/document.dart';
import '../vcs/stop.dart';
import '../vcs/tool_runner.dart';
import 'script_text.dart';

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
}

/// What a planner gets from the handoff: the scripts directory and the bash
/// that ran the shim.
class FinishContext {
  FinishContext({
    required this.scriptsDir,
    required this.bash,
    this.environment,
    this.windows,
    this.stateReader,
  });

  final String scriptsDir;
  final String bash;

  /// The environment `git` and `cygpath` run with; null is the parent's. Tests
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
/// C3: the printed `script` and `after_rerun` call `bash <specwright-pr>/scripts/vcs.sh`
/// by path, never an `sw` binary. C1: ids and date prefixes match ASCII digits
/// only.
Future<Map<String, Object?>> undoArchivePlan(
  UndoRequest request,
  FinishContext ctx,
) => _Planner(request, ctx).run();

/// The lexical normalisation of [path] (Python's `os.path.normpath`) with `/`
/// separators: `.` and empty parts dropped, `..` folded into its parent, none
/// kept at a root. [windows] (default: this OS) treats `\` as a separator and
/// reads a drive (`C:`) or a UNC share (`//server/share`) as a root.
String normalizeLexical(String path, {bool? windows}) {
  final win = windows ?? Platform.isWindows;
  var rest = win ? path.replaceAll(r'\', '/') : path;
  var prefix = '';
  if (win) {
    final drive = RegExp(r'^(?:[A-Za-z]:|//[^/]+/[^/]+)').firstMatch(rest);
    if (drive != null) {
      prefix = drive.group(0)!;
      rest = rest.substring(prefix.length);
    }
    if (rest.startsWith('/')) {
      prefix += '/';
      rest = rest.replaceFirst(RegExp(r'^/+'), '');
    }
  } else if (rest.startsWith('/')) {
    final slashes = RegExp(r'^/+').firstMatch(rest)!.group(0)!.length;
    prefix = slashes == 2 ? '//' : '/';
    rest = rest.replaceFirst(RegExp(r'^/+'), '');
  }
  final parts = <String>[];
  for (final part in rest.split('/')) {
    if (part.isEmpty || part == '.') continue;
    if (part == '..') {
      if (parts.isNotEmpty && parts.last != '..') {
        parts.removeLast();
      } else if (!prefix.endsWith('/')) {
        parts.add('..');
      }
    } else {
      parts.add(part);
    }
  }
  final out = prefix + parts.join('/');
  return out.isEmpty ? '.' : out;
}

VcsStop _usage(String message) => VcsStop('usage', message, code: 2);

/// `json.loads` of what `vcs.sh` printed, as `finish.sh` read it: a name that
/// was not valid UTF-8 went out as raw bytes and came back as U+FFFD.
Object? _asRead(Object? value) {
  if (value is String) return decodeReplacing(encodeEscaped(value));
  if (value is List) return <Object?>[for (final v in value) _asRead(v)];
  if (value is Map) {
    return <String, Object?>{
      for (final e in value.entries) e.key as String: _asRead(e.value),
    };
  }
  return value;
}

String _joinAll(List<String> parts) =>
    parts.where((p) => p.isNotEmpty).join('/');

/// `os.path.join(top, path)` for a relative [path].
String _under(String top, String path) =>
    top.endsWith('/') ? '$top$path' : '$top/$path';

Uint8List _raw(String path) => encodeEscaped(path);

bool _isDir(String path) => Directory.fromRawPath(_raw(path)).existsSync();

bool _isFile(String path) => File.fromRawPath(_raw(path)).existsSync();

bool _exists(String path) => _isFile(path) || _isDir(path);

/// The tree under [rel] (relative to [top]) with the finish link policy: a link
/// to a directory is listed under `dirs` and not entered, any other link under
/// `files`. A name that is not UTF-8 stops the plan with `not_utf8`.
List<WalkDirectory> _walkArchive(String top, String rel) {
  try {
    return walkTree(_under(top, rel), policy: WalkPolicy.finish, prefix: rel);
  } on NotUtf8 catch (e) {
    throw VcsStop.notUtf8(e);
  }
}

/// A file's bytes, or null when it cannot be read (`wd_bytes`).
Uint8List? _readFile(String path) {
  try {
    return File.fromRawPath(_raw(path)).readAsBytesSync();
  } on FileSystemException {
    return null;
  }
}

class _Planner {
  _Planner(this.request, this.ctx)
    : windows = ctx.windows ?? Platform.isWindows,
      env = {...(ctx.environment ?? Platform.environment)}
        ..putIfAbsent('GIT_TERMINAL_PROMPT', () => '0');

  final UndoRequest request;
  final FinishContext ctx;
  final bool windows;
  final Map<String, String> env;

  /// `<pr scripts>`: the lexical normalisation of
  /// `<scripts dir>/../../specwright-pr/scripts` (D2).
  late final String prScripts = normalizeLexical(
    '${ctx.scriptsDir}/../../specwright-pr/scripts',
    windows: windows,
  );
  late final String vcsSh = '$prScripts/vcs.sh';

  Future<ToolResult> git(String cwd, List<String> args) =>
      runTool(ctx.bash, cwd, ['git', ...args], environment: env);

  String textOf(ToolResult r) => pyStrip(decodeReplacing(r.stdout));

  List<String> nulList(ToolResult r) {
    final out = <String>[];
    var start = 0;
    final bytes = r.stdout;
    for (var i = 0; i <= bytes.length; i++) {
      if (i == bytes.length || bytes[i] == 0) {
        if (i > start) out.add(decodeReplacing(bytes.sublist(start, i)));
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
    if (!_isFile(vcsSh)) {
      throw VcsStop(
        'vcs_script_missing',
        '$vcsSh is missing; finish.sh reads the branch through it',
        code: 2,
        extra: {'path': vcsSh},
      );
    }
    final role = code != null && code.isNotEmpty
        ? ['--role', 'store', '--code', codeFor(top, code)]
        : ['--role', 'code'];
    if (branch != null && branch.isNotEmpty) role.addAll(['--branch', branch]);
    try {
      final reader = ctx.stateReader;
      if (reader != null) {
        return (_asRead(await reader(top, code, branch))! as Map).cast();
      }
      final parsed = parseVcsArguments(['state', '--repo', top, ...role]);
      final session = await openSession(
        VcsContext(parsed, prScripts, ctx.bash),
      );
      return (_asRead(await stateDocument(session))! as Map).cast();
    } on VcsStop catch (stop) {
      throw VcsStop(
        stop.error.isEmpty ? 'vcs_error' : stop.error,
        stop.message.isEmpty ? 'vcs.sh state failed' : stop.message,
      );
    }
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
    var d = request.dir;
    var code = request.code;
    try {
      d = await nativePath(
        d,
        ctx.bash,
        windows: ctx.windows,
        environment: ctx.environment,
      );
      if (code != null) {
        code = await nativePath(
          code,
          ctx.bash,
          windows: ctx.windows,
          environment: ctx.environment,
        );
      }
    } on BadPathException catch (e) {
      throw VcsStop('bad_path', e.toString(), code: 2, extra: {'path': e.path});
    }
    var prefix = request.prefix!.replaceAll(RegExp(r'^/+|/+$'), '');
    if (prefix == '.') prefix = '';

    var r = await git(d, ['rev-parse', '--show-toplevel']);
    if (r.exitCode != 0 || textOf(r).isEmpty) {
      throw VcsStop('not_a_repo', '$d is not inside a git work tree');
    }
    final top = textOf(r);
    final gitdir = textOf(await git(top, ['rev-parse', '--absolute-git-dir']));
    r = await git(top, ['rev-parse', '--verify', '-q', 'HEAD^{commit}']);
    if (r.exitCode != 0) {
      throw VcsStop('not_a_repo', 'the repository has no commit');
    }
    var head = textOf(r);
    final vs = await vcsState(top, code, request.branch);
    final jj = vs['backend'] == 'jj';
    final gb = vs['backend'] == 'gitbutler';
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
    final adInHead = listed.stdout.any((b) => !_asciiSpace(b));
    final uncommitted = adInWd && !adInHead;
    final typ = request.type != null && request.type!.isNotEmpty
        ? request.type!
        : _typeOf(branch);
    final backupDir = '$gitdir/specwright-undo/$archived';

    Future<bool> has(String tree, String path) async =>
        (await git(top, ['cat-file', '-e', '$tree:$path'])).exitCode == 0;

    Future<Uint8List?> blob(String tree, String path) async {
      final r = await git(top, ['cat-file', 'blob', '$tree:$path']);
      return r.exitCode == 0 ? r.stdout : null;
    }

    // The blob as a checkout writes it (eol and filter attributes,
    // core.autocrlf), to compare with working-tree bytes.
    Future<Uint8List?> blobWd(String tree, String path) async {
      final r = await git(top, ['cat-file', '--filters', '$tree:$path']);
      return r.exitCode == 0 ? r.stdout : null;
    }

    Uint8List? wdBytes(String path) => _readFile(_under(top, path));

    // no index on jj; GitButler never stages
    Future<List<String>> staged() async => jj || gb
        ? <String>[]
        : nulList(await git(top, ['diff', '--cached', '--name-only', '-z']));

    // Two archive directories that restore to one changes/<name>/ would nest
    // one inside the other.
    void uniqueMembers(List<(String, String)> order) {
      final seen = <String, String>{};
      for (final (dname, nm) in order) {
        if (seen.containsKey(nm)) {
          final tgt = _joinAll([prefix, 'changes', nm]);
          throw VcsStop(
            'duplicate_member',
            '${seen[nm]} and $dname both restore to $tgt; move one out of '
                '${_joinAll([prefix, 'changes', 'archive'])}/, then plan again',
            extra: {
              'path': tgt,
              'archived_names': [seen[nm], dname],
            },
          );
        }
        seen[nm] = dname;
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

    final warnings = <String>[];
    final members = <_Member>[];
    var mainMod = <String>[];
    var mainNew = <String>[];
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
        );
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
        final rv = wdBytes(_joinAll([mdir, 'review.md']));
        members.add(
          _Member(
            nm,
            dname,
            isDeferredVerdict(decodeReplacing(rv ?? Uint8List(0))),
            waitingOnUser(wdBytes(_joinAll([mdir, 'tasks.md']))),
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
            final cur = File.fromRawPath(_raw(_under(top, '${m.dir}/$rel')))
                .readAsBytesSync();
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
      r = await git(top, ['rev-parse', '--verify', '-q', 'refs/heads/$branch']);
      t = r.exitCode == 0 ? textOf(r) : '';
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
        final dirty = pySplitLines(
          textOf(await git(top, ['status', '--porcelain'])),
        );
        if (dirty.isNotEmpty) {
          throw VcsStop(
            'dirty_tree',
            'The working tree is dirty, so the branch cannot be checked out: '
                '${dirty.map(pyStrip).join('; ')}',
            extra: {
              'files': [for (final x in dirty) _dropPoints(x, 3)],
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
      final changes = nulList(r);
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
        if (!await has(t, dir)) goneDirs.add(dir);
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
      for (final dn in [archived, ...dnames]) {
        final mdir = _joinAll([archiveBase, dn]);
        // a dated name is archived as it is
        final nm = dn == archived
            ? change
            : moved.contains(dn)
            ? dn
            : stripDatePrefix(dn);
        final rv = await blob(t, _joinAll([mdir, 'review.md']));
        // on the current branch the undo moves the working-tree folder back,
        // so its tasks.md is the one rerun reads
        var tk = branch == cb ? wdBytes(_joinAll([mdir, 'tasks.md'])) : null;
        tk ??= await blob(t, _joinAll([mdir, 'tasks.md']));
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
      if (_exists(backupDir)) {
        throw VcsStop(
          'backup_exists',
          '$backupDir exists; move or delete it, then plan again',
          extra: {'path': backupDir},
        );
      }
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
        final out = await git(top, [
          'status',
          '--porcelain=v1',
          '-z',
          '--untracked-files=all',
          '--',
          for (final m in members) m.dir,
        ]);
        var start = 0;
        final bytes = out.stdout;
        for (var i = 0; i <= bytes.length; i++) {
          if (i == bytes.length || bytes[i] == 0) {
            if (i - start > 3) {
              carried.add(
                _dropPoints(decodeReplacing(bytes.sublist(start, i)), 3),
              );
            }
            start = i + 1;
          }
        }
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
      for (final f in backupFiles) {
        Uint8List? cur = branch == cb ? wdBytes(f) : null;
        final Uint8List? synced;
        if (cur == null) {
          cur = await blob(t, f);
          synced = await blob(arch, f);
        } else {
          synced = await blobWd(arch, f);
        }
        if (!_sameOptional(cur, synced)) amended.add(f);
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
    warnings.add('Do not edit files while the script runs.');

    // ---- the guard --------------------------------------------------------
    final sq = shellQuote;
    final touchedAll = [
      for (final m in members) m.dir,
      for (final m in members) _joinAll([prefix, 'changes', m.name]),
      ...mainMod,
      ...mainNew,
    ];
    final committed = mode == 'committed';
    final List<String> lines;
    var rev = '';
    var fsets = '';
    // Deliberate gap C13: the printed jj and GitButler guards read the
    // `vcs.sh state` document by text, matching the compact `"branch":"<name>"`
    // that `sw vcs` prints, until native-cli-internal-calls replaces that
    // boundary. Keep this pattern in step with the document form.
    final branchPattern = sq('"branch":${documentText(planBranch)}');
    if (gb) {
      // the guard reads: the branch is applied at the planned tip and the
      // touched paths have no uncommitted change
      final stateCmd =
          'bash ${sq(vcsSh)} state --repo ${sq(top)} --role code --branch ${sq(branch)}';
      lines = [
        'set -euo pipefail',
        'cd ${sq(top)}',
        'case "\$($stateCmd)" in *$branchPattern*) ;; *) echo "wrong branch" >&2; exit 1 ;; esac',
        'test "\$(git rev-parse ${sq(headref)})" = ${sq(t)}',
        // HEAD is the workspace commit: a touched path that differs from the
        // tip there is another applied branch's, and restoring the file would
        // undo that branch's committed change
        'git diff --quiet ${sq(t)} HEAD -- ${touchedAll.map(sq).join(' ')}'
            ' || { echo "another applied branch changes a path the undo restores" >&2; exit 1; }',
      ];
      if (committed) {
        lines.add(
          'test -z "\$(git --no-optional-locks status --porcelain '
          '--untracked-files=all -- ${touchedAll.map(sq).join(' ')})"',
        );
      }
      lines.add('test ! -e ${sq(backupDir)}');
    } else if (jj) {
      // a revset symbol or string
      rev = RegExp(r'^[A-Za-z0-9._/]+(-[A-Za-z0-9._/]+)*$').hasMatch(branch)
          ? branch
          : jjString(branch);
      fsets = touchedAll.map((f) => sq('root:${jjString(f)}')).join(' ');
      final stateRole = code != null && code.isNotEmpty
          ? '--role store --code ${sq(code)}'
          : '--role code';
      final stateCmd = 'bash ${sq(vcsSh)} state --repo ${sq(top)} $stateRole';
      lines = ['set -euo pipefail', 'cd ${sq(top)}'];
      if (committed && branch != cb) {
        lines.addAll([
          'test -z "\$(jj diff -r @ --name-only)"',
          'test "\$(git rev-parse ${sq('refs/heads/$branch')})" = ${sq(t)}',
          'jj new ${sq(rev)}',
        ]);
      }
      lines.addAll([
        'case "\$($stateCmd)" in *$branchPattern*) ;; *) echo "wrong branch" >&2; exit 1 ;; esac',
        'test "\$(git rev-parse ${sq(headref)})" = ${sq(t)}',
      ]);
      if (committed) lines.add('test -z "\$(jj diff -r @ --name-only $fsets)"');
      lines.add('test ! -e ${sq(backupDir)}');
    } else {
      lines = ['set -euo pipefail', 'cd ${sq(top)}'];
    }
    final guard = [
      'test "\$(git branch --show-current)" = ${sq(planBranch)}',
      'test "\$(git rev-parse ${sq(headref)})" = ${sq(t)}',
      'git diff --cached --quiet',
      'test ! -e ${sq(backupDir)}',
    ];
    if (!jj && !gb) {
      if (committed && branch != cb) {
        lines.addAll([
          'test -z "\$(git status --porcelain)"',
          'test "\$(git rev-parse ${sq('refs/heads/$branch')})" = ${sq(t)}',
          'git checkout -q ${sq(branch)} --',
        ]);
      }
      lines.addAll(guard);
    }

    // ---- the backups ------------------------------------------------------
    final dirs = sortedByCodePoint({
      for (final f in backupFiles) '$backupDir/amended/${_dirname(f)}',
      if (committed)
        for (final f in backupFiles) '$backupDir/base/${_dirname(f)}',
    });
    if (backupFiles.isNotEmpty) {
      lines.add('mkdir -p -- ${dirs.map(sq).join(' ')}');
    }
    for (final f in backupFiles) {
      if (committed) {
        lines.add(
          'git cat-file --filters ${sq('$a:$f')} > ${sq('$backupDir/base/$f')}',
        );
      }
      lines.add('cp -- ${sq(f)} ${sq('$backupDir/amended/$f')}');
    }
    if (backupFiles.isEmpty) lines.add('mkdir -p -- ${sq(backupDir)}');

    if (committed && !jj && !gb) {
      for (final m in members) {
        lines.add('git rm -r -q --cached -- ${sq(m.dir)}');
        lines.add(
          'git read-tree --prefix=${sq('${_joinAll([prefix, 'changes', m.name])}/')} '
          '${sq('$t:${m.dir}')}',
        );
        if (markerDirs[m.name]!) {
          lines.add(
            'git rm -q --cached -- '
            '${sq(_joinAll([prefix, 'changes', m.name, 'specwright-change.yaml']))}',
          );
        }
      }
      if (mainMod.isNotEmpty) {
        lines.add(
          'git restore --source=${sq('$a^')} --staged -- '
          '${mainMod.map(sq).join(' ')}',
        );
      }
      if (mainNew.isNotEmpty) {
        lines.add('git rm -q --cached -- ${mainNew.map(sq).join(' ')}');
      }
      final subject = '$typ($change): undo archive of ${namesAll.join(', ')}';
      lines.add('git commit -q -m ${sq(subject)}');
    }
    for (final m in members) {
      lines.add(
        'mv -- ${sq(m.dir)} ${sq(_joinAll([prefix, 'changes', m.name]))}',
      );
      if (markerDirs[m.name]!) {
        lines.add(
          'rm -f -- '
          '${sq(_joinAll([prefix, 'changes', m.name, 'specwright-change.yaml']))}',
        );
      }
    }
    final src = committed ? '--source=${sq('$a^')}' : '--source=${sq(t)}';
    if (mainMod.isNotEmpty && jj) {
      lines.add(
        'jj restore --from ${sq(committed ? '$a-' : t)} '
        '${mainMod.map((f) => sq('root:${jjString(f)}')).join(' ')}',
      );
    } else if (mainMod.isNotEmpty && gb) {
      // a file write from a Git read: `git restore` would be a Git write to
      // the shared work tree
      final baseRev = committed ? '$a^' : t;
      for (final f in mainMod) {
        lines.add('git cat-file --filters ${sq('$baseRev:$f')} > ${sq(f)}');
      }
    } else if (mainMod.isNotEmpty) {
      lines.add('git restore $src --worktree -- ${mainMod.map(sq).join(' ')}');
    }
    if (mainNew.isNotEmpty) {
      lines.add('rm -f -- ${mainNew.map(sq).join(' ')}');
      for (final dn in sortedByCodePoint({
        for (final f in mainNew) _dirname(f),
      })) {
        lines.add('rmdir ${sq(dn)} 2>/dev/null || true');
      }
    }
    if (jj && committed) {
      final subject = '$typ($change): undo archive of ${namesAll.join(', ')}';
      lines.add('jj commit -m ${sq(subject)} $fsets');
      lines.add('jj bookmark set ${sq(rev)} -r @-');
    }
    if (gb && committed) {
      final subject = '$typ($change): undo archive of ${namesAll.join(', ')}';
      final msgfile = '$backupDir/commit-message.txt';
      lines.add("printf '%s\\n' ${sq(subject)} > ${sq(msgfile)}");
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
      lines.add(
        'bash ${sq(vcsSh)} commit --repo ${sq(top)} --role code --branch '
        '${sq(branch)} --message-file ${sq(msgfile)} -- '
        '${cpaths.map(sq).join(' ')}',
      );
    }
    lines.add("echo ${sq('Undo done. Saved copies are in $backupDir')}");
    final script = '${lines.join('\n')}\n';

    if (committed && jj) {
      warnings.add(
        'If the script fails after it began changing the working copy and '
        'before it commits, run `jj restore $fsets` and plan again. Unlike '
        'the Git script, the working tree is NOT untouched until the commit '
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
        'The script moves and rewrites files in the shared GitButler work '
        'tree first and commits them last, with `vcs.sh commit` (`but commit '
        '-b $branch`), naming only the touched paths; no Git write runs. If '
        'it fails before the commit, those files are uncommitted changes: '
        'move the archived directories back by hand, write each main spec '
        'again with `git cat-file --filters <archive commit>^:<path>`, and '
        'plan again.',
      );
    } else if (committed) {
      warnings.add(
        'If the script fails after it began changing the index and before it '
        'commits, run `git restore --staged -- ${touchedAll.join(' ')}` and '
        'plan again; the working tree is untouched until the commit.',
      );
    }
    if (backupFiles.isNotEmpty && committed) {
      warnings.add(
        'Base and amended copies of the synced main specs are saved in '
        '$backupDir; no step reads or deletes them.',
      );
    }

    // ---- after_rerun ------------------------------------------------------
    String? after;
    // every bulk member but the deferred ones and those waiting on the user,
    // the named one included
    final rerun = [
      for (final m in members)
        if (!m.deferred && m.waiting.isEmpty) m,
    ];
    var merge = <String>[];
    var left = committed ? [...amended] : <String>[];
    var redelete = <String>[];
    var names = '';
    if (committed && rerun.isNotEmpty) {
      final syncedByRerun = <String>{};
      for (final m in rerun) {
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
        );
        for (final p in listing) {
          final rel = _dropPoints(p, m.dir.runes.length + 1);
          if (rel.endsWith('/spec.md')) {
            syncedByRerun.add(_joinAll([prefix, rel]));
          }
        }
      }
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
    if (rerun.isNotEmpty) {
      names = rerun.map((m) => m.name).join(', ');
      final al = ['set -euo pipefail', 'cd ${sq(top)}'];
      // stop before any archive when the user made a new spec of the same name
      for (final f in redelete) {
        al.add(
          'test ! -e ${sq(f)} || { echo '
          '${sq('$f exists; the after-rerun script would delete it. Move it away, then run again.')}'
          ' >&2; exit 1; }',
        );
      }
      for (final m in rerun) {
        al.add('openspec archive ${sq(m.name)} --yes');
      }
      for (final f in merge) {
        al.add(
          'git merge-file -L rerun -L archived -L amended ${sq(f)} '
          '${sq('$backupDir/base/$f')} ${sq('$backupDir/amended/$f')}',
        );
      }
      for (final f in redelete) {
        al.add('rm -f -- ${sq(f)}');
      }
      final done = merge.isNotEmpty
          ? 'Amendments merged.'
          : 'Archived again by after_rerun.';
      al.add('echo ${sq('$done Now start finish for: $names')}');
      after = '${al.join('\n')}\n';
      warnings.add(
        'Run after_rerun after script: it archives $names again'
        '${merge.isNotEmpty ? ' and merges the saved amendments into ${merge.join(', ')}. '
                  'On a conflict it stops with markers in the file; both copies stay in $backupDir.' : '.'}',
      );
    }
    for (final f in goneSpecs) {
      if (redelete.contains(f)) {
        warnings.add(
          '$f was deleted on $branch after the archive; the undo leaves it '
          'deleted, and after_rerun deletes it again after it archives '
          '$names.',
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
      'script': script,
      'after_rerun': after,
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
