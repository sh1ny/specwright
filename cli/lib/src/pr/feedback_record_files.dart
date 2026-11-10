import 'dart:ffi';
import 'dart:io';

import 'package:ffi/ffi.dart';

import '../vcs/codec.dart';

abstract class RecordOutput {
  void writeAll(List<int> bytes);
  void close();
}

class RecordAlreadyExists implements Exception {
  RecordAlreadyExists(this.path);
  final String path;
}

/// Exclusive creation belongs to the SDK. The native boundary only reports
/// success for hard links, replacement and private POSIX permissions.
abstract class RecordFiles {
  factory RecordFiles.native({
    RandomAccessFile Function(File)? openCreated,
    void Function(String)? makePrivate,
  }) => _SdkFiles(openCreated: openCreated, makePrivate: makePrivate);

  void acquireLock(String path);
  void releaseLock(String path);

  /// The bytes of [path]; with [limit], at most `limit + 1` of them (one more than the bound, so a longer file shows).
  List<int> readBytes(String path, {int? limit});
  void link(String source, String destination);
  RecordOutput createExclusive(String path);
  void replace(String source, String destination);
  void delete(String path);
}

class _SdkFiles implements RecordFiles {
  _SdkFiles({RandomAccessFile Function(File)? openCreated, this.makePrivate})
    : _openCreated =
          openCreated ?? ((file) => file.openSync(mode: FileMode.write));

  final RandomAccessFile Function(File) _openCreated;
  final void Function(String)? makePrivate;
  late final _NativeOperations _native = Platform.isWindows
      ? _WindowsOperations()
      : _PosixOperations();

  File _file(String path) => File.fromRawPath(encodeEscaped(path));

  void _create(String path) {
    try {
      _file(path).createSync(exclusive: true);
    } on PathExistsException {
      // The holder may already have released by the time we handle this.
      throw RecordAlreadyExists(path);
    } on FileSystemException {
      // Windows reports a directory collision as access denied. This check
      // classifies a failed exclusive operation; it never grants ownership.
      // Check the link itself before queries that could follow its target.
      final raw = encodeEscaped(path);
      if (Link.fromRawPath(raw).existsSync() ||
          _file(path).existsSync() ||
          Directory.fromRawPath(raw).existsSync()) {
        throw RecordAlreadyExists(path);
      }
      rethrow;
    }
  }

  @override
  void acquireLock(String path) => _create(path);
  @override
  void releaseLock(String path) => _file(path).deleteSync();
  @override
  List<int> readBytes(String path, {int? limit}) {
    if (limit == null) return _file(path).readAsBytesSync();
    // at most limit + 1 bytes, so a caller sees that the file is longer without reading it whole
    final file = _file(path).openSync();
    try {
      return file.readSync(limit + 1);
    } finally {
      file.closeSync();
    }
  }

  @override
  void delete(String path) => _file(path).deleteSync();
  @override
  void link(String source, String destination) =>
      _native.link(source, destination);
  @override
  void replace(String source, String destination) =>
      _native.replace(source, destination);

  @override
  RecordOutput createExclusive(String path) {
    _create(path);
    try {
      (makePrivate ?? _native.makePrivate)(path);
      return _SdkOutput(_openCreated(_file(path)));
    } on Object {
      try {
        _file(path).deleteSync();
      } on FileSystemException {
        // Preserve the permission/open failure, not its cleanup error.
      }
      rethrow;
    }
  }
}

class _SdkOutput implements RecordOutput {
  _SdkOutput(this.file);
  final RandomAccessFile file;
  @override
  void writeAll(List<int> bytes) => file.writeFromSync(bytes);
  @override
  void close() => file.closeSync();
}

abstract class _NativeOperations {
  void link(String source, String destination);
  void replace(String source, String destination);
  void makePrivate(String path);
}

class _PosixOperations implements _NativeOperations {
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
    _chmod = library
        .lookupFunction<
          Int32 Function(Pointer<Uint8>, Uint32),
          int Function(Pointer<Uint8>, int)
        >('chmod');
  }
  late final int Function(Pointer<Uint8>, Pointer<Uint8>) _link, _rename;
  late final int Function(Pointer<Uint8>, int) _chmod;

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
  @override
  void makePrivate(String path) {
    final pointer = _path(path);
    try {
      if (_chmod(pointer, 0x180) != 0) {
        throw FileSystemException('private permissions failed', path);
      }
    } finally {
      calloc.free(pointer);
    }
  }
}

class _WindowsOperations implements _NativeOperations {
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

  @override
  void makePrivate(String path) {
    // Inherit the same per-user directory ACL as the existing Windows records.
  }
}
