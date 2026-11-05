// Compiles cli/bin/sw.dart to cli/build/sw (sw.exe on Windows) with the
// version from the repository VERSION file. Run from anywhere:
//   dart run cli/tool/build.dart
import 'dart:io';

Future<void> main() async {
  final cliDir = File.fromUri(Platform.script).parent.parent;
  final version = File.fromUri(cliDir.uri.resolve('../VERSION'))
      .readAsStringSync()
      .trim();
  final buildDir = Directory.fromUri(cliDir.uri.resolve('build/'))
    ..createSync(recursive: true);
  // buildDir.path already ends with a path separator.
  final out = '${buildDir.path}sw${Platform.isWindows ? '.exe' : ''}';
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
  stdout.writeln(out);
}
