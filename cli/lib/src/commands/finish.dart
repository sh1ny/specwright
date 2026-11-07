import 'dart:io' as io;

import '../finish/undo_plan.dart';
import '../vcs/args.dart';
import '../vcs/document.dart';
import '../vcs/stop.dart';
import 'vcs.dart' show readAllStdin;

const String _argvUsage = 'usage: sw finish --args-stdin';

const String finishHandoffUsage =
    'usage: sw finish --args-stdin (stdin: scripts dir, bash path, then '
    "finish.sh's arguments, each record ending in a NUL byte)";

/// `finish.sh`'s usage text for a missing or unknown subcommand.
const String finishUsage =
    'usage: finish.sh [--dir <planning toplevel>] undo-archive-plan '
    '--change <name> --archived-name <archived> --prefix <P> --main <main> '
    '[--branch <branch>] [--type <type>] [--code <code toplevel>]';

const Map<String, String> _undoOptions = {
  '--change': 'change',
  '--archived-name': 'archived',
  '--prefix': 'prefix',
  '--main': 'main',
  '--branch': 'branch',
  '--type': 'type',
  '--code': 'code',
};

VcsStop _usage(String message) => VcsStop('usage', message, code: 2);

/// `finish.sh`'s `parse_args`: each option takes the next argument as its
/// value, whatever it looks like; the last one wins.
Map<String, String> _parseOptions(List<String> argv) {
  final found = <String, String>{};
  var i = 0;
  while (i < argv.length) {
    final token = argv[i];
    final key = _undoOptions[token];
    if (key != null) {
      if (i + 1 >= argv.length) throw _usage('$token needs a value');
      found[key] = argv[i + 1];
      i += 2;
    } else if (token.startsWith('--')) {
      throw _usage('unknown option $token');
    } else {
      throw _usage('unexpected argument $token');
    }
  }
  return found;
}

/// `sw finish --args-stdin`: nothing else on [args]. Reads the handoff from
/// [readStdin] (default: the process stdin): the scripts dir, the bash, then
/// `finish.sh`'s own arguments. A leading `--dir <d>` is read first, then the
/// subcommand `undo-archive-plan` and its options, and [planner] (default
/// [undoArchivePlan]) builds the document. Returns the exit code: 0, a stop's
/// (1 or 2), or 1 for an unexpected failure (`internal_error`).
Future<int> runFinishCommand(
  List<String> args, {
  required void Function(List<int> bytes) writeOut,
  Future<List<int>> Function()? readStdin,
  UndoPlanner? planner,
}) async {
  Map<String, Object?> document;
  var code = 0;
  try {
    if (args.length != 1 || args.first != '--args-stdin') {
      throw _usage(_argvUsage);
    }
    var stdin = await (readStdin ?? readAllStdin)();
    // `finish.sh` with no argument prints its usage text: give the handoff
    // parser an empty argument record so that it gets there.
    if (stdin.isNotEmpty && stdin.last == 0 && _records(stdin) == 2) {
      stdin = [...stdin, 0];
    }
    final handoff = parseHandoff(stdin, finishHandoffUsage);
    var rest = handoff.argv;
    String? dir;
    if (rest.first == '--dir') {
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
    document = await (planner ?? undoArchivePlan)(
      request,
      FinishContext(scriptsDir: handoff.scriptsDir, bash: handoff.bash),
    );
  } on VcsStop catch (stop) {
    document = stop.object();
    code = stop.code;
  } on Object catch (e) {
    document = {
      'ok': false,
      'error': 'internal_error',
      'message': '${e.runtimeType}: ${e is StateError ? e.message : e}',
    };
    code = 1;
  }
  writeOut(documentBytes(document));
  return code;
}

int _records(List<int> bytes) => bytes.where((b) => b == 0).length;
