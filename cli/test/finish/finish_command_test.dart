import 'dart:convert';
import 'dart:io';

import 'package:specwright_cli/src/cli.dart';
import 'package:specwright_cli/src/commands/finish.dart';
import 'package:specwright_cli/src/finish/undo_plan.dart';
import 'package:specwright_cli/src/vcs/stop.dart';
import 'package:test/test.dart';

List<int> _records(List<String> records) => [
  for (final r in records) ...[...utf8.encode(r), 0],
];

const _usageText =
    'usage: finish.sh [--dir <planning toplevel>] undo-archive-plan '
    '--change <name> --archived-name <archived> --prefix <P> --main <main> '
    '[--branch <branch>] [--type <type>] [--code <code toplevel>]';

void main() {
  late List<int> out;
  late UndoRequest? seenRequest;
  late FinishContext? seenContext;
  late UndoPlanner planner;

  setUp(() {
    out = [];
    seenRequest = null;
    seenContext = null;
    planner = (request, ctx) async {
      seenRequest = request;
      seenContext = ctx;
      return {'ok': true, 'planned': request.change};
    };
  });

  Future<int> run(List<String> argv, List<int> stdin) => runFinishCommand(
    argv,
    writeOut: out.addAll,
    readStdin: () async => stdin,
    planner: planner,
  );

  Map<String, Object?> doc() =>
      jsonDecode(utf8.decode(out)) as Map<String, Object?>;

  Future<void> expectUsage(List<String> finishArgv, String message) async {
    final code = await run([
      '--args-stdin',
    ], _records(['/s', '/b', ...finishArgv]));
    expect(code, 2, reason: '$finishArgv');
    expect(doc(), {'ok': false, 'error': 'usage', 'message': message});
    expect(seenRequest, isNull);
  }

  group('sw finish --args-stdin', () {
    test(
      'a leading --dir is parsed and undo-archive-plan dispatches',
      () async {
        final code = await run(
          ['--args-stdin'],
          _records([
            '/scripts',
            '/bin/bash',
            '--dir',
            '/plan',
            'undo-archive-plan',
            '--change',
            'x',
            '--archived-name',
            '2026-01-01-x',
            '--prefix',
            'openspec',
            '--main',
            'main',
            '--branch',
            'feat/x',
            '--type',
            'feat',
            '--code',
            '/code',
          ]),
        );
        expect(code, 0);
        expect(doc(), {'ok': true, 'planned': 'x'});
        final r = seenRequest!;
        expect(r.dir, '/plan');
        expect(r.change, 'x');
        expect(r.archived, '2026-01-01-x');
        expect(r.prefix, 'openspec');
        expect(r.main, 'main');
        expect(r.branch, 'feat/x');
        expect(r.type, 'feat');
        expect(r.code, '/code');
        expect(seenContext!.scriptsDir, '/scripts');
        expect(seenContext!.bash, '/bin/bash');
      },
    );

    test('without --dir the directory is the current one', () async {
      await run([
        '--args-stdin',
      ], _records(['/s', '/b', 'undo-archive-plan', '--change', 'x']));
      expect(seenRequest!.dir, Directory.current.path);
      expect(seenRequest!.branch, isNull);
    });

    test('an empty --dir is the current directory too', () async {
      await run([
        '--args-stdin',
      ], _records(['/s', '/b', '--dir', '', 'undo-archive-plan']));
      expect(seenRequest!.dir, Directory.current.path);
    });

    test('the last value of a repeated option wins', () async {
      await run(
        ['--args-stdin'],
        _records([
          '/s',
          '/b',
          'undo-archive-plan',
          '--change',
          'a',
          '--change',
          'b',
        ]),
      );
      expect(seenRequest!.change, 'b');
    });

    test('an option value may start with dashes or be empty', () async {
      await run(
        ['--args-stdin'],
        _records([
          '/s',
          '/b',
          'undo-archive-plan',
          '--change',
          '--x',
          '--type',
          '',
        ]),
      );
      expect(seenRequest!.change, '--x');
      expect(seenRequest!.type, '');
    });

    test('a planner stop prints its document and exit code', () async {
      planner = (request, ctx) async => throw VcsStop(
        'no_archive',
        'nothing',
        extra: {'commits': <String>[]},
      );
      final code = await run([
        '--args-stdin',
      ], _records(['/s', '/b', 'undo-archive-plan']));
      expect(code, 1);
      expect(doc(), {
        'ok': false,
        'error': 'no_archive',
        'message': 'nothing',
        'commits': <String>[],
      });
    });

    test('an unexpected failure is one internal_error document', () async {
      planner = (request, ctx) async => throw StateError('boom');
      final code = await run([
        '--args-stdin',
      ], _records(['/s', '/b', 'undo-archive-plan']));
      expect(code, 1);
      expect(doc()['ok'], false);
      expect(doc()['error'], 'internal_error');
      expect(doc()['message'], contains('boom'));
    });

    test('U+2028 in a document parses back', () async {
      planner = (request, ctx) async => {
        'v': 'a${String.fromCharCode(0x2028)}b',
      };
      await run(['--args-stdin'], _records(['/s', '/b', 'undo-archive-plan']));
      expect(doc()['v'], 'a${String.fromCharCode(0x2028)}b');
    });

    test('an unknown subcommand is a usage stop with the usage text', () async {
      await expectUsage(['frobnicate'], _usageText);
    });

    test('--dir and nothing after it is a usage stop', () async {
      await expectUsage(['--dir', 'd'], _usageText);
    });

    test('--dir without a value is a usage stop', () async {
      await expectUsage(['--dir'], '--dir needs a value');
    });

    test('no arguments at all give the usage text', () async {
      final code = await run(['--args-stdin'], _records(['/s', '/b']));
      expect(code, 2);
      expect(doc(), {'ok': false, 'error': 'usage', 'message': _usageText});
    });

    test('--dir twice is an unknown subcommand', () async {
      await expectUsage([
        '--dir',
        'a',
        '--dir',
        'b',
        'undo-archive-plan',
      ], _usageText);
    });

    test('an unknown option is a usage stop', () async {
      await expectUsage([
        'undo-archive-plan',
        '--bogus',
        'v',
      ], 'unknown option --bogus');
    });

    test('--dir after the subcommand is an unknown option', () async {
      await expectUsage([
        'undo-archive-plan',
        '--dir',
        'd',
      ], 'unknown option --dir');
    });

    test('an option with no value is a usage stop', () async {
      await expectUsage([
        'undo-archive-plan',
        '--change',
      ], '--change needs a value');
    });

    test('a bare word after the subcommand is a usage stop', () async {
      await expectUsage([
        'undo-archive-plan',
        '--change',
        'x',
        'stray',
      ], 'unexpected argument stray');
    });

    for (final argv in [
      <String>[],
      ['undo-archive-plan'],
      ['--args-stdin', 'extra'],
      ['--other'],
    ]) {
      test('sw argv $argv is a usage stop with exit 2', () async {
        final code = await run(
          argv,
          _records(['/s', '/b', 'undo-archive-plan']),
        );
        expect(code, 2);
        expect(doc()['error'], 'usage');
        expect(doc()['message'], contains('sw finish'));
        expect(seenRequest, isNull);
      });
    }

    test('a handoff that does not end in a NUL is a usage stop', () async {
      final code = await run([
        '--args-stdin',
      ], utf8.encode('/s\u0000/b\u0000x'));
      expect(code, 2);
      expect(doc()['error'], 'usage');
      expect(doc()['message'], contains('sw finish'));
    });
  });

  group('runCli', () {
    test('routes finish before the argument parser', () async {
      final bytes = <int>[];
      final code = await runCli(
        ['finish', '--args-stdin'],
        out: StringBuffer(),
        err: StringBuffer(),
        outBytes: bytes.addAll,
        errBytes: (_) {},
        readStdin: () async =>
            _records(['/s', '/b', 'undo-archive-plan', '--change', 'q']),
        undoPlanner: planner,
      );
      expect(code, 0);
      expect(jsonDecode(utf8.decode(bytes)), {'ok': true, 'planned': 'q'});
    });

    test('the top-level usage names finish', () async {
      final e = StringBuffer();
      final code = await runCli([], out: StringBuffer(), err: e);
      expect(code, 2);
      expect(e.toString(), contains('finish --args-stdin'));
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
