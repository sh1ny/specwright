import 'dart:convert';
import 'dart:io';

import 'package:specwright_cli/src/finish/undo_step.dart';
import 'package:test/test.dart';

String _git(String dir, List<String> args) {
  final r = Process.runSync('git', args, workingDirectory: dir);
  if (r.exitCode != 0) fail('git ${args.join(' ')}: ${r.stderr}');
  return (r.stdout as String).trim();
}

void main() {
  late Directory tmp;
  late String repo;

  setUp(() {
    tmp = Directory.systemTemp.createTempSync('claude-ncrs-g4-');
    repo = '${tmp.path}/work';
    Directory(repo).createSync();
    _git(repo, ['init', '-q', '-b', 'main']);
    for (final kv in [
      ['user.name', 'T'],
      ['user.email', 't@example.com'],
      ['commit.gpgsign', 'false'],
      ['core.autocrlf', 'false'],
    ]) {
      _git(repo, ['config', kv[0], kv[1]]);
    }
    File('$repo/a.txt').writeAsStringSync('one\n');
    _git(repo, ['add', '-A']);
    _git(repo, ['commit', '-q', '-m', 'initial']);
  });
  tearDown(() => tmp.deleteSync(recursive: true));

  /// Runs one step in [repo]: its exit code and the document it printed.
  Future<(int, Map<String, Object?>?)> step(
    List<String> args, {
    UndoStateReader? reader,
  }) async {
    final out = <int>[];
    final code = await runUndoStep(
      args,
      writeOut: out.addAll,
      cwd: repo,
      stateReader: reader,
    );
    return (
      code,
      out.isEmpty ? null : jsonDecode(utf8.decode(out)) as Map<String, Object?>,
    );
  }

  Future<void> passes(List<String> args, {UndoStateReader? reader}) async {
    final (code, doc) = await step(args, reader: reader);
    expect(code, 0, reason: '$args $doc');
    expect(doc, isNull);
  }

  Future<Map<String, Object?>> fails(
    List<String> args, {
    UndoStateReader? reader,
  }) async {
    final (code, doc) = await step(args, reader: reader);
    expect(code, 1, reason: '$args $doc');
    expect(doc!['ok'], false);
    expect(doc['error'], 'undo_step_failed');
    return doc;
  }

  group('file steps', () {
    test('mkdir makes every directory, nested ones too', () async {
      await passes(['mkdir', 'x/y/z', 'w']);
      expect(Directory('$repo/x/y/z').existsSync(), isTrue);
      expect(Directory('$repo/w').existsSync(), isTrue);
    });

    test('copy keeps the source and fails when it is missing', () async {
      await passes(['copy', 'a.txt', 'b.txt']);
      expect(File('$repo/b.txt').readAsStringSync(), 'one\n');
      expect(File('$repo/a.txt').existsSync(), isTrue);
      await fails(['copy', 'nope.txt', 'c.txt']);
    });

    test('copy of a source that is not a regular file is vcs_error naming '
        'it, and writes nothing', () async {
      Directory('$repo/dir').createSync();
      final (code, doc) = await step(['copy', 'dir', 'c.txt']);
      expect(code, 1);
      expect(doc!['error'], 'vcs_error');
      expect(doc['message'], contains('dir'));
      expect(File('$repo/c.txt').existsSync(), isFalse);
    });

    test(
      'copy of a link to a FIFO is vcs_error and does not block (POSIX)',
      () async {
        if (Platform.isWindows) {
          markTestSkipped('no FIFO on Windows');
          return;
        }
        Process.runSync('mkfifo', ['$repo/pipe']);
        Link('$repo/marker.yaml').createSync('$repo/pipe');
        final (code, doc) = await step(['copy', 'marker.yaml', 'backup.yaml']);
        expect(code, 1);
        expect(doc!['error'], 'vcs_error');
        expect(doc['message'], contains('marker.yaml'));
        expect(File('$repo/backup.yaml').existsSync(), isFalse);
      },
      timeout: const Timeout(Duration(seconds: 60)),
    );

    test('move renames a directory and a file', () async {
      File('$repo/d/f.txt').createSync(recursive: true);
      await passes(['move', 'd', 'e']);
      expect(File('$repo/e/f.txt').existsSync(), isTrue);
      expect(Directory('$repo/d').existsSync(), isFalse);
      await passes(['move', 'a.txt', 'z.txt']);
      expect(File('$repo/z.txt').readAsStringSync(), 'one\n');
      await fails(['move', 'missing', 'else']);
    });

    test('remove deletes files and ignores a missing one', () async {
      File('$repo/g.txt').writeAsStringSync('x');
      await passes(['remove', 'g.txt', 'never-there.txt']);
      expect(File('$repo/g.txt').existsSync(), isFalse);
      expect(File('$repo/a.txt').existsSync(), isTrue);
    });

    test('rmdir-if-empty removes an empty directory only', () async {
      Directory('$repo/empty').createSync();
      File('$repo/held/other.md').createSync(recursive: true);
      await passes(['rmdir-if-empty', 'empty']);
      expect(Directory('$repo/empty').existsSync(), isFalse);
      await passes(['rmdir-if-empty', 'held', 'missing']);
      expect(File('$repo/held/other.md').existsSync(), isTrue);
    });

    test('write-text writes the text and a newline', () async {
      await passes(['write-text', 'msg.txt', 'feat(x): undo archive of x']);
      expect(
        File('$repo/msg.txt').readAsStringSync(),
        'feat(x): undo archive of x\n',
      );
    });

    test('write-blob writes the bytes a checkout would write', () async {
      File('$repo/.gitattributes').writeAsStringSync('*.crlf text eol=crlf\n');
      File('$repo/f.crlf').writeAsStringSync('l1\nl2\n');
      _git(repo, ['add', '-A']);
      _git(repo, ['commit', '-q', '-m', 'crlf']);
      await passes(['write-blob', 'HEAD', 'f.crlf', 'out.bin']);
      expect(
        File('$repo/out.bin').readAsBytesSync(),
        utf8.encode('l1\r\nl2\r\n'),
      );
      await fails(['write-blob', 'HEAD', 'nope.crlf', 'out2.bin']);
      expect(File('$repo/out2.bin').existsSync(), isFalse);
    });

    test('merge-back merges, or stops at a conflict with markers', () async {
      File('$repo/base.md').writeAsStringSync('a\nb\nc\n');
      File('$repo/amended.md').writeAsStringSync('a\nb mine\nc\n');
      File('$repo/ok.md').writeAsStringSync('a\nb\nc\nd\n');
      await passes(['merge-back', 'ok.md', 'base.md', 'amended.md']);
      expect(File('$repo/ok.md').readAsStringSync(), 'a\nb mine\nc\nd\n');
      File('$repo/clash.md').writeAsStringSync('a\nb theirs\nc\n');
      await fails(['merge-back', 'clash.md', 'base.md', 'amended.md']);
      expect(
        File('$repo/clash.md').readAsStringSync(),
        contains('<<<<<<< rerun'),
      );
    });

    test('a step with the wrong number of arguments is a usage stop', () async {
      final (code, doc) = await step(['copy', 'only-one']);
      expect(code, 2);
      expect(doc!['error'], 'usage');
    });

    test('an unknown kind is a usage stop', () async {
      final (code, doc) = await step(['frobnicate']);
      expect(code, 2);
      expect(doc!['error'], 'usage');
      final (code2, _) = await step(['check', 'frobnicate']);
      expect(code2, 2);
    });
  });

  group('check', () {
    test('absent passes for a missing path and names a present one', () async {
      await passes(['check', 'absent', 'nope']);
      final doc = await fails(['check', 'absent', 'a.txt']);
      expect(doc['message'], 'a.txt exists');
      final said = await fails([
        'check',
        'absent',
        'a.txt',
        '--message',
        'move it',
      ]);
      expect(said['message'], 'move it');
    });

    test('tip passes at the planned commit and fails at another', () async {
      final head = _git(repo, ['rev-parse', 'HEAD']);
      await passes(['check', 'tip', 'HEAD', head]);
      await passes(['check', 'tip', 'refs/heads/main', head]);
      File('$repo/a.txt').writeAsStringSync('two\n');
      _git(repo, ['commit', '-q', '-am', 'later']);
      await fails(['check', 'tip', 'HEAD', head]);
    });

    test('index fails when something is staged', () async {
      await passes(['check', 'index']);
      File('$repo/s.txt').writeAsStringSync('x');
      _git(repo, ['add', 's.txt']);
      await fails(['check', 'index']);
    });

    test('clean looks at the given paths, or at the whole tree', () async {
      await passes(['check', 'clean']);
      File('$repo/new/u.txt').createSync(recursive: true);
      await fails(['check', 'clean']);
      await fails(['check', 'clean', '--', 'new']);
      await passes(['check', 'clean', '--', 'a.txt']);
    });

    test(
      'unchanged compares the paths with a revision, with a message',
      () async {
        final head = _git(repo, ['rev-parse', 'HEAD']);
        await passes(['check', 'unchanged', head, '--', 'a.txt']);
        File('$repo/a.txt').writeAsStringSync('two');
        _git(repo, ['commit', '-q', '-am', 'later']);
        final doc = await fails([
          'check',
          'unchanged',
          head,
          '--message',
          'another applied branch changes a path the undo restores',
          '--',
          'a.txt',
        ]);
        expect(
          doc['message'],
          'another applied branch changes a path the undo restores',
        );
      },
    );

    test('a failing step says why on stderr too', () async {
      final said = <String>[];
      final out = <int>[];
      final code = await runUndoStep(
        ['check', 'absent', 'a.txt', '--message', 'move a.txt away'],
        writeOut: out.addAll,
        writeErr: said.add,
        cwd: repo,
      );
      expect(code, 1);
      expect(said, ['move a.txt away']);
    });

    test('branch on git reads the current branch and names both', () async {
      await passes(['check', 'branch', 'main']);
      final doc = await fails(['check', 'branch', 'feat/x']);
      expect(doc['message'], contains('main'));
      expect(doc['message'], contains('feat/x'));
    });

    test('branch refuses a settings file that is not a regular file', () async {
      Directory('$repo/openspec/specwright.yaml').createSync(recursive: true);
      final (code, doc) = await step(['check', 'branch', 'main']);
      expect(code, 1);
      expect(doc!['error'], 'vcs_error');
      expect(doc['message'], contains('openspec/specwright.yaml'));
    });

    test(
      'branch refuses a settings link to a FIFO without blocking (POSIX)',
      () async {
        if (Platform.isWindows) {
          markTestSkipped('no FIFO on Windows');
          return;
        }
        Process.runSync('mkfifo', ['$repo/pipe']);
        Directory('$repo/openspec').createSync();
        Link('$repo/openspec/specwright.yaml').createSync('$repo/pipe');
        final (code, doc) = await step(['check', 'branch', 'main']);
        expect(code, 1);
        expect(doc!['error'], 'vcs_error');
      },
      timeout: const Timeout(Duration(seconds: 60)),
    );

    for (final backend in ['jj', 'gitbutler']) {
      test('branch on $backend reads the structured branch', () async {
        String? seenCode;
        String? seenBranch;
        Future<Map<String, Object?>> reader(
          String top,
          String? code,
          String? branch,
        ) async {
          seenCode = code;
          seenBranch = branch;
          return {'ok': true, 'backend': backend, 'branch': 'feat/x'};
        }

        // the planned branch passes; the old guard's text search could not
        // tell `feat/x` from a branch that only contains it
        await passes([
          'check',
          'branch',
          'feat/x',
          '--backend',
          backend,
        ], reader: reader);
        expect(seenBranch, backend == 'gitbutler' ? 'feat/x' : isNull);
        final other = await fails([
          'check',
          'branch',
          'feat/',
          '--backend',
          backend,
          '--code',
          'cd',
        ], reader: reader);
        expect(seenCode, 'cd');
        expect(other['message'], contains('feat/x'));
        expect(other['message'], contains('feat/'));
      });
    }
  });

  group('doc comments', () {
    test('runUndoStep carries C5', () {
      final src = File('lib/src/finish/undo_step.dart').readAsStringSync();
      final at = src.indexOf('Future<int> runUndoStep(');
      expect(at, greaterThan(0));
      final doc = src
          .substring(0, at)
          .split('\n')
          .reversed
          .takeWhile((l) => l.startsWith('///') || l.trim().isEmpty)
          .toList()
          .reversed
          .join('\n');
      expect(doc, contains('C5'));
      expect(
        doc,
        contains(
          'The undo primitives exist so a plan stays something the user runs step',
        ),
      );
      expect(doc, contains('no command may run a whole undo'));
    });
  });
}
