import '../vcs/document.dart';
import 'context.dart';

/// Placeholder for `task-cover`; group 3 of native-cli-commit replaces it.
Future<int> runTaskCover(List<String> args, CommitContext ctx) async {
  ctx.writeOut(
    documentBytes({
      'ok': false,
      'error': 'internal_error',
      'message': 'task-cover is not ported yet',
    }, escapeLineSeparators: false),
  );
  return 1;
}
