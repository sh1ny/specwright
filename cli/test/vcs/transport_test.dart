import 'dart:convert';
import 'dart:io';

import 'package:specwright_cli/src/vcs/tool_runner.dart';
import 'package:test/test.dart';

import 'bash_support.dart';

/// A4 (design D3): in Git Bash, `read -r -d ''` on a pipe consumes stdin only
/// up to each NUL, so the bytes after the N-th record stay unread for the
/// exec'd tool. This runs the production prelude, with `git check-ignore -z
/// --stdin` as the tool.
void main() {
  final bash = findBash();
  final skip = bash == null ? 'no bash installed' : false;

  List<int> records(List<String> parts) => [
    for (final p in parts) ...[...utf8.encode(p), 0],
  ];

  late Directory repo;
  setUp(() {
    repo = Directory.systemTemp.createTempSync('claude-ncv-g2-');
  });
  tearDown(() => repo.deleteSync(recursive: true));

  test('A4: bytes after the N-th record stay on stdin for the tool', () async {
    final git = Process.runSync('git', [
      'init',
      '-q',
    ], workingDirectory: repo.path);
    expect(git.exitCode, 0);
    File('${repo.path}/.gitignore').writeAsStringSync('ignored.txt\n');
    final framed = [
      ...frameCommand(repo.path, ['git', 'check-ignore', '-z', '--stdin']),
      ...records(['ignored.txt', 'kept.txt']),
    ];
    final r = await runFramed(bash!, framed);
    expect(r.exitCode, 0);
    expect(r.stdout, [...utf8.encode('ignored.txt'), 0]);
  }, skip: skip);

  test('non-digit count exits 126 before any tool runs', () async {
    final r = await runFramed(bash!, [
      ...records([cwdRecord(repo.path), 'x', 'touch', 'ran']),
    ]);
    expect(r.exitCode, 126);
    expect(File('${repo.path}/ran').existsSync(), isFalse);
  }, skip: skip);

  test('fewer records than the count exits 126 before any tool runs', () async {
    final r = await runFramed(bash!, [
      ...records([cwdRecord(repo.path), '3', 'touch', 'ran']),
    ]);
    expect(r.exitCode, 126);
    expect(File('${repo.path}/ran').existsSync(), isFalse);
  }, skip: skip);
}
