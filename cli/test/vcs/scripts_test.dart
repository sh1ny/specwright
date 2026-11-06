import 'dart:convert';
import 'dart:io';

import 'package:specwright_cli/src/cli.dart';
import 'package:specwright_cli/src/vcs/codec.dart';
import 'package:specwright_cli/src/vcs/scripts.dart';
import 'package:specwright_cli/src/vcs/stop.dart';
import 'package:specwright_cli/src/vcs/tool_runner.dart';
import 'package:test/test.dart';

import 'bash_support.dart';

/// A `pr-pair.sh` that logs its arguments (one line per call) and answers
/// `vcs` and `context` from files next to it.
const _fakePrPair = r'''#!/usr/bin/env bash
d=$(dirname "$0")
for a in "$@"; do printf '%s|' "$a" >> "$d/calls.log"; done
printf '\n' >> "$d/calls.log"
case "$1" in
  vcs|context)
    [ -f "$d/$1.out" ] && cat "$d/$1.out"
    [ -f "$d/$1.err" ] && cat "$d/$1.err" >&2
    exit "$(cat "$d/$1.rc" 2>/dev/null || echo 0)"
    ;;
esac
exit 9
''';

/// An `as.sh` that logs its working directory and arguments and answers from
/// files next to it.
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
  void put(String name, String text) =>
      File('${scriptsDir.path}/$name').writeAsStringSync(text);
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

  group('readSettings', () {
    test('code role: reads the backend, main and login', () async {
      put('vcs.out', '{"ok": true, "code": "jj", "store": "git"}\n');
      put(
        'context.out',
        '{"ok": true, "code": {"login": "bot", "main": "trunk"}, '
            '"store": {"login": "other", "main": "dev"}}\n',
      );
      final s = await readSettings(
        scripts(),
        code: code(),
        repo: code(),
        role: 'code',
      );
      expect((s.backend, s.main, s.login), ('jj', 'trunk', 'bot'));
      expect(lines('calls.log'), [
        'vcs|--code|${code()}|',
        'context|--code|${code()}|--only|repos|',
      ]);
    }, skip: skip);

    test(
      'store role: reads the store backend and passes --store <repo>',
      () async {
        put('vcs.out', '{"ok": true, "code": "gitbutler", "store": "jj"}');
        put(
          'context.out',
          '{"ok": true, "code": {"login": "bot", "main": "trunk"}, '
              '"store": {"login": "keeper", "main": "dev"}}',
        );
        final storeDir = Directory('${tmp.path}/store')..createSync();
        final store = posix(storeDir.path);
        final s = await readSettings(
          scripts(),
          code: code(),
          repo: store,
          role: 'store',
        );
        expect((s.backend, s.main, s.login), ('jj', 'dev', 'keeper'));
        expect(lines('calls.log'), [
          'vcs|--code|${code()}|',
          'context|--code|${code()}|--only|repos|--store|$store|',
        ]);
      },
      skip: skip,
    );

    test('an absent main or login is the empty string', () async {
      put('vcs.out', '{"ok": true, "code": "git", "store": "git"}');
      put('context.out', '{"ok": true, "code": {"main": null}}');
      final s = await readSettings(
        scripts(),
        code: code(),
        repo: code(),
        role: 'code',
      );
      expect((s.backend, s.main, s.login), ('git', '', ''));
      put('context.out', '{"ok": true}');
      final t = await readSettings(
        scripts(),
        code: code(),
        repo: code(),
        role: 'code',
      );
      expect((t.main, t.login), ('', ''));
    }, skip: skip);

    test('pr-pair.sh vcs failing with a document keeps its error and message, exit capped at 3', () async {
      put(
        'vcs.out',
        '{"ok": false, "error": "unknown_vcs", "message": "unknown code VCS \'svn\'"}',
      );
      for (final (rc, want) in [(1, 1), (2, 2), (3, 3), (7, 3)]) {
        put('vcs.rc', '$rc');
        final stop = await stopOf(
          () =>
              readSettings(scripts(), code: code(), repo: code(), role: 'code'),
        );
        expect(
          (stop.error, stop.message, stop.code),
          ('unknown_vcs', "unknown code VCS 'svn'", want),
          reason: 'rc $rc',
        );
      }
    }, skip: skip);

    test(
      'a failure document without error or message gets the defaults',
      () async {
        put('vcs.out', '{"ok": false}');
        put('vcs.rc', '1');
        final stop = await stopOf(
          () =>
              readSettings(scripts(), code: code(), repo: code(), role: 'code'),
        );
        expect(
          (stop.error, stop.message, stop.code),
          ('settings_error', 'could not read VCS settings', 1),
        );
      },
      skip: skip,
    );

    test('pr-pair.sh vcs failing without JSON says what it printed', () async {
      put('vcs.out', 'plain out\n');
      put('vcs.err', '  boom on stderr \n');
      put('vcs.rc', '2');
      var stop = await stopOf(
        () => readSettings(scripts(), code: code(), repo: code(), role: 'code'),
      );
      expect(
        (stop.error, stop.message, stop.code),
        ('settings_error', 'boom on stderr', 2),
      );
      File('${scriptsDir.path}/vcs.err').deleteSync();
      stop = await stopOf(
        () => readSettings(scripts(), code: code(), repo: code(), role: 'code'),
      );
      expect(stop.message, 'plain out');
    }, skip: skip);

    test(
      'a missing pr-pair.sh is a settings_error with bash\'s words',
      () async {
        File('${scriptsDir.path}/pr-pair.sh').deleteSync();
        final stop = await stopOf(
          () =>
              readSettings(scripts(), code: code(), repo: code(), role: 'code'),
        );
        expect(stop.error, 'settings_error');
        expect(stop.message, isNotEmpty);
        expect(stop.code, 3, reason: 'bash exits 127, capped at 3');
      },
      skip: skip,
    );

    test('invalid JSON from pr-pair.sh vcs is a settings_error', () async {
      put('vcs.out', 'not json');
      final stop = await stopOf(
        () => readSettings(scripts(), code: code(), repo: code(), role: 'code'),
      );
      expect(
        (stop.error, stop.message, stop.code),
        ('settings_error', 'pr-pair.sh vcs returned invalid JSON', 1),
      );
    }, skip: skip);

    test('an unusable backend is a settings_error', () async {
      for (final text in [
        '{"ok": true, "code": "hg", "store": "git"}',
        '{"ok": true, "store": "git"}',
        '{"ok": true, "code": "git", "store": "gitbutler"}',
      ]) {
        put('vcs.out', text);
        final stop = await stopOf(
          () => readSettings(
            scripts(),
            code: code(),
            repo: code(),
            role: text.contains('"store": "gitbutler"') ? 'store' : 'code',
          ),
        );
        expect(
          (stop.error, stop.message, stop.code),
          (
            'settings_error',
            'pr-pair.sh vcs did not return a valid backend',
            1,
          ),
          reason: text,
        );
      }
    }, skip: skip);

    test(
      'invalid JSON from pr-pair.sh context is checked before its exit',
      () async {
        put('vcs.out', '{"ok": true, "code": "git", "store": "git"}');
        put('context.out', 'nope');
        put('context.rc', '1');
        final stop = await stopOf(
          () =>
              readSettings(scripts(), code: code(), repo: code(), role: 'code'),
        );
        expect(
          (stop.error, stop.message, stop.code),
          ('settings_error', 'pr-pair.sh context returned invalid JSON', 1),
        );
      },
      skip: skip,
    );

    test(
      'pr-pair.sh context failing keeps its document, exit capped at 3',
      () async {
        put('vcs.out', '{"ok": true, "code": "git", "store": "git"}');
        put(
          'context.out',
          '{"ok": false, "error": "bad_setting", "message": "line 3: why"}',
        );
        put('context.rc', '2');
        var stop = await stopOf(
          () =>
              readSettings(scripts(), code: code(), repo: code(), role: 'code'),
        );
        expect(
          (stop.error, stop.message, stop.code),
          ('bad_setting', 'line 3: why', 2),
        );
        put('context.out', '{"ok": false}');
        put('context.rc', '9');
        stop = await stopOf(
          () =>
              readSettings(scripts(), code: code(), repo: code(), role: 'code'),
        );
        expect(
          (stop.error, stop.message, stop.code),
          ('settings_error', 'could not read repository settings', 3),
        );
      },
      skip: skip,
    );

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
        put('vcs.out', '{"ok": true, "code": "jj", "store": "git"}');
        put('context.out', '{"ok": true, "code": {"main": "m"}}');
        await runTool(bash, posix(tmp.path), [
          'cp',
          '${posix(scriptsDir.path)}/vcs.out',
          '${posix(scriptsDir.path)}/context.out',
          raw,
        ]);
        final s = await readSettings(
          VcsScripts(raw, bash),
          code: code(),
          repo: code(),
          role: 'code',
        );
        expect((s.backend, s.main), ('jj', 'm'));
        final log = await runTool(bash, posix(tmp.path), [
          'cat',
          '$raw/calls.log',
        ]);
        expect(decodeEscaped(log.stdout), startsWith('vcs|--code|'));
      },
      skip: Platform.isLinux ? skip : 'Linux only: macOS (APFS) and Windows refuse names that are not valid UTF-8',
    );
  });

  group('fence', () {
    test('a given login is used as is and as.sh does not run', () async {
      expect(
        await fenceLogin(scripts(), code(), github: true, login: 'KintsugiBot'),
        'KintsugiBot',
      );
      expect(await fenceLogin(scripts(), code(), github: false), '');
      expect(lines('as.log'), isEmpty);
    }, skip: skip);

    test(
      'a GitHub remote with no login resolves one with --resolve in the repo',
      () async {
        put('as.out', '  pinned-bot \n');
        final who = await fenceLogin(scripts(), code(), github: true);
        expect(who, 'pinned-bot');
        expect(lines('as.log'), ['--resolve|']);
        expect(
          posix(lines('as.cwd').single).toLowerCase(),
          endsWith('/repo'),
          reason: 'as.sh ran in the repo',
        );
      },
      skip: skip,
    );

    test('an empty login also resolves', () async {
      put('as.out', 'x\n');
      expect(await fenceLogin(scripts(), code(), github: true, login: ''), 'x');
    }, skip: skip);

    test(
      'a refused resolve is fence_failed with exit 3 and as.sh\'s words',
      () async {
        put('as.err', 'as.sh: no active github.com account\n');
        put('as.rc', '3');
        var stop = await stopOf(
          () => fenceLogin(scripts(), code(), github: true),
        );
        expect(
          (stop.error, stop.message, stop.code),
          ('fence_failed', 'as.sh: no active github.com account', 3),
        );
        File('${scriptsDir.path}/as.err').deleteSync();
        put('as.rc', '1');
        stop = await stopOf(() => fenceLogin(scripts(), code(), github: true));
        expect(
          (stop.error, stop.message, stop.code),
          ('fence_failed', 'as.sh could not resolve GitHub login', 3),
        );
      },
      skip: skip,
    );

    test('runAs passes <login> <command...> to as.sh from the repo', () async {
      put('as.out', 'pushed\n');
      put('as.err', 'note\n');
      final r = await runAs(scripts(), code(), 'KintsugiBot', [
        'git',
        'push',
        '-u',
        'origin',
        'HEAD',
      ]);
      expect((r.code, r.stdout, r.stderr), (0, 'pushed\n', 'note\n'));
      expect(lines('as.log'), ['KintsugiBot|git|push|-u|origin|HEAD|']);
      expect(posix(lines('as.cwd').single).toLowerCase(), endsWith('/repo'));
    }, skip: skip);

    test('runAs reports the exit code and output of a refusal', () async {
      put('as.err', 'as.sh: no credential for x\n');
      put('as.rc', '3');
      final r = await runAs(scripts(), code(), 'x', ['git', 'push']);
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

    void gitInit() {
      final r = Process.runSync('git', [
        'init',
        '-q',
        '-b',
        'trunk',
        repo.path,
      ]);
      expect(r.exitCode, 0, reason: '${r.stderr}');
    }

    test('a Git repository: backend, main and no jj_present', () async {
      gitInit();
      put('vcs.out', '{"ok": true, "code": "git", "store": "git"}');
      put('context.out', '{"ok": true, "code": {"main": "release"}}');
      final (code, doc) = await run('probe', []);
      expect(code, 0, reason: '$doc');
      expect(doc, {'ok': true, 'backend': 'git', 'main': 'release'});
    }, skip: skip);

    test('main falls back to what the repository has, then to main', () async {
      gitInit();
      put('vcs.out', '{"ok": true, "code": "git", "store": "git"}');
      put('context.out', '{"ok": true, "code": {}}');
      expect((await run('probe', [])).$2['main'], 'main');
    }, skip: skip);

    test('--main overrides the probed main', () async {
      gitInit();
      put('vcs.out', '{"ok": true, "code": "git", "store": "git"}');
      put('context.out', '{"ok": true, "code": {"main": "release"}}');
      final (_, doc) = await run('probe', ['--main', 'other']);
      expect(doc['main'], 'other');
    }, skip: skip);

    test('a .jj directory in a Git repository is jj_present', () async {
      gitInit();
      Directory('${repo.path}/.jj').createSync();
      put('vcs.out', '{"ok": true, "code": "git", "store": "git"}');
      put('context.out', '{"ok": true, "code": {}}');
      final (_, doc) = await run('probe', []);
      expect(doc, {
        'ok': true,
        'backend': 'git',
        'main': 'main',
        'jj_present': true,
      });
    }, skip: skip);

    test('not a Git work tree is not_repository', () async {
      put('vcs.out', '{"ok": true, "code": "git", "store": "git"}');
      put('context.out', '{"ok": true, "code": {}}');
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
        put('vcs.out', '{"ok": true, "code": "git", "store": "git"}');
        put('context.out', '{"ok": true, "code": {}}');
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
        put('vcs.out', '{"ok": true, "code": "gitbutler", "store": "git"}');
        put('context.out', '{"ok": true, "code": {}}');
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
        put(
          'vcs.out',
          '{"ok": false, "error": "unknown_vcs", "message": "unknown code VCS \'svn\'"}',
        );
        put('vcs.rc', '1');
        for (final command in ['probe', 'state', 'push']) {
          final (code, doc) = await run(command, []);
          expect(code, 1, reason: command);
          expect(doc, {
            'ok': false,
            'error': 'unknown_vcs',
            'message': "unknown code VCS 'svn'",
          }, reason: command);
        }
      },
      skip: skip,
    );

    test('the backend the settings name runs after the probe', () async {
      gitInit();
      put('vcs.out', '{"ok": true, "code": "git", "store": "git"}');
      put('context.out', '{"ok": true, "code": {}}');
      final (code, doc) = await run('state', []);
      expect(code, 0);
      expect(doc['ok'], true);
      expect(doc['backend'], 'git');
    }, skip: skip);
  });
}
