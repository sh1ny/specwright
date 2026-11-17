import 'dart:convert';
import 'dart:io';

import 'package:path/path.dart' as p;

import '../commit/task_cover.dart' show isPySpace;

/// Text and path helpers for the `sw update` modules, each the one thing
/// `scripts/update.sh`'s Python helper did with `str.strip`, `Path.resolve`,
/// `Path.as_posix` and `json.dumps`.

/// Python's `str.strip()`: the characters `str.isspace` takes.
String pyStrip(String text) {
  var start = 0;
  var end = text.length;
  while (start < end && isPySpace(text.codeUnitAt(start))) {
    start++;
  }
  while (end > start && isPySpace(text.codeUnitAt(end - 1))) {
    end--;
  }
  return text.substring(start, end);
}

/// Python's `str.lstrip()`.
String pyLstrip(String text) {
  var start = 0;
  while (start < text.length && isPySpace(text.codeUnitAt(start))) {
    start++;
  }
  return text.substring(start);
}

/// [path] with forward slashes (a backslash separates only on Windows).
String posixPath(String path) =>
    Platform.isWindows ? path.replaceAll(r'\', '/') : path;

/// `Path(path).resolve()` as a forward-slash path: absolute, links followed,
/// `.` and `..` folded. A path that does not exist is made absolute and
/// normalised, as Python's non-strict `resolve` does.
String resolvePosix(String path) {
  try {
    return posixPath(Directory(path).resolveSymbolicLinksSync());
  } on FileSystemException {
    // fall through
  }
  return posixPath(p.normalize(p.absolute(path)));
}

/// True when [a] and [b] are the same path (case-insensitive on Windows).
bool samePath(String a, String b) => p.equals(a, b);

/// True when [path] is [top] or lies below it, by text (see [resolvePosix]).
bool pathWithin(String path, String top) =>
    p.equals(path, top) || p.isWithin(top, path);

/// `Path(path).relative_to(top).as_posix()`, or null when [path] is not below
/// [top].
String? relativeTo(String top, String path) {
  if (p.equals(path, top)) return '.';
  if (!p.isWithin(top, path)) return null;
  return posixPath(p.relative(path, from: top));
}

/// Text from bytes as Python's `bytes.decode('utf-8', 'replace')`.
String decodeLossy(List<int> bytes) => utf8.decode(bytes, allowMalformed: true);

/// `json.dumps(value)`: Python's default form, with `, ` and `: ` separators
/// and every non-ASCII character escaped.
String jsonDumps(Object? value) {
  switch (value) {
    case null:
      return 'null';
    case bool b:
      return b ? 'true' : 'false';
    case num n:
      return '$n';
    case String s:
      return _asciiString(s);
    case List<Object?> l:
      return '[${l.map(jsonDumps).join(', ')}]';
    case Map<Object?, Object?> m:
      return '{${m.entries.map((e) => '${_asciiString('${e.key}')}: ${jsonDumps(e.value)}').join(', ')}}';
  }
  throw ArgumentError('not JSON: ${value.runtimeType}');
}

String _asciiString(String s) {
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
        if (unit < 0x20 || unit > 0x7e) {
          out.write('\\u${unit.toRadixString(16).padLeft(4, '0')}');
        } else {
          out.writeCharCode(unit);
        }
    }
  }
  return (out..write('"')).toString();
}
