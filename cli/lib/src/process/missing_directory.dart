import 'dart:io';

/// Python's `repr()` of a `str`: single quotes unless the text holds `'` and
/// no `"`; backslash, the quote, newline, return, tab and other controls
/// escaped; a lone surrogate as a `u` escape.
String pyRepr(String s) {
  const bs = r'\';
  final quote = s.contains("'") && !s.contains('"') ? '"' : "'";
  final out = StringBuffer(quote);
  final units = s.codeUnits;
  for (var i = 0; i < units.length; i++) {
    final u = units[i];
    if (u == 0x5c) {
      out.write('$bs$bs');
    } else if (String.fromCharCode(u) == quote) {
      out.write('$bs$quote');
    } else if (u == 0x0a) {
      out.write('${bs}n');
    } else if (u == 0x0d) {
      out.write('${bs}r');
    } else if (u == 0x09) {
      out.write('${bs}t');
    } else if (u < 0x20 || u == 0x7f) {
      out.write('${bs}x${u.toRadixString(16).padLeft(2, '0')}');
    } else if (u >= 0xd800 && u <= 0xdbff) {
      final next = i + 1 < units.length ? units[i + 1] : 0;
      if (next >= 0xdc00 && next <= 0xdfff) {
        out
          ..writeCharCode(u)
          ..writeCharCode(next);
        i++;
      } else {
        out.write('${bs}u${u.toRadixString(16)}');
      }
    } else if (u >= 0xdc00 && u <= 0xdfff) {
      out.write('${bs}u${u.toRadixString(16)}');
    } else {
      out.writeCharCode(u);
    }
  }
  return (out..write(quote)).toString();
}

/// What Python's `str(OSError)` says when `Popen` is given a `cwd` that does
/// not name a directory: POSIX `[Errno 2] No such file or directory: '<dir>'`
/// (`[Errno 20] Not a directory` for a file), Windows `[WinError 267] The
/// directory name is invalid`.
String missingDirectoryText(String cwd, {bool? windows, bool isFile = false}) {
  if (windows ?? Platform.isWindows) {
    return '[WinError 267] The directory name is invalid';
  }
  return isFile
      ? '[Errno 20] Not a directory: ${pyRepr(cwd)}'
      : '[Errno 2] No such file or directory: ${pyRepr(cwd)}';
}
