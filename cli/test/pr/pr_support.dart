import 'dart:convert';
import 'dart:io';

import 'package:specwright_cli/src/pr/context.dart';
import 'package:specwright_cli/src/process/limit_line.dart' show BoundedLimit;
import 'package:specwright_cli/src/pr/gh.dart';
import 'package:specwright_cli/src/vcs/codec.dart';
import 'package:specwright_cli/src/vcs/text_result.dart';

/// A gh answer: exit 0 and [stdout] by default. [merged] is the combined
/// output of a call that ran in merged mode (the `--log-failed` call): its
/// stdout and stderr stay empty, as `runGh` returns them.
GhResult answer(
  String stdout, {
  int exit = 0,
  String stderr = '',
  String? limitLine,
  BoundedLimit? limit,
  String? merged,
}) => GhResult(
  exitCode: exit,
  stdout: utf8.encode(stdout),
  stderr: utf8.encode(stderr),
  limitLine: limitLine,
  limit: limit,
  merged: merged == null ? null : utf8.encode(merged),
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
    writeAmbientSettings(tempDir);
    ctx = PrContext(
      writeOut: out.addAll,
      writeErr: err.addAll,
      environment: environment,
      git: (_, args) async => switch (args.join(' ')) {
        'rev-parse --show-toplevel' => TextResult(0, tempDir.path, ''),
        'rev-parse --git-dir' => TextResult(0, '.git', ''),
        'symbolic-ref --quiet --short HEAD' => TextResult(0, 'feature', ''),
        'remote' => TextResult(0, 'origin\n', ''),
        'remote get-url origin' || 'remote get-url --push --all origin' =>
          TextResult(0, 'https://github.com/o/n.git\n', ''),
        _ => throw StateError('unexpected Git call: $args'),
      },
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

  String get stdout => decodeReplacing(out);
  String get stderr => decodeReplacing(err);

  void dispose() => tempDir.deleteSync(recursive: true);

  /// Files left in the temp directory.
  List<String> get leftovers => [
    for (final e in tempDir.listSync())
      if (!e.path.endsWith('${Platform.pathSeparator}openspec'))
        e.uri.pathSegments.last,
  ];

  File file(String name, String text) =>
      File('${tempDir.path}/$name')..writeAsBytesSync(utf8.encode(text));
}

/// I/O fixtures exercise transport after authentication, under an explicit
/// caller account (the equivalent of the frozen workflow's token input).
void writeAmbientSettings(Directory root) {
  File('${root.path}/openspec/specwright.yaml')
    ..createSync(recursive: true)
    ..writeAsStringSync('github:\n  fence: false\n');
}
