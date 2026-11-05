// The two libc functions sw needs on Linux and macOS (D12): bound by hand over
// package:ffi. The process's own symbols are used, so no library path differs
// between the two systems. Opened on first use.
import 'dart:ffi';

final DynamicLibrary _libc = DynamicLibrary.process();

final int Function() _setsid = _libc
    .lookupFunction<Int32 Function(), int Function()>('setsid');

final int Function(int, int) _kill = _libc
    .lookupFunction<Int32 Function(Int32, Int32), int Function(int, int)>(
      'kill',
    );

const int sigkill = 9;

/// Makes the calling process the leader of a new session and process group.
/// False when it fails (for example, it already leads a group).
bool setsid() => _setsid() != -1;

/// `kill(2)`; true when the signal was sent. A negative [pid] signals the
/// process group with that ID.
bool kill(int pid, int signal) => _kill(pid, signal) == 0;
