import 'dart:convert';
import 'dart:io';

import '../pr/gh.dart';
import '../vcs/tool_runner.dart';
import 'exec_inherit.dart';
import 'fence.dart';
import 'urls.dart';

/// `sw as <login> <command...>` or `sw as --resolve`: the identity fence. The
/// arguments are the process's own, so each reaches the fenced command as one
/// whole value. A call with no argument prints the usage line and exits 1, as
/// `as.sh` did.
///
/// [gh], [git] and [launch] are the seams the tests replace; by default they
/// run the bounded gh lookups, the fence's plain git reads, and the command
/// under [runFenced].
Future<int> runAsCommand(
  List<String> args, {
  required void Function(List<int> bytes) writeOut,
  required void Function(List<int> bytes) writeErr,
  String host = defaultGitHubHost,
  Map<String, String>? environment,
  GhCall? gh,
  GitCall? git,
  Launch? launch,
  List<String>? helperCommand,
}) async {
  void err(String text) => writeErr(utf8.encode(text));
  // D8: an inherited GH_REPO reaches neither the lookups nor the fenced command
  final env = {...(environment ?? Platform.environment)}..remove('GH_REPO');
  return runFence(
    args,
    environment: env,
    host: host,
    gh:
        gh ??
        (ghArgs, e) =>
            runGh('.', ghArgs, environment: e, helperCommand: helperCommand),
    git:
        git ??
        (command, e) async {
          final r = await runTool('.', command, environment: e);
          return r;
        },
    launch: launch ?? (command, e) => runFenced(command, e),
    out: (text) => writeOut(utf8.encode(text)),
    err: err,
  );
}
