import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:specwright_cli/src/fence/as_command.dart';
import 'package:specwright_cli/src/fence/fence.dart';
import 'package:specwright_cli/src/pr/gh.dart';
import 'package:specwright_cli/src/vcs/tool_runner.dart';
import 'package:test/test.dart';

void main() {
  late Directory dir;
  late List<int> out;
  late List<int> err;
  late List<List<String>> launched;
  late List<List<String>> ghCalls;

  setUp(() {
    dir = Directory.systemTemp.createTempSync('sw-as-cmd-');
    out = [];
    err = [];
    launched = [];
    ghCalls = [];
  });
  tearDown(() => dir.deleteSync(recursive: true));

  Future<GhResult> fakeGh(List<String> a, Map<String, String> e) async {
    ghCalls.add(a);
    final text = a.contains('--help')
        ? '--user'
        : a.first == 'auth'
        ? 'tok\n'
        : 'me\n';
    return GhResult(
      exitCode: 0,
      stdout: utf8.encode(text),
      stderr: Uint8List(0),
    );
  }

  Future<ToolResult> fakeGit(List<String> c, Map<String, String> e) async =>
      ToolResult(0, utf8.encode('false\n'), Uint8List(0));

  Future<int> run(List<String> args) => runAsCommand(
    args,
    writeOut: out.addAll,
    writeErr: err.addAll,
    environment: {'KEEP': '1'},
    gh: fakeGh,
    git: fakeGit,
    launch: (c, e) async {
      launched.add(c);
      return 5;
    },
  );

  String said() => utf8.decode(err);

  test('the login and the command run the fence, as given', () async {
    expect(await run(['me', 'git', 'fetch', '']), 5);
    expect(launched, [
      ['git', 'fetch', ''],
    ]);
  });

  test('--resolve prints the login', () async {
    expect(await run(['--resolve']), 0);
    expect(utf8.decode(out), 'me\n');
  });

  test('no argument is as.sh with no argument: usage, exit 1', () async {
    expect(await run([]), 1);
    expect(said(), contains('usage: as.sh <login> <command>'));
    expect(ghCalls, isEmpty);
  });

  test('a refusal of the fence is exit 3 with its as.sh message', () async {
    expect(await run(['me', 'git', 'clone', 'https://u:p@github.com/o/r']), 3);
    expect(said(), contains('credentials in a github.com URL'));
    expect(said(), isNot(contains(':p@')));
    expect(launched, isEmpty);
  });

  test('the old --args-file form is no handoff: it is a login', () async {
    // sw refuses the flag at the entry (cli.dart); the fence itself reads no file
    final file = File('${dir.path}/handoff')..writeAsStringSync('x');
    await run(['--args-file', file.path]);
    expect(
      file.existsSync(),
      isTrue,
      reason: 'the file is not read or deleted',
    );
  });

  test('FenceStop carries its exit status', () {
    expect(FenceStop('as.sh: x').code, 3);
  });
}
