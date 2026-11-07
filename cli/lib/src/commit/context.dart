/// What a `sw commit` subcommand gets from the handoff: the scripts directory,
/// the bash that ran the shim, and the two output sinks (raw bytes, because a
/// task title or subject need not be UTF-8).
class CommitContext {
  CommitContext({
    required this.scriptsDir,
    required this.bash,
    required this.writeOut,
    required this.writeErr,
  });

  final String scriptsDir;
  final String bash;
  final void Function(List<int> bytes) writeOut;
  final void Function(List<int> bytes) writeErr;
}

/// Runs one subcommand with its arguments (the handoff records after the
/// subcommand) and returns the exit code.
typedef CommitHandler = Future<int> Function(
  List<String> args,
  CommitContext ctx,
);
