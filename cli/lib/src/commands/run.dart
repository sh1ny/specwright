import 'dart:io';

import '../process/bounded_run.dart';
import '../process/limit_line.dart';
import '../process/limits.dart';
import '../process/platform_tree.dart';
import '../process/resolve.dart';
import '../process/transport.dart';

const String runUsage =
    'usage: sw run --bounded [--paged] [--secret] -- cmd [args...]\n';

/// A parsed `sw run` command line.
class RunInvocation {
  const RunInvocation({
    required this.paged,
    required this.secret,
    required this.command,
  });

  final bool paged;
  final bool secret;
  final List<String> command;
}

/// Parses the arguments after `run`: flags, `--`, then the command. Null when
/// the invocation is invalid: no `--bounded`, no `--`, nothing after `--`, or
/// a flag other than `--bounded`, `--paged` and `--secret`.
RunInvocation? parseRunArgs(List<String> args) {
  final dashes = args.indexOf('--');
  if (dashes < 0) return null;
  final flags = args.sublist(0, dashes);
  final command = args.sublist(dashes + 1);
  if (command.isEmpty) return null;
  const known = {'--bounded', '--paged', '--secret'};
  if (flags.any((f) => !known.contains(f)) || !flags.contains('--bounded')) {
    return null;
  }
  return RunInvocation(
    paged: flags.contains('--paged'),
    secret: flags.contains('--secret'),
    command: command,
  );
}

/// `sw run --bounded [--paged] [--secret] -- <cmd> [args...]`; returns the
/// exit code. [writeOut] and [writeErr] receive the command's bytes. Secret
/// mode behaves the same way: output is only ever held in memory, and on a
/// limit nothing but the limit line is printed in either mode.
Future<int> runCommand(
  List<String> args, {
  required StringSink err,
  required void Function(List<int> bytes) writeOut,
  required void Function(List<int> bytes) writeErr,
  Map<String, String>? env,
  List<String>? helperCommand,
}) async {
  final invocation = parseRunArgs(args);
  if (invocation == null) {
    err.write(runUsage);
    return 2;
  }
  final environment = env ?? Platform.environment;
  final command = invocation.command;

  final path = resolveCommand(command.first, environment);
  if (path == null) {
    err.write('bounded: cannot start ${command.first}: command not found\n');
    return 127;
  }
  if (Platform.isWindows &&
      RegExp(r'\.(cmd|bat)$', caseSensitive: false).hasMatch(path)) {
    err.write('bounded: batch shims are not supported yet: ${command.first}\n');
    return 127;
  }

  final transport = transportFor([path, ...command.skip(1)]);
  final result = await BoundedRun(
    command: transport.command,
    stdinBytes: transport.stdinBytes,
    limits: resolveLimits(environment, paged: invocation.paged),
    helperCommand: helperCommand,
    treeFor: () => platformTree(environment),
    preGoFile: environment['SPECWRIGHT_TEST_PRE_GO'],
    note: err.write,
  ).run();

  final label = commandLabel(command);
  if (result.helperNotStopped) {
    err.write('bounded: helper not stopped: $label\n');
  }
  final limit = result.limit;
  if (limit != null) {
    err.write(limitLine(limit, command));
    return limit.exitCode;
  }
  if (result.helperExited) {
    err.write('bounded: helper exited during startup: $label\n');
    return 127;
  }
  final startError = result.startError;
  if (startError != null) {
    err.write('bounded: cannot start ${command.first}: $startError\n');
    return 127;
  }
  writeOut(result.stdout);
  writeErr(result.stderr);
  final code = result.exitCode ?? 127;
  return code < 0 ? 128 - code : code;
}
