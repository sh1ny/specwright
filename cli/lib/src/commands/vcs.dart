import 'dart:io' as io;

import '../process/launch.dart' show Unrepresentable;
import '../vcs/args.dart';
import '../vcs/codec.dart';
import '../vcs/document.dart';
import '../vcs/git_backend.dart';
import '../vcs/gitbutler_backend.dart';
import '../vcs/jj_backend.dart';
import '../vcs/plan.dart';
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
  final repo = await resolvePath(request.repo);
  final code = await resolvePath(request.code);
  final scripts = VcsScripts(ctx.scriptsDir, ctx.bash);
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

/// `state` after the probe, by backend. Public so that `sw finish` reads the
/// branch and working-copy changes through it.
Future<Map<String, Object?>> stateDocument(VcsSession s) async {
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

/// The dispatch seam: subcommand name to handler.
final Map<String, VcsHandler> vcsHandlers = {
  'probe': probed(probeDocument),
  'state': probed(stateDocument),
  for (final command in knownCommands)
    if (command != 'probe' && command != 'state')
      command: command == 'plan' ? probed(planDocument) : _operation(command),
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
    final handoff = parseHandoff(
      await (readStdin ?? readAllStdin)(),
      handoffUsage,
    );
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
  } on NotUtf8 catch (e) {
    final stop = VcsStop.notUtf8(e);
    document = stop.object();
    code = stop.code;
  } on Unrepresentable catch (e) {
    final stop = VcsStop.unrepresentable(e);
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

/// Reads the handoff with `readByteSync`, never as a stream: at a pipe's EOF
/// the stream closes fd 0, and Dart 3.13's process spawn can then hand a
/// child's stdin pipe the number 0 and close it in the child
/// (dart-lang/sdk#64744), so a tool's `read` fails with EBADF. The handoff is
/// a few hundred bytes.
Future<List<int>> readAllStdin() async {
  final bytes = <int>[];
  for (var b = io.stdin.readByteSync(); b != -1; b = io.stdin.readByteSync()) {
    bytes.add(b);
  }
  return bytes;
}
