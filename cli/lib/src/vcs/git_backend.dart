import 'dart:convert';
import 'dart:io';

import '../commands/vcs.dart';
import '../process/launch.dart' show launch;
import 'codec.dart';
import 'git_common.dart';
import 'stop.dart';
import 'tool_runner.dart';

/// The Git backend of `vcs.sh` (`git_state`, `run_git_operation`), one
/// function per Python function. Every stop keeps its error code, message and
/// exit code.

/// `vcs.sh`'s `require_branch`: `--branch`, or the usage stop (exit 2).
String requireBranch(VcsSession s) {
  final branch = s.request.branch;
  if (branch == null || branch.isEmpty) {
    throw VcsStop('usage', 'missing --branch', code: 2);
  }
  return branch;
}

VcsStop _usage(String message) => VcsStop('usage', message, code: 2);

/// One `git status --porcelain=v1 -z` record as the bytes Git wrote: the two
/// status bytes, the path, and for a rename or copy the source path that
/// follows it. Nothing is decoded, trimmed or rewritten.
class ZRecord {
  ZRecord(this.status, this.path, this.source);

  /// The two status characters, `XY`.
  final List<int> status;
  final List<int> path;

  /// The source path of a rename or copy (`R` or `C` in either status column);
  /// null for any other record.
  final List<int>? source;

  /// Every path of the record decoded strictly (D4): a name that is not UTF-8
  /// is a [NotUtf8], never a look-alike. A caller drops the records it does
  /// not use before it decodes, so an unrelated name never stops it.
  ZEntry decode() => ZEntry(
    String.fromCharCodes(status),
    decodeStrict(path, 'file name'),
    source == null ? null : decodeStrict(source!, 'file name'),
  );
}

/// A [ZRecord] decoded strictly: the status, the path as Git named it, and the
/// source path of a rename or copy.
class ZEntry {
  ZEntry(this.status, this.path, this.source);

  final String status;
  final String path;
  final String? source;
}

/// The records of a `-z` porcelain listing, framed and paired but not read.
class ZRecords {
  ZRecords(this.records, this.complete);

  final List<ZRecord> records;

  /// True when the bytes are empty or end with the NUL that closes a whole
  /// record, every record is a status, a space and a path, and a rename or
  /// copy has its source path. False for a final unterminated field, a short
  /// record or a rename cut before its source.
  final bool complete;
}

/// The framing [parsePorcelain] and [parseZRecords] share, over code units:
/// NUL separates the records, a record is `XY`, a space and a path, and a
/// record whose status holds `R` or `C` is followed by its source path as the
/// next record. A record shorter than four units is skipped; a rename with no
/// source record left gets an empty one. [records] is the listing split on NUL.
List<({List<int> status, List<int> path, List<int>? source})> _pairRecords(
  List<List<int>> records,
) {
  final out = <({List<int> status, List<int> path, List<int>? source})>[];
  var next = 0;
  while (next < records.length) {
    final record = records[next++];
    if (record.length < 4) continue;
    final status = record.sublist(0, 2);
    final path = record.sublist(3);
    List<int>? source;
    if (status.contains(0x52) || status.contains(0x43)) {
      source = next < records.length ? records[next++] : const <int>[];
    }
    out.add((status: status, path: path, source: source));
  }
  return out;
}

/// Frames and pairs the raw records of a `git status --porcelain=v1 -z` output
/// and changes no byte. A caller drops the records it does not need, then
/// decodes the kept ones with [ZRecord.decode]: the `XY ` prefix is cut once
/// (the path is what follows the third byte), a rename or copy takes the next
/// NUL record as its source, and each path is decoded strictly. [parsePorcelain]
/// keeps its slash rewrite ([pathText]) at its own call, so the VCS state is
/// unchanged; the undo planner uses this parser and rewrites nothing.
///
/// C50: an inventory read is complete only when its stdout is empty or ends
/// with the command's own record terminator after a whole logical record (NUL
/// with that `-z` format's field count, where a rename or copy is one record
/// with its source and a `--name-status` pair is one; LF for `for-each-ref` and
/// `rev-list`), with no stderr byte and no recorded stream error. A final
/// unterminated field or a short record is a malformed ending and a failed
/// read, distinct from the reader's own early stop on a refusal, which reports
/// that refusal. [ZRecords.complete] answers this for a porcelain listing and
/// [readInventory] applies the whole rule to a finished tool run.
ZRecords parseZRecords(List<int> bytes) {
  final tokens = <List<int>>[];
  var start = 0;
  for (var i = 0; i < bytes.length; i++) {
    if (bytes[i] == 0) {
      tokens.add(bytes.sublist(start, i));
      start = i + 1;
    }
  }
  var complete = start == bytes.length;
  if (!complete) tokens.add(bytes.sublist(start));
  var next = 0;
  while (complete && next < tokens.length) {
    final record = tokens[next++];
    if (record.length < 4) {
      complete = false;
    } else if (record.take(2).any((b) => b == 0x52 || b == 0x43)) {
      if (next >= tokens.length) {
        complete = false;
      } else {
        next++;
      }
    }
  }
  return ZRecords([
    for (final r in _pairRecords(tokens)) ZRecord(r.status, r.path, r.source),
  ], complete);
}

/// How a listing's records end: [nul] for `-z` output (`fields` NUL-ended
/// fields make one logical record) and [lf] for line formats.
enum Framing { nul, lf }

/// The failed read [label] names: a `vcs_error` stop. [stderr] is cut to 4 KiB.
VcsStop failedRead(
  String label, {
  int? exitCode,
  List<int> stderr = const <int>[],
  Object? streamError,
  String? why,
}) {
  final said = decodeText(stderr.take(4096).toList()).trim();
  final String message;
  if (exitCode != null && exitCode != 0) {
    message = said.isNotEmpty
        ? '$label failed: $said'
        : '$label failed with exit status $exitCode';
  } else if (said.isNotEmpty) {
    message = '$label wrote to stderr, so its output is not trusted: $said';
  } else if (streamError != null) {
    message = '$label output ended with an error: $streamError';
  } else {
    message =
        '$label output ended inside a record${why == null ? '' : ' ($why)'}';
  }
  return VcsStop('vcs_error', message);
}

/// The first part of the C50 test, for a read that frames its own records: a
/// [failedRead] unless the tool exited 0 with no stderr byte and no recorded
/// stream error.
void checkRead(ToolResult r, String label) {
  if (r.exitCode != 0 || r.stderr.isNotEmpty || r.streamError != null) {
    throw failedRead(
      label,
      exitCode: r.exitCode,
      stderr: r.stderr,
      streamError: r.streamError,
    );
  }
}

/// Checks that a finished tool run is a complete read (C50) and returns its
/// logical records as raw bytes: [fields] fields per record for [Framing.nul],
/// one line each for [Framing.lf]. Anything else is a [failedRead] naming
/// [label], never a shorter listing: a non-zero exit, any stderr byte, a
/// recorded stream error, or an end that is not a record terminator after a
/// whole record. Empty stdout is a complete, empty listing.
List<List<List<int>>> readInventory(
  ToolResult r,
  String label, {
  Framing framing = Framing.nul,
  int fields = 1,
}) {
  checkRead(r, label);
  final bytes = r.stdout;
  final terminator = framing == Framing.nul ? 0 : 0x0a;
  final tokens = <List<int>>[];
  var start = 0;
  for (var i = 0; i < bytes.length; i++) {
    if (bytes[i] == terminator) {
      tokens.add(bytes.sublist(start, i));
      start = i + 1;
    }
  }
  final width = framing == Framing.nul ? fields : 1;
  if (start != bytes.length) {
    throw failedRead(label, why: 'the last record has no terminator');
  }
  if (tokens.length % width != 0) {
    throw failedRead(label, why: 'a record is cut before its last field');
  }
  return [
    for (var i = 0; i < tokens.length; i += width) tokens.sublist(i, i + width),
  ];
}

/// A porcelain read through the shared reader: [checkRead], then
/// [parseZRecords], and a listing that does not end whole is a [failedRead].
List<ZRecord> readPorcelain(ToolResult r, String label) {
  checkRead(r, label);
  final parsed = parseZRecords(r.stdout);
  if (!parsed.complete) {
    throw failedRead(label, why: 'a record is cut or has no terminator');
  }
  return parsed.records;
}

/// `vcs.sh`'s `parse_porcelain` on `git status --porcelain -z` output: the
/// paths (a rename or copy adds its source) and the entries, with `\` made `/`
/// in each path ([pathText]). [out] is the output, framed by the pairing
/// [parseZRecords] uses.
({List<String> paths, List<Map<String, Object?>> entries}) parsePorcelain(
  String out,
) {
  final paths = <String>[];
  final entries = <Map<String, Object?>>[];
  for (final r in _pairRecords([
    for (final record in out.split('\u0000')) record.codeUnits,
  ])) {
    final status = String.fromCharCodes(r.status);
    final name = pathText(String.fromCharCodes(r.path));
    final entry = <String, Object?>{'status': status, 'path': name};
    paths.add(name);
    final source = r.source;
    if (source != null) {
      final from = pathText(String.fromCharCodes(source));
      entry['from'] = from;
      paths.add(from);
    }
    entries.add(entry);
  }
  return (paths: paths, entries: entries);
}

/// `vcs.sh`'s `git_current`: the current branch, empty when detached.
Future<String> gitCurrent(VcsSession s) async {
  final r = await git(s.scripts, s.repo, ['branch', '--show-current']);
  if (r.code != 0) {
    final said = r.stderr.trim();
    throw VcsStop(
      'git_error',
      said.isNotEmpty ? said : 'git branch --show-current failed',
    );
  }
  return r.names('branch name').trim();
}

/// The state's `git status` for the undo planner ([VcsContext.readOnlyStatus],
/// C10): it runs read-only, with `GIT_OPTIONAL_LOCKS=0` and
/// `-c core.fsmonitor=false`, drains stdout without buffering or decoding it and
/// checks only the command's result. A failed status is still `git_error`;
/// stderr output or a stream error at exit 0 is a `vcs_error`, the C50 rule.
Future<void> _drainStatus(VcsSession s) async {
  final command = [
    'git',
    '-c',
    'core.fsmonitor=false',
    '--no-optional-locks',
    'status',
    '--porcelain',
    '-z',
  ];
  final base = s.scripts.environmentFor?.call(command) ?? Platform.environment;
  final r = await launch(
    command,
    cwd: s.repo,
    environment: {...base, 'GIT_OPTIONAL_LOCKS': '0'},
    stdoutSink: (_) async {},
  );
  if (r.exitCode != 0) {
    final said = decodeText(r.stderr).trim();
    throw VcsStop(
      'git_error',
      said.isNotEmpty ? said : 'git status --porcelain -z failed',
    );
  }
  checkRead(r, 'git status');
}

/// `vcs.sh`'s `git_state`.
Future<Map<String, Object?>> gitState(VcsSession s) async {
  final branch = await gitCurrent(s);
  final ({List<String> paths, List<Map<String, Object?>> entries}) parsed;
  if (s.ctx.readOnlyStatus) {
    await _drainStatus(s);
    parsed = (paths: <String>[], entries: <Map<String, Object?>>[]);
  } else {
    final status = await git(s.scripts, s.repo, [
      'status',
      '--porcelain',
      '-z',
    ]);
    if (status.code != 0) {
      final said = status.stderr.trim();
      throw VcsStop(
        'git_error',
        said.isNotEmpty ? said : 'git status --porcelain -z failed',
      );
    }
    parsed = parsePorcelain(status.names('file name'));
  }
  return {
    'ok': true,
    'backend': 'git',
    'main': s.info.main,
    'branch': branch,
    'on_main': branch == s.info.main,
    'clean': parsed.paths.isEmpty,
    'dirty_paths': parsed.paths,
    'dirty': parsed.entries,
    'behind': <Object?>[],
    'behind_truncated': false,
    if (s.info.jjPresent) 'jj_present': true,
  };
}

/// `vcs.sh`'s `current_state` for a Git or jj [state]: adds `head` (the
/// commit HEAD names, empty when there is none) and, when `--branch` was
/// given, `branch_matches`. `--branch` is reported, never a stop.
Future<Map<String, Object?>> addHeadFields(
  VcsSession s,
  Map<String, Object?> state,
) async {
  final head = await git(s.scripts, s.repo, [
    'rev-parse',
    '--verify',
    '-q',
    'HEAD^{commit}',
  ]);
  state['head'] = head.code == 0 ? head.stdout.trim() : '';
  final branch = s.request.branch;
  if (branch != null && branch.isNotEmpty) {
    state['branch_matches'] = state['branch'] == branch;
  }
  return state;
}

/// `state` on the Git backend.
Future<Map<String, Object?>> gitStateDocument(VcsSession s) async =>
    addHeadFields(s, await gitState(s));

/// `vcs.sh`'s `check_branch`: the stop `wrong_branch` unless the current
/// branch is [expected].
Future<String> checkBranch(VcsSession s, String expected) async {
  final current = await gitCurrent(s);
  if (current != expected) {
    throw VcsStop(
      'wrong_branch',
      'expected branch ${pyRepr(expected)}, currently on ${pyRepr(current)}',
    );
  }
  return current;
}

Future<String> _head(VcsSession s) async =>
    (await gitChecked(s.scripts, s.repo, ['rev-parse', 'HEAD'])).stdout.trim();

String? _loginFor(VcsSession s) {
  final given = s.request.login;
  return given != null && given.isNotEmpty ? given : s.info.login;
}

/// `vcs.sh`'s `run_git_operation` for `command`. [windows] overrides the OS
/// for the commit's command-line size check.
///
/// Constraint C29: on Windows a resolved line of exactly 32,767 visible units
/// is now refused before start as `Unrepresentable`, where it used to fail at
/// start; each caller maps that refusal as it already maps `Unrepresentable`,
/// and no mapping changes: a direct launch through the VCS mapper reports
/// `not_utf8` (a Git `commit` refused there leaves what `git add` staged;
/// `sw vcs merge`, which reported `merge_failed`, now reports `not_utf8`), a
/// GitButler commit keeps `too_many_paths` (D1), and a fenced Git network call
/// keeps `git_network_error`, exit 3.
Future<Map<String, Object?>> runGitOperation(
  VcsSession s,
  String command, {
  bool? windows,
}) async {
  final request = s.request;
  final repo = s.repo;
  final scripts = s.scripts;
  final main = s.info.main;
  final remote = s.info.remote;
  final connection = s.info.connection;
  final messageFile = request.messageFile ?? '';
  switch (command) {
    case 'branch-create':
      final branch = requireBranch(s);
      final r = await gitChecked(scripts, repo, ['checkout', '-b', branch]);
      return {
        'ok': true,
        'backend': 'git',
        'branch': branch,
        'output': r.stdout.trim(),
      };
    case 'switch':
      final branch = requireBranch(s);
      final r = await gitChecked(scripts, repo, ['checkout', branch]);
      return {
        'ok': true,
        'backend': 'git',
        'branch': branch,
        'output': r.stdout.trim(),
      };
    case 'commit':
      // C29: on Windows a resolved `git commit` line of exactly 32,767
      // visible units is refused before start as `Unrepresentable`, which the
      // VCS mapper reports as `not_utf8`, as before. The refusal comes after
      // `git add`, so what it staged stays staged.
      final branch = requireBranch(s);
      final paths = request.paths;
      if (messageFile.isEmpty || paths.isEmpty) {
        throw _usage(
          'commit requires --message-file and at least one path after --',
        );
      }
      if (windows ?? Platform.isWindows) {
        var size = 0;
        for (final p in paths) {
          size += utf8.encode(p).length + 1;
        }
        size += utf8.encode(messageFile).length;
        if (size > 32000) {
          throw VcsStop(
            'too_many_paths',
            'named Git paths exceed the Windows command-line limit; name a '
                'containing directory instead',
          );
        }
      }
      await checkBranch(s, branch);
      await gitChecked(scripts, repo, ['add', '--', ...paths]);
      final result = await git(scripts, repo, [
        'commit',
        '-F',
        messageFile,
        '--',
        ...paths,
      ]);
      if (result.code != 0) {
        final said = orElse(result.stderr, result.stdout).trim();
        throw VcsStop(
          'git_commit_failed',
          said.isNotEmpty ? said : 'git commit failed',
        );
      }
      return {
        'ok': true,
        'backend': 'git',
        'branch': branch,
        'commit': await _head(s),
      };
    case 'merge':
      final branch = requireBranch(s);
      if (messageFile.isEmpty) throw _usage('merge requires --message-file');
      await checkBranch(s, main);
      await gitChecked(scripts, repo, [
        'merge',
        '--no-ff',
        branch,
        '-F',
        messageFile,
      ], error: 'merge_failed');
      return {
        'ok': true,
        'backend': 'git',
        'branch': branch,
        'commit': await _head(s),
      };
    case 'delete-branch':
      final branch = requireBranch(s);
      if (request.force && await gitCurrent(s) == branch) {
        throw VcsStop(
          'branch_is_current',
          'refusing to force-delete the currently checked out branch',
        );
      }
      await gitChecked(scripts, repo, [
        'branch',
        request.force ? '-D' : '-d',
        branch,
      ], error: 'branch_delete_failed');
      return {'ok': true, 'backend': 'git', 'branch': branch};
    case 'fetch-main':
      await networkGit(
        scripts,
        repo,
        [
          'fetch',
          if (request.quiet) '-q',
          if (request.noTags) '--no-tags',
          remote.name,
          main,
        ],
        _loginFor(s),
        remote: remote.name,
        connection: connection,
      );
      final commit = (await gitChecked(scripts, repo, [
        'rev-parse',
        '--verify',
        'refs/remotes/${remote.name}/$main^{commit}',
      ], error: 'fetch_failed')).stdout.trim();
      return {
        'ok': true,
        'backend': 'git',
        'ref': '${remote.name}/$main',
        'commit': commit,
      };
    case 'pull':
      final explicitlyNamed = request.remoteBranch || remote.explicit;
      await networkGit(
        scripts,
        repo,
        [
          'pull',
          '--ff-only',
          if (explicitlyNamed) ...[remote.name, main],
        ],
        _loginFor(s),
        remote: explicitlyNamed ? remote.name : null,
        connection: connection,
      );
      return {'ok': true, 'backend': 'git', 'branch': await gitCurrent(s)};
    case 'push':
      final branch = requireBranch(s);
      await checkBranch(s, branch);
      await networkGit(
        scripts,
        repo,
        ['push', '-u', remote.name, 'HEAD'],
        _loginFor(s),
        remote: remote.name,
        connection: connection,
        expectedRepo: request.expectedRepo,
      );
      return {'ok': true, 'backend': 'git', 'branch': branch};
    case 'advance':
      if (request.scope == null) throw _usage('advance requires --scope');
      return {
        'ok': true,
        'backend': 'git',
        'branch': await gitCurrent(s),
        'advanced': false,
      };
  }
  throw _usage('$command is not implemented for the Git backend');
}
