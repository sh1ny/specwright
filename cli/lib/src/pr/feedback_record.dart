import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math';

import '../process/limits.dart';
import '../settings/reviewer_config.dart' show sha256Hex;
import '../vcs/codec.dart';
import '../vcs/document.dart';
import 'feedback_record_files.dart';
import 'pair.dart';

export 'feedback_record_files.dart'
    show RecordAlreadyExists, RecordFiles, RecordOutput;

class LocatedRecord {
  LocatedRecord(this.path, this.ignoredLegacy);
  final String path;
  final String? ignoredLegacy;
}

/// C8: SDK-exclusive publication prefers a hard link, then creates and opens
/// its own file. Interruption can leave an empty or partial record: write
/// refuses it as record_exists; plan/adopt/done refuse it as record_unreadable.
/// Ordinary permission/open/write/close failure cleans only the created file.
/// Native lock files and legacy lock directories share the .lock path and
/// block each other. Native cleanup never removes a legacy directory.
///
/// C15: SDK exceptions, post-failure occupancy and single-call native success
/// classify outcomes. Cross-FFI errno/GetLastError branching (SDK issue 38832),
/// exists-then-create exclusivity and process-wide umask changes stay rejected.
/// This owner-approved lock representation refines ADR 0031; stored records
/// and the explicit interrupted-pass recovery workflow remain interoperable.
///
/// JSON indentation/key order are not protocol; existing legacy bytes are
/// copied unchanged when their identity is migrated.
class FeedbackRecordStore {
  FeedbackRecordStore(this.directory, {RecordFiles? files})
    : files = files ?? RecordFiles.native();
  final String directory;
  final RecordFiles files;
  final List<String> leftLocks = [];
  static final _random = Random.secure();
  static String _normal(String value) => value.replaceAll(r'\', '/');
  static String _safe(String value) => String.fromCharCodes(
    value.runes.map(
      (r) =>
          r >= 65 && r <= 90 ||
              r >= 97 && r <= 122 ||
              r >= 48 && r <= 57 ||
              r == 46 ||
              r == 95 ||
              r == 45
          ? r
          : 95,
    ),
  );
  static File _file(String path) => File.fromRawPath(encodeEscaped(path));
  String recordPath(String repo, String change) {
    final slash = repo.indexOf('/');
    final owner = slash < 0 ? repo : repo.substring(0, slash),
        name = slash < 0 ? '' : repo.substring(slash + 1);
    final hash = sha256Hex(
      encodeEscaped('${owner.toLowerCase()}\n${name.toLowerCase()}\n$change'),
    ).substring(0, 32);
    final readable = '${_safe(owner)}.${_safe(name)}.${_safe(change)}';
    return '$directory/${readable.substring(0, min(120, readable.length)).toLowerCase()}-$hash.json';
  }

  String legacyPath(String repo, String change) {
    final slash = repo.indexOf('/');
    return '$directory/${_safe(slash < 0 ? repo : repo.substring(0, slash))}-${_safe(slash < 0 ? '' : repo.substring(slash + 1))}-${_safe(change)}.json';
  }

  Future<T> withLock<T>(String path, FutureOr<T> Function() body) async {
    final lock = '$path.lock';
    try {
      files.acquireLock(lock);
    } on RecordAlreadyExists {
      throw PairStop(
        'record_busy',
        '$lock exists: another call or an interrupted call holds the record',
        extra: {'path': _normal(path), 'lock': _normal(lock)},
      );
    }
    try {
      return await body();
    } finally {
      try {
        files.releaseLock(lock);
      } on FileSystemException {
        leftLocks.add(_normal(lock));
      }
    }
  }

  void publish(String source, String destination) {
    try {
      files.link(source, destination);
      return;
    } on RecordAlreadyExists {
      rethrow;
    } on FileSystemException {
      /* Any failed link permits SDK-exclusive fallback, which still refuses
         an occupied destination without changing it. */
    }
    final output = files.createExclusive(destination);
    try {
      _writeAndClose(output, () => files.readBytes(source));
    } on Object {
      try {
        files.delete(destination);
      } on FileSystemException {
        /* Retain the primary publication failure. */
      }
      rethrow;
    }
  }

  void _writeAndClose(RecordOutput output, List<int> Function() content) {
    Object? failure;
    StackTrace? trace;
    try {
      output.writeAll(content());
    } on Object catch (error, stack) {
      failure = error;
      trace = stack;
    }
    try {
      output.close();
    } on Object catch (error, stack) {
      failure ??= error;
      trace ??= stack;
    }
    if (failure != null) Error.throwWithStackTrace(failure, trace!);
  }

  void _removeTemporary(String path) {
    try {
      files.delete(path);
    } on FileSystemException {
      // Cleanup never replaces the publication/replacement outcome.
    }
  }

  String _temporary(String path, Map<String, Object?> record) {
    // Derive the parent from the original string. File.parent uses .path,
    // which decodes and loses non-UTF-8 bytes even on File.fromRawPath.
    final parent = FileSystemEntity.parentOf(path);
    // SDK recursive creation also derives parents from .path. Create missing
    // ancestors individually so their original bytes survive. Directory
    // creation may share an ancestor; unlike a lock, it grants no ownership.
    final missing = <String>[];
    var ancestor = parent;
    while (!Directory.fromRawPath(encodeEscaped(ancestor)).existsSync()) {
      missing.add(ancestor);
      final next = FileSystemEntity.parentOf(ancestor);
      if (next == ancestor) break;
      ancestor = next;
    }
    for (final directory in missing.reversed) {
      Directory.fromRawPath(encodeEscaped(directory)).createSync();
    }
    for (var attempt = 0; attempt < 10; attempt++) {
      final nonce = List.generate(
        16,
        (_) => _random.nextInt(256).toRadixString(16).padLeft(2, '0'),
      ).join();
      final temp = '$parent/.tmp-$nonce.json';
      RecordOutput output;
      try {
        output = files.createExclusive(temp);
      } on RecordAlreadyExists {
        continue;
      }
      try {
        _writeAndClose(output, () {
          // Record contents are UTF-8 JSON, not filesystem bytes. Escape
          // surrogate units, including path escapes, without changing the
          // shared document writer's stdout byte protocol. Escaped pairs
          // still decode to the same supplementary Unicode characters.
          final json = jsonEncode(record).replaceAllMapped(
            RegExp(r'[\uD800-\uDFFF]'),
            (match) =>
                '\\u${match[0]!.codeUnitAt(0).toRadixString(16).padLeft(4, '0')}',
          );
          return utf8.encode('$json\n');
        });
      } on Object {
        try {
          files.delete(temp);
        } on FileSystemException {
          /* Retain the primary temporary-write failure. */
        }
        rethrow;
      }
      return temp;
    }
    throw FileSystemException(
      'could not create a unique feedback temporary file',
      path,
    );
  }

  void writeNew(String path, Map<String, Object?> record) {
    final temp = _temporary(path, record);
    try {
      try {
        publish(temp, path);
      } on RecordAlreadyExists {
        throw PairStop(
          'record_exists',
          'a feedback pass record exists at $path; resume that pass before starting another',
          extra: {'path': _normal(path)},
        );
      }
    } finally {
      _removeTemporary(temp);
    }
  }

  void replaceRecord(String path, Map<String, Object?> record) {
    final temp = _temporary(path, record);
    try {
      files.replace(temp, path);
    } finally {
      _removeTemporary(temp);
    }
  }

  Object? load(String path) {
    List<int> bytes;
    try {
      bytes = files.readBytes(path, limit: defaultMaxBytes);
    } on FileSystemException catch (e) {
      if (e.osError?.errorCode == 2 ||
          Platform.isWindows && e.osError?.errorCode == 3) {
        return null;
      }
      throw PairStop('record_unreadable', '$path: $e');
    }
    if (bytes.length > defaultMaxBytes) {
      throw PairStop(
        'record_unreadable',
        '$path: larger than ${defaultMaxBytes ~/ (1024 * 1024)} MiB',
      );
    }
    try {
      return decodeJson(decodeJsonBytes(bytes, path), file: path);
    } on JsonInputException catch (e) {
      throw PairStop('record_unreadable', e.message);
    }
  }

  bool _legacyExists(String path) {
    try {
      return _file(path).existsSync();
    } on FileSystemException catch (e) {
      if ([36, 63, 206].contains(e.osError?.errorCode)) return false;
      rethrow;
    }
  }

  LocatedRecord locate(String repo, String change) {
    final path = recordPath(repo, change), old = legacyPath(repo, change);
    if (!_legacyExists(old)) return LocatedRecord(path, null);
    if (_file(path).existsSync()) {
      try {
        final a = files.readBytes(old), b = files.readBytes(path);
        if (a.length == b.length &&
            Iterable.generate(a.length, (i) => a[i] == b[i]).every((v) => v)) {
          files.delete(old);
          return LocatedRecord(path, null);
        }
      } on FileSystemException {
        /* Continue with identity-aware legacy recovery. */
      }
    }
    Object? record;
    try {
      record = load(old);
    } on PairStop {
      if (_file(path).existsSync()) return LocatedRecord(path, _normal(old));
      rethrow;
    }
    if (record is! Map ||
        (record['code_repo'] ?? '').toString().toLowerCase() !=
            repo.toLowerCase() ||
        record['change'] != change) {
      return LocatedRecord(path, null);
    }
    if (_file(path).existsSync()) return LocatedRecord(path, _normal(old));
    try {
      publish(old, path);
    } on RecordAlreadyExists {
      return LocatedRecord(path, _normal(old));
    }
    try {
      files.delete(old);
    } on FileSystemException catch (e) {
      if (e.osError?.errorCode != 2 && e.osError?.errorCode != 3) rethrow;
    }
    return LocatedRecord(path, null);
  }
}
