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
    'forward link chains remain readable without exposing outside targets',
    () async {
      File('${repo.path}/target.txt').writeAsStringSync('chain contents\n');
      Directory('${repo.path}/folder').createSync();
      File('${repo.path}/folder/seed.txt')
          .writeAsStringSync('directory contents\n');
      File('${work.path}/outside.txt').writeAsStringSync('outside secret\n');
      await git(repo, ['add', 'target.txt', 'folder/seed.txt']);
      for (final (name, target) in [
        ('a', 'b'),
        ('b', 'target.txt'),
        ('dir-a', 'dir-b'),
        ('dir-b', 'folder'),
        ('folder/linked', '../target.txt'),
        ('a-through-dir', 'dir-a/linked'),
        ('cycle-a', 'cycle-b'),
        ('cycle-b', 'cycle-a'),
        ('escape-a', 'escape-b'),
        ('escape-b', '../outside.txt'),
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
      await git(repo, ['commit', '-q', '-m', 'forward link chains']);
      final head = (await git(repo, ['rev-parse', 'HEAD'])).trim();
      final dest = Directory('${work.path}/view');
      await snapshotTip(repo.path, head, dest, helperCommand: helper);
      expect(File('${dest.path}/a').readAsStringSync(), 'chain contents\n');
      expect(
        File('${dest.path}/a-through-dir').readAsStringSync(),
        'chain contents\n',
      );
      expect(
        File('${dest.path}/dir-a/linked').readAsStringSync(),
        'chain contents\n',
      );
      expect(
        File('${dest.path}/dir-a/seed.txt').readAsStringSync(),
        'directory contents\n',
      );
      for (final (name, target) in [
        ('cycle-a', 'cycle-b'),
        ('cycle-b', 'cycle-a'),
        ('escape-a', 'escape-b'),
        ('escape-b', '../outside.txt'),
      ]) {
        expect(Link('${dest.path}/$name').existsSync(), isFalse);
        expect(File('${dest.path}/$name').readAsStringSync(), target);
      }
    },
  );

  test(
    'a non-UTF-8 tracked name is a named stop, never a replacement-name file',
    () async {
      File('${repo.path}/fixture.txt').writeAsStringSync('fixture');
      final blob = (await git(repo, [
        'hash-object',
        '-w',
        'fixture.txt',
      ])).trim();
      final treeFile = File('${work.path}/raw-tree');
      treeFile.writeAsBytesSync([
        ...ascii.encode('100644 '),
        0xff,
        0,
        for (var i = 0; i < blob.length; i += 2)
          int.parse(blob.substring(i, i + 2), radix: 16),
      ]);
      final tree = (await git(repo, [
        'hash-object',
        '-w',
        '-t',
        'tree',
        treeFile.path,
      ])).trim();
      final head = (await git(repo, [
        'commit-tree',
        tree,
      ], input: 'non-utf8\n')).trim();
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
