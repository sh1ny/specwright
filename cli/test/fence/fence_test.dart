import 'dart:convert';
import 'dart:typed_data';

import 'package:specwright_cli/src/fence/fence.dart';
import 'package:specwright_cli/src/fence/urls.dart';
import 'package:specwright_cli/src/pr/gh.dart';
import 'package:specwright_cli/src/process/limit_line.dart';
import 'package:specwright_cli/src/vcs/tool_runner.dart';
import 'package:test/test.dart';

GhResult ok(String out) =>
    GhResult(exitCode: 0, stdout: utf8.encode(out), stderr: Uint8List(0));

GhResult fail([int code = 1]) =>
    GhResult(exitCode: code, stdout: Uint8List(0), stderr: Uint8List(0));

ToolResult tool(String out, [int code = 0]) =>
    ToolResult(code, utf8.encode(out), Uint8List(0));

void main() {
  group('urls', () {
    test('lowerAscii folds ASCII only', () {
      expect(lowerAscii('GitHub.COM'), 'github.com');
      // U+0130 and U+212A lower-case under Unicode rules; tr A-Z a-z leaves them
      expect(lowerAscii('İK'), 'İK');
    });

    test('userinfo on a github.com URL is found, others are not', () {
      expect(ghUserinfo('https://u:p@github.com/o/r'), isTrue);
      expect(ghUserinfo('https://token@GitHub.com/o/r'), isTrue);
      expect(ghUserinfo('https://github.com/o/r'), isFalse);
      expect(ghUserinfo('https://u@example.com/o/r'), isFalse);
      expect(ghUserinfo('https://u@github.com.evil.test/o/r'), isFalse);
    });

    test('mask hides the userinfo', () {
      expect(mask('https://u:p@github.com/o/r'), 'https://***@github.com/o/r');
    });
  });

  group('environment', () {
    test('discovery drops the token and host variables', () {
      final env = discoveryEnvironment({
        'GH_TOKEN': 'a',
        'GITHUB_TOKEN': 'b',
        'GH_HOST': '',
        'GH_ENTERPRISE_TOKEN': 'c',
        'GITHUB_ENTERPRISE_TOKEN': 'd',
        'KEEP': 'e',
      }, windows: false);
      expect(env, {'KEEP': 'e'});
    });

    test('on Windows the names match without case', () {
      final env = discoveryEnvironment({
        'gh_token': 'a',
        'Github_Token': 'b',
        'KEEP': 'e',
      }, windows: true);
      expect(env, {'KEEP': 'e'});
    });

    test('originals are saved once, and only the ones that were set', () {
      final first = saveOriginals({
        'GH_HOST': 'h',
        'GIT_ASKPASS': 'x',
        'GH_TOKEN': 'never',
      }, windows: false);
      expect(first['AS_SH_ORIG_GH_HOST'], 'h');
      expect(first['AS_SH_ORIG_GIT_ASKPASS'], 'x');
      expect(first.containsKey('AS_SH_ORIG_GH_TOKEN'), isFalse);
      expect(first.containsKey('AS_SH_ORIG_SSH_ASKPASS'), isFalse);
      expect(first['AS_SH_ORIG_SET'], ' GH_HOST GIT_ASKPASS');
      // a nested run keeps the outer originals
      final nested = saveOriginals({
        ...first,
        'GH_HOST': 'changed',
      }, windows: false);
      expect(nested['AS_SH_ORIG_GH_HOST'], 'h');
      expect(nested['AS_SH_ORIG_SET'], ' GH_HOST GIT_ASKPASS');
    });

    test('the fenced environment lists the config in order', () async {
      final calls = <List<String>>[];
      Future<ToolResult> git(List<String> c, Map<String, String> e) async {
        calls.add(c);
        // unsorted, a repeat, and two keys that differ only past byte 0x7f
        return tool(
          'http.https://b/.extraheader\n'
          'http.https://a/.extraheader\n'
          'http.https://b/.extraheader\n'
          'http.https://\u{1F600}/.extraheader\n'
          'http.https://～/.extraheader\n',
        );
      }

      final env = await fencedEnvironment({'GH_TOKEN': 't', 'X': 'y'}, git);
      expect(env['GIT_TERMINAL_PROMPT'], '0');
      expect(env['GCM_INTERACTIVE'], 'never');
      expect(env['GIT_ASKPASS'], '');
      expect(env['SSH_ASKPASS'], '');
      expect(env['GIT_SSH_COMMAND'], contains('SSH is disabled'));
      expect(env['X'], 'y');
      final keys = [
        for (var i = 0; i < int.parse(env['GIT_CONFIG_COUNT']!); i++)
          env['GIT_CONFIG_KEY_$i'],
      ];
      expect(keys, [
        'http.extraHeader',
        'http.https://a/.extraheader',
        'http.https://b/.extraheader',
        'http.https://～/.extraheader',
        'http.https://\u{1F600}/.extraheader',
        'credential.helper',
        'credential.helper',
      ]);
      final n = keys.length;
      expect(env['GIT_CONFIG_VALUE_${n - 2}'], '');
      expect(env['GIT_CONFIG_VALUE_${n - 1}'], contains(r'password=$GH_TOKEN'));
      expect(calls.single.take(3), ['git', 'config', '--name-only']);
    });
  });

  group('identity', () {
    test('discovery has no token and verification has the token', () async {
      final seen = <(List<String>, bool)>[];
      Future<GhResult> gh(List<String> a, Map<String, String> e) async {
        seen.add((a, e.containsKey('GH_TOKEN')));
        return a.first == 'auth' ? ok('tok\n') : ok('me\n');
      }

      final env = await verifyIdentity('me', gh, {'KEEP': '1'});
      expect(env['GH_TOKEN'], 'tok');
      expect(seen.map((s) => s.$2), [false, true]);
      expect(seen.last.$1.first, 'api');
    });

    test('a configured account that is not the active one passes', () async {
      Future<GhResult> gh(List<String> a, Map<String, String> e) async =>
          a.first == 'auth' ? ok('other-token\n') : ok('configured\n');
      final env = await verifyIdentity('configured', gh, {});
      expect(env['GH_TOKEN'], 'other-token');
    });

    test('a token of another login is refused', () async {
      Future<GhResult> gh(List<String> a, Map<String, String> e) async =>
          a.first == 'auth' ? ok('tok\n') : ok('someone\n');
      expect(
        () => verifyIdentity('me', gh, {}),
        throwsA(
          isA<FenceStop>().having(
            (s) => s.message,
            'message',
            "as.sh: token resolves to 'someone', expected 'me'; refusing",
          ),
        ),
      );
    });

    test('no credential is refused before the identity call', () async {
      var calls = 0;
      Future<GhResult> gh(List<String> a, Map<String, String> e) async {
        calls++;
        return fail();
      }

      await expectLater(
        () => verifyIdentity('me', gh, {}),
        throwsA(
          isA<FenceStop>().having(
            (s) => s.message,
            'message',
            "as.sh: no gh credential for 'me' (gh auth login)",
          ),
        ),
      );
      expect(calls, 1);
    });

    test('a limit on the token lookup stops with exit 3', () async {
      Future<GhResult> gh(List<String> a, Map<String, String> e) async =>
          GhResult(
            exitCode: 124,
            limit: BoundedLimit.deadlineExceeded,
            limitLine: 'x',
            stdout: Uint8List(0),
            stderr: Uint8List(0),
          );
      await expectLater(
        () => verifyIdentity('me', gh, {}),
        throwsA(
          isA<FenceStop>()
              .having(
                (s) => s.message,
                'message',
                startsWith('as.sh: deadline_exceeded: gh auth token'),
              )
              .having((s) => s.code, 'code', 3),
        ),
      );
    });
  });

  group('arguments', () {
    void refused(List<String> cmd) => expect(
      () => checkArguments(cmd),
      throwsA(isA<FenceStop>().having((s) => s.code, 'code', 3)),
    );

    test('userinfo in an argument or in its value is refused, masked', () {
      refused(['git', 'clone', 'https://u:p@github.com/o/r']);
      refused(['git', '-c', 'remote.x.url=https://t@github.com/o/r', 'fetch']);
      try {
        checkArguments(['git', 'clone', 'https://u:secret@github.com/o/r']);
      } on FenceStop catch (e) {
        expect(e.message, isNot(contains('secret')));
        expect(e.message, contains('https://***@github.com/o/r'));
      }
    });

    test('a rewrite rule that adds userinfo is refused', () {
      refused([
        'git',
        '-c',
        'url.https://t@github.com/.insteadOf=https://github.com/',
        'fetch',
      ]);
    });

    test('plain arguments pass', () {
      checkArguments(['git', 'fetch', 'origin', 'https://github.com/o/r']);
    });
  });

  group('options', () {
    void refused(List<String> cmd) => expect(
      () => checkOptions(cmd),
      throwsA(isA<FenceStop>().having((s) => s.code, 'code', 3)),
    );

    test('git options that pick another repository are refused', () {
      refused(['git', '-C', 'x', 'fetch']);
      refused(['git', '--git-dir=x', 'fetch']);
      refused(['git', '--work-tree', 'x', 'fetch']);
      checkOptions(['git', '-c', 'a=b', 'fetch']);
    });

    test('but runs only pull', () {
      checkOptions(['but', 'pull']);
      refused(['but', 'push']);
      refused(['but', '-C', 'x', 'pull']);
    });

    test('jj runs only git push and git fetch', () {
      checkOptions(['jj', 'git', 'fetch']);
      checkOptions(['jj', '--color', 'never', 'git', 'push']);
      refused(['jj', 'log']);
      refused(['jj', 'git', 'clone']);
      refused(['jj', '-R', 'x', 'git', 'fetch']);
      refused(['jj', '--config', 'a=b', 'git', 'fetch']);
    });
  });

  group('remotes', () {
    test('no checks outside a work tree', () async {
      var n = 0;
      Future<ToolResult> git(List<String> c, Map<String, String> e) async {
        n++;
        return tool('false\n');
      }

      await checkRemotes(git, {});
      expect(n, 1);
    });

    test('a remote URL with userinfo is refused', () async {
      Future<ToolResult> git(List<String> c, Map<String, String> e) async {
        if (c.contains('--is-inside-work-tree')) return tool('true\n');
        if (c.length == 2) return tool('origin\n');
        if (c.contains('get-url')) {
          return tool(
            c.contains('--push')
                ? 'https://u:p@github.com/o/r\n'
                : 'https://github.com/o/r\n',
          );
        }
        return tool('');
      }

      await expectLater(
        () => checkRemotes(git, {}),
        throwsA(
          isA<FenceStop>().having(
            (s) => s.message,
            'message',
            contains("remote 'origin' push URL"),
          ),
        ),
      );
    });

    test('an insteadOf rule that adds userinfo is refused', () async {
      Future<ToolResult> git(List<String> c, Map<String, String> e) async {
        if (c.contains('--is-inside-work-tree')) return tool('true\n');
        if (c.contains('--get-regexp')) {
          return tool(
            'url.https://t@github.com/.insteadof https://github.com/\n',
          );
        }
        return tool('');
      }

      await expectLater(
        () => checkRemotes(git, {}),
        throwsA(
          isA<FenceStop>().having(
            (s) => s.message,
            'message',
            contains('rewrite rule'),
          ),
        ),
      );
    });
  });

  group('runFence', () {
    Future<(int, String, String, List<List<String>>)> run(
      List<String> argv, {
      GhCall? gh,
      GitCall? git,
    }) async {
      final out = StringBuffer();
      final err = StringBuffer();
      final launched = <List<String>>[];
      final code = await runFence(
        argv,
        environment: {'KEEP': '1'},
        gh:
            gh ??
            (a, e) async => a.first == 'auth'
                ? (a.contains('--help') ? ok('--user\n') : ok('tok\n'))
                : ok('me\n'),
        git: git ?? (c, e) async => tool('false\n'),
        launch: (c, e) async {
          launched.add(c);
          return 7;
        },
        out: out.write,
        err: err.write,
      );
      return (code, out.toString(), err.toString(), launched);
    }

    test('the command runs once checked and its status is returned', () async {
      final r = await run(['me', 'git', 'fetch']);
      expect(r.$1, 7);
      expect(r.$4, [
        ['git', 'fetch'],
      ]);
    });

    test('--resolve prints the active login', () async {
      final r = await run(['--resolve']);
      expect((r.$1, r.$2), (0, 'me\n'));
      expect(r.$4, isEmpty);
    });

    test('no arguments is the usage line, exit 1', () async {
      final r = await run([]);
      expect(r.$1, 1);
      expect(r.$3, contains('usage: as.sh <login> <command>'));
    });

    test('a login with no command is exit 2', () async {
      final r = await run(['me']);
      expect(r.$1, 2);
      expect(r.$4, isEmpty);
    });

    test(
      'a gh that cannot look up per account is refused with exit 3',
      () async {
        final r = await run(
          ['me', 'git', 'fetch'],
          gh: (a, e) async =>
              a.contains('--help') ? ok('no such flag\n') : fail(),
        );
        expect(r.$1, 3);
        expect(r.$3, contains('gh auth token --user'));
        expect(r.$4, isEmpty);
      },
    );

    test('a refused argument runs nothing', () async {
      final r = await run(['me', 'git', 'clone', 'https://u:p@github.com/o/r']);
      expect(r.$1, 3);
      expect(r.$4, isEmpty);
    });

    test(
      'input the launcher cannot represent is an as.sh stop, exit 2',
      () async {
        final err = StringBuffer();
        final code = await runFence(
          ['me', 'git', 'fetch'],
          environment: {'KEEP': '1'},
          gh: (a, e) async => a.first == 'auth'
              ? (a.contains('--help') ? ok('--user\n') : ok('tok\n'))
              : ok('me\n'),
          git: (c, e) async => tool('false\n'),
          launch: (c, e) async =>
              throw const Unrepresentable('git', 'argument'),
          out: (_) {},
          err: err.write,
        );
        expect(code, 2);
        expect(err.toString(), 'as.sh: unrepresentable argument: git\n');
      },
    );
  });
}
