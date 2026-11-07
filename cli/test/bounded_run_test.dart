@Tags(['process'])
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:specwright_cli/src/commands/run.dart';
import 'package:specwright_cli/src/process/bounded_run.dart';
import 'package:specwright_cli/src/process/frame.dart';
import 'package:specwright_cli/src/process/limits.dart';
import 'package:specwright_cli/src/process/platform_tree.dart';
import 'package:specwright_cli/src/process/tree_stop.dart';
import 'package:test/test.dart';

import 'helper_support.dart';

/// Records what `BoundedRun` asks of the tree, and stops nothing itself.
class _RecordingTree implements ProcessTree {
  Process? helper;
  final calls = <String>[];

  @override
  void started(Process helper) {
    this.helper = helper;
    calls.add('started');
  }

  @override
  bool hello(HelloFrame frame) {
    calls.add('hello');
    return true;
  }

  @override
  String? ready(ReadyFrame frame) {
    calls.add('ready');
    return null;
  }

  @override
  bool get helperGone => false;

  @override
  Future<void> stop() async => calls.add('stop');

  @override
  void dispose() => calls.add('dispose');
}

/// A stand-in helper: writes [stderrText] on its stderr, then waits long
/// enough to outlive the run unless something kills it.
String _fakeHelper(Directory dir, String stderrText) {
  final file = File('${dir.path}/fake_helper.dart');
  final escaped = stderrText
      .replaceAll(r'\', r'\\')
      .replaceAll('\x00', r'\x00')
      .replaceAll('\n', r'\n');
  file.writeAsStringSync('''
import 'dart:io';
Future<void> main() async {
  stderr.write('$escaped');
  await stderr.flush();
  await Future<void>.delayed(const Duration(seconds: 60));
}
''');
  return file.path;
}

void main() {
  late Directory dir;
  final started = <Process>[];

  setUp(() => dir = Directory.systemTemp.createTempSync('sw-bounded-run-'));
  tearDown(() {
    for (final p in started) {
      p.kill(ProcessSignal.sigkill); // our own fake helper, by its handle
    }
    started.clear();
    dir.deleteSync(recursive: true);
  });

  Future<(BoundedResult, _RecordingTree)> runWith(String stderrText) async {
    final tree = _RecordingTree();
    final result = await BoundedRun(
      command: const ['unused'],
      limits: const RunLimits(
        deadline: Duration(seconds: 30),
        maxBytes: 1 << 20,
      ),
      treeFor: () => tree,
      helperCommand: [
        Platform.resolvedExecutable,
        _fakeHelper(dir, stderrText),
      ],
      note: (_) {},
    ).run();
    started.add(tree.helper!);
    return (result, tree);
  }

  Future<bool> stillRunning(Process p) async {
    try {
      await p.exitCode.timeout(const Duration(seconds: 1));
      return false;
    } on TimeoutException {
      return true;
    }
  }

  // Cleanup after a bad frame goes through the tree, which acts only on an
  // identified helper (C2): BoundedRun never signals the helper by itself.
  test('a malformed first frame stops nothing but through the tree', () async {
    final (result, tree) = await runWith('garbage\n');
    expect(result.startError, isNotNull);
    expect(tree.calls, containsAllInOrder(['started', 'stop', 'dispose']));
    expect(tree.calls, isNot(contains('hello')));
    expect(
      await stillRunning(tree.helper!),
      isTrue,
      reason: 'BoundedRun killed the unidentified helper itself',
    );
  });

  test('a malformed ready frame stops the helper through the tree', () async {
    final (result, tree) = await runWith('\x00sw-hello -\n\x00sw-bogus\n');
    expect(result.startError, isNotNull);
    expect(
      tree.calls,
      containsAllInOrder(['started', 'hello', 'stop', 'dispose']),
    );
    expect(tree.calls, isNot(contains('ready')));
    expect(
      await stillRunning(tree.helper!),
      isTrue,
      reason: 'BoundedRun killed the helper outside the tree',
    );
  });

  group('environment (D6, C12)', () {
    // The real helper, compiled once for the group.
    late final Directory built;
    late final List<String> helper;
    setUpAll(() async {
      built = Directory.systemTemp.createTempSync('sw-env-helper-');
      helper = await buildHelper(built);
    });
    tearDownAll(() => built.deleteSync(recursive: true));

    // A command that prints the value of each variable named on its command
    // line, as JSON (null for an absent one).
    String probe() {
      final file = File('${dir.path}/probe.dart');
      file.writeAsStringSync('''
import 'dart:convert';
import 'dart:io';
void main(List<String> names) {
  stdout.write(jsonEncode({for (final n in names) n: Platform.environment[n]}));
}
''');
      return file.path;
    }

    // A variable the test process has and the probe does not need.
    String inherited() => const [
      'HOME',
      'USERPROFILE',
      'USERNAME',
      'USER',
      'LOGNAME',
      'TEMP',
    ].firstWhere(Platform.environment.containsKey);

    Future<Map<String, Object?>> run(
      List<String> names,
      Map<String, String>? environment,
    ) async {
      final result = await BoundedRun(
        command: [Platform.resolvedExecutable, probe(), ...names],
        limits: const RunLimits(
          deadline: Duration(seconds: 60),
          maxBytes: 1 << 20,
        ),
        treeFor: () => platformTree(Platform.environment),
        helperCommand: helper,
        environment: environment,
        note: (_) {},
      ).run();
      expect(result.exitCode, 0, reason: utf8.decode(result.stderr));
      return jsonDecode(utf8.decode(result.stdout)) as Map<String, Object?>;
    }

    test('a variable left out of the map is absent in the command', () async {
      final name = inherited();
      final map = {...Platform.environment}..remove(name);
      if (Platform.isWindows) {
        map.removeWhere((k, _) => k.toLowerCase() == name.toLowerCase());
      }
      expect((await run([name], map))[name], isNull);
    });

    test('a variable in the map arrives', () async {
      final map = {...Platform.environment, 'SW_TEST_FROM_MAP': 'a b=c'};
      expect(
        (await run(['SW_TEST_FROM_MAP'], map))['SW_TEST_FROM_MAP'],
        'a b=c',
      );
    });

    test('sw run --bounded passes no map and still inherits', () async {
      final name = inherited();
      final out = <int>[];
      final code = await runCommand(
        ['--bounded', '--', Platform.resolvedExecutable, probe(), name],
        err: StringBuffer(),
        writeOut: out.addAll,
        writeErr: (_) {},
        helperCommand: helper,
      );
      expect(code, 0);
      final seen = jsonDecode(utf8.decode(out)) as Map<String, Object?>;
      expect(seen[name], Platform.environment[name]);
    });
  });
}
