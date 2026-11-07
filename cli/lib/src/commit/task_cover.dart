import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import '../vcs/codec.dart';
import '../vcs/document.dart';
import '../vcs/stop.dart';
import '../vcs/tool_runner.dart';
import 'context.dart';
import 'paths.dart';

/// Runs one `git` command line (the tool name first) and returns what it
/// produced. The default is `runTool(bash, '.', argv)`; tests substitute it.
typedef GitTool = Future<ToolResult> Function(List<String> argv);

/// Converts a path argument to a native path (design D9). The default is
/// [nativePath] with the handoff's bash; it throws [BadPathException].
typedef PathConverter = Future<String> Function(String path);

const String _usage =
    'task-cover.sh --repo <dir> --range <a>..<b> --tasks <tasks.md> '
    '--change <name> [--rev <sha>] [--code <dir>]';

const int _maxTasksBytes = 1024 * 1024;
const int _defaultMaxCommits = 10000;
const int _maxField = 64 * 1024;

/// `sw commit task-cover`: which tasks of `tasks.md` the commits of a range
/// cover. Prints one JSON document, byte for byte what `task-cover.sh` printed
/// (keys in order, `", "` and `": "` separators, raw UTF-8, U+2028 and U+2029
/// not escaped, `\r\n` on Windows) and returns the exit code: 0 answered, 1
/// `range_too_large` or `internal_error`, 2 usage or bad input, 3 git failed.
///
/// Constraint C2: sw commit runs git with no deadline and no byte bound, as
/// task-cover.sh did. Adding bounds is a behaviour change for its own change.
///
/// [git], [convert] and [environment] are the seams the tests use; they
/// default to `runTool` through the handoff's bash, [nativePath] and the
/// process environment.
Future<int> taskCover(
  List<String> args,
  CommitContext ctx, {
  GitTool? git,
  PathConverter? convert,
  Map<String, String>? environment,
}) async {
  Map<String, Object?> doc;
  var code = 0;
  try {
    doc = await _cover(
      args,
      git: git ?? (argv) => runTool(ctx.bash, '.', argv),
      convert: convert ?? (path) => nativePath(path, ctx.bash),
      environment: environment ?? Platform.environment,
    );
  } on VcsStop catch (stop) {
    doc = stop.object();
    code = stop.code;
  } on Object catch (e) {
    doc = _internalError(e);
    code = 1;
  }
  List<int> bytes;
  try {
    bytes = documentBytes(doc, escapeLineSeparators: false);
  } on Object catch (e) {
    code = 1;
    bytes = documentBytes(_internalError(e), escapeLineSeparators: false);
  }
  ctx.writeOut(bytes);
  return code;
}

/// The entry the dispatcher calls: [taskCover] with the real runners.
Future<int> runTaskCover(List<String> args, CommitContext ctx) =>
    taskCover(args, ctx);

Map<String, Object?> _internalError(Object e) => {
  'ok': false,
  'error': 'internal_error',
  'message': switch (e) {
    StateError(:final message) => message,
    ArgumentError(:final message) => '$message',
    FormatException(:final message) => message,
    _ => e.toString(),
  },
};

/// One git call from `dir`: its stdout, or null for a failed soft call.
typedef GitCall = Future<Uint8List?> Function(
  String repo,
  List<String> args, {
  required bool soft,
});

Future<Map<String, Object?>> _cover(
  List<String> args, {
  required GitTool git,
  required PathConverter convert,
  required Map<String, String> environment,
}) async {
  final maxCommits = _maxCommits(environment['TASK_COVER_MAX_COMMITS']);
  final want = _parseArgs(args);
  final String repo;
  final String tasksPath;
  try {
    tasksPath = await convert(want['--tasks']!);
    repo = await convert(want['--repo']!);
  } on BadPathException catch (e) {
    throw VcsStop('bad_path', e.toString(), code: 2);
  }
  final rng = want['--range']!;
  final change = want['--change']!;
  final rev = want['--rev'];

  Future<Uint8List?> call(
    String dir,
    List<String> a, {
    required bool soft,
  }) async {
    // log.showSignature would print signature checks into the machine-readable
    // log; a local refs/replace entry must not change what a commit holds.
    final r = await git([
      'git',
      '--no-replace-objects',
      '-c',
      'log.showSignature=false',
      '-C',
      dir,
      ...a,
    ]);
    // Exit 127 is the transport's: git could not start (no git on PATH, a
    // vanished directory). It stops even a soft call.
    if (r.exitCode == 127) {
      throw VcsStop(
        'git_failed',
        'cannot run git: ${pyStrip(decodeReplacing(r.stderr))}',
        code: 3,
      );
    }
    if (r.exitCode != 0) {
      if (soft) return null;
      throw VcsStop(
        'git_failed',
        'git ${a.first} failed: ${pyStrip(decodeReplacing(r.stderr))}',
        code: 3,
      );
    }
    return r.stdout;
  }

  Future<Uint8List> hard(String dir, List<String> a) async =>
      (await call(dir, a, soft: false))!;

  final py = PyPath();
  Uint8List rawTasks;
  String? relDir;
  if (rev != null && rev.isNotEmpty) {
    final top = pyStrip(
      decodeReplacing(await hard(repo, ['rev-parse', '--show-toplevel'])),
    );
    // The path inside the repo is taken lexically: following a working-tree
    // symlink would let the checkout pick which committed file is read. Only
    // the repo's own location may be resolved (macOS /var -> /private/var).
    String? tasksRel;
    for (final base in [py.abspath(repo), py.abspath(top), py.realpath(repo)]) {
      final r = py
          .relpath(py.abspath(tasksPath), base)
          ?.replaceAll(py.sep, '/');
      if (r == null) continue;
      if (r != '.' && r != '..' && !r.startsWith('../')) {
        tasksRel = r;
        break;
      }
    }
    if (tasksRel == null) {
      throw VcsStop(
        'no_tasks',
        'tasks file $tasksPath is outside the repo',
        code: 2,
      );
    }
    final noTasks = VcsStop(
      'no_tasks',
      'no tasks file $tasksRel at $rev',
      code: 2,
    );
    // only a regular file is a task list: a committed symlink or directory
    // would parse as one with no tasks
    final entry =
        await call(repo, ['ls-tree', '-z', rev, '--', tasksRel], soft: true) ??
        Uint8List(0);
    final trimmed = _rstripNul(entry);
    final tab = trimmed.indexOf(9);
    final meta = _fields(tab < 0 ? trimmed : trimmed.sublist(0, tab));
    final name = tab < 0 ? Uint8List(0) : trimmed.sublist(tab + 1);
    if (meta.length != 3 ||
        !_fileModes.contains(meta[0]) ||
        meta[1] != 'blob' ||
        !_bytesEqual(name, encodeEscaped(tasksRel)) ||
        trimmed.contains(0)) {
      throw noTasks;
    }
    final blob = await call(repo, ['cat-file', 'blob', meta[2]], soft: true);
    if (blob == null) throw noTasks;
    rawTasks = blob;
    relDir = tasksRel.contains('/')
        ? tasksRel.substring(0, tasksRel.lastIndexOf('/'))
        : '';
  } else {
    final file = File.fromRawPath(encodeEscaped(tasksPath));
    final stat = file.statSync();
    if (stat.type != FileSystemEntityType.file) {
      throw VcsStop('no_tasks', 'no tasks file: $tasksPath', code: 2);
    }
    if (stat.size > _maxTasksBytes) {
      throw VcsStop('tasks_too_large', 'tasks.md is over 1 MiB', code: 2);
    }
    rawTasks = file.readAsBytesSync();
  }
  if (rawTasks.length > _maxTasksBytes) {
    throw VcsStop('tasks_too_large', 'tasks.md is over 1 MiB', code: 2);
  }
  final parsed = parseTasks(decodeReplacing(rawTasks));
  // a repeated id would let one line's evidence hide the other's: tasks.md is
  // invalid, report no coverage
  if (parsed.repeated.isNotEmpty) {
    throw VcsStop(
      'duplicate_task_ids',
      '$tasksPath repeats task ids: ${parsed.repeated.join(', ')}',
      code: 2,
    );
  }
  final tasks = parsed.tasks;

  final countText = pyStrip(
    utf8.decode(await hard(repo, ['rev-list', '--count', rng])),
  );
  final count = countText.isEmpty ? 0 : int.parse(countText);
  if (count > maxCommits) {
    throw VcsStop(
      'range_too_large',
      'range $rng has $count commits, over the bound of $maxCommits',
      code: 1,
    );
  }

  final raw = await hard(repo, [
    'log',
    '-z',
    '--format=%H%x00%s%x00%(trailers:key=Specwright-Task,valueonly,'
        'separator=%x1F)%x00'
        '%(trailers:key=Specwright-User-Task,valueonly,separator=%x1F)',
    rng,
  ]);
  final tok = decodeReplacing(raw).split('\u0000');
  // a trailing empty token after the last record terminator
  if (tok.isNotEmpty && tok.last.isEmpty) tok.removeLast();
  if (tok.length % 4 != 0) {
    throw VcsStop('git_failed', 'unexpected git log output', code: 3);
  }

  final ct = _reEscape(change);
  final subjTask = RegExp('^[^$_ws]+\\($ct\\): task ([0-9]+\\.[0-9]+) ');
  final subjGroup = RegExp('^[^$_ws]+\\($ct\\): group ([0-9]+) ');
  final taskId = RegExp(r'^[0-9]+\.[0-9]+$');
  final byId = {for (final t in tasks) t.id: t};
  final cross = <Map<String, Object?>>[];
  for (var i = 0; i < tok.length; i += 4) {
    final sha = pyStrip(tok[i]);
    final subject = cutField(tok[i + 1]);
    final trailers = cutField(tok[i + 2]);
    final userTrailers = cutField(tok[i + 3]);
    final forms = <String, String>{};
    BigInt? grp;
    final m = subjTask.firstMatch(subject);
    if (m != null) {
      forms[m.group(1)!] = 'subject';
      grp = BigInt.parse(m.group(1)!.split('.').first);
    } else {
      final g = subjGroup.firstMatch(subject);
      if (g != null) grp = BigInt.parse(g.group(1)!);
    }
    if (trailers.isNotEmpty) {
      for (final part in trailers.split('\u001f')) {
        final v = pyStrip(part);
        if (!taskId.hasMatch(v)) continue;
        forms.putIfAbsent(v, () => 'trailer');
        if (grp != null && BigInt.parse(v.split('.').first) != grp) {
          cross.add({'sha': sha, 'task': v, 'group': grp});
        }
      }
    }
    // a Specwright-User-Task trailer covers a user task only and is never
    // cross-group
    if (userTrailers.isNotEmpty) {
      for (final part in userTrailers.split('\u001f')) {
        final v = pyStrip(part);
        final t = byId[v];
        if (t != null && t.kind == 'user') forms[v] = 'user_trailer';
      }
    }
    for (final e in forms.entries) {
      byId[e.key]?.commits.add({'sha': sha, 'form': e.value});
    }
  }

  final groupIds = <BigInt>{
    for (final t in tasks) t.group,
    ...parsed.headings.keys,
  }.toList()..sort();

  bool work(TaskItem t) => t.kind != 'user' && t.ticked && t.commits.isEmpty;

  final uncovered = [
    for (final t in tasks)
      if (work(t)) t.id,
  ];
  final pending = <Map<String, Object?>>[];
  for (final g in groupIds) {
    final ids = [
      for (final t in tasks)
        if (t.group == g && work(t)) t.id,
    ];
    if (ids.isNotEmpty) pending.add({'group': g, 'tasks': ids});
  }
  final waiting = [
    for (final t in tasks)
      if (t.kind == 'user' && !t.ticked) t.id,
  ];
  final userUncommitted = [
    for (final t in tasks)
      if (t.kind == 'user' &&
          t.ticked &&
          !t.commits.any((c) => c['form'] == 'user_trailer'))
        t.id,
  ];
  final evidenceMissing = <String>[];
  for (final t in tasks) {
    if (t.kind == 'evidence' &&
        t.ticked &&
        !await evidenceOk(
          parsed.texts[t.id]!,
          call: call,
          repo: repo,
          tasksPath: tasksPath,
          rev: rev != null && rev.isNotEmpty ? rev : null,
          relDir: relDir,
        )) {
      evidenceMissing.add(t.id);
    }
  }
  final taskGroups = <BigInt>{for (final t in tasks) t.group}.toList()..sort();
  return {
    'ok': true,
    'change': change,
    'range': rng,
    'tasks': [for (final t in tasks) t.toJson()],
    'groups': [
      for (final g in groupIds) {'group': g, 'heading': parsed.headings[g]},
    ],
    'pending_groups': pending,
    'uncovered': uncovered,
    'waiting_on_user': waiting,
    'user_uncommitted': userUncommitted,
    'evidence_missing': evidenceMissing,
    'duplicates': [
      for (final t in tasks)
        if (t.commits.length > 1)
          {
            'task': t.id,
            'commits': [for (final c in t.commits) c['sha']],
          },
    ],
    'cross_group': cross,
    'missing_headings': [
      for (final g in taskGroups)
        if (!parsed.headings.containsKey(g)) g,
    ],
  };
}

int _maxCommits(String? value) {
  if (value == null || value.isEmpty) return _defaultMaxCommits;
  return int.parse(pyStrip(value));
}

Map<String, String?> _parseArgs(List<String> argv) {
  final want = <String, String?>{
    '--repo': null,
    '--range': null,
    '--tasks': null,
    '--change': null,
    '--rev': null,
    '--code': null,
  };
  var i = 0;
  while (i < argv.length) {
    if (want.containsKey(argv[i]) && i + 1 < argv.length) {
      want[argv[i]] = argv[i + 1];
      i += 2;
    } else {
      throw VcsStop('usage', _usage, code: 2);
    }
  }
  for (final k in ['--repo', '--range', '--tasks', '--change']) {
    final v = want[k];
    if (v == null || v.isEmpty) throw VcsStop('usage', _usage, code: 2);
  }
  return want;
}

const Set<String> _fileModes = {'100644', '100755'};

/// Whether the task text of an evidence task names a file that counts.
///
/// Constraint C3: Evidence files are read only from the index or from the tree
/// at --rev, never through the working tree, and paths are opened only by raw
/// bytes.
///
/// The first `evidence/<path>` in [taskText] (sentence punctuation after it is
/// not part of it) is relative to the change folder, the directory of
/// [tasksPath]. It counts only as a regular, non-empty blob: at [rev] in the
/// tree of [repo] (the change folder is [relDir] there), else in the index of
/// the repo that holds `tasks.md`. A path with a backslash, a colon or an
/// empty, `.` or `..` segment never counts. [call] is the git runner.
Future<bool> evidenceOk(
  String taskText, {
  required GitCall call,
  required String repo,
  required String tasksPath,
  String? rev,
  String? relDir,
}) async {
  final m = _evidence.firstMatch(taskText);
  if (m == null) return false;
  var rel = m.group(1)!;
  // sentence or markdown punctuation after the path is not part of it
  while (rel.isNotEmpty && '.:*!?'.contains(rel[rel.length - 1])) {
    rel = rel.substring(0, rel.length - 1);
  }
  // `\` and `:` would let Windows read a segment as a UNC or drive path
  // outside the change: reject before any filesystem access, as are empty,
  // `.` and `..` segments.
  if (rel.contains(r'\') ||
      rel.contains(':') ||
      rel.split('/').any((s) => s.isEmpty || s == '.' || s == '..')) {
    return false;
  }
  if (rev != null) {
    // only a regular file entry counts: a tree, symlink (120000) or submodule
    // entry does not
    final path = [
      if (relDir != null && relDir.isNotEmpty) relDir,
      rel,
    ].join('/');
    final entry = await call(repo, [
      'ls-tree',
      '-z',
      rev,
      '--',
      path,
    ], soft: true);
    if (entry == null || entry.isEmpty) return false;
    final trimmed = _rstripNul(entry);
    final tab = trimmed.indexOf(9);
    final fields = _fields(tab < 0 ? trimmed : trimmed.sublist(0, tab));
    final name = tab < 0 ? Uint8List(0) : trimmed.sublist(tab + 1);
    if (fields.length != 3 ||
        !_fileModes.contains(fields[0]) ||
        decodeReplacing(name) != path) {
      return false;
    }
    final size = await call(repo, ['cat-file', '-s', fields[2]], soft: true);
    return size != null && _nonEmptySize(size);
  }
  // The index of the repo holding tasks.md (the planning repo, whatever --repo
  // names), never the working tree: no path is opened, so no symlink, UNC or
  // drive path, or swap during the check can make another file count.
  final py = PyPath();
  final changeDir = py.dirname(py.abspath(tasksPath));
  final entry = await call(changeDir, [
    'ls-files',
    '-s',
    '-z',
    '--',
    ':(literal)$rel',
  ], soft: true);
  if (entry == null || entry.isEmpty) return false;
  final entries = <Uint8List>[];
  var start = 0;
  for (var i = 0; i <= entry.length; i++) {
    if (i == entry.length || entry[i] == 0) {
      if (i > start) entries.add(entry.sublist(start, i));
      start = i + 1;
    }
  }
  if (entries.length != 1) return false;
  final tab = entries.first.indexOf(9);
  final fields = _fields(
    tab < 0 ? entries.first : entries.first.sublist(0, tab),
  ); // mode, object, stage
  final name = tab < 0 ? Uint8List(0) : entries.first.sublist(tab + 1);
  if (fields.length != 3 ||
      !_fileModes.contains(fields[0]) ||
      fields[2] != '0' ||
      decodeReplacing(name) != rel) {
    return false;
  }
  final size = await call(changeDir, ['cat-file', '-s', fields[1]], soft: true);
  return size != null && _nonEmptySize(size);
}

bool _nonEmptySize(Uint8List size) {
  final s = _asciiStrip(size);
  return s.isNotEmpty && s != '0';
}

String _asciiStrip(Uint8List b) {
  var lo = 0;
  var hi = b.length;
  bool ws(int c) => c == 32 || (c >= 9 && c <= 13);
  while (lo < hi && ws(b[lo])) {
    lo++;
  }
  while (hi > lo && ws(b[hi - 1])) {
    hi--;
  }
  return latin1.decode(b.sublist(lo, hi));
}

Uint8List _rstripNul(Uint8List b) {
  var n = b.length;
  while (n > 0 && b[n - 1] == 0) {
    n--;
  }
  return b.sublist(0, n);
}

/// bytes.split(): runs of ASCII whitespace separate the fields.
List<String> _fields(Uint8List b) {
  final out = <String>[];
  var start = -1;
  for (var i = 0; i <= b.length; i++) {
    final isWs = i == b.length || b[i] == 32 || (b[i] >= 9 && b[i] <= 13);
    if (isWs) {
      if (start >= 0) out.add(latin1.decode(b.sublist(start, i)));
      start = -1;
    } else if (start < 0) {
      start = i;
    }
  }
  return out;
}

bool _bytesEqual(List<int> a, List<int> b) {
  if (a.length != b.length) return false;
  for (var i = 0; i < a.length; i++) {
    if (a[i] != b[i]) return false;
  }
  return true;
}

String _reEscape(String s) => s.replaceAllMapped(
  RegExp(r'[\\^$.|?*+()\[\]{}/-]'),
  (m) => '\\${m.group(0)}',
);

// ---------------------------------------------------------------------------
// The tasks.md parser.

/// The characters `str.isspace()` accepts, as the inside of a regex class.
const String _ws =
    r'\t\n\v\f\r\x1c-\x1f \x85\xa0\u1680\u2000-\u200a\u2028\u2029\u202f'
    r'\u205f\u3000';

final RegExp _heading = RegExp(
  r'^##[ \t]+([0-9]+)\.[ \t]+([^' + _ws + r'].*?)[ \t]*$',
  dotAll: true,
);
final RegExp _task = RegExp(
  r'^[ \t]*-[ \t]+\[([^\]\r\n]*)\][ \t]+([0-9]+)\.([0-9]+)(?=[' +
      _ws +
      r']|$)(.*)$',
  dotAll: true,
);
final RegExp _marker = RegExp(r'^[ \t]*\[(user|evidence)\](?=[ \t]|$)');
final RegExp _evidence = RegExp(
  '(?:^|[$_ws(`\'"*_])(evidence/[^$_ws)`\'",;]+)',
);

/// One `- [<box>] X.Y ` line of `tasks.md`. [commits] fills in as the log is
/// read: `{sha, form}` entries.
class TaskItem {
  TaskItem(this.id, this.group, this.kind, this.ticked);

  final String id;
  final BigInt group;
  final String kind;
  final bool ticked;
  final List<Map<String, String>> commits = [];

  Map<String, Object?> toJson() => {
    'id': id,
    'group': group,
    'kind': kind,
    'ticked': ticked,
    'commits': commits,
  };
}

/// What [parseTasks] read: the tasks in file order, the first heading of each
/// group, each task's text after its id, and the ids on more than one line.
class ParsedTasks {
  final List<TaskItem> tasks = [];
  final Map<BigInt, String> headings = {};
  final Map<String, String> texts = {};
  final List<String> repeated = [];
}

/// tasks.md is parsed with Python's text rules: str.splitlines line
/// boundaries, str.isspace whitespace for \s, strip and the TASK lookahead,
/// `.` excluding only `\n`, fields cut at 64 Ki code points, and rev-list
/// --count decoded strictly. A simpler Dart default changes which tasks and
/// user checks are found.
///
/// The one difference from the script: ids are ASCII digits only
/// (`[0-9]`, not Python's `\d`), so `\u0661.\u0661` is not a task.
ParsedTasks parseTasks(String text) {
  final out = ParsedTasks();
  for (final line in pySplitLines(text)) {
    final h = _heading.firstMatch(line);
    if (h != null) {
      out.headings.putIfAbsent(BigInt.parse(h.group(1)!), () => h.group(2)!);
      continue;
    }
    final m = _task.firstMatch(line);
    if (m == null) continue;
    final id = '${m.group(2)}.${m.group(3)}';
    final rest = m.group(4)!;
    final mk = _marker.firstMatch(rest);
    out.texts[id] = rest;
    out.tasks.add(
      TaskItem(
        id,
        BigInt.parse(m.group(2)!),
        mk?.group(1) ?? 'agent',
        _boxDone(m.group(1)!),
      ),
    );
  }
  final seen = <String>{};
  for (final t in out.tasks) {
    if (!seen.add(t.id) && !out.repeated.contains(t.id)) out.repeated.add(t.id);
  }
  return out;
}

/// the apply schema: a box holding only x (any case, any spacing) is done;
/// every other marker is not
bool _boxDone(String box) {
  final s = pyStrip(box);
  return s == 'x' || s == 'X';
}

/// Python's `str.splitlines()`: lines end at `\n`, `\r`, `\r\n`, `\v`, `\f`,
/// `\x1c`-`\x1e`, `\x85`, U+2028 and U+2029; the terminators are dropped and a
/// final terminator starts no further line.
List<String> pySplitLines(String s) {
  final out = <String>[];
  var start = 0;
  var i = 0;
  final n = s.length;
  while (i < n) {
    final c = s.codeUnitAt(i);
    if (_isLineBoundary(c)) {
      out.add(s.substring(start, i));
      if (c == 0x0d && i + 1 < n && s.codeUnitAt(i + 1) == 0x0a) i++;
      start = i + 1;
    }
    i++;
  }
  if (start < n) out.add(s.substring(start));
  return out;
}

bool _isLineBoundary(int c) =>
    (c >= 0x0a && c <= 0x0d) ||
    (c >= 0x1c && c <= 0x1e) ||
    c == 0x85 ||
    c == 0x2028 ||
    c == 0x2029;

/// Python's `str.isspace` for one UTF-16 unit (every such character is in the
/// BMP).
bool isPySpace(int c) =>
    (c >= 0x09 && c <= 0x0d) ||
    (c >= 0x1c && c <= 0x20) ||
    c == 0x85 ||
    c == 0xa0 ||
    c == 0x1680 ||
    (c >= 0x2000 && c <= 0x200a) ||
    c == 0x2028 ||
    c == 0x2029 ||
    c == 0x202f ||
    c == 0x205f ||
    c == 0x3000;

/// Python's `str.strip()`: removes [isPySpace] characters at both ends.
String pyStrip(String s) {
  var lo = 0;
  var hi = s.length;
  while (lo < hi && isPySpace(s.codeUnitAt(lo))) {
    lo++;
  }
  while (hi > lo && isPySpace(s.codeUnitAt(hi - 1))) {
    hi--;
  }
  return s.substring(lo, hi);
}

/// `s[:65536]` in Python: 64 Ki code points, never half a surrogate pair.
String cutField(String s) {
  if (s.length <= _maxField) return s;
  var units = 0;
  var points = 0;
  while (units < s.length && points < _maxField) {
    final c = s.codeUnitAt(units);
    final pair =
        c >= 0xd800 &&
        c <= 0xdbff &&
        units + 1 < s.length &&
        s.codeUnitAt(units + 1) >= 0xdc00 &&
        s.codeUnitAt(units + 1) <= 0xdfff;
    units += pair ? 2 : 1;
    points++;
  }
  return s.substring(0, units);
}

// ---------------------------------------------------------------------------
// os.path as Python gives it, for the few calls task-cover makes.

/// `os.path.abspath`, `relpath`, `realpath` and `dirname`, for the host OS
/// (or [windows]) with [cwdOverride] (default: the process's cwd).
class PyPath {
  PyPath({bool? windows, this.cwdOverride})
    : windows = windows ?? Platform.isWindows;

  final bool windows;
  final String? cwdOverride;

  String get sep => windows ? r'\' : '/';
  String get cwd => cwdOverride ?? Directory.current.path;

  /// The drive (a letter and colon, or `\\server\share`) and the rest. On
  /// POSIX the drive is empty.
  (String, String) splitDrive(String p) {
    if (!windows) return ('', p);
    final n = p.replaceAll('/', r'\');
    if (n.startsWith(r'\\') && !n.startsWith(r'\\\')) {
      final i = n.indexOf(r'\', 2);
      if (i == -1) return ('', n);
      var j = n.indexOf(r'\', i + 1);
      if (j == -1) j = n.length;
      if (j == i + 1) return ('', n);
      return (n.substring(0, j), n.substring(j));
    }
    if (n.length >= 2 && n[1] == ':') {
      return (n.substring(0, 2), n.substring(2));
    }
    return ('', n);
  }

  String normpath(String p) {
    final (drive, rest0) = splitDrive(windows ? p.replaceAll('/', r'\') : p);
    var rest = rest0;
    var root = '';
    if (rest.startsWith(sep)) {
      var k = 0;
      while (k < rest.length && rest[k] == sep) {
        k++;
      }
      root = !windows && k == 2 ? '//' : sep;
      rest = rest.substring(k);
    }
    final stack = <String>[];
    for (final c in rest.split(sep)) {
      if (c.isEmpty || c == '.') continue;
      if (c == '..') {
        if (stack.isNotEmpty && stack.last != '..') {
          stack.removeLast();
        } else if (root.isEmpty) {
          stack.add('..');
        }
      } else {
        stack.add(c);
      }
    }
    final r = drive + root + stack.join(sep);
    return r.isEmpty ? '.' : r;
  }

  String abspath(String p) {
    var s = windows ? p.replaceAll('/', r'\') : p;
    if (windows) {
      final (drive, rest) = splitDrive(s);
      final (cwdDrive, _) = splitDrive(cwd);
      if (rest.startsWith(sep)) {
        if (drive.isEmpty) s = cwdDrive + s;
      } else if (drive.isEmpty ||
          drive.toLowerCase() == cwdDrive.toLowerCase()) {
        s = '$cwd$sep$rest';
      } else {
        s = '$drive$sep$rest';
      }
    } else if (!s.startsWith('/')) {
      s = '$cwd/$s';
    }
    return normpath(s);
  }

  String _normcase(String s) => windows ? s.toLowerCase() : s;

  /// `os.path.relpath(path, start)`; null where Python raises `ValueError`
  /// (Windows: another drive).
  String? relpath(String path, String start) {
    final (startDrive, startRest) = splitDrive(abspath(start));
    final (pathDrive, pathRest) = splitDrive(abspath(path));
    if (_normcase(startDrive) != _normcase(pathDrive)) return null;
    final startList = startRest.split(sep).where((x) => x.isNotEmpty).toList();
    final pathList = pathRest.split(sep).where((x) => x.isNotEmpty).toList();
    var i = 0;
    while (i < startList.length &&
        i < pathList.length &&
        _normcase(startList[i]) == _normcase(pathList[i])) {
      i++;
    }
    final rel = [
      for (var k = 0; k < startList.length - i; k++) '..',
      ...pathList.sublist(i),
    ];
    return rel.isEmpty ? '.' : rel.join(sep);
  }

  /// `os.path.realpath`: symbolic links resolved when the path exists, else
  /// [abspath].
  String realpath(String p) {
    final a = abspath(p);
    try {
      return Directory.fromRawPath(encodeEscaped(a)).resolveSymbolicLinksSync();
    } on Object {
      return a;
    }
  }

  /// `os.path.dirname` of a normalised absolute path.
  String dirname(String p) {
    final (drive, rest) = splitDrive(p);
    final i = rest.lastIndexOf(sep);
    var head = rest.substring(0, i + 1);
    if (head.isNotEmpty && head.split('').any((c) => c != sep)) {
      var n = head.length;
      while (n > 0 && head[n - 1] == sep) {
        n--;
      }
      head = head.substring(0, n);
    }
    return drive + head;
  }
}
