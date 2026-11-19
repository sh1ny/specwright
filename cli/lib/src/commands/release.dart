import 'dart:io';

import '../release/commands.dart';
import '../vcs/document.dart' show documentBytes;

/// `sw release [--dir <repo>] <sub> [options]`: runs one release subcommand
/// from plain arguments in the current directory, writes exactly one JSON
/// document and returns its status (0 done, 1 a stop, 2 usage, 3 a git or
/// network call failed).
Future<int> runReleaseCommand(
  List<String> args, {
  required void Function(List<int> bytes) writeOut,
}) async {
  final outcome = await releaseOutcome(args, cwd: Directory.current.path);
  writeOut(documentBytes(outcome.document));
  return outcome.code;
}
