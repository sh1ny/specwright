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
    StringBuffer? err,
  }) => runCli(
    args,
    out: StringBuffer(),
    err: err ?? StringBuffer(),
    outBytes: (out ?? <int>[]).addAll,
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

  group('the old handoff flags', () {
    const calls = {
      'vcs': ['vcs', '--args-stdin', 'state'],
      'commit': ['commit', '--args-stdin'],
      'finish': ['finish', '--args-stdin'],
      'review': ['review', '--args-stdin'],
      'release': ['release', '--args-stdin'],
      'pr': ['pr', 'snapshot', '--args-stdin'],
      'as': ['as', '--args-file', 'handoff.bin'],
    };
    for (final MapEntry(key: name, value: args) in calls.entries) {
      test('sw $name stops with an unknown option, exit 2', () async {
        final err = StringBuffer();
        final out = <int>[];
        // a project in another version: the option is refused first, with no
        // other work, so no sw_mismatch document is printed either
        File('${repo.path}/openspec/.specwright/VERSION')
            .writeAsStringSync('9.9.9\n');
        final code = await run(
          ['--project', repo.path, ...args],
          err: err,
          out: out,
        );
        expect(code, 2);
        expect(out, isEmpty);
        expect(
          err.toString(),
          contains(
            'unknown option: ${args[1] == 'snapshot' ? args[2] : args[1]}',
          ),
        );
      });
    }
  });

  test('an MSYS-form path is used as given, not converted', () async {
    final out = <int>[];
    final code = await run([
      '--project',
      repo.path,
      'vcs',
      'state',
      '--repo',
      '/c/sw-no-such-dir/p',
      '--role',
      'code',
    ], out: out);
    final document = jsonDecode(utf8.decode(out)) as Map<String, Object?>;
    expect(code, 1);
    expect(document['error'], 'not_repository');
  });
}
