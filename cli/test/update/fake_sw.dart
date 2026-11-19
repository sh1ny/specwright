import 'dart:io';

import 'package:specwright_cli/src/commands/version.dart' show interfaceVersion;
import 'package:test/test.dart';

/// Compiles `fixtures/fake_sw_main.dart` once (run from `cli/`) into [dir]
/// and returns the path of the executable. [version] and [interface] are what
/// it reports when no `fake_sw.txt` stands beside it (the interface is the
/// running sw's by default); [name] tells two
/// compiled variants apart.
Future<String> compileFakeSw(
  Directory dir, {
  String name = 'fake-sw',
  String version = '0.37.0',
  int interface = interfaceVersion,
}) async {
  final out = '${dir.path}/$name${Platform.isWindows ? '.exe' : ''}';
  final result = await Process.run(Platform.resolvedExecutable, [
    'compile',
    'exe',
    '--define=FAKE_VERSION=$version',
    '--define=FAKE_INTERFACE=$interface',
    '-o',
    out,
    'test/update/fixtures/fake_sw_main.dart',
  ]);
  expect(result.exitCode, 0, reason: '${result.stdout}${result.stderr}');
  return out;
}

/// Puts a copy of the compiled fake sw at `<dir>/<name>` (a missing [dir] is
/// made) and returns that path. [config] is the content of `fake_sw.txt`
/// beside it; the default reports [version] at the running sw's interface.
String installFakeSw(
  String compiled,
  String dir,
  String name, {
  String version = '0.37.0',
  String? config,
}) {
  Directory(dir).createSync(recursive: true);
  final path = '$dir/$name';
  File(compiled).copySync(path);
  File('$dir/fake_sw.txt').writeAsStringSync(
    config ?? 'print\n{"version":"$version","interface":$interfaceVersion}\n',
  );
  return path;
}

/// Puts a copy of the compiled fake sw at `<dir>/<name>` with no
/// `fake_sw.txt`, so that it reports what it was compiled to report wherever
/// it is moved. Returns that path.
String copyFakeSw(String compiled, String dir, String name) {
  Directory(dir).createSync(recursive: true);
  final path = '$dir/$name';
  File(compiled).copySync(path);
  return path;
}
