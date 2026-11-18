import 'dart:typed_data';

import '../process/launch.dart';
import 'text.dart';

/// What one `git` run of `sw update` ended in.
class GitResult {
  GitResult(this.code, this.stdout, this.stderr);

  final int code;
  final Uint8List stdout;
  final Uint8List stderr;

  bool get ok => code == 0;

  /// stdout as text (a bad byte is U+FFFD).
  String get text => decodeLossy(stdout);

  /// stderr as text.
  String get errText => decodeLossy(stderr);

  /// The non-blank lines of stdout; empty when the run failed.
  List<String> get lines => ok
      ? [
          for (final line in text.split('\n'))
            if (pyStrip(line).isNotEmpty) line,
        ]
      : const [];
}

/// Runs `git` with [args] in [dir]: the seam every git call of `sw update`
/// goes through, so a test can replace it.
typedef GitRunner = Future<GitResult> Function(
  String dir,
  List<String> args, {
  List<int>? input,
});

/// The `git -C <dir> -c core.quotepath=off <args>` of `update.sh`, started
/// through `launch()` with no shell and `sw`'s own environment. A missing
/// directory or a missing `git` is a failed run (exit 127), as `git -C` on a
/// missing directory is one.
Future<GitResult> runUpdateGit(
  String dir,
  List<String> args, {
  List<int>? input,
}) async {
  final result = await launch(
    ['git', '-C', dir, '-c', 'core.quotepath=off', ...args],
    cwd: dir,
    input: input,
  );
  return GitResult(result.exitCode, result.stdout, result.stderr);
}
