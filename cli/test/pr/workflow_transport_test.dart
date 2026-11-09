import 'dart:typed_data';

import 'package:specwright_cli/src/vcs/codec.dart';

import 'dart:io';

import 'package:test/test.dart';
import 'package:specwright_cli/src/pr/gh.dart';
import 'package:specwright_cli/src/pr/pair.dart';
import 'package:specwright_cli/src/pr/workflow_transport.dart';
import 'package:specwright_cli/src/process/limits.dart';
import 'package:specwright_cli/src/process/limit_line.dart';

import '../helper_support.dart';
import '../vcs/bash_support.dart';

GhResult result(String text, [int code = 0]) => GhResult(
  exitCode: code,
  stdout: Uint8List.fromList(text.codeUnits),
  stderr: Uint8List(0),
);

void main() {
  test(
    'real workflow command preserves empty long and raw argument bytes',
    () async {
      final bash = findBash();
      expect(bash, isNotNull);
      final native = WorkflowTransport.native(
        directory: Directory.current.path,
        bash: bash!,
      );
      final transport = WorkflowTransport(
        directory: Directory.current.path,
        environment: {},
        runner: (dir, command, env, limits) async {
          if (command.contains('--help')) return result('--user');
          if (command.contains('token')) return result('token');
          if (command[0] == 'gh') return result('bot');
          if (command[0] == 'git') return result('');
          return native.runner(dir, command, native.environment, limits);
        },
      );
      final args = [
        '',
        'space quote " dollar \$ glob *',
        'é',
        List.filled(100000, 'x').join(),
        if (!Platform.isWindows) decodeEscaped([0x80, 0xff]),
      ];
      final r = await transport.fenced('bot', [
        bash,
        '-c',
        r'printf "%s\0" "$@"',
        'capture',
        ...args,
      ]);
      expect(r.exitCode, 0);
      expect(r.stdout, encodeEscaped('${args.join('\x00')}\x00'));
    },
  );
  test('typed lookup byte limit remains refusal for lower equal and larger outer caps', () async {
    final transport = WorkflowTransport(
      directory: 'repo',
      environment: {'SPECWRIGHT_NET_MAX_BYTES': '10'},
      runner: (dir, command, env, limits) async => GhResult(
        exitCode: 125,
        limit: BoundedLimit.responseTooLarge,
        stdout: Uint8List(0),
        stderr: Uint8List(0),
      ),
    );
    for (final cap in [5, 10, 100]) {
      await expectLater(
        transport.fenced(
          'bot',
          ['capture'],
          outer: RunLimits(deadline: const Duration(seconds: 1), maxBytes: cap),
        ),
        throwsA(
          isA<PairStop>().having((s) => s.error, 'error', 'fence_refused'),
        ),
      );
    }
  });

  test(
    'typed inner deadline remains refusal before longer outer deadline',
    () async {
      final transport = WorkflowTransport(
        directory: 'repo',
        environment: {'SPECWRIGHT_NET_DEADLINE': '0.01'},
        runner: (dir, command, env, limits) async => GhResult(
          exitCode: 124,
          limit: BoundedLimit.deadlineExceeded,
          stdout: Uint8List(0),
          stderr: Uint8List(0),
        ),
      );
      await expectLater(
        transport.fenced(
          'bot',
          ['capture'],
          outer: const RunLimits(deadline: Duration(seconds: 1), maxBytes: 100),
        ),
        throwsA(
          isA<PairStop>().having((s) => s.error, 'error', 'fence_refused'),
        ),
      );
    },
  );

  test('unsafe target remotes refuse with masked diagnostics', () async {
    var launched = false;
    final transport = WorkflowTransport(
      directory: 'store',
      environment: {},
      runner: (dir, command, env, limits) async {
        if (command.contains('--help')) return result('--user');
        if (command.contains('token')) return result('private-token');
        if (command[0] == 'gh') return result('bot');
        if (command.contains('--is-inside-work-tree')) return result('true\n');
        if (command.join(' ') == 'git remote') return result('origin\n');
        if (command.contains('get-url')) {
          return result('https://secret@github.com/o/store\n');
        }
        if (command[0] == 'capture') launched = true;
        return result('');
      },
    );
    await expectLater(
      transport.fenced('bot', ['capture']),
      throwsA(
        isA<PairStop>()
            .having(
              (s) => s.message,
              'masked',
              contains('https://***@github.com'),
            )
            .having(
              (s) => s.message,
              'no token',
              isNot(contains('private-token')),
            )
            .having((s) => s.message, 'no userinfo', isNot(contains('secret'))),
      ),
    );
    expect(launched, false);
  });
  test(
    'target callbacks verify separate logins with private environments',
    () async {
      final original = {'GH_TOKEN': 'ambient', 'KEEP': 'yes'};
      final seen = <String>[];
      final transport = WorkflowTransport(
        directory: 'target-store',
        environment: original,
        runner: (dir, command, env, limits) async {
          expect(dir, 'target-store');
          if (command[0] == 'gh') {
            if (command.contains('--help')) return result('--user');
            if (command.contains('token')) {
              expect(env.containsKey('GH_TOKEN'), false);
              return result('token-${command.last}');
            }
            return result(env['GH_TOKEN']!.substring(6));
          }
          if (command[0] == 'git') return result('');
          seen.add(env['GH_TOKEN']!);
          return result('ok');
        },
      );
      await transport.fenced('one', ['capture']);
      await transport.fenced('two', ['capture']);
      expect(seen, ['token-one', 'token-two']);
      expect(original, {'GH_TOKEN': 'ambient', 'KEEP': 'yes'});
    },
  );

  test(
    'nested lookup limit is a fence refusal, normal exit 3 is command result',
    () async {
      var limited = true;
      final transport = WorkflowTransport(
        directory: 'repo',
        environment: {},
        runner: (dir, command, env, limits) async {
          if (command.contains('--help')) return result('--user');
          if (command.contains('token')) {
            return limited ? result('', 124) : result('token');
          }
          if (command[0] == 'gh') return result('bot');
          return result('', command[0] == 'capture' ? 3 : 0);
        },
      );
      await expectLater(
        transport.fenced('bot', ['capture']),
        throwsA(
          isA<PairStop>().having((s) => s.error, 'error', 'fence_refused'),
        ),
      );
      limited = false;
      expect((await transport.fenced('bot', ['capture'])).exitCode, 3);
    },
  );

  test('outer expiry takes priority over inner refusal', () async {
    final transport = WorkflowTransport(
      directory: 'repo',
      environment: {},
      runner: (dir, command, env, limits) async {
        await Future<void>.delayed(const Duration(milliseconds: 30));
        return result('', 124);
      },
    );
    await expectLater(
      transport.fenced(
        'bot',
        ['capture'],
        outer: const RunLimits(
          deadline: Duration(milliseconds: 10),
          maxBytes: 100,
        ),
      ),
      throwsA(
        isA<PairStop>().having((s) => s.error, 'error', 'deadline_exceeded'),
      ),
    );
  });

  test(
    'checks consume one shared budget; unbounded command stays unbounded',
    () async {
      final budgets = <Duration?>[];
      final transport = WorkflowTransport(
        directory: 'repo',
        environment: {},
        runner: (dir, command, env, limits) async {
          budgets.add(limits?.deadline);
          await Future<void>.delayed(const Duration(milliseconds: 5));
          if (command.contains('--help')) return result('--user');
          if (command.contains('token')) return result('token');
          if (command[0] == 'gh') return result('bot');
          return result('');
        },
      );
      await transport.fenced('bot', [
        'capture',
      ], outer: const RunLimits(deadline: Duration(seconds: 2), maxBytes: 100));
      expect(budgets.length, greaterThan(3));
      expect(
        budgets.last!.inMicroseconds,
        lessThan(budgets.first!.inMicroseconds),
      );
      budgets.clear();
      await transport.fenced('bot', ['capture']);
      expect(budgets.last, isNull);
    },
  );

  test(
    'real bounded command stops its descendant within the outer budget',
    () async {
      final bash = findBash();
      expect(bash, isNotNull);
      final temp = Directory.systemTemp.createTempSync(
        'sw-workflow-transport-',
      );
      try {
        final helper = await buildHelper(temp);
        final late = File('${temp.path}/late');
        final native = WorkflowTransport.native(
          directory: temp.path,
          bash: bash!,
          helperCommand: helper,
        );
        final transport = WorkflowTransport(
          directory: temp.path,
          environment: {},
          runner: (dir, command, env, limits) async {
            if (command.contains('--help')) return result('--user');
            if (command.contains('token')) return result('token');
            if (command[0] == 'gh') return result('bot');
            if (command[0] == 'git') return result('');
            return native.runner(dir, command, native.environment, limits);
          },
        );
        await expectLater(
          transport.fenced(
            'bot',
            [
              bash,
              '-c',
              r'(sleep 2; printf late > "$1") & wait',
              'x',
              late.path.replaceAll(r'\', '/'),
            ],
            outer: const RunLimits(
              deadline: Duration(milliseconds: 700),
              maxBytes: 4096,
            ),
          ),
          throwsA(
            isA<PairStop>().having(
              (s) => s.error,
              'error',
              'deadline_exceeded',
            ),
          ),
        );
        await Future<void>.delayed(const Duration(seconds: 3));
        expect(
          late.existsSync(),
          false,
          reason: 'descendant survived cancellation',
        );
      } finally {
        temp.deleteSync(recursive: true);
      }
    },
  );
}
