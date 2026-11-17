import '../update/options.dart';
import '../update/stop.dart';
import '../update/sw_install.dart';
import '../vcs/document.dart' show documentBytes;

/// `sw update <subcommand> [options]`: the update lifecycle that
/// `scripts/update.sh` carried (design D1 of native-cli-update). Writes
/// exactly one JSON document and returns its status: 0 done, 1 a stop, 2
/// usage.
///
/// Only `interface`, `sw-install` and the option rules are here so far: every
/// other subcommand validates its options and then stops with
/// `not_implemented` until the later task groups fill it in. [environment]
/// (default: the process environment) is where `sw-install` reads
/// `SPECWRIGHT_HOME`, the proxy variables and the test seams from.
Future<int> runUpdateCommand(
  List<String> args, {
  required void Function(List<int> bytes) writeOut,
  String? cwd,
  Map<String, String>? environment,
  void Function(int code)? exitProcess,
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
  if (options.subcommand == 'sw-install') {
    try {
      writeOut(
        documentBytes(
          await swInstall(
            options,
            environment: environment,
            exitProcess: exitProcess,
          ),
        ),
      );
      return 0;
    } on UpdateUsage catch (usage) {
      writeOut(documentBytes(usage.document()));
      return 2;
    } on UpdateStop catch (stop) {
      writeOut(
        documentBytes({
          'ok': false,
          'interface': updateInterface,
          'subcommand': 'sw-install',
          'error': stop.code,
          'message': stop.message,
        }),
      );
      return 1;
    }
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
