import 'dart:io' as io;

import '../vcs/args.dart';
import '../vcs/document.dart';
import '../vcs/stop.dart';

/// What a subcommand handler gets: the parsed request and the two values the
/// shim handed over (design D2).
class VcsContext {
  VcsContext(this.request, this.scriptsDir, this.bash);

  final VcsRequest request;
  final String scriptsDir;
  final String bash;
}

/// Runs one subcommand. It returns the document to print (exit 0) or throws a
/// [VcsStop] (its own exit code).
typedef VcsHandler = Future<Map<String, Object?>> Function(VcsContext ctx);

/// The dispatch seam: subcommand name to handler. The backend task groups
/// (git, jj, GitButler, plan) fill it in.
///
/// TEMPORARY: it is empty until those groups land, so every known subcommand
/// answers `internal_error` ("not ported yet").
final Map<String, VcsHandler> vcsHandlers = {};

const String _argvUsage = 'usage: sw vcs --args-stdin';

/// `sw vcs --args-stdin`: nothing else on [args]. Reads the handoff from
/// [readStdin], runs the handler and writes one document to [writeOut].
/// Returns the exit code: 0, or the stop's (1, 2 or 3), or 1 for an
/// unexpected failure (`internal_error`, never a stack trace).
Future<int> runVcsCommand(
  List<String> args, {
  required void Function(List<int> bytes) writeOut,
  Future<List<int>> Function()? readStdin,
  Map<String, VcsHandler>? handlers,
}) async {
  Map<String, Object?> document;
  var code = 0;
  try {
    if (args.length != 1 || args.first != '--args-stdin') {
      throw VcsStop('usage', _argvUsage, code: 2);
    }
    final handoff = parseHandoff(await (readStdin ?? _readAllStdin)());
    final request = parseVcsArguments(handoff.argv);
    final handler = (handlers ?? vcsHandlers)[request.command];
    if (handler == null) {
      throw StateError('${request.command} is not ported yet');
    }
    document = await handler(
      VcsContext(request, handoff.scriptsDir, handoff.bash),
    );
  } on VcsStop catch (stop) {
    document = stop.object();
    code = stop.code;
  } on Object catch (e) {
    document = _internalError(e);
    code = 1;
  }
  try {
    writeOut(documentBytes(document));
  } on Object catch (e) {
    // A document that cannot be encoded is an unexpected failure too.
    document = _internalError(e);
    code = 1;
    writeOut(documentBytes(document));
  }
  return code;
}

Map<String, Object?> _internalError(Object e) => {
  'ok': false,
  'error': 'internal_error',
  'message': switch (e) {
    StateError(:final message) => message,
    ArgumentError(:final message) => '$message',
    FormatException(:final message) => message,
    _ => e.toString(),
  },
};

Future<List<int>> _readAllStdin() async {
  final bytes = <int>[];
  await for (final chunk in io.stdin) {
    bytes.addAll(chunk);
  }
  return bytes;
}
