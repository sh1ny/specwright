import 'dart:convert';
import 'dart:io';

import 'package:specwright_cli/src/pr/context.dart';
import 'package:specwright_cli/src/process/limit_line.dart' show BoundedLimit;
import 'package:specwright_cli/src/pr/gh.dart';
import 'package:specwright_cli/src/vcs/codec.dart';

/// A gh answer: exit 0 and [stdout] by default.
GhResult answer(
  String stdout, {
  int exit = 0,
  String stderr = '',
  String? limitLine,
  BoundedLimit? limit,
}) => GhResult(
  exitCode: exit,
  stdout: encodeEscaped(stdout),
  stderr: encodeEscaped(stderr),
  limitLine: limitLine,
  limit: limit,
);

/// What the commands ran against, with every call recorded: the answers come from [onGh], the temp files from
/// [tempDir] and the pauses from [onSleep] (the clock moves by each one).
class Fixture {
  Fixture({
    this.onGh,
    this.onSleep,
    this.onBounded,
    Directory? temp,
    Map<String, String>? environment,
  }) : tempDir = temp ?? Directory.systemTemp.createTempSync('sw-pr-test-') {
    ctx = PrContext(
      scriptsDir: 'scripts',
      bash: 'bash',
      writeOut: out.addAll,
      writeErr: err.addAll,
      environment: environment,
      seconds: () => clock,
      bounded: (command, {environment}) async {
        boundedCalls.add(command);
        boundedEnvs.add(environment);
        final r = onBounded?.call(command);
        if (r == null) throw StateError('unexpected bounded call: $command');
        return r;
      },
      gh: (args, {environment, paged = false}) async {
        ghCalls.add(args);
        ghEnvs.add(environment);
        final r = onGh?.call(args);
        if (r == null) throw StateError('unexpected gh call: $args');
        return r;
      },
      sleep: (seconds) async {
        sleeps.add(seconds);
        clock += seconds;
        onSleep?.call(seconds);
      },
      makeTemp: ([template]) async {
        tempCalls.add(template);
        if (tempFails) return null;
        if (fixedTemp != null) return fixedTemp;
        final dir = template == null
            ? tempDir.path
            : template.substring(0, template.lastIndexOf('/'));
        final f = File('$dir/tmp.${++tempCount}')..createSync();
        return f.path;
      },
      cwd: tempDir.path,
    );
  }

  final Directory tempDir;
  final List<int> out = [];
  final List<int> err = [];
  final List<List<String>> ghCalls = [];
  final List<Map<String, String>?> ghEnvs = [];
  final List<int> sleeps = [];
  final List<List<String>> boundedCalls = [];
  final List<Map<String, String>?> boundedEnvs = [];
  final List<String?> tempCalls = [];
  GhResult Function(List<String> args)? onGh;
  GhResult Function(List<String> command)? onBounded;

  /// The monotonic seconds the command sees (`$SECONDS`); each pause moves it.
  int clock = 0;
  void Function(int seconds)? onSleep;
  bool tempFails = false;
  String? fixedTemp;
  int tempCount = 0;
  late final PrContext ctx;

  String get stdout => decodeEscaped(out);
  String get stderr => decodeEscaped(err);

  void dispose() => tempDir.deleteSync(recursive: true);

  /// Files left in the temp directory.
  List<String> get leftovers => [
    for (final e in tempDir.listSync()) e.uri.pathSegments.last,
  ];

  File file(String name, String text) =>
      File('${tempDir.path}/$name')..writeAsBytesSync(utf8.encode(text));
}
