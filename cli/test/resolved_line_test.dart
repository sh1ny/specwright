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
    checkCommandLine(_name, args, windows: true);
    expect(
      () => checkCommandLine(_name, [
        '${bin.path}\\$_name.exe',
        args[1],
      ], windows: true),
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
}
