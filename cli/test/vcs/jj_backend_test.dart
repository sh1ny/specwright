import 'dart:io';

import 'package:specwright_cli/src/commands/vcs.dart';
import 'package:specwright_cli/src/vcs/args.dart';
import 'package:specwright_cli/src/vcs/jj_backend.dart';
import 'package:specwright_cli/src/vcs/probe.dart';
import 'package:specwright_cli/src/vcs/scripts.dart';
import 'package:specwright_cli/src/vcs/stop.dart';
import 'package:test/test.dart';

import 'bash_support.dart';
import 'fake_fence.dart';

bool _jjInstalled() {
  try {
    return Process.runSync('jj', ['--version']).exitCode == 0;
  } on ProcessException {
    return false;
  }
}

void main() {
  final bash = findBash();
  final skip = bash == null
      ? 'no bash installed'
      : !_jjInstalled()
      ? 'no jj installed'
      : false;
  late Directory tmp;
  late Directory scriptsDir;
  late Directory repoDir;
  late Directory originDir;

  String posix(String p) => p.replaceAll(r'\', '/');

  String run(String tool, List<String> args, String dir) {
    final r = Process.runSync(tool, args, workingDirectory: dir);
    if (r.exitCode != 0) fail('$tool ${args.join(' ')}: ${r.stderr}');
    return (r.stdout as String).trim();
  }

  String jjIn(List<String> args) => run('jj', args, repoDir.path);
  String gitIn(List<String> args, [String? dir]) =>
      run('git', args, dir ?? repoDir.path);

  void write(String name, String text) {
    final f = File('${repoDir.path}/$name');
    f.parent.createSync(recursive: true);
    f.writeAsStringSync(text);
  }

  setUp(() {
    tmp = Directory.systemTemp.createTempSync('claude-ncv-g5-');
    // The pure helpers need no fixture; the build runners have no jj.
    if (skip != false) return;
    scriptsDir = Directory('${tmp.path}/scripts')..createSync();
    originDir = Directory('${tmp.path}/origin.git')..createSync();
    gitIn(['init', '-q', '--bare', '-b', 'main'], originDir.path);
    final seed = Directory('${tmp.path}/seed')..createSync();
    gitIn(['init', '-q', '-b', 'main'], seed.path);
    gitIn(['config', 'user.name', 'T'], seed.path);
    gitIn(['config', 'user.email', 't@example.com'], seed.path);
    gitIn(['config', 'commit.gpgsign', 'false'], seed.path);
    File('${seed.path}/base.txt').writeAsStringSync('base\n');
    gitIn(['add', '-A'], seed.path);
    gitIn(['commit', '-q', '-m', 'base'], seed.path);
    gitIn(['remote', 'add', 'origin', posix(originDir.path)], seed.path);
    gitIn(['push', '-q', 'origin', 'main'], seed.path);
    repoDir = Directory('${tmp.path}/repo');
    run('jj', [
      '--config',
      'user.name="T"',
      '--config',
      'user.email="t@example.com"',
      'git',
      'clone',
      '--colocate',
      posix(originDir.path),
      posix(repoDir.path),
    ], tmp.path);
    jjIn(['config', 'set', '--repo', 'user.name', 'T']);
    jjIn(['config', 'set', '--repo', 'user.email', 't@example.com']);
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
    List<String> paths = const [],
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
      paths: paths,
    );
    final scriptsPath = posix(scriptsDir.path);
    return VcsSession(
      VcsContext(request, scriptsPath, bash!),
      repo,
      repo,
      ProbeInfo('jj', 'main', repo, infoLogin),
      VcsScripts(scriptsPath, bash, fence: fakeFence(scriptsDir)),
    );
  }

  Future<Map<String, Object?>> op(
    String command,
    VcsSession s, {
    bool? windows,
  }) => runJjOperation(s, command, windows: windows);

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

  String messageFile([String text = 'feat(x): a message\n']) {
    final f = File('${tmp.path}/msg.txt')..writeAsStringSync(text);
    return posix(f.path);
  }

  Future<void> onBranch(String name) async {
    await op('branch-create', session(command: 'branch-create', branch: name));
  }

  Future<String> commitFile(String name, String text, String branch) async {
    write(name, text);
    final r = await op(
      'commit',
      session(
        command: 'commit',
        branch: branch,
        messageFile: messageFile(),
        paths: [name],
      ),
    );
    return r['commit'] as String;
  }

  group('pure helpers', () {
    test('jjPath names a path the way jj does', () {
      expect(jjPath('./a'), 'a');
      expect(jjPath('a/../a'), 'a');
      expect(jjPath('a/'), 'a');
      expect(jjPath(''), '.');
      expect(jjPath('//a'), '//a');
      expect(jjPath('///a'), '/a');
      expect(jjPath(r'a\b', windows: true), 'a/b');
    });

    test('revset and fileset text escape quotes and backslashes', () {
      expect(revsetText(r'a"b\c'), r'"a\"b\\c"');
      expect(filesetText('d/f'), 'root:"d/f"');
      expect(exactPattern('x'), 'exact:"x"');
    });

    test('windowsCommandLine quotes every argument', () {
      expect(
        windowsCommandLine(['jj', 'a b', r'q"x', r'tail\']),
        r'"jj" "a b" "q\"x" "tail\\"',
      );
    });
  });

  group('jj state', skip: skip, () {
    test(
      'on main: no branch, on_main, head and branch_matches absent',
      () async {
        final doc = await jjStateDocument(session());
        expect(doc.keys.toList(), [
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
        expect(doc['backend'], 'jj');
        expect(doc['branch'], '');
        expect(doc['on_main'], true);
        expect(doc['clean'], true);
        expect(doc['head'], gitIn(['rev-parse', 'HEAD']));
      },
    );

    test('a change shows as a dirty path', () async {
      write('a.txt', 'a\n');
      final doc = await jjStateDocument(session());
      expect(doc['clean'], false);
      expect(doc['dirty_paths'], ['a.txt']);
      expect(doc['dirty'], [
        {'status': 'A', 'path': 'a.txt'},
      ]);
    });

    test('a bookmark at @- is the branch', () async {
      await onBranch('feat');
      final doc = await jjStateDocument(
        session(branch: 'feat', command: 'state'),
      );
      expect(doc['branch'], 'feat');
      expect(doc['on_main'], false);
      expect(doc['branch_matches'], true);
    });

    test('two bookmarks at @- are ambiguous_branch', () async {
      await onBranch('b1');
      jjIn(['bookmark', 'create', 'b2', '-r', '@-']);
      expectStop(
        await stopOf(() => jjState(session())),
        'ambiguous_branch',
        message: 'multiple local bookmarks point at @-: b1, b2',
      );
    });

    test('a conflicted bookmark is ambiguous_branch', () async {
      jjIn(['new', 'main', '-m', 'left']);
      jjIn(['new', 'main', '-m', 'right']);
      String id(String d) => jjIn([
        'log',
        '--no-graph',
        '-r',
        'description(exact:"$d\\n")',
        '-T',
        'commit_id',
      ]);
      final left = id('left');
      final right = id('right');
      jjIn(['bookmark', 'create', 'feat', '-r', left]);
      jjIn(['--at-op', '@-', 'bookmark', 'create', 'feat', '-r', right]);
      jjIn(['new', left]);
      expectStop(
        await stopOf(() => jjState(session())),
        'ambiguous_branch',
        messageHas: 'conflicted local bookmark(s): feat',
      );
    });

    test('a bookmark behind @- within its scope is recovered', () async {
      await onBranch('x');
      final first = await commitFile('a.txt', 'a\n', 'x');
      write('b.txt', 'b\n');
      jjIn(['commit', '-m', 'feat(x): second']);
      final doc = await jjState(session(), 'x');
      expect(doc['branch'], 'x');
      final behind = (doc['behind'] as List).cast<Map<String, Object?>>();
      expect(behind, hasLength(1));
      expect(behind.single['subject'], 'feat(x): second');
      expect(behind.single['parents'], 1);
      expect(first, isNotEmpty);
    });
  });

  group('jj operations', skip: skip, () {
    test('an unknown command is a usage stop', () async {
      expectStop(
        await stopOf(() => op('bogus', session(command: 'bogus'))),
        'usage',
        code: 2,
        message: 'unknown command: bogus',
      );
    });

    test('branch-create and switch need --branch', () async {
      for (final c in ['branch-create', 'switch']) {
        expectStop(
          await stopOf(() => op(c, session(command: c))),
          'usage',
          code: 2,
          message: 'missing --branch',
        );
      }
    });

    test('branch-create makes the bookmark at @-', () async {
      final r = await op(
        'branch-create',
        session(command: 'branch-create', branch: 'feat'),
      );
      expect(r.keys.toList(), ['ok', 'backend', 'branch', 'commit']);
      expect(r['commit'], gitIn(['rev-parse', 'HEAD']));
    });

    test('switch moves an empty working copy onto the branch', () async {
      await onBranch('feat');
      final c = await commitFile('a.txt', 'a\n', 'feat');
      final r = await op('switch', session(command: 'switch', branch: 'main'));
      expect(r, {'ok': true, 'backend': 'jj', 'branch': 'main'});
      expect(gitIn(['rev-parse', 'HEAD']), isNot(c));
    });

    test('switch with conflicting edits is carry_conflict', () async {
      await onBranch('feat');
      await commitFile('a.txt', 'one\n', 'feat');
      jjIn(['new', 'main']);
      write('a.txt', 'two\n');
      final stop = await stopOf(
        () => op('switch', session(command: 'switch', branch: 'feat')),
      );
      expectStop(stop, 'carry_conflict', messageHas: 'in: a.txt; nothing was');
      expect(stop.extra, {
        'paths': ['a.txt'],
      });
      expect(File('${repoDir.path}/a.txt').readAsStringSync(), 'two\n');
    });

    group('commit', () {
      test('usage without a message file or a path', () async {
        await onBranch('feat');
        expectStop(
          await stopOf(
            () => op(
              'commit',
              session(command: 'commit', branch: 'feat', paths: ['a']),
            ),
          ),
          'usage',
          code: 2,
          message:
              'commit requires --message-file and at least one path after --',
        );
      });

      test('on another branch is wrong_branch', () async {
        write('a.txt', 'a\n');
        expectStop(
          await stopOf(
            () => op(
              'commit',
              session(
                command: 'commit',
                branch: 'feat',
                messageFile: messageFile(),
                paths: ['a.txt'],
              ),
            ),
          ),
          'wrong_branch',
          message: "expected branch 'feat', currently on 'main'",
        );
      });

      test('commits the named path and moves the bookmark', () async {
        await onBranch('feat');
        write('a.txt', 'a\n');
        write('other.txt', 'o\n');
        final r = await op(
          'commit',
          session(
            command: 'commit',
            branch: 'feat',
            messageFile: messageFile(),
            paths: ['./a.txt'],
          ),
        );
        expect(r.keys.toList(), ['ok', 'backend', 'branch', 'commit']);
        expect(r['commit'], gitIn(['rev-parse', 'refs/heads/feat']));
        expect(gitIn(['show', '--name-only', '--format=', 'feat']), 'a.txt');
      });

      test('a path with no change is nothing_to_commit', () async {
        await onBranch('feat');
        expectStop(
          await stopOf(
            () => op(
              'commit',
              session(
                command: 'commit',
                branch: 'feat',
                messageFile: messageFile(),
                paths: ['base.txt'],
              ),
            ),
          ),
          'nothing_to_commit',
          message: 'no changes to commit in the named paths',
        );
      });

      test('an ignored path is path_not_tracked', () async {
        await onBranch('feat');
        write('.gitignore', 'secret.txt\n');
        write('secret.txt', 's\n');
        final stop = await stopOf(
          () => op(
            'commit',
            session(
              command: 'commit',
              branch: 'feat',
              messageFile: messageFile(),
              paths: ['secret.txt'],
            ),
          ),
        );
        expectStop(
          stop,
          'path_not_tracked',
          message:
              'secret.txt is not tracked in the jj working copy: it is '
              'ignored, or larger than snapshot.max-new-file-size',
        );
        expect(stop.extra, {'path': 'secret.txt'});
      });

      test('a file over the snapshot limit is path_not_tracked', () async {
        await onBranch('feat');
        jjIn(['config', 'set', '--repo', 'snapshot.max-new-file-size', '20']);
        write('big.bin', 'x' * 100);
        final stop = await stopOf(
          () => op(
            'commit',
            session(
              command: 'commit',
              branch: 'feat',
              messageFile: messageFile(),
              paths: ['big.bin'],
            ),
          ),
        );
        expectStop(
          stop,
          'path_not_tracked',
          message:
              'big.bin is not tracked in the jj working copy: it is larger '
              'than snapshot.max-new-file-size (20 bytes)',
        );
        expect(stop.extra, {'path': 'big.bin'});
      });

      test('an oversized file in a named directory and in its child names '
          "the parent's file", () async {
        await onBranch('feat');
        jjIn(['config', 'set', '--repo', 'snapshot.max-new-file-size', '20']);
        write('dir/small.txt', 's\n');
        write('dir/sub/small.txt', 's\n');
        write('dir/zbig.bin', 'x' * 100);
        write('dir/sub/abig.bin', 'x' * 100);
        final stop = await stopOf(
          () => op(
            'commit',
            session(
              command: 'commit',
              branch: 'feat',
              messageFile: messageFile(),
              paths: ['dir', 'dir/sub'],
            ),
          ),
        );
        expectStop(
          stop,
          'path_not_tracked',
          message:
              'dir/zbig.bin is not tracked in the jj working copy: it is '
              'larger than snapshot.max-new-file-size (20 bytes)',
        );
        expect(stop.extra, {'path': 'dir/zbig.bin'});
      });

      test(
        'an oversized file that Git ignores does not stop the commit',
        () async {
          await onBranch('feat');
          jjIn(['config', 'set', '--repo', 'snapshot.max-new-file-size', '20']);
          write('.gitignore', 'dir/big.bin\n');
          write('dir/small.txt', 's\n');
          write('dir/big.bin', 'x' * 100);
          final r = await op(
            'commit',
            session(
              command: 'commit',
              branch: 'feat',
              messageFile: messageFile(),
              paths: ['dir'],
            ),
          );
          expect(r['ok'], true);
        },
      );

      test(
        'paths over the Windows command-line limit are too_many_paths',
        () async {
          await onBranch('feat');
          final stop = await stopOf(
            () => op(
              'commit',
              session(
                command: 'commit',
                branch: 'feat',
                messageFile: messageFile(),
                paths: [for (var i = 0; i < 400; i++) 'a${'x' * 80}$i'],
              ),
              windows: true,
            ),
          );
          expectStop(
            stop,
            'too_many_paths',
            message:
                'named paths and message exceed the command-line limit; name a '
                'containing directory instead',
          );
        },
      );
    });

    group('advance', () {
      test('needs --scope', () async {
        expectStop(
          await stopOf(() => op('advance', session(command: 'advance'))),
          'usage',
          code: 2,
          message: 'advance requires --scope',
        );
      });

      test('a different resolved branch is wrong_branch', () async {
        await onBranch('feat');
        expectStop(
          await stopOf(
            () => op(
              'advance',
              session(command: 'advance', scope: 'x', branch: 'other'),
            ),
          ),
          'wrong_branch',
          message: "expected branch 'other', resolved 'feat'",
        );
      });

      test('nothing behind is advanced false', () async {
        await onBranch('feat');
        final r = await op('advance', session(command: 'advance', scope: 'x'));
        expect(r, {
          'ok': true,
          'backend': 'jj',
          'branch': 'feat',
          'advanced': false,
        });
      });

      test('commits in scope move the bookmark', () async {
        await onBranch('x');
        await commitFile('a.txt', 'a\n', 'x');
        write('b.txt', 'b\n');
        jjIn(['commit', '-m', 'feat(x): second']);
        final r = await op('advance', session(command: 'advance', scope: 'x'));
        expect(r['advanced'], true);
        expect(r['commit'], gitIn(['rev-parse', 'HEAD']));
      });

      test('commits outside the scope are bookmark_behind', () async {
        await onBranch('x');
        await commitFile('a.txt', 'a\n', 'x');
        write('b.txt', 'b\n');
        jjIn(['commit', '-m', 'fix(y): other']);
        final stop = await stopOf(
          () => op('advance', session(command: 'advance', scope: 'x')),
        );
        expectStop(stop, 'bookmark_behind', messageHas: 'outside scope x: ');
        expect((stop.extra['commits'] as List), hasLength(1));
      });
    });

    group('merge, delete-branch', () {
      Future<void> featureCommit() async {
        await onBranch('feat');
        await commitFile('a.txt', 'a\n', 'feat');
        await op('switch', session(command: 'switch', branch: 'main'));
      }

      test('merge needs a branch and a message file', () async {
        expectStop(
          await stopOf(() => op('merge', session(command: 'merge'))),
          'usage',
          code: 2,
        );
        expectStop(
          await stopOf(
            () => op('merge', session(command: 'merge', branch: 'feat')),
          ),
          'usage',
          code: 2,
          message: 'merge requires --message-file',
        );
      });

      test('a missing bookmark is no_such_branch', () async {
        expectStop(
          await stopOf(
            () => op(
              'merge',
              session(
                command: 'merge',
                branch: 'nope',
                messageFile: messageFile(),
              ),
            ),
          ),
          'no_such_branch',
          message: 'bookmark nope does not exist',
        );
      });

      test('merging off main is wrong_branch', () async {
        await featureCommit();
        await onBranch('other');
        expectStop(
          await stopOf(
            () => op(
              'merge',
              session(
                command: 'merge',
                branch: 'feat',
                messageFile: messageFile('merge feat\n'),
              ),
            ),
          ),
          'wrong_branch',
          message: "expected to be on 'main', currently on 'other'",
        );
      });

      test('merge, then merge again is already_merged', () async {
        await featureCommit();
        final s = session(
          command: 'merge',
          branch: 'feat',
          messageFile: messageFile('merge feat\n'),
        );
        final r = await op('merge', s);
        expect(r.keys.toList(), ['ok', 'backend', 'branch', 'commit']);
        expect(r['commit'], gitIn(['rev-parse', 'refs/heads/main']));
        final again = await op('merge', s);
        expect(again['already_merged'], true);
      });

      test('delete-branch of an unmerged branch is not_merged', () async {
        await featureCommit();
        expectStop(
          await stopOf(
            () => op(
              'delete-branch',
              session(command: 'delete-branch', branch: 'feat'),
            ),
          ),
          'not_merged',
          message: 'branch feat is not merged into main',
        );
      });

      test('force deletes it, and a merged one deletes without', () async {
        await featureCommit();
        final r = await op(
          'delete-branch',
          session(command: 'delete-branch', branch: 'feat', force: true),
        );
        expect(r, {'ok': true, 'backend': 'jj', 'branch': 'feat'});
        expect(jjIn(['bookmark', 'list', 'feat']), isEmpty);
        await onBranch('merged');
        await op(
          'delete-branch',
          session(command: 'delete-branch', branch: 'merged'),
        );
      });
    });

    group('push, fetch-main, pull', () {
      test('push from another branch is wrong_branch', () async {
        await onBranch('feat');
        expectStop(
          await stopOf(
            () => op('push', session(command: 'push', branch: 'other')),
          ),
          'wrong_branch',
          message: "expected branch 'other', currently on 'feat'",
        );
      });

      test('push with an undescribed commit is undescribed', () async {
        await onBranch('feat');
        write('a.txt', 'a\n');
        jjIn(['commit', '-m', '']);
        jjIn(['bookmark', 'set', 'feat', '-r', '@-']);
        final stop = await stopOf(
          () => op('push', session(command: 'push', branch: 'feat')),
        );
        expectStop(stop, 'undescribed', messageHas: 'commit(s) in main..feat');
        expect((stop.extra['commits'] as List), hasLength(1));
      });

      test('push with a conflicted commit is conflicted', () async {
        await onBranch('feat');
        write('base.txt', 'branch side\n');
        jjIn(['commit', '-m', 'feat: branch']);
        jjIn(['bookmark', 'set', 'feat', '-r', '@-']);
        jjIn(['new', 'main']);
        write('base.txt', 'main side\n');
        jjIn(['commit', '-m', 'chore: main']);
        jjIn(['bookmark', 'set', 'main', '-r', '@-']);
        jjIn(['rebase', '-b', 'feat', '-o', 'main']);
        jjIn(['new', 'feat']);
        final stop = await stopOf(
          () => op('push', session(command: 'push', branch: 'feat')),
        );
        expectStop(stop, 'conflicted', messageHas: 'are conflicted: ');
      });

      test('push sends the bookmark', () async {
        await onBranch('feat');
        final c = await commitFile('a.txt', 'a\n', 'feat');
        final r = await op('push', session(command: 'push', branch: 'feat'));
        expect(r, {'ok': true, 'backend': 'jj', 'branch': 'feat'});
        expect(gitIn(['rev-parse', 'refs/heads/feat'], originDir.path), c);
      });

      test('fetch-main returns the fetched commit', () async {
        final r = await op('fetch-main', session(command: 'fetch-main'));
        expect(r.keys.toList(), ['ok', 'backend', 'ref', 'commit']);
        expect(r['ref'], r['commit']);
        expect(r['commit'], gitIn(['rev-parse', 'refs/heads/main']));
      });

      test('a remote that cannot be reached is git_network_error', () async {
        gitIn(['remote', 'set-url', 'origin', posix('${tmp.path}/nowhere')]);
        final stop = await stopOf(
          () => op('fetch-main', session(command: 'fetch-main')),
        );
        expectStop(stop, 'git_network_error', code: 3);
      });

      test('a refused fence on GitHub is fence_failed', () async {
        gitIn(['remote', 'set-url', 'origin', 'https://github.com/a/b.git']);
        File('${scriptsDir.path}/as.rc').writeAsStringSync('3');
        File('${scriptsDir.path}/as.err').writeAsStringSync('no such login');
        final stop = await stopOf(
          () => op('fetch-main', session(command: 'fetch-main', login: 'bot')),
        );
        expectStop(stop, 'fence_failed', code: 3, message: 'no such login');
        expect(
          File('${scriptsDir.path}/as.log').readAsStringSync(),
          startsWith('bot|git|fetch|'),
        );
      });

      Future<String> pushFromOther(String name, String text) async {
        final other = Directory('${tmp.path}/other')..createSync();
        if (!File('${other.path}/.git/HEAD').existsSync()) {
          gitIn(['clone', '-q', posix(originDir.path), '.'], other.path);
          gitIn(['config', 'user.name', 'O'], other.path);
          gitIn(['config', 'user.email', 'o@example.com'], other.path);
          gitIn(['config', 'commit.gpgsign', 'false'], other.path);
        }
        File('${other.path}/$name').writeAsStringSync(text);
        gitIn(['add', '-A'], other.path);
        gitIn(['commit', '-q', '-m', 'other $name'], other.path);
        gitIn(['push', '-q', 'origin', 'main'], other.path);
        return gitIn(['rev-parse', 'HEAD'], other.path);
      }

      test('pull with nothing new is moved false', () async {
        final r = await op('pull', session(command: 'pull'));
        expect(r['moved'], false);
        expect(r['branch'], 'main');
      });

      test('pull fast-forwards main and moves the working copy', () async {
        final tip = await pushFromOther('o.txt', 'o\n');
        final r = await op('pull', session(command: 'pull'));
        expect(r.keys.toList(), ['ok', 'backend', 'branch', 'commit', 'moved']);
        expect(r['moved'], true);
        expect(r['commit'], tip);
        expect(gitIn(['rev-parse', 'HEAD']), tip);
      });

      test('pull with a diverged main is not_fast_forward', () async {
        await pushFromOther('o.txt', 'o\n');
        await onBranch('feat');
        write('l.txt', 'l\n');
        jjIn(['commit', '-m', 'local']);
        jjIn(['bookmark', 'set', 'main', '-r', '@-', '--allow-backwards']);
        expectStop(
          await stopOf(() => op('pull', session(command: 'pull'))),
          'not_fast_forward',
          messageHas: 'have diverged',
        );
      });
    });
  });
}
