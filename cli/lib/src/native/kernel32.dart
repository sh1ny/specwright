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
