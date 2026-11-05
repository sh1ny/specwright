// The few kernel32 functions sw needs for job objects and process handles
// (D12): bound by hand over package:ffi, no package:win32. Handles travel as
// plain ints (the pointer's address). Windows only; the library is opened on
// first use.
import 'dart:ffi';

import 'package:ffi/ffi.dart';

final DynamicLibrary _kernel32 = DynamicLibrary.open('kernel32.dll');

typedef _Handle = Pointer<Void>;

final _Handle Function(Pointer<Void>, Pointer<Utf16>) _createJobObject =
    _kernel32.lookupFunction<
      _Handle Function(Pointer<Void>, Pointer<Utf16>),
      _Handle Function(Pointer<Void>, Pointer<Utf16>)
    >('CreateJobObjectW');

final int Function(_Handle, _Handle) _assignProcessToJobObject = _kernel32
    .lookupFunction<
      Int32 Function(_Handle, _Handle),
      int Function(_Handle, _Handle)
    >('AssignProcessToJobObject');

final int Function(_Handle, int) _terminateJobObject = _kernel32
    .lookupFunction<
      Int32 Function(_Handle, Uint32),
      int Function(_Handle, int)
    >('TerminateJobObject');

final int Function(_Handle, int) _terminateProcess = _kernel32
    .lookupFunction<
      Int32 Function(_Handle, Uint32),
      int Function(_Handle, int)
    >('TerminateProcess');

final _Handle Function() _getCurrentProcess = _kernel32
    .lookupFunction<_Handle Function(), _Handle Function()>(
      'GetCurrentProcess',
    );

final int Function(_Handle) _closeHandle = _kernel32
    .lookupFunction<Int32 Function(_Handle), int Function(_Handle)>(
      'CloseHandle',
    );

final _Handle Function(int, int, int) _openProcess = _kernel32
    .lookupFunction<
      _Handle Function(Uint32, Int32, Uint32),
      _Handle Function(int, int, int)
    >('OpenProcess');

final int Function(_Handle, _Handle, Pointer<Int32>) _isProcessInJob = _kernel32
    .lookupFunction<
      Int32 Function(_Handle, _Handle, Pointer<Int32>),
      int Function(_Handle, _Handle, Pointer<Int32>)
    >('IsProcessInJob');

final int Function(
  _Handle,
  Pointer<Uint64>,
  Pointer<Uint64>,
  Pointer<Uint64>,
  Pointer<Uint64>,
)
_getProcessTimes = _kernel32
    .lookupFunction<
      Int32 Function(
        _Handle,
        Pointer<Uint64>,
        Pointer<Uint64>,
        Pointer<Uint64>,
        Pointer<Uint64>,
      ),
      int Function(
        _Handle,
        Pointer<Uint64>,
        Pointer<Uint64>,
        Pointer<Uint64>,
        Pointer<Uint64>,
      )
    >('GetProcessTimes');

final int Function(_Handle, int) _waitForSingleObject = _kernel32
    .lookupFunction<
      Uint32 Function(_Handle, Uint32),
      int Function(_Handle, int)
    >('WaitForSingleObject');

final int Function() _getLastError = _kernel32
    .lookupFunction<Uint32 Function(), int Function()>('GetLastError');

const int processTerminate = 0x0001;
const int processSetQuota = 0x0100;
const int processQueryLimitedInformation = 0x1000;
const int synchronize = 0x00100000;

/// The access `sw` asks for on the helper (D1's identity rule).
const int helperAccess =
    processSetQuota |
    processTerminate |
    processQueryLimitedInformation |
    synchronize;

const int _waitTimeout = 0x102;

/// The calling thread's last Win32 error, read right after a failed call.
int lastError() => _getLastError();

/// A new unnamed job object, or 0 when it cannot be created. It has no limits,
/// so closing its handle does not kill anything (no kill-on-close).
int createJobObject() => _createJobObject(nullptr, nullptr).address;

bool assignProcessToJobObject(int job, int process) =>
    _assignProcessToJobObject(
      Pointer.fromAddress(job),
      Pointer.fromAddress(process),
    ) !=
    0;

bool terminateJobObject(int job, int exitCode) =>
    _terminateJobObject(Pointer.fromAddress(job), exitCode) != 0;

/// Ends the process behind [process] (a handle with `PROCESS_TERMINATE`).
/// Ending one that already exited does nothing and reports failure.
bool terminateProcess(int process, int exitCode) =>
    _terminateProcess(Pointer.fromAddress(process), exitCode) != 0;

/// The pseudo handle of the calling process (valid only in this process).
int getCurrentProcess() => _getCurrentProcess().address;

bool closeHandle(int handle) => _closeHandle(Pointer.fromAddress(handle)) != 0;

/// A handle for process [pid] with [access], or 0.
int openProcess(int access, int pid) => _openProcess(access, 0, pid).address;

/// Whether [process] is in [job] (also when it is in a job nested under it);
/// null when the call fails.
bool? isProcessInJob(int process, int job) {
  final result = calloc<Int32>();
  try {
    final ok = _isProcessInJob(
      Pointer.fromAddress(process),
      Pointer.fromAddress(job),
      result,
    );
    return ok == 0 ? null : result.value != 0;
  } finally {
    calloc.free(result);
  }
}

/// The creation time of [process] as the 64-bit FILETIME (100 ns ticks since
/// 1601), or null when the call fails. The handle needs
/// `PROCESS_QUERY_LIMITED_INFORMATION`.
int? processCreationTime(int process) {
  final times = calloc<Uint64>(4); // creation, exit, kernel, user
  try {
    final ok = _getProcessTimes(
      Pointer.fromAddress(process),
      times,
      times + 1,
      times + 2,
      times + 3,
    );
    return ok == 0 ? null : times[0];
  } finally {
    calloc.free(times);
  }
}

/// Whether [process] has not exited yet (a zero-timeout wait on its handle,
/// which needs `SYNCHRONIZE`); false when it has, or when the wait fails.
bool isProcessRunning(int process) =>
    _waitForSingleObject(Pointer.fromAddress(process), 0) == _waitTimeout;

final int Function(
  Pointer<Utf16>,
  Pointer<Utf16>,
  Pointer<Void>,
  Pointer<Void>,
  int,
  int,
  Pointer<Void>,
  Pointer<Utf16>,
  Pointer<Uint8>,
  Pointer<Uint8>,
)
_createProcess = _kernel32
    .lookupFunction<
      Int32 Function(
        Pointer<Utf16>,
        Pointer<Utf16>,
        Pointer<Void>,
        Pointer<Void>,
        Int32,
        Uint32,
        Pointer<Void>,
        Pointer<Utf16>,
        Pointer<Uint8>,
        Pointer<Uint8>,
      ),
      int Function(
        Pointer<Utf16>,
        Pointer<Utf16>,
        Pointer<Void>,
        Pointer<Void>,
        int,
        int,
        Pointer<Void>,
        Pointer<Utf16>,
        Pointer<Uint8>,
        Pointer<Uint8>,
      )
    >('CreateProcessW');

final int Function(_Handle, Pointer<Uint32>) _getExitCodeProcess = _kernel32
    .lookupFunction<
      Int32 Function(_Handle, Pointer<Uint32>),
      int Function(_Handle, Pointer<Uint32>)
    >('GetExitCodeProcess');

const int _infinite = 0xFFFFFFFF;
const int _startupInfoSize = 104; // STARTUPINFOW on 64-bit Windows

/// Runs [application] with exactly [commandLine] (no quoting is added), lets
/// it inherit this process's standard handles, waits for it, and returns its
/// exit status as a signed 32-bit value. [status] is null when the process
/// cannot be created, and [error] is then the Win32 error.
({int? status, int error}) runWithCommandLine(
  String application,
  String commandLine,
) {
  final app = application.toNativeUtf16();
  final line = commandLine.toNativeUtf16();
  final startup = calloc<Uint8>(_startupInfoSize);
  final info = calloc<Uint8>(24); // PROCESS_INFORMATION
  try {
    startup.cast<Uint32>().value = _startupInfoSize;
    final ok = _createProcess(
      app,
      line,
      nullptr,
      nullptr,
      1,
      0,
      nullptr,
      nullptr,
      startup,
      info,
    );
    if (ok == 0) return (status: null, error: _getLastError());
    final handles = info.cast<IntPtr>();
    final process = Pointer<Void>.fromAddress(handles[0]);
    _closeHandle(Pointer.fromAddress(handles[1]));
    _waitForSingleObject(process, _infinite);
    final code = calloc<Uint32>();
    try {
      final got = _getExitCodeProcess(process, code);
      final value = got == 0 ? 1 : code.value;
      return (
        status: value >= 0x80000000 ? value - 0x100000000 : value,
        error: 0,
      );
    } finally {
      calloc.free(code);
      _closeHandle(process);
    }
  } finally {
    calloc.free(app);
    calloc.free(line);
    calloc.free(startup);
    calloc.free(info);
  }
}
