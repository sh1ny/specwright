import 'dart:io' as io;

import '../vcs/args.dart';
import '../vcs/document.dart';
import '../vcs/git_backend.dart';
import '../vcs/gitbutler_backend.dart';
import '../vcs/jj_backend.dart';
import '../vcs/probe.dart';
import '../vcs/scripts.dart';
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

/// What every subcommand after the probe works with: `vcs.sh`'s `main` up to
/// its dispatch. [repo] and [code] are the resolved directories, [info] the
/// probe's answer (with `--main` applied) and [scripts] the scripts directory
/// and bash from the stdin header.
class VcsSession {
  VcsSession(this.ctx, this.repo, this.code, this.info, this.scripts);

  final VcsContext ctx;
  final String repo;
  final String code;
  final ProbeInfo info;
  final VcsScripts scripts;

  VcsRequest get request => ctx.request;
}

/// `vcs.sh`'s `main` before dispatch: resolve `--repo` and `--code`, probe the
/// backend, apply `--main`.
Future<VcsSession> openSession(VcsContext ctx) async {
  final request = ctx.request;
  final scripts = VcsScripts(ctx.scriptsDir, ctx.bash);
  final repo = await resolvePath(ctx.bash, request.repo);
  final code = await resolvePath(ctx.bash, request.code);
  final info = await probe(scripts, repo, code, request.role);
  final main = request.main;
  if (main != null && main.isNotEmpty) info.main = main;
  return VcsSession(ctx, repo, code, info, scripts);
}

typedef VcsSessionHandler = Future<Map<String, Object?>> Function(
  VcsSession session,
);

/// A [VcsHandler] that runs [handler] after the probe, as `vcs.sh` dispatches.
VcsHandler probed(VcsSessionHandler handler) =>
    (ctx) async => handler(await openSession(ctx));

/// `probe`'s own document.
Future<Map<String, Object?>> probeDocument(VcsSession session) async => {
  'ok': true,
  'backend': session.info.backend,
  'main': session.info.main,
  if (session.info.backend == 'git' && session.info.jjPresent)
    'jj_present': true,
};

/// `state` after the probe: Git is ported, the other backends are not yet.
Future<Map<String, Object?>> _state(VcsSession s) async {
  if (s.info.backend == 'git') return gitStateDocument(s);
  if (s.info.backend == 'jj') return jjStateDocument(s);
  if (s.info.backend == 'gitbutler') return gitbutlerStateDocument(s);
  throw StateError('state is not ported yet');
}

/// An operation after the probe, as `vcs.sh` dispatches by backend. Only the
/// Git backend is ported.
VcsHandler _operation(String command) => probed((VcsSession s) async {
  if (s.info.backend == 'git') return runGitOperation(s, command);
  if (s.info.backend == 'jj') return runJjOperation(s, command);
  if (s.info.backend == 'gitbutler') return runGitbutlerOperation(s, command);
  throw StateError('$command is not ported yet');
});

/// The dispatch seam: subcommand name to handler. The jj, GitButler and plan
/// task groups replace the remaining entries.
///
/// TEMPORARY: `plan` and the non-Git backends run the probe and then answer
/// `internal_error` ("not ported yet").
final Map<String, VcsHandler> vcsHandlers = {
  'probe': probed(probeDocument),
  'state': probed(_state),
  for (final command in knownCommands)
    if (command != 'probe' && command != 'state')
      command: command == 'plan'
          ? probed((_) async => throw StateError('plan is not ported yet'))
          : _operation(command),
};

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
