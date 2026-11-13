import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:crypto/crypto.dart';
import 'package:specwright_cli/src/review/snapshot.dart';
import 'package:specwright_cli/src/review/stop.dart';
import 'package:test/test.dart';

void main() {
  late Directory work;
  late Directory repo;
  final helper = [
    Platform.resolvedExecutable,
    File('bin/sw.dart').absolute.path,
    '__exec',
  ];
  setUp(() async {
    work = Directory.systemTemp.createTempSync('sw-review-snapshot-');
    repo = Directory('${work.path}/repo')..createSync();
    await git(repo, ['init', '-q', '-b', 'main']);
    await git(repo, ['config', 'user.name', 'Snapshot Fixture']);
    await git(repo, ['config', 'user.email', 'fixture@example.invalid']);
    await git(repo, ['config', 'commit.gpgsign', 'false']);
  });
  tearDown(() => work.deleteSync(recursive: true));

  test('copies a multi-chunk binary from the tip despite export-ignore and working changes', () async {
    final bytes = Uint8List.fromList(
      List.generate(256 * 1024 + 17, (i) => (i * 31 + 7) & 255),
    );
    File('${repo.path}/large.bin').writeAsBytesSync(bytes);
    File('${repo.path}/.gitattributes')
        .writeAsStringSync('large.bin export-ignore\n');
    await git(repo, ['add', '-A']);
    await git(repo, ['commit', '-q', '-m', 'fixture']);
    final head = (await git(repo, ['rev-parse', 'HEAD'])).trim();
    File('${repo.path}/large.bin')
        .writeAsStringSync('uncommitted workspace content');
    final dest = Directory('${work.path}/view');
    await snapshotTip(repo.path, head, dest, helperCommand: helper);
    expect(
      sha256
          .convert(File('${dest.path}/large.bin').readAsBytesSync())
          .toString(),
      sha256.convert(bytes).toString(),
    );
    expect(
      File('${repo.path}/large.bin').readAsStringSync(),
      'uncommitted workspace content',
    );
    expect(
      File('${dest.path}/.gitattributes').readAsStringSync(),
      'large.bin export-ignore\n',
    );
  });

  test('inside symlinks remain readable while outside links cannot expose outside contents', () async {
    File('${repo.path}/target.txt').writeAsStringSync('inside fixture\n');
    File('${work.path}/outside.txt').writeAsStringSync('outside secret\n');
    await git(repo, ['add', 'target.txt']);
    for (final (name, target) in [
      ('inside', 'target.txt'),
      ('outside', '../outside.txt'),
    ]) {
      final oid = (await git(repo, [
        'hash-object',
        '-w',
        '--stdin',
      ], input: target)).trim();
      await git(repo, [
        'update-index',
        '--add',
        '--cacheinfo',
        '120000,$oid,$name',
      ]);
    }
    await git(repo, ['commit', '-q', '-m', 'links']);
    final head = (await git(repo, ['rev-parse', 'HEAD'])).trim();
    final dest = Directory('${work.path}/view');
    await snapshotTip(repo.path, head, dest, helperCommand: helper);
    expect(File('${dest.path}/inside').readAsStringSync(), 'inside fixture\n');
    expect(Link('${dest.path}/outside').existsSync(), isFalse);
    expect(File('${dest.path}/outside').readAsStringSync(), '../outside.txt');
  });

  test(
    'a non-UTF-8 tracked name is a named stop, never a replacement-name file',
    () async {
      final raw = Uint8List.fromList([...utf8.encode('${repo.path}/'), 0xff]);
      File.fromRawPath(raw).writeAsStringSync('fixture');
      await git(repo, ['add', '-A']);
      await git(repo, ['commit', '-q', '-m', 'non-utf8']);
      final head = (await git(repo, ['rev-parse', 'HEAD'])).trim();
      await expectLater(
        snapshotTip(
          repo.path,
          head,
          Directory('${work.path}/view'),
          helperCommand: helper,
        ),
        throwsA(isA<ReviewStop>().having((e) => e.error, 'error', 'not_utf8')),
      );
    },
    skip: Platform.isWindows ? 'Windows filesystem names are UTF-16' : false,
  );
}

Future<String> git(Directory repo, List<String> args, {String? input}) async {
  final process = await Process.start('git', args, workingDirectory: repo.path);
  final stdout = process.stdout.transform(utf8.decoder).join();
  final stderr = process.stderr.transform(utf8.decoder).join();
  if (input != null) process.stdin.write(input);
  await process.stdin.close();
  final code = await process.exitCode;
  final message = await stderr;
  expect(code, 0, reason: 'git $args: $message');
  return stdout;
}
