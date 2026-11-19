import '../review/run.dart';
import '../review/stop.dart';
import '../vcs/document.dart' show documentBytes;
import '../vcs/stop.dart';

/// `sw review <subcommand> [options]`: runs one review operation and writes
/// exactly one native JSON document, returning its historical status.
Future<int> runReviewCommand(
  List<String> args, {
  required void Function(List<int> bytes) writeOut,
}) async {
  Map<String, Object?> document;
  var code = 0;
  try {
    document = await runReviewOperation(argv: args);
  } on ReviewStop catch (stop) {
    document = stop.toJson();
    code = stop.code;
  } on VcsStop catch (stop) {
    document = stop.object();
    code = stop.code;
  } on Object catch (error) {
    final refusal = VcsStop.refusal(error);
    if (refusal is VcsStop) {
      document = refusal.object();
      code = refusal.code;
    } else {
      final message = error is StateError ? error.message : error;
      document = {
        'ok': false,
        'error': 'internal_error',
        'message': '${error.runtimeType}: $message',
      };
      code = 1;
    }
  }
  writeOut(documentBytes(document));
  return code;
}
