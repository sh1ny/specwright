// The two file operations `sw` needs that the Dart SDK does not offer (design
// D8): a hard link that never replaces its destination (`ln`), and a rename
// that replaces it (`mv -f`). POSIX `link` and `rename`; Windows
// `CreateHardLinkW` and `MoveFileExW` with replace. Opened on first use.
import 'dart:ffi';
import 'dart:io';

import 'package:ffi/ffi.dart';

import '../vcs/codec.dart';

/// Makes [destination] a hard link to [source]. Fails with a
/// [FileSystemException] when [destination] exists or the link cannot be made.
void hardLink(String source, String destination) =>
    _operations.link(source, destination);

/// Renames [source] to [destination], replacing [destination] when it exists.
/// Fails with a [FileSystemException] when the rename cannot be made.
void replaceFile(String source, String destination) =>
    _operations.replace(source, destination);

final _Operations _operations = Platform.isWindows
    ? _WindowsOperations()
    : _PosixOperations();

abstract class _Operations {
  void link(String source, String destination);
  void replace(String source, String destination);
}

class _PosixOperations implements _Operations {
  _PosixOperations() {
    final library = DynamicLibrary.process();
    _link = library
        .lookupFunction<
          Int32 Function(Pointer<Uint8>, Pointer<Uint8>),
          int Function(Pointer<Uint8>, Pointer<Uint8>)
        >('link');
    _rename = library
        .lookupFunction<
          Int32 Function(Pointer<Uint8>, Pointer<Uint8>),
          int Function(Pointer<Uint8>, Pointer<Uint8>)
        >('rename');
  }
  late final int Function(Pointer<Uint8>, Pointer<Uint8>) _link, _rename;

  Pointer<Uint8> _path(String path) {
    final bytes = encodeEscaped(path);
    final pointer = calloc<Uint8>(bytes.length + 1);
    pointer.asTypedList(bytes.length).setAll(0, bytes);
    return pointer;
  }

  void _pair(
    String source,
    String destination,
    int Function(Pointer<Uint8>, Pointer<Uint8>) operation,
    String name,
  ) {
    final a = _path(source), b = _path(destination);
    try {
      if (operation(a, b) != 0) {
        throw FileSystemException('$name failed', destination);
      }
    } finally {
      calloc.free(a);
      calloc.free(b);
    }
  }

  @override
  void link(String source, String destination) =>
      _pair(source, destination, _link, 'hard link');
  @override
  void replace(String source, String destination) =>
      _pair(source, destination, _rename, 'atomic replacement');
}

class _WindowsOperations implements _Operations {
  _WindowsOperations() {
    final library = DynamicLibrary.open('kernel32.dll');
    _link = library
        .lookupFunction<
          Int32 Function(Pointer<Utf16>, Pointer<Utf16>, Pointer<Void>),
          int Function(Pointer<Utf16>, Pointer<Utf16>, Pointer<Void>)
        >('CreateHardLinkW');
    _rename = library
        .lookupFunction<
          Int32 Function(Pointer<Utf16>, Pointer<Utf16>, Uint32),
          int Function(Pointer<Utf16>, Pointer<Utf16>, int)
        >('MoveFileExW');
  }
  late final int Function(Pointer<Utf16>, Pointer<Utf16>, Pointer<Void>) _link;
  late final int Function(Pointer<Utf16>, Pointer<Utf16>, int) _rename;

  @override
  void link(String source, String destination) {
    final a = source.toNativeUtf16(), b = destination.toNativeUtf16();
    try {
      if (_link(b, a, nullptr) == 0) {
        throw FileSystemException('hard link failed', destination);
      }
    } finally {
      calloc.free(a);
      calloc.free(b);
    }
  }

  @override
  void replace(String source, String destination) {
    final a = source.toNativeUtf16(), b = destination.toNativeUtf16();
    try {
      if (_rename(a, b, 1) == 0) {
        throw FileSystemException('atomic replacement failed', destination);
      }
    } finally {
      calloc.free(a);
      calloc.free(b);
    }
  }
}
