import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import '../process/limits.dart';

/// Every JSON input the CLI reads is refused through this one type. [message] starts with `<file>: ` when the source is
/// a file, so a caller that prints it names the file.
class JsonInputException extends FormatException {
  JsonInputException(super.message);
}

/// C4: the one JSON reader. `jsonDecode` refuses `NaN`, `Infinity` and `-Infinity`, and a byte-order mark; it keeps the
/// last of two duplicate keys and a lone surrogate escape as written; it reads an integer past 64 bits as a `double`,
/// so a caller that needs an exact integer checks `is int`. It keeps its own stack, so nesting depth needs no limit
/// here: the size bound of [readJsonFile] is the protection, and a `StackOverflowError` is mapped to the same stop in
/// case a later SDK recurses. [file] names the source in the refusal's message.
Object? decodeJson(String text, {String file = ''}) {
  final prefix = file.isEmpty ? '' : '$file: ';
  try {
    return jsonDecode(text);
  } on FormatException catch (e) {
    final at = e.offset == null ? '' : ' (char ${e.offset})';
    throw JsonInputException('${prefix}not valid JSON: ${e.message}$at');
  } on StackOverflowError {
    throw JsonInputException('${prefix}not valid JSON: nested too deeply');
  }
}

/// [bytes], the content of [file], as strict UTF-8 text. A byte-order mark is kept in the text, so it is refused as
/// invalid JSON.
String decodeJsonBytes(List<int> bytes, String file) {
  try {
    final bom =
        bytes.length >= 3 &&
        bytes[0] == 0xef &&
        bytes[1] == 0xbb &&
        bytes[2] == 0xbf;
    final body = utf8.decode(bom ? bytes.sublist(3) : bytes);
    return bom ? '\u{feff}$body' : body;
  } on FormatException catch (e) {
    throw JsonInputException('$file: not valid UTF-8: ${e.message}');
  }
}

/// C10: reads the JSON file at [path], the raw path a caller was given. The read takes at most [defaultMaxBytes] (32
/// MiB) plus one byte, and a longer file is `<path>: larger than 32 MiB` without being read whole. Bytes that are not
/// UTF-8, a document that is not JSON and a file that cannot be read each stop with a [JsonInputException] whose
/// message starts with `<path>: `.
Object? readJsonFile(String path) =>
    decodeJson(decodeJsonBytes(readBounded(path), path), file: path);

/// The bytes of [path], at most [limit] of them; a file over the limit is a [JsonInputException] naming [path] (the
/// file is never read whole).
List<int> readBounded(String path, {int limit = defaultMaxBytes}) {
  final Uint8List bytes;
  try {
    final file = File(path).openSync();
    try {
      bytes = file.readSync(limit + 1);
    } finally {
      file.closeSync();
    }
  } on FileSystemException catch (e) {
    final os = e.osError?.message.trim();
    throw JsonInputException(
      '$path: cannot read: ${os == null || os.isEmpty ? e.message : os}',
    );
  }
  if (bytes.length > limit) {
    throw JsonInputException(
      '$path: larger than ${limit ~/ (1024 * 1024)} MiB',
    );
  }
  return bytes;
}

/// The text of [value] as compact JSON: no space after `,` or `:`, keys in insertion order, non-ASCII text raw, and
/// only `"`, `\` and the controls below U+0020 escaped. Consumers parse documents and never match their text, so the
/// raw U+2028 and U+2029 are legal (`sw pr snapshot` parses the documents it reads, so no reader depends on this form).
///
/// `JsonEncoder` writes a lone surrogate as the six-character escape `\udXXX` (A3 of native-cli-library-foundations
/// found this). The encoder's own escapes of lone surrogates are turned back into the unit, so a caller that digests
/// the text (`reviewerConfigBytes`) sees the unit; text a caller wrote with a backslash is escaped by the encoder
/// (`\\`) and is left alone. A value JSON cannot hold (`NaN`, `Infinity`, a `BigInt`, a key that is not a string, an
/// unknown object) throws a `JsonUnsupportedObjectError`.
String documentText(Object? value) {
  final text = const JsonEncoder().convert(value);
  return text.contains(r'\ud') ? _restoreLoneSurrogates(text) : text;
}

String _restoreLoneSurrogates(String text) {
  final out = StringBuffer();
  var i = 0;
  while (i < text.length) {
    final c = text.codeUnitAt(i);
    if (c != 0x5c) {
      out.writeCharCode(c);
      i++;
      continue;
    }
    // an escape: `\u` and four hex digits, or a backslash and one more character
    if (i + 5 < text.length && text.codeUnitAt(i + 1) == 0x75) {
      final unit = int.tryParse(text.substring(i + 2, i + 6), radix: 16);
      if (unit != null && unit >= 0xd800 && unit <= 0xdfff) {
        out.writeCharCode(unit);
        i += 6;
        continue;
      }
    }
    out.write(text.substring(i, i + 2));
    i += 2;
  }
  return out.toString();
}

/// C3: the bytes `sw` writes to stdout for [value]: [documentText] as UTF-8, then one LF on every platform. A lone
/// surrogate is a `FormatException`, as Python fails to encode it: a name that is not UTF-8 never reaches a document,
/// because names are decoded strictly (D4).
Uint8List documentBytes(Object? value) {
  final text = '${documentText(value)}\n';
  final units = text.codeUnits;
  for (var i = 0; i < units.length; i++) {
    final u = units[i];
    final high = u >= 0xd800 && u <= 0xdbff;
    if (high &&
        i + 1 < units.length &&
        units[i + 1] >= 0xdc00 &&
        units[i + 1] <= 0xdfff) {
      i++;
    } else if (u >= 0xd800 && u <= 0xdfff) {
      throw FormatException('lone surrogate U+${u.toRadixString(16)}');
    }
  }
  return Uint8List.fromList(utf8.encode(text));
}
