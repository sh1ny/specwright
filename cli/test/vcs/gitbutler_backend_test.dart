import 'dart:collection';
import 'dart:convert';
import 'dart:io';

import 'package:specwright_cli/src/commands/vcs.dart';
import 'package:specwright_cli/src/process/command_line.dart'
    show UnsafeBatchArgument;
import 'package:specwright_cli/src/vcs/args.dart';
import 'package:specwright_cli/src/vcs/gitbutler_backend.dart';
import 'package:specwright_cli/src/vcs/probe.dart';
import 'package:specwright_cli/src/vcs/scripts.dart';
import 'package:specwright_cli/src/vcs/stop.dart';
import 'package:test/test.dart';

import '../support/exe_shim.dart';
import 'fake_fence.dart';

/// A `but` that logs its arguments, runs `hook.<cmd>` (sourced, so it can
/// `exec`), then answers from `out.<cmd>` / `err.<cmd>` / `rc.<cmd>` files.
const _fakeBut = r'''#!/usr/bin/env bash
d="$BUT_DIR"
printf '%s\n' "$*" >> "$d/but.log"
[ -f "$d/hook.$1" ] && . "$d/hook.$1"
[ -f "$d/out.$1" ] && cat "$d/out.$1"
[ -f "$d/err.$1" ] && cat "$d/err.$1" >&2
exit "$(cat "$d/rc.$1" 2>/dev/null || echo 0)"
''';

/// A `pr-pair.sh` that logs its arguments and answers from files next to it.
String _fakeScript(String prefix) =>
    '''#!/usr/bin/env bash
d=\$(dirname "\$0")
for a in "\$@"; do printf '%s|' "\$a" >> "\$d/$prefix.log"; done
printf '\\n' >> "\$d/$prefix.log"
[ -f "\$d/$prefix.out" ] && cat "\$d/$prefix.out"
[ -f "\$d/$prefix.err" ] && cat "\$d/$prefix.err" >&2
exit "\$(cat "\$d/$prefix.rc" 2>/dev/null || echo 0)"
''';

const _settings = 'openspec/specwright.yaml';

void main() {
  useExeShim();
  late Directory tmp;
  late Directory scriptsDir;
  late Directory butDir;
  late Directory repoDir;
  late Directory originDir;
  late String baseSha;

  String posix(String p) => p.replaceAll(r'\', '/');

  String sh(String dir, List<String> args) {
    final r = Process.runSync('git', args, workingDirectory: dir);
    if (r.exitCode != 0) fail('git ${args.join(' ')}: ${r.stderr}');
    return (r.stdout as String).trim();
  }

  String gitIn(List<String> args) => sh(repoDir.path, args);

  void write(String name, String text, [String? dir]) {
    final f = File('${dir ?? repoDir.path}/$name');
    f.parent.createSync(recursive: true);
    f.writeAsStringSync(text);
  }

  void but(String file, String text) =>
      File('${butDir.path}/$file').writeAsStringSync(text);

  String butLog() {
    final f = File('${butDir.path}/but.log');
    return f.existsSync() ? f.readAsStringSync() : '';
  }

  String log(String name) {
    final f = File('${scriptsDir.path}/$name.log');
    return f.existsSync() ? f.readAsStringSync() : '';
  }

  /// The `but status --json` the fake answers with.
  void setStatus({
    List<Map<String, Object?>> stacks = const [],
    List<String> uncommitted = const [],
    String? base,
  }) {
    but(
      'out.status',
      jsonEncode({
        'stacks': stacks,
        'uncommittedChanges': [
          for (final p in uncommitted) {'filePath': p},
        ],
        'mergeBase': {'commitId': base ?? baseSha},
      }),
    );
  }

  Map<String, Object?> stack(
    String name, {
    List<String> assigned = const [],
    bool commits = false,
  }) => {
    'branches': [
      {
        'name': name,
        'commits': commits
            ? [
                {'id': 'c'},
              ]
            : <Object?>[],
      },
    ],
    'assignedChanges': [
      for (final p in assigned) {'filePath': p},
    ],
  };

  setUp(() {
    tmp = Directory.systemTemp.createTempSync('claude-ncv-g6-');
    scriptsDir = Directory('${tmp.path}/scripts')..createSync();
    File('${scriptsDir.path}/pr-pair.sh').writeAsStringSync(_fakeScript('pp'));
    butDir = Directory('${tmp.path}/but')..createSync();
    File('${butDir.path}/but').writeAsStringSync(_fakeBut);
    if (!Platform.isWindows) {
      Process.runSync('chmod', ['+x', '${butDir.path}/but']);
    }
    shimExe('${butDir.path}/but');
    originDir = Directory('${tmp.path}/origin.git')..createSync();
    sh(originDir.path, ['init', '-q', '--bare', '-b', 'main']);
    repoDir = Directory('${tmp.path}/repo')..createSync();
    gitIn(['init', '-q', '-b', 'main']);
    gitIn(['config', 'user.name', 'T']);
    gitIn(['config', 'user.email', 't@example.com']);
    gitIn(['config', 'commit.gpgsign', 'false']);
    gitIn(['config', 'core.autocrlf', 'false']);
    write('base.txt', 'base\n');
    write(_settings, 'validate: x\n');
    gitIn(['add', '-A']);
    gitIn(['commit', '-q', '-m', 'base']);
    gitIn(['remote', 'add', 'origin', posix(originDir.path)]);
    gitIn(['push', '-q', 'origin', 'main']);
    baseSha = gitIn(['rev-parse', 'HEAD']);
    setStatus();
  });
  tearDown(() => tmp.deleteSync(recursive: true));

  Map<String, String> environment() {
    final env = Map<String, String>.of(Platform.environment);
    final key = env.keys.firstWhere(
      (k) => k.toUpperCase() == 'PATH',
      orElse: () => 'PATH',
    );
    final sep = Platform.isWindows ? ';' : ':';
    env[key] = '${posix(butDir.path)}$sep${env[key] ?? ''}';
    env['BUT_DIR'] = posix(butDir.path);
    return env;
  }

  VcsSession session({
    String command = 'state',
    String? branch,
    String? messageFile,
    String? login,
    String? mergedCommit,
    String? prefix,
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
      login: login,
      mergedCommit: mergedCommit,
      prefix: prefix,
      force: force,
      paths: paths,
    );
    return VcsSession(
      VcsContext(request),
      repo,
      repo,
      ProbeInfo('gitbutler', 'main', repo, ''),
      VcsScripts(fence: fakeFence(scriptsDir)),
    );
  }

  Future<Map<String, Object?>> op(
    String command,
    VcsSession s, {
    Map<String, String>? env,
  }) => runGitbutlerOperation(s, command, environment: env ?? environment());

  Future<Map<String, Object?>> state(VcsSession s) =>
      GitButler(s, environment: environment()).state();

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
    Map<String, Object?>? extra,
  }) {
    expect(stop.error, error);
    expect(stop.code, code);
    if (message != null) expect(stop.message, message);
    if (messageHas != null) expect(stop.message, contains(messageHas));
    if (extra != null) expect(stop.extra, extra);
  }

  /// Makes `refs/heads/<name>` point at a new commit on top of [base] that
  /// holds [files] (path to text).
  String makeBranch(String name, {Map<String, String> files = const {}}) {
    if (files.isEmpty) {
      gitIn(['branch', name, baseSha]);
      return baseSha;
    }
    gitIn(['checkout', '-q', '-b', 'tmp-$name', baseSha]);
    for (final e in files.entries) {
      write(e.key, e.value);
    }
    gitIn(['add', '-A']);
    gitIn(['commit', '-q', '-m', 'on $name']);
    final sha = gitIn(['rev-parse', 'HEAD']);
    gitIn(['checkout', '-q', 'main']);
    gitIn(['branch', '-q', '-M', 'tmp-$name', name]);
    return sha;
  }

  String messageFile([String text = 'a message\n']) {
    final f = File('${tmp.path}/msg.txt')..writeAsStringSync(text);
    return posix(f.path);
  }

  group('but_run', () {
    test('a failing write gives but\'s stderr and the autocrlf hint', () async {
      gitIn(['config', 'core.autocrlf', 'true']);
      but('rc.branch', '1');
      but('err.branch', 'cannot make it\n');
      final stop = await stopOf(
        () => op('branch-create', session(branch: 'feat')),
      );
      expectStop(
        stop,
        'but_error',
        message:
            'cannot make it\nhint: core.autocrlf is true; GitButler '
            'checkouts can conflict on line endings',
      );
    });

    test('a failing status has no hint and the "failed" fallback', () async {
      gitIn(['config', 'core.autocrlf', 'true']);
      File('${butDir.path}/out.status').deleteSync();
      but('rc.status', '2');
      final stop = await stopOf(() => state(session()));
      expectStop(stop, 'but_error', message: 'but status --json failed');
    });

    test('invalid bytes in but output become U+FFFD', () async {
      but('rc.branch', '1');
      File('${butDir.path}/err.branch')
          .writeAsBytesSync([0x62, 0x61, 0x64, 0xff, 0x0a]);
      final stop = await stopOf(
        () => op('branch-create', session(branch: 'feat')),
      );
      expect(stop.message, 'bad\u{fffd}');
    });

    test('output past the cap kills but and stops', () async {
      but('hook.status', 'head -c 20000 /dev/zero\ncd /\nexec sleep 5\n');
      final watch = Stopwatch()..start();
      final stop = await stopOf(
        () => GitButler(
          session(),
          environment: environment(),
        ).butRun(['status', '--json'], cap: 1000),
      );
      expectStop(
        stop,
        'but_output_too_large',
        message: 'but status printed more than 1000 bytes; nothing was changed',
      );
      expect(watch.elapsed, lessThan(const Duration(seconds: 15)));
    }, timeout: const Timeout(Duration(seconds: 60)));

    test('a missing work directory is tool_missing', () async {
      final s = session();
      repoDir.deleteSync(recursive: true);
      final stop = await stopOf(
        () => GitButler(s, environment: environment()).butRun(['status']),
      );
      expectStop(stop, 'tool_missing', messageHas: 'but could not run: ');
    });
  });

  group('but status', () {
    test('invalid JSON is a but_error', () async {
      but('out.status', 'not json');
      final stop = await stopOf(() => state(session()));
      expectStop(
        stop,
        'but_error',
        message: 'but status --json returned invalid JSON',
      );
    });

    test('a JSON document that is not an object is a but_error', () async {
      but('out.status', '[1]');
      final stop = await stopOf(() => state(session()));
      expectStop(
        stop,
        'but_error',
        message: 'but status --json returned an unexpected document',
      );
    });
  });

  group('state', () {
    test(
      'no branch: on main, uncommitted paths unassigned, key order',
      () async {
        setStatus(
          stacks: [
            stack('other', assigned: ['o.txt']),
          ],
          uncommitted: ['u.txt'],
        );
        final doc = await state(session());
        expect(doc.keys.toList(), [
          'ok',
          'backend',
          'main',
          'branch',
          'on_main',
          'applied',
          'head',
          'target',
          'applied_branches',
          'change_paths',
          'unassigned_paths',
          'other_branch_paths',
          'clean',
          'dirty_paths',
          'dirty',
          'behind',
          'behind_truncated',
        ]);
        expect(doc, {
          'ok': true,
          'backend': 'gitbutler',
          'main': 'main',
          'branch': '',
          'on_main': true,
          'applied': false,
          'head': '',
          'target': baseSha,
          'applied_branches': ['other'],
          'change_paths': <String>[],
          'unassigned_paths': ['u.txt'],
          'other_branch_paths': [
            {'path': 'o.txt', 'branch': 'other'},
          ],
          'clean': true,
          'dirty_paths': ['u.txt', 'o.txt'],
          'dirty': [
            {'status': '', 'path': 'u.txt'},
            {'status': '', 'path': 'o.txt'},
          ],
          'behind': <Object?>[],
          'behind_truncated': false,
        });
      },
    );

    test('an applied branch owns its assigned, its change dir and its '
        'touched files', () async {
      final tip = makeBranch('c/feat', files: {'t.txt': 't\n'});
      setStatus(
        stacks: [
          stack('c/feat', assigned: ['a.txt']),
        ],
        uncommitted: [
          'openspec/changes/feat/proposal.md',
          't.txt',
          'x.txt',
          'a.txt',
        ],
      );
      final doc = await state(session(branch: 'c/feat'));
      expect(doc['branch'], 'c/feat');
      expect(doc['applied'], true);
      expect(doc['on_main'], false);
      expect(doc['head'], tip);
      expect(doc['change_paths'], [
        'a.txt',
        'openspec/changes/feat/proposal.md',
        't.txt',
      ]);
      expect(doc['unassigned_paths'], ['x.txt']);
      expect(doc['clean'], false);
    });

    test('the change dir follows --prefix', () async {
      makeBranch('feat');
      setStatus(
        stacks: [stack('feat')],
        uncommitted: ['docs/changes/feat/p.md', 'openspec/changes/feat/q.md'],
      );
      final doc = await state(session(branch: 'feat', prefix: '/docs\\'));
      expect(doc['change_paths'], ['docs/changes/feat/p.md']);
    });

    test('a sibling stack holding an edit of the settings stops', () async {
      makeBranch('feat');
      setStatus(
        stacks: [
          stack('feat'),
          stack('sib', assigned: [_settings]),
        ],
      );
      final stop = await stopOf(() => state(session(branch: 'feat')));
      expectStop(
        stop,
        'settings_not_pinned',
        messageHas: 'holds an uncommitted edit of $_settings from branch sib',
      );
    });

    test('a branch whose settings differ from HEAD stops', () async {
      makeBranch('feat', files: {_settings: 'validate: y\n'});
      setStatus(stacks: [stack('feat')]);
      final stop = await stopOf(() => state(session(branch: 'feat')));
      expectStop(
        stop,
        'settings_not_pinned',
        message:
            'another applied branch changes $_settings, so the work tree\'s '
            'settings are not those of feat; unapply that branch, or bring '
            'the change onto feat, first',
      );
    });
  });

  group('operations', () {
    test(
      'switch to main needs nothing, to another branch needs it applied',
      () async {
        expect(await op('switch', session(branch: 'main')), {
          'ok': true,
          'backend': 'gitbutler',
          'branch': 'main',
          'switched': false,
        });
        final stop = await stopOf(() => op('switch', session(branch: 'feat')));
        expectStop(
          stop,
          'branch_not_applied',
          extra: {'branch': 'feat'},
          messageHas: 'branch feat is not applied in the GitButler workspace',
        );
        setStatus(stacks: [stack('feat')]);
        expect(
          (await op('switch', session(branch: 'feat')))['switched'],
          false,
        );
      },
    );

    test('a missing --branch is a usage stop', () async {
      final stop = await stopOf(() => op('switch', session()));
      expectStop(stop, 'usage', code: 2, message: 'missing --branch');
    });

    test('merge and advance are unsupported_combination', () async {
      for (final c in ['merge', 'advance']) {
        final stop = await stopOf(() => op(c, session()));
        expectStop(
          stop,
          'unsupported_combination',
          message:
              '$c has no GitButler meaning: vcs: gitbutler runs only with '
              'finish: pr, where the PR merges on GitHub',
        );
      }
    });

    test('anything else is unsupported', () async {
      final stop = await stopOf(() => op('bogus', session()));
      expectStop(
        stop,
        'unsupported',
        message: 'the GitButler backend does not implement bogus yet',
      );
    });
  });

  group('branch-create', () {
    test('an existing ref stops', () async {
      makeBranch('feat');
      final stop = await stopOf(
        () => op('branch-create', session(branch: 'feat')),
      );
      expectStop(
        stop,
        'branch_exists',
        extra: {'branch': 'feat'},
        messageHas: 'branch feat already exists (applied or not)',
      );
    });

    test('creates the branch on the target with no commits', () async {
      but(
        'hook.branch',
        'git branch "\$3" $baseSha\n'
            'printf \'%s\' \'${jsonEncode({
              'stacks': [stack('feat')],
              'uncommittedChanges': <Object?>[],
              'mergeBase': {'commitId': baseSha},
            })}\' > "\$BUT_DIR/out.status"\n',
      );
      final doc = await op('branch-create', session(branch: 'feat'));
      expect(doc, {
        'ok': true,
        'backend': 'gitbutler',
        'branch': 'feat',
        'commit': baseSha,
        'applied': true,
      });
      expect(butLog(), contains('branch new feat --json'));
    });

    test('a branch that is not applied after the create stops', () async {
      but('hook.branch', 'git branch "\$3" $baseSha\n');
      final stop = await stopOf(
        () => op('branch-create', session(branch: 'feat')),
      );
      expectStop(
        stop,
        'branch_create_mismatch',
        message:
            'branch feat was created but is not applied on the target with '
            'no commits (tip $baseSha, target $baseSha)',
      );
    });
  });

  group('commit', () {
    Future<VcsStop> commitStop(List<String> paths, {String? message}) => stopOf(
      () => op(
        'commit',
        session(
          command: 'commit',
          branch: 'feat',
          messageFile: messageFile(message ?? 'a message\n'),
          paths: paths,
        ),
      ),
    );

    setUp(() {
      makeBranch('feat');
      setStatus(stacks: [stack('feat')], uncommitted: ['f.txt', 'dir/g.txt']);
    });

    test('no message file or no path is a usage stop', () async {
      final stop = await stopOf(
        () => op('commit', session(branch: 'feat', paths: ['f.txt'])),
      );
      expectStop(
        stop,
        'usage',
        code: 2,
        message:
            'commit requires --message-file and at least one path after --',
      );
    });

    test('a branch that is not applied stops', () async {
      setStatus();
      final stop = await commitStop(['f.txt']);
      expectStop(stop, 'branch_not_applied');
    });

    test('a glob stops', () async {
      final stop = await commitStop(['*.txt']);
      expectStop(
        stop,
        'bad_path',
        message:
            '*.txt contains glob characters; name the file or its '
            'directory',
        extra: {'path': '*.txt'},
      );
    });

    test('a path outside the repo or inside .git stops', () async {
      for (final p in [
        '../x',
        'a/../../x',
        '/abs',
        'C:x',
        '.git/config',
        '.',
      ]) {
        final stop = await commitStop([p]);
        expectStop(
          stop,
          'bad_path',
          message: '$p is not a path inside the repository',
          extra: {'path': p},
        );
      }
    });

    test('a path that covers another stack\'s change stops', () async {
      makeBranch('sib');
      setStatus(
        stacks: [
          stack('feat'),
          stack('sib', assigned: ['dir/s.txt']),
        ],
        uncommitted: ['dir/g.txt'],
      );
      final stop = await commitStop(['dir/']);
      expectStop(
        stop,
        'path_owned_elsewhere',
        message:
            'dir/s.txt is assigned to branch sib, not feat; nothing was '
            'committed',
        extra: {'path': 'dir/s.txt', 'branch': 'sib'},
      );
    });

    test('a path with no change stops', () async {
      final stop = await commitStop(['none.txt']);
      expectStop(
        stop,
        'nothing_to_commit',
        message: 'no changes to commit in the named paths',
      );
    });

    /// A `but commit` that commits [files] on top of the branch's tip.
    void commitHook(Map<String, String> files, {String? message}) {
      final lines = StringBuffer()
        ..writeln('old=\$(git rev-parse refs/heads/feat)')
        ..writeln('export GIT_INDEX_FILE="\$BUT_DIR/idx"')
        ..writeln('git read-tree "\$old"');
      for (final e in files.entries) {
        lines
          ..writeln('mkdir -p "\$(dirname "${e.key}")"')
          ..writeln('printf x > "${e.key}"')
          ..writeln('git add -- "${e.key}"');
      }
      lines
        ..writeln('tree=\$(git write-tree)')
        ..writeln(
          message == null
              ? 'new=\$(git commit-tree "\$tree" -p "\$old" -F "\$5")'
              : 'new=\$(printf "$message" | git commit-tree "\$tree" -p "\$old")',
        )
        ..writeln('git update-ref refs/heads/feat "\$new"')
        ..writeln('unset GIT_INDEX_FILE');
      but('hook.commit', lines.toString());
    }

    test('commits the named paths and reports what was taken', () async {
      final old = gitIn(['rev-parse', 'feat']);
      commitHook({'f.txt': 'x', 'dir/g.txt': 'x'});
      final doc = await op(
        'commit',
        session(
          command: 'commit',
          branch: 'feat',
          messageFile: messageFile(),
          paths: ['f.txt', 'dir\\', 'f.txt'],
        ),
      );
      final tip = gitIn(['rev-parse', 'feat']);
      expect(tip, isNot(old));
      expect(doc, {
        'ok': true,
        'backend': 'gitbutler',
        'branch': 'feat',
        'commit': tip,
        'files': ['dir/g.txt', 'f.txt'],
      });
      expect(butLog(), contains('commit -b feat -F'));
      expect(butLog(), contains('--json f.txt dir/'));
    });

    test(
      'a commit that holds more, or another message, is commit_mismatch',
      () async {
        final old = gitIn(['rev-parse', 'feat']);
        commitHook({'f.txt': 'x', 'extra.txt': 'x'}, message: 'other\\n');
        final stop = await commitStop(['f.txt']);
        final tip = gitIn(['rev-parse', 'feat']);
        expectStop(
          stop,
          'commit_mismatch',
          message:
              'the GitButler commit on feat is not what was asked: it holds '
              'files outside the named paths: extra.txt; its message differs '
              'from the message file; the commit was left in place (tip $tip, '
              'was $old); files taken: extra.txt, f.txt',
          extra: {
            'old_tip': old,
            'new_tip': tip,
            'files': ['extra.txt', 'f.txt'],
          },
        );
      },
    );

    // D1: the read-back reads the file text and the stored body alike, with
    // CRLF and a lone CR as LF. The hook stores the file as it is (git
    // commit-tree -F keeps its CRs); the stored body is read back folded.
    test('read-back folds a CRLF file to the stored body', () async {
      commitHook({'f.txt': 'x'});
      final doc = await op(
        'commit',
        session(
          command: 'commit',
          branch: 'feat',
          messageFile: messageFile('docs(x): subject\r\n\r\nBody line\r\n'),
          paths: ['f.txt'],
        ),
      );
      expect(doc['ok'], true);
      expect(doc['commit'], gitIn(['rev-parse', 'feat']));
    });

    test('read-back folds an interior lone CR', () async {
      commitHook({'f.txt': 'x'});
      final doc = await op(
        'commit',
        session(
          command: 'commit',
          branch: 'feat',
          messageFile: messageFile('one\rtwo\n'),
          paths: ['f.txt'],
        ),
      );
      expect(doc['ok'], true);
    });

    test('read-back with a differing body is commit_mismatch', () async {
      final old = gitIn(['rev-parse', 'feat']);
      commitHook({
        'f.txt': 'x',
      }, message: 'docs(x): subject\\n\\nOther line\\n');
      final stop = await commitStop([
        'f.txt',
      ], message: 'docs(x): subject\r\n\r\nBody line\r\n');
      final tip = gitIn(['rev-parse', 'feat']);
      expect(tip, isNot(old), reason: 'the new tip is left in place');
      expectStop(
        stop,
        'commit_mismatch',
        messageHas: 'its message differs from the message file',
        extra: {
          'old_tip': old,
          'new_tip': tip,
          'files': ['f.txt'],
        },
      );
    });

    // The old estimate quoted every argument and stopped a Windows commit at
    // 32,000 bytes; the real `but commit` line of these paths fits the limit.
    test('paths over the old 32,000-byte estimate commit', () async {
      final names = [
        for (var i = 0; i < 1250; i++)
          'many/${'n' * 14}${i.toString().padLeft(5, '0')}',
      ];
      for (final name in names) {
        write(name, 'x\n');
      }
      expect(
        names.fold<int>(0, (n, p) => n + p.length + 3),
        greaterThan(32000),
        reason: 'over the old quoted estimate',
      );
      setStatus(stacks: [stack('feat')], uncommitted: names);
      but('hook.commit', '''
old=\$(git rev-parse refs/heads/feat)
export GIT_INDEX_FILE="\$BUT_DIR/idx"
git read-tree "\$old"
git add -A -- many
tree=\$(git write-tree)
new=\$(git commit-tree "\$tree" -p "\$old" -F "\$5")
git update-ref refs/heads/feat "\$new"
unset GIT_INDEX_FILE
''');
      final doc = await op(
        'commit',
        session(
          command: 'commit',
          branch: 'feat',
          messageFile: messageFile(),
          paths: names,
        ),
      );
      expect(doc['ok'], true);
      expect(doc['files'], hasLength(names.length));
    });

    // D1 on POSIX: no estimate. The OS refuses the start with E2BIG, which
    // the commit launch reports as too_many_paths; a start that fails for any
    // other reason stays tool_missing.
    final posixOnly = Platform.isWindows ? 'POSIX only' : false;

    test(
      'an environment past ARG_MAX at the commit is too_many_paths',
      () async {
        final pads = {for (var i = 0; i < 100; i++) 'SW_PAD_$i': 'x' * 100000};
        final stop = await stopOf(
          () => op(
            'commit',
            session(
              command: 'commit',
              branch: 'feat',
              messageFile: messageFile(),
              paths: ['f.txt'],
            ),
            // the `but status` read before the commit runs with the plain one
            env: _LateEnv(
              environment(),
              pads,
              () => butLog().contains('status'),
            ),
          ),
        );
        expect(stop.error, 'too_many_paths', reason: stop.message);
        expectStop(
          stop,
          'too_many_paths',
          message:
              'named paths and message exceed the command-line limit; name a '
              'containing directory instead',
        );
        expect(butLog(), isNot(contains('commit')), reason: 'no start');
      },
      skip: posixOnly,
    );

    test('a but removed after the last read is tool_missing', () async {
      but('hook.status', 'rm "\$BUT_DIR/but"\n');
      final stop = await commitStop(['f.txt']);
      expectStop(stop, 'tool_missing', messageHas: 'but could not run');
    }, skip: posixOnly);

    test('a but swapped for a script with a missing interpreter is '
        'tool_missing, not too_many_paths', () async {
      but('hook.status', r'''
printf '#!/no/such/interpreter\n' > "$BUT_DIR/but.new"
chmod +x "$BUT_DIR/but.new"
mv "$BUT_DIR/but.new" "$BUT_DIR/but"
''');
      final stop = await commitStop(['f.txt']);
      expectStop(stop, 'tool_missing');
    }, skip: posixOnly);

    // D1 on Windows: no estimate, the launcher's own refusal. `but.exe` is
    // first on PATH for the `but status` read; the commit's line is the real
    // one, resolved path and all.
    final windowsOnly = Platform.isWindows ? false : 'Windows only';

    List<String> manyNames(int count, int width) => [
      for (var i = 0; i < count; i++)
        'many/${'n' * (width - 8)}${i.toString().padLeft(3, '0')}',
    ];

    /// `but.exe` on PATH until a `but status` has been logged, `but.cmd` (the
    /// only `but` in [cmdDir]) from then on: every read before the commit runs
    /// through the exe, the commit launch resolves the batch file.
    Map<String, String> exeThenCmd(Directory cmdDir) {
      final base = environment();
      final key = base.keys.firstWhere((k) => k.toUpperCase() == 'PATH');
      base['PATHEXT'] = '.COM;.EXE;.BAT;.CMD';
      return _LateEnv(base, {
        key: cmdDir.path,
      }, () => butLog().contains('status'));
    }

    Directory batchBut() {
      final dir = Directory('${tmp.path}/cmd-bin')..createSync();
      File(
        '${dir.path}/but.cmd',
      ).writeAsStringSync('@echo off\r\necho invoked> "%~dp0invoked.txt"\r\n');
      return dir;
    }

    test(
      'windows: but.exe line over the limit is too_many_paths, no start',
      () async {
        // 1,500 paths of 23 units: the real line is over 32,766 units
        final names = manyNames(1500, 22);
        setStatus(stacks: [stack('feat')], uncommitted: names);
        final stop = await commitStop(names);
        expectStop(stop, 'too_many_paths');
        expect(butLog(), isNot(contains('commit')), reason: 'no start');
      },
      skip: windowsOnly,
    );

    test(
      'windows: but.exe then but.cmd over the batch cap is too_many_paths',
      () async {
        // 450 paths of 29 units: over the 8,191-unit batch payload cap, under
        // the native limit
        final names = manyNames(450, 28);
        setStatus(stacks: [stack('feat')], uncommitted: names);
        final cmdDir = batchBut();
        final stop = await stopOf(
          () => op(
            'commit',
            session(
              command: 'commit',
              branch: 'feat',
              messageFile: messageFile(),
              paths: names,
            ),
            env: exeThenCmd(cmdDir),
          ),
        );
        expectStop(stop, 'too_many_paths');
        expect(File('${cmdDir.path}/invoked.txt').existsSync(), isFalse);
        expect(butLog(), isNot(contains('commit')), reason: 'no start');
      },
      skip: windowsOnly,
    );

    test('windows: but.cmd with % in the resolved message path', () async {
      final cmdDir = batchBut();
      final work = Directory('${tmp.path}/a%b')..createSync();
      File('${work.path}/msg.txt').writeAsStringSync('a message\n');
      final previous = Directory.current;
      Directory.current = work;
      try {
        await expectLater(
          op(
            'commit',
            session(
              command: 'commit',
              branch: 'feat',
              messageFile: 'msg.txt',
              paths: ['f.txt'],
            ),
            env: exeThenCmd(cmdDir),
          ),
          throwsA(isA<UnsafeBatchArgument>()),
        );
      } finally {
        Directory.current = previous;
      }
      expect(File('${cmdDir.path}/invoked.txt').existsSync(), isFalse);
      expect(butLog(), isNot(contains('commit')), reason: 'never invoked');
    }, skip: windowsOnly);
  });

  group('pull', () {
    setUp(() => makeBranch('feat'));

    test('another applied branch skips the pull', () async {
      setStatus(stacks: [stack('feat'), stack('sib')]);
      expect(await op('pull', session(command: 'pull', branch: 'feat')), {
        'ok': true,
        'backend': 'gitbutler',
        'branch': 'feat',
        'pulled': false,
        'reason': 'pull_skipped',
        'applied_branches': ['sib'],
        'worktrees': <String>[],
      });
      expect(butLog(), isNot(contains('pull')));
    });

    test('a linked worktree skips the pull', () async {
      setStatus(stacks: [stack('feat')]);
      final wt = posix('${tmp.path}/wt');
      gitIn(['worktree', 'add', '-q', '--detach', wt]);
      final doc = await op('pull', session(command: 'pull', branch: 'feat'));
      expect(doc['pulled'], false);
      expect(doc['applied_branches'], <String>[]);
      expect((doc['worktrees']! as List).single, endsWith('/wt'));
    });

    test('a pull on a plain remote runs but directly and reports', () async {
      setStatus(stacks: [stack('feat')]);
      but('out.pull', '{"status": "updated"}');
      final doc = await op('pull', session(command: 'pull', branch: 'feat'));
      expect(doc, {
        'ok': true,
        'backend': 'gitbutler',
        'branch': 'feat',
        'pulled': true,
        'status': 'updated',
        'target': baseSha,
        'applied_branches': ['feat'],
      });
      expect(butLog(), contains('pull --json'));
      expect(log('as'), isEmpty);
    });

    test('an output that is not a report is ignored', () async {
      setStatus(stacks: [stack('feat')]);
      but('out.pull', 'done');
      final doc = await op('pull', session(command: 'pull', branch: 'feat'));
      expect(doc.containsKey('status'), false);
      expect(doc['pulled'], true);
    });

    test('a GitHub origin pulls through the fence with the login', () async {
      gitIn(['remote', 'set-url', 'origin', 'https://github.com/o/r.git']);
      setStatus(stacks: [stack('feat')]);
      final doc = await op(
        'pull',
        session(command: 'pull', branch: 'feat', login: 'bot'),
      );
      expect(doc['pulled'], true);
      expect(log('as'), contains('bot|'));
      expect(log('as'), contains('but|pull|--json|'));
    });

    test('a refused fence is fence_failed with exit 3', () async {
      gitIn(['remote', 'set-url', 'origin', 'https://github.com/o/r.git']);
      setStatus(stacks: [stack('feat')]);
      File('${scriptsDir.path}/as.rc').writeAsStringSync('3');
      File('${scriptsDir.path}/as.err').writeAsStringSync('as.sh: no\n');
      final stop = await stopOf(
        () => op('pull', session(command: 'pull', branch: 'feat', login: 'b')),
      );
      expectStop(stop, 'fence_failed', code: 3, message: 'as.sh: no');
    });

    test(
      'a failed pull is but_error with the hint and the undo note',
      () async {
        gitIn(['config', 'core.autocrlf', 'true']);
        setStatus(stacks: [stack('feat')]);
        but('rc.pull', '1');
        but('err.pull', 'conflict\n');
        final stop = await stopOf(
          () => op('pull', session(command: 'pull', branch: 'feat')),
        );
        expectStop(
          stop,
          'but_error',
          message:
              'conflict\nhint: core.autocrlf is true; GitButler checkouts can '
              'conflict on line endings\nGitButler keeps its own undo '
              '(`but undo`); Specwright runs none',
        );
      },
    );
  });

  group('push', () {
    setUp(() {
      makeBranch('feat');
      setStatus(stacks: [stack('feat')]);
    });

    test('an unapplied branch stops', () async {
      setStatus();
      final stop = await stopOf(
        () => op('push', session(command: 'push', branch: 'feat')),
      );
      expectStop(stop, 'branch_not_applied');
    });

    test('a branch ref that is gone is git_error', () async {
      gitIn(['branch', '-D', 'feat']);
      final stop = await stopOf(
        () => op('push', session(command: 'push', branch: 'feat')),
      );
      expectStop(
        stop,
        'git_error',
        messageHas: 'git diff of $_settings failed',
      );
    });

    test('an unpinned work-tree edit stops with its file and ref', () async {
      write(_settings, 'vcs: gitbutler\nvalidate: x\n');
      final stop = await stopOf(
        () => op('push', session(command: 'push', branch: 'feat')),
      );
      expectStop(
        stop,
        'settings_not_pinned',
        messageHas: 'differs from the copy at refs/heads/feat',
        extra: {'file': _settings, 'ref': 'refs/heads/feat'},
      );
      expect(log('pp'), '', reason: 'no pr-pair.sh process starts');
      expect(sh(originDir.path, ['branch', '--list', 'feat']), '');
    });

    test(
      'a work tree that matches the branch pushes without pr-pair.sh',
      () async {
        write(_settings, 'vcs: gitbutler\nvalidate: x\n');
        gitIn(['add', '-A']);
        gitIn(['commit', '-q', '-m', 'pin']);
        gitIn(['branch', '-f', 'feat', 'HEAD']);
        final doc = await op('push', session(command: 'push', branch: 'feat'));
        expect(doc['ok'], true);
        expect(log('pp'), '');
      },
    );

    test('pushes the branch ref to origin and nothing else', () async {
      final tip = gitIn(['rev-parse', 'feat']);
      final doc = await op('push', session(command: 'push', branch: 'feat'));
      expect(doc, {'ok': true, 'backend': 'gitbutler', 'branch': 'feat'});
      expect(sh(originDir.path, ['rev-parse', 'refs/heads/feat']), tip);
      expect(butLog(), contains('status'));
      expect(butLog(), isNot(contains('push')));
    });

    test('a non-fast-forward push is push_rejected', () async {
      final other = Directory('${tmp.path}/other')..createSync();
      sh(other.path, ['clone', '-q', posix(originDir.path), '.']);
      sh(other.path, ['config', 'user.name', 'T']);
      sh(other.path, ['config', 'user.email', 't@example.com']);
      sh(other.path, ['config', 'commit.gpgsign', 'false']);
      sh(other.path, ['checkout', '-q', '-b', 'feat']);
      write('o.txt', 'o\n', other.path);
      sh(other.path, ['add', '-A']);
      sh(other.path, ['commit', '-q', '-m', 'o']);
      sh(other.path, ['push', '-q', 'origin', 'feat']);
      // give feat a commit of its own so the push is not a fast-forward
      makeBranch('feat2', files: {'t.txt': 't\n'});
      gitIn(['branch', '-f', 'feat', 'feat2']);
      final stop = await stopOf(
        () => op('push', session(command: 'push', branch: 'feat')),
      );
      expectStop(
        stop,
        'push_rejected',
        extra: {'branch': 'feat'},
        messageHas:
            'the remote rejected the push of feat as non-fast-forward; '
            'Specwright never forces it: the user decides (',
      );
      expect(stop.message, isNot(contains('\n')));
    });
  });

  group('fetch-main and delete-branch', () {
    test('fetch-main reports the fetched commit', () async {
      final doc = await op('fetch-main', session(command: 'fetch-main'));
      expect(doc, {
        'ok': true,
        'backend': 'gitbutler',
        'ref': baseSha,
        'commit': baseSha,
      });
    });

    test('a bad --merged-commit is a usage stop', () async {
      final stop = await stopOf(
        () => op('delete-branch', session(branch: 'feat', mergedCommit: 'xyz')),
      );
      expectStop(
        stop,
        'usage',
        code: 2,
        message: '--merged-commit must be a commit id of 7 to 40 hex digits',
      );
    });

    test('a branch with no ref is already deleted', () async {
      expect(await op('delete-branch', session(branch: 'feat')), {
        'ok': true,
        'backend': 'gitbutler',
        'branch': 'feat',
        'deleted': false,
        'reason': 'already_deleted',
      });
    });

    test('a branch not applied stops', () async {
      makeBranch('feat');
      final stop = await stopOf(
        () => op('delete-branch', session(branch: 'feat')),
      );
      expectStop(stop, 'branch_not_applied');
    });

    test('a tip missing from the fetched main is not_merged', () async {
      makeBranch('feat', files: {'t.txt': 't\n'});
      setStatus(stacks: [stack('feat')]);
      final stop = await stopOf(
        () => op('delete-branch', session(branch: 'feat')),
      );
      expectStop(
        stop,
        'not_merged',
        message:
            'branch feat is not merged into the fetched main; nothing was '
            'deleted',
        extra: {'branch': 'feat'},
      );
      expect(butLog(), isNot(contains('delete')));
    });

    test('a merged branch the base does not hold stays applied', () async {
      final tip = makeBranch('feat', files: {'t.txt': 't\n'});
      setStatus(stacks: [stack('feat')]);
      final doc = await op(
        'delete-branch',
        session(branch: 'feat', force: true),
      );
      expect(doc, {
        'ok': true,
        'backend': 'gitbutler',
        'branch': 'feat',
        'deleted': false,
        'reason': 'left_applied',
        'base': baseSha,
        'message':
            'branch feat stays applied: the workspace base $baseSha does not '
            "hold its merge yet; the user's next `but pull` removes it",
      });
      expect(tip, isNot(baseSha));
    });

    test('--merged-commit proves the merge for a force delete', () async {
      final tip = makeBranch('feat', files: {'t.txt': 't\n'});
      setStatus(stacks: [stack('feat')], base: tip);
      // the base holds the tip itself: no proof needed beyond it
      final doc = await op(
        'delete-branch',
        session(branch: 'feat', force: true, mergedCommit: baseSha),
      );
      expect(doc['deleted'], true);
      expect(butLog(), contains('branch delete feat --json'));
    });

    test('a merged branch is deleted through but', () async {
      makeBranch('feat');
      setStatus(stacks: [stack('feat')]);
      final doc = await op('delete-branch', session(branch: 'feat'));
      expect(doc, {
        'ok': true,
        'backend': 'gitbutler',
        'branch': 'feat',
        'deleted': true,
      });
      expect(butLog(), contains('branch delete feat --json'));
    });
  });

  group('gitbutlerPath', () {
    test('normalizes and marks directories', () async {
      final gb = GitButler(session());
      Directory('${repoDir.path}/dir').createSync();
      expect(gb.gitbutlerPath('.\\a//b/./c.txt'), 'a/b/c.txt');
      expect(gb.gitbutlerPath('dir'), 'dir/');
      expect(gb.gitbutlerPath('a/'), 'a/');
      expect(gb.gitbutlerPath('a/../b'), 'b');
    });
  });
}

/// An environment that holds [_late] on top of [_base] once [_on] says so, read
/// at each lookup, so a test can change what a launch sees between two
/// launches (what `but` resolves to, or how large the environment is).
class _LateEnv extends MapBase<String, String> {
  _LateEnv(this._base, this._late, this._on);

  final Map<String, String> _base;
  final Map<String, String> _late;
  final bool Function() _on;

  @override
  String? operator [](Object? key) =>
      _on() && _late.containsKey(key) ? _late[key] : _base[key];

  @override
  void operator []=(String key, String value) => _base[key] = value;

  @override
  void clear() => _base.clear();

  @override
  Iterable<String> get keys =>
      _on() ? {..._base.keys, ..._late.keys} : _base.keys;

  @override
  String? remove(Object? key) => _base.remove(key);
}
