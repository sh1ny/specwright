import 'dart:io';

// Windows command-line arithmetic for the tests of the line checks (D5).
//
// Written from the documented `CommandLineToArgvW` quoting rules and kept
// apart from `lib/`, so a boundary test never computes its expectation with
// the code it tests.

/// Units one argument takes on a Windows command line: its own length when it
/// is non-empty and holds no space, tab or quote; otherwise two quotes around
/// it, a quote escaped by a backslash, and the backslashes before a quote (or
/// before the closing quote) doubled.
int quotedUnits(String arg) {
  if (arg.isNotEmpty && !RegExp(r'[ \t"]').hasMatch(arg)) return arg.length;
  var units = 2;
  var slashes = 0;
  for (final unit in arg.codeUnits) {
    if (unit == 0x5c) {
      slashes++;
      continue;
    }
    units += unit == 0x22 ? slashes * 2 + 2 : slashes + 1;
    slashes = 0;
  }
  return units + slashes * 2;
}

/// Units of the whole command line for [argv]: each argument quoted, one space
/// between them, no terminating NUL.
int lineUnits(List<String> argv) =>
    argv.map(quotedUnits).fold<int>(0, (a, b) => a + b) + argv.length - 1;

/// A plain ASCII argument (no quoting) that makes [prefix] followed by it a
/// line of exactly [units] units.
String fillTo(List<String> prefix, int units) {
  final n = units - lineUnits([...prefix, 'x']) + 1;
  if (n < 1) throw StateError('prefix already takes more than $units units');
  return 'x' * n;
}

/// This process's environment with [extra] on top, matching names without
/// regard to case: a plain map keeps `Path` and `PATH` apart, and a lookup
/// that takes the first match would read the inherited one.
Map<String, String> withEnv(Map<String, String> extra) {
  final names = {for (final k in extra.keys) k.toUpperCase()};
  return {
    for (final e in Platform.environment.entries)
      if (!names.contains(e.key.toUpperCase())) e.key: e.value,
    ...extra,
  };
}
