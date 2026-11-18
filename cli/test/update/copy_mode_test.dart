// Verifies assumption A2 of the native-cli-update design on POSIX.
//
// A2: `File.copy` keeps the source's POSIX mode bits, as `cp` without `-p`
// does, so a staged `.sh` file stays executable. If this fails, staging sets
// the mode explicitly (task 5.1).
@TestOn('linux || mac-os')
library;

import 'dart:io';

import 'package:test/test.dart';

void main() {
  late Directory temp;

  setUp(() {
    temp = Directory.systemTemp.createTempSync('sw-copy-mode-');
  });

  tearDown(() {
    temp.deleteSync(recursive: true);
  });

  for (final mode in ['755', '700', '644']) {
    test('A2: File.copy keeps mode $mode', () async {
      final source = File('${temp.path}/source.sh')
        ..writeAsStringSync('#!/bin/sh\necho hi\n');
      final chmod = await Process.run('chmod', [mode, source.path]);
      expect(chmod.exitCode, 0, reason: '${chmod.stderr}');
      final copy = await source.copy('${temp.path}/copy.sh');
      final want = int.parse(mode, radix: 8);
      expect(source.statSync().mode & 0x1ff, want);
      expect(copy.statSync().mode & 0x1ff, want);
    });
  }
}
