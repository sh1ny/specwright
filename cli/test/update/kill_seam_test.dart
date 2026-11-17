// Verifies assumption A3 of the native-cli-update design.
//
// A3: `exit(137)` ends the process without running pending `finally` blocks
// and without flushing journal writes that have not happened yet, so the
// kill seam (D3) reproduces an external kill between file operations.
import 'dart:io';

import 'package:test/test.dart';

const _helper = r'''
import 'dart:io';

Future<void> main(List<String> args) async {
  final dir = args[0];
  final journal = File('$dir/update.json');
  // A write that happened: synchronous, on disk before the kill.
  journal.writeAsStringSync('{"format":2,"phase":"staged"}\n', flush: true);
  // A write that has not happened yet: buffered in a sink, never flushed.
  final sink = journal.openWrite(mode: FileMode.append);
  sink.write('{"phase":"swapping"}\n');
  try {
    exit(137);
  } finally {
    File('$dir/marker').writeAsStringSync('finally ran');
  }
}
''';

void main() {
  late Directory temp;

  setUp(() {
    temp = Directory.systemTemp.createTempSync('sw-kill-seam-');
  });

  tearDown(() {
    temp.deleteSync(recursive: true);
  });

  test('A3: exit(137) runs no finally and flushes no pending write', () async {
    final script = File('${temp.path}/helper.dart')..writeAsStringSync(_helper);
    final work = Directory('${temp.path}/work')..createSync();
    final result = await Process.run(Platform.resolvedExecutable, [
      'run',
      script.path,
      work.path,
    ]);
    expect(result.exitCode, 137, reason: '${result.stdout}${result.stderr}');
    expect(File('${work.path}/marker').existsSync(), isFalse);
    expect(
      File('${work.path}/update.json').readAsStringSync(),
      '{"format":2,"phase":"staged"}\n',
    );
  });
}
