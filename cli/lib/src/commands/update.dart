import 'dart:io' show FileSystemException;

import '../update/file_ops.dart';
import '../update/lifecycle.dart';
import '../update/recover.dart';
import '../update/stage.dart';
import '../update/swap.dart';
import '../update/openspec.dart';
import '../update/options.dart';
import '../update/pack_docs.dart';
import '../update/pack_verify.dart';
import '../update/packs.dart';
import '../update/plan.dart';
import '../update/stop.dart';
import '../update/sw_install.dart';
import '../vcs/document.dart' show documentBytes;

/// The subcommands that read the download tree. `update.sh` took the
/// directory above itself when `--download` was not given; `sw` has no script
/// directory, so these need it named (`sw-install` words its own need, because
/// a ref that is not a release tag reads no download).
const Set<String> _readsDownload = {
  'plan',
  'stage',
  'swap',
  'recover',
  'pack-check',
  'pack-verify',
  'pack-docs',
};

/// `sw update <subcommand> [options]`: the update lifecycle that
/// `scripts/update.sh` carried (design D1 of native-cli-update). Writes
/// exactly one JSON document and returns its status: 0 done, 1 a stop, 2
/// usage.
///
/// Every subcommand is here: `interface`, `plan`, `stage`, `swap`,
/// `note-config`, `finish`, `recover`, `pack-check`, `pack-verify`,
/// `pack-docs` and `sw-install`. [environment] (default: the process
/// environment) is where `sw-install` reads `SPECWRIGHT_HOME`, the proxy
/// variables and the test seams from. [fileOps] and [openspec] replace the
/// counting file-operation wrapper and the `openspec` runner (tests).
Future<int> runUpdateCommand(
  List<String> args, {
  required void Function(List<int> bytes) writeOut,
  String? cwd,
  Map<String, String>? environment,
  void Function(int code)? exitProcess,
  UpdateFileOps? fileOps,
  OpenspecRunner? openspec,
}) async {
  final UpdateOptions options;
  try {
    options = parseUpdateOptions(args, cwd: cwd);
  } on UpdateUsage catch (usage) {
    writeOut(documentBytes(usage.document()));
    return 2;
  }
  if (options.download == null && _readsDownload.contains(options.subcommand)) {
    // there is no script directory to default to: the download is named
    writeOut(
      documentBytes(
        UpdateUsage('${options.subcommand} needs --download DIR').document(),
      ),
    );
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
  if (options.subcommand == 'pack-check') {
    final (doc, status) = packCheckDocument(options);
    writeOut(documentBytes(doc));
    return status;
  }
  final run = UpdateRun(
    options,
    environment: environment,
    ops:
        fileOps ??
        UpdateFileOps(environment: environment, exitProcess: exitProcess),
    openspec: openspec,
  );
  if (options.subcommand == 'plan') {
    try {
      final (doc, status) = await planDocument(
        options,
        environment: run.environment,
        repo: run.repo,
        run: run.openspec,
        ops: run.ops,
        recover: planRecovery(run),
      );
      writeOut(documentBytes(doc));
      return status;
    } on UpdateDie catch (stop) {
      writeOut(documentBytes(dieDocument(run, stop)));
      return 1;
    } on UpdateStop catch (stop) {
      writeOut(
        documentBytes({
          'ok': false,
          'interface': updateInterface,
          'subcommand': 'plan',
          'error': stop.code,
          'message': stop.message,
        }),
      );
      return 1;
    }
  }
  final body = switch (options.subcommand) {
    'stage' => stageUpdate,
    'swap' => swapUpdate,
    'note-config' => noteConfig,
    'finish' => finishUpdate,
    'recover' => recoverUpdate,
    'pack-verify' => packVerify,
    'pack-docs' => packDocs,
    _ => null,
  };
  if (body != null) return _lifecycle(run, body, writeOut);
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

/// Runs one lifecycle subcommand and writes its document. A stop is the
/// `die` document of `update.sh`: the base members, `error`, `message` and the
/// stop's extras; a journal that cannot be read has no base members.
Future<int> _lifecycle(
  UpdateRun run,
  Future<(Map<String, Object?>, int)> Function(UpdateRun run) body,
  void Function(List<int> bytes) writeOut,
) async {
  try {
    final (doc, status) = await body(run);
    writeOut(documentBytes(doc));
    return status;
  } on UpdateStop catch (stop) {
    writeOut(documentBytes(dieDocument(run, UpdateDie.from(stop))));
    return 1;
  } on FileSystemException catch (e) {
    writeOut(
      documentBytes(
        dieDocument(
          run,
          UpdateDie(
            'file_operation_failed',
            'a file operation failed: ${e.message}'
                '${e.path == null ? '' : ' (${e.path})'}',
          ),
        ),
      ),
    );
    return 1;
  }
}
