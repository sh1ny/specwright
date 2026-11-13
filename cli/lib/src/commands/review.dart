import '../review/run.dart';
import '../review/stop.dart';
import '../vcs/args.dart';
import '../vcs/document.dart' show documentBytes;
import '../vcs/stop.dart';
import 'vcs.dart' show readAllStdin;

const String _argvUsage = 'usage: sw review --args-stdin';
const String _handoffUsage =
    'usage: sw review --args-stdin (stdin: scripts dir, bash path, subcommand and arguments, each record ending in a NUL byte)';

/// `sw review --args-stdin`: reads the script directory, its bash path and the
/// original `review-run.sh` arguments as NUL-terminated handoff records, then
/// writes exactly one native JSON document and returns its historical status.
Future<int> runReviewCommand(
  List<String> args, {
  required void Function(List<int> bytes) writeOut,
  Future<List<int>> Function()? readStdin,
}) async {
  Map<String, Object?> document;
  var code = 0;
  try {
    if (args.length != 1 || args.single != '--args-stdin') {
      throw ReviewStop('usage', _argvUsage, code: 2);
    }
    var stdin = await (readStdin ?? readAllStdin)();
    if (stdin.isNotEmpty &&
        stdin.last == 0 &&
        stdin.where((byte) => byte == 0).length == 2) {
      stdin = [...stdin, 0];
    }
    final handoff = parseHandoff(stdin, _handoffUsage);
    document = await runReviewOperation(
      scriptsDir: handoff.scriptsDir,
      bash: handoff.bash,
      argv: handoff.argv,
    );
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
