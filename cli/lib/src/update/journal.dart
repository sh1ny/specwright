import 'dart:io';

import '../vcs/document.dart' show decodeJson, decodeJsonBytes, readBounded;
import 'file_ops.dart';

/// The journal cannot be read: its text is not JSON (trailing text included),
/// or it is not a format 1 or 2 object. Reported as `journal_unreadable`.
class JournalUnreadable implements Exception {
  JournalUnreadable(this.message);

  final String message;

  String get code => 'journal_unreadable';

  @override
  String toString() => message;
}

/// The update journal, `openspec/.specwright/update.json` (design D2 of
/// native-cli-update): format 2, byte-compatible with what `scripts/update.sh`
/// writes, and format 1 is still read. The members stay a map in their file
/// order; later task groups read and change them by name.
///
/// The fields are those of `scripts/update.sh`'s header: format, from, to,
/// ref, kind, role, code, root, inflight, owner_id, store_owner,
/// store_version, store_record, store_lock, store_staging, store_state, token,
/// prev_config, prev_store, config_sha, prev_packs, phase, then the lists
/// groups, targets and manifest.
class Journal {
  Journal(this.data);

  /// Reads [text] as the journal. Throws [JournalUnreadable] for text that is
  /// not one JSON document (anything after the document is garbage), and for
  /// a document that is not an object whose `format` is 1 or 2.
  factory Journal.parse(String text) {
    final Object? decoded;
    try {
      decoded = decodeJson(text);
    } on FormatException catch (e) {
      throw JournalUnreadable('update.json is not readable JSON (${_why(e)})');
    }
    final format = decoded is Map ? decoded['format'] : null;
    if (decoded is! Map ||
        format is bool ||
        format is! num ||
        (format != 1 && format != 2)) {
      throw JournalUnreadable(
        'update.json has format ${_repr(format)}, not 1 or 2',
      );
    }
    return Journal(Map<String, Object?>.from(decoded));
  }

  /// The members, in file order.
  final Map<String, Object?> data;

  int get format => (data['format'] as num).toInt();

  /// The journal text as `update.sh`'s `format_journal` writes it: the scalar
  /// members one per line, then `groups`, `targets` and `manifest` with one
  /// entry per line, values as Python's `json.dumps` writes them (`, ` and
  /// `: ` separators, text kept as it is), and one LF at the end.
  String toText() {
    const lists = ['groups', 'targets', 'manifest'];
    final lines = <String>['{'];
    for (final entry in data.entries) {
      if (lists.contains(entry.key)) continue;
      lines.add('  ${_dump(entry.key)}: ${_dump(entry.value)},');
    }
    for (final key in lists) {
      final entries = (data[key] as List?) ?? const [];
      lines.add('  "$key": [');
      lines.add([for (final e in entries) '    ${_dump(e)}'].join(',\n'));
      lines.add('  ]${key == lists.last ? '' : ','}');
    }
    lines.add('}');
    return '${lines.join('\n')}\n';
  }
}

/// The journal file of one code checkout, `update.json`, and its temporary
/// `update.json.tmp` in [stateDir] (`<code>/openspec/.specwright`).
class JournalFile {
  JournalFile(this.stateDir, this._ops);

  final String stateDir;
  final UpdateFileOps _ops;

  String get path => '$stateDir/update.json';

  String get tempPath => '$stateDir/update.json.tmp';

  /// The journal, or null when there is no file. Throws [JournalUnreadable].
  Journal? read() {
    if (!File(path).existsSync()) return null;
    try {
      return Journal.parse(decodeJsonBytes(readBounded(path), path));
    } on JournalUnreadable {
      rethrow;
    } on FormatException catch (e) {
      throw JournalUnreadable('update.json is not readable JSON (${_why(e)})');
    }
  }

  /// Writes [journal] atomically: its text goes to `update.json.tmp`, and
  /// the rename onto `update.json` is the counted file operation, as the
  /// shell's external `mv` was. A run killed between the two leaves the
  /// previous journal and the temporary file.
  void write(Journal journal) {
    File(tempPath).writeAsStringSync(journal.toText(), flush: true);
    _ops.rename(tempPath, path);
  }
}

String _why(FormatException e) {
  final message = e.message;
  final prefix = RegExp(r'^(?:.*?: )?not valid JSON: ').firstMatch(message);
  return prefix == null ? message : message.substring(prefix.end);
}

/// Python's `repr` of a JSON value, for the format message.
String _repr(Object? value) => switch (value) {
  null => 'None',
  true => 'True',
  false => 'False',
  String s => "'${s.replaceAll(r'\', r'\\').replaceAll("'", r"\'")}'",
  _ => '$value',
};

/// `json.dumps(value, ensure_ascii=False)`.
String _dump(Object? value) {
  switch (value) {
    case null:
      return 'null';
    case bool b:
      return b ? 'true' : 'false';
    case num n:
      return '$n';
    case String s:
      return _string(s);
    case List<Object?> l:
      return '[${l.map(_dump).join(', ')}]';
    case Map<Object?, Object?> m:
      return '{${m.entries.map((e) => '${_string('${e.key}')}: ${_dump(e.value)}').join(', ')}}';
  }
  throw ArgumentError('not JSON: ${value.runtimeType}');
}

String _string(String s) {
  final out = StringBuffer('"');
  for (final unit in s.codeUnits) {
    switch (unit) {
      case 0x22:
        out.write(r'\"');
      case 0x5c:
        out.write(r'\\');
      case 0x0a:
        out.write(r'\n');
      case 0x0d:
        out.write(r'\r');
      case 0x09:
        out.write(r'\t');
      case 0x08:
        out.write(r'\b');
      case 0x0c:
        out.write(r'\f');
      default:
        if (unit < 0x20) {
          out.write('\\u${unit.toRadixString(16).padLeft(4, '0')}');
        } else {
          out.writeCharCode(unit);
        }
    }
  }
  return (out..write('"')).toString();
}
