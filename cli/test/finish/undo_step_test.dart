import 'dart:convert';
import 'dart:io';

import 'package:specwright_cli/src/finish/undo_step.dart';
import 'package:test/test.dart';

String _git(String dir, List<String> args) {
  final r = Process.runSync('git', args, workingDirectory: dir);
  if (r.exitCode != 0) fail('git ${args.join(' ')}: ${r.stderr}');
  return (r.stdout as String).trim();
}

/// The doc comment directly above the declaration that starts with
/// [signature] (leading spaces ignored) in [file], joined and unwrapped.
String _docOf(
  String signature, {
  String file = 'lib/src/finish/undo_step.dart',
}) {
  final lines = File(file).readAsLinesSync();
  final at = lines.indexWhere((l) => l.trimLeft().startsWith(signature));
  expect(at, greaterThan(0), reason: '$signature in $file');
  final doc = <String>[];
  for (var i = at - 1; i >= 0 && lines[i].trimLeft().startsWith('///'); i--) {
    doc.insert(0, lines[i].trimLeft().substring(3).trim());
  }
  return doc.join(' ');
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
    Map<String, String>? environment,
    String? at,
  }) async {
    final out = <int>[];
    final code = await runUndoStep(
      args,
      writeOut: out.addAll,
      cwd: at ?? repo,
      stateReader: reader,
      environment: environment,
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

  group('Git guards (D2)', () {
    String gd() => _git(repo, ['rev-parse', '--absolute-git-dir']);

    /// The view `check preflight` is given: what a plan records.
    List<String> view({String? index}) => [
      '--git-dir',
      gd(),
      '--common-dir',
      gd(),
      '--index',
      index ?? '${gd()}/index',
      '--objects',
      '${gd()}/objects',
    ];

    Map<String, String> envWith(Map<String, String> extra) => {
      ...Platform.environment,
      ...extra,
    };

    Future<Map<String, Object?>> stops(
      List<String> args,
      String error, {
      Map<String, String>? environment,
      String? at,
    }) async {
      final (code, doc) = await step(args, environment: environment, at: at);
      expect(code, 1, reason: '$args $doc');
      expect(doc!['error'], error, reason: '$doc');
      return doc;
    }

    void commit(String message) =>
        _git(repo, ['commit', '-q', '-a', '-m', message]);

    test('preflight passes in an ordinary checkout', () async {
      await passes(['check', 'preflight', ...view()]);
    });

    for (final name in [
      'GIT_GLOB_PATHSPECS',
      'GIT_NOGLOB_PATHSPECS',
      'GIT_ICASE_PATHSPECS',
    ]) {
      test('preflight refuses $name when Git reads it as true', () async {
        for (final value in ['1', 'true', 'yes', 'on']) {
          final doc = await stops(
            ['check', 'preflight', ...view()],
            'git_env',
            environment: envWith({name: value}),
          );
          expect(doc['message'], contains(name));
        }
        for (final value in ['', '0', 'false', 'no', 'off']) {
          final (code, _) = await step([
            'check',
            'preflight',
            ...view(),
          ], environment: envWith({name: value}));
          expect(code, 0, reason: '$name=$value');
        }
      });
    }

    for (final name in ['GIT_NAMESPACE', 'GIT_ALTERNATE_OBJECT_DIRECTORIES']) {
      test('preflight refuses a non-empty $name', () async {
        final doc = await stops(
          ['check', 'preflight', ...view()],
          'git_env',
          environment: envWith({name: 'x'}),
        );
        expect(doc['message'], contains(name));
      });
    }

    test('preflight refuses an index routed elsewhere', () async {
      File('${gd()}/undo-index')
          .writeAsBytesSync(File('${gd()}/index').readAsBytesSync());
      final doc = await stops(
        ['check', 'preflight', ...view()],
        'git_env',
        environment: envWith({'GIT_INDEX_FILE': '${gd()}/undo-index'}),
      );
      expect(doc['message'], contains('index'));
    });

    test('preflight stops at the first recorded value that differs', () async {
      final doc = await stops([
        'check',
        'preflight',
        ...view(index: '${gd()}/other-index'),
      ], 'git_env');
      expect(doc['message'], contains('index'));
      expect(doc['message'], contains('other-index'));
    });

    test('preflight refuses a work tree rerouted by configuration', () async {
      final other = Directory('${tmp.path}/elsewhere')..createSync();
      _git(repo, ['config', 'core.worktree', other.path]);
      final doc = await stops(['check', 'preflight', ...view()], 'git_env');
      expect(doc['message'], contains('work tree'));
    });

    test('preflight refuses a grafts file', () async {
      Directory('${gd()}/info').createSync(recursive: true);
      File('${gd()}/info/grafts').writeAsStringSync('\n');
      final doc = await stops(['check', 'preflight', ...view()], 'git_env');
      expect(doc['message'], contains('grafts'));
    });

    test('preflight refuses a partial clone however it shows', () async {
      _git(repo, ['config', 'remote.origin.promisor', 'false']);
      await passes(['check', 'preflight', ...view()]);
      _git(repo, ['config', 'remote.origin.promisor', 'true']);
      var doc = await stops(['check', 'preflight', ...view()], 'git_env');
      expect(doc['message'], contains('partial clone'));
      _git(repo, ['config', '--unset', 'remote.origin.promisor']);
      _git(repo, ['config', 'extensions.partialClone', 'origin']);
      doc = await stops(['check', 'preflight', ...view()], 'git_env');
      expect(doc['message'], contains('partial clone'));
      _git(repo, ['config', '--unset', 'extensions.partialClone']);
      File('${gd()}/objects/pack/pack-x.promisor').writeAsStringSync('');
      doc = await stops(['check', 'preflight', ...view()], 'git_env');
      expect(doc['message'], contains('partial clone'));
    });

    test('preflight refuses a sparse checkout', () async {
      _git(repo, ['config', 'core.sparseCheckout', 'true']);
      final doc = await stops(['check', 'preflight', ...view()], 'git_env');
      expect(doc['message'], contains('sparse checkout'));
    });

    test(
      'preflight refuses GitButler metadata, whatever the settings say',
      () async {
        Directory('${gd()}/gitbutler').createSync();
        await stops(['check', 'preflight', ...view()], 'gitbutler_workspace');
      },
    );

    for (final marker in [
      'MERGE_HEAD',
      'CHERRY_PICK_HEAD',
      'REVERT_HEAD',
      'rebase-merge',
      'rebase-apply',
      'sequencer',
    ]) {
      test('preflight and check index refuse while $marker exists', () async {
        final path = '${gd()}/$marker';
        if (marker.startsWith('rebase') || marker == 'sequencer') {
          Directory(path).createSync();
        } else {
          File(path)
              .writeAsStringSync('${_git(repo, ['rev-parse', 'HEAD'])}\n');
        }
        await stops(['check', 'preflight', ...view()], 'operation_in_progress');
        await stops(['check', 'index'], 'operation_in_progress');
      });
    }

    test('preflight tests run in a fixed order', () async {
      Directory('${gd()}/gitbutler').createSync();
      File('${gd()}/MERGE_HEAD').writeAsStringSync('x\n');
      await stops(['check', 'preflight', ...view()], 'gitbutler_workspace');
      await stops(
        ['check', 'preflight', ...view()],
        'git_env',
        environment: envWith({'GIT_NAMESPACE': 'x'}),
      );
    });

    test(
      'index sees a staged gitlink that diff.ignoreSubmodules hides',
      () async {
        _git(repo, ['config', 'diff.ignoreSubmodules', 'all']);
        final oid = _git(repo, ['rev-parse', 'HEAD']);
        _git(repo, ['update-index', '--add', '--cacheinfo', '160000,$oid,sub']);
        final doc = await fails(['check', 'index']);
        expect(doc['message'], contains('index'));
      },
    );

    test('index sees a staged path that a diff helper would hide', () async {
      _git(repo, ['config', 'diff.external', 'true']);
      _git(repo, ['config', 'diff.trustExitCode', 'true']);
      File('$repo/s.txt').writeAsStringSync('x');
      _git(repo, ['add', 's.txt']);
      await fails(['check', 'index']);
    });

    test('preflight refuses GIT_ATTR_SOURCE and attr.tree', () async {
      var doc = await stops(
        ['check', 'preflight', ...view()],
        'git_env',
        environment: envWith({'GIT_ATTR_SOURCE': 'HEAD'}),
      );
      expect(doc['message'], contains('GIT_ATTR_SOURCE'));
      _git(repo, ['config', 'attr.tree', 'HEAD']);
      doc = await stops(['check', 'preflight', ...view()], 'git_env');
      expect(doc['message'], contains('attr.tree'));
    });

    group('check attributes', () {
      /// An archive branch holding `d/tasks.md` and `d/review.md`, with
      /// [rules] as `d/.gitattributes` when given; back on `main`. Returns
      /// the tip.
      String archiveBranch([String? rules]) {
        _git(repo, ['checkout', '-q', '-b', 'arch']);
        for (final f in ['review.md', 'tasks.md']) {
          File('$repo/d/$f')
            ..createSync(recursive: true)
            ..writeAsStringSync('$f\n');
        }
        if (rules != null) {
          File('$repo/d/.gitattributes').writeAsStringSync(rules);
        }
        _git(repo, ['add', '-A']);
        _git(repo, ['commit', '-q', '-m', 'archive']);
        final tip = _git(repo, ['rev-parse', 'HEAD']);
        _git(repo, ['checkout', '-q', 'main']);
        return tip;
      }

      test('passes when neither side converts the files', () async {
        final tip = archiveBranch('tasks.md text\n');
        await passes([
          'check',
          'attributes',
          tip,
          '--',
          'd/review.md',
          'd/tasks.md',
        ]);
      });

      test('refuses a filter and an unset on the tip', () async {
        for (final rule in [
          'tasks.md filter=sentinel',
          'tasks.md -filter',
          'tasks.md -working-tree-encoding',
        ]) {
          final tip = archiveBranch('$rule\n');
          final (code, doc) = await step([
            'check',
            'attributes',
            tip,
            '--',
            'd/review.md',
            'd/tasks.md',
          ]);
          expect(code, 1, reason: '$rule $doc');
          expect(doc!['error'], 'unsupported_filter', reason: rule);
          expect(doc['message'], contains('d/tasks.md'));
          _git(repo, ['branch', '-q', '-D', 'arch']);
        }
      });

      test('reads the attribute view of the steps, not the plan', () async {
        final tip = archiveBranch();
        final rules = File('${tmp.path}/attributes')
          ..writeAsStringSync('tasks.md filter=sentinel\n');
        final ran = File('${tmp.path}/ran.txt');
        _git(repo, [
          'config',
          'filter.sentinel.smudge',
          'echo ran > "${ran.path.replaceAll(r'\', '/')}"; cat',
        ]);
        final env = envWith({
          'GIT_CONFIG_COUNT': '1',
          'GIT_CONFIG_KEY_0': 'core.attributesFile',
          'GIT_CONFIG_VALUE_0': rules.path.replaceAll(r'\', '/'),
        });
        await passes([
          'check',
          'attributes',
          tip,
          '--',
          'd/review.md',
          'd/tasks.md',
        ]);
        final (code, doc) = await step([
          'check',
          'attributes',
          tip,
          '--',
          'd/review.md',
          'd/tasks.md',
        ], environment: env);
        expect(code, 1, reason: '$doc');
        expect(doc!['error'], 'unsupported_filter');
        expect(doc['message'], contains('d/tasks.md'));
        expect(ran.existsSync(), isFalse);
      });

      test('refuses what HEAD alone converts', () async {
        final tip = archiveBranch();
        File('$repo/.gitattributes').writeAsStringSync('tasks.md -filter\n');
        _git(repo, ['add', '-A']);
        _git(repo, ['commit', '-q', '-m', 'main converts']);
        final (code, doc) = await step([
          'check',
          'attributes',
          tip,
          '--',
          'd/review.md',
          'd/tasks.md',
        ]);
        expect(code, 1, reason: '$doc');
        expect(doc!['error'], 'unsupported_filter');
        expect(doc['message'], contains('HEAD'));
      });
    });

    test('unchanged takes a bracketed path literally', () async {
      File('$repo/a1.txt').writeAsStringSync('one\n');
      _git(repo, ['add', '-A']);
      _git(repo, ['commit', '-q', '-m', 'add a1']);
      final head = _git(repo, ['rev-parse', 'HEAD']);
      File('$repo/a1.txt').writeAsStringSync('two\n');
      commit('change a1');
      await passes(['check', 'unchanged', head, '--', 'a[1].txt']);
      await fails(['check', 'unchanged', head, '--', 'a1.txt']);
    });

    test('unchanged compares a directory recursively', () async {
      File('$repo/d/x.txt').createSync(recursive: true);
      File('$repo/d/y.txt').createSync(recursive: true);
      _git(repo, ['add', '-A']);
      _git(repo, ['commit', '-q', '-m', 'add d']);
      final head = _git(repo, ['rev-parse', 'HEAD']);
      File('$repo/d/y.txt').writeAsStringSync('changed\n');
      commit('change d/y');
      await passes(['check', 'unchanged', head, '--', 'd/x.txt']);
      await fails(['check', 'unchanged', head, '--', 'd']);
    });

    test('clean sees a submodule change that ignore = all hides', () async {
      final sub = Directory('${tmp.path}/subsrc')..createSync();
      _git(sub.path, ['init', '-q', '-b', 'main']);
      for (final kv in [
        ['user.name', 'T'],
        ['user.email', 't@example.com'],
        ['commit.gpgsign', 'false'],
      ]) {
        _git(sub.path, ['config', kv[0], kv[1]]);
      }
      File('${sub.path}/f.txt').writeAsStringSync('one\n');
      _git(sub.path, ['add', '-A']);
      _git(sub.path, ['commit', '-q', '-m', 'sub']);
      _git(repo, [
        '-c',
        'protocol.file.allow=always',
        'submodule',
        'add',
        '-q',
        sub.path,
        'sub',
      ]);
      _git(repo, ['commit', '-q', '-m', 'add the submodule']);
      _git(repo, ['config', 'submodule.sub.ignore', 'all']);
      await passes(['check', 'clean']);
      File('$repo/sub/f.txt').writeAsStringSync('changed\n');
      await fails(['check', 'clean']);
    });

    test(
      'clean refuses an assume-unchanged edit, whole tree or scoped',
      () async {
        File('$repo/b.txt').writeAsStringSync('b\n');
        _git(repo, ['add', 'b.txt']);
        commit('b');
        _git(repo, ['update-index', '--assume-unchanged', 'a.txt']);
        File('$repo/a.txt').writeAsStringSync('hidden edit\n');
        var doc = await stops(['check', 'clean'], 'git_env');
        expect(doc['message'], contains('a.txt'));
        doc = await stops(['check', 'clean', '--', 'a.txt'], 'git_env');
        expect(doc['message'], contains('a.txt'));
        await passes(['check', 'clean', '--', 'b.txt']);
      },
    );

    test('clean refuses a skip-worktree entry', () async {
      _git(repo, ['update-index', '--skip-worktree', 'a.txt']);
      final doc = await stops(['check', 'clean'], 'git_env');
      expect(doc['message'], contains('a.txt'));
    });

    test('tip on a branch ref is an exact branch lookup', () async {
      final head = _git(repo, ['rev-parse', 'HEAD']);
      _git(repo, ['branch', 'feat/x']);
      await passes(['check', 'tip', 'refs/heads/feat/x', head]);
      _git(repo, ['tag', 'refs/heads/feat/x']);
      _git(repo, ['branch', '-D', 'feat/x']);
      await fails(['check', 'tip', 'refs/heads/feat/x', head]);
    });

    test('branch on git stops with git_env when the settings select another '
        'backend', () async {
      File('$repo/openspec/specwright.yaml')
        ..createSync(recursive: true)
        ..writeAsStringSync('vcs: jj\n');
      final doc = await stops([
        'check',
        'branch',
        'main',
        '--backend',
        'git',
      ], 'git_env');
      expect(doc['message'], contains('jj'));
      expect(doc['message'], contains('git'));
    });

    test('a store plan reads the store role from the code operand', () async {
      final code = Directory('${tmp.path}/code')..createSync();
      File('${code.path}/openspec/specwright.yaml')
        ..createSync(recursive: true)
        ..writeAsStringSync('vcs: jj\nplanning_store:\n  vcs: git\n');
      await passes([
        'check',
        'branch',
        'main',
        '--backend',
        'git',
        '--code',
        code.path,
      ]);
      File('${code.path}/openspec/specwright.yaml')
          .writeAsStringSync('planning_store:\n  vcs: jj\n');
      final doc = await stops([
        'check',
        'branch',
        'main',
        '--backend',
        'git',
        '--code',
        code.path,
      ], 'git_env');
      expect(doc['message'], contains('jj'));
    });

    test('branch on git needs Git to read the branch', () async {
      final outside = Directory('${tmp.path}/not-a-repo')..createSync();
      await stops(
        ['check', 'branch', 'main', '--backend', 'git'],
        'vcs_error',
        at: outside.path,
      );
    });
  });

  group('doc comments', () {
    test('checkIndex carries C19', () {
      final doc = _docOf('Future<void> checkIndex(');
      expect(doc, contains('C19'));
      expect(doc, contains('uses `git diff-index --cached`'));
      expect(doc, contains('`--literal-pathspecs` and `--no-replace-objects`'));
    });

    test('the index check carries C31', () {
      final doc = _docOf('Future<void> checkIndex(');
      expect(doc, contains('C31'));
      expect(doc, contains('prints no recovery command'));
      expect(
        doc,
        contains('Rejected: printing an executable recovery command'),
      );
    });

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
