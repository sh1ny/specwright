// The final run of the fence (`runFenced`) and the assumptions it rests on.
//
// A1 (POSIX): a child started with inheritStdio that ends by a signal reports
// -N, so `sw as` can return 128+N as the shell did.
// A2: a child started from a process that has its own group (POSIX) or sits in
// a job (Windows) belongs to that group or job, so a bounded caller that stops
// the tree stops the fenced command too.
@Tags(['process'])
@Timeout(Duration(minutes: 3))
library;

import 'dart:async';
import 'dart:io';

import 'package:specwright_cli/src/fence/exec_inherit.dart';
import 'package:specwright_cli/src/native/kernel32.dart' as k32;
import 'package:test/test.dart';

import '../vcs/bash_support.dart';

String _fwd(String path) => path.replaceAll(r'\', '/');

/// POSIX: puts itself in a new session (its own process group), starts a child
/// that reports its group, and prints its own group and the child's.
const _posixParent = r'''
import 'dart:ffi';
import 'dart:io';

Future<void> main() async {
  final libc = DynamicLibrary.process();
  final setsid = libc.lookupFunction<Int32 Function(), int Function()>('setsid');
  setsid();
  final mine = Process.runSync('ps', ['-o', 'pgid=', '-p', '$pid']);
  stdout.writeln('parent ${(mine.stdout as String).trim()}');
  await stdout.flush();
  final child = await Process.start(
    'sh',
    ['-c', 'ps -o pgid= -p \$\$ | sed "s/^ */child /"'],
    mode: ProcessStartMode.inheritStdio,
  );
  exit(await child.exitCode);
}
''';

/// Windows: waits for a byte (the test puts it in a job meanwhile), starts a
/// child that sleeps and prints the child's pid.
const _windowsParent = r'''
import 'dart:io';

Future<void> main(List<String> args) async {
  stdin.readByteSync();
  final child = await Process.start(
    Platform.resolvedExecutable,
    [args[0]],
    mode: ProcessStartMode.inheritStdio,
  );
  stdout.writeln('child ${child.pid}');
  await stdout.flush();
  exit(await child.exitCode);
}
''';

const _sleeper = r'''
Future<void> main() => Future<void>.delayed(const Duration(minutes: 2));
''';

void main() {
  final bash = findBash();
  late Directory dir;
  late Directory other;

  setUp(() {
    dir = Directory.systemTemp.createTempSync('sw-fenced-');
    other = Directory.systemTemp.createTempSync('sw-fenced-out-');
  });
  tearDown(() {
    dir.deleteSync(recursive: true);
    other.deleteSync(recursive: true);
  });

  Future<int> fenced(List<String> command, {Map<String, String>? env}) =>
      runFenced(
        bash!,
        command,
        env ?? Map.of(Platform.environment),
        tempRoot: dir,
      );

  group('the prelude', () {
    Future<ProcessResult> prelude(String file) =>
        Process.run(bash!, ['-c', fencedPrelude, 'as.sh', _fwd(file)]);

    test('a missing file exits 126 and runs nothing', () async {
      final r = await prelude('${dir.path}/nothing');
      expect(r.exitCode, 126);
      expect(r.stderr, contains('as.sh: handoff: malformed'));
    });

    test('a file without the end record exits 126 and runs nothing', () async {
      final ran = File('${other.path}/ran');
      final file = File('${dir.path}/args')
        ..writeAsBytesSync([
          ...'touch\x00${_fwd(ran.path)}\x00'.codeUnits, // no --sw-end--
        ]);
      final r = await prelude(file.path);
      expect(r.exitCode, 126);
      expect(ran.existsSync(), isFalse);
    });

    test('a cut-off last record exits 126 and runs nothing', () async {
      final ran = File('${other.path}/ran');
      final file = File('${dir.path}/args')
        ..writeAsBytesSync(
          'touch\x00${_fwd(ran.path)}\x00--sw-end--'.codeUnits, // no final NUL
        );
      final r = await prelude(file.path);
      expect(r.exitCode, 126);
      expect(ran.existsSync(), isFalse);
    });
  });

  group('runFenced', () {
    test(
      'the arguments arrive whole and the status is the command\'s',
      () async {
        final out = File('${other.path}/out');
        final code = await fenced([
          bash!,
          '-c',
          r'printf "%s|" "$@" > "$0"; exit 7',
          _fwd(out.path),
          'a b',
          '',
          r'$x "y" *',
          '--sw-end--x',
        ]);
        expect(code, 7);
        expect(out.readAsStringSync(), r'a b||$x "y" *|--sw-end--x|');
      },
    );

    test('a command that is not found ends 127', () async {
      expect(await fenced(['sw-no-such-command-xyz']), 127);
    });

    test(
      'the file and its directory are gone before the command runs',
      () async {
        final listing = File('${other.path}/listing');
        final code = await fenced([
          bash!,
          '-c',
          r'ls -A "$1" > "$2"',
          'x',
          _fwd(dir.path),
          _fwd(listing.path),
        ]);
        expect(code, 0);
        expect(listing.readAsStringSync(), isEmpty);
        expect(dir.listSync(), isEmpty);
      },
    );

    test('the directory is removed when the command could not start', () async {
      await fenced(['sw-no-such-command-xyz']);
      expect(dir.listSync(), isEmpty);
    });

    test('a variable left out of the map does not arrive', () async {
      final name = [
        'NUMBER_OF_PROCESSORS',
        'COMPUTERNAME',
        'USERDOMAIN',
        'LOGNAME',
        'SHELL',
        'LANG',
      ].firstWhere((n) => Platform.environment.containsKey(n));
      final out = File('${other.path}/env');
      final env = Map.of(Platform.environment)
        ..removeWhere((k, _) => k.toLowerCase() == name.toLowerCase());
      final code = await fenced([
        bash!,
        '-c',
        r'printf "%s" "${!1-unset}" > "$0"',
        _fwd(out.path),
        name,
      ], env: env);
      expect(code, 0);
      expect(out.readAsStringSync(), 'unset');
    });

    test(
      'a PWD in the map is not kept on Windows',
      () async {
        final out = File('${other.path}/pwd');
        final code = await fenced(
          [bash!, '-c', r'printf "%s" "$PWD" > "$0"', _fwd(out.path)],
          env: {...Platform.environment, 'PWD': 'C:/sw-test-not-the-cwd'},
        );
        expect(code, 0);
        expect(out.readAsStringSync(), isNot('C:/sw-test-not-the-cwd'));
      },
      skip: Platform.isWindows
          ? false
          : 'Windows: the shim hands sw a drive-form PWD',
    );

    test('a command ended by SIGTERM gives 128+15', () async {
      expect(await fenced([bash!, '-c', r'kill -TERM $$']), 143);
    }, skip: Platform.isWindows ? 'POSIX signals' : false);
  });

  group('A1', () {
    test(
      'a child ended by SIGTERM started with inheritStdio reports -15',
      () async {
        final p = await Process.start(bash!, [
          '-c',
          r'kill -TERM $$',
        ], mode: ProcessStartMode.inheritStdio);
        expect(await p.exitCode, -15);
      },
      skip: Platform.isWindows ? 'POSIX signals' : false,
    );
  });

  group('A2', () {
    test(
      'a child of a process in its own group has the parent\'s group',
      () async {
        final script = File('${dir.path}/parent.dart')
          ..writeAsStringSync(_posixParent);
        final r = await Process.run(Platform.resolvedExecutable, [script.path]);
        expect(r.exitCode, 0, reason: '${r.stdout}${r.stderr}');
        final seen = <String, String>{};
        for (final line in (r.stdout as String).trim().split('\n')) {
          final parts = line.trim().split(RegExp(r'\s+'));
          seen[parts[0]] = parts[1];
        }
        expect(seen['child'], isNotNull, reason: '${r.stdout}');
        expect(seen['child'], seen['parent']);
      },
      skip: Platform.isWindows ? 'POSIX process groups' : false,
    );

    test('a child of a process in a job is in the job', () async {
      final sleeper = File('${dir.path}/sleeper.dart')
        ..writeAsStringSync(_sleeper);
      final parent = File('${dir.path}/parent.dart')
        ..writeAsStringSync(_windowsParent);
      final job = k32.createJobObject();
      expect(job, isNot(0), reason: 'CreateJobObject failed');
      addTearDown(() => k32.terminateJobObject(job, 1));
      addTearDown(() => k32.closeHandle(job));
      final p = await Process.start(Platform.resolvedExecutable, [
        parent.path,
        sleeper.path,
      ]);
      final lines = <String>[];
      final seen = Completer<void>();
      p.stdout
          .transform(const SystemEncoding().decoder)
          .listen(
            (text) {
              lines.addAll(text.split('\n').where((l) => l.isNotEmpty));
              if (lines.isNotEmpty && !seen.isCompleted) seen.complete();
            },
            onDone: () {
              if (!seen.isCompleted) seen.complete();
            },
          );
      p.stderr.drain<void>();
      final handle = k32.openProcess(k32.helperAccess, p.pid);
      expect(handle, isNot(0), reason: 'OpenProcess failed');
      addTearDown(() => k32.closeHandle(handle));
      expect(k32.assignProcessToJobObject(job, handle), isTrue);
      p.stdin.add([0x67]);
      await p.stdin.close();
      await seen.future.timeout(const Duration(seconds: 60));
      final childPid = int.parse(lines.first.split(' ').last);
      final child = k32.openProcess(
        k32.processQueryLimitedInformation,
        childPid,
      );
      expect(child, isNot(0), reason: 'OpenProcess($childPid) failed');
      addTearDown(() => k32.closeHandle(child));
      expect(k32.isProcessInJob(child, job), isTrue);
    }, skip: Platform.isWindows ? false : 'Windows jobs');
  });
}
