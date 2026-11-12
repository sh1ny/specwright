import 'dart:convert';
import 'dart:io';

import '../commands/vcs.dart';
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

/// `vcs.sh`'s `parse_porcelain` on `git status --porcelain -z` output: the
/// paths (a rename or copy adds its source) and the entries. [records] is the
/// output split on NUL.
({List<String> paths, List<Map<String, Object?>> entries}) parsePorcelain(
  String out,
) {
  final paths = <String>[];
  final entries = <Map<String, Object?>>[];
  final records = out.split('\u0000');
  var next = 0;
  while (next < records.length) {
    final record = records[next++];
    if (record.length < 4) continue;
    final status = record.substring(0, 2);
    final name = pathText(record.substring(3));
    final entry = <String, Object?>{'status': status, 'path': name};
    paths.add(name);
    if (status.contains('R') || status.contains('C')) {
      final from = next < records.length ? pathText(records[next++]) : '';
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

/// `vcs.sh`'s `git_state`.
Future<Map<String, Object?>> gitState(VcsSession s) async {
  final branch = await gitCurrent(s);
  final status = await git(s.scripts, s.repo, ['status', '--porcelain', '-z']);
  if (status.code != 0) {
    final said = status.stderr.trim();
    throw VcsStop(
      'git_error',
      said.isNotEmpty ? said : 'git status --porcelain -z failed',
    );
  }
  final parsed = parsePorcelain(status.names('file name'));
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
Future<Map<String, Object?>> runGitOperation(
  VcsSession s,
  String command, {
  bool? windows,
}) async {
  final request = s.request;
  final repo = s.repo;
  final scripts = s.scripts;
  final main = s.info.main;
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
      await networkGit(scripts, repo, [
        'fetch',
        if (request.quiet) '-q',
        if (request.noTags) '--no-tags',
        'origin',
        main,
      ], _loginFor(s));
      final commit = (await gitChecked(scripts, repo, [
        'rev-parse',
        '--verify',
        'refs/remotes/origin/$main^{commit}',
      ], error: 'fetch_failed')).stdout.trim();
      return {
        'ok': true,
        'backend': 'git',
        'ref': 'origin/$main',
        'commit': commit,
      };
    case 'pull':
      await networkGit(scripts, repo, [
        'pull',
        '--ff-only',
        if (request.remoteBranch) ...['origin', main],
      ], _loginFor(s));
      return {'ok': true, 'backend': 'git', 'branch': await gitCurrent(s)};
    case 'push':
      final branch = requireBranch(s);
      await checkBranch(s, branch);
      await networkGit(scripts, repo, [
        'push',
        '-u',
        'origin',
        'HEAD',
      ], _loginFor(s));
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
