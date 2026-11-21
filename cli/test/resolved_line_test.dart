// native-cli-launcher D5: a Windows command line past 32,767 units is refused
// by name, and nothing starts. The limit applies to the line with the RESOLVED
// path, so a command whose arguments fit with its short name can still be too
// long once `PATH` resolves it. `planLaunch` checks it for every native plan;
// each entry point that starts a native command maps the refusal:
// `launch`, `sw run --bounded`, bounded gh and the fence.
//
// Windows only: the limit is a Windows one.
@TestOn('windows')
library;

import 'dart:io';

import 'package:specwright_cli/src/commands/run.dart';
import 'package:specwright_cli/src/fence/exec_inherit.dart';
import 'package:specwright_cli/src/pr/gh.dart';
import 'package:specwright_cli/src/process/command_line.dart';
import 'package:specwright_cli/src/process/launch.dart';
import 'package:test/test.dart';

import 'line_support.dart';

const _name = 'longtool';

void main() {
  late Directory root;
  late Directory bin;
  late Map<String, String> env;
  late List<String> args;

  setUp(() {
    root = Directory.systemTemp.createTempSync('sw-resolved-line-');
    // a long directory, so the resolved path is far longer than the short name
    bin = Directory('${root.path}\\${'d' * 100}\\${'e' * 100}')
      ..createSync(recursive: true);
    File('${bin.path}\\$_name.exe').writeAsBytesSync([0]);
    env = {...Platform.environment, 'PATH': bin.path, 'PATHEXT': '.EXE;.CMD'};
    // `longtool`, a space and the argument: exactly 32,767 units with the short
    // name, so more than that with the resolved path
    args = [_name, 'x' * (32767 - _name.length - 1)];
  });

  tearDown(() => root.deleteSync(recursive: true));

  test('the arguments fit with the short name', () {
    // the as-given check keeps admitting 32,767 units (it counts no NUL)
    checkCommandLine(_name, args, windows: true);
    expect(
      () => checkCommandLine(_name, [
        '${bin.path}\\$_name.exe',
        args[1],
      ], windows: true),
      throwsA(isA<Unrepresentable>()),
    );
  });

  // D5 / C1: CreateProcessW takes 32,767 units including the terminating NUL,
  // so the longest line that starts has 32,766 visible units.
  test('32,766 units start, 32,767 are refused', () {
    final path = '${bin.path}\\$_name.exe';
    LaunchPlan plan(int units) => planLaunch(
      path,
      [
        _name,
        fillTo([path], units),
      ],
      env,
      windows: true,
      transport: false,
    );
    expect(plan(32766), isNotNull);
    expect(
      () => plan(32767),
      throwsA(
        isA<Unrepresentable>()
            .having((e) => e.command, 'command', _name)
            .having((e) => e.what, 'what', 'command line'),
      ),
    );
  });

  test('a started line over 32,766 units is refused', () {
    final path = '${bin.path}\\$_name.exe';
    expect(
      () => planLaunch(
        path,
        [
          _name,
          fillTo([path], 32768),
        ],
        env,
        windows: true,
        transport: false,
      ),
      throwsA(isA<Unrepresentable>()),
    );
  });

  test('planLaunch refuses a native line over the limit by name', () {
    expect(
      () => planLaunch('${bin.path}\\$_name.exe', args, env, windows: true),
      throwsA(
        isA<Unrepresentable>()
            .having((e) => e.command, 'command', _name)
            .having((e) => e.what, 'what', 'command line'),
      ),
    );
  });

  test('launch refuses it', () async {
    await expectLater(
      launch(args, cwd: root.path, environment: env),
      throwsA(isA<Unrepresentable>()),
    );
  });

  test('sw run --bounded refuses it with exit 2', () async {
    final err = StringBuffer();
    final code = await runCommand(
      ['--bounded', '--', ...args],
      err: err,
      writeOut: (_) {},
      writeErr: (_) {},
      env: env,
    );
    expect(err.toString(), 'bounded: unrepresentable command line: $_name\n');
    expect(code, 2);
  });

  test('bounded gh refuses it and nothing starts', () async {
    final result = await runBoundedCommand(root.path, args, environment: env);
    expect(
      String.fromCharCodes(result.stderr),
      'bounded: cannot start $_name: unrepresentable command line: $_name\n',
    );
    expect(result.exitCode, 127);
  });

  test('the fence refuses it by throwing Unrepresentable', () async {
    final saved = Directory.current;
    Directory.current = root;
    addTearDown(() => Directory.current = saved);
    await expectLater(
      runFenced(args, env),
      throwsA(
        isA<Unrepresentable>().having((e) => e.what, 'what', 'command line'),
      ),
    );
  });

  // D5: the arguments after `<name>` of a Windows `bash -c` travel on stdin, so
  // a line that is over 32,767 units as the caller wrote it starts once they
  // moved, and the started line and the helper's line are checked with them
  // moved. An eval cannot hold this row on Windows: the test's own launch of
  // `sw` would carry the same arguments on its command line.
  test('bash -c arguments fit once moved to stdin', () {
    const bash = r'C:\tools\bash.exe';
    final command = [
      'bash',
      '-c',
      r'printf %s "$#"',
      'name',
      for (var i = 0; i < 25; i++) 'a' * 1500,
    ];
    expect(lineUnits([bash, ...command.skip(1)]), greaterThan(32767));
    final plan = planBoundedLaunch(bash, command, env, const [
      r'C:\sw\sw.exe',
      '__exec',
    ], windows: true);
    expect(plan.lineTooLong, isFalse);
    expect(lineUnits(plan.plan.command), lessThan(1000));
    expect(plan.plan.stdinBytes, isNotEmpty);
    expect(
      plan.plan.stdinBytes.where((b) => b == 0).length,
      26,
      reason: 'the 25 arguments and the end marker',
    );
    expect(lineUnits(plan.helperArgv), lessThan(32767));
  });
}
