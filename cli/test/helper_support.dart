import 'dart:io';

import 'package:test/test.dart';

/// Compiles `bin/sw.dart` into [dir] (run from `cli/`) and returns the helper
/// command line, `<sw> __exec`. The helper needs a real executable: it is
/// identified by its own process, which `dart bin/sw.dart` is not on Windows.
Future<List<String>> buildHelper(Directory dir) async {
  final sw =
      '${dir.path}${Platform.pathSeparator}sw${Platform.isWindows ? '.exe' : ''}';
  final result = await Process.run(Platform.resolvedExecutable, [
    'compile',
    'exe',
    '--define=SW_VERSION=test',
    '-o',
    sw,
    'bin/sw.dart',
  ]);
  expect(result.exitCode, 0, reason: '${result.stdout}${result.stderr}');
  return [sw, '__exec'];
}
