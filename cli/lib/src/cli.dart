import 'dart:convert';
import 'dart:io' as io;

import 'package:args/args.dart';

import 'commands/commit.dart';
import 'commands/finish.dart';
import 'commands/pr.dart';
import 'commands/release.dart';
import 'commands/review.dart';
import 'commands/run.dart';
import 'commands/update.dart';
import 'commands/vcs.dart';
import 'commands/version.dart';
import 'entry/project_version.dart';
import 'entry/raw_arguments.dart';
import 'fence/as_command.dart';
import 'finish/undo_plan.dart';
import 'process/exec_helper.dart';
import 'process/platform_tree.dart';
import 'vcs/document.dart' show documentBytes;

const _usage =
    'usage: sw [--project <code checkout>] <command>\n'
    'commands:\n'
    '  version [--json]  print the sw version and interface version\n'
    '  run --bounded [--paged] [--secret] -- cmd [args...]\n'
    '                    run a command under a deadline and a byte bound\n'
    '  vcs --args-stdin  run one VCS operation; stdin: scripts dir, bash,\n'
    '                    subcommand and arguments, each ending in a NUL\n'
    '  commit --args-stdin  run task-cover or fit-subject; same stdin as vcs\n'
    '  finish --args-stdin  print the undo plan of an archive; same stdin as vcs\n'
    '  review --args-stdin  select, run or record a design/pre-ship review; same stdin as vcs\n'
    '  release [--dir <repo>] <sub> [options]\n'
    '                    check, bump, status, untagged, publish or notes\n'
    '  release --args-stdin  run a release subcommand for the shim; same stdin as vcs\n'
    '  pr snapshot|reply --args-stdin  read or answer a pull request; same stdin as vcs\n'
    '  update <sub> [options]  stage, swap, recover and finish an update;\n'
    '                    plan, note-config, pack-check, pack-verify, pack-docs,\n'
    '                    sw-install or interface\n'
    '  as --args-file <path>  run the identity fence for the as.sh shim; the\n'
    '                    file holds the same records, and is deleted when read\n';

/// Whether [args] use the old stdin or file handoff of the shell shims, which
/// resolved the version-matched `sw` themselves; task 7.3 removes the handoff
/// and this exemption with it.
bool _isHandoff(List<String> args) =>
    args.contains('--args-stdin') || args.contains('--args-file');

/// Runs sw with [args], writing to [out] and [err]; returns the exit code.
///
/// `run` passes the command's own bytes through [outBytes] and [errBytes]
/// (default: the process stdout and stderr), because they need not be text.
Future<int> runCli(
  List<String> rawArgs, {
  required StringSink out,
  required StringSink err,
  void Function(List<int> bytes)? outBytes,
  void Function(List<int> bytes)? errBytes,
  Future<List<int>> Function()? readStdin,
  Map<String, VcsHandler>? vcsHandlers,
  Map<String, CommitHandler>? commitHandlers,
  UndoPlanner? undoPlanner,
}) async {
  void writeDocument(Map<String, Object?> document) =>
      (outBytes ?? io.stdout.add)(documentBytes(document));
  // Before any other work: an argument that is not well-formed Unicode as it
  // reached the process stops here (native-cli "Arguments sw cannot
  // represent are refused").
  final bad = firstUnrepresentableArgument(rawArgs);
  if (bad != null) {
    writeDocument({
      'ok': false,
      'error': 'bad_argument',
      'message': 'argument $bad is not well-formed Unicode',
    });
    return 2;
  }
  final ProjectChoice choice;
  try {
    choice = chooseProject(rawArgs, io.Directory.current.path);
  } on ProjectUsage catch (e) {
    err.write('${e.message}\n$_usage');
    return 2;
  }
  final args = choice.rest;
  if (args.isNotEmpty &&
      projectCommands.contains(args.first) &&
      !_isHandoff(args) &&
      !(args.first == 'pr' && args.length > 1 && args[1] == 'reviewers')) {
    final mismatch = versionMismatch(choice.dir);
    if (mismatch != null) {
      writeDocument(mismatch);
      return 1;
    }
  }
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
  if (args.isNotEmpty && args.first == 'as') {
    return runAsCommand(
      args.sublist(1),
      writeOut: outBytes ?? io.stdout.add,
      writeErr: errBytes ?? io.stderr.add,
    );
  }
  if (args.isNotEmpty && args.first == 'pr') {
    return runPrCommand(
      args.sublist(1),
      writeOut: outBytes ?? io.stdout.add,
      writeErr: errBytes ?? io.stderr.add,
      readStdin: readStdin,
    );
  }
  if (args.isNotEmpty && args.first == 'finish') {
    return runFinishCommand(
      args.sublist(1),
      writeOut: outBytes ?? io.stdout.add,
      readStdin: readStdin,
      planner: undoPlanner,
    );
  }
  if (args.isNotEmpty && args.first == 'release') {
    return runReleaseCommand(
      args.sublist(1),
      writeOut: outBytes ?? io.stdout.add,
      readStdin: readStdin,
    );
  }
  if (args.isNotEmpty && args.first == 'review') {
    return runReviewCommand(
      args.sublist(1),
      writeOut: outBytes ?? io.stdout.add,
      readStdin: readStdin,
    );
  }
  if (args.isNotEmpty && args.first == 'update') {
    return runUpdateCommand(
      args.sublist(1),
      writeOut: outBytes ?? io.stdout.add,
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
