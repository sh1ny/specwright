import 'dart:convert';
import 'dart:io';

import 'package:specwright_cli/src/cli.dart';
import 'package:specwright_cli/src/entry/project_version.dart';
import 'package:test/test.dart';

void main() {
  late Directory project;
  setUp(() {
    project = Directory.systemTemp.createTempSync('sw-project-version-');
    Directory('${project.path}/.git').createSync();
    Directory('${project.path}/openspec/.specwright')
        .createSync(recursive: true);
  });
  tearDown(() => project.deleteSync(recursive: true));

  void writeVersion(String text) =>
      File('${project.path}/openspec/.specwright/VERSION')
          .writeAsBytesSync(utf8.encode(text));

  Map<String, Object?>? check([String version = '0.38.0']) => versionMismatch(
    project.path,
    version: version,
    environment: {'SPECWRIGHT_HOME': '/home/u', 'HOME': '/home/u'},
  );

  group('the version check reads only a version', () {
    test('VERSION with CRLF matches', () {
      writeVersion('0.38.0\r\n');
      expect(check(), isNull);
    });

    test('a pre-release or build suffix is a version', () {
      writeVersion('0.38.0-rc.1+b5\n');
      expect(check('0.38.0-rc.1+b5'), isNull);
    });

    for (final value in [
      '../../../planted/.specwright/bin/0.38.0',
      '0.38.0\nextra\n',
      '0.38',
      '',
      '${'1' * 5000}.0.0',
    ]) {
      test('${value.length > 40 ? 'a long value' : jsonEncode(value)} '
          'is not a version', () {
        writeVersion(value);
        final doc = check()!;
        expect(doc['ok'], false);
        expect(doc['error'], 'sw_mismatch');
        expect(doc['message'], contains('not a version'));
        expect((doc['message'] as String).length, lessThan(500));
      });
    }
  });

  group('the mismatch document', () {
    test('another version names both versions and the binary to run', () {
      writeVersion('0.39.0\n');
      final doc = check()!;
      expect(doc['error'], 'sw_mismatch');
      final message = doc['message'] as String;
      expect(message, contains('0.38.0'));
      expect(message, contains('0.39.0'));
      expect(
        message,
        contains(
          '/home/u/.specwright/bin/0.39.0/sw${Platform.isWindows ? '.exe' : ''}',
        ),
      );
    });

    test('no VERSION says no installed version was found', () {
      final doc = check()!;
      expect(doc['error'], 'sw_mismatch');
      expect(doc['message'], contains('no installed version found'));
      expect(doc['message'], contains('rerun the install prompt'));
    });

    test('the project is the first directory at or above with .git', () {
      writeVersion('0.38.0\n');
      final deep = Directory('${project.path}/a/b')
        ..createSync(recursive: true);
      expect(
        versionMismatch(deep.path, version: '0.38.0'),
        isNull,
        reason: 'found the VERSION of the checkout the directory is in',
      );
    });
  });

  group('through runCli', () {
    Future<(int, String, String)> run(List<String> args) async {
      final out = <int>[];
      final text = StringBuffer();
      final err = StringBuffer();
      final code = await runCli(
        args,
        out: text,
        err: err,
        outBytes: out.addAll,
        readStdin: () async => <int>[],
      );
      return (code, text.toString() + utf8.decode(out), err.toString());
    }

    test('a project command in another version stops with exit 1', () async {
      writeVersion('9.9.9\n');
      final (code, out, _) = await run([
        '--project',
        project.path,
        'vcs',
        'state',
      ]);
      expect(code, 1);
      final doc = jsonDecode(out) as Map<String, Object?>;
      expect(doc['error'], 'sw_mismatch');
      expect(doc['message'], contains('9.9.9'));
    });

    test('the command\'s own --code chooses the project', () async {
      writeVersion('9.9.9\n');
      final (code, out, _) = await run([
        'as',
        'someone',
        '--code',
        project.path,
      ]);
      expect(code, 1);
      expect((jsonDecode(out) as Map)['error'], 'sw_mismatch');
    });

    test('the old handoff is not checked here', () async {
      writeVersion('9.9.9\n');
      final (_, out, _) = await run([
        '--project',
        project.path,
        'vcs',
        '--args-stdin',
      ]);
      expect(out, isNot(contains('sw_mismatch')));
    });

    test('two leading --project options are a usage stop, exit 2', () async {
      final (code, out, err) = await run([
        '--project',
        'a',
        '--project',
        'b',
        'vcs',
        'state',
      ]);
      expect(code, 2);
      expect(out, isEmpty);
      expect(err, contains('--project'));
    });

    test('version and pr reviewers check no project version', () async {
      writeVersion('9.9.9\n');
      final (versionCode, versionOut, _) = await run([
        '--project',
        project.path,
        'version',
        '--json',
      ]);
      expect(versionCode, 0);
      expect(versionOut, contains('"version"'));
      final (_, reviewersOut, reviewersErr) = await run([
        '--project',
        project.path,
        'pr',
        'reviewers',
      ]);
      expect(reviewersOut + reviewersErr, isNot(contains('sw_mismatch')));
    });
  });
}
