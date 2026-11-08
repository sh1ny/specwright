import 'dart:convert';
import 'dart:io';
import 'dart:math';
import 'dart:typed_data';

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
    compact: true,
    escapeLineSeparators: false,
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

// ---- SHA-256 (FIPS 180-4) ---------------------------------------------------------------------------------------

const List<int> _k = [
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, //
  0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
  0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786,
  0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147,
  0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
  0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b,
  0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a,
  0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
  0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
];

const int _mask = 0xffffffff;

int _rotr(int x, int n) => ((x >> n) | (x << (32 - n))) & _mask;

/// The SHA-256 of [data] as 64 lowercase hex digits (`hashlib.sha256(data).hexdigest()`). `cli/` takes no package for
/// it: a 30-line digest is cheaper than a dependency the single-file build would carry (ADR 0027).
String sha256Hex(List<int> data) {
  final h = [
    0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, //
    0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
  ];
  final length = data.length;
  final padded = Uint8List(((length + 9 + 63) ~/ 64) * 64)
    ..setRange(0, length, data);
  padded[length] = 0x80;
  final bits = length * 8;
  for (var i = 0; i < 8; i++) {
    padded[padded.length - 1 - i] = (bits >> (8 * i)) & 0xff;
  }
  final w = List<int>.filled(64, 0);
  for (var block = 0; block < padded.length; block += 64) {
    for (var t = 0; t < 16; t++) {
      final i = block + t * 4;
      w[t] =
          (padded[i] << 24) |
          (padded[i + 1] << 16) |
          (padded[i + 2] << 8) |
          padded[i + 3];
    }
    for (var t = 16; t < 64; t++) {
      final s0 = _rotr(w[t - 15], 7) ^ _rotr(w[t - 15], 18) ^ (w[t - 15] >> 3);
      final s1 = _rotr(w[t - 2], 17) ^ _rotr(w[t - 2], 19) ^ (w[t - 2] >> 10);
      w[t] = (w[t - 16] + s0 + w[t - 7] + s1) & _mask;
    }
    var a = h[0], b = h[1], c = h[2], d = h[3];
    var e = h[4], f = h[5], g = h[6], hh = h[7];
    for (var t = 0; t < 64; t++) {
      final s1 = _rotr(e, 6) ^ _rotr(e, 11) ^ _rotr(e, 25);
      final ch = (e & f) ^ (~e & _mask & g);
      final t1 = (hh + s1 + ch + _k[t] + w[t]) & _mask;
      final s0 = _rotr(a, 2) ^ _rotr(a, 13) ^ _rotr(a, 22);
      final maj = (a & b) ^ (a & c) ^ (b & c);
      final t2 = (s0 + maj) & _mask;
      hh = g;
      g = f;
      f = e;
      e = (d + t1) & _mask;
      d = c;
      c = b;
      b = a;
      a = (t1 + t2) & _mask;
    }
    h[0] = (h[0] + a) & _mask;
    h[1] = (h[1] + b) & _mask;
    h[2] = (h[2] + c) & _mask;
    h[3] = (h[3] + d) & _mask;
    h[4] = (h[4] + e) & _mask;
    h[5] = (h[5] + f) & _mask;
    h[6] = (h[6] + g) & _mask;
    h[7] = (h[7] + hh) & _mask;
  }
  return h.map((x) => x.toRadixString(16).padLeft(8, '0')).join();
}
