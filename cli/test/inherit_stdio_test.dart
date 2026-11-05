// Verifies assumption A5 of the native-cli-spike design: a helper process that
// starts the command with ProcessStartMode.inheritStdio hands over its stdout,
// stderr and (the rest of) its stdin pipe, and a one-byte stdin read does not
// buffer past that byte.
@Tags(['process'])
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:test/test.dart';

const _helperSource = r'''
import 'dart:io';

Future<void> main(List<String> args) async {
  final go = stdin.readByteSync();
  if (go != 0x67) exit(9);
  final p = await Process.start(
    Platform.resolvedExecutable,
    [args[0]],
    mode: ProcessStartMode.inheritStdio,
  );
  if (args[1] == 'exit-first') exit(0);
  exit(await p.exitCode);
}
''';

const _childSource = r'''
import 'dart:convert';
import 'dart:io';

Future<void> main() async {
  final rest = <int>[];
  int b;
  while ((b = stdin.readByteSync()) != -1) {
    rest.add(b);
  }
  stdout.writeln('child-got:' + utf8.decode(rest));
  stderr.writeln('child-err');
  await stdout.flush();
  await Future<void>.delayed(const Duration(milliseconds: 1500));
  stdout.writeln('child-late');
}
''';

void main() {
  late Directory dir;
  late String helper;
  late String child;

  setUpAll(() {
    dir = Directory.systemTemp.createTempSync('sw-g4-inherit-');
    helper = '${dir.path}${Platform.pathSeparator}helper.dart';
    child = '${dir.path}${Platform.pathSeparator}child.dart';
    File(helper).writeAsStringSync(_helperSource);
    File(child).writeAsStringSync(_childSource);
  });

  tearDownAll(() => dir.deleteSync(recursive: true));

  Future<void> check(String mode) async {
    final p = await Process.start(Platform.resolvedExecutable, [
      helper,
      child,
      mode,
    ]);
    final events = <String>[];
    final out = StringBuffer();
    final err = StringBuffer();
    final outDone = p.stdout
        .transform(utf8.decoder)
        .forEach(out.write)
        .then((_) => events.add('stdout-eof'));
    final errDone = p.stderr.transform(utf8.decoder).forEach(err.write);
    final exited = p.exitCode.then((c) {
      events.add('helper-exit');
      return c;
    });
    // 'g' is what the helper reads; the rest must reach the child as its stdin.
    p.stdin.add(utf8.encode('gTRANSPORT-BYTES'));
    await p.stdin.close();
    expect(await exited, 0);
    await Future.wait([outDone, errDone]);
    expect(out.toString(), contains('child-got:TRANSPORT-BYTES'));
    expect(out.toString(), contains('child-late'));
    expect(err.toString(), contains('child-err'));
    // stdout reaches EOF only once the child (the last holder) is done: with
    // the helper gone first, the EOF is the last event.
    if (mode == 'exit-first') {
      expect(events, ['helper-exit', 'stdout-eof']);
    } else {
      expect(events, unorderedEquals(['helper-exit', 'stdout-eof']));
    }
  }

  test(
    'child keeps the helper pipes and reads the rest of stdin (helper waits)',
    () => check('wait'),
  );

  test(
    'stdout EOF waits for the child when the helper exits first',
    () => check('exit-first'),
  );
}
