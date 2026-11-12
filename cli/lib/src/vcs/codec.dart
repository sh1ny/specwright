import 'dart:typed_data';

/// The NUL-terminated records of a handoff, each decoded strictly (D4): the
/// scripts directory, the bash path, then the arguments of the call. A record
/// that is not UTF-8 throws [NotUtf8] naming `scripts directory`, `bash path`
/// or `argument N`. Bytes after the last NUL are ignored: the callers check
/// that the input ends in one.
List<String> decodeHandoffRecords(Uint8List bytes) {
  final records = <String>[];
  var start = 0;
  for (var i = 0; i < bytes.length; i++) {
    if (bytes[i] == 0) {
      final what = switch (records.length) {
        0 => 'scripts directory',
        1 => 'bash path',
        _ => 'argument ${records.length - 1}',
      };
      records.add(decodeStrict(Uint8List.sublistView(bytes, start, i), what));
      start = i + 1;
    }
  }
  return records;
}

/// Display text from a tool: [decodeReplacing], then `\r\n` and a lone `\r`
/// become `\n` (Python's universal newlines).
String decodeText(List<int> bytes) =>
    decodeReplacing(bytes).replaceAll('\r\n', '\n').replaceAll('\r', '\n');

/// Output of `but`, as `vcs.sh` reads it: invalid bytes become U+FFFD, one per
/// maximal invalid subpart as Python's `errors='replace'` does, and newlines
/// are left alone.
String decodeReplacing(List<int> bytes) =>
    _decode(bytes, (units, run) => units.add(0xfffd));

/// A name or path that `sw` acts on or reports as a path was not valid UTF-8.
/// [what] says which name it was; [shown] is the name as it is reported: each
/// invalid byte as `\xHH`, or already rendered by the caller (a directory walk
/// shows U+FFFD).
class NotUtf8 implements Exception {
  NotUtf8(this.what, this.shown);

  final String what;
  final String shown;

  /// For a JSON document's `message` field and for the terminal.
  String get message => '$what is not valid UTF-8: $shown';

  @override
  String toString() => 'NotUtf8: $message';
}

/// A name or path that `sw` acts on or reports as a path is decoded strictly.
/// Display text is decoded with replacement.
///
/// Returns the decoded string, or throws [NotUtf8] naming [what] and showing
/// each invalid byte as `\xHH` in uppercase hex.
String decodeStrict(List<int> bytes, String what) {
  var valid = true;
  final shown = _decode(bytes, (units, run) {
    valid = false;
    for (final b in run) {
      final hex = b.toRadixString(16).toUpperCase().padLeft(2, '0');
      units.addAll('\\x$hex'.codeUnits);
    }
  });
  if (!valid) throw NotUtf8(what, shown);
  return shown;
}

String _decode(
  List<int> b,
  void Function(List<int> units, List<int> invalidRun) onInvalid,
) {
  final units = <int>[];
  final n = b.length;
  var i = 0;
  while (i < n) {
    final b0 = b[i];
    if (b0 < 0x80) {
      units.add(b0);
      i++;
      continue;
    }
    int need;
    var lo = 0x80;
    var hi = 0xbf;
    if (b0 >= 0xc2 && b0 <= 0xdf) {
      need = 1;
    } else if (b0 >= 0xe0 && b0 <= 0xef) {
      need = 2;
      if (b0 == 0xe0) lo = 0xa0;
      if (b0 == 0xed) hi = 0x9f;
    } else if (b0 >= 0xf0 && b0 <= 0xf4) {
      need = 3;
      if (b0 == 0xf0) lo = 0x90;
      if (b0 == 0xf4) hi = 0x8f;
    } else {
      onInvalid(units, [b0]);
      i++;
      continue;
    }
    var cp = b0 & (0x3f >> need);
    var k = 1;
    for (; k <= need; k++) {
      if (i + k >= n) break;
      final c = b[i + k];
      if (c < (k == 1 ? lo : 0x80) || c > (k == 1 ? hi : 0xbf)) break;
      cp = (cp << 6) | (c & 0x3f);
    }
    if (k <= need) {
      onInvalid(units, b.sublist(i, i + k));
      i += k;
      continue;
    }
    if (cp >= 0x10000) {
      units
        ..add(0xd800 + ((cp - 0x10000) >> 10))
        ..add(0xdc00 + ((cp - 0x10000) & 0x3ff));
    } else {
      units.add(cp);
    }
    i += need + 1;
  }
  return String.fromCharCodes(units);
}
