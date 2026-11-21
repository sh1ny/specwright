import 'dart:io';

import '../entry/regular_file.dart';
import '../vcs/stop.dart';

/// The `vcs_error` stop for a work-tree target that is not a regular file: it
/// names the path and nothing was opened.
VcsStop notRegularStop(NotRegularFile e) => VcsStop(
  'vcs_error',
  '${e.path} is not a regular file (${e.kind}); it is not read. Replace it '
      'with a regular file, or remove it, then plan again',
);

/// The finish-side strict settings read: the file `openspec/specwright.yaml`
/// under the first of [bases] that holds one (the directory the settings are
/// read from, then its top level) must be a regular file, following links.
/// A present one that is not, such as a link to a FIFO, stops with `vcs_error`
/// naming the path instead of being opened, by the planner and by the
/// `check branch` guard alike. A file that exists but cannot be read is the same stop. A missing file passes,
/// as it means Git.
///
/// The shared settings reader (`readSettingsText`) and its release and update
/// callers are unchanged (C38).
void requireRegularSettings(Iterable<String> bases) {
  for (final base in bases) {
    final path = '$base/openspec/specwright.yaml';
    try {
      // one byte: the guard reads nothing the shared reader will use
      if (readRegularFile(path, limit: 1) != null) return;
    } on NotRegularFile catch (e) {
      throw notRegularStop(e);
    } on FileSystemException catch (e) {
      throw VcsStop('vcs_error', 'cannot read $path: ${e.message}');
    }
  }
}
