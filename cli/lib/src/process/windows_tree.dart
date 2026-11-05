import 'dart:async';
import 'dart:io';

import '../native/kernel32.dart' as k32;
import 'frame.dart';
import 'tree_stop.dart';

/// The Windows calls [WindowsTree] makes, behind a seam so a test can drive
/// its identity check with a fake. [NativeWindowsApi] is the real one.
abstract interface class WindowsApi {
  /// A new job object without limits, or 0.
  int createJob();

  bool assign(int job, int process);

  bool terminateJob(int job);

  /// A handle on [pid] with the access `sw` needs on the helper, or 0.
  int open(int pid);

  /// The creation time (FILETIME) behind [process], or null.
  int? creationTime(int process);

  bool isRunning(int process);

  bool terminate(int process);

  bool close(int handle);

  int lastError();

  /// `taskkill /T /F` on [pid]; only called while a handle pins the PID.
  /// Returns within [wait]: a `taskkill` still running then is stopped.
  Future<void> killTree(int pid, Duration wait);
}

class NativeWindowsApi implements WindowsApi {
  const NativeWindowsApi();

  @override
  int createJob() => k32.createJobObject();

  @override
  bool assign(int job, int process) =>
      k32.assignProcessToJobObject(job, process);

  @override
  bool terminateJob(int job) => k32.terminateJobObject(job, 1);

  @override
  int open(int pid) => k32.openProcess(k32.helperAccess, pid);

  @override
  int? creationTime(int process) => k32.processCreationTime(process);

  @override
  bool isRunning(int process) => k32.isProcessRunning(process);

  @override
  bool terminate(int process) => k32.terminateProcess(process, 1);

  @override
  bool close(int handle) => k32.closeHandle(handle);

  @override
  int lastError() => k32.lastError();

  @override
  Future<void> killTree(int pid, Duration wait) async {
    final Process taskkill;
    try {
      taskkill = await Process.start('taskkill', ['/T', '/F', '/PID', '$pid']);
    } on ProcessException {
      return; // the handle terminate still ends the helper
    }
    // Drain its output so a full pipe cannot stall it.
    unawaited(taskkill.stdout.drain<void>());
    unawaited(taskkill.stderr.drain<void>());
    try {
      await taskkill.exitCode.timeout(wait);
    } on TimeoutException {
      taskkill.kill(ProcessSignal.sigkill); // our own child, by Dart's handle
    }
  }
}

/// The Windows tree of one run: an unnamed job object the parent assigns the
/// helper to, stopped with `TerminateJobObject`.
///
/// On Windows the command must already be inside the job object when it
/// starts. The parent acts on the helper only through the process handle it
/// matched against the helper's identity frame, never a bare PID: it opens the
/// PID when the hello frame arrives and keeps the handle only if its creation
/// time is the frame's and the process still runs. That handle stays open
/// until the run ends, so the PID cannot be reused while the parent can still
/// act on it. After the ready frame and before the go, the parent assigns the
/// handle to the job; the helper starts nothing before the go, so nothing
/// escapes. Kill-on-close is never set (closing the job handle kills
/// nothing), and the PID fallback announces itself: without a job (the test
/// hook `SPECWRIGHT_TEST_NO_JOB`, a job that could not be created or an
/// assignment that failed) the run announces `bounded: no job object:
/// reason` and a limit stops the tree with `taskkill /T /F` by the pinned
/// PID. The handle is closed exactly once, before the job handle.
class WindowsTree implements ProcessTree {
  WindowsTree({
    WindowsApi api = const NativeWindowsApi(),
    String? noJobReason,
    this.killTreeWait = const Duration(seconds: 5),
  }) : _api = api {
    if (noJobReason != null) {
      _failure = noJobReason;
    } else {
      final job = api.createJob();
      if (job == 0) {
        _failure = 'CreateJobObject failed (error ${api.lastError()})';
      } else {
        _job = job;
      }
    }
  }

  factory WindowsTree.native(Map<String, String> env) => WindowsTree(
    noJobReason: env['SPECWRIGHT_TEST_NO_JOB'] == '1'
        ? 'SPECWRIGHT_TEST_NO_JOB is set'
        : null,
  );

  final WindowsApi _api;

  /// How long the PID fallback's `taskkill` may run before it is abandoned.
  final Duration killTreeWait;
  int _job = 0;
  String? _failure;
  int _pid = 0;
  int _handle = 0;
  bool _assigned = false;

  @override
  void started(Process helper) => _pid = helper.pid;

  @override
  bool hello(HelloFrame frame) {
    final handle = _api.open(_pid);
    if (handle == 0) return false;
    final claimed = frame.creationTime;
    if (claimed == null ||
        _api.creationTime(handle) != claimed ||
        !_api.isRunning(handle)) {
      _api.close(handle);
      return false;
    }
    _handle = handle;
    return true;
  }

  @override
  String? ready(ReadyFrame frame) {
    final reason = _failure ?? frame.jobReason;
    if (reason != null) return reason;
    if (_handle == 0 || !_api.isRunning(_handle)) return null; // it is gone
    if (_api.assign(_job, _handle)) {
      _assigned = true;
      return null;
    }
    return 'AssignProcessToJobObject failed (error ${_api.lastError()})';
  }

  @override
  bool get helperGone => _handle != 0 && !_api.isRunning(_handle);

  @override
  Future<void> stop() async {
    if (_assigned) _api.terminateJob(_job);
    if (_handle == 0) return; // never act on a PID that was not identified
    if (!_assigned) {
      try {
        await _api.killTree(_pid, killTreeWait).timeout(killTreeWait);
      } on TimeoutException {
        // abandoned: the handle terminate below still ends the helper
      }
    }
    _api.terminate(_handle);
  }

  @override
  void dispose() {
    if (_handle != 0) {
      _api.close(_handle);
      _handle = 0;
    }
    if (_job != 0) {
      _api.close(_job);
      _job = 0;
    }
  }
}
