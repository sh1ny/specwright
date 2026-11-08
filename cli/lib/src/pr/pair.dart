import '../vcs/document.dart';
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

/// `parse_args(argv, spec)`: [spec] maps a flag to its destination, and a destination starting with `+` collects every
/// value. An unknown `--` word is a usage stop; a flag without a value too.
PairArgs parsePairArgs(List<String> argv, Map<String, String> spec) {
  final a = PairArgs();
  var i = 0;
  while (i < argv.length) {
    final t = argv[i];
    final dest = spec[t];
    if (dest != null) {
      if (i + 1 >= argv.length) pairUsage('$t needs a value');
      final v = argv[i + 1];
      i += 2;
      if (dest.startsWith('+')) {
        (a.lists[dest.substring(1)] ??= []).add(v);
      } else {
        a.values[dest] = v;
      }
    } else if (t.startsWith('--')) {
      pairUsage('unknown option $t');
    } else {
      a.positional.add(t);
      i++;
    }
  }
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
