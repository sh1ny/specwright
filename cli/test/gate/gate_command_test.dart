import 'dart:convert';
import 'dart:io';

import 'package:specwright_cli/src/commands/gate.dart';
import 'package:test/test.dart';

// `sw gate` as a command: how it finds the store repository from `--store`.
// Runs git in a temporary directory.

void main() {
  late Directory tmp;
  late Directory cwd;

  setUp(() {
    cwd = Directory.current;
    tmp = Directory.systemTemp.createTempSync('gate-command-test-');
    final init = Process.runSync('git', [
      'init',
      '-q',
      'store',
    ], workingDirectory: tmp.path);
    expect(init.exitCode, 0, reason: '${init.stderr}');
  });
  tearDown(() {
    Directory.current = cwd;
    tmp.deleteSync(recursive: true);
  });

  Future<(int, Map<String, Object?>)> gate(List<String> args) async {
    final out = <int>[];
    final status = await runGateCommand(args, writeOut: out.addAll);
    return (status, jsonDecode(utf8.decode(out)) as Map<String, Object?>);
  }

  test('a relative --store is read against the working directory', () async {
    Directory.current = tmp;
    final (status, doc) = await gate(['show', '--store', 'store']);
    expect(status, 0, reason: '$doc');
    expect(doc['ok'], true);
    expect(doc['held'], false);
  });

  test(
    'lock and unlock with a relative --store use the store repository',
    () async {
      Directory.current = tmp;
      final (locked, doc) = await gate([
        'lock',
        '--store',
        'store',
        '--branch',
        'feat/x',
        '--code',
        tmp.path,
      ]);
      expect(locked, 0, reason: '$doc');
      expect(
        Directory('${tmp.path}/store/.git/specwright-gate.lock').existsSync(),
        true,
      );
      final token = (doc['owner'] as Map)['token'] as String;
      final (unlocked, _) = await gate([
        'unlock',
        '--store',
        'store',
        '--token',
        token,
      ]);
      expect(unlocked, 0);
      expect(
        Directory('${tmp.path}/store/.git/specwright-gate.lock').existsSync(),
        false,
      );
    },
  );
}
