import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:specwright_cli/src/fence/as_command.dart';
import 'package:specwright_cli/src/fence/fence.dart';
import 'package:specwright_cli/src/pr/gh.dart';
import 'package:specwright_cli/src/vcs/codec.dart';
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

  File handoff(List<int> bytes) =>
      File('${dir.path}/handoff')..writeAsBytesSync(bytes);

  List<int> records(List<String> rs) => [
    for (final r in rs) ...[...encodeEscaped(r), 0],
  ];

  Future<GhResult> fakeGh(List<String> a, Map<String, String> e) async {
    ghCalls.add(a);
    final text = a.contains('--help')
        ? '--user'
        : a.first == 'auth'
        ? 'tok\n'
        : 'me\n';
    return GhResult(
      exitCode: 0,
      stdout: encodeEscaped(text),
      stderr: Uint8List(0),
    );
  }

  Future<ToolResult> fakeGit(List<String> c, Map<String, String> e) async =>
      ToolResult(0, encodeEscaped('false\n'), Uint8List(0));

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

  test('anything but --args-file <path> is a usage stop, exit 2', () async {
    for (final args in [
      <String>[],
      ['--resolve'],
      ['--args-file'],
      ['--args-file', 'a', 'b'],
      ['sh1ny', 'git'],
    ]) {
      err.clear();
      expect(await run(args), 2, reason: '$args');
      expect(said(), 'usage: sw as --args-file <path>\n');
    }
    expect(ghCalls, isEmpty);
  });

  test('the file is read, deleted, and its records run the fence', () async {
    final file = handoff(
      records(['/scripts', '/bin/bash', 'me', 'git', 'fetch', '']),
    );
    expect(await run(['--args-file', file.path]), 5);
    expect(file.existsSync(), isFalse);
    expect(launched, [
      ['git', 'fetch', ''],
    ]);
  });

  test('--resolve in the records prints the login', () async {
    final file = handoff(records(['/s', '/bin/bash', '--resolve']));
    expect(await run(['--args-file', file.path]), 0);
    expect(utf8.decode(out), 'me\n');
  });

  test('two records only is as.sh with no argument: usage, exit 1', () async {
    final file = handoff(records(['/s', '/bin/bash']));
    expect(await run(['--args-file', file.path]), 1);
    expect(said(), contains('usage: as.sh <login> <command>'));
    expect(ghCalls, isEmpty);
  });

  test('fewer than two records is a malformed handoff, exit 3', () async {
    for (final bytes in [
      <int>[],
      records(['/s']),
    ]) {
      err.clear();
      final file = handoff(bytes);
      expect(await run(['--args-file', file.path]), 3);
      expect(said(), 'as.sh: handoff: malformed\n');
      expect(file.existsSync(), isFalse);
    }
    expect(ghCalls, isEmpty);
  });

  test('a last byte that is not NUL is a malformed handoff, exit 3', () async {
    final file = handoff([
      ...records(['/s', '/bin/bash', 'me', 'git']),
      0x78,
    ]);
    expect(await run(['--args-file', file.path]), 3);
    expect(said(), 'as.sh: handoff: malformed\n');
    expect(ghCalls, isEmpty);
    expect(launched, isEmpty);
  });

  test('a file that cannot be read is exit 3 with the reason', () async {
    expect(await run(['--args-file', '${dir.path}/missing']), 3);
    expect(said(), startsWith('as.sh: handoff: '));
    expect(ghCalls, isEmpty);
  });

  test('a path that cannot be deleted is exit 3 and runs nothing', () async {
    // a directory is readable by no one and removable by deleteSync only when
    // empty: reading it fails first, which is the same stop
    final sub = Directory('${dir.path}/sub')..createSync();
    expect(await run(['--args-file', sub.path]), 3);
    expect(said(), startsWith('as.sh: handoff: '));
    expect(launched, isEmpty);
  });

  test('a refusal of the fence is exit 3 with its as.sh message', () async {
    final file = handoff(
      records([
        '/s',
        '/bin/bash',
        'me',
        'git',
        'clone',
        'https://u:p@github.com/o/r',
      ]),
    );
    expect(await run(['--args-file', file.path]), 3);
    expect(said(), contains('credentials in a github.com URL'));
    expect(said(), isNot(contains(':p@')));
    expect(launched, isEmpty);
  });

  test('an argument that is not UTF-8 reaches the command unchanged', () async {
    final odd = [0x61, 0xff, 0x62, 0];
    final file = handoff([
      ...records(['/s', '/bin/bash', 'me', 'git']),
      ...odd,
    ]);
    expect(await run(['--args-file', file.path]), 5);
    expect(encodeEscaped(launched.single.last), [0x61, 0xff, 0x62]);
  });

  test('FenceStop carries its exit status', () {
    expect(FenceStop('as.sh: x').code, 3);
  });
}
