import 'dart:io';

import '../pr/gh.dart';
import '../vcs/codec.dart';
import '../vcs/text_result.dart';
import '../vcs/tool_runner.dart';
import 'fence.dart';

/// `as.sh <login> <command...>` (or `as.sh --resolve`) run in this process in
/// [repo]: [runFence] with the bounded `gh` lookups of `sw as` ([runGh]), the
/// fence's own git reads and the fenced command through [runTool], and no
/// outer deadline. Its output is kept as text: [TextResult.code] is the
/// fence's exit status (3 for a refusal or a limit, the command's own
/// otherwise), [TextResult.stdout] is `--resolve`'s login or the command's
/// output, and [TextResult.stderr] is the refusal line or the command's
/// errors.
///
/// Constraint C3: the fence called from `sw vcs` keeps the fenced command
/// unbounded and only the gh lookups bounded; refusals keep exit 3 and the
/// `as.sh:` prefix that Git, jj and GitButler map to `fence_failed`.
///
/// [argv] is `as.sh`'s argument list. [environment] defaults to this process's
/// and is the whole environment the lookups and the command start from. [gh],
/// [git] and [launch] are the seams the tests replace; by default they run the
/// bounded gh lookups ([helperCommand] names the helper, default `sw __exec`),
/// the unbounded git reads, and the command with its output captured.
Future<TextResult> fencedText(
  String bash,
  String repo,
  List<String> argv, {
  Map<String, String>? environment,
  GhCall? gh,
  GitCall? git,
  Launch? launch,
  List<String>? helperCommand,
}) async {
  final out = StringBuffer();
  final err = StringBuffer();
  final code = await runFence(
    argv,
    environment: environment ?? Map<String, String>.of(Platform.environment),
    gh:
        gh ??
        (ghArgs, e) => runGh(
          bash,
          repo,
          ghArgs,
          environment: e,
          helperCommand: helperCommand,
        ),
    git: git ?? (command, e) => runTool(bash, repo, command, environment: e),
    launch:
        launch ??
        (command, e) async {
          final r = await runTool(bash, repo, command, environment: e);
          out.write(decodeText(r.stdout));
          err.write(decodeText(r.stderr));
          return r.exitCode;
        },
    out: out.write,
    err: err.write,
  );
  return TextResult(code, out.toString(), err.toString());
}
