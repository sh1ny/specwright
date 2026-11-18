// `chmod(2)` bound by hand over package:ffi, like the other native calls of sw.
// Dart's own file API cannot set a mode, and a downloaded sw has none that
// runs.
import 'dart:convert';
import 'dart:ffi';
import 'dart:io' show Platform;

import 'package:ffi/ffi.dart';

/// Makes [path] mode 0755 on Linux and macOS, and does nothing on Windows,
/// where a file runs by its extension. False when the call fails.
bool makeExecutable(String path) {
  if (Platform.isWindows) return true;
  final chmod = DynamicLibrary.process()
      .lookupFunction<
        Int32 Function(Pointer<Uint8>, Uint32),
        int Function(Pointer<Uint8>, int)
      >('chmod');
  final bytes = utf8.encode(path);
  final pointer = calloc<Uint8>(bytes.length + 1);
  pointer.asTypedList(bytes.length).setAll(0, bytes);
  try {
    return chmod(pointer, 493) == 0; // 0755
  } finally {
    calloc.free(pointer);
  }
}
