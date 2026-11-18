import 'dart:io';

import 'package:specwright_cli/src/cli.dart';
import 'package:specwright_cli/src/entry/raw_arguments.dart';
import 'package:specwright_cli/src/vcs/document.dart';

Future<void> main(List<String> args) async {
  // Before any other work: an argument that is not well-formed Unicode as it
  // reached the process stops here (native-cli "Arguments sw cannot
  // represent are refused").
  final bad = firstUnrepresentableArgument(args);
  if (bad != null) {
    stdout.add(
      documentBytes({
        'ok': false,
        'error': 'bad_argument',
        'message': 'argument $bad is not well-formed Unicode',
      }),
    );
    await stdout.flush();
    exit(2);
  }
  final code = await runCli(args, out: stdout, err: stderr);
  await stdout.flush();
  await stderr.flush();
  // exit, not just exitCode: the helper reads stdin synchronously and nothing
  // may keep the process alive once its command is done.
  exit(code);
}
