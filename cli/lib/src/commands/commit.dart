import 'dart:io' as io;

import '../commit/context.dart';
import '../commit/fit_subject.dart';
import '../commit/task_cover.dart';
import '../vcs/document.dart';
import '../vcs/stop.dart';

export '../commit/context.dart';

/// The dispatch seam: subcommand name to handler.
final Map<String, CommitHandler> commitHandlers = {
  'task-cover': runTaskCover,
  'fit-subject': runFitSubject,
};

const String _usage = 'usage: sw commit task-cover|fit-subject [arguments]';

/// `sw commit <subcommand> [arguments]`: runs the subcommand's handler from
/// [handlers] (default [commitHandlers]); its exit code is returned. A missing
/// or unknown subcommand is one usage document on stdout with exit 2.
Future<int> runCommitCommand(
  List<String> args, {
  required void Function(List<int> bytes) writeOut,
  void Function(List<int> bytes)? writeErr,
  Map<String, CommitHandler>? handlers,
}) async {
  try {
    if (args.isEmpty) throw VcsStop('usage', _usage, code: 2);
    final sub = args.first;
    final handler = (handlers ?? commitHandlers)[sub];
    if (handler == null) {
      throw VcsStop('usage', '$_usage: unknown subcommand $sub', code: 2);
    }
    return await handler(
      args.sublist(1),
      CommitContext(writeOut: writeOut, writeErr: writeErr ?? io.stderr.add),
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
