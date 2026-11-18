// Reads the process's own argument list as the operating system holds it,
// so the entry can refuse an argument that is not well-formed Unicode
// (native-cli "Arguments sw cannot represent are refused", ADR 0040).
//
// The Dart runtime decodes argv before `main` runs and may replace what it
// cannot decode with U+FFFD, which then looks like a valid argument that
// holds U+FFFD. The raw list tells the two apart: /proc/self/cmdline on
// Linux, _NSGetArgv on macOS, GetCommandLineW on Windows.
import 'dart:convert';
import 'dart:ffi';
import 'dart:io';

import 'package:ffi/ffi.dart';

/// The 1-based position among [args] of the first argument that is not
/// well-formed Unicode as it reached the process, or null when every one is.
///
/// [args] are the arguments `main` received. When the raw list cannot be
/// read, or it does not end with as many entries as [args] holds, only [args]
/// themselves are checked (a lone surrogate in a Dart string).
int? firstUnrepresentableArgument(List<String> args) {
  for (var i = 0; i < args.length; i++) {
    if (hasLoneSurrogate(args[i])) return i + 1;
  }
  if (args.isEmpty) return null;
  final List<bool>? raw;
  try {
    raw = _rawWellFormed();
  } on Object {
    return null;
  }
  if (raw == null || raw.length < args.length) return null;
  final tail = raw.sublist(raw.length - args.length);
  for (var i = 0; i < tail.length; i++) {
    if (!tail[i]) return i + 1;
  }
  return null;
}

/// Whether [value] holds a UTF-16 surrogate that is not part of a pair.
bool hasLoneSurrogate(String value) {
  final units = value.codeUnits;
  for (var i = 0; i < units.length; i++) {
    final unit = units[i];
    if (unit >= 0xD800 && unit <= 0xDBFF) {
      if (i + 1 < units.length &&
          units[i + 1] >= 0xDC00 &&
          units[i + 1] <= 0xDFFF) {
        i++;
        continue;
      }
      return true;
    }
    if (unit >= 0xDC00 && unit <= 0xDFFF) return true;
  }
  return false;
}

/// Whether [bytes] are well-formed UTF-8.
bool isUtf8(List<int> bytes) {
  try {
    const Utf8Decoder(allowMalformed: false).convert(bytes);
    return true;
  } on FormatException {
    return false;
  }
}

/// For each raw argument after the program name, whether it is well-formed;
/// null on a platform with no raw source.
List<bool>? _rawWellFormed() {
  if (Platform.isLinux) return _linux();
  if (Platform.isMacOS) return _macos();
  if (Platform.isWindows) return _windows();
  return null;
}

List<bool> _linux() {
  final bytes = File('/proc/self/cmdline').readAsBytesSync();
  final entries = <List<int>>[];
  var start = 0;
  for (var i = 0; i < bytes.length; i++) {
    if (bytes[i] == 0) {
      entries.add(bytes.sublist(start, i));
      start = i + 1;
    }
  }
  if (start < bytes.length) entries.add(bytes.sublist(start));
  return [for (final entry in entries.skip(1)) isUtf8(entry)];
}

List<bool> _macos() {
  final library = DynamicLibrary.process();
  final argc = library
      .lookupFunction<Pointer<Int32> Function(), Pointer<Int32> Function()>(
        '_NSGetArgc',
      )()
      .value;
  final argv = library
      .lookupFunction<
        Pointer<Pointer<Pointer<Uint8>>> Function(),
        Pointer<Pointer<Pointer<Uint8>>> Function()
      >('_NSGetArgv')()
      .value;
  final result = <bool>[];
  for (var i = 1; i < argc; i++) {
    final entry = argv[i];
    var length = 0;
    while (entry[length] != 0) {
      length++;
    }
    result.add(isUtf8(entry.asTypedList(length)));
  }
  return result;
}

List<bool> _windows() {
  final kernel32 = DynamicLibrary.open('kernel32.dll');
  final shell32 = DynamicLibrary.open('shell32.dll');
  final commandLine = kernel32
      .lookupFunction<Pointer<Utf16> Function(), Pointer<Utf16> Function()>(
        'GetCommandLineW',
      )();
  final toArgv = shell32
      .lookupFunction<
        Pointer<Pointer<Uint16>> Function(Pointer<Utf16>, Pointer<Int32>),
        Pointer<Pointer<Uint16>> Function(Pointer<Utf16>, Pointer<Int32>)
      >('CommandLineToArgvW');
  final localFree = kernel32
      .lookupFunction<
        Pointer<Void> Function(Pointer<Void>),
        Pointer<Void> Function(Pointer<Void>)
      >('LocalFree');
  final count = calloc<Int32>();
  try {
    final argv = toArgv(commandLine, count);
    if (argv == nullptr) throw StateError('CommandLineToArgvW failed');
    try {
      final result = <bool>[];
      for (var i = 1; i < count.value; i++) {
        final entry = argv[i];
        var length = 0;
        while (entry[length] != 0) {
          length++;
        }
        result.add(
          !hasLoneSurrogate(String.fromCharCodes(entry.asTypedList(length))),
        );
      }
      return result;
    } finally {
      localFree(argv.cast());
    }
  } finally {
    calloc.free(count);
  }
}
