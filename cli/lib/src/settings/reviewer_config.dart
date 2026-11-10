import 'dart:convert';
import 'dart:io';
import 'dart:math';
import 'dart:typed_data';

import 'package:crypto/crypto.dart' show sha256;

import '../vcs/document.dart';
import 'rules.dart';

// The reviewer-config file of `pr-pair.sh` (`reviewer_config_bytes` and `write_reviewer_config`,
// pr-pair.sh:915-949): a reviewer set written as canonical JSON and named by the SHA-256 of its bytes, so a snapshot
// can carry the digest and `policy` can compare it. The one difference from the script is `"format": 2` (design D10).

/// A reviewer-config file stays under this many bytes; reaching it is reported (a problem), not refused.
const int maxConfigBytes = 64 * 1024;

/// What [writeReviewerConfig] settled: where the file is (null when no place was writable), the SHA-256 hex of its
/// bytes, and the size problem if there is one.
class ReviewerConfigFile {
  ReviewerConfigFile(this.path, this.digest, this.problem);

  /// The file's path with `/` separators, or null.
  final String? path;
  final String digest;
  final SettingProblem? problem;
}

/// Python's string order: by code point, which differs from UTF-16 order for a code point past U+FFFF against one in
/// U+E000..U+FFFF.
int compareCodePoints(String a, String b) {
  final x = a.runes.iterator;
  final y = b.runes.iterator;
  while (true) {
    final hasX = x.moveNext();
    final hasY = y.moveNext();
    if (!hasX || !hasY) return hasX == hasY ? 0 : (hasX ? 1 : -1);
    if (x.current != y.current) return x.current < y.current ? -1 : 1;
  }
}

Map<String, Object?> _sortedByCodePoint(Map<String, Object?> m) {
  final keys = m.keys.toList()..sort(compareCodePoints);
  return {for (final k in keys) k: m[k]};
}

/// The canonical bytes of a reviewer-config file: reviewers by login, sorted keys, compact, UTF-8, no `request`.
///
/// Invariant C2: The reviewer-config bytes (`"format": 2`, sorted logins, sorted keys, compact, no `request`) and their
/// SHA-256 name are what every snapshot and `policy` compare. Any change to what a pattern matches must raise
/// `format`, so evidence decided under the old rules never carries a matching digest (D10).
///
/// This is `json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)` encoded with
/// `errors="replace"`: keys sort by code point and a lone surrogate (from a `\ud800` escape) becomes `?`.
///
/// Invariant C1: these bytes and their digest must not change with a JSON library change. [documentText] writes the same
/// bytes as the old writer for every value a reviewer config holds (integers within 64 bits, raw non-ASCII text). A
/// lone surrogate, which `JsonEncoder` writes as an escape, is restored by [documentText] before this function replaces
/// it by `?` (A7 of native-cli-library-foundations). A test pins the digest of such a config.
Uint8List reviewerConfigBytes(Map<String, Reviewer> reviewers) {
  final logins = reviewers.keys.toList()..sort(compareCodePoints);
  final entries = [
    for (final login in logins)
      _sortedByCodePoint({
        'login': login,
        'role': reviewers[login]!.role,
        'timeout': reviewers[login]!.timeout,
        'report': _sortedByCodePoint(reviewers[login]!.report),
      }),
  ];
  final text = documentText(
    _sortedByCodePoint({'format': 2, 'reviewers': entries}),
  );
  final replaced = String.fromCharCodes([
    for (final r in text.runes) (r >= 0xd800 && r <= 0xdfff) ? 0x3f : r,
  ]);
  return Uint8List.fromList(utf8.encode(replaced));
}

String _normal(String path) {
  var p = path.replaceAll(r'\', '/');
  while (p.length > 1 && p.endsWith('/') && !p.endsWith(':/')) {
    p = p.substring(0, p.length - 1);
  }
  return p;
}

String _home(Map<String, String> env) {
  final String? home;
  if (Platform.isWindows) {
    final profile = env['USERPROFILE'];
    home = profile != null && profile.isNotEmpty
        ? profile
        : (env['HOMEDRIVE'] != null && env['HOMEPATH'] != null
              ? '${env['HOMEDRIVE']}${env['HOMEPATH']}'
              : null);
  } else {
    home = env['HOME'];
  }
  if (home == null || home.isEmpty) {
    throw StateError('Could not determine home directory.');
  }
  return home;
}

/// `tempfile.gettempdir()`: the first of TMPDIR, TEMP and TMP that names a directory, else the system's.
String _tempDirectory(Map<String, String> env) {
  for (final name in const ['TMPDIR', 'TEMP', 'TMP']) {
    final v = env[name];
    if (v != null && v.isNotEmpty && Directory(v).existsSync()) return v;
  }
  return Directory.systemTemp.path;
}

final Random _random = Random.secure();

/// `tempfile.mkstemp(dir=..., prefix=".tmp-", suffix=".json")`: a new, empty file with a name no one else has.
File _createTemp(String dir) {
  const letters = 'abcdefghijklmnopqrstuvwxyz0123456789_';
  for (var attempt = 0; ; attempt++) {
    final name = [
      for (var i = 0; i < 8; i++) letters[_random.nextInt(letters.length)],
    ].join();
    final file = File('$dir/.tmp-$name.json');
    try {
      file.createSync(exclusive: true);
      return file;
    } on FileSystemException {
      if (attempt >= 100 || !file.existsSync()) rethrow;
    }
  }
}

bool _sameBytes(List<int> a, List<int> b) {
  if (a.length != b.length) return false;
  for (var i = 0; i < a.length; i++) {
    if (a[i] != b[i]) return false;
  }
  return true;
}

/// Writes the set as a content-addressed file: the path (or null), the SHA-256 hex of its bytes, and a problem at
/// 64 KiB or more. The file lives in `<state dir>/reviewers/<digest>.json`, else under the system temp directory
/// (`<temp>/specwright/reviewers/`); an existing file of that name with the same bytes is reused. The location never
/// stops the caller: with no writable place the path is null.
///
/// `<state dir>` is `SPECWRIGHT_STATE_DIR`, else `~/.cache/specwright`. [environment] is the environment to read
/// (default: the process's) and [tempDirectory] the system temp directory (default: TMPDIR, TEMP or TMP, else the
/// platform's). The file is written to a `.tmp-*.json` beside the target and renamed over it; a writer that loses the
/// rename race reads the target and, when its bytes are the set's, returns it.
///
/// Deliberate gap C6: A writer killed mid-write leaves its `.tmp-*.json` beside the target, and nothing removes it.
/// Reconsider if users report the reviewer-config directory growing.
ReviewerConfigFile writeReviewerConfig(
  Map<String, Reviewer> reviewers, {
  Map<String, String>? environment,
  String? tempDirectory,
}) {
  final env = environment ?? Platform.environment;
  final data = reviewerConfigBytes(reviewers);
  final digest = sha256Hex(data);
  final why = data.length >= maxConfigBytes
      ? SettingProblem(
          'reviewer config',
          '${data.length} bytes is over the ${maxConfigBytes ~/ 1024} KB limit',
        )
      : null;
  final stateEnv = env['SPECWRIGHT_STATE_DIR'];
  final state = _normal(
    stateEnv != null && stateEnv.isNotEmpty
        ? stateEnv
        : '${_home(env)}/.cache/specwright',
  );
  final temp = _normal(tempDirectory ?? _tempDirectory(env));
  for (final base in [state, '$temp/specwright']) {
    final target = File('$base/reviewers/$digest.json');
    File? tmp;
    try {
      target.parent.createSync(recursive: true);
      if (FileSystemEntity.isFileSync(target.path) &&
          _sameBytes(target.readAsBytesSync(), data)) {
        return ReviewerConfigFile(
          target.path.replaceAll(r'\', '/'),
          digest,
          why,
        );
      }
      tmp = _createTemp(target.parent.path);
      tmp.writeAsBytesSync(data, flush: true);
      tmp.renameSync(target.path);
      return ReviewerConfigFile(target.path.replaceAll(r'\', '/'), digest, why);
    } on FileSystemException {
      try {
        tmp?.deleteSync();
      } on FileSystemException {
        // the temp file is already gone
      }
      try {
        // a concurrent writer of the same rules may have won the rename
        if (_sameBytes(target.readAsBytesSync(), data)) {
          return ReviewerConfigFile(
            target.path.replaceAll(r'\', '/'),
            digest,
            why,
          );
        }
      } on FileSystemException {
        // not there, or not readable: try the next place
      }
    }
  }
  return ReviewerConfigFile(null, digest, why);
}

/// The SHA-256 of [data] as 64 lowercase hex digits (`hashlib.sha256(data).hexdigest()`), from `package:crypto`.
String sha256Hex(List<int> data) => sha256.convert(data).toString();
