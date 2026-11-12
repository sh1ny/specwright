// `runWithCommandLine` with an environment block and a working directory: the
// child sees exactly the variables it is given, in the directory it is given.
@TestOn('windows')
@Tags(['process', 'windows'])
library;

import 'dart:convert';
import 'dart:io';

import 'package:specwright_cli/src/native/kernel32.dart' as k32;
import 'package:test/test.dart';

/// Writes its environment and directory as JSON to the file named by its first
/// argument, and exits with 9.
const _reporter = r'''
import 'dart:convert';
import 'dart:io';

void main(List<String> args) {
  File(args[0]).writeAsStringSync(
    jsonEncode({'env': Platform.environment, 'cwd': Directory.current.path}),
  );
  exit(9);
}
''';

void main() {
  late Directory dir;
  late Directory work;
  late File script;
  late File out;

  setUp(() {
    dir = Directory.systemTemp.createTempSync('sw-k32-');
    work = Directory('${dir.path}\\work dir é')..createSync();
    script = File('${dir.path}\\reporter.dart')..writeAsStringSync(_reporter);
    out = File('${dir.path}\\out.json');
  });
  tearDown(() => dir.deleteSync(recursive: true));

  String line() =>
      '"${Platform.resolvedExecutable}" "${script.path}" "${out.path}"';

  Map<String, dynamic> report() =>
      jsonDecode(out.readAsStringSync()) as Map<String, dynamic>;

  test('the child sees exactly the given variables', () {
    final env = {
      'SystemRoot': Platform.environment['SystemRoot'] ?? r'C:\Windows',
      'SW_A': '1',
      'SW_B': 'é€ "x" \$y',
      'SW_EMPTY': '',
    };
    final r = k32.runWithCommandLine(
      Platform.resolvedExecutable,
      line(),
      environment: env,
    );
    expect(r.status, 9, reason: 'error ${r.error}');
    final seen = (report()['env'] as Map<String, dynamic>).map(
      (k, v) => MapEntry(k.toUpperCase(), v as String),
    );
    expect(seen, {for (final e in env.entries) e.key.toUpperCase(): e.value});
  });

  test('the child starts in the given directory', () {
    final r = k32.runWithCommandLine(
      Platform.resolvedExecutable,
      line(),
      environment: {
        'SystemRoot': Platform.environment['SystemRoot'] ?? r'C:\Windows',
      },
      workingDirectory: work.path,
    );
    expect(r.status, 9, reason: 'error ${r.error}');
    expect(
      Directory(report()['cwd'] as String).resolveSymbolicLinksSync(),
      work.resolveSymbolicLinksSync(),
    );
  });

  test('without them the child inherits this process\'s', () {
    final r = k32.runWithCommandLine(Platform.resolvedExecutable, line());
    expect(r.status, 9, reason: 'error ${r.error}');
    final seen = report();
    expect(
      Directory(seen['cwd'] as String).resolveSymbolicLinksSync(),
      Directory.current.resolveSymbolicLinksSync(),
    );
    expect(
      (seen['env'] as Map<String, dynamic>).keys.map((k) => k.toUpperCase()),
      containsAll(['PATH', 'SYSTEMROOT']),
    );
  });

  test('a program that cannot be created has no status', () {
    final r = k32.runWithCommandLine(
      '${dir.path}\\no-such.exe',
      '"${dir.path}\\no-such.exe"',
      environment: const {},
    );
    expect(r.status, isNull);
  });
}
