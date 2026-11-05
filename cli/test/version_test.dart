import 'package:specwright_cli/src/cli.dart';
import 'package:specwright_cli/src/commands/version.dart';
import 'package:test/test.dart';

void main() {
  group('versionReport', () {
    test('has the version and interface 1', () {
      expect(versionReport(version: '1.2.3'), {
        'version': '1.2.3',
        'interface': 1,
      });
    });

    test('defaults to 0.0.0-dev when no SW_VERSION is defined', () {
      expect(buildVersion, '0.0.0-dev');
    });
  });

  group('runCli', () {
    Future<(int, String, String)> run(List<String> args) async {
      final out = StringBuffer();
      final err = StringBuffer();
      final code = await runCli(args, out: out, err: err);
      return (code, out.toString(), err.toString());
    }

    test('version --json prints one JSON object and exits 0', () async {
      final (code, out, err) = await run(['version', '--json']);
      expect(code, 0);
      expect(out, '{"version":"0.0.0-dev","interface":1}\n');
      expect(err, isEmpty);
    });

    test('plain version prints the same JSON', () async {
      final (code, out, _) = await run(['version']);
      expect(code, 0);
      expect(out, '{"version":"0.0.0-dev","interface":1}\n');
    });

    for (final args in [
      <String>[],
      ['frobnicate'],
      ['version', '--bogus'],
    ]) {
      test('$args prints usage naming the commands and exits 2', () async {
        final (code, out, err) = await run(args);
        expect(code, 2);
        expect(out, isEmpty);
        expect(err, startsWith('usage: sw'));
        expect(err, contains('version'));
        expect(err, contains('run'));
      });
    }
  });
}
