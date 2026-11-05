// PosixTree's spawn record (D6): the part that needs no signals, so it runs on
// every OS. The group kill itself is proven by evals/cli/test_sw_tree.py on
// Linux and macOS.
import 'dart:async';
import 'dart:io';

import 'package:specwright_cli/src/process/frame.dart';
import 'package:specwright_cli/src/process/posix_tree.dart';
import 'package:test/test.dart';

class _FakeProcess implements Process {
  @override
  int get pid => 31337;

  @override
  Future<int> get exitCode => Completer<int>().future;

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

PosixTree _tree(Map<String, String> env) =>
    PosixTree(env)..started(_FakeProcess());

void main() {
  late Directory dir;

  setUp(() => dir = Directory.systemTemp.createTempSync('sw-posix-tree-'));
  tearDown(() => dir.deleteSync(recursive: true));

  test('with the variable, an empty file named after the helper appears', () {
    final tree = _tree({'SPECWRIGHT_TEST_SPAWN_DIR': dir.path});
    expect(tree.hello(const HelloFrame.none()), isTrue);
    expect(tree.ready(const ReadyFrame.ok()), isNull);
    final names = dir.listSync().map((e) => e.uri.pathSegments.last).toList();
    expect(names, ['31337']);
    expect(File('${dir.path}${Platform.pathSeparator}31337').lengthSync(), 0);
  });

  test('without the variable nothing is written', () {
    _tree({}).ready(const ReadyFrame.ok());
    expect(dir.listSync(), isEmpty);
  });

  test('an unwritable directory is ignored', () {
    final tree = _tree({
      'SPECWRIGHT_TEST_SPAWN_DIR': '${dir.path}${Platform.pathSeparator}nope',
    });
    expect(tree.ready(const ReadyFrame.ok()), isNull);
    expect(dir.listSync(), isEmpty);
  });

  test('a helper that could not start a session is announced', () {
    expect(
      _tree({}).ready(const ReadyFrame.noJob('setsid failed')),
      'setsid failed',
    );
  });
}
