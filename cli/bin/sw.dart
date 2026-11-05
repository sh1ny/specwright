import 'dart:io';

import 'package:specwright_cli/src/cli.dart';

Future<void> main(List<String> args) async {
  exitCode = await runCli(args, out: stdout, err: stderr);
}
