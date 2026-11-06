import 'dart:io';

import 'package:specwright_cli/src/commands/vcs.dart';
import 'package:specwright_cli/src/vcs/args.dart';
import 'package:specwright_cli/src/vcs/git_backend.dart';
import 'package:specwright_cli/src/vcs/git_common.dart';
import 'package:specwright_cli/src/vcs/probe.dart';
import 'package:specwright_cli/src/vcs/scripts.dart';
import 'package:specwright_cli/src/vcs/stop.dart';
import 'package:test/test.dart';

import 'bash_support.dart';

/// An `as.sh` that logs its arguments and answers from files next to it.
const _fakeAs = r'''#!/usr/bin/env bash
d=$(dirname "$0")
for a in "$@"; do printf '%s|' "$a" >> "$d/as.log"; done
printf '\n' >> "$d/as.log"
[ -f "$d/as.out" ] && cat "$d/as.out"
[ -f "$d/as.err" ] && cat "$d/as.err" >&2
exit "$(cat "$d/as.rc" 2>/dev/null || echo 0)"
''';

void main() {
  final bash = findBash();
  final skip = bash == null ? 'no bash installed' : false;
  late Directory tmp;
  late Directory scriptsDir;
  late Directory repoDir;

  String posix(String p) => p.replaceAll(r'\', '/');

  String sh(String dir, List<String> args) {
    final r = Process.runSync('git', args, workingDirectory: dir);
    if (r.exitCode != 0) fail('git ${args.join(' ')}: ${r.stderr}');
    return (r.stdout as String).trim();
  }

  void gitIn(List<String> args) => sh(repoDir.path, args);

  void write(String name, String text, [String? dir]) =>
      File('${dir ?? repoDir.path}/$name').writeAsStringSync(text);

  void commitAll(String message) {
    gitIn(['add', '-A']);
    gitIn(['commit', '-q', '-m', message]);
  }

  void configure(String dir) {
    sh(dir, ['config', 'user.name', 'T']);
    sh(dir, ['config', 'user.email', 't@example.com']);
    sh(dir, ['config', 'commit.gpgsign', 'false']);
  }

  setUp(() {
    tmp = Directory.systemTemp.createTempSync('claude-ncv-g4-');
    scriptsDir = Directory('${tmp.path}/scripts')..createSync();
    File('${scriptsDir.path}/as.sh').writeAsStringSync(_fakeAs);
    repoDir = Directory('${tmp.path}/repo')..createSync();
    sh(repoDir.path, ['init', '-q', '-b', 'main']);
    configure(repoDir.path);
    write('base.txt', 'base\n');
    commitAll('base');
  });
  tearDown(() => tmp.deleteSync(recursive: true));

  VcsSession session({
    String command = 'state',
    String? branch,
    String? messageFile,
    String? scope,
    String? login,
    String infoLogin = '',
    bool force = false,
    bool noTags = false,
    bool quiet = false,
    bool remoteBranch = false,
    List<String> paths = const [],
    bool jjPresent = false,
  }) {
    final repo = posix(repoDir.path);
    final request = VcsRequest(
      command: command,
      repo: repo,
      role: 'code',
      code: repo,
      branch: branch,
      messageFile: messageFile,
      scope: scope,
      login: login,
      force: force,
      noTags: noTags,
      quiet: quiet,
      remoteBranch: remoteBranch,
      paths: paths,
    );
    final scriptsPath = posix(scriptsDir.path);
    return VcsSession(
      VcsContext(request, scriptsPath, bash!),
      repo,
      repo,
      ProbeInfo('git', 'main', repo, infoLogin, jjPresent: jjPresent),
      VcsScripts(scriptsPath, bash),
    );
  }

  Future<Map<String, Object?>> op(String command, VcsSession s) =>
      runGitOperation(s, command);

  Future<VcsStop> stopOf(Future<Object?> Function() body) async {
    try {
      await body();
    } on VcsStop catch (stop) {
      return stop;
    }
    fail('expected a VcsStop');
  }

  void expectStop(
    VcsStop stop,
    String error, {
    int code = 1,
    String? message,
    String? messageHas,
  }) {
    expect(stop.error, error);
    expect(stop.code, code);
    if (message != null) expect(stop.message, message);
    if (messageHas != null) expect(stop.message, contains(messageHas));
  }

  String messageFile([String text = 'a message\n']) {
    final f = File('${tmp.path}/msg.txt')..writeAsStringSync(text);
    return posix(f.path);
  }

  group('parsePorcelain', () {
    test('plain entries, with a backslash made a slash', () {
      final p = parsePorcelain(' M a.txt\u0000?? dir\\b.txt\u0000');
      expect(p.paths, ['a.txt', 'dir/b.txt']);
      expect(p.entries, [
        {'status': ' M', 'path': 'a.txt'},
        {'status': '??', 'path': 'dir/b.txt'},
      ]);
    });

    test(
      'a rename or copy takes its source record, a missing one is empty',
      () {
        final p = parsePorcelain('R  new.txt\u0000old.txt\u0000C  c.txt\u0000');
        expect(p.paths, ['new.txt', 'old.txt', 'c.txt', '']);
        expect(p.entries.first.keys.toList(), ['status', 'path', 'from']);
        expect(p.entries.last['from'], '');
      },
    );

    test('records shorter than four characters are skipped', () {
      expect(parsePorcelain('ab\u0000 M \u0000').paths, isEmpty);
    });
  });

  group('isGithubUrl', () {
    test('GitHub hosts, URL and scp forms', () {
      for (final url in [
        'https://github.com/a/b.git',
        'https://user@GitHub.com./a/b',
        'ssh://git@ssh.github.com:443/a/b',
        'git@github.com:a/b.git',
        'github.com:a/b',
      ]) {
        expect(isGithubUrl(url), isTrue, reason: url);
      }
    });

    test('other hosts, local paths and drive paths', () {
      for (final url in [
        '',
        '/srv/git/repo',
        r'C:\repos\x',
        'C:/repos/x',
        'https://example.com/github.com/x',
        'git@gitlab.com:a/b',
        'https://github.com.evil.example/x',
      ]) {
        expect(isGithubUrl(url), isFalse, reason: url);
      }
    });
  });

  group('state', () {
    test('a clean repo on main', () async {
      final state = await gitStateDocument(session());
      expect(state.keys.toList(), [
        'ok',
        'backend',
        'main',
        'branch',
        'on_main',
        'clean',
        'dirty_paths',
        'dirty',
        'behind',
        'behind_truncated',
        'head',
      ]);
      expect(state['branch'], 'main');
      expect(state['on_main'], true);
      expect(state['clean'], true);
      expect(state['head'], sh(repoDir.path, ['rev-parse', 'HEAD']));
    }, skip: skip);

    test('dirty paths, a rename, jj_present and branch_matches', () async {
      write('new.txt', 'x\n');
      gitIn(['mv', 'base.txt', 'moved.txt']);
      final state = await gitStateDocument(
        session(branch: 'other', jjPresent: true),
      );
      expect(state['clean'], false);
      expect(state['dirty_paths'], containsAll(['moved.txt', 'base.txt']));
      final dirty = state['dirty']! as List;
      expect((dirty.first as Map)['from'], 'base.txt');
      final keys = state.keys.toList();
      expect(keys.sublist(keys.length - 3), [
        'jj_present',
        'head',
        'branch_matches',
      ]);
      expect(state['branch_matches'], false);
    }, skip: skip);

    test('a detached HEAD has an empty branch', () async {
      gitIn(['checkout', '-q', '--detach']);
      final state = await gitStateDocument(session(branch: ''));
      expect(state['branch'], '');
      expect(state['on_main'], false);
      expect(state.containsKey('branch_matches'), false);
    }, skip: skip);
  });

  group('usage stops', () {
    for (final command in [
      'branch-create',
      'switch',
      'commit',
      'merge',
      'delete-branch',
      'push',
    ]) {
      test('$command without --branch', () async {
        final stop = await stopOf(() => op(command, session(command: command)));
        expectStop(stop, 'usage', code: 2, message: 'missing --branch');
      }, skip: skip);
    }

    test('commit without a message file or paths', () async {
      final noMessage = await stopOf(
        () => op('commit', session(branch: 'main', paths: ['a'])),
      );
      expectStop(
        noMessage,
        'usage',
        code: 2,
        message:
            'commit requires --message-file and at least one path after --',
      );
      final noPaths = await stopOf(
        () => op('commit', session(branch: 'main', messageFile: 'm')),
      );
      expectStop(noPaths, 'usage', code: 2, message: noMessage.message);
    }, skip: skip);

    test('merge without a message file', () async {
      final stop = await stopOf(() => op('merge', session(branch: 'x')));
      expectStop(
        stop,
        'usage',
        code: 2,
        message: 'merge requires --message-file',
      );
    }, skip: skip);

    test('advance without --scope', () async {
      final stop = await stopOf(() => op('advance', session()));
      expectStop(stop, 'usage', code: 2, message: 'advance requires --scope');
    }, skip: skip);

    test('a command the Git backend does not know', () async {
      final stop = await stopOf(() => op('plan', session()));
      expectStop(
        stop,
        'usage',
        code: 2,
        message: 'plan is not implemented for the Git backend',
      );
    }, skip: skip);
  });

  group('branch-create and switch', () {
    test('branch-create makes and enters the branch', () async {
      final doc = await op('branch-create', session(branch: 'feat/x'));
      expect(doc.keys.toList(), ['ok', 'backend', 'branch', 'output']);
      expect(doc['branch'], 'feat/x');
      expect(sh(repoDir.path, ['branch', '--show-current']), 'feat/x');
    }, skip: skip);

    test('branch-create on an existing branch is git_error', () async {
      gitIn(['branch', 'dup']);
      final stop = await stopOf(
        () => op('branch-create', session(branch: 'dup')),
      );
      expectStop(stop, 'git_error', messageHas: 'already exists');
    }, skip: skip);

    test('switch moves, and an unknown branch is git_error', () async {
      gitIn(['branch', 'other']);
      await op('switch', session(branch: 'other'));
      expect(sh(repoDir.path, ['branch', '--show-current']), 'other');
      final stop = await stopOf(() => op('switch', session(branch: 'nope')));
      expectStop(stop, 'git_error', messageHas: 'nope');
    }, skip: skip);
  });

  group('commit', () {
    test('commits the named paths and returns HEAD', () async {
      write('a.txt', 'a\n');
      write('b.txt', 'b\n');
      final doc = await op(
        'commit',
        session(branch: 'main', messageFile: messageFile(), paths: ['a.txt']),
      );
      expect(doc.keys.toList(), ['ok', 'backend', 'branch', 'commit']);
      expect(doc['commit'], sh(repoDir.path, ['rev-parse', 'HEAD']));
      expect(sh(repoDir.path, ['status', '--porcelain']), '?? b.txt');
    }, skip: skip);

    test('wrong_branch quotes both names as Python repr', () async {
      final stop = await stopOf(
        () => op(
          'commit',
          session(branch: "it's", messageFile: 'm', paths: ['a']),
        ),
      );
      expectStop(
        stop,
        'wrong_branch',
        message: 'expected branch "it\'s", currently on \'main\'',
      );
    }, skip: skip);

    test('git add failing is git_error', () async {
      final stop = await stopOf(
        () => op(
          'commit',
          session(
            branch: 'main',
            messageFile: messageFile(),
            paths: ['missing.txt'],
          ),
        ),
      );
      expectStop(stop, 'git_error', messageHas: 'missing.txt');
    }, skip: skip);

    test('nothing to commit is git_commit_failed', () async {
      final stop = await stopOf(
        () => op(
          'commit',
          session(
            branch: 'main',
            messageFile: messageFile(),
            paths: ['base.txt'],
          ),
        ),
      );
      expectStop(stop, 'git_commit_failed');
    }, skip: skip);

    test('a Windows command line over 32000 bytes is too_many_paths', () async {
      final paths = [for (var i = 0; i < 40; i++) '${'p' * 999}$i'];
      final stop = await stopOf(
        () => runGitOperation(
          session(
            command: 'commit',
            branch: 'main',
            messageFile: 'm',
            paths: paths,
          ),
          'commit',
          windows: true,
        ),
      );
      expectStop(
        stop,
        'too_many_paths',
        message:
            'named Git paths exceed the Windows command-line limit; name a '
            'containing directory instead',
      );
    }, skip: skip);
  });

  group('merge', () {
    test('merges with --no-ff and returns the merge commit', () async {
      gitIn(['checkout', '-q', '-b', 'feat']);
      write('f.txt', 'f\n');
      commitAll('feat');
      gitIn(['checkout', '-q', 'main']);
      final doc = await op(
        'merge',
        session(branch: 'feat', messageFile: messageFile('merged\n')),
      );
      expect(doc.keys.toList(), ['ok', 'backend', 'branch', 'commit']);
      expect(sh(repoDir.path, ['log', '-1', '--format=%s']), 'merged');
      expect(
        sh(repoDir.path, ['rev-list', '--parents', '-n1', 'HEAD']).split(' '),
        hasLength(3),
      );
    }, skip: skip);

    test('off the main branch is wrong_branch', () async {
      gitIn(['checkout', '-q', '-b', 'feat']);
      final stop = await stopOf(
        () => op('merge', session(branch: 'feat', messageFile: messageFile())),
      );
      expectStop(
        stop,
        'wrong_branch',
        message: "expected branch 'main', currently on 'feat'",
      );
    }, skip: skip);

    test('an unknown branch is merge_failed', () async {
      final stop = await stopOf(
        () => op('merge', session(branch: 'nope', messageFile: messageFile())),
      );
      expectStop(stop, 'merge_failed', messageHas: 'nope');
    }, skip: skip);
  });

  group('delete-branch', () {
    test('deletes a merged branch', () async {
      gitIn(['branch', 'done']);
      final doc = await op('delete-branch', session(branch: 'done'));
      expect(doc, {'ok': true, 'backend': 'git', 'branch': 'done'});
      expect(sh(repoDir.path, ['branch', '--list', 'done']), '');
    }, skip: skip);

    test(
      'an unmerged branch is branch_delete_failed, --force deletes it',
      () async {
        gitIn(['checkout', '-q', '-b', 'wip']);
        write('w.txt', 'w\n');
        commitAll('wip');
        gitIn(['checkout', '-q', 'main']);
        final stop = await stopOf(
          () => op('delete-branch', session(branch: 'wip')),
        );
        expectStop(
          stop,
          'branch_delete_failed',
          messageHas: 'not fully merged',
        );
        await op('delete-branch', session(branch: 'wip', force: true));
        expect(sh(repoDir.path, ['branch', '--list', 'wip']), '');
      },
      skip: skip,
    );

    test('--force on the current branch is branch_is_current', () async {
      final stop = await stopOf(
        () => op('delete-branch', session(branch: 'main', force: true)),
      );
      expectStop(
        stop,
        'branch_is_current',
        message: 'refusing to force-delete the currently checked out branch',
      );
    }, skip: skip);
  });

  group('advance', () {
    test('answers advanced false on the current branch', () async {
      final doc = await op('advance', session(scope: 'x'));
      expect(doc, {
        'ok': true,
        'backend': 'git',
        'branch': 'main',
        'advanced': false,
      });
    }, skip: skip);
  });

  group('network commands against a local remote', () {
    late Directory remote;

    // A second clone that pushes a commit the repo does not have.
    void pushFromElsewhere() {
      final other = '${tmp.path}/other';
      sh(tmp.path, ['clone', '-q', posix(remote.path), other]);
      configure(other);
      write('o.txt', 'o\n', other);
      sh(other, ['add', '-A']);
      sh(other, ['commit', '-q', '-m', 'other']);
      sh(other, ['push', '-q', 'origin', 'main']);
    }

    setUp(() {
      remote = Directory('${tmp.path}/remote.git')..createSync();
      sh(remote.path, ['init', '-q', '--bare', '-b', 'main']);
      gitIn(['remote', 'add', 'origin', posix(remote.path)]);
      gitIn(['push', '-q', '-u', 'origin', 'main']);
    });

    test('fetch-main fetches and reports the remote-tracking commit', () async {
      final doc = await op('fetch-main', session(quiet: true, noTags: true));
      expect(doc.keys.toList(), ['ok', 'backend', 'ref', 'commit']);
      expect(doc['ref'], 'origin/main');
      expect(doc['commit'], sh(repoDir.path, ['rev-parse', 'origin/main']));
    }, skip: skip);

    test('fetch-main without a tracking ref is fetch_failed', () async {
      gitIn(['config', '--unset-all', 'remote.origin.fetch']);
      gitIn(['update-ref', '-d', 'refs/remotes/origin/main']);
      final stop = await stopOf(() => op('fetch-main', session()));
      expect(stop.error, 'fetch_failed');
      expect(stop.code, 1);
    }, skip: skip);

    test('a failing fetch is git_network_error with exit 3', () async {
      gitIn(['remote', 'set-url', 'origin', posix('${tmp.path}/nowhere')]);
      final stop = await stopOf(() => op('fetch-main', session()));
      expectStop(stop, 'git_network_error', code: 3);
    }, skip: skip);

    test('pull fast-forwards and reports the branch', () async {
      pushFromElsewhere();
      final doc = await op('pull', session(remoteBranch: true));
      expect(doc, {'ok': true, 'backend': 'git', 'branch': 'main'});
      expect(File('${repoDir.path}/o.txt').existsSync(), isTrue);
    }, skip: skip);

    test('a diverged pull is not_fast_forward with exit 1', () async {
      pushFromElsewhere();
      write('mine.txt', 'm\n');
      commitAll('mine');
      final stop = await stopOf(() => op('pull', session(remoteBranch: true)));
      expect(stop.error, 'not_fast_forward');
      expect(stop.code, 1);
    }, skip: skip);

    test('push publishes the branch and sets its upstream', () async {
      gitIn(['checkout', '-q', '-b', 'feat']);
      write('f.txt', 'f\n');
      commitAll('feat');
      final doc = await op('push', session(branch: 'feat'));
      expect(doc, {'ok': true, 'backend': 'git', 'branch': 'feat'});
      expect(
        sh(remote.path, ['rev-parse', 'refs/heads/feat']),
        sh(repoDir.path, ['rev-parse', 'HEAD']),
      );
    }, skip: skip);

    test('push from another branch is wrong_branch', () async {
      final stop = await stopOf(() => op('push', session(branch: 'feat')));
      expectStop(
        stop,
        'wrong_branch',
        message: "expected branch 'feat', currently on 'main'",
      );
    }, skip: skip);

    test('a rejected push is git_network_error with exit 3', () async {
      pushFromElsewhere();
      write('mine.txt', 'm\n');
      commitAll('mine');
      final stop = await stopOf(() => op('push', session(branch: 'main')));
      expectStop(stop, 'git_network_error', code: 3);
    }, skip: skip);
  });

  group('the identity fence on a GitHub remote', () {
    setUp(() {
      gitIn(['remote', 'add', 'origin', 'https://github.com/a/b.git']);
    });

    String asLog() {
      final f = File('${scriptsDir.path}/as.log');
      return f.existsSync() ? f.readAsStringSync() : '';
    }

    void answer(String file, String text) =>
        File('${scriptsDir.path}/$file').writeAsStringSync(text);

    test('fetch-main runs as.sh with the given login', () async {
      gitIn(['update-ref', 'refs/remotes/origin/main', 'HEAD']);
      final doc = await op(
        'fetch-main',
        session(login: 'bot', quiet: true, noTags: true),
      );
      expect(asLog(), 'bot|git|fetch|-q|--no-tags|origin|main|\n');
      expect(doc['ref'], 'origin/main');
    }, skip: skip);

    test('the pinned login is used when none was given', () async {
      await op('pull', session(infoLogin: 'pinned'));
      expect(asLog(), 'pinned|git|pull|--ff-only|\n');
    }, skip: skip);

    test('without a login as.sh --resolve supplies one', () async {
      answer('as.out', 'resolved\n');
      await op('pull', session(remoteBranch: true));
      expect(asLog(), '--resolve|\nresolved|git|pull|--ff-only|origin|main|\n');
    }, skip: skip);

    test('a refused resolve is fence_failed with exit 3', () async {
      answer('as.err', 'as.sh: nope\n');
      answer('as.rc', '3');
      final stop = await stopOf(() => op('pull', session()));
      expectStop(stop, 'fence_failed', code: 3, message: 'as.sh: nope');
    }, skip: skip);

    test('a resolve that says nothing has the default message', () async {
      answer('as.rc', '1');
      final stop = await stopOf(() => op('pull', session()));
      expectStop(
        stop,
        'fence_failed',
        code: 3,
        message: 'as.sh could not resolve GitHub login',
      );
    }, skip: skip);

    test('exit 3 from the fenced command is fence_failed', () async {
      answer('as.rc', '3');
      answer('as.err', 'as.sh: refused\n');
      final stop = await stopOf(
        () => op('push', session(login: 'bot', branch: 'main')),
      );
      expectStop(stop, 'fence_failed', code: 3, message: 'as.sh: refused');
    }, skip: skip);

    test('another failure is git_network_error, default message', () async {
      answer('as.rc', '1');
      final stop = await stopOf(() => op('fetch-main', session(login: 'bot')));
      expectStop(
        stop,
        'git_network_error',
        code: 3,
        message: 'Git network operation failed',
      );
    }, skip: skip);

    test(
      'a pull that cannot fast-forward is not_fast_forward, exit 1',
      () async {
        answer('as.rc', '1');
        answer('as.err', 'fatal: Not possible to fast-forward, aborting.\n');
        final stop = await stopOf(() => op('pull', session(login: 'bot')));
        expectStop(
          stop,
          'not_fast_forward',
          message: 'fatal: Not possible to fast-forward, aborting.',
        );
      },
      skip: skip,
    );
  });
}
