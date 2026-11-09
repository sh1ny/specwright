import 'dart:io';

import '../fence/fence.dart';
import '../process/limit_line.dart';
import '../process/limits.dart';
import '../vcs/tool_runner.dart';
import 'gh.dart';
import 'pair.dart';

typedef WorkflowRunner = Future<GhResult> Function(
  String directory,
  List<String> command,
  Map<String, String> environment,
  RunLimits? limits,
);

/// C5: the explicit target and private environment belong to this request.
/// No operation changes global cwd or environment. A fence refusal remains
/// distinct from an ordinary command exit 3; enclosing expiry wins over an
/// inner lookup limit. With no enclosing budget, local checks and the launched
/// command retain their unbounded mode.
class WorkflowTransport {
  WorkflowTransport({
    required this.directory,
    required this.environment,
    required this.runner,
  });
  final String directory;
  final Map<String, String> environment;
  final WorkflowRunner runner;

  factory WorkflowTransport.native({
    required String directory,
    required String bash,
    Map<String, String>? environment,
    List<String>? helperCommand,
  }) => WorkflowTransport(
    directory: directory,
    environment: Map.of(environment ?? Platform.environment),
    runner: (dir, command, env, limits) async {
      if (limits != null) {
        return runBoundedCommand(
          bash,
          dir,
          command,
          environment: env,
          limits: limits,
          helperCommand: helperCommand,
        );
      }
      final r = await runTool(bash, dir, command, environment: env);
      return GhResult(exitCode: r.exitCode, stdout: r.stdout, stderr: r.stderr);
    },
  );

  Future<GhResult> fenced(
    String login,
    List<String> command, {
    RunLimits? outer,
  }) async {
    final watch = Stopwatch()..start();
    Never limited(BoundedLimit limit) => throw PairStop(
      limit.label,
      'GitHub state unknown: ${limit.label}: ${command.take(2).join(' ')}',
      code: 3,
      extra: {'unknown': true},
    );
    void checkOuter() {
      if (outer != null && watch.elapsed >= outer.deadline) {
        limited(BoundedLimit.deadlineExceeded);
      }
    }

    Future<GhResult> call(
      List<String> cmd,
      Map<String, String> env, {
      bool lookup = false,
    }) async {
      checkOuter();
      final inner = lookup ? resolveLimits(env, paged: false) : null;
      RunLimits? limits = inner;
      var enclosing = false;
      if (outer != null) {
        final left = outer.deadline - watch.elapsed;
        enclosing = inner == null || left <= inner.deadline;
        limits = RunLimits(
          deadline: enclosing ? left : inner.deadline,
          maxBytes: inner == null || outer.maxBytes < inner.maxBytes
              ? outer.maxBytes
              : inner.maxBytes,
        );
      }
      final r = await runner(directory, cmd, Map.of(env), limits);
      checkOuter();
      final outerLimit = r.limit == BoundedLimit.responseTooLarge
          // The old outer wrapper captured the fence's final output, never
          // its private lookup streams. A lookup byte stop is a fence refusal
          // even when its cap equals the enclosing command's stream cap.
          ? !lookup
          : enclosing;
      if (r.limit != null && (outerLimit || !lookup)) limited(r.limit!);
      return r;
    }

    try {
      final discovery = discoveryEnvironment(saveOriginals(environment));
      Future<GhResult> gh(List<String> args, Map<String, String> env) =>
          call(['gh', ...args], env, lookup: true);
      Future<ToolResult> git(List<String> cmd, Map<String, String> env) async {
        final r = await call(cmd, env);
        return ToolResult(r.exitCode, r.stdout, r.stderr);
      }

      await checkGhVersion(gh, discovery);
      final tokenEnv = await verifyIdentity(login, gh, discovery);
      checkOuter();
      checkArguments(command);
      checkOptions(command);
      await checkRemotes(git, tokenEnv);
      final fenced = await fencedEnvironment(tokenEnv, git);
      return await call(command, fenced);
    } on FenceStop catch (stop) {
      checkOuter();
      throw PairStop(
        'fence_refused',
        'as.sh refused the read in $directory: ${stop.message.trim()}',
        code: 3,
        extra: {'repo_dir': directory},
      );
    } finally {
      watch.stop();
    }
  }
}
