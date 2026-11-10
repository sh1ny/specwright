import 'package:args/args.dart';

// The one option rule of `sw vcs`, `sw finish` and `sw pr` (design D3), over `ArgParser`: `--name value` and `--name=value`;
// the next word is the value whatever it looks like (`--` and `--force` included); a repeated option keeps its last value,
// a list option every value, unsplit; a flag takes no value and has no `--no-` form; no abbreviations; no `-x` words.
// What an option word cannot be (unknown, abbreviated, single-dash, missing its value) goes to the command's own `usage`
// stop through [parseOptions]'s callback, so each command keeps its stop type and its document.

/// Parses [argv] against the option names given without their `--`: [values] take one value, [lists] collect every value,
/// [flags] take none. Words that are not options, and everything after a `--` that is not an option's value, are
/// `rest`; the caller decides whether `rest` is allowed. A parse failure calls [usage] with its message.
ArgResults parseOptions(
  List<String> argv, {
  Iterable<String> values = const [],
  Iterable<String> lists = const [],
  Iterable<String> flags = const [],
  required Never Function(String message) usage,
}) {
  final parser = ArgParser();
  for (final name in values) {
    parser.addOption(name);
  }
  for (final name in lists) {
    parser.addMultiOption(name, splitCommas: false);
  }
  for (final name in flags) {
    parser.addFlag(name, negatable: false);
  }
  try {
    return parser.parse(argv);
  } on FormatException catch (e) {
    usage(e.message);
  }
}
