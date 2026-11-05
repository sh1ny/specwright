// WindowsTree's identity check and handle ownership, driven through the
// WindowsApi seam with a fake: no process is started, so it runs everywhere.
import 'dart:async';
import 'dart:io';

import 'package:specwright_cli/src/process/frame.dart';
import 'package:specwright_cli/src/process/windows_tree.dart';
import 'package:test/test.dart';

const _pid = 4242;
const _created = 133800000000000000;
const _hello = HelloFrame('$_created');

/// Records every call. The helper process is [_pid], creation time [created],
/// and is running while [running].
class _FakeApi implements WindowsApi {
  _FakeApi({
    this.created = _created,
    this.running = true,
    this.openFails = false,
  });

  int? created;
  bool running;
  bool openFails;
  bool assignFails = false;
  bool jobFails = false;
  final calls = <String>[];
  var _next = 100;

  @override
  int createJob() {
    calls.add('createJob');
    return jobFails ? 0 : 7;
  }

  @override
  bool assign(int job, int process) {
    calls.add('assign($job,$process)');
    return !assignFails;
  }

  @override
  bool terminateJob(int job) {
    calls.add('terminateJob($job)');
    return true;
  }

  @override
  int open(int pid) {
    calls.add('open($pid)');
    return openFails ? 0 : _next++;
  }

  @override
  int? creationTime(int process) => created;

  @override
  bool isRunning(int process) => running;

  @override
  bool terminate(int process) {
    calls.add('terminate($process)');
    return true;
  }

  @override
  bool close(int handle) {
    calls.add('close($handle)');
    return true;
  }

  @override
  int lastError() => 5;

  /// When set, `taskkill` never finishes.
  bool killTreeHangs = false;

  @override
  Future<void> killTree(int pid, Duration wait) {
    calls.add('killTree($pid)');
    return killTreeHangs ? Completer<void>().future : Future.value();
  }

  /// The calls that act on a process or a job, not on handles' life cycle.
  List<String> get actions => calls
      .where(
        (c) =>
            c.startsWith('assign') ||
            c.startsWith('terminate') ||
            c.startsWith('killTree'),
      )
      .toList();
}

class _FakeProcess implements Process {
  @override
  int get pid => _pid;

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

WindowsTree _tree(_FakeApi api, {String? noJobReason}) {
  final tree = WindowsTree(api: api, noJobReason: noJobReason);
  tree.started(_FakeProcess());
  return tree;
}

void main() {
  group('a helper that matches its hello frame', () {
    test('is assigned through the handle, stopped through it, closed once', () async {
      final api = _FakeApi();
      final tree = _tree(api);
      expect(tree.hello(_hello), isTrue);
      expect(tree.helperGone, isFalse);
      expect(tree.ready(const ReadyFrame.ok()), isNull);
      expect(api.calls, ['createJob', 'open($_pid)', 'assign(7,100)']);
      await tree.stop();
      expect(api.actions, [
        'assign(7,100)',
        'terminateJob(7)',
        'terminate(100)',
      ]);
      tree.dispose();
      tree.dispose();
      // the helper's handle is closed before the job handle, each exactly once
      expect(api.calls.where((c) => c.startsWith('close')), [
        'close(100)',
        'close(7)',
      ]);
    });

    test('a helper that exits after the hello is gone and is not assigned', () {
      final api = _FakeApi();
      final tree = _tree(api);
      expect(tree.hello(_hello), isTrue);
      api.running = false;
      expect(tree.helperGone, isTrue);
      expect(tree.ready(const ReadyFrame.ok()), isNull);
      expect(api.actions, isEmpty);
    });
  });

  group('a helper that cannot be identified', () {
    Future<void> expectUntouched(
      _FakeApi api,
      WindowsTree tree, {
      required int closed,
    }) async {
      expect(tree.ready(const ReadyFrame.ok()), isNull);
      expect(tree.helperGone, isFalse);
      await tree.stop();
      tree.dispose();
      expect(api.actions, isEmpty, reason: 'nothing assigned or terminated');
      expect(
        api.calls.where((c) => c.startsWith('close')).length,
        closed + 1, // the job handle, which the tree created itself
        reason: 'what was opened is closed',
      );
    }

    test(
      'a mismatched creation time refuses it and closes the handle',
      () async {
        final api = _FakeApi(created: _created + 1);
        final tree = _tree(api);
        expect(tree.hello(_hello), isFalse);
        expect(api.calls, contains('close(100)'));
        await expectUntouched(api, tree, closed: 1);
      },
    );

    test('a failed open refuses it', () async {
      final api = _FakeApi(openFails: true);
      final tree = _tree(api);
      expect(tree.hello(_hello), isFalse);
      await expectUntouched(api, tree, closed: 0);
    });

    test('an exited process refuses it and closes the handle', () async {
      final api = _FakeApi(running: false);
      final tree = _tree(api);
      expect(tree.hello(_hello), isFalse);
      expect(api.calls, contains('close(100)'));
      api.running = true; // whatever answers later changes nothing
      await expectUntouched(api, tree, closed: 1);
    });

    test('a hello with no creation time refuses it', () async {
      final api = _FakeApi();
      final tree = _tree(api);
      expect(tree.hello(const HelloFrame.none()), isFalse);
      await expectUntouched(api, tree, closed: 1);
    });
  });

  group('without a job', () {
    test(
      'a job that cannot be created announces why and stops by PID',
      () async {
        final api = _FakeApi()..jobFails = true;
        final tree = _tree(api);
        expect(tree.hello(_hello), isTrue);
        expect(tree.ready(const ReadyFrame.ok()), contains('CreateJobObject'));
        await tree.stop();
        expect(api.actions, ['killTree($_pid)', 'terminate(100)']);
        tree.dispose();
        expect(api.calls.where((c) => c.startsWith('close')), ['close(100)']);
      },
    );

    test('the test hook skips the job without creating one', () async {
      final api = _FakeApi();
      final tree = _tree(api, noJobReason: 'SPECWRIGHT_TEST_NO_JOB is set');
      expect(api.calls, isEmpty);
      expect(tree.hello(_hello), isTrue);
      expect(
        tree.ready(const ReadyFrame.ok()),
        'SPECWRIGHT_TEST_NO_JOB is set',
      );
      await tree.stop();
      expect(api.actions, ['killTree($_pid)', 'terminate(100)']);
    });

    test('a taskkill that never finishes is bounded, and the handle still terminates', () async {
      final api = _FakeApi()..killTreeHangs = true;
      final tree = WindowsTree(
        api: api,
        noJobReason: 'SPECWRIGHT_TEST_NO_JOB is set',
        killTreeWait: const Duration(milliseconds: 200),
      );
      tree.started(_FakeProcess());
      expect(tree.hello(_hello), isTrue);
      tree.ready(const ReadyFrame.ok());
      await tree.stop().timeout(const Duration(seconds: 5));
      expect(api.actions, ['killTree($_pid)', 'terminate(100)']);
    });

    test('a failed assignment announces why and stops by PID', () async {
      final api = _FakeApi()..assignFails = true;
      final tree = _tree(api);
      expect(tree.hello(_hello), isTrue);
      expect(
        tree.ready(const ReadyFrame.ok()),
        'AssignProcessToJobObject failed (error 5)',
      );
      await tree.stop();
      expect(api.actions, [
        'assign(7,100)',
        'killTree($_pid)',
        'terminate(100)',
      ]);
    });
  });
}
