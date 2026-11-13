import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:path/path.dart' as p;

import '../process/launch.dart';
import 'stop.dart';

const int _blobWriteSize = 64 * 1024;

/// Materializes the exact Git tree at [tip] under [destination]. It reads paths
/// from `ls-tree` and streams `cat-file --batch` blobs to disk incrementally;
/// it adds no snapshot deadline, and its path-list memory grows with file count.
/// The caller supplies a private destination that does not yet exist.
Future<void> snapshotTip(
  String directory,
  String tip,
  Directory destination, {
  Map<String, String>? environment,
  List<String>? helperCommand,
}) async {
  final tree = await launch(
    ['git', 'ls-tree', '-r', '-z', '--full-tree', tip],
    cwd: directory,
    environment: environment,
    helperCommand: helperCommand,
  );
  _checkGit(tree, 'ls-tree', directory, tip);
  final blobs = _treeBlobs(tree.stdout, tip);
  final style = _pathContext;
  var rootPath = style.normalize(p.absolute(destination.path));
  Directory? linkData;
  _BlobWriter? writer;
  var madeDestination = false;
  var completed = false;

  try {
    destination.createSync(recursive: true);
    madeDestination = true;
    rootPath = Directory(destination.path).resolveSymbolicLinksSync();
    if (blobs.any((blob) => blob.isLink)) {
      linkData = Directory.systemTemp.createTempSync('sw-review-links-');
      var linkIndex = 0;
      for (final blob in blobs) {
        if (blob.isLink) {
          blob.linkData = File(style.join(linkData.path, '$linkIndex'));
          linkIndex++;
        }
      }
    }

    writer = _BlobWriter(blobs, Directory(rootPath), style);
    final objectIds = BytesBuilder(copy: false);
    for (final blob in blobs) {
      objectIds.add(ascii.encode(blob.oid));
      objectIds.add(const [0x0a]);
    }
    final result = await launch(
      ['git', 'cat-file', '--batch'],
      cwd: directory,
      input: objectIds.takeBytes(),
      environment: environment,
      helperCommand: helperCommand,
      stdoutSink: writer.add,
    );
    _checkGit(result, 'cat-file', directory, tip);
    await writer.finish();

    for (final blob in blobs) {
      if (blob.isLink) {
        await _materializeLink(blob, rootPath, style);
      }
    }
    completed = true;
  } finally {
    try {
      await writer?.close();
    } on Object {
      // Preserve the error that stopped snapshot materialization.
    }
    try {
      linkData?.deleteSync(recursive: true);
    } on FileSystemException {
      // Best-effort cleanup of private scratch files.
    }
    if (!completed && madeDestination) {
      try {
        destination.deleteSync(recursive: true);
      } on FileSystemException {
        // Preserve the original failure.
      }
    }
  }
}

final p.Context _pathContext = p.Context(
  style: Platform.isWindows ? p.Style.windows : p.Style.posix,
);

class _TreeBlob {
  _TreeBlob(this.oid, this.parts, this.isLink);

  final String oid;
  final List<String> parts;
  final bool isLink;
  File? linkData;

  String outputPath(Directory destination, p.Context style) =>
      style.join(destination.path, parts.join(style.separator));
}

List<_TreeBlob> _treeBlobs(Uint8List bytes, String tip) {
  final blobs = <_TreeBlob>[];
  var start = 0;
  while (start < bytes.length) {
    var end = start;
    while (end < bytes.length && bytes[end] != 0) {
      end++;
    }
    if (end == bytes.length) {
      throw ReviewStop(
        'git_error',
        'git ls-tree $tip returned an incomplete tree',
      );
    }
    if (end == start) {
      start = end + 1;
      continue;
    }

    var tab = start;
    while (tab < end && bytes[tab] != 0x09) {
      tab++;
    }
    if (tab == end) {
      throw ReviewStop(
        'git_error',
        'git ls-tree $tip returned a malformed tree entry',
      );
    }
    final fields = ascii
        .decode(Uint8List.sublistView(bytes, start, tab))
        .split(' ');
    if (fields.length != 3) {
      throw ReviewStop(
        'git_error',
        'git ls-tree $tip returned a malformed tree entry',
      );
    }
    final nameBytes = Uint8List.sublistView(bytes, tab + 1, end);
    final String name;
    try {
      name = utf8.decode(nameBytes);
    } on FormatException {
      throw ReviewStop(
        'not_utf8',
        'git tree for $tip contains a path that is not UTF-8',
      );
    }
    final parts = name.split('/');
    if (fields[1] == 'blob' &&
        !parts.any((part) => part.isEmpty || part == '.' || part == '..')) {
      blobs.add(_TreeBlob(fields[2], parts, fields[0] == '120000'));
    }
    start = end + 1;
  }
  return blobs;
}

void _checkGit(
  LaunchResult result,
  String command,
  String directory,
  String tip,
) {
  if (!result.startFailed && result.exitCode == 0) return;
  final detail = utf8.decode(result.stderr, allowMalformed: true).trim();
  throw ReviewStop(
    'git_error',
    'git $command $tip in $directory failed'
        '${detail.isEmpty ? '' : ': $detail'}',
  );
}

class _BlobWriter {
  _BlobWriter(this.blobs, this.destination, this.style);

  final List<_TreeBlob> blobs;
  final Directory destination;
  final p.Context style;
  final List<int> _header = [];
  int _index = 0;
  int _remaining = 0;
  _BatchState _state = _BatchState.header;
  RandomAccessFile? _output;

  Future<void> add(List<int> bytes) async {
    var offset = 0;
    while (offset < bytes.length) {
      switch (_state) {
        case _BatchState.header:
          final lineStart = offset;
          while (offset < bytes.length && bytes[offset] != 0x0a) {
            offset++;
          }
          _header.addAll(bytes.getRange(lineStart, offset));
          if (offset == bytes.length) return;
          offset++; // the header LF
          await _openBlob();
          break;
        case _BatchState.blob:
          final count = _remaining < bytes.length - offset
              ? _remaining
              : bytes.length - offset;
          final writeLength = count < _blobWriteSize ? count : _blobWriteSize;
          await _output!.writeFrom(bytes, offset, offset + writeLength);
          offset += writeLength;
          _remaining -= writeLength;
          if (_remaining == 0) _state = _BatchState.separator;
          break;
        case _BatchState.separator:
          if (bytes[offset] != 0x0a) {
            throw ReviewStop(
              'git_error',
              'git cat-file returned a malformed blob separator',
            );
          }
          offset++;
          final output = _output;
          _output = null;
          await output!.close();
          _index++;
          _state = _BatchState.header;
          break;
      }
    }
  }

  Future<void> _openBlob() async {
    final fields = ascii.decode(_header).split(RegExp(r'\s+'));
    _header.clear();
    if (_index >= blobs.length || fields.length != 3) {
      throw ReviewStop(
        'git_error',
        'git cat-file returned a malformed batch header',
      );
    }
    final blob = blobs[_index];
    final size = int.tryParse(fields[2]);
    if (fields[0] != blob.oid ||
        fields[1] != 'blob' ||
        size == null ||
        size < 0) {
      throw ReviewStop(
        'git_error',
        'git cat-file returned an unexpected batch object',
      );
    }
    final path = blob.isLink
        ? blob.linkData!.path
        : blob.outputPath(destination, style);
    Directory(style.dirname(path)).createSync(recursive: true);
    _output = await File(path).open(mode: FileMode.write);
    _remaining = size;
    _state = size == 0 ? _BatchState.separator : _BatchState.blob;
  }

  Future<void> finish() async {
    if (_index != blobs.length ||
        _state != _BatchState.header ||
        _header.isNotEmpty) {
      throw ReviewStop(
        'git_error',
        'git cat-file returned an incomplete batch',
      );
    }
  }

  Future<void> close() async {
    final output = _output;
    _output = null;
    if (output != null) await output.close();
  }
}

enum _BatchState { header, blob, separator }

Future<void> _materializeLink(
  _TreeBlob blob,
  String root,
  p.Context style,
) async {
  final dataFile = blob.linkData!;
  final destination = blob.outputPath(Directory(root), style);
  Directory(style.dirname(destination)).createSync(recursive: true);
  String? target;
  try {
    target = await dataFile.readAsString();
  } on FormatException {
    // Dart's filesystem APIs cannot represent an arbitrary non-UTF-8 target.
  }

  String? realTarget;
  if (target != null) {
    try {
      final requested = style.isAbsolute(target)
          ? target
          : style.join(style.dirname(destination), target);
      realTarget = File(requested).resolveSymbolicLinksSync();
    } on FileSystemException {
      // An unresolved link is materialized as its target text below.
    }
  }
  final inside = realTarget != null && _isInside(root, realTarget, style);
  if (inside) {
    try {
      Link(destination).createSync(target!);
      return;
    } on FileSystemException {
      // Without symlink support, fall back to copying the safe in-tree target.
    }
  }
  if (inside) {
    final resolvedTarget = realTarget!;
    final type = FileSystemEntity.typeSync(resolvedTarget);
    if (type == FileSystemEntityType.file) {
      await File(resolvedTarget).copy(destination);
      return;
    }
    if (type == FileSystemEntityType.directory) {
      await _copyInsideDirectory(
        resolvedTarget,
        destination,
        root,
        style,
        <String>{},
      );
      return;
    }
  }
  await dataFile.copy(destination);
}

bool _isInside(String root, String target, p.Context style) {
  final relative = style.relative(target, from: root);
  return relative != '.' &&
      relative != '..' &&
      !relative.startsWith('..${style.separator}') &&
      !style.isAbsolute(relative);
}

Future<void> _copyInsideDirectory(
  String source,
  String destination,
  String root,
  p.Context style,
  Set<String> visiting,
) async {
  Directory(destination).createSync(recursive: true);
  final realSource = Directory(source).resolveSymbolicLinksSync();
  if (!_isInside(root, realSource, style) || !visiting.add(realSource)) return;
  try {
    for (final entity in Directory(realSource).listSync(followLinks: false)) {
      final target = style.join(destination, style.basename(entity.path));
      final type = FileSystemEntity.typeSync(entity.path, followLinks: false);
      if (type == FileSystemEntityType.file) {
        await File(entity.path).copy(target);
      } else if (type == FileSystemEntityType.directory) {
        await _copyInsideDirectory(entity.path, target, root, style, visiting);
      } else if (type == FileSystemEntityType.link) {
        final linkTarget = Link(entity.path).targetSync();
        String? realTarget;
        try {
          realTarget = Link(entity.path).resolveSymbolicLinksSync();
        } on FileSystemException {
          // An unresolved nested link becomes a file holding its target text.
        }
        if (realTarget != null && _isInside(root, realTarget, style)) {
          final linkType = FileSystemEntity.typeSync(realTarget);
          if (linkType == FileSystemEntityType.file) {
            await File(realTarget).copy(target);
            continue;
          }
          if (linkType == FileSystemEntityType.directory) {
            await _copyInsideDirectory(
              realTarget,
              target,
              root,
              style,
              visiting,
            );
            continue;
          }
        }
        await File(target).writeAsString(linkTarget);
      }
    }
  } finally {
    visiting.remove(realSource);
  }
}
