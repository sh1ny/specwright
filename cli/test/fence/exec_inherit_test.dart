// The final run of the fence (`runFenced`) and the assumptions it rests on.
//
// native-cli-launcher D3: the fenced command starts with no shell before it,
// with this process's stdio, the given environment and this process's
// directory. A `.cmd` or `.bat` command (Windows) runs through
// `runWithCommandLine` in process.
//
// Every run below has a recording `bash` and `sh` that fail first on `PATH`,
// so a launch that goes through a shell by name leaves a record and a
// different status.
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
import 'dart:convert';
import 'dart:io';

import 'package:specwright_cli/src/fence/exec_inherit.dart';
import 'package:specwright_cli/src/native/kernel32.dart' as k32;
import 'package:test/test.dart';

import '../vcs/bash_support.dart';

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

/// The fenced command of most tests: reports what it got as one ASCII JSON line
/// on stdout (arguments, the stdin it read to the end, its environment and
/// directory) and exits with the status in `PROBE_EXIT`.
const _probe = r'''
import 'dart:convert';
import 'dart:io';

Future<void> main(List<String> args) async {
  final input = await utf8.decodeStream(stdin);
  final text = jsonEncode({
    'args': args,
    'stdin': input,
    'env': Platform.environment,
    'cwd': Directory.current.path,
  });
  final ascii = StringBuffer();
  for (final unit in text.codeUnits) {
    ascii.write(unit < 0x80
        ? String.fromCharCode(unit)
        : '\\u${unit.toRadixString(16).padLeft(4, '0')}');
  }
  stdout.writeln(ascii);
  exit(int.parse(Platform.environment['PROBE_EXIT'] ?? '0'));
}
''';

/// A copy of [base] with [set] added and every key of [drop] removed, keys
/// compared without case (Windows names).
Map<String, String> _env(
  Map<String, String> base, {
  Map<String, String> set = const {},
  List<String> drop = const [],
}) {
  final names = {...drop, ...set.keys}.map((n) => n.toUpperCase()).toSet();
  return {
    for (final e in base.entries)
      if (!names.contains(e.key.toUpperCase())) e.key: e.value,
    ...set,
  };
}

void main() {
  final bash = findBash();
  late Directory dir;
  late Directory other;
  late Directory shells;
  late File shellLog;
  late File probe;

  setUp(() {
    dir = Directory.systemTemp.createTempSync('sw-fenced-');
    other = Directory.systemTemp.createTempSync('sw-fenced-out-');
    shells = Directory('${other.path}/failing-shells')..createSync();
    shellLog = File('${other.path}/shell.log');
    for (final name in ['bash', 'sh']) {
      if (Platform.isWindows) {
        File(
          '${shells.path}/$name.cmd',
        ).writeAsStringSync('@echo $name>>"%SW_SHELL_LOG%"\r\n@exit /b 1\r\n');
      } else {
        File('${shells.path}/$name').writeAsStringSync(
          '#!/bin/sh\nprintf "%s\\n" $name >> "\$SW_SHELL_LOG"\nexit 1\n',
        );
        Process.runSync('chmod', ['755', '${shells.path}/$name']);
      }
    }
    probe = File('${dir.path}/probe.dart')..writeAsStringSync(_probe);
  });
  tearDown(() async {
    for (final d in [dir, other]) {
      // a child that ended a moment ago can still hold its directory on Windows
      for (var i = 0; i < 20; i++) {
        try {
          d.deleteSync(recursive: true);
          break;
        } on FileSystemException {
          await Future<void>.delayed(const Duration(milliseconds: 250));
        }
      }
    }
  });

  /// The environment of a run: this process's, the failing shells first on
  /// `PATH`, and [set].
  Map<String, String> envOf({Map<String, String> set = const {}}) {
    final path = Platform.environment['PATH'] ?? Platform.environment['Path'];
    return _env(
      Platform.environment,
      set: {
        'PATH': '${shells.path}${Platform.isWindows ? ';' : ':'}${path ?? ''}',
        'SW_SHELL_LOG': shellLog.path,
        ...set,
      },
    );
  }

  void expectNoShell() => expect(
    shellLog.existsSync() ? shellLog.readAsStringSync() : '',
    isEmpty,
    reason: 'a shell was started',
  );

  Future<int> fenced(List<String> command, {Map<String, String>? env}) =>
      runFenced(command, env ?? envOf());

  /// Runs `fenced_driver.dart` (which calls `runFenced` with its own stdio),
  /// writes [stdin] on its stdin and returns what it printed and exited with.
  Future<({int code, String out, String err})> driven(
    List<String> command, {
    String stdin = '',
    Map<String, String>? env,
  }) async {
    final p = await Process.start(
      Platform.resolvedExecutable,
      ['test/fence/fenced_driver.dart', ...command],
      environment: env ?? envOf(),
      includeParentEnvironment: false,
    );
    final out = utf8.decodeStream(p.stdout);
    final err = utf8.decodeStream(p.stderr);
    p.stdin.write(stdin);
    await p.stdin.close();
    final code = await p.exitCode;
    return (code: code, out: await out, err: await err);
  }

  Map<String, dynamic> reported(String out) =>
      jsonDecode(out.trim().split('\n').last) as Map<String, dynamic>;

  group('runFenced', () {
    test('the command keeps stdin, arguments and exit status, and no shell '
        'starts', () async {
      final args = ['a b', '', r'$x "y" *', '--sw-end--x', 'é€', r'back\'];
      final r = await driven(
        [Platform.resolvedExecutable, probe.path, ...args],
        stdin: 'line one\nline two\n',
        env: envOf(set: {'PROBE_EXIT': '7'}),
      );
      expect(r.code, 7, reason: r.err);
      final seen = reported(r.out);
      expect(seen['args'], args);
      expect(seen['stdin'], 'line one\nline two\n');
      expectNoShell();
    });

    test('a command that is not found ends 127 and names itself', () async {
      final r = await driven(['sw-no-such-command-xyz']);
      expect(r.code, 127);
      expect(r.err, 'as.sh: sw-no-such-command-xyz: command not found\n');
      expectNoShell();
    });

    test('the command runs in the directory the fence runs in', () async {
      final r = await driven([
        Platform.resolvedExecutable,
        probe.path,
      ], env: envOf());
      expect(r.code, 0, reason: r.err);
      expect(
        Directory(reported(r.out)['cwd'] as String).resolveSymbolicLinksSync(),
        Directory.current.resolveSymbolicLinksSync(),
      );
    });

    test('a command found on PATH by name starts', () async {
      final tool = File('${other.path}/sw-tool')
        ..writeAsStringSync('#!/bin/sh\nexit 5\n');
      Process.runSync('chmod', ['755', tool.path]);
      final code = await fenced([
        'sw-tool',
      ], env: envOf(set: {'PATH': '${other.path}:${envOf()['PATH']}'}));
      expect(code, 5);
      expectNoShell();
    }, skip: Platform.isWindows ? 'POSIX: an extensionless script' : false);

    test('a variable left out of the map does not arrive', () async {
      final name = [
        'NUMBER_OF_PROCESSORS',
        'COMPUTERNAME',
        'USERDOMAIN',
        'LOGNAME',
        'SHELL',
        'LANG',
      ].firstWhere((n) => Platform.environment.containsKey(n));
      final r = await driven([
        Platform.resolvedExecutable,
        probe.path,
      ], env: _env(envOf(), drop: [name]));
      expect(r.code, 0, reason: r.err);
      final env = reported(r.out)['env'] as Map<String, dynamic>;
      expect(
        env.keys.map((k) => k.toUpperCase()),
        isNot(contains(name.toUpperCase())),
      );
    });

    test('a variable in the map arrives with its value', () async {
      final r = await driven([
        Platform.resolvedExecutable,
        probe.path,
      ], env: envOf(set: {'SW_FENCED_VALUE': 'é€ "q" \$x'}));
      expect(r.code, 0, reason: r.err);
      final env = reported(r.out)['env'] as Map<String, dynamic>;
      expect(env['SW_FENCED_VALUE'], 'é€ "q" \$x');
    });

    test(
      'a PWD in the map is not kept on Windows',
      () async {
        final r = await driven([
          Platform.resolvedExecutable,
          probe.path,
        ], env: envOf(set: {'PWD': 'C:/sw-test-not-the-cwd'}));
        expect(r.code, 0, reason: r.err);
        final env = reported(r.out)['env'] as Map<String, dynamic>;
        expect(env.keys.map((k) => k.toUpperCase()), isNot(contains('PWD')));
      },
      skip: Platform.isWindows
          ? false
          : 'Windows: the shim hands sw a drive-form PWD',
    );

    test('SIGTERM ends the fence with 143 and no shell', () async {
      final script = File('${dir.path}/term.dart')
        ..writeAsStringSync(r'''
import 'dart:io';
Future<void> main() async {
  Process.killPid(pid, ProcessSignal.sigterm);
  await Future<void>.delayed(const Duration(seconds: 30));
}
''');
      final r = await driven([Platform.resolvedExecutable, script.path]);
      expect(r.code, 143, reason: r.err);
      expectNoShell();
    }, skip: Platform.isWindows ? 'POSIX signals' : false);

    test('a .cmd command keeps the caller\'s stdin and stdout and gets the '
        'environment', () async {
      File('${dir.path}/fake.cmd').writeAsStringSync(
        '@echo off\r\nset /p L=\r\necho got:%L% token:%GH_TOKEN%\r\n'
        'exit /b 3\r\n',
      );
      final r = await driven(
        ['fake'],
        stdin: 'from the caller\r\n',
        env: envOf(
          set: {
            'GH_TOKEN': 'tok-1',
            'PATH':
                '${dir.path};${shells.path};${Platform.environment['PATH'] ?? Platform.environment['Path']}',
          },
        ),
      );
      expect(r.code, 3, reason: r.err);
      expect(r.out, contains('got:from the caller token:tok-1'));
      expect(r.err, isEmpty, reason: 'no helper frame on stderr');
      expectNoShell();
    }, skip: Platform.isWindows ? false : 'Windows batch files');

    test('the arguments arrive whole in process too', () async {
      final out = File('${other.path}/out');
      final script = File('${dir.path}/write.dart')
        ..writeAsStringSync(r'''
import 'dart:io';
void main(List<String> a) {
  File(a[0]).writeAsStringSync(a.skip(1).join('|'));
  exit(7);
}
''');
      final code = await fenced([
        Platform.resolvedExecutable,
        script.path,
        out.path,
        'a b',
        '',
        r'$x "y" *',
      ]);
      expect(code, 7);
      expect(out.readAsStringSync(), r'a b||$x "y" *');
      expectNoShell();
    });
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
