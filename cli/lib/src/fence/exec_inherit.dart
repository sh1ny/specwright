import 'dart:async';
import 'dart:io';
import 'dart:typed_data';

import '../vcs/codec.dart';

/// The last record of the fenced-arguments file: the prelude runs nothing when
/// the last record it read is not this, so a missing or cut-off file is caught.
const String fencedEnd = '--sw-end--';

/// Constraint C11: the fence's bash prelude runs on bash 3.2, the `/bin/bash`
/// of macOS: no `mapfile` and no bash 4 expansion. It reads the NUL-terminated
/// records of the file `$1` into an array with `read -r -d ''` and `+=`, checks
/// that the last one is [fencedEnd] and drops it, removes the file and its
/// directory, and runs the rest with `exec`. The file is read through a
/// redirection, so the command's own stdin is left alone. A missing, unreadable
/// or cut-off file exits 126 with `as.sh: handoff: malformed` and runs nothing.
const String fencedPrelude =
    r'''__f=$1; __a=(); while IFS= read -r -d '' __x; do __a+=("$__x"); done < "$__f" || { echo "as.sh: handoff: malformed" >&2; exit 126; }; __n=${#__a[@]}; if [ "$__n" -lt 2 ] || [ "${__a[__n-1]}" != --sw-end-- ]; then echo "as.sh: handoff: malformed" >&2; exit 126; fi; unset "__a[__n-1]"; rm -f -- "$__f"; rmdir -- "${__f%/*}" 2>/dev/null; exec "${__a[@]}"''';

/// Constraint C2: the fenced command runs through bash's own lookup, `exec` in
/// [fencedPrelude], and never through `resolveCommand`, so an extensionless
/// script on Windows is found, a shell function is not, `PATH` order decides,
/// and a missing command ends 127 with its name on stderr, as `exec "$@"` in
/// `as.sh` did.
///
/// The arguments travel as records in a file inside a private directory made
/// under [tempRoot] (the system temp directory), never on `bash`'s command
/// line, so every byte arrives. `bash` starts with `sw`'s own stdin, stdout and
/// stderr, the whole of [environment] and nothing of `sw`'s own, in the
/// directory `sw` is in. The returned status is the command's; a command ended
/// by signal N gives 128+N (Dart reports -N on POSIX). On POSIX, SIGINT,
/// SIGTERM and SIGHUP sent to `sw` are sent on to `bash` while it runs. The
/// directory is removed again at the end whatever happened.
Future<int> runFenced(
  String bash,
  List<String> command,
  Map<String, String> environment, {
  Directory? tempRoot,
}) async {
  final dir = (tempRoot ?? Directory.systemTemp).createTempSync('sw-as-');
  final subscriptions = <StreamSubscription<ProcessSignal>>[];
  try {
    final records = BytesBuilder(copy: false);
    for (final record in [...command, fencedEnd]) {
      records
        ..add(encodeEscaped(record))
        ..addByte(0);
    }
    final file = File('${dir.path}${Platform.pathSeparator}args')
      ..writeAsBytesSync(records.takeBytes());
    // `sw` got `PWD` in its drive form from the shim's bash, and a bash that is
    // given a valid `PWD` keeps it: dropped, the command's bash works its own
    // out, in the MSYS form `as.sh` ran with.
    final env = Map.of(environment);
    if (Platform.isWindows) {
      env.removeWhere((key, _) => key.toUpperCase() == 'PWD');
    }
    final Process process;
    try {
      process = await Process.start(
        bash,
        ['-c', fencedPrelude, 'as.sh', file.path.replaceAll(r'\', '/')],
        environment: env,
        includeParentEnvironment: false,
        mode: ProcessStartMode.inheritStdio,
      );
    } on ProcessException catch (e) {
      stderr.writeln('as.sh: cannot start bash: ${e.message}');
      return 127;
    }
    if (!Platform.isWindows) {
      for (final signal in [
        ProcessSignal.sigint,
        ProcessSignal.sigterm,
        ProcessSignal.sighup,
      ]) {
        subscriptions.add(signal.watch().listen(process.kill));
      }
    }
    final code = await process.exitCode;
    return code < 0 ? 128 - code : code;
  } finally {
    for (final subscription in subscriptions) {
      unawaited(subscription.cancel());
    }
    try {
      dir.deleteSync(recursive: true);
    } on FileSystemException {
      // already removed by the prelude
    }
  }
}
