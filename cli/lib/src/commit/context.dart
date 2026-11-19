/// What a `sw commit` subcommand gets: the two output sinks (raw bytes,
/// because a task title or subject need not be UTF-8).
class CommitContext {
  CommitContext({required this.writeOut, required this.writeErr});

  final void Function(List<int> bytes) writeOut;
  final void Function(List<int> bytes) writeErr;
}

/// Runs one subcommand with its arguments (those after the subcommand) and
/// returns the exit code.
typedef CommitHandler = Future<int> Function(
  List<String> args,
  CommitContext ctx,
);
