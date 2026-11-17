import '../update/options.dart';
import '../vcs/document.dart' show documentBytes;

/// `sw update <subcommand> [options]`: the update lifecycle that
/// `scripts/update.sh` carried (design D1 of native-cli-update). Writes
/// exactly one JSON document and returns its status: 0 done, 1 a stop, 2
/// usage.
///
/// Only `interface` and the option rules are here so far: every other
/// subcommand validates its options and then stops with `not_implemented`
/// until the later task groups fill it in.
Future<int> runUpdateCommand(
  List<String> args, {
  required void Function(List<int> bytes) writeOut,
  String? cwd,
}) async {
  final UpdateOptions options;
  try {
    options = parseUpdateOptions(args, cwd: cwd);
  } on UpdateUsage catch (usage) {
    writeOut(documentBytes(usage.document()));
    return 2;
  }
  if (options.subcommand == 'interface') {
    // D11: reads and writes nothing else. No journal recovery, no lock, no
    // settings: the prompt runs it on the checked temporary binary before
    // anything is placed.
    writeOut(documentBytes({'ok': true, 'interface': updateInterface}));
    return 0;
  }
  writeOut(
    documentBytes({
      'ok': false,
      'interface': updateInterface,
      'subcommand': options.subcommand,
      'error': 'not_implemented',
      'message': 'sw update ${options.subcommand} is not implemented yet',
    }),
  );
  return 1;
}
