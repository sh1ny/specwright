import '../pr/context.dart';
import '../pr/identity.dart';
import '../pr/policy.dart';
import '../pr/settings_commands.dart';
import '../pr/reviewers.dart';
import '../pr/reply.dart';
import '../pr/snapshot.dart';
import '../pr/workflow.dart';
import '../pr/pair.dart';

/// The commands `sw pr` runs besides `reviewers`.
const List<String> _commands = [
  'snapshot',
  'reply',
  'identity',
  'vcs',
  'tier',
  'context',
  'policy',
  'discover',
  'ensure-pr',
  'link',
  'expected',
  'pair-state',
  'rounds',
  'closing-check',
  'closed-check',
  'merge',
  'delete-remote',
  'item-issues',
  'pass',
  'cleanup-plan',
  'branch-check',
  'pair', // Internal entry that prints the pair usage.
];

final String _usage =
    'usage: sw pr reviewers|${_commands.join('|')} [arguments]';

/// `sw pr reviewers` (`sw pr snapshot` runs it as a bounded child) and `sw pr <command> [arguments]` for every other
/// command. [context] builds what the command runs against (default: real `gh` and tools). Returns the command's exit
/// code; a call that names no command exits 2 with a usage line.
Future<int> runPrCommand(
  List<String> args, {
  required void Function(List<int> bytes) writeOut,
  required void Function(List<int> bytes) writeErr,
  PrContext Function()? context,
}) async {
  if (args.isNotEmpty && args[0] == 'reviewers') {
    return runReviewers(
      args.sublist(1),
      writeOut: writeOut,
      writeErr: writeErr,
    );
  }
  if (args.isEmpty || !_commands.contains(args[0])) {
    writeErr('$_usage\n'.codeUnits);
    return 2;
  }
  final rest = args.sublist(1);
  final ctx =
      context?.call() ?? PrContext(writeOut: writeOut, writeErr: writeErr);
  return switch (args[0]) {
    'pair' => runPairCommand(ctx, () async {
      pairUsage(
        'subcommand: identity | context | tier | vcs | discover | expected | ensure-pr | closing-check | closed-check | link | pair-state | rounds | pass | cleanup-plan | branch-check | merge | delete-remote | policy | item-issues',
      );
    }),
    'snapshot' => runSnapshot(ctx, rest),
    'reply' => runReply(ctx, rest),
    'identity' => runIdentity(ctx, rest),
    'vcs' => runVcs(ctx, rest),
    'tier' => runTier(ctx, rest),
    'context' => runContext(ctx, rest),
    'discover' ||
    'ensure-pr' ||
    'link' ||
    'expected' ||
    'pair-state' ||
    'rounds' ||
    'closing-check' ||
    'closed-check' ||
    'merge' ||
    'delete-remote' ||
    'item-issues' ||
    'pass' ||
    'cleanup-plan' ||
    'branch-check' => runWorkflow(ctx, args[0], rest),
    _ => runPolicy(ctx, rest),
  };
}
