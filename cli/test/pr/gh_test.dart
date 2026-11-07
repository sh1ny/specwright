@Tags(['process'])
library;

import 'dart:io';

import 'package:specwright_cli/src/pr/gh.dart';
import 'package:specwright_cli/src/process/limit_line.dart';
import 'package:specwright_cli/src/process/limits.dart';
import 'package:specwright_cli/src/vcs/codec.dart';
import 'package:test/test.dart';

import '../helper_support.dart';
import '../vcs/bash_support.dart';

void main() {
  final bash = findBash();
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

  // A fake `gh` first on PATH: an extensionless shell script, as the evals'
  // fake is, so only bash finds it on Windows.
  void fakeGh(String body) {
    final gh = File('${dir.path}/bin/gh')
      ..createSync(recursive: true)
      ..writeAsStringSync('#!/bin/sh\n$body\n');
    if (!Platform.isWindows) Process.runSync('chmod', ['+x', gh.path]);
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
    bash!,
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
      expect(decodeEscaped(r.stdout).split('\x00')..removeLast(), args);
    });

    test('a 20,000-character argument arrives whole', () async {
      fakeGh(echoArgs);
      final big = 'x' * 20000;
      final r = await gh(['api', big, 'tail']);
      expect(r.exitCode, 0, reason: decodeText(r.stderr));
      expect(decodeEscaped(r.stdout).split('\x00')..removeLast(), [
        'api',
        big,
        'tail',
      ]);
    });

    test(
      'an argument with a byte that is not UTF-8 arrives unchanged',
      () async {
        fakeGh(echoArgs);
        final odd =
            'a${String.fromCharCode(0xdcff)}b${String.fromCharCode(0xdce9)}';
        final r = await gh(['api', odd]);
        expect(r.exitCode, 0, reason: decodeText(r.stderr));
        expect(r.stdout, [
          ...encodeEscaped('api'),
          0,
          ...encodeEscaped(odd),
          0,
        ]);
        expect(r.stdout, contains(0xff));
      },
      skip: Platform.isWindows ? 'POSIX argument bytes' : false,
    );

    test('the command exit status and both streams pass through', () async {
      fakeGh(r'echo out; echo err >&2; exit 7');
      final r = await gh(['api']);
      expect(
        (r.exitCode, decodeText(r.stdout), decodeText(r.stderr)),
        (7, 'out\n', 'err\n'),
      );
      expect(r.limit, isNull);
    });

    test('a broken framing exits 126 and runs nothing', () async {
      final marker = '${dir.path}/ran'.replaceAll(r'\', '/');
      fakeGh('touch "$marker"');
      // a count of 3 with a single record after it
      final r = await runGhFramed(
        bash!,
        '.\x003\x00gh\x00'.codeUnits,
        environment: env,
        limits: limits,
        helperCommand: helper,
      );
      expect(r.exitCode, 126);
      expect(decodeText(r.stderr), 'bounded: argument transport failed\n');
      expect(File(marker).existsSync(), isFalse);
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
          bash!,
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
