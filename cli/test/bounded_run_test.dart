@Tags(['process'])
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:specwright_cli/src/commands/run.dart';
import 'package:specwright_cli/src/process/bounded_run.dart';
import 'package:specwright_cli/src/process/frame.dart';
import 'package:specwright_cli/src/process/limit_line.dart';
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

  // native-cli-launcher D1, C6: no deadline, no byte bound, a stdout-only
  // cap, and the working directory the caller names.
  group('unbounded runs, a stdout cap and a working directory', () {
    late final Directory built;
    late final List<String> helper;
    setUpAll(() async {
      built = Directory.systemTemp.createTempSync('sw-unbounded-helper-');
      helper = await buildHelper(built);
    });
    tearDownAll(() => built.deleteSync(recursive: true));

    // A command that writes [stdoutBytes] bytes on stdout, then [stderrBytes]
    // bytes on stderr, then prints nothing else and exits 0.
    List<String> writer(int stdoutBytes, int stderrBytes) {
      final file = File('${dir.path}/writer.dart');
      file.writeAsStringSync("""
import 'dart:io';
import 'dart:typed_data';
Future<void> main(List<String> args) async {
  Future<void> write(IOSink sink, int total) async {
    final chunk = Uint8List(1 << 16)..fillRange(0, 1 << 16, 0x78);
    var left = total;
    while (left > 0) {
      final n = left < chunk.length ? left : chunk.length;
      sink.add(n == chunk.length ? chunk : Uint8List.sublistView(chunk, 0, n));
      left -= n;
    }
    await sink.flush();
  }
  await write(stderr, int.parse(args[1]));
  await write(stdout, int.parse(args[0]));
}
""");
      return [
        Platform.resolvedExecutable,
        file.path,
        '$stdoutBytes',
        '$stderrBytes',
      ];
    }

    Future<BoundedResult> run(
      List<String> command,
      RunLimits limits, {
      String? workingDirectory,
    }) => BoundedRun(
      command: command,
      limits: limits,
      treeFor: () => platformTree(Platform.environment),
      helperCommand: helper,
      workingDirectory: workingDirectory,
      note: (_) {},
    ).run();

    test(
      'no deadline and no byte bound run past 32 MiB and arm no timer',
      () async {
        final timers = <Duration>[];
        final result = await runZoned(
          () => run(writer(33 * 1024 * 1024, 0), const RunLimits()),
          zoneSpecification: ZoneSpecification(
            createTimer: (self, parent, zone, duration, callback) {
              timers.add(duration);
              return parent.createTimer(zone, duration, callback);
            },
          ),
        );
        expect(result.limit, isNull);
        expect(result.exitCode, 0);
        expect(result.stdout, hasLength(33 * 1024 * 1024));
        // Nothing like the 120 s default: only the short grace and stop waits.
        expect(
          timers.where((d) => d >= const Duration(seconds: 60)),
          isEmpty,
          reason: 'timers: $timers',
        );
      },
      timeout: const Timeout(Duration(minutes: 2)),
    );

    test('a deadline still arms its timer (the probe sees timers)', () async {
      final timers = <Duration>[];
      final result = await runZoned(
        () => run(
          writer(10, 0),
          const RunLimits(deadline: Duration(seconds: 120), maxBytes: 1 << 20),
        ),
        zoneSpecification: ZoneSpecification(
          createTimer: (self, parent, zone, duration, callback) {
            timers.add(duration);
            return parent.createTimer(zone, duration, callback);
          },
        ),
      );
      expect(result.exitCode, 0);
      expect(timers, contains(const Duration(seconds: 120)));
    });

    test('a stdout cap ignores a large stderr', () async {
      final result = await run(
        writer(10, 3 * 1024 * 1024),
        const RunLimits(stdoutCap: 1024),
      );
      expect(result.limit, isNull);
      expect(result.exitCode, 0);
      expect(result.stdout, hasLength(10));
      expect(result.stderr, hasLength(3 * 1024 * 1024));
    });

    test('a stdout cap stops on stdout overflow', () async {
      final result = await run(
        writer(256 * 1024, 0),
        const RunLimits(stdoutCap: 1024),
      );
      expect(result.limit, BoundedLimit.responseTooLarge);
      expect(result.exitCode, isNull);
    });

    test('BoundedRun runs its command in the working directory', () async {
      final where = Directory('${dir.path}/where')..createSync();
      final file = File('${dir.path}/cwd.dart')
        ..writeAsStringSync(
          "import 'dart:io';\n"
          'void main() => stdout.write(Directory.current.path);\n',
        );
      final result = await run(
        [Platform.resolvedExecutable, file.path],
        const RunLimits(),
        workingDirectory: where.path,
      );
      expect(result.exitCode, 0, reason: utf8.decode(result.stderr));
      expect(
        Directory(utf8.decode(result.stdout)).resolveSymbolicLinksSync(),
        where.resolveSymbolicLinksSync(),
      );
    });

    test('a normal exit reports no held pipes', () async {
      final result = await run(writer(10, 0), const RunLimits());
      expect(result.exitCode, 0);
      expect(result.pipesHeld, isFalse);
    });

    test(
      'a grandchild holding stdout is reported after the parent exits',
      () async {
        final file = File('${dir.path}/held_pipe.dart')
          ..writeAsStringSync('''
import 'dart:async';
import 'dart:io';
Future<void> main(List<String> args) async {
  if (args.isNotEmpty) {
    Timer.periodic(const Duration(hours: 1), (_) {});
    stdout.write('held');
    await stdout.flush();
    return;
  }
  await Process.start(
    Platform.resolvedExecutable,
    [Platform.script.toFilePath(), 'hold'],
    mode: ProcessStartMode.inheritStdio,
  );
  exit(7);
}
''');
        final result = await run([
          Platform.resolvedExecutable,
          file.path,
        ], const RunLimits(deadline: Duration(seconds: 30), maxBytes: 1 << 20));
        expect(result.limit, isNull);
        expect(result.exitCode, 7);
        expect(result.pipesHeld, isTrue);
      },
    );
  });
}
