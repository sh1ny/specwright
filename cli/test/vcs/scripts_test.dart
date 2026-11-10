import 'dart:convert';
import 'dart:io';

import 'package:specwright_cli/src/cli.dart';
import 'package:specwright_cli/src/vcs/codec.dart';
import 'package:specwright_cli/src/vcs/scripts.dart';
import 'package:specwright_cli/src/vcs/stop.dart';
import 'package:specwright_cli/src/vcs/tool_runner.dart';
import 'package:test/test.dart';

import 'bash_support.dart';

/// A `pr-pair.sh` that logs its arguments (one line per call): settings are read in process, so it must never run.
const _fakePrPair = r'''#!/usr/bin/env bash
d=$(dirname "$0")
for a in "$@"; do printf '%s|' "$a" >> "$d/calls.log"; done
printf '\n' >> "$d/calls.log"
exit 9
''';

/// An `as.sh` that logs its working directory and arguments: the fence runs in
/// process, so it must never run.
const _fakeAs = r'''#!/usr/bin/env bash
d=$(dirname "$0")
printf '%s\n' "$PWD" >> "$d/as.cwd"
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
  late Directory repo;

  setUp(() {
    tmp = Directory.systemTemp.createTempSync('claude-ncv-g3-');
    scriptsDir = Directory('${tmp.path}/scripts')..createSync();
    repo = Directory('${tmp.path}/repo')..createSync();
    File('${scriptsDir.path}/pr-pair.sh').writeAsStringSync(_fakePrPair);
    File('${scriptsDir.path}/as.sh').writeAsStringSync(_fakeAs);
  });
  tearDown(() => tmp.deleteSync(recursive: true));

  String posix(String p) => p.replaceAll(r'\', '/');
  List<String> lines(String name) {
    final f = File('${scriptsDir.path}/$name');
    return f.existsSync() ? f.readAsLinesSync() : <String>[];
  }

  VcsScripts scripts() => VcsScripts(posix(scriptsDir.path), bash!);
  String code() => posix(repo.path);

  Future<VcsStop> stopOf(Future<Object?> Function() body) async {
    try {
      await body();
    } on VcsStop catch (stop) {
      return stop;
    }
    fail('expected a VcsStop');
  }

  /// Writes `openspec/specwright.yaml` under the repo and makes it a Git repository with branch `trunk`.
  void settings(String yaml) {
    final f = File('${repo.path}/openspec/specwright.yaml');
    f.parent.createSync(recursive: true);
    f.writeAsStringSync(yaml);
  }

  void gitInit() {
    final r = Process.runSync('git', ['init', '-q', '-b', 'trunk', repo.path]);
    expect(r.exitCode, 0, reason: '${r.stderr}');
  }

  group('readSettings', () {
    test('code role: reads the backend, main and login in process', () async {
      gitInit();
      settings('vcs: jj\nmain_branch: trunk\ngithub:\n  login: bot\n');
      final s = await readSettings(
        scripts(),
        code: code(),
        repo: code(),
        role: 'code',
      );
      expect((s.backend, s.main, s.login), ('jj', 'trunk', 'bot'));
      expect(lines('calls.log'), isEmpty, reason: 'no pr-pair.sh process');
    }, skip: skip);

    test('store role: reads the store backend, main and login', () async {
      gitInit();
      final storeDir = Directory('${tmp.path}/store')..createSync();
      final store = posix(storeDir.path);
      settings(
        'vcs: git\nmain_branch: trunk\nplanning_store:\n  vcs: jj\n  main_branch: dev\n  login: keeper\n',
      );
      final s = await readSettings(
        scripts(),
        code: code(),
        repo: store,
        role: 'store',
      );
      expect((s.backend, s.main, s.login), ('jj', 'dev', 'keeper'));
      expect(lines('calls.log'), isEmpty);
    }, skip: skip);

    test('an absent main is detected, an absent login is empty', () async {
      gitInit();
      settings('vcs: git\n');
      final s = await readSettings(
        scripts(),
        code: code(),
        repo: code(),
        role: 'code',
      );
      expect((s.backend, s.main, s.login), ('git', 'main', ''));
    }, skip: skip);

    test('no settings file means Git', () async {
      final s = await readSettings(
        scripts(),
        code: code(),
        repo: code(),
        role: 'code',
      );
      expect((s.backend, s.login), ('git', ''));
    }, skip: skip);

    test('a refusal keeps its error code and exit status', () async {
      settings('vcs: svn\n');
      var stop = await stopOf(
        () => readSettings(scripts(), code: code(), repo: code(), role: 'code'),
      );
      expect((stop.error, stop.code), ('unknown_vcs', 1));
      expect(stop.message, startsWith('unknown code VCS '));
      expect(stop.message, contains('svn'));
      settings('planning_store:\n  vcs: gitbutler\n');
      stop = await stopOf(
        () => readSettings(scripts(), code: code(), repo: code(), role: 'code'),
      );
      expect(stop.error, 'unsupported_vcs');
      settings('vcs: gitbutler\nfinish: local\n');
      stop = await stopOf(
        () => readSettings(scripts(), code: code(), repo: code(), role: 'code'),
      );
      expect(stop.error, 'unsupported_combination');
      expect(stop.code, lessThanOrEqualTo(3));
      expect(lines('calls.log'), isEmpty);
    }, skip: skip);

    test(
      'scripts under a directory whose name holds the byte 0xFF',
      () async {
        final raw = '${posix(tmp.path)}/odd-\udcff-dir';
        final made = await runTool(bash!, posix(tmp.path), [
          'cp',
          '-r',
          posix(scriptsDir.path),
          raw,
        ]);
        expect(made.exitCode, 0, reason: decodeEscaped(made.stderr));
        gitInit();
        settings('vcs: jj\nmain_branch: m\n');
        final s = await readSettings(
          VcsScripts(raw, bash),
          code: code(),
          repo: code(),
          role: 'code',
        );
        expect((s.backend, s.main), ('jj', 'm'));
      },
      skip: Platform.isLinux ? skip : 'Linux only: macOS (APFS) and Windows refuse names that are not valid UTF-8',
    );
  });

  group('fence', () {
    // The fence runs in this process, through VcsScripts.fenced: no as.sh is
    // started (the directory holds a recording one that must stay unused). The
    // fence itself is tested in test/fence/fenced_text_test.dart.
    final calls = <(String, List<String>)>[];
    var result = TextResult(0, '', '');

    VcsScripts fenced() => VcsScripts(
      posix(scriptsDir.path),
      bash!,
      fence: (repo, argv) async {
        calls.add((repo, argv));
        return result;
      },
    );

    setUp(() {
      calls.clear();
      result = TextResult(0, '', '');
    });

    test('a given login is used as is and nothing runs', () async {
      expect(
        await fenceLogin(fenced(), code(), github: true, login: 'KintsugiBot'),
        'KintsugiBot',
      );
      expect(await fenceLogin(fenced(), code(), github: false), '');
      expect(calls, isEmpty);
      expect(lines('as.log'), isEmpty);
    }, skip: skip);

    test(
      'a GitHub remote with no login resolves one with --resolve in the repo',
      () async {
        result = TextResult(0, '  pinned-bot \n', '');
        final who = await fenceLogin(fenced(), code(), github: true);
        expect(who, 'pinned-bot');
        expect(calls.single.$1, code());
        expect(calls.single.$2, ['--resolve']);
        expect(lines('as.log'), isEmpty, reason: 'as.sh did not run');
      },
      skip: skip,
    );

    test('an empty login also resolves', () async {
      result = TextResult(0, 'x\n', '');
      expect(await fenceLogin(fenced(), code(), github: true, login: ''), 'x');
    }, skip: skip);

    test(
      'a refused resolve is fence_failed with exit 3 and the fence\'s words',
      () async {
        result = TextResult(3, '', 'as.sh: no active github.com account\n');
        var stop = await stopOf(
          () => fenceLogin(fenced(), code(), github: true),
        );
        expect(
          (stop.error, stop.message, stop.code),
          ('fence_failed', 'as.sh: no active github.com account', 3),
        );
        result = TextResult(1, '', '');
        stop = await stopOf(() => fenceLogin(fenced(), code(), github: true));
        expect(
          (stop.error, stop.message, stop.code),
          ('fence_failed', 'as.sh could not resolve GitHub login', 3),
        );
        expect(lines('as.log'), isEmpty);
      },
      skip: skip,
    );

    test(
      'runAs passes <login> <command...> to the fence for the repo',
      () async {
        result = TextResult(0, 'pushed\n', 'note\n');
        final r = await runAs(fenced(), code(), 'KintsugiBot', [
          'git',
          'push',
          '-u',
          'origin',
          'HEAD',
        ]);
        expect((r.code, r.stdout, r.stderr), (0, 'pushed\n', 'note\n'));
        expect(calls.single.$1, code());
        expect(calls.single.$2, [
          'KintsugiBot',
          'git',
          'push',
          '-u',
          'origin',
          'HEAD',
        ]);
        expect(lines('as.log'), isEmpty, reason: 'as.sh did not run');
      },
      skip: skip,
    );

    test('runAs reports the exit code and output of a refusal', () async {
      result = TextResult(3, '', 'as.sh: no credential for x\n');
      final r = await runAs(fenced(), code(), 'x', ['git', 'push']);
      expect(
        (r.code, r.stdout, r.stderr),
        (3, '', 'as.sh: no credential for x\n'),
      );
    }, skip: skip);
  });

  group('probe through sw vcs', () {
    Future<(int, Map<String, Object?>)> run(
      String command,
      List<String> extra, {
      String? where,
    }) async {
      final target = where ?? posix(repo.path);
      final records = [
        posix(scriptsDir.path),
        bash!,
        command,
        '--repo',
        target,
        '--role',
        'code',
        ...extra,
      ];
      final out = <int>[];
      final code = await runCli(
        ['vcs', '--args-stdin'],
        out: StringBuffer(),
        err: StringBuffer(),
        outBytes: out.addAll,
        readStdin: () async => [
          for (final r in records) ...[...encodeEscaped(r), 0],
        ],
      );
      return (code, jsonDecode(utf8.decode(out)) as Map<String, Object?>);
    }

    test('a Git repository: backend, main and no jj_present', () async {
      gitInit();
      settings('main_branch: release\n');
      final (code, doc) = await run('probe', []);
      expect(code, 0, reason: '$doc');
      expect(doc, {'ok': true, 'backend': 'git', 'main': 'release'});
    }, skip: skip);

    test('main falls back to what the repository has, then to main', () async {
      gitInit();
      settings('vcs: git\n');
      expect((await run('probe', [])).$2['main'], 'main');
    }, skip: skip);

    test('--main overrides the probed main', () async {
      gitInit();
      settings('main_branch: release\n');
      final (_, doc) = await run('probe', ['--main', 'other']);
      expect(doc['main'], 'other');
    }, skip: skip);

    test('a .jj directory in a Git repository is jj_present', () async {
      gitInit();
      Directory('${repo.path}/.jj').createSync();
      settings('vcs: git\n');
      final (_, doc) = await run('probe', []);
      expect(doc, {
        'ok': true,
        'backend': 'git',
        'main': 'main',
        'jj_present': true,
      });
    }, skip: skip);

    test('not a Git work tree is not_repository', () async {
      settings('vcs: git\n');
      final (code, doc) = await run('probe', []);
      expect(code, 1);
      expect(doc['error'], 'not_repository');
      expect(doc['message'], startsWith('not inside a Git work tree: '));
    }, skip: skip);

    test(
      'Git backend in a GitButler workspace is gitbutler_workspace',
      () async {
        gitInit();
        Directory('${repo.path}/.git/gitbutler').createSync();
        final set = Process.runSync('git', [
          '-C',
          repo.path,
          'config',
          'gitbutler.project.targetRef',
          'refs/heads/main',
        ]);
        expect(set.exitCode, 0);
        settings('vcs: git\n');
        final (code, doc) = await run('probe', []);
        expect(code, 1);
        expect(doc['error'], 'gitbutler_workspace');
      },
      skip: skip,
    );

    test(
      'gitbutler selected on a repo it does not manage is not_managed',
      () async {
        gitInit();
        settings('vcs: gitbutler\nfinish: pr\n');
        final (code, doc) = await run('probe', []);
        expect(code, 1);
        expect(doc['error'], 'not_managed');
        expect(
          doc['message'],
          startsWith('vcs: gitbutler selected, but GitButler'),
        );
      },
      skip: skip,
    );

    test(
      'an unknown backend stops every subcommand before its handler',
      () async {
        gitInit();
        settings('vcs: svn\n');
        for (final command in ['probe', 'state', 'push']) {
          final (code, doc) = await run(command, []);
          expect(code, 1, reason: command);
          expect(doc['error'], 'unknown_vcs', reason: command);
          expect(
            doc['message'],
            startsWith('unknown code VCS '),
            reason: command,
          );
          expect(doc['message'], contains('svn'), reason: command);
        }
      },
      skip: skip,
    );

    test('the backend the settings name runs after the probe', () async {
      gitInit();
      settings('vcs: git\n');
      final (code, doc) = await run('state', []);
      expect(code, 0);
      expect(doc['ok'], true);
      expect(doc['backend'], 'git');
    }, skip: skip);
  });
}
