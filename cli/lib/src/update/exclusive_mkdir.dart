// `mkdir(2)` and `CreateDirectoryW` bound by hand over package:ffi, like the
// other native calls of sw. `Directory.createSync` succeeds on a directory that
// is there already, so two runs creating the update lock would both win; these
// fail with "exists", which is what the lock's mutual exclusion needs.
import 'dart:ffi';
import 'dart:io' show Platform;

import 'package:ffi/ffi.dart';

/// Creates the directory [path] (its parent must exist) and returns true, or
/// returns false when it cannot, an existing directory included.
bool createDirectoryExclusive(String path) =>
    Platform.isWindows ? _createWindows(path) : _createPosix(path);

bool _createPosix(String path) {
  final mkdir = DynamicLibrary.process()
      .lookupFunction<
        Int32 Function(Pointer<Utf8>, Uint32),
        int Function(Pointer<Utf8>, int)
      >('mkdir');
  final native = path.toNativeUtf8();
  try {
    return mkdir(native, 511) == 0; // 0777, less the umask, as `mkdir` does
  } finally {
    calloc.free(native);
  }
}

bool _createWindows(String path) {
  final create = DynamicLibrary.open('kernel32.dll')
      .lookupFunction<
        Int32 Function(Pointer<Utf16>, Pointer<Void>),
        int Function(Pointer<Utf16>, Pointer<Void>)
      >('CreateDirectoryW');
  final native = path.toNativeUtf16();
  try {
    return create(native, nullptr) != 0;
  } finally {
    calloc.free(native);
  }
}
