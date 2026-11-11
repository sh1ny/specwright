// A process that runs `runFenced` with this process's own stdio and
// environment, so `exec_inherit_test.dart` can give the fenced command a real
// stdin and read its stdout, stderr and exit status. Not a test.
import 'dart:io';

import 'package:specwright_cli/src/fence/exec_inherit.dart';

Future<void> main(List<String> args) async {
  exit(await runFenced(args, Map.of(Platform.environment)));
}
