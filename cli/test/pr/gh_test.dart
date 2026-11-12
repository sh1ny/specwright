@Tags(['process'])
library;

import 'dart:io';

import 'package:specwright_cli/src/pr/gh.dart';
import 'package:specwright_cli/src/process/limit_line.dart';
import 'package:specwright_cli/src/process/limits.dart';
import 'package:specwright_cli/src/vcs/codec.dart';
import 'package:test/test.dart';

import '../helper_support.dart';
import '../support/exe_shim.dart';

void main() {
  useExeShim();
  late Directory dir;
  late Map<String, String> env;
  // The real helper, compiled once.
  late Directory built;
  late List<String> helper;
  setUpAll(() async {
    built = Directory.systemTemp.createTempSync('sw-gh-helper-');
    helper = await buildHelper(built);
  });
  tearDownAll(() => built.deleteSync(recursive: true));
  const limits = RunLimits(deadline: Duration(seconds: 60), maxBytes: 1 << 20);

  // A fake `gh` first on PATH: a shell script, with an `.exe` shim beside it
  // on Windows, where only a PATHEXT name is found (D9).
  void fakeGh(String body) {
    final gh = File('${dir.path}/bin/gh')
      ..createSync(recursive: true)
      ..writeAsStringSync('#!/bin/sh\n$body\n');
    if (!Platform.isWindows) Process.runSync('chmod', ['+x', gh.path]);
    shimExe(gh.path);
  }

  setUp(() {
    dir = Directory.systemTemp.createTempSync('sw-gh-');
    final sep = Platform.isWindows ? ';' : ':';
    env = {...Platform.environment};
    env.removeWhere((k, _) => k.toLowerCase() == 'path');
    env['PATH'] =
        '${dir.path}${Platform.pathSeparator}bin$sep'
        '${Platform.environment['PATH'] ?? Platform.environment['Path'] ?? ''}';
  });
  tearDown(() => dir.deleteSync(recursive: true));

  Future<GhResult> gh(List<String> args, {RunLimits lim = limits}) => runGh(
    Directory.current.path,
    args,
    environment: env,
    limits: lim,
    helperCommand: helper,
  );

  // The fake prints each argument it got, NUL-terminated.
  const echoArgs = r'printf "%s\0" "$@"';

  group('runGh', () {
    test('every argument arrives whole, an empty one included', () async {
      fakeGh(echoArgs);
      final args = ['api', 'x y', '', '--jq', r'.a | "b" $c', 'e=f'];
      final r = await gh(args);
      expect(r.exitCode, 0, reason: decodeText(r.stderr));
      expect(decodeReplacing(r.stdout).split('\x00')..removeLast(), args);
    });

    test('a 20,000-character argument arrives whole', () async {
      fakeGh(echoArgs);
      final big = 'x' * 20000;
      final r = await gh(['api', big, 'tail']);
      expect(r.exitCode, 0, reason: decodeText(r.stderr));
      expect(decodeReplacing(r.stdout).split('\x00')..removeLast(), [
        'api',
        big,
        'tail',
      ]);
    });

    // D5: a byte that is not UTF-8 cannot be handed on whole, so nothing runs.
    test('an argument with a byte that is not UTF-8 is refused', () async {
      final marker = '${dir.path}/ran'.replaceAll(r'\', '/');
      fakeGh('touch "$marker"');
      final odd = 'a${String.fromCharCode(0xdcff)}b';
      final r = await gh(['api', odd]);
      expect(r.exitCode, 127);
      expect(decodeText(r.stderr), contains('unrepresentable argument'));
      expect(File(marker).existsSync(), isFalse);
    });

    test('the command exit status and both streams pass through', () async {
      fakeGh(r'echo out; echo err >&2; exit 7');
      final r = await gh(['api']);
      expect(
        (r.exitCode, decodeText(r.stdout), decodeText(r.stderr)),
        (7, 'out\n', 'err\n'),
      );
      expect(r.limit, isNull);
    });

    // The tool is started itself (D2), with no bash handed to the call.
    test('a bounded launch stops a hung descendant', () async {
      final late = '${dir.path}/late'.replaceAll(r'\', '/');
      final done = '${dir.path}/done'.replaceAll(r'\', '/');
      env
        ..['SW_LATE'] = late
        ..['SW_DONE'] = done;
      fakeGh(
        r'(sleep 4; printf late > "$SW_LATE") & wait; printf x > "$SW_DONE"',
      );
      final r = await runGh(
        Directory.current.path,
        ['api', 'user'],
        environment: env,
        limits: const RunLimits(
          deadline: Duration(milliseconds: 800),
          maxBytes: 1 << 20,
        ),
        helperCommand: helper,
      );
      expect(r.limit, BoundedLimit.deadlineExceeded);
      expect(r.limitLine, 'bounded: deadline_exceeded: gh api\n');
      await Future<void>.delayed(const Duration(seconds: 5));
      expect(File(late).existsSync(), isFalse, reason: 'the child survived');
      expect(File(done).existsSync(), isFalse, reason: 'gh itself survived');
    });

    test("a bounded command runs in the caller's directory", () async {
      // `sw` runs in the current directory (store A); the command is told to
      // run in store B.
      final b = Directory('${dir.path}/store-b')..createSync();
      final where = File('${dir.path}/bin/where');
      where
        ..createSync(recursive: true)
        ..writeAsStringSync('#!/bin/sh\npwd -W 2>/dev/null || pwd\n');
      if (!Platform.isWindows) Process.runSync('chmod', ['+x', where.path]);
      shimExe(where.path);
      final r = await runBoundedCommand(
        b.path,
        ['where'],
        environment: env,
        limits: limits,
        helperCommand: helper,
      );
      expect(r.exitCode, 0, reason: decodeText(r.stderr));
      String norm(String s) => s.trim().replaceAll(r'\', '/').toLowerCase();
      // The shell may print the 8.3 short form of a CI temp path (RUNNER~1);
      // resolve what it printed as well, so both sides are the long path.
      final printed = Directory(decodeText(r.stdout).trim());
      expect(
        norm(printed.resolveSymbolicLinksSync()),
        norm(b.resolveSymbolicLinksSync()),
      );
      expect(norm(Directory.current.path), isNot(norm(b.path)));
    });

    test(
      'a deadline gives the limit line naming gh and its first argument',
      () async {
        fakeGh('sleep 30');
        final r = await gh(
          ['api', 'user'],
          lim: const RunLimits(
            deadline: Duration(seconds: 1),
            maxBytes: 1 << 20,
          ),
        );
        expect(r.limit, BoundedLimit.deadlineExceeded);
        expect(r.limitLine, 'bounded: deadline_exceeded: gh api\n');
      },
    );

    // The scripts' `gh()` passed `--paged` whenever SW_PAGED was set.
    for (final (label, paged, finishes) in [
      ('an inherited SW_PAGED takes the paged deadline', '1', true),
      ('without SW_PAGED the normal deadline applies', '', false),
    ]) {
      test(label, () async {
        fakeGh('sleep 2; printf ok');
        env
          ..['SW_PAGED'] = paged
          ..['SPECWRIGHT_NET_DEADLINE'] = '1'
          ..['SPECWRIGHT_NET_PAGED_DEADLINE'] = '60'
          ..remove('SPECWRIGHT_NET_DEADLINE_AT');
        final r = await runGh(
          Directory.current.path,
          ['api', 'user'],
          environment: env,
          helperCommand: helper,
        );
        if (finishes) {
          expect(r.limit, isNull);
          expect(decodeText(r.stdout), 'ok');
        } else {
          expect(r.limit, BoundedLimit.deadlineExceeded);
        }
      });
    }
  });
}
