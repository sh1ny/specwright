import 'dart:convert';
import 'dart:io';

import 'package:specwright_cli/src/cli.dart';
import 'package:test/test.dart';

const _subcommands =
    'plan, stage, swap, note-config, finish, recover, pack-check, pack-verify, '
    'pack-docs, sw-install, interface';

void main() {
  late Directory temp;

  setUp(() {
    temp = Directory.systemTemp.createTempSync('sw-update-command-');
  });

  tearDown(() {
    temp.deleteSync(recursive: true);
  });

  Future<(int, String, String)> run(List<String> args) async {
    final out = <int>[];
    final err = StringBuffer();
    final code = await runCli(
      ['update', ...args],
      out: StringBuffer(),
      err: err,
      outBytes: out.addAll,
      errBytes: (_) {},
    );
    return (code, utf8.decode(out), err.toString());
  }

  Future<void> expectUsage(List<String> args, String message) async {
    final (code, out, _) = await run(args);
    expect(code, 2, reason: '$args -> $out');
    expect(jsonDecode(out), {
      'ok': false,
      'error': 'usage',
      'message': message,
    }, reason: '$args');
    expect(out.endsWith('\n'), isTrue);
  }

  group('usage errors exit 2 with one JSON document', () {
    test('no subcommand or a plan-only misuse is a usage error', () async {
      await expectUsage(
        [],
        'a subcommand is required: plan, stage, swap, note-config, finish, '
        'recover, pack-check, pack-verify, pack-docs, sw-install or interface',
      );
      await expectUsage([
        'plan',
        '--rollback',
      ], '--rollback belongs to the recover subcommand');
      await expectUsage([
        '--rollback',
        'stage',
      ], '--rollback belongs to the recover subcommand');
    });

    test('an unknown subcommand names the known ones', () async {
      await expectUsage([
        'frobnicate',
      ], 'unknown subcommand frobnicate ($_subcommands)');
    });

    test('an unknown option', () async {
      await expectUsage(['plan', '--bogus'], 'unknown option --bogus');
      await expectUsage(['plan', '-x'], 'unknown option -x');
      // update.sh has no --name=value form
      await expectUsage(['plan', '--code=/x'], 'unknown option --code=/x');
    });

    test('an option with no value', () async {
      for (final name in [
        '--code',
        '--root',
        '--skills',
        '--agents',
        '--download',
        '--ref',
        '--pack',
        '--pack-doc',
        '--release-url',
        '--previous',
        '--build',
      ]) {
        await expectUsage(['plan', name], '$name needs a value');
      }
    });

    test('--agents needs KIND=DIR', () async {
      await expectUsage([
        'plan',
        '--agents',
        'claude',
      ], '--agents needs KIND=DIR');
    });

    test('two subcommands', () async {
      await expectUsage(['plan', 'stage'], 'one subcommand only');
    });

    test('an option value may look like an option', () async {
      final (code, out, _) = await run(['interface', '--ref', '--rollback']);
      expect(code, 0, reason: out);
    });
  });

  group('interface', () {
    test('prints {"ok":true,"interface":3} and touches no file', () async {
      final before = _listing(temp);
      final (code, out, err) = await run([
        'interface',
        '--code',
        temp.path,
        '--root',
        temp.path,
      ]);
      expect(code, 0, reason: out);
      expect(out, '{"ok":true,"interface":3}\n');
      expect(err, isEmpty);
      expect(_listing(temp), before);
      expect(
        Directory('${temp.path}/openspec').existsSync(),
        isFalse,
        reason: 'no state directory, journal or lock',
      );
    });

    test('ignores a pending journal: no recovery, no lock', () async {
      final state = Directory('${temp.path}/openspec/.specwright')
        ..createSync(recursive: true);
      final journal = File('${state.path}/update.json')
        ..writeAsStringSync('{"format": 9}\n');
      final before = _listing(temp);
      final (code, out, _) = await run(['interface', '--code', temp.path]);
      expect(code, 0, reason: out);
      expect(out, '{"ok":true,"interface":3}\n');
      expect(_listing(temp), before);
      expect(journal.readAsStringSync(), '{"format": 9}\n');
    });
  });

  group('--download is required by every subcommand that reads the download', () {
    for (final sub in [
      'plan',
      'stage',
      'swap',
      'recover',
      'pack-check',
      'pack-verify',
      'pack-docs',
    ]) {
      test('$sub without --download is a usage error and writes nothing', () async {
        await expectUsage([
          sub,
          '--code',
          temp.path,
        ], '$sub needs --download DIR');
        expect(_listing(temp), isEmpty);
      });
    }

    test('note-config and finish read no download', () async {
      for (final sub in ['note-config', 'finish']) {
        final (code, out, _) = await run([sub, '--code', temp.path]);
        expect(
          (jsonDecode(out) as Map)['error'],
          isNot('usage'),
          reason: '$sub: $out',
        );
        expect(code, isNot(2), reason: '$sub: $out');
      }
    });

    test('recover accepts --rollback', () async {
      await expectUsage([
        'recover',
        '--rollback',
        '--code',
        temp.path,
      ], 'recover needs --download DIR');
    });
  });
}

List<String> _listing(Directory dir) =>
    [for (final e in dir.listSync(recursive: true)) e.path]..sort();
