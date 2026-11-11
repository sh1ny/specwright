import 'dart:io';
import 'dart:typed_data';

import '../process/bounded_run.dart';
import '../process/limit_line.dart';
import '../process/limits.dart';
import '../process/platform_tree.dart';
import '../vcs/codec.dart';

/// What one bounded `gh` (or `sw pr reviewers`) call ended in. Without a [limit],
/// the output and [exitCode] are the command's own; a call that could not
/// start is exit 127 with the reason on [stderr].
class GhResult {
  GhResult({
    required this.exitCode,
    this.limit,
    this.limitLine,
    required this.stdout,
    required this.stderr,
  });

  final int exitCode;

  /// The limit that ended the call, if one did.
  final BoundedLimit? limit;

  /// `bounded: <limit>: <command> <first argument>\n` when [limit] is set.
  final String? limitLine;
  final Uint8List stdout;
  final Uint8List stderr;
}

// The bash argument transport the bounded calls still use. Task 5.2 of
// `native-cli-launcher` replaces it with a direct start and deletes this block.

/// Shell text put in front of `exec "$@"` in the transported `bash -c`.
///
/// It reads the working directory record, then the argument count (decimal
/// digits, NUL-terminated) and exactly that many NUL-terminated records, one
/// `read -r -d ''` at a time into the positional list, and leaves the rest of
/// stdin unread for the exec'd tool. A missing directory record, a count that
/// is not decimal digits (or is zero, or is longer than nine digits) and fewer
/// records than the count exit 126 before any tool runs. No argument value is
/// reserved. Last it enters the directory with `CDPATH= cd -- "$dir"` (an
/// empty `CDPATH` for `cd` only, so a drive-form path is never searched
/// through it, and nothing is printed); a directory that vanished exits 127,
/// silently.
///
/// The records are read with `LC_ALL=C`, and `LC_ALL` is restored (or unset)
/// before the tool runs: in a UTF-8 locale bash's `read` takes a lead byte at
/// the end of a record (`\xe9` then NUL) as the start of a character and
/// swallows the NUL that ends the record.
const String _prelude =
    r'''__lcs=${LC_ALL+x}; __lc=${LC_ALL-}; LC_ALL=C; __d=; IFS= read -r -d '' __d || { echo "vcs: argument transport failed" >&2; exit 126; }; __c=; IFS= read -r -d '' __c || __c=x; case $__c in ''|*[!0-9]*|0*) echo "vcs: argument transport failed" >&2; exit 126;; esac; [ "${#__c}" -le 9 ] || { echo "vcs: argument transport failed" >&2; exit 126; }; set --; __i=0; while [ "$__i" -lt "$__c" ]; do IFS= read -r -d '' __a || { echo "vcs: argument transport failed" >&2; exit 126; }; set -- "$@" "$__a"; __i=$((__i+1)); done; if [ -n "$__lcs" ]; then LC_ALL=$__lc; else unset LC_ALL; fi; CDPATH= cd -- "$__d" >/dev/null 2>&1 || exit 127; unset __d __c __i __a __lc __lcs''';

/// [_prelude] with the `bounded:` message prefix `sw run --bounded` printed.
final String boundedPrelude = _prelude.replaceAll(
  'vcs: argument transport failed',
  'bounded: argument transport failed',
);

/// The working directory as the transport's first record: absolute, and on
/// Windows in its drive form with `/` separators (`C:/Users/x`).
String _cwdRecord(String cwd, {bool? windows}) =>
    (windows ?? Platform.isWindows) ? cwd.replaceAll(r'\', '/') : cwd;

/// The argument records: the count of [command] entries in decimal, then each
/// entry, every record followed by a NUL. Encoded with surrogateescape
/// ([encodeEscaped]).
Uint8List _frameArguments(List<String> command) {
  final out = BytesBuilder(copy: false);
  _record(out, '${command.length}');
  for (final c in command) {
    _record(out, c);
  }
  return out.takeBytes();
}

/// Everything the child reads ahead of any tool input: the working directory
/// record ([_cwdRecord]), then [_frameArguments].
Uint8List _frameCommand(String cwd, List<String> command) {
  final out = BytesBuilder(copy: false)
    ..add(_recordBytes(_cwdRecord(cwd)))
    ..add(_frameArguments(command));
  return out.takeBytes();
}

void _record(BytesBuilder out, String text) => out.add(_recordBytes(text));

Uint8List _recordBytes(String text) {
  final bytes = encodeEscaped(text);
  if (bytes.contains(0)) {
    throw ArgumentError('a transported record cannot hold a NUL byte');
  }
  return Uint8List.fromList([...bytes, 0]);
}

/// Runs `gh <args>` in [cwd] under the bounded helper: a deadline, a byte bound
/// on each stream and a stop of the whole process tree.
///
/// Constraint C16: `gh` and `sw pr reviewers` arguments reach the command only as
/// escaped records on stdin, never through Dart's process arguments. The helper
/// starts `bash -c '<prelude>; exec "$@"'`, which reads the working directory
/// and the argument records the parent sends after the go byte, so on every OS
/// MSYS never expands them and on POSIX an escaped byte keeps its value.
///
/// [environment] is the whole environment of the call (see
/// [BoundedRun.environment]); null keeps `sw`'s own. [paged] picks the longer
/// paged deadline. [limits] overrides the resolved ones, and [helperCommand] the
/// helper's command line (tests run it from source).
Future<GhResult> runGh(
  String bash,
  String cwd,
  List<String> args, {
  Map<String, String>? environment,
  bool paged = false,
  RunLimits? limits,
  List<String>? helperCommand,
}) => _run(
  bash,
  'gh',
  _frameCommand(cwd, ['gh', ...args]),
  ['gh', ...args],
  environment: environment,
  paged: paged,
  limits: limits,
  helperCommand: helperCommand,
);

/// [runGh] with the bytes sent on stdin given as they are, so a test can send
/// a bad count or a short read.
Future<GhResult> runGhFramed(
  String bash,
  List<int> stdinBytes, {
  Map<String, String>? environment,
  RunLimits? limits,
  List<String>? helperCommand,
}) => _run(
  bash,
  'gh',
  stdinBytes,
  const ['gh'],
  environment: environment,
  paged: false,
  limits: limits,
  helperCommand: helperCommand,
);

/// Runs `sw pr reviewers <args>` the same way (the caller's [command] starts with
/// the `sw` executable).
Future<GhResult> runBoundedCommand(
  String bash,
  String cwd,
  List<String> command, {
  Map<String, String>? environment,
  bool paged = false,
  RunLimits? limits,
  List<String>? helperCommand,
}) => _run(
  bash,
  command.first,
  _frameCommand(cwd, command),
  command,
  environment: environment,
  paged: paged,
  limits: limits,
  helperCommand: helperCommand,
);

Future<GhResult> _run(
  String bash,
  String name,
  List<int> stdinBytes,
  List<String> logical, {
  required Map<String, String>? environment,
  required bool paged,
  required RunLimits? limits,
  required List<String>? helperCommand,
}) async {
  final result = await BoundedRun(
    command: [bash, '-c', '$boundedPrelude; exec "\$@"', name],
    stdinBytes: stdinBytes,
    environment: environment,
    // the scripts' `gh()` passed `--paged` whenever SW_PAGED was set, too
    limits:
        limits ??
        resolveLimits(
          _platformEnv(environment),
          paged:
              paged || (_platformEnv(environment)['SW_PAGED'] ?? '').isNotEmpty,
        ),
    helperCommand: helperCommand,
    treeFor: () => platformTree(environment ?? _platformEnv(null)),
    note: (_) {},
  ).run();
  final limit = result.limit;
  if (limit != null) {
    return GhResult(
      exitCode: limit.exitCode,
      limit: limit,
      limitLine: limitLine(limit, [bash, '-c', 'exec "\$@"', ...logical]),
      stdout: Uint8List(0),
      stderr: Uint8List(0),
    );
  }
  if (result.helperExited) {
    return GhResult(
      exitCode: 127,
      stdout: Uint8List(0),
      stderr: encodeEscaped(
        'bounded: helper exited during startup: ${commandLabel(logical)}\n',
      ),
    );
  }
  final startError = result.startError;
  if (startError != null) {
    return GhResult(
      exitCode: 127,
      stdout: Uint8List(0),
      stderr: encodeEscaped(
        'bounded: cannot start ${logical.first}: $startError\n',
      ),
    );
  }
  return GhResult(
    exitCode: result.exitCode ?? 127,
    stdout: Uint8List.fromList(result.stdout),
    stderr: Uint8List.fromList(result.stderr),
  );
}

Map<String, String> _platformEnv(Map<String, String>? given) =>
    given ?? Platform.environment;
