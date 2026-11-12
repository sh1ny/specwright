import '../options.dart';
import '../vcs/codec.dart' show NotUtf8;
import '../vcs/document.dart';
import '../vcs/stop.dart';
import 'context.dart';

// What the five `pr-pair.sh` subcommands that moved to `sw pr` share (design D1): the script's stop, its flag reader and
// the one place that prints an answer and turns an unexpected exception into `internal_error`.

/// `Stop` of `pr-pair.sh`: an error code, a message, an exit status and extra fields. Printed as
/// `{ok: false, error, message, ...extra}`.
class PairStop implements Exception {
  PairStop(this.error, this.message, {this.code = 1, this.extra = const {}});

  final String error;
  final String message;
  final int code;
  final Map<String, Object?> extra;

  Map<String, Object?> toJson() => {
    'ok': false,
    'error': error,
    'message': message,
    ...extra,
  };

  @override
  String toString() => '$error: $message';
}

/// `usage(msg)`: exit 2.
Never pairUsage(String message) => throw PairStop('usage', message, code: 2);

/// What `parse_args` read: flags with one value ([values]), repeated flags ([lists], the spec's `+dest`) and the
/// words that are not flags.
class PairArgs {
  final Map<String, String> values = {};
  final Map<String, List<String>> lists = {};
  final List<String> positional = [];

  /// `a.get(name)`.
  String? operator [](String name) => values[name];
}

/// `parse_args(argv, spec)` under the one option rule (`options.dart`): [spec] maps `--flag` to its destination, and a
/// destination starting with `+` collects every value. An unknown, abbreviated or single-dash word is a usage stop; so is
/// a flag without a value. The words that are not options are [PairArgs.positional].
PairArgs parsePairArgs(List<String> argv, Map<String, String> spec) {
  String name(String flag) => flag.substring(2);
  final parsed = parseOptions(
    argv,
    values: [
      for (final e in spec.entries)
        if (!e.value.startsWith('+')) name(e.key),
    ],
    lists: [
      for (final e in spec.entries)
        if (e.value.startsWith('+')) name(e.key),
    ],
    usage: pairUsage,
  );
  final a = PairArgs();
  for (final e in spec.entries) {
    final option = name(e.key);
    if (!parsed.wasParsed(option)) continue;
    if (e.value.startsWith('+')) {
      a.lists[e.value.substring(1)] = parsed.multiOption(option);
    } else {
      a.values[e.value] = parsed.option(option)!;
    }
  }
  a.positional.addAll(parsed.rest);
  return a;
}

/// `need(a, *names)`: a missing or empty value is a usage stop.
void needArgs(PairArgs a, List<String> names) {
  for (final n in names) {
    final v = a.values[n];
    if (v == null || v.isEmpty) {
      pairUsage('missing --${n.replaceAll('_', '-')}');
    }
  }
}

/// Runs a subcommand's [body] and prints its answer: one JSON line, exit 0. A [PairStop] prints its object with its exit
/// status; anything else is `internal_error` with the exception's type and text, exit 1, and never a stack trace.
Future<int> runPairCommand(
  PrContext ctx,
  Future<Map<String, Object?>> Function() body,
) async {
  Map<String, Object?> answer;
  int code = 0;
  try {
    answer = await body();
  } on PairStop catch (e) {
    answer = e.toJson();
    code = e.code;
  } on NotUtf8 catch (e) {
    // D4: a path or name a git read printed is not UTF-8: refused by name, exit 1
    answer = VcsStop.notUtf8(e).object();
    code = 1;
  } on Object catch (e) {
    answer = {
      'ok': false,
      'error': 'internal_error',
      'message': '${e.runtimeType}: $e',
    };
    code = 1;
  }
  try {
    ctx.writeOut(documentBytes(answer));
  } on Object catch (e) {
    // a value the document cannot hold: still one JSON line
    ctx.writeOut(
      documentBytes({
        'ok': false,
        'error': 'internal_error',
        'message': '${e.runtimeType}: $e',
      }),
    );
    return 1;
  }
  return code;
}
