import 'dart:convert';

import 'package:args/args.dart';

import 'commands/version.dart';

const _usage =
    'usage: sw <command>\n'
    'commands:\n'
    '  version [--json]  print the sw version and interface version\n'
    '  run               run a command (not available yet)\n';

/// Runs sw with [args], writing to [out] and [err]; returns the exit code.
Future<int> runCli(
  List<String> args, {
  required StringSink out,
  required StringSink err,
}) async {
  final parser = ArgParser()
    ..addCommand('version', ArgParser()..addFlag('json', negatable: false))
    ..addCommand('run');
  final ArgResults results;
  try {
    results = parser.parse(args);
  } on ArgParserException {
    err.write(_usage);
    return 2;
  }
  final command = results.command;
  if (command == null || results.rest.isNotEmpty) {
    err.write(_usage);
    return 2;
  }
  switch (command.name) {
    case 'version':
      out.writeln(jsonEncode(versionReport()));
      return 0;
    default:
      err.write(_usage);
      return 2;
  }
}
