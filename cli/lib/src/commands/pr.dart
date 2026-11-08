import '../pr/context.dart';
import '../pr/identity.dart';
import '../pr/policy.dart';
import '../pr/settings_commands.dart';
import '../pr/reviewers.dart';
import '../pr/reply.dart';
import '../pr/snapshot.dart';
import 'vcs.dart' show readAllStdin;

/// The commands that take the shim's handoff on stdin.
const List<String> _handoffCommands = [
  'snapshot',
  'reply',
  'identity',
  'vcs',
  'tier',
  'context',
  'policy',
];

final String _usage = 'usage: sw pr ${_handoffCommands.join('|')} --args-stdin';

final String _handoffUsage =
    'usage: sw pr ${_handoffCommands.join('|')} --args-stdin (stdin: scripts dir, bash path, then '
    "the script's arguments, each record ending in a NUL byte)";

/// `sw pr reviewers` (on argv: no shim calls it, `sw pr snapshot` runs it as a bounded child), and
/// `sw pr snapshot|reply|identity|vcs|tier|context|policy --args-stdin`: the shims of `pr-snapshot.sh`, `pr-reply.sh` and
/// `pr-pair.sh` hand over the scripts directory, their bash and every script argument as NUL-terminated records. [context] builds what the
/// command runs against (default: real `gh` and tools). Returns the script's exit code; a call that is not one of the two
/// forms, or a handoff that is not records, exits 2 with a usage line.
Future<int> runPrCommand(
  List<String> args, {
  required void Function(List<int> bytes) writeOut,
  required void Function(List<int> bytes) writeErr,
  Future<List<int>> Function()? readStdin,
  PrContext Function(String scriptsDir, String bash)? context,
}) async {
  if (args.isNotEmpty && args[0] == 'reviewers') {
    return runReviewers(
      args.sublist(1),
      writeOut: writeOut,
      writeErr: writeErr,
    );
  }
  void usage(String text) => writeErr('$text\n'.codeUnits);
  if (args.length != 2 ||
      args[1] != '--args-stdin' ||
      !_handoffCommands.contains(args[0])) {
    usage(_usage);
    return 2;
  }
  final handoff = parsePrHandoff(await (readStdin ?? readAllStdin)());
  if (handoff == null) {
    usage(_handoffUsage);
    return 2;
  }
  final ctx =
      context?.call(handoff.scriptsDir, handoff.bash) ??
      PrContext(
        scriptsDir: handoff.scriptsDir,
        bash: handoff.bash,
        writeOut: writeOut,
        writeErr: writeErr,
      );
  return switch (args[0]) {
    'snapshot' => runSnapshot(ctx, handoff.args),
    'reply' => runReply(ctx, handoff.args),
    'identity' => runIdentity(ctx, handoff.args),
    'vcs' => runVcs(ctx, handoff.args),
    'tier' => runTier(ctx, handoff.args),
    'context' => runContext(ctx, handoff.args),
    _ => runPolicy(ctx, handoff.args),
  };
}
