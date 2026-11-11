// The three libc functions sw needs on Linux and macOS (D12, D8): bound by hand over
// package:ffi. The process's own symbols are used, so no library path differs
// between the two systems. Opened on first use.
import 'dart:ffi';
import 'dart:io' show Platform;

import 'package:ffi/ffi.dart';

final DynamicLibrary _libc = DynamicLibrary.process();

final int Function() _setsid = _libc
    .lookupFunction<Int32 Function(), int Function()>('setsid');

final int Function(int, int) _kill = _libc
    .lookupFunction<Int32 Function(Int32, Int32), int Function(int, int)>(
      'kill',
    );

final int Function(int) _sysconf = _libc
    .lookupFunction<Long Function(Int32), int Function(int)>('sysconf');

// open(2) is variadic: the mode goes through VarArgs so it is passed right on every ABI.
final int Function(Pointer<Uint8>, int, int) _open = _libc
    .lookupFunction<
      Int32 Function(Pointer<Uint8>, Int32, VarArgs<(Int32,)>),
      int Function(Pointer<Uint8>, int, int)
    >('open');

final int Function(int) _close = _libc
    .lookupFunction<Int32 Function(Int32), int Function(int)>('close');

const int sigkill = 9;

/// Creates the file at [path] (NUL-free bytes) with `O_CREAT|O_EXCL|O_WRONLY` and [mode], then closes it.
/// False when it fails, including when the path already exists.
bool createExclusive(List<int> path, int mode) {
  // O_WRONLY is 1; O_CREAT and O_EXCL are 0x40 and 0x80 on Linux, 0x200 and 0x800 on macOS.
  final flags = Platform.isMacOS ? 0x1 | 0x200 | 0x800 : 0x1 | 0x40 | 0x80;
  final pointer = calloc<Uint8>(path.length + 1);
  try {
    pointer.asTypedList(path.length).setAll(0, path);
    final fd = _open(pointer, flags, mode);
    if (fd < 0) return false;
    _close(fd);
    return true;
  } finally {
    calloc.free(pointer);
  }
}

/// Makes the calling process the leader of a new session and process group.
/// False when it fails (for example, it already leads a group).
bool setsid() => _setsid() != -1;

/// `kill(2)`; true when the signal was sent. A negative [pid] signals the
/// process group with that ID.
bool kill(int pid, int signal) => _kill(pid, signal) == 0;

/// `sysconf(_SC_ARG_MAX)`: the byte limit of a command line and its
/// environment (`getconf ARG_MAX`), or null when the system does not say.
int? argMax() {
  // _SC_ARG_MAX is 0 on Linux and 1 on macOS.
  final value = _sysconf(Platform.isMacOS ? 1 : 0);
  return value > 0 ? value : null;
}
