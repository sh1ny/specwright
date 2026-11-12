import 'dart:io';

import 'package:test/test.dart';

import '../vcs/bash_support.dart';

/// Windows resolves commands through PATHEXT only (design D9), so an
/// extensionless script fake named `but`, `git` or `cygpath` is not found. This
/// compiles one small Dart shim per test process; [shimExe] then copies it as
/// `<fake>.exe` beside a fake, and the copy runs the script beside it (its own
/// path minus `.exe`) through Git Bash with the same arguments, stdin, stdout,
/// stderr and exit code. Off Windows every call is a no-op.
///
/// Call [useExeShim] once at the top of `main()`.
Directory? _shimDir;
File? _shim;

const _source = r'''
import 'dart:io';

Future<void> main(List<String> args) async {
  const bash = String.fromEnvironment('SHIM_BASH');
  final me = Platform.resolvedExecutable;
  final script = me.substring(0, me.length - '.exe'.length);
  final p = await Process.start(
    bash,
    [script.replaceAll(r'\', '/'), ...args],
    mode: ProcessStartMode.inheritStdio,
  );
  exit(await p.exitCode);
}
''';

/// Registers the per-process compile and its cleanup for this test file.
void useExeShim() {
  if (!Platform.isWindows) return;
  setUpAll(() async {
    final bash = findBash();
    if (bash == null) return;
    final dir = Directory.systemTemp.createTempSync('sw-exe-shim-');
    _shimDir = dir;
    final src = File('${dir.path}/shim.dart')..writeAsStringSync(_source);
    final out = File('${dir.path}/shim.exe');
    final r = await Process.run(Platform.resolvedExecutable, [
      'compile',
      'exe',
      '-DSHIM_BASH=$bash',
      '-o',
      out.path,
      src.path,
    ]);
    expect(r.exitCode, 0, reason: '${r.stdout}${r.stderr}');
    _shim = out;
  });
  tearDownAll(() {
    final dir = _shimDir;
    if (dir != null && dir.existsSync()) dir.deleteSync(recursive: true);
    _shimDir = null;
    _shim = null;
  });
}

/// Puts `<fake>.exe` beside the script [fake] on Windows; does nothing
/// elsewhere. The script must already be written.
void shimExe(String fake) {
  final shim = _shim;
  if (!Platform.isWindows || shim == null) return;
  shim.copySync('$fake.exe');
}
