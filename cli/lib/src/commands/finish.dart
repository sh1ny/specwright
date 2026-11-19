import 'dart:io' as io;

import '../finish/undo_plan.dart';
import '../finish/undo_step.dart';
import '../options.dart';
import '../vcs/document.dart';
import '../vcs/stop.dart';

/// `finish.sh`'s usage text for a missing or unknown subcommand.
const String finishUsage =
    'usage: finish.sh [--dir <planning toplevel>] undo-archive-plan '
    '--change <name> --archived-name <archived> --prefix <P> --main <main> '
    '[--branch <branch>] [--type <type>] [--code <code toplevel>]';

const List<String> _undoOptions = [
  'change',
  'archived-name',
  'prefix',
  'main',
  'branch',
  'type',
  'code',
];

VcsStop _usage(String message) => VcsStop('usage', message, code: 2);

/// `finish.sh`'s `parse_args` under the one option rule (`options.dart`): each
/// option takes the next argument as its value, whatever it looks like; the
/// last one wins; a word that is not an option is a usage stop. Keyed by the
/// name `UndoRequest` knows, `archived-name` as `archived`.
Map<String, String> _parseOptions(List<String> argv) {
  final parsed = parseOptions(
    argv,
    values: _undoOptions,
    usage: (message) => throw _usage(message),
  );
  if (parsed.rest.isNotEmpty) {
    throw _usage('unexpected argument ${parsed.rest.first}');
  }
  return {
    for (final name in _undoOptions)
      if (parsed.wasParsed(name))
        (name == 'archived-name' ? 'archived' : name): parsed.option(name)!,
  };
}

/// `sw finish [--dir <d>] undo-archive-plan <options>`, or `sw finish undo-step`.
/// A leading `--dir <d>` is read first, then the subcommand
/// `undo-archive-plan` and its options, and [planner] (default
/// [undoArchivePlan]) builds the document. Returns the exit code: 0, a stop's
/// (1 or 2), or 1 for an unexpected failure (`internal_error`).
Future<int> runFinishCommand(
  List<String> args, {
  required void Function(List<int> bytes) writeOut,
  UndoPlanner? planner,
}) async {
  if (args.isNotEmpty && args.first == 'undo-step') {
    return runUndoStep(args.sublist(1), writeOut: writeOut);
  }
  Map<String, Object?> document;
  var code = 0;
  try {
    var rest = args;
    String? dir;
    if (rest.isNotEmpty && rest.first == '--dir') {
      if (rest.length < 2) throw _usage('--dir needs a value');
      dir = rest[1];
      rest = rest.sublist(2);
    }
    if (rest.isEmpty || rest.first != 'undo-archive-plan') {
      throw _usage(finishUsage);
    }
    final options = _parseOptions(rest.sublist(1));
    final request = UndoRequest(
      dir: dir == null || dir.isEmpty ? io.Directory.current.path : dir,
      change: options['change'],
      archived: options['archived'],
      prefix: options['prefix'],
      main: options['main'],
      branch: options['branch'],
      type: options['type'],
      code: options['code'],
    );
    document = await (planner ?? undoArchivePlan)(request, FinishContext());
  } on VcsStop catch (stop) {
    document = stop.object();
    code = stop.code;
  } on Object catch (e) {
    final stop = VcsStop.refusal(e);
    document =
        stop?.object() ??
        {
          'ok': false,
          'error': 'internal_error',
          'message': '${e.runtimeType}: ${e is StateError ? e.message : e}',
        };
    code = stop?.code ?? 1;
  }
  writeOut(documentBytes(document));
  return code;
}
