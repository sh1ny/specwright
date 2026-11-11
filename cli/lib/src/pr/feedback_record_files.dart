import 'dart:ffi';
import 'dart:io';

import 'package:ffi/ffi.dart';

import '../fs/link.dart';
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
  void link(String source, String destination) => hardLink(source, destination);
  @override
  void replace(String source, String destination) =>
      replaceFile(source, destination);

  @override
  RecordOutput createExclusive(String path) {
    _create(path);
    try {
      (makePrivate ?? _makePrivate)(path);
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

/// Private POSIX permissions for a new record. Windows records inherit the
/// per-user directory ACL.
void _makePrivate(String path) {
  if (Platform.isWindows) return;
  final chmod = DynamicLibrary.process()
      .lookupFunction<
        Int32 Function(Pointer<Uint8>, Uint32),
        int Function(Pointer<Uint8>, int)
      >('chmod');
  final bytes = encodeEscaped(path);
  final pointer = calloc<Uint8>(bytes.length + 1);
  pointer.asTypedList(bytes.length).setAll(0, bytes);
  try {
    if (chmod(pointer, 0x180) != 0) {
      throw FileSystemException('private permissions failed', path);
    }
  } finally {
    calloc.free(pointer);
  }
}
