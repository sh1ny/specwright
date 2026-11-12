import 'dart:convert';
import 'dart:io';

import '../commands/vcs.dart';
import '../fs/walk.dart';
import '../native/libc.dart' as libc;
import 'codec.dart';
import 'document.dart';
import 'git_backend.dart';
import 'git_common.dart';
import 'scripts.dart';
import 'stop.dart';
import 'tool_runner.dart';
import 'walk.dart';

/// The jj backend of `vcs.sh` (`jj_state` and `run_jj_operation` with the
/// functions they call), one function per Python function. Every stop keeps
/// its error code, message, extra fields and exit code.

/// `stringify()` keeps the conditional lazy: a conflicted bookmark has no
/// `normal_target`.
const String bookmarkTemplate =
    r'if(remote, "", json({"name" => name, "conflict" => conflict, '
    r'"target" => stringify(if(normal_target, normal_target.commit_id(), ""))})) ++ "\n"';

VcsStop _usage(String message) => VcsStop('usage', message, code: 2);

/// `vcs.sh`'s `jj(repo, *args)`.
Future<TextResult> jj(VcsSession s, List<String> args) =>
    runText(s.repo, ['jj', ...args]);

/// `vcs.sh`'s `jj_result`: jj's stdout, or the `jj_error` stop.
Future<String> jjResult(
  VcsSession s,
  List<String> args, {
  String? names,
}) async {
  final r = await jj(s, args);
  if (r.code != 0) {
    final said = orElse(
      r.stderr.trim(),
      orElse(r.stdout.trim(), 'jj command failed'),
    );
    throw VcsStop('jj_error', said);
  }
  // [names] says the output lists names: they are decoded strictly (D4)
  return names == null ? r.stdout : r.names(names);
}

/// `vcs.sh`'s `jj_log`.
Future<String> jjLog(
  VcsSession s,
  String revset,
  String template, {
  int? limit,
}) => jjResult(s, [
  'log',
  '--no-graph',
  '--color=never',
  '-r',
  revset,
  '-T',
  template,
  if (limit != null) ...['-n', '$limit'],
]);

/// `vcs.sh`'s `jj_one`: the first line of a one-commit log, trimmed.
Future<String> jjOne(VcsSession s, String revset, String template) async =>
    (await jjLog(s, revset, template, limit: 1)).trim();

/// `vcs.sh`'s `revset_text`: a quoted string literal.
String revsetText(String name) =>
    '"${name.replaceAll(r'\', r'\\').replaceAll('"', r'\"')}"';

/// `vcs.sh`'s `fileset_text`.
String filesetText(String path) => 'root:${revsetText(path)}';

/// `vcs.sh`'s `exact_pattern`.
String exactPattern(String name) => 'exact:${revsetText(name)}';

/// Python's `posixpath.normpath`.
String posixNormpath(String path) {
  if (path.isEmpty) return '.';
  var initial = path.startsWith('/') ? 1 : 0;
  if (initial == 1 && path.startsWith('//') && !path.startsWith('///')) {
    initial = 2;
  }
  final out = <String>[];
  for (final c in path.split('/')) {
    if (c.isEmpty || c == '.') continue;
    if (c != '..' ||
        (initial == 0 && out.isEmpty) ||
        (out.isNotEmpty && out.last == '..')) {
      out.add(c);
    } else if (out.isNotEmpty) {
      out.removeLast();
    }
  }
  final joined = '${'/' * initial}${out.join('/')}';
  return joined.isEmpty ? '.' : joined;
}

/// `vcs.sh`'s `jj_path`: the repo-relative spelling jj uses (`./a`, `a/../a`
/// and `a/` all name `a`).
String jjPath(String path, {bool? windows}) =>
    posixNormpath((windows ?? Platform.isWindows) ? pathText(path) : path);

List<String> _lines(String text) => const LineSplitter().convert(text);

Map<String, Object?> _obj(String line) =>
    decodeJson(line) as Map<String, Object?>;

bool _truthy(Object? v) => v != null && v != false && v != '' && v != 0;

final _spaceOnly = RegExp(r'^\s$');

/// `vcs.sh`'s `jj_state`: [scope] is the commit scope, empty or null for none.
Future<Map<String, Object?>> jjState(VcsSession s, [String? scope]) async {
  final main = s.info.main;
  final scoped0 = scope != null && scope.isNotEmpty;
  final parentText = (await jjLog(
    s,
    '@',
    r'parents.map(|c| json(c.commit_id())).join("\t") ++ "\n"',
  )).trim();
  final parentIds = parentText.isEmpty
      ? <String>[]
      : [for (final p in parentText.split('\t')) decodeJson(p) as String];
  if (parentIds.length != 1) {
    throw VcsStop(
      'ambiguous_branch',
      'working copy @ must have exactly one parent; found ${parentIds.length}',
    );
  }
  final parent = parentIds.first;
  final bookmarksRaw = await jjResult(s, [
    'bookmark',
    'list',
    '--revision',
    '@-',
    '-T',
    bookmarkTemplate,
  ]);
  final bookmarks = <Map<String, Object?>>[];
  for (final line in _lines(bookmarksRaw)) {
    if (line.trim().isEmpty) continue;
    final Map<String, Object?> item;
    try {
      item = _obj(line);
    } on FormatException {
      throw VcsStop('jj_error', 'jj bookmark list returned invalid JSON');
    }
    if (_truthy(item['name'])) bookmarks.add(item);
  }
  final candidates = [
    for (final b in bookmarks)
      if (b['name'] != main) b['name'] as String,
  ];
  final mainAtParent = bookmarks.any((b) => b['name'] == main);
  final relevant = <String>{...candidates, main};
  var scoped = <Map<String, Object?>>[];
  if (scoped0) {
    final raw = await jjResult(s, [
      'bookmark',
      'list',
      scope,
      'glob:**/$scope',
      '-T',
      bookmarkTemplate,
    ]);
    scoped = [
      for (final line in _lines(raw))
        if (line.trim().isNotEmpty) _obj(line),
    ];
    scoped = [
      for (final b in scoped)
        if (b['name'] == scope ||
            ((b['name'] as String?) ?? '').endsWith('/$scope'))
          b,
    ];
    relevant.addAll([for (final b in scoped) b['name'] as String]);
  }
  final conflicts = <String>[];
  for (final name in relevant.toList()..sort()) {
    final conflicted = await jjResult(s, [
      'bookmark',
      'list',
      '--conflicted',
      name,
      '-T',
      bookmarkTemplate,
    ]);
    conflicts.addAll([
      for (final line in _lines(conflicted))
        if (line.trim().isNotEmpty) _obj(line)['name'] as String,
    ]);
  }
  if (conflicts.isNotEmpty) {
    throw VcsStop(
      'ambiguous_branch',
      'conflicted local bookmark(s): '
          '${(conflicts.toSet().toList()..sort()).join(', ')}',
    );
  }
  if (candidates.length > 1) {
    throw VcsStop(
      'ambiguous_branch',
      'multiple local bookmarks point at @-: '
          '${(candidates.toList()..sort()).join(', ')}',
    );
  }
  var branch = candidates.isNotEmpty ? candidates.first : '';
  Map<String, Object?>? selected;
  for (final b in bookmarks) {
    if (b['name'] == branch) {
      selected = b;
      break;
    }
  }
  var behind = <Map<String, Object?>>[];
  var truncated = false;
  if (branch.isEmpty && scoped0) {
    scoped = [
      for (final b in scoped)
        if (_truthy(b['target']) && b['name'] != main) b,
    ];
    if (scoped.length == 1 &&
        await gitAncestor(
          s.scripts,
          s.repo,
          scoped.first['target'] as String,
          parent,
        )) {
      selected = scoped.first;
      branch = selected['name'] as String;
    }
  }
  if (branch.isNotEmpty &&
      scoped0 &&
      selected != null &&
      _truthy(selected['target']) &&
      selected['target'] != parent) {
    const template =
        r'json({"commit" => commit_id, "subject" => description.first_line(), "parents" => parents.len()}) ++ "\n"';
    final record = await jjLog(
      s,
      '${selected['target']}..$parent',
      template,
      limit: 51,
    );
    behind = [
      for (final line in _lines(record))
        if (line.trim().isNotEmpty) _obj(line),
    ];
    if (behind.length > 50) {
      behind = behind.sublist(0, 50);
      truncated = true;
    }
    if (behind.any((item) => (item['parents'] ?? 0) != 1)) {
      throw VcsStop(
        'ambiguous_branch',
        'bookmark recovery range is not linear',
      );
    }
  }
  final status = await jjResult(s, [
    'diff',
    '--summary',
    '-r',
    '@',
  ], names: 'file name');
  final entries = <Map<String, Object?>>[];
  for (final line in _lines(status)) {
    if (line.length >= 3 &&
        'AMDRC'.contains(line[0]) &&
        _spaceOnly.hasMatch(line[1])) {
      entries.add({'status': line[0], 'path': pathText(line.substring(2))});
    }
  }
  final paths = [for (final e in entries) e['path']];
  return {
    'ok': true,
    'backend': 'jj',
    'main': main,
    'branch': branch,
    'on_main': branch.isEmpty && mainAtParent,
    'clean': paths.isEmpty,
    'dirty_paths': paths,
    'dirty': entries,
    'behind': behind,
    'behind_truncated': truncated,
  };
}

/// `state` on the jj backend.
Future<Map<String, Object?>> jjStateDocument(VcsSession s) async =>
    addHeadFields(s, await jjState(s, s.request.scope));

/// `vcs.sh`'s `snapshot_limit`: `snapshot.max-new-file-size` in bytes, 1 MiB
/// when jj does not say or says something unreadable.
Future<int> snapshotLimit(VcsSession s) async {
  final r = await jj(s, ['config', 'get', 'snapshot.max-new-file-size']);
  final text = r.code == 0 ? r.stdout.trim() : '';
  final found = RegExp(
    r'^(\d+)\s*([KMGT]?)(i?)B?$',
    caseSensitive: false,
  ).firstMatch(text);
  if (found == null) return 1024 * 1024;
  final base = found.group(3)!.isNotEmpty ? 1024 : 1000;
  final unit = found.group(2)!.isEmpty ? 'B' : found.group(2)!.toUpperCase();
  var scale = 1;
  for (var i = 0; i < 'BKMGT'.indexOf(unit); i++) {
    scale *= base;
  }
  return int.parse(found.group(1)!) * scale;
}

/// Python's `process_arguments` on Windows: every argument double-quoted, the
/// quotes and trailing backslashes escaped, joined by spaces.
String windowsCommandLine(List<String> args) => args
    .map((a) {
      a = a.replaceAllMapped(
        RegExp(r'(\\*)"'),
        (m) => '${r'\' * (2 * m[1]!.length + 1)}"',
      );
      a = a.replaceAllMapped(RegExp(r'(\\+)$'), (m) => m[1]! * 2);
      return '"$a"';
    })
    .join(' ');

/// `vcs.sh`'s `jj_commit_argv_check`: `too_many_paths` when `jj commit` would
/// not fit on a command line (32,000 bytes of the quoted form on Windows;
/// `sysconf(_SC_ARG_MAX)` less the environment and 4096 elsewhere, 100000 when
/// the system gives none). [argMax] replaces the `sysconf` read.
Future<void> jjCommitArgvCheck(
  VcsSession s,
  List<String> filesets,
  String message, {
  bool? windows,
  int? Function()? argMax,
}) async {
  final argv = ['jj', 'commit', ...filesets, '-m', message];
  final int size;
  final int limit;
  if (windows ?? Platform.isWindows) {
    size = utf8.encode(windowsCommandLine(argv)).length;
    limit = 32000;
  } else {
    final max = (argMax ?? libc.argMax)();
    if (max == null) {
      limit = 100000;
    } else {
      var env = 0;
      Platform.environment.forEach((k, v) {
        env += utf8.encode(k).length + utf8.encode(v).length + 2;
      });
      limit = max - env - 4096;
    }
    size = argv.fold(0, (n, a) => n + utf8.encode(a).length + 1);
  }
  if (size > limit) {
    throw VcsStop(
      'too_many_paths',
      'named paths and message exceed the command-line limit; name a '
          'containing directory instead',
    );
  }
}

bool _isFile(String full) => File(full).existsSync();

bool _isDir(String full) => Directory(full).existsSync();

bool _isLink(String full) => Link(full).existsSync();

/// `vcs.sh`'s `check_directory_snapshot`: one snapshotted file does not cover
/// a named directory, because jj leaves out a new file over the size limit.
/// The directory is walked in process ([walkFiles], D6) and a name that is not
/// UTF-8 stops the walk with [NotUtf8]; the first oversize, unlisted file that
/// Git does not ignore is the `path_not_tracked` stop.
Future<void> checkDirectorySnapshot(
  VcsSession s,
  String path,
  Set<String> listed,
) async {
  final limit = await snapshotLimit(s);
  final oversize = <String>[];
  final root = walkRoot(s.repo, path);
  final base = relpathText(root, s.repo);
  for (final f in walkFiles(root, prefix: base == '.' ? '' : base)) {
    if (!listed.contains(f.name) && f.size > limit) oversize.add(f.name);
  }
  if (oversize.isEmpty) return;
  // NUL-separated both ways: git quotes a non-ASCII path otherwise
  final names = oversize.map((rel) => '$rel\u0000').join();
  final checked = await runTool(s.repo, [
    'git',
    'check-ignore',
    '-z',
    '--stdin',
  ], input: utf8.encode(names));
  final ignored = {
    for (final name in decodeStrict(
      checked.stdout,
      'file name',
    ).split('\u0000'))
      if (name.isNotEmpty) pathText(name),
  };
  for (final rel in oversize) {
    if (!ignored.contains(rel)) {
      throw VcsStop(
        'path_not_tracked',
        '$rel is not tracked in the jj working copy: it is larger than '
            'snapshot.max-new-file-size ($limit bytes)',
        extra: {'path': rel},
      );
    }
  }
}

/// `vcs.sh`'s `check_tracked`: every named path that exists must be covered by
/// the working-copy snapshot, else `path_not_tracked`.
Future<void> checkTracked(
  VcsSession s,
  List<String> paths,
  List<String> filesets,
) async {
  final present = <(String, String)>[
    for (var i = 0; i < paths.length && i < filesets.length; i++)
      if (_isFile(walkRoot(s.repo, paths[i])) ||
          _isDir(walkRoot(s.repo, paths[i])) ||
          _isLink(walkRoot(s.repo, paths[i])))
        (paths[i], filesets[i]),
  ];
  if (present.isEmpty) return;
  final named = [for (final p in present) p.$2];
  final listed = [
    for (final l in _lines(
      await jjResult(s, [
        'file',
        'list',
        '-r',
        '@',
        ...named,
      ], names: 'file name'),
    ))
      pathText(l),
  ];
  List<String>? parentListed;
  for (final (path, _) in present) {
    var norm = path;
    while (norm.endsWith('/')) {
      norm = norm.substring(0, norm.length - 1);
    }
    if (norm.isEmpty) norm = '.';
    final full = walkRoot(s.repo, path);
    var covered =
        norm == '.' || listed.any((i) => i == norm || i.startsWith('$norm/'));
    if (!covered && _isDir(full)) {
      // a directory whose tracked files were all deleted names those deletions
      parentListed ??= [
        for (final l in _lines(
          await jjResult(s, [
            'file',
            'list',
            '-r',
            '@-',
            ...named,
          ], names: 'file name'),
        ))
          pathText(l),
      ];
      covered = parentListed.any((i) => i.startsWith('$norm/'));
    }
    if (covered) {
      if (_isDir(full)) await checkDirectorySnapshot(s, path, listed.toSet());
      continue;
    }
    final String reason;
    if (_isFile(full) &&
        !_isLink(full) &&
        File(full).lengthSync() > await snapshotLimit(s)) {
      reason =
          'it is larger than snapshot.max-new-file-size '
          '(${await snapshotLimit(s)} bytes)';
    } else {
      reason = 'it is ignored, or larger than snapshot.max-new-file-size';
    }
    throw VcsStop(
      'path_not_tracked',
      '$path is not tracked in the jj working copy: $reason',
      extra: {'path': path},
    );
  }
}

/// `vcs.sh`'s `jj_verify_head`: Git's HEAD must be [branch]'s tip.
Future<String> jjVerifyHead(VcsSession s, String branch) async {
  final head = (await gitChecked(s.scripts, s.repo, [
    'rev-parse',
    'HEAD',
  ])).stdout.trim();
  final tip = (await gitChecked(s.scripts, s.repo, [
    'rev-parse',
    'refs/heads/$branch',
  ])).stdout.trim();
  if (head != tip) {
    throw VcsStop(
      'jj_error',
      'Git HEAD $head differs from bookmark $branch at $tip',
    );
  }
  return head;
}

final _wideSpace = RegExp(r'\s{2,}');

Future<List<String>> _resolveList(VcsSession s, String revision) async {
  final listed = await jj(s, ['resolve', '--list', '-r', revision]);
  return [
    for (final line in _lines(listed.names('file name')))
      if (line.trim().isNotEmpty) pathText(line.trim().split(_wideSpace).first),
  ];
}

/// `vcs.sh`'s `jj_switch`: moves the working copy onto [target], carrying its
/// edits. A carry that conflicts is undone and is the `carry_conflict` stop.
Future<void> jjSwitch(VcsSession s, String target) async {
  if (await jjOne(s, '@', 'if(empty, "1", "0")') == '1') {
    await jjResult(s, ['new', revsetText(target)]);
    return;
  }
  final old = await jjOne(s, '@-', 'commit_id');
  await jjResult(s, ['rebase', '-r', '@', '-o', revsetText(target)]);
  if (await jjOne(s, '@', 'if(conflict, "1", "0")') != '1') return;
  final names = await _resolveList(s, '@');
  await jjResult(s, ['rebase', '-r', '@', '-o', revsetText(old)]);
  throw VcsStop(
    'carry_conflict',
    'edits conflict with $target in: ${names.join(', ')}; nothing was moved',
    extra: {'paths': names},
  );
}

/// `vcs.sh`'s `jj_advance`.
Future<Map<String, Object?>> jjAdvance(VcsSession s) async {
  final scope = s.request.scope;
  if (scope == null) throw _usage('advance requires --scope');
  final state = await jjState(s, scope);
  final branch = state['branch'] as String;
  final expected = s.request.branch;
  if (expected != null && expected.isNotEmpty && expected != branch) {
    throw VcsStop(
      'wrong_branch',
      'expected branch ${pyRepr(expected)}, resolved ${pyRepr(branch)}',
    );
  }
  final behind = (state['behind'] as List).cast<Map<String, Object?>>();
  if (behind.isEmpty) {
    return {'ok': true, 'backend': 'jj', 'branch': branch, 'advanced': false};
  }
  final tip = (await gitChecked(s.scripts, s.repo, [
    'rev-parse',
    'refs/heads/$branch',
  ])).stdout.trim();
  if ((await jjOne(s, '${revsetText(tip)} & ::@-', 'commit_id')).isEmpty) {
    throw VcsStop(
      'ambiguous_branch',
      'bookmark $branch is not an ancestor of @-',
    );
  }
  final pattern = RegExp(
    '^[A-Za-z][A-Za-z0-9-]*\\(${RegExp.escape(scope)}\\): ',
  );
  final truncated = state['behind_truncated'] == true;
  if (truncated ||
      !behind.every((i) => pattern.hasMatch((i['subject'] ?? '') as String))) {
    final listing = behind
        .map((i) => '${i['commit']} ${i['subject'] ?? ''}')
        .join('; ');
    final shown = truncated ? ' (first ${behind.length} shown)' : '';
    throw VcsStop(
      'bookmark_behind',
      'bookmark $branch is behind commits outside scope $scope$shown: '
          '$listing',
      extra: {'commits': behind},
    );
  }
  final target = await jjOne(s, '@-', 'commit_id');
  await jjResult(s, ['bookmark', 'set', branch, '-r', revsetText(target)]);
  return {
    'ok': true,
    'backend': 'jj',
    'branch': branch,
    'advanced': true,
    'commit': await jjVerifyHead(s, branch),
  };
}

/// `vcs.sh`'s `jj_bookmark`: the commit the local bookmark [name] points at.
/// A conflicted or targetless one is `''` when [allowConflict], else the
/// `ambiguous_branch` stop.
Future<String> jjBookmark(
  VcsSession s,
  String name, {
  bool allowConflict = false,
}) async {
  final raw = await jjResult(s, [
    'bookmark',
    'list',
    exactPattern(name),
    '-T',
    bookmarkTemplate,
  ]);
  final items = [
    for (final line in _lines(raw))
      if (line.trim().isNotEmpty) _obj(line),
  ];
  if (items.isEmpty) {
    throw VcsStop('no_such_branch', 'bookmark $name does not exist');
  }
  final item = items.first;
  if (_truthy(item['conflict']) || !_truthy(item['target'])) {
    if (allowConflict) return '';
    throw VcsStop('ambiguous_branch', 'bookmark $name is conflicted');
  }
  return item['target'] as String;
}

/// `vcs.sh`'s `conflict_paths`.
Future<List<String>> conflictPaths(VcsSession s, String revision) =>
    _resolveList(s, revision);

/// `vcs.sh`'s `network_jj`: `jj <args>` in the repo, through `as.sh <login>`
/// when `origin` is on GitHub.
Future<TextResult> networkJj(
  VcsSession s,
  List<String> args,
  String? login,
) async {
  final github = isGithubUrl(await remoteUrl(s.scripts, s.repo));
  final who = await fenceLogin(s.scripts, s.repo, github: github, login: login);
  final result = github
      ? await runAs(s.scripts, s.repo, who, ['jj', ...args])
      : await jj(s, args);
  if (result.code != 0) {
    final said = orElse(result.stderr, result.stdout).trim();
    throw VcsStop(
      github && result.code == 3 ? 'fence_failed' : 'git_network_error',
      said.isNotEmpty ? said : 'jj network operation failed',
      code: 3,
    );
  }
  return result;
}

/// `vcs.sh`'s `jj_fetch_main`: `git fetch` of the main branch, then the commit
/// it fetched.
Future<String> jjFetchMain(VcsSession s, String? login) async {
  await networkGit(s.scripts, s.repo, [
    'fetch',
    if (s.request.quiet) '-q',
    if (s.request.noTags) '--no-tags',
    '--refmap=',
    'origin',
    'refs/heads/${s.info.main}',
  ], login);
  return (await gitChecked(s.scripts, s.repo, [
    'rev-parse',
    '--verify',
    'FETCH_HEAD^{commit}',
  ], error: 'fetch_failed')).stdout.trim();
}

/// `vcs.sh`'s `jj_find_merge`: the merge of [branchId] into [mainId] whose
/// subject is [subject], or `''`.
Future<String> jjFindMerge(
  VcsSession s,
  String mainId,
  String branchId,
  String subject,
) async {
  final revset =
      'merges() & children(${revsetText(mainId)}) & '
      'children(${revsetText(branchId)})';
  const template =
      r'json({"commit" => commit_id, "subject" => description.first_line(), '
      r'"parents" => stringify(parents.map(|c| c.commit_id()).join(" "))}) ++ "\n"';
  for (final line in _lines(await jjLog(s, revset, template))) {
    if (line.trim().isEmpty) continue;
    final item = _obj(line);
    final parents = (item['parents'] as String).split(' ');
    final first = (item['subject'] as String).replaceAll(RegExp(r'\r+$'), '');
    if (parents.length == 2 &&
        parents[0] == mainId &&
        parents[1] == branchId &&
        first == subject) {
      return item['commit'] as String;
    }
  }
  return '';
}

/// Reads the `--message-file` as strict UTF-8 with its newlines untouched; a
/// missing file is the `internal_error` Python's `open` gave.
String _readMessage(String path) {
  final List<int> bytes;
  try {
    bytes = File(path).readAsBytesSync();
  } on FileSystemException {
    throw StateError('[Errno 2] No such file or directory: ${pyRepr(path)}');
  }
  return utf8.decode(bytes);
}

/// `vcs.sh`'s `jj_merge`.
Future<Map<String, Object?>> jjMerge(VcsSession s) async {
  final branch = requireBranch(s);
  final messageFile = s.request.messageFile ?? '';
  if (messageFile.isEmpty) throw _usage('merge requires --message-file');
  final main = s.info.main;
  final state = await jjState(s);
  final mainId = await jjBookmark(s, main);
  final branchId = await jjBookmark(s, branch);
  if ((await jjOne(
    s,
    '${revsetText(branchId)} & ::${revsetText(mainId)}',
    'commit_id',
  )).isNotEmpty) {
    return {
      'ok': true,
      'backend': 'jj',
      'branch': branch,
      'commit': mainId,
      'already_merged': true,
    };
  }
  final message = _readMessage(messageFile);
  final subject = _lines(message).firstOrNull ?? '';
  var merge = await jjFindMerge(s, mainId, branchId, subject);
  final resumed =
      merge.isNotEmpty && await jjOne(s, '@-', 'commit_id') == merge;
  if (!resumed && state['on_main'] != true) {
    throw VcsStop(
      'wrong_branch',
      'expected to be on ${pyRepr(main)}, currently on '
          '${pyRepr(state['branch'] as String)}',
    );
  }
  if (merge.isEmpty) {
    await jjResult(s, [
      'new',
      '--no-edit',
      '-m',
      message,
      revsetText(mainId),
      revsetText(branchId),
    ]);
    merge = await jjFindMerge(s, mainId, branchId, subject);
    if (merge.isEmpty) {
      throw VcsStop(
        'jj_error',
        'could not find the merge commit that jj new created',
      );
    }
  }
  if (!resumed) {
    if (await jjOne(s, revsetText(merge), 'if(conflict, "1", "0")') == '1') {
      final names = await conflictPaths(s, merge);
      await jjResult(s, ['abandon', revsetText(merge)]);
      throw VcsStop(
        'conflicted',
        'merging $branch into $main conflicts in: ${names.join(', ')}; the '
            'merge was abandoned',
        extra: {'paths': names},
      );
    }
    try {
      await jjSwitch(s, merge);
    } on VcsStop catch (stop) {
      if (stop.error == 'carry_conflict') {
        await jjResult(s, ['abandon', revsetText(merge)]);
      }
      rethrow;
    }
  }
  await jjResult(s, ['bookmark', 'set', main, '-r', revsetText(merge)]);
  return {
    'ok': true,
    'backend': 'jj',
    'branch': branch,
    'commit': await jjVerifyHead(s, main),
  };
}

/// `vcs.sh`'s `jj_delete`.
Future<Map<String, Object?>> jjDelete(VcsSession s) async {
  final branch = requireBranch(s);
  final force = s.request.force;
  await jjBookmark(s, branch, allowConflict: force);
  if (!force) {
    final mainId = await jjBookmark(s, s.info.main);
    if ((await jjOne(
      s,
      '${revsetText(branch)} & ::${revsetText(mainId)}',
      'commit_id',
    )).isEmpty) {
      throw VcsStop(
        'not_merged',
        'branch $branch is not merged into ${s.info.main}',
      );
    }
  }
  await jjResult(s, ['bookmark', 'forget', exactPattern(branch)]);
  return {'ok': true, 'backend': 'jj', 'branch': branch};
}

/// `vcs.sh`'s `jj_pull`.
Future<Map<String, Object?>> jjPull(VcsSession s, String? login) async {
  final main = s.info.main;
  final wasOnMain = (await jjState(s))['on_main'] == true;
  final old = await jjBookmark(s, main);
  final fetched = await jjFetchMain(s, login);
  final branch = wasOnMain ? main : '';
  if (await gitAncestor(s.scripts, s.repo, fetched, old)) {
    return {
      'ok': true,
      'backend': 'jj',
      'branch': branch,
      'commit': old,
      'moved': false,
    };
  }
  if (!await gitAncestor(s.scripts, s.repo, old, fetched)) {
    throw VcsStop(
      'not_fast_forward',
      'local $main at $old and origin $main at $fetched have diverged',
    );
  }
  await networkJj(s, [
    'git',
    'fetch',
    '--remote',
    'origin',
    '--branch',
    exactPattern(main),
  ], login);
  var current = await jjBookmark(s, main, allowConflict: true);
  final remote = await jjOne(
    s,
    '${revsetText(main)}@${revsetText('origin')}',
    'commit_id',
  );
  if (current.isNotEmpty &&
      remote.isNotEmpty &&
      current != remote &&
      await gitAncestor(s.scripts, s.repo, current, remote)) {
    await jjResult(s, ['bookmark', 'set', main, '-r', revsetText(remote)]);
    current = remote;
  }
  if (current.isEmpty || !await gitAncestor(s.scripts, s.repo, old, current)) {
    await jjResult(s, [
      'bookmark',
      'set',
      main,
      '-r',
      revsetText(old),
      '--allow-backwards',
    ]);
    throw VcsStop(
      'not_fast_forward',
      'origin $main moved during the pull; local $main was set back to $old',
    );
  }
  if (wasOnMain) {
    try {
      await jjSwitch(s, current);
    } on VcsStop catch (stop) {
      if (stop.error == 'carry_conflict') {
        // a failed switch leaves main where the pull found it
        await jjResult(s, [
          'bookmark',
          'set',
          main,
          '-r',
          revsetText(old),
          '--allow-backwards',
        ]);
      }
      rethrow;
    }
  }
  return {
    'ok': true,
    'backend': 'jj',
    'branch': branch,
    'commit': current,
    'moved': true,
  };
}

/// `vcs.sh`'s `jj_push`.
Future<Map<String, Object?>> jjPush(VcsSession s, String? login) async {
  final branch = requireBranch(s);
  final main = s.info.main;
  final current = (await jjState(s))['branch'] as String;
  if (current != branch) {
    throw VcsStop(
      'wrong_branch',
      'expected branch ${pyRepr(branch)}, currently on ${pyRepr(current)}',
    );
  }
  const template =
      r'json({"commit" => commit_id, "conflict" => conflict, "subject" => description.first_line(), '
      r'"described" => if(description.trim(), "1", "0")}) ++ "\n"';
  final commits = [
    for (final line in _lines(
      await jjLog(s, '${revsetText(main)}..${revsetText(branch)}', template),
    ))
      if (line.trim().isNotEmpty) _obj(line),
  ];
  var bad = [
    for (final c in commits)
      if (_truthy(c['conflict'])) c['commit'] as String,
  ];
  if (bad.isNotEmpty) {
    throw VcsStop(
      'conflicted',
      'commit(s) in $main..$branch are conflicted: ${bad.join(', ')}',
      extra: {'commits': bad},
    );
  }
  bad = [
    for (final c in commits)
      if (c['described'] != '1') c['commit'] as String,
  ];
  if (bad.isNotEmpty) {
    throw VcsStop(
      'undescribed',
      'commit(s) in $main..$branch have no description: ${bad.join(', ')}',
      extra: {'commits': bad},
    );
  }
  await networkJj(s, [
    'git',
    'push',
    '--remote',
    'origin',
    '--bookmark',
    exactPattern(branch),
  ], login);
  return {'ok': true, 'backend': 'jj', 'branch': branch};
}

/// `vcs.sh`'s `run_jj_operation` for [command]. [windows] overrides the OS for
/// the commit's command-line size check, [argMax] replaces its `sysconf` read.
Future<Map<String, Object?>> runJjOperation(
  VcsSession session,
  String command, {
  bool? windows,
  int? Function()? argMax,
}) async {
  // jj runs in the Git work tree's root, not in the directory `--repo` named.
  final s = VcsSession(
    session.ctx,
    session.info.repo,
    session.code,
    session.info,
    session.scripts,
  );
  final request = s.request;
  final given = request.login;
  final login = given != null && given.isNotEmpty ? given : s.info.login;
  switch (command) {
    case 'branch-create':
      final branch = requireBranch(s);
      await jjResult(s, ['bookmark', 'create', branch, '-r', '@-']);
      return {
        'ok': true,
        'backend': 'jj',
        'branch': branch,
        'commit': await jjVerifyHead(s, branch),
      };
    case 'switch':
      final branch = requireBranch(s);
      await jjState(s);
      await jjSwitch(s, branch);
      return {'ok': true, 'backend': 'jj', 'branch': branch};
    case 'advance':
      return jjAdvance(s);
    case 'commit':
      final branch = requireBranch(s);
      final messageFile = request.messageFile ?? '';
      if (messageFile.isEmpty || request.paths.isEmpty) {
        throw _usage(
          'commit requires --message-file and at least one path after --',
        );
      }
      final state = await jjState(s);
      // jj_state reads main as branch ""; a commit on main names it, as on Git
      final current = state['on_main'] == true
          ? s.info.main
          : state['branch'] as String;
      if (current != branch) {
        throw VcsStop(
          'wrong_branch',
          'expected branch ${pyRepr(branch)}, currently on ${pyRepr(current)}',
        );
      }
      final paths = [
        for (final p in request.paths) jjPath(p, windows: windows),
      ];
      final filesets = [for (final p in paths) filesetText(p)];
      final message = _readMessage(messageFile);
      await jjCommitArgvCheck(
        s,
        filesets,
        message,
        windows: windows,
        argMax: argMax,
      );
      await checkTracked(s, paths, filesets);
      final changed = await jjResult(s, [
        'diff',
        '-r',
        '@',
        '--name-only',
        ...filesets,
      ]);
      if (changed.trim().isEmpty) {
        throw VcsStop(
          'nothing_to_commit',
          'no changes to commit in the named paths',
        );
      }
      await jjResult(s, ['commit', ...filesets, '-m', message]);
      await jjResult(s, ['bookmark', 'set', branch, '-r', '@-']);
      return {
        'ok': true,
        'backend': 'jj',
        'branch': branch,
        'commit': await jjVerifyHead(s, branch),
      };
    case 'merge':
      return jjMerge(s);
    case 'delete-branch':
      return jjDelete(s);
    case 'fetch-main':
      final sha = await jjFetchMain(s, login);
      return {'ok': true, 'backend': 'jj', 'ref': sha, 'commit': sha};
    case 'pull':
      return jjPull(s, login);
    case 'push':
      return jjPush(s, login);
  }
  throw _usage('unknown command: $command');
}
