import 'dart:io';
import 'dart:typed_data';

/// A path that exists but, following links, is not a regular file.
class NotRegularFile implements Exception {
  NotRegularFile(this.path, this.kind);

  /// The path as it was given.
  final String path;

  /// What it is instead: `directory`, `pipe`, `unixDomainSock` or `link`.
  final String kind;

  @override
  String toString() => '$path is not a regular file ($kind)';
}

/// The type [path] has, following links.
FileSystemEntityType _typeOf(String path) => FileSystemEntity.typeSync(path);

/// Throws [NotRegularFile] when [path] exists and is not a regular file;
/// returns whether it is one (false: it is not there).
bool _isRegular(String path) {
  final type = _typeOf(path);
  if (type == FileSystemEntityType.notFound) return false;
  if (type == FileSystemEntityType.file) return true;
  throw NotRegularFile(path, type.toString());
}

/// The one reader of a work-tree file in the finish code and the version check
/// (C38).
///
/// C38: every work-tree file open (read or copy source) in `cli/lib/src/finish/`,
/// `cli/lib/src/entry/project_version.dart` and the finish-side strict settings
/// read goes through [readRegularFile] or [copyRegularFile]. Release and update
/// settings reads are out of scope and unchanged. It refuses a target that is
/// not a regular file before opening it, so no planner, guard or version check
/// blocks on a FIFO or device a branch or a symlink put in its path. A source
/// test enforces the single reader.
///
/// It stats [path], following links, and returns null when nothing is there,
/// throws [NotRegularFile] (never opening it) for anything but a regular file,
/// and otherwise reads the file: all of it, or at most [limit] bytes. Each
/// caller maps the refusal to its own code (`sw_mismatch` for the version
/// stamp, `vcs_error` naming the path elsewhere). A link to a regular file
/// reads as the file; the window between the stat and the open needs a local
/// writer and is outside the threat model. Any other failure is the
/// [FileSystemException] of the open.
Uint8List? readRegularFile(String path, {int? limit}) {
  if (!_isRegular(path)) return null;
  final handle = File(path).openSync();
  try {
    final size = handle.lengthSync();
    return handle.readSync(limit == null || size < limit ? size : limit);
  } finally {
    handle.closeSync();
  }
}

/// Copies the regular file [from] to [to]; [NotRegularFile] when [from] is not
/// one (nothing is written), and a [FileSystemException] when it is not there.
void copyRegularFile(String from, String to) {
  if (!_isRegular(from)) {
    throw FileSystemException('Cannot open file', from);
  }
  File(from).copySync(to);
}
