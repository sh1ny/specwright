import 'dart:io';

import 'package:specwright_cli/src/cli.dart';

Future<void> main(List<String> args) async {
  final code = await runCli(args, out: stdout, err: stderr);
  await stdout.flush();
  await stderr.flush();
  // exit, not just exitCode: the helper reads stdin synchronously and nothing
  // may keep the process alive once its command is done.
  exit(code);
}
