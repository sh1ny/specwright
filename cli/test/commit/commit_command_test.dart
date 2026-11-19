import 'dart:convert';
import 'dart:io';

import 'package:specwright_cli/src/cli.dart';
import 'package:specwright_cli/src/commands/commit.dart';
import 'package:specwright_cli/src/process/command_line.dart';
import 'package:test/test.dart';

class _Seen {
  CommitContext? ctx;
  List<String>? args;
}

void main() {
  late List<int> out;
  late List<int> err;
  late _Seen seen;
  late Map<String, CommitHandler> handlers;
  late Directory project;

  setUp(() {
    // a project of a test build's version (no SW_VERSION defined)
    project = Directory.systemTemp.createTempSync('sw-commit-cmd-');
    Directory('${project.path}/.git').createSync();
    Directory('${project.path}/openspec/.specwright')
        .createSync(recursive: true);
    File('${project.path}/openspec/.specwright/VERSION')
        .writeAsStringSync('0.0.0-dev\n');
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

  tearDown(() => project.deleteSync(recursive: true));

  Future<int> run(List<String> argv) => runCommitCommand(
    argv,
    writeOut: out.addAll,
    writeErr: err.addAll,
    handlers: handlers,
  );

  group('sw commit', () {
    for (final sub in ['task-cover', 'fit-subject']) {
      test('$sub dispatches from the arguments', () async {
        final code = await run([sub, '--repo', '/r', '']);
        expect(code, 7);
        expect(utf8.decode(out), 'ran $sub\n');
        expect(seen.args, [sub, '--repo', '/r', '']);
      });
    }

    test(
      'a launch the launcher refuses is a not_utf8 document, exit 1',
      () async {
        handlers['fit-subject'] = (args, ctx) async =>
            throw const Unrepresentable('git', 'command line');
        final code = await run(['fit-subject', 'm.txt']);
        expect(code, 1);
        final doc = jsonDecode(utf8.decode(out)) as Map<String, Object?>;
        expect(doc['error'], 'not_utf8');
        expect(doc['message'], contains('cannot start git'));
      },
    );

    test('an unknown subcommand is a usage stop with exit 2', () async {
      final code = await run(['frobnicate']);
      expect(code, 2);
      final doc = jsonDecode(utf8.decode(out)) as Map<String, Object?>;
      expect(doc['ok'], false);
      expect(doc['error'], 'usage');
      expect(doc['message'], contains('sw commit'));
      expect(seen.args, isNull);
    });

    test('no subcommand is a usage stop with exit 2', () async {
      final code = await run([]);
      expect(code, 2);
      final doc = jsonDecode(utf8.decode(out)) as Map<String, Object?>;
      expect(doc['error'], 'usage');
      expect(doc['message'], contains('sw commit'));
      expect(seen.args, isNull);
    });
  });

  group('runCli', () {
    test('routes commit before the argument parser', () async {
      final o = StringBuffer();
      final e = StringBuffer();
      final bytes = <int>[];
      final code = await runCli(
        ['--project', project.path, 'commit', 'task-cover'],
        out: o,
        err: e,
        outBytes: bytes.addAll,
        errBytes: (_) {},
        commitHandlers: handlers,
      );
      expect(code, 7);
      expect(utf8.decode(bytes), 'ran task-cover\n');
    });

    test('the top-level usage names commit', () async {
      final e = StringBuffer();
      final code = await runCli([], out: StringBuffer(), err: e);
      expect(code, 2);
      expect(e.toString(), contains('commit task-cover|fit-subject'));
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
