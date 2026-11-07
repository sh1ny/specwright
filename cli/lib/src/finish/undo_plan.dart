import '../vcs/stop.dart';

/// What `sw finish undo-archive-plan` was asked, as `finish.sh` parsed it:
/// [dir] is the planning repo (`--dir`, the current directory when absent or
/// empty); every other field is the option's last value, null when not given.
class UndoRequest {
  UndoRequest({
    required this.dir,
    this.change,
    this.archived,
    this.prefix,
    this.main,
    this.branch,
    this.type,
    this.code,
  });

  final String dir;
  final String? change;

  /// `--archived-name`.
  final String? archived;
  final String? prefix;
  final String? main;
  final String? branch;
  final String? type;
  final String? code;
}

/// What a planner gets from the handoff: the scripts directory and the bash
/// that ran the shim.
class FinishContext {
  FinishContext({required this.scriptsDir, required this.bash});

  final String scriptsDir;
  final String bash;
}

/// Builds the undo plan: returns the document to print (exit 0) or throws a
/// [VcsStop] (its own exit code).
typedef UndoPlanner = Future<Map<String, Object?>> Function(
  UndoRequest request,
  FinishContext ctx,
);

/// `undo-archive-plan`. The plan itself is not ported yet.
Future<Map<String, Object?>> undoArchivePlan(
  UndoRequest request,
  FinishContext ctx,
) async => throw StateError('undo-archive-plan is not ported yet');
