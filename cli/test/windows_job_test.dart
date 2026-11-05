// A1: a compiled `sw __exec` helper started with Process.start and held before
// its go is opened by its parent through OpenProcess on its PID, matched by the
// creation time in its hello frame, and assigned to a job through
// AssignProcessToJobObject on that handle, also when the parent already runs
// inside another job (nested jobs, Windows 8+). The command the helper starts
// after the go is in the job. The helper is the real `sw __exec`; the test
// plays the parent's part with the same native calls.
@TestOn('windows')
@Tags(['process', 'windows'])
@Timeout(Duration(minutes: 5))
library;

import 'dart:async';
import 'dart:io';

import 'package:specwright_cli/src/native/kernel32.dart' as k32;
import 'package:specwright_cli/src/process/frame.dart';
import 'package:test/test.dart';

late Directory _build;
late String _sw;
late String _commandScript;

/// Records its PID in the file named by its first argument, then waits.
const _commandSource = r'''
import 'dart:io';

Future<void> main(List<String> args) async {
  File(args[0]).writeAsStringSync('$pid');
  await Future<void>.delayed(const Duration(minutes: 5));
}
''';

/// A started helper, held before its go, with the frames it wrote.
class _Held {
  _Held(this.process, this.hello, this.ready, this.pidFile);

  final Process process;
  final HelloFrame hello;
  final ReadyFrame ready;
  final String pidFile;
}

/// Starts `sw __exec -- dart <script> <pid file>`, and waits for both frames.
Future<_Held> _startHeld() async {
  final pidFile =
      '${_build.path}${Platform.pathSeparator}'
      'command-${DateTime.now().microsecondsSinceEpoch}.pid';
  final helper = await Process.start(_sw, [
    '__exec',
    '--',
    Platform.resolvedExecutable,
    _commandScript,
    pidFile,
  ]);
  final parser = FrameParser();
  final settled = Completer<void>();
  helper.stderr.listen(
    (chunk) {
      parser.add(chunk);
      if (parser.state == FrameState.ready ||
          parser.state == FrameState.malformed) {
        if (!settled.isCompleted) settled.complete();
      }
    },
    onDone: () {
      parser.close();
      if (!settled.isCompleted) settled.complete();
    },
  );
  helper.stdout.drain<void>();
  await settled.future.timeout(const Duration(seconds: 20));
  expect(parser.state, FrameState.ready, reason: '${parser.problem}');
  return _Held(helper, parser.hello!, parser.ready!, pidFile);
}

/// The parent's identity check: open the PID, keep the handle only if its
/// creation time is the one in the hello frame and the process still runs.
int _identify(_Held held) {
  final handle = k32.openProcess(k32.helperAccess, held.process.pid);
  expect(handle, isNot(0), reason: 'OpenProcess failed (${k32.lastError()})');
  expect(held.hello.creationTime, isNotNull, reason: 'hello: ${held.hello.id}');
  expect(k32.processCreationTime(handle), held.hello.creationTime);
  expect(k32.isProcessRunning(handle), isTrue);
  return handle;
}

Future<String> _waitForFile(String path) async {
  for (var i = 0; i < 300; i++) {
    final file = File(path);
    if (file.existsSync() && file.readAsStringSync().isNotEmpty) {
      return file.readAsStringSync();
    }
    await Future<void>.delayed(const Duration(milliseconds: 100));
  }
  fail('$path never appeared');
}

bool? _pidInJob(int pid, int job) {
  final handle = k32.openProcess(k32.processQueryLimitedInformation, pid);
  expect(handle, isNot(0), reason: 'OpenProcess($pid) failed');
  try {
    return k32.isProcessInJob(handle, job);
  } finally {
    k32.closeHandle(handle);
  }
}

/// Assigns the held helper through its checked handle, releases it with the
/// go, and checks the helper and its command are in [job] (and [outer]).
Future<void> _assignAndGo(_Held held, int job, {int? outer}) async {
  final handle = _identify(held);
  addTearDown(() => k32.closeHandle(handle));
  addTearDown(() => k32.terminateJobObject(job, 1));
  expect(
    k32.assignProcessToJobObject(job, handle),
    isTrue,
    reason: 'AssignProcessToJobObject failed (${k32.lastError()})',
  );
  expect(k32.isProcessInJob(handle, job), isTrue);
  if (outer != null) expect(k32.isProcessInJob(handle, outer), isTrue);

  held.process.stdin.add([0x67]); // the go
  await held.process.stdin.close();
  final commandPid = int.parse(await _waitForFile(held.pidFile));
  expect(commandPid, isNot(held.process.pid));
  expect(_pidInJob(commandPid, job), isTrue, reason: 'the command escaped');
  if (outer != null) expect(_pidInJob(commandPid, outer), isTrue);

  k32.terminateJobObject(job, 1);
  await held.process.exitCode.timeout(const Duration(seconds: 20));
}

void main() {
  setUpAll(() async {
    _build = Directory.systemTemp.createTempSync('sw-a1-');
    _sw = '${_build.path}${Platform.pathSeparator}sw.exe';
    _commandScript = '${_build.path}${Platform.pathSeparator}command.dart';
    File(_commandScript).writeAsStringSync(_commandSource);
    final result = await Process.run(Platform.resolvedExecutable, [
      'compile',
      'exe',
      '--define=SW_VERSION=a1',
      '-o',
      _sw,
      'bin/sw.dart',
    ]);
    expect(result.exitCode, 0, reason: '${result.stdout}${result.stderr}');
  });

  tearDownAll(() {
    try {
      _build.deleteSync(recursive: true);
    } on FileSystemException {
      // best effort
    }
  });

  test('the helper writes its creation time first, then is held', () async {
    final held = await _startHeld();
    addTearDown(() => held.process.kill());
    expect(held.ready.hasJob, isTrue, reason: '${held.ready.jobReason}');
    final handle = _identify(held);
    k32.closeHandle(handle);
    expect(File(held.pidFile).existsSync(), isFalse, reason: 'no go yet');
  });

  test(
    'a parent assigns the held helper to a job; the command follows',
    () async {
      final job = k32.createJobObject();
      expect(job, isNot(0), reason: 'CreateJobObject failed');
      addTearDown(() => k32.closeHandle(job));
      await _assignAndGo(await _startHeld(), job);
    },
  );

  test('it also works when the parent already runs inside a job', () async {
    final outer = k32.createJobObject();
    expect(outer, isNot(0));
    addTearDown(() => k32.closeHandle(outer));
    // The test process becomes a member of the outer job (no limits, nothing
    // is killed when it ends); the job it then creates is nested in it.
    expect(
      k32.assignProcessToJobObject(outer, k32.getCurrentProcess()),
      isTrue,
      reason:
          'cannot put the test process into an outer job '
          '(error ${k32.lastError()})',
    );
    final inner = k32.createJobObject();
    expect(inner, isNot(0));
    addTearDown(() => k32.closeHandle(inner));
    await _assignAndGo(await _startHeld(), inner, outer: outer);
  });
}
