// Compiles cli/bin/sw.dart with SW_VERSION set. Run from anywhere:
//   dart run cli/tool/build.dart [--version <v>] [--output <file>]
//       [--install [--expect-update-interface <n>]]
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
// build and stops before anything is placed. `mise run install-sw` runs this.
// No bash is started: only the Dart SDK and the built binary.
import 'dart:convert';
import 'dart:io';

Never _fail(String message, [int code = 1]) {
  stderr.writeln(message);
  exit(code);
}

Future<void> main(List<String> args) async {
  String? version, output, expect;
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
      case '--install':
        install = true;
      default:
        _fail('unknown option $arg', 2);
    }
  }
  if (expect != null && !install) {
    _fail('--expect-update-interface goes with --install', 2);
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
