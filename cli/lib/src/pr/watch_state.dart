import 'dart:io' as io;
import 'dart:io';
import 'dart:math';

import '../fence/urls.dart' show lowerAscii;
import '../vcs/codec.dart';
import 'context.dart';
import 'text.dart';

// The watch claims and head records of `pr-snapshot.sh` (design D9, constraint C6), kept as they were: the v2 layout,
// the claim names, the nonce format and the order of claims. `pr-pair.sh` and a watcher of the old script read and
// write the same files.

/// `SPECWRIGHT_STATE_DIR`, else `$HOME/.cache/specwright`. On Windows a `/`-path (Git Bash's form of `HOME`) goes through
/// `cygpath -m`, so it names the directory the old script used (D9).
Future<String> stateBase(PrContext ctx) async {
  final env = ctx.env;
  var base = env['SPECWRIGHT_STATE_DIR'];
  if (base == null || base.isEmpty) {
    base = '${env['HOME'] ?? ''}/.cache/specwright';
  }
  return ctx.native(base);
}

/// `<base>/watch/v2/<owner>/<name>/<pr>`, lower case: ASCII folding only, as `tr 'A-Z' 'a-z'`.
String claimDirectory(String base, String owner, String name, String pr) =>
    '$base/watch/v2/${lowerAscii('$owner/$name/$pr')}';

/// `<base>/heads/<owner>/<name>/<pr>`, lower case.
String headsDirectory(String base, String owner, String name, String pr) =>
    '$base/heads/${lowerAscii('$owner/$name/$pr')}';

class _Listed {
  _Listed(this.number, this.nonce, this.name);

  final int number;

  /// `-` for a bare number.
  final String nonce;
  final String name;
}

/// `claim_list`: the claims in [dir], a file named `<n>` or `<n>-<nonce>` (names starting with a dot are not listed, as
/// the shell's `*` does not match them; an entry that does not exist, such as a dangling link, is skipped).
List<_Listed> _listClaims(String dir) {
  final out = <_Listed>[];
  final List<FileSystemEntity> entries;
  try {
    entries = rawDirectory(dir).listSync(followLinks: false);
  } on FileSystemException {
    return out;
  }
  for (final e in entries) {
    final b = e.path.substring(e.path.lastIndexOf(RegExp(r'[\\/]')) + 1);
    if (b.startsWith('.')) continue;
    final dash = b.indexOf('-');
    final digits = dash < 0 ? b : b.substring(0, dash);
    final n = RegExp(r'^[0-9]+$').hasMatch(digits)
        ? int.tryParse(digits)
        : null;
    if (n == null ||
        FileSystemEntity.typeSync(e.path) == FileSystemEntityType.notFound) {
      continue;
    }
    out.add(_Listed(n, dash < 0 ? '-' : b.substring(dash + 1), b));
  }
  return out;
}

/// Bytewise order of two nonces (`[[ a > b ]]` compares by the locale's collation; C15 accepts the difference).
int _byBytes(String a, String b) {
  final x = encodeEscaped(a);
  final y = encodeEscaped(b);
  for (var i = 0; i < x.length && i < y.length; i++) {
    if (x[i] != y[i]) return x[i] - y[i];
  }
  return x.length - y.length;
}

/// One watcher's claim on a PR: a file `<n>-<nonce>` in the PR's claim directory. A new `--wait` takes the highest
/// number plus one and a nonce of its own, so no two claims share a name; claims order by number, then by nonce (bytes).
/// A new claim removes the lower ones, and a watcher owns the PR while its own file exists and no claim is above it.
class WatchClaim {
  WatchClaim._(this.dir, this.number, this.nonce);

  final String dir;
  final int number;
  final String nonce;

  /// The claim's file name.
  String get name => '$number-$nonce';

  String get _path => '$dir/$name';

  /// `claim_watch`: makes [dir] and the claim file (no clobber), then removes the lower claims. Null when the directory
  /// or the file cannot be created: the watcher polls unowned and the caller says so.
  static WatchClaim? claim(String dir, {Random? random, int? pid}) {
    try {
      rawDirectory(dir).createSync(recursive: true);
    } on FileSystemException {
      return null;
    }
    final top = _listClaims(dir).fold(0, (t, c) => max(t, c.number));
    final r = random ?? Random();
    String five() => r.nextInt(32768).toString().padLeft(5, '0');
    final claim = WatchClaim._(
      dir,
      top + 1,
      '${pid ?? io.pid}.${five()}${five()}',
    );
    try {
      rawFile(claim._path).createSync(exclusive: true);
    } on FileSystemException {
      return null;
    }
    for (final c in _listClaims(dir)) {
      if (c.name != claim.name && !claim.above(c.number, c.nonce)) {
        removeFile('$dir/${c.name}');
      }
    }
    return claim;
  }

  /// `claim_above`: is claim [n]-[otherNonce] above this one?
  bool above(int n, String otherNonce) =>
      n > number || (n == number && _byBytes(otherNonce, nonce) > 0);

  /// `still_owner`: the own file exists and no claim is above it.
  bool stillOwner() {
    if (!rawFile(_path).existsSync()) return false;
    for (final c in _listClaims(dir)) {
      if (c.name != name && above(c.number, c.nonce)) return false;
    }
    return true;
  }

  /// `release_watch`: removes the own file, by its unique name, and nothing else.
  void release() => removeFile(_path);
}

/// Where the first sighting of a head comes from.
class FirstSeen {
  FirstSeen(this.date, this.source);

  /// An HTTP date.
  final String date;

  /// `first_seen` (the record was published or read) or `first_seen_unsaved` (this process's own sighting).
  final String source;
}

final RegExp _httpDate = RegExp(
  r'^[A-Za-z]{3}, [0-9]{2} [A-Za-z]{3} [0-9]{4} [0-9:]{8} GMT$',
);

/// True when [text] is an HTTP date, as `prepare_cfg` checks the `Date` header.
bool isHttpDate(String text) => grepQuiet(_httpDate, text);

/// `resolve_first_seen`: the earliest GitHub time any snapshot on this machine saw head [oid], kept in `<[dir]>/<oid>`.
/// The record is written to a temp file from `mktemp` and published with a no-clobber `ln`, so the first writer wins and
/// nobody sees an empty record; publishing it removes the records of the PR's other heads. If it can be neither published
/// nor read (or does not parse), [firstSeen], this process's own sighting, is used (`first_seen_unsaved`).
Future<FirstSeen> resolveFirstSeen(
  PrContext ctx, {
  required String dir,
  required String oid,
  required String firstSeen,
}) async {
  final record = '$dir/$oid';
  final slashed = Platform.isWindows ? dir.replaceAll(r'\', '/') : dir;
  var seen = FirstSeen(firstSeen, 'first_seen_unsaved');
  var made = false;
  try {
    rawDirectory(dir).createSync(recursive: true);
    made = true;
  } on FileSystemException {
    // unsaved
  }
  final tmp = made ? await ctx.makeTemp('$slashed/.tmp.XXXXXX') : null;
  if (tmp != null) {
    if (_write(tmp, '$firstSeen\n') &&
        (await ctx.tool(['ln', tmp, '$slashed/$oid'])).exitCode == 0) {
      try {
        for (final e in rawDirectory(dir).listSync(followLinks: false)) {
          final b = e.path.substring(e.path.lastIndexOf(RegExp(r'[\\/]')) + 1);
          if (!b.startsWith('.') && b != oid) removeFile(e.path);
        }
      } on FileSystemException {
        // the other heads' records stay
      }
    }
    removeFile(tmp);
  }
  try {
    final d = firstLine(decodeEscaped(rawFile(record).readAsBytesSync()));
    if (isHttpDate(d)) seen = FirstSeen(d, 'first_seen');
  } on FileSystemException {
    // unsaved
  }
  return seen;
}

bool _write(String path, String text) {
  try {
    rawFile(path).writeAsBytesSync(encodeEscaped(text));
    return true;
  } on FileSystemException {
    return false;
  }
}
