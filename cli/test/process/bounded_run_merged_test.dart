// D4: the merged mode of BoundedRun (the `--log-failed` call of `sw pr
// snapshot --logs`): stdout and stderr in the order their chunks reached the
// parent, under one byte budget. The helper is a scripted FakeProcess, so the
// order of the chunks never depends on a pause.
import 'dart:async';
import 'dart:convert';

import 'package:specwright_cli/src/process/bounded_run.dart';
import 'package:specwright_cli/src/process/limit_line.dart';
import 'package:specwright_cli/src/process/limits.dart';
import 'package:test/test.dart';

import '../fake_process.dart';

/// One turn of the event loop, so the chunk just added is delivered before the
/// next one is added.
Future<void> turn() => Future<void>.delayed(Duration.zero);

Future<(BoundedResult, FakeProcess)> merged(
  Future<void> Function(FakeProcess) script, {
  int maxBytes = 1 << 20,
}) async {
  final process = FakeProcess();
  final future = BoundedRun(
    command: const ['unused'],
    limits: RunLimits(
      deadline: const Duration(seconds: 30),
      maxBytes: maxBytes,
    ),
    treeFor: NoopTree.new,
    startProcess: FakeStarter(process).call,
    helperCommand: const ['fake-helper', '__exec'],
    mergeOutput: true,
    note: (_) {},
  ).run();
  process.frames();
  await process.untilGo();
  await script(process);
  return (await future, process);
}

Future<void> finish(FakeProcess p, int code) async {
  p.exit(code);
  await p.stdoutController.close();
  await p.stderrController.close();
}

void main() {
  group('merged mode', () {
    test('merged mode keeps arrival order', () async {
      final (result, _) = await merged((p) async {
        p.stdoutController.add(utf8.encode('out 1\n'));
        await turn();
        p.stderrController.add(utf8.encode('err 1\n'));
        await turn();
        p.stdoutController.add(utf8.encode('out 2\n'));
        await turn();
        p.stderrController.add(utf8.encode('err 2\n'));
        await turn();
        await finish(p, 0);
      });
      expect(result.exitCode, 0);
      expect(utf8.decode(result.merged!), 'out 1\nerr 1\nout 2\nerr 2\n');
    });

    test('a stderr chunk inside a stdout line is kept', () async {
      final (result, _) = await merged((p) async {
        p.stdoutController.add(utf8.encode('abc'));
        await turn();
        p.stderrController.add(utf8.encode('ERR'));
        await turn();
        p.stdoutController.add(utf8.encode('def\n'));
        await turn();
        await finish(p, 0);
      });
      expect(utf8.decode(result.merged!), 'abcERRdef\n');
    });

    test('a stderr chunk may split a UTF-8 sequence', () async {
      final euro = utf8.encode('€'); // three bytes
      final (result, _) = await merged((p) async {
        p.stdoutController.add(euro.sublist(0, 2));
        await turn();
        p.stderrController.add(utf8.encode('E'));
        await turn();
        p.stdoutController.add(euro.sublist(2));
        await turn();
        await finish(p, 0);
      });
      expect(result.merged, [...euro.sublist(0, 2), 0x45, ...euro.sublist(2)]);
    });

    test(
      'the helper frames never enter the merged buffer, its own text does',
      () async {
        final (result, _) = await merged((p) async {
          p.stderrController.add(utf8.encode('bounded: cannot start x\n'));
          await turn();
          await finish(p, 127);
        });
        expect(result.exitCode, 127);
        expect(utf8.decode(result.merged!), 'bounded: cannot start x\n');
        expect(result.merged, isNot(contains(0)));
      },
    );

    test('only the merged buffer is kept, not separate copies', () async {
      final (result, _) = await merged((p) async {
        p.stdoutController.add(utf8.encode('o'));
        await turn();
        p.stderrController.add(utf8.encode('e'));
        await turn();
        await finish(p, 3);
      });
      expect(result.exitCode, 3);
      expect(result.stdout, isEmpty);
      expect(result.stderr, isEmpty);
      expect(utf8.decode(result.merged!), 'oe');
    });

    test('an unmerged run has no merged buffer', () async {
      final process = FakeProcess();
      final future = BoundedRun(
        command: const ['unused'],
        limits: const RunLimits(
          deadline: Duration(seconds: 30),
          maxBytes: 1 << 20,
        ),
        treeFor: NoopTree.new,
        startProcess: FakeStarter(process).call,
        helperCommand: const ['fake-helper', '__exec'],
        note: (_) {},
      ).run();
      process.frames();
      await process.untilGo();
      process.stdoutController.add(utf8.encode('x'));
      await finish(process, 0);
      final result = await future;
      expect(result.merged, isNull);
      expect(utf8.decode(result.stdout), 'x');
    });
  });

  group('one budget', () {
    test('two streams over maxBytes together are response_too_large', () async {
      final (result, _) = await merged(maxBytes: 100, (p) async {
        p.stdoutController.add(List.filled(60, 0x61));
        await turn();
        p.stderrController.add(List.filled(60, 0x62));
        await turn();
        await finish(p, 0);
      });
      expect(result.limit, BoundedLimit.responseTooLarge);
      expect(result.merged, isNull, reason: 'no partial output is kept');
      expect(result.stdout, isEmpty);
      expect(result.stderr, isEmpty);
    });

    test('a sum of exactly maxBytes keeps every byte', () async {
      final (result, _) = await merged(maxBytes: 100, (p) async {
        p.stdoutController.add(List.filled(60, 0x61));
        await turn();
        p.stderrController.add(List.filled(40, 0x62));
        await turn();
        await finish(p, 0);
      });
      expect(result.limit, isNull);
      expect(result.merged, [
        ...List.filled(60, 0x61),
        ...List.filled(40, 0x62),
      ]);
    });

    test('stdout alone over the budget is response_too_large', () async {
      final (result, _) = await merged(maxBytes: 100, (p) async {
        p.stdoutController.add(List.filled(101, 0x61));
        await turn();
        await finish(p, 0);
      });
      expect(result.limit, BoundedLimit.responseTooLarge);
      expect(result.merged, isNull);
    });

    test('stderr alone over the budget is response_too_large', () async {
      final (result, _) = await merged(maxBytes: 100, (p) async {
        p.stderrController.add(List.filled(101, 0x62));
        await turn();
        await finish(p, 0);
      });
      expect(result.limit, BoundedLimit.responseTooLarge);
      expect(result.merged, isNull);
    });
  });

  group('merged mode needs finite bounds', () {
    FakeStarter? starter;

    Future<BoundedResult> start({RunLimits? limits, bool sink = false}) {
      final process = FakeProcess();
      starter = FakeStarter(process);
      return BoundedRun(
        command: const ['unused'],
        limits: limits ?? const RunLimits(maxBytes: 100),
        treeFor: NoopTree.new,
        startProcess: starter!.call,
        helperCommand: const ['fake-helper', '__exec'],
        mergeOutput: true,
        stdoutSink: sink ? (_) async {} : null,
        note: (_) {},
      ).run();
    }

    test('no maxBytes is an ArgumentError', () async {
      await expectLater(
        () => start(limits: const RunLimits()),
        throwsArgumentError,
      );
      await expectLater(
        () => start(limits: const RunLimits(stdoutCap: 100)),
        throwsArgumentError,
      );
    });

    test('a stdout sink is an ArgumentError', () async {
      await expectLater(() => start(sink: true), throwsArgumentError);
    });

    test('the helper is not started on refusal', () async {
      await expectLater(
        () => start(limits: const RunLimits()),
        throwsArgumentError,
      );
      expect(starter!.starts, isEmpty);
    });
  });
}
