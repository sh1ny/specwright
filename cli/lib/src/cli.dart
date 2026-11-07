import 'dart:convert';
import 'dart:io' as io;

import 'package:args/args.dart';

import 'commands/commit.dart';
import 'commands/run.dart';
import 'commands/vcs.dart';
import 'commands/version.dart';
import 'process/exec_helper.dart';
import 'process/platform_tree.dart';

const _usage =
    'usage: sw <command>\n'
    'commands:\n'
    '  version [--json]  print the sw version and interface version\n'
    '  run --bounded [--paged] [--secret] -- cmd [args...]\n'
    '                    run a command under a deadline and a byte bound\n'
    '  vcs --args-stdin  run one VCS operation; stdin: scripts dir, bash,\n'
    '                    subcommand and arguments, each ending in a NUL\n'
    '  commit --args-stdin  run task-cover or fit-subject; same stdin as vcs\n';

/// Runs sw with [args], writing to [out] and [err]; returns the exit code.
///
/// `run` passes the command's own bytes through [outBytes] and [errBytes]
/// (default: the process stdout and stderr), because they need not be text.
Future<int> runCli(
  List<String> args, {
  required StringSink out,
  required StringSink err,
  void Function(List<int> bytes)? outBytes,
  void Function(List<int> bytes)? errBytes,
  Future<List<int>> Function()? readStdin,
  Map<String, VcsHandler>? vcsHandlers,
  Map<String, CommitHandler>? commitHandlers,
}) async {
  if (args.isNotEmpty && args.first == '__exec') {
    return runExecHelper(
      args.sublist(1),
      hello: platformHello(),
      contain: platformContainment(),
    );
  }
  if (args.isNotEmpty && args.first == 'run') {
    return runCommand(
      args.sublist(1),
      err: err,
      writeOut: outBytes ?? io.stdout.add,
      writeErr: errBytes ?? io.stderr.add,
    );
  }
  if (args.isNotEmpty && args.first == 'commit') {
    return runCommitCommand(
      args.sublist(1),
      writeOut: outBytes ?? io.stdout.add,
      writeErr: errBytes ?? io.stderr.add,
      readStdin: readStdin,
      handlers: commitHandlers,
    );
  }
  if (args.isNotEmpty && args.first == 'vcs') {
    return runVcsCommand(
      args.sublist(1),
      writeOut: outBytes ?? io.stdout.add,
      readStdin: readStdin,
      handlers: vcsHandlers,
    );
  }
  final parser = ArgParser()
    ..addCommand('version', ArgParser()..addFlag('json', negatable: false));
  final ArgResults results;
  try {
    results = parser.parse(args);
  } on ArgParserException {
    err.write(_usage);
    return 2;
  }
  final command = results.command;
  if (command == null || results.rest.isNotEmpty) {
    err.write(_usage);
    return 2;
  }
  switch (command.name) {
    case 'version':
      out.writeln(jsonEncode(versionReport()));
      return 0;
    default:
      err.write(_usage);
      return 2;
  }
}
