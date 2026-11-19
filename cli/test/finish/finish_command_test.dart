import 'dart:convert';
import 'dart:io';

import 'package:specwright_cli/src/cli.dart';
import 'package:specwright_cli/src/commands/finish.dart';
import 'package:specwright_cli/src/finish/undo_plan.dart';
import 'package:specwright_cli/src/process/command_line.dart';
import 'package:specwright_cli/src/vcs/stop.dart';
import 'package:test/test.dart';

const _usageText =
    'usage: finish.sh [--dir <planning toplevel>] undo-archive-plan '
    '--change <name> --archived-name <archived> --prefix <P> --main <main> '
    '[--branch <branch>] [--type <type>] [--code <code toplevel>]';

void main() {
  late List<int> out;
  late UndoRequest? seenRequest;
  late UndoPlanner planner;

  setUp(() {
    out = [];
    seenRequest = null;
    planner = (request, ctx) async {
      seenRequest = request;
      return {'ok': true, 'planned': request.change};
    };
  });

  Future<int> run(List<String> argv) =>
      runFinishCommand(argv, writeOut: out.addAll, planner: planner);

  Map<String, Object?> doc() =>
      jsonDecode(utf8.decode(out)) as Map<String, Object?>;

  Future<void> expectUsage(List<String> finishArgv, String message) async {
    final code = await run(finishArgv);
    expect(code, 2, reason: '$finishArgv');
    expect(doc(), {'ok': false, 'error': 'usage', 'message': message});
    expect(seenRequest, isNull);
  }

  /// A usage stop from the option rule: the stop type and exit status, not the parser's wording.
  Future<void> expectUsageStop(List<String> finishArgv) async {
    out.clear();
    final code = await run(finishArgv);
    expect(code, 2, reason: '$finishArgv');
    expect(doc()['error'], 'usage', reason: '$finishArgv');
    expect(seenRequest, isNull);
  }

  group('sw finish', () {
    test(
      'a leading --dir is parsed and undo-archive-plan dispatches',
      () async {
        final code = await run([
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
        ]);
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
      },
    );

    test('without --dir the directory is the current one', () async {
      await run(['undo-archive-plan', '--change', 'x']);
      expect(seenRequest!.dir, Directory.current.path);
      expect(seenRequest!.branch, isNull);
    });

    test('an empty --dir is the current directory too', () async {
      await run(['--dir', '', 'undo-archive-plan']);
      expect(seenRequest!.dir, Directory.current.path);
    });

    test('an MSYS-form --dir is used as given, not converted', () async {
      await run(['--dir', '/c/sw-none/p', 'undo-archive-plan']);
      expect(seenRequest!.dir, '/c/sw-none/p');
    });

    test('the last value of a repeated option wins', () async {
      await run(['undo-archive-plan', '--change', 'a', '--change', 'b']);
      expect(seenRequest!.change, 'b');
    });

    test('an option value may start with dashes or be empty', () async {
      await run(['undo-archive-plan', '--change', '--x', '--type', '']);
      expect(seenRequest!.change, '--x');
      expect(seenRequest!.type, '');
    });

    test('a planner stop prints its document and exit code', () async {
      planner = (request, ctx) async => throw VcsStop(
        'no_archive',
        'nothing',
        extra: {'commits': <String>[]},
      );
      final code = await run(['undo-archive-plan']);
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
      final code = await run(['undo-archive-plan']);
      expect(code, 1);
      expect(doc()['ok'], false);
      expect(doc()['error'], 'internal_error');
      expect(doc()['message'], contains('boom'));
    });

    test('U+2028 in a document parses back', () async {
      planner = (request, ctx) async => {
        'v': 'a${String.fromCharCode(0x2028)}b',
      };
      await run(['undo-archive-plan']);
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
      final code = await run([]);
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
      await expectUsageStop(['undo-archive-plan', '--bogus', 'v']);
      await expectUsageStop(['undo-archive-plan', '--chan', 'v']);
    });

    test('--dir after the subcommand is an unknown option', () async {
      await expectUsageStop(['undo-archive-plan', '--dir', 'd']);
    });

    test('an option with no value is a usage stop', () async {
      await expectUsageStop(['undo-archive-plan', '--change']);
    });

    test('a bare word after the subcommand is a usage stop', () async {
      await expectUsageStop(['undo-archive-plan', '--change', 'x', 'stray']);
      await expectUsageStop(['undo-archive-plan', '--change', 'x', '--', 'a']);
    });

    test(
      'a launch the launcher refuses is a not_utf8 document, exit 1',
      () async {
        planner = (request, ctx) async =>
            throw const Unrepresentable('git', 'command line');
        final code = await run(['undo-archive-plan', '--change', 'x']);
        expect(code, 1);
        expect(doc()['error'], 'not_utf8');
        expect(doc()['message'], contains('cannot start git'));
      },
    );
  });

  group('sw finish undo-step', () {
    test('runs a primitive, not the planner', () async {
      final code = await run([
        'undo-step',
        'check',
        'absent',
        '${Directory.systemTemp.path}/claude-ncrs-no-such-path',
      ]);
      expect(code, 0);
      expect(out, isEmpty);
      expect(seenRequest, isNull);
    });

    test('an unknown kind is a usage stop', () async {
      final code = await run(['undo-step', 'frobnicate']);
      expect(code, 2);
      expect(doc()['error'], 'usage');
    });
  });

  group('runCli', () {
    late Directory project;
    setUp(() {
      // a project of a test build's version (no SW_VERSION defined)
      project = Directory.systemTemp.createTempSync('sw-finish-cmd-');
      Directory('${project.path}/.git').createSync();
      Directory('${project.path}/openspec/.specwright')
          .createSync(recursive: true);
      File('${project.path}/openspec/.specwright/VERSION')
          .writeAsStringSync('0.0.0-dev\n');
    });
    tearDown(() => project.deleteSync(recursive: true));

    test('routes finish before the argument parser', () async {
      final bytes = <int>[];
      final code = await runCli(
        [
          '--project',
          project.path,
          'finish',
          'undo-archive-plan',
          '--change',
          'q',
        ],
        out: StringBuffer(),
        err: StringBuffer(),
        outBytes: bytes.addAll,
        errBytes: (_) {},
        undoPlanner: planner,
      );
      expect(code, 0);
      expect(jsonDecode(utf8.decode(bytes)), {'ok': true, 'planned': 'q'});
    });

    test('the top-level usage names finish', () async {
      final e = StringBuffer();
      final code = await runCli([], out: StringBuffer(), err: e);
      expect(code, 2);
      expect(e.toString(), contains('finish [--dir <repo>]'));
      expect(e.toString(), isNot(contains('--args-')));
    });

    test('sw version --json reports interface 2', () async {
      final o = StringBuffer();
      final code = await runCli(
        ['version', '--json'],
        out: o,
        err: StringBuffer(),
      );
      expect(code, 0);
      expect(o.toString(), '{"version":"0.0.0-dev","interface":2}\n');
    });
  });
}
