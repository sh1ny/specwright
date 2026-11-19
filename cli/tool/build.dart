// Compiles cli/bin/sw.dart with SW_VERSION set. Run from anywhere:
//   dart run cli/tool/build.dart [--version <v>] [--output <file>]
//       [--install [--expect-update-interface <n>] [--interface-from <file>]]
// Without options it reads the repository VERSION file and writes
// cli/build/sw (sw.exe on Windows). `--version` and `--output` build another
// version to another file, for the eval fixtures.
//
// `--install` builds to a temporary path inside cli/build/, then runs that
// binary as `sw update sw-install --build <it> --download <this tree>`, which
// checks its version, places it with THIRD_PARTY_NOTICES.txt at
// <home>/.specwright/bin/<VERSION>/ and prints the placed path. With
// `--expect-update-interface <n>` it first runs the built binary's
// `sw update interface`: a different number, or a failed run, deletes the
// build and stops before anything is placed. It also runs the built binary's
// `version --json` and compares its workflow `interface` with the
// `interface <n>` line of the tree's skills/specwright-pr/SKILL.md (or of
// `--interface-from <file>`); a different number deletes the build and stops
// before anything is placed. `mise run install-sw` runs this.
// It first regenerates cli/lib/src/review/references.g.dart from the review
// skill's references (cli/tool/references.dart). No bash is started: only the
// Dart SDK and the built binary.
import 'dart:convert';
import 'dart:io';

import 'references.dart';

Never _fail(String message, [int code = 1]) {
  stderr.writeln(message);
  exit(code);
}

Future<void> main(List<String> args) async {
  String? version, output, expect, interfaceFrom;
  var install = false;
  for (var i = 0; i < args.length; i++) {
    final arg = args[i];
    String value() {
      if (i + 1 >= args.length) _fail('$arg needs a value', 2);
      return args[++i];
    }

    switch (arg) {
      case '--version':
        version = value();
      case '--output':
        output = value();
      case '--expect-update-interface':
        expect = value();
      case '--interface-from':
        interfaceFrom = value();
      case '--install':
        install = true;
      default:
        _fail('unknown option $arg', 2);
    }
  }
  if (expect != null && !install) {
    _fail('--expect-update-interface goes with --install', 2);
  }
  if (interfaceFrom != null && !install) {
    _fail('--interface-from goes with --install', 2);
  }

  final cliDir = File.fromUri(Platform.script).parent.parent;
  final treeDir = cliDir.parent;
  version ??= File.fromUri(cliDir.uri.resolve('../VERSION'))
      .readAsStringSync()
      .trim();
  final buildDir = Directory.fromUri(cliDir.uri.resolve('build/'))
    ..createSync(recursive: true);
  final ext = Platform.isWindows ? '.exe' : '';
  // buildDir.path already ends with a path separator.
  final temporary = install && output == null;
  final out =
      output ??
      (temporary
          ? '${buildDir.path}.install-$pid$ext'
          : '${buildDir.path}sw$ext');
  // D9: the built-in review references come from the skill's files.
  writeReferences(treeDir);
  final result = await Process.run(Platform.resolvedExecutable, [
    'compile',
    'exe',
    '--define=SW_VERSION=$version',
    '-o',
    out,
    'bin/sw.dart',
  ], workingDirectory: cliDir.path);
  stdout.write(result.stdout);
  stderr.write(result.stderr);
  if (result.exitCode != 0) exit(result.exitCode);
  if (!install) {
    stdout.writeln(out);
    return;
  }

  void discard() {
    final file = File(out);
    if (file.existsSync()) file.deleteSync();
  }

  try {
    final pinFile = File(
      interfaceFrom ??
          treeDir.uri.resolve('skills/specwright-pr/SKILL.md').toFilePath(),
    );
    final pin = _pinnedInterface(pinFile);
    if (pin == null) {
      discard();
      _fail(
        'no "interface <n>" line in ${pinFile.path}, so the workflow '
        'interface of the build cannot be checked; nothing was placed',
      );
    }
    final reported = await Process.run(out, ['version', '--json']);
    Object? workflow;
    try {
      workflow = (jsonDecode(
        reported.stdout as String,
      ) as Map<String, Object?>)['interface'];
    } on Object {
      workflow = null;
    }
    if ('$workflow' != pin) {
      discard();
      _fail(
        'the build reports workflow interface $workflow, but the skills in '
        '${pinFile.path} require interface $pin; nothing was placed',
      );
    }
    if (expect != null) {
      final probe = await Process.run(out, ['update', 'interface']);
      Object? found;
      if (probe.exitCode == 0) {
        try {
          found = (jsonDecode(
            probe.stdout as String,
          ) as Map<String, Object?>)['interface'];
        } on Object {
          found = null;
        }
      }
      if ('$found' != expect) {
        discard();
        _fail(
          found == null
              ? 'the build has no update interface (sw update interface '
                    'failed), expected $expect; nothing was placed'
              : 'the build reports update interface $found, expected '
                    '$expect; nothing was placed',
        );
      }
    }
    final placed = await Process.run(out, [
      'update',
      'sw-install',
      '--build',
      out,
      '--download',
      treeDir.path,
    ]);
    Object? doc;
    try {
      doc = jsonDecode(placed.stdout as String);
    } on Object {
      doc = null;
    }
    if (placed.exitCode != 0 || doc is! Map || doc['ok'] != true) {
      stderr.write(placed.stdout);
      stderr.write(placed.stderr);
      discard();
      exit(placed.exitCode == 0 ? 1 : placed.exitCode);
    }
    stdout.writeln(doc['path']);
  } finally {
    if (temporary) discard();
  }
}

/// The number on the `interface <n>` line of the pr skill, or null.
String? _pinnedInterface(File file) {
  if (!file.existsSync()) return null;
  final match = RegExp(
    r'^interface (\d+)\s*$',
    multiLine: true,
  ).firstMatch(file.readAsStringSync());
  return match?.group(1);
}
