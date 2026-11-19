import 'dart:io' show Directory;

import 'package:args/args.dart';

import '../gate/lock.dart';
import '../update/git.dart' show runUpdateGit;
import '../update/text.dart' show pyStrip, resolvePosix;
import '../vcs/document.dart' show documentBytes;

const _usage =
    'usage: sw gate lock --store <store> --branch <name> --code <code>\n'
    '       sw gate show --store <store>\n'
    '       sw gate unlock --store <store> (--token <token> | --stale '
    '(--token <token> | --ownerless))';

ArgParser _parser() => ArgParser()
  ..addOption('store')
  ..addOption('branch')
  ..addOption('code')
  ..addOption('token')
  ..addFlag('stale', negatable: false)
  ..addFlag('ownerless', negatable: false);

/// `sw gate lock|show|unlock` (design D6): the store gate lock, in the form
/// `sw update` and the earlier shell lock use. Writes one JSON document and
/// returns its status: 0 done, 1 a stop, 2 usage.
Future<int> runGateCommand(
  List<String> args, {
  required void Function(List<int> bytes) writeOut,
}) async {
  int usage(String why) {
    writeOut(
      documentBytes({
        'ok': false,
        'error': 'usage',
        'message': '$why\n$_usage',
      }),
    );
    return 2;
  }

  if (args.isEmpty || !{'lock', 'show', 'unlock'}.contains(args.first)) {
    return usage('gate needs lock, show or unlock');
  }
  final sub = args.first;
  final ArgResults options;
  try {
    options = _parser().parse(args.sublist(1));
  } on FormatException catch (e) {
    return usage(e.message);
  }
  final store = options['store'] as String?;
  final branch = options['branch'] as String?;
  final code = options['code'] as String?;
  final token = options['token'] as String?;
  final stale = options['stale'] as bool;
  final ownerless = options['ownerless'] as bool;
  if (options.rest.isNotEmpty) return usage('unexpected ${options.rest.first}');
  if (store == null || store.isEmpty) return usage('--store is required');
  if (sub == 'lock' && (branch == null || code == null)) {
    return usage('lock needs --branch and --code');
  }
  if (sub == 'unlock') {
    final valid = stale
        ? ownerless != (token != null)
        : token != null && !ownerless;
    if (!valid) {
      return usage(
        'unlock needs --token, or --stale with --token or --ownerless',
      );
    }
  }
  // git runs with the store as its working directory and `-C`: a relative
  // path would be applied twice, so it is made absolute first.
  final storeDir = Directory(store).absolute.path;
  final git = await runUpdateGit(storeDir, ['rev-parse', '--git-common-dir']);
  final common = pyStrip(git.text);
  if (!git.ok || common.isEmpty) {
    writeOut(
      documentBytes({
        'ok': false,
        'error': 'not_a_repo',
        'message': '$store is not inside a Git repository',
      }),
    );
    return 1;
  }
  final absolute =
      common.startsWith('/') ||
      common.startsWith(r'\') ||
      RegExp(r'^[A-Za-z]:').hasMatch(common);
  final lock =
      '${resolvePosix(absolute ? common : '$storeDir/$common')}'
      '/specwright-gate.lock';
  final (Map<String, Object?> document, int status) = switch (sub) {
    'lock' => gateLock(lock, branch!, code!),
    'show' => (gateShow(lock), 0),
    _ => gateUnlock(lock, token: token, stale: stale, ownerless: ownerless),
  };
  writeOut(documentBytes(document));
  return status;
}
