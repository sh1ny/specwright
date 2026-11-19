// Every command takes its arguments as the process's own argument list
// (native-cli "sw takes its arguments directly"): spaces and non-ASCII text
// reach the command as one whole value each.
import 'dart:convert';
import 'dart:io';

import 'package:specwright_cli/src/cli.dart';
import 'package:specwright_cli/src/commands/commit.dart';
import 'package:specwright_cli/src/commands/vcs.dart';
import 'package:test/test.dart';

void main() {
  late Directory root;
  late Directory repo;
  setUp(() {
    root = Directory.systemTemp.createTempSync('sw-direct-');
    repo = Directory('${root.path}/a dir é')..createSync();
    Directory('${repo.path}/.git').createSync();
    Directory('${repo.path}/openspec/.specwright').createSync(recursive: true);
    // the version of a test build (no SW_VERSION defined)
    File('${repo.path}/openspec/.specwright/VERSION')
        .writeAsStringSync('0.0.0-dev\n');
  });
  tearDown(() => root.deleteSync(recursive: true));

  Future<int> run(
    List<String> args, {
    Map<String, VcsHandler>? vcsHandlers,
    Map<String, CommitHandler>? commitHandlers,
    List<int>? out,
  }) => runCli(
    args,
    out: StringBuffer(),
    err: StringBuffer(),
    outBytes: (out ?? <int>[]).addAll,
    readStdin: () async => throw StateError('a direct call reads no stdin'),
    vcsHandlers: vcsHandlers,
    commitHandlers: commitHandlers,
  );

  test('sw vcs takes whole values with spaces and non-ASCII text', () async {
    VcsContext? seen;
    final out = <int>[];
    final code = await run(
      [
        'vcs',
        'commit',
        '--repo',
        repo.path,
        '--role',
        'code',
        '--branch',
        'feat/x',
        '--message-file',
        'm é.txt',
        '--',
        'a b.md',
      ],
      vcsHandlers: {
        'commit': (ctx) async {
          seen = ctx;
          return {'ok': true};
        },
      },
      out: out,
    );
    expect(code, 0, reason: utf8.decode(out));
    expect(seen!.request.repo, repo.path);
    expect(seen!.request.messageFile, 'm é.txt');
    expect(seen!.request.paths, ['a b.md']);
  });

  test('sw commit takes its subcommand and arguments directly', () async {
    List<String>? seen;
    final code = await run(
      ['--project', repo.path, 'commit', 'fit-subject', 'm é.txt'],
      commitHandlers: {
        'fit-subject': (args, ctx) async {
          seen = args;
          return 0;
        },
      },
    );
    expect(code, 0);
    expect(seen, ['m é.txt']);
  });
}
