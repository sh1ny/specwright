import 'dart:convert';
import 'dart:io' as io;

import '../commit/context.dart';
import '../commit/fit_subject.dart';
import '../commit/task_cover.dart';
import '../vcs/args.dart';
import '../vcs/codec.dart' show NotUtf8;
import '../vcs/document.dart';
import '../vcs/stop.dart';
import 'vcs.dart' show readAllStdin;

export '../commit/context.dart';

/// The dispatch seam: subcommand name to handler.
final Map<String, CommitHandler> commitHandlers = {
  'task-cover': runTaskCover,
  'fit-subject': runFitSubject,
};

const String _argvUsage = 'usage: sw commit --args-stdin';

const String commitHandoffUsage =
    'usage: sw commit --args-stdin (stdin: scripts dir, bash path, '
    'subcommand task-cover or fit-subject and arguments, each record ending '
    'in a NUL byte)';

/// `sw commit --args-stdin`: nothing else on [args]. Reads the handoff from
/// [readStdin] (default: the process stdin) and runs the subcommand's handler
/// from [handlers] (default [commitHandlers]); its exit code is returned.
/// A bad argv, a short handoff or an unknown subcommand is one usage document
/// on stdout with exit 2.
Future<int> runCommitCommand(
  List<String> args, {
  required void Function(List<int> bytes) writeOut,
  void Function(List<int> bytes)? writeErr,
  Future<List<int>> Function()? readStdin,
  Map<String, CommitHandler>? handlers,
}) async {
  try {
    if (args.length != 1 || args.first != '--args-stdin') {
      throw VcsStop('usage', _argvUsage, code: 2);
    }
    final input = await (readStdin ?? readAllStdin)();
    final Handoff handoff;
    try {
      handoff = parseHandoff(input, commitHandoffUsage);
    } on NotUtf8 catch (e) {
      // D4: refused before any file is read. `fit-subject.sh` has no document: its line is on stderr, exit 2.
      if (_subcommandOf(input) == 'fit-subject') {
        (writeErr ?? io.stderr.add)(
          utf8.encode('fit-subject.sh: not valid UTF-8: ${e.shown}\n'),
        );
        return 2;
      }
      throw VcsStop.notUtf8(e);
    }
    final sub = handoff.argv.first;
    final handler = (handlers ?? commitHandlers)[sub];
    if (handler == null) {
      throw VcsStop('usage', '$_argvUsage: unknown subcommand $sub', code: 2);
    }
    return await handler(
      handoff.argv.sublist(1),
      CommitContext(
        scriptsDir: handoff.scriptsDir,
        bash: handoff.bash,
        writeOut: writeOut,
        writeErr: writeErr ?? io.stderr.add,
      ),
    );
  } on VcsStop catch (stop) {
    writeOut(documentBytes(stop.object()));
    return stop.code;
  } on Object catch (e) {
    final stop = VcsStop.refusal(e);
    if (stop == null) rethrow;
    writeOut(documentBytes(stop.object()));
    return stop.code;
  }
}

/// The subcommand record of a handoff (the third), read as ASCII: null when it is missing or not a plain word.
String? _subcommandOf(List<int> input) {
  var nul = 0;
  var start = 0;
  for (var i = 0; i < input.length; i++) {
    if (input[i] != 0) continue;
    if (nul == 2) return String.fromCharCodes(input.sublist(start, i));
    nul++;
    start = i + 1;
  }
  return null;
}
