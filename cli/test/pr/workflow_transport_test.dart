import 'dart:convert';
import 'dart:typed_data';

import 'package:specwright_cli/src/pr/context.dart';

import 'package:specwright_cli/src/vcs/codec.dart';

import 'dart:io';

import 'package:test/test.dart';
import 'package:specwright_cli/src/pr/gh.dart';
import 'package:specwright_cli/src/pr/pair.dart';
import 'package:specwright_cli/src/pr/workflow_transport.dart';
import 'package:specwright_cli/src/pr/workflow.dart';
import 'package:specwright_cli/src/process/limits.dart';
import 'package:specwright_cli/src/process/limit_line.dart';

import '../helper_support.dart';
import '../vcs/bash_support.dart';

GhResult result(String text, [int code = 0]) => GhResult(
  exitCode: code,
  stdout: Uint8List.fromList(text.codeUnits),
  stderr: Uint8List(0),
);

/// A [Workflow] whose every `gh` call answers [stdout] / [stderr] / [code], recording the arguments.
Workflow slurpWorkflow(
  String stdout,
  List<List<String>> calls, {
  int code = 0,
  String stderr = '',
}) => Workflow(
  PrContext(
    scriptsDir: '.',
    bash: 'bash',
    writeOut: (_) {},
    writeErr: (_) {},
    environment: {},
    gh: (args, {environment, paged = false}) async {
      calls.add(args);
      return GhResult(
        exitCode: code,
        stdout: Uint8List.fromList(stdout.codeUnits),
        stderr: Uint8List.fromList(stderr.codeUnits),
      );
    },
  ),
);

void main() {
  test('slurped pages flatten in order', () async {
    final calls = <List<String>>[];
    final pages = [
      for (var p = 0; p < 3; p++)
        [
          for (var i = 0; i < (p == 2 ? 7 : 100); i++) {'n': p * 100 + i},
        ],
    ];
    final items = await slurpWorkflow(
      jsonEncode(pages),
      calls,
    ).list('repos/o/n/pulls');
    expect(items.length, 207);
    expect(items.map((e) => (e as Map)['n']), [
      for (var i = 0; i < 100; i++) i,
      for (var i = 0; i < 100; i++) 100 + i,
      for (var i = 0; i < 7; i++) 200 + i,
    ]);
    expect(calls.single, ['api', '--paginate', '--slurp', 'repos/o/n/pulls']);
  });

  test('an empty slurp is an empty list', () async {
    expect(await slurpWorkflow('[]', []).list('e'), isEmpty);
    expect(await slurpWorkflow('[[]]', []).list('e'), isEmpty);
  });

  test('a non-array page is an unknown read', () async {
    for (final body in ['[[1],{"a":1}]', '{"a":1}', '[1]', 'not json']) {
      await expectLater(
        slurpWorkflow(body, []).list('e'),
        throwsA(
          isA<PairStop>()
              .having((s) => s.error, 'error', 'lookup_failed')
              .having((s) => s.code, 'code', 3),
        ),
        reason: body,
      );
    }
  });

  test('a slurp failure names gh 2.48', () async {
    await expectLater(
      slurpWorkflow('', [], code: 1, stderr: 'unknown flag: --slurp').list('e'),
      throwsA(
        isA<PairStop>()
            .having((s) => s.error, 'error', 'lookup_failed')
            .having((s) => s.message, 'message', contains('gh 2.48')),
      ),
    );
  });

  test(
    'workflow JSON reader preserves raw POSIX snapshot paths',
    () async {
      final directory = Directory.systemTemp.createTempSync('workflow-json-');
      addTearDown(() => directory.deleteSync(recursive: true));
      final rawDirectory = Uint8List.fromList([
        ...encodeEscaped(directory.path),
        0x2f,
        0x80,
      ]);
      Directory.fromRawPath(rawDirectory).createSync();
      final rawFile = Uint8List.fromList([...rawDirectory, 0x2f, 0xff]);
      File.fromRawPath(rawFile).writeAsStringSync('{"value":"é"}');
      expect(await readWorkflowJson(decodeEscaped(rawFile)), {'value': 'é'});
    },
    skip: !Platform.isLinux
        ? 'Linux only: macOS and Windows refuse invalid UTF-8 filenames'
        : false,
  );

  test(
    'workflow JSON reader retains Unicode and unreadable-file errors',
    () async {
      final directory = Directory.systemTemp.createTempSync('workflow-json-');
      addTearDown(() => directory.deleteSync(recursive: true));
      final file = File('${directory.path}/snapshot-é.json');
      file.writeAsStringSync('{"value":"é"}');
      expect(await readWorkflowJson(file.path), {'value': 'é'});
      await expectLater(
        readWorkflowJson('${file.path}.missing'),
        throwsA(
          isA<FormatException>().having(
            (e) => e.message,
            'message',
            startsWith('${file.path}.missing: cannot read: '),
          ),
        ),
      );
    },
  );

  test('oversized workflow JSON retains its stop and raw path', () async {
    final directory = Directory.systemTemp.createTempSync('workflow-json-');
    addTearDown(() => directory.deleteSync(recursive: true));
    final file = File('${directory.path}/snapshot-\u00e9.json');
    file.openSync(mode: FileMode.write)
      ..truncateSync(defaultMaxBytes + 1)
      ..closeSync();
    await expectLater(
      readWorkflowJson(file.path),
      throwsA(
        isA<FormatException>().having(
          (e) => e.message,
          'message',
          allOf(startsWith('${file.path}: '), contains('32 MiB')),
        ),
      ),
    );
    // the file at the cap is read (and refused as JSON, not as too long)
    file.openSync(mode: FileMode.write)
      ..truncateSync(defaultMaxBytes)
      ..closeSync();
    await expectLater(
      readWorkflowJson(file.path),
      throwsA(
        isA<FormatException>().having(
          (e) => e.message,
          'message',
          isNot(contains('32 MiB')),
        ),
      ),
    );
  });

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
