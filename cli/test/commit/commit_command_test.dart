import 'dart:convert';

import 'package:specwright_cli/src/cli.dart';
import 'package:specwright_cli/src/commands/commit.dart';
import 'package:specwright_cli/src/process/command_line.dart';
import 'package:test/test.dart';

List<int> _records(List<String> records) => [
  for (final r in records) ...[...utf8.encode(r), 0],
];

class _Seen {
  CommitContext? ctx;
  List<String>? args;
}

void main() {
  late List<int> out;
  late List<int> err;
  late _Seen seen;
  late Map<String, CommitHandler> handlers;

  setUp(() {
    out = [];
    err = [];
    seen = _Seen();
    handlers = {
      for (final sub in ['task-cover', 'fit-subject'])
        sub: (args, ctx) async {
          seen
            ..ctx = ctx
            ..args = [sub, ...args];
          ctx.writeOut(utf8.encode('ran $sub\n'));
          return 7;
        },
    };
  });

  Future<int> run(List<String> argv, List<int> stdin) => runCommitCommand(
    argv,
    writeOut: out.addAll,
    writeErr: err.addAll,
    readStdin: () async => stdin,
    handlers: handlers,
  );

  group('sw commit --args-stdin', () {
    for (final sub in ['task-cover', 'fit-subject']) {
      test('$sub dispatches from the handoff', () async {
        final code = await run([
          '--args-stdin',
        ], _records(['/scripts', '/bin/bash', sub, '--repo', '/r', '']));
        expect(code, 7);
        expect(utf8.decode(out), 'ran $sub\n');
        expect(seen.args, [sub, '--repo', '/r', '']);
        expect(seen.ctx!.scriptsDir, '/scripts');
        expect(seen.ctx!.bash, '/bin/bash');
      });
    }

    test(
      'a launch the launcher refuses is a not_utf8 document, exit 1',
      () async {
        handlers['fit-subject'] = (args, ctx) async =>
            throw const Unrepresentable('git', 'command line');
        final code = await run([
          '--args-stdin',
        ], _records(['/scripts', '/bin/bash', 'fit-subject', 'm.txt']));
        expect(code, 1);
        final doc = jsonDecode(utf8.decode(out)) as Map<String, Object?>;
        expect(doc['error'], 'not_utf8');
        expect(doc['message'], contains('cannot start git'));
      },
    );

    test('an unknown subcommand is a usage stop with exit 2', () async {
      final code = await run([
        '--args-stdin',
      ], _records(['/s', '/b', 'frobnicate']));
      expect(code, 2);
      final doc = jsonDecode(utf8.decode(out)) as Map<String, Object?>;
      expect(doc['ok'], false);
      expect(doc['error'], 'usage');
      expect(doc['message'], contains('sw commit'));
      expect(seen.args, isNull);
    });

    for (final argv in [
      <String>[],
      ['task-cover'],
      ['--args-stdin', 'extra'],
      ['--other'],
    ]) {
      test('argv $argv is a usage stop with exit 2', () async {
        final code = await run(argv, _records(['/s', '/b', 'task-cover']));
        expect(code, 2);
        final doc = jsonDecode(utf8.decode(out)) as Map<String, Object?>;
        expect(doc['error'], 'usage');
        expect(doc['message'], contains('sw commit'));
        expect(seen.args, isNull);
      });
    }

    test(
      r'a task-cover argument that is not UTF-8 is a not_utf8 document, exit 1',
      () async {
        final code = await run(
          ['--args-stdin'],
          [
            ..._records(['/s', '/b', 'task-cover', '--repo']),
            0x61,
            0xff,
            0,
          ],
        );
        expect(code, 1);
        final doc = jsonDecode(utf8.decode(out)) as Map<String, Object?>;
        expect(doc['ok'], false);
        expect(doc['error'], 'not_utf8');
        expect(doc['message'], contains(r'a\xFF'));
        expect(doc['message'], contains('rename'));
        expect(seen.args, isNull, reason: 'no handler ran');
      },
    );

    test(
      r'a fit-subject path that is not UTF-8 is a stderr line, exit 2',
      () async {
        final code = await run(
          ['--args-stdin'],
          [
            ..._records(['/s', '/b', 'fit-subject']),
            0x6d,
            0xff,
            0x2e,
            0,
          ],
        );
        expect(code, 2);
        expect(utf8.decode(err), 'fit-subject.sh: not valid UTF-8: m\\xFF.\n');
        expect(out, isEmpty);
        expect(seen.args, isNull, reason: 'no handler ran');
      },
    );

    test('a fit-subject scripts directory that is not UTF-8 asks for a UTF-8 install path', () async {
      final code = await run(
        ['--args-stdin'],
        [
          0x73,
          0xff,
          0,
          ..._records(['/b', 'fit-subject', 'm.txt']),
        ],
      );
      expect(code, 1);
      final doc = jsonDecode(utf8.decode(out)) as Map<String, Object?>;
      expect(doc['error'], 'not_utf8');
      expect(doc['message'], contains('install the skills under a UTF-8 path'));
      expect(err, isEmpty);
      expect(seen.args, isNull, reason: 'no handler ran');
    });

    test('a short handoff is a usage stop naming sw commit', () async {
      final code = await run(['--args-stdin'], _records(['/s', '/b']));
      expect(code, 2);
      final doc = jsonDecode(utf8.decode(out)) as Map<String, Object?>;
      expect(doc['error'], 'usage');
      expect(doc['message'], contains('sw commit'));
    });
  });

  group('runCli', () {
    test('routes commit before the argument parser', () async {
      final o = StringBuffer();
      final e = StringBuffer();
      final bytes = <int>[];
      final code = await runCli(
        ['commit', '--args-stdin'],
        out: o,
        err: e,
        outBytes: bytes.addAll,
        errBytes: (_) {},
        readStdin: () async => _records(['/s', '/b', 'task-cover']),
        commitHandlers: handlers,
      );
      expect(code, 7);
      expect(utf8.decode(bytes), 'ran task-cover\n');
    });

    test('the top-level usage names commit', () async {
      final e = StringBuffer();
      final code = await runCli([], out: StringBuffer(), err: e);
      expect(code, 2);
      expect(e.toString(), contains('commit --args-stdin'));
    });

    test('sw version --json still reports interface 1', () async {
      final o = StringBuffer();
      final code = await runCli(
        ['version', '--json'],
        out: o,
        err: StringBuffer(),
      );
      expect(code, 0);
      expect(o.toString(), '{"version":"0.0.0-dev","interface":1}\n');
    });
  });
}
