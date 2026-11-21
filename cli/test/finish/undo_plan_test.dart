import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:specwright_cli/src/commands/finish.dart';
import 'package:specwright_cli/src/finish/script_text.dart';
import 'package:specwright_cli/src/finish/undo_plan.dart';
import 'package:specwright_cli/src/process/command_line.dart'
    show commandLineUnits;
import 'package:specwright_cli/src/commands/version.dart' show buildVersion;
import 'package:specwright_cli/src/vcs/jj_backend.dart'
    show bookmarkTemplate, exactPattern;
import 'package:specwright_cli/src/vcs/stop.dart';
import 'package:specwright_cli/src/vcs/tool_runner.dart'
    show ToolResult, runTool;
import 'package:test/test.dart';

import '../vcs/bash_support.dart';
import '../support/exe_shim.dart';

List<int> _b(String s) => utf8.encode(s);

String _posix(String p) => p.replaceAll(r'\', '/');

const String _date = '2026-10-19';

/// The commit [branch] points at in [repo].
String _headOf(String repo, String branch) =>
    (Process.runSync('git', [
              'rev-parse',
              'refs/heads/$branch',
            ], workingDirectory: repo).stdout
            as String)
        .trim();

/// Matches a list of steps that holds [argv] (lists compare by value).
Matcher hasStep(List<String> argv) => contains(equals(argv));

/// The index of the step [argv] in [steps], or -1.
int indexOfStep(List<List<String>> steps, List<String> argv) =>
    steps.indexWhere((s) => equals(argv).matches(s, {}));

/// The argv of each printed step.
List<List<String>> argvsOf(Object? steps) => [
  for (final s in steps! as List) ((s! as Map)['argv']! as List).cast<String>(),
];

/// The argv of an `sw --project <project> finish undo-step <rest>` step.
List<String> undoStep(String project, List<String> rest) => [
  Platform.resolvedExecutable,
  '--project',
  project,
  'finish',
  'undo-step',
  ...rest,
];

/// The argv of an `sw --project <project> <rest>` step.
List<String> swStep(String project, List<String> rest) => [
  Platform.resolvedExecutable,
  '--project',
  project,
  ...rest,
];

/// The global options every emitted Git step carries.
const List<String> _g = ['git', '--literal-pathspecs', '--no-replace-objects'];

/// The `check preflight` step a Git plan for [repo] starts with.
List<String> preflightStep(String repo) {
  String out(List<String> args) => _gitOut(repo, args);
  return undoStep(out(['rev-parse', '--show-toplevel']), [
    'check',
    'preflight',
    '--git-dir',
    out(['rev-parse', '--absolute-git-dir']),
    '--common-dir',
    out(['rev-parse', '--path-format=absolute', '--git-common-dir']),
    '--index',
    out(['rev-parse', '--path-format=absolute', '--git-path', 'index']),
    '--objects',
    out(['rev-parse', '--path-format=absolute', '--git-path', 'objects']),
  ]);
}

/// The version stamp the running `sw` checks in the project at [dir].
void stamp(String dir, [String version = buildVersion]) =>
    put(dir, 'openspec/.specwright/VERSION', '$version\n');

void put(String repo, String rel, String text) {
  final f = File('$repo/$rel');
  f.parent.createSync(recursive: true);
  f.writeAsStringSync(text);
}

String read(String repo, String rel) => File('$repo/$rel').readAsStringSync();

String baseSpec(String cap) =>
    '# $cap Specification\n\n## Purpose\nBaseline purpose of $cap.\n\n'
    '## Requirements\n\n### Requirement: Old thing\nThe system SHALL do old.\n\n'
    '#### Scenario: Old\n- **WHEN** x\n- **THEN** y\n';

String deltaText(String req) =>
    '## ADDED Requirements\n\n### Requirement: $req\n'
    'The system SHALL do ${req.toLowerCase()}.\n\n'
    '#### Scenario: $req\n- **WHEN** a\n- **THEN** b\n';

String _gitOut(String dir, List<String> args) {
  final r = Process.runSync('git', args, workingDirectory: dir);
  if (r.exitCode != 0) fail('git ${args.join(' ')}: ${r.stderr}');
  return (r.stdout as String).trim();
}

String commitAll(String repo, String subject) {
  _gitOut(repo, ['add', '-A']);
  _gitOut(repo, ['commit', '-q', '-m', subject]);
  return _gitOut(repo, ['rev-parse', 'HEAD']);
}

/// `openspec/changes/<name>/` with its artifacts, one delta spec per
/// `{capability: requirement title}`; committed unless [commit] is false.
void makeChange(
  String repo,
  String name, {
  String verdict = 'DEFERRED',
  Map<String, String> deltas = const {},
  String tasks = '# Tasks\n\n- [ ] 1.1 do it\n',
  bool commit = true,
}) {
  final base = 'openspec/changes/$name';
  put(repo, '$base/.openspec.yaml', 'schema: specwright\n');
  put(repo, '$base/proposal.md', '## Why\n\nBecause $name.\n');
  put(repo, '$base/design.md', '# Design\n\nOriginal design.\n');
  put(repo, '$base/tasks.md', tasks);
  put(repo, '$base/review.md', '# Review\n\n## Verdict\n\nVERDICT: $verdict\n');
  deltas.forEach((cap, req) {
    put(repo, '$base/specs/$cap/spec.md', deltaText(req));
  });
  if (commit) commitAll(repo, 'docs($name): add planning artifacts');
}

/// What `openspec archive` does to a main spec: append the delta's
/// requirements, creating the spec when it is absent.
void syncDelta(String repo, String cap, String delta) {
  final body = delta
      .split('\n')
      .where((l) => !l.startsWith('## '))
      .join('\n')
      .replaceAll(RegExp(r'^\n+|\n+$'), '');
  final rel = 'openspec/specs/$cap/spec.md';
  final f = File('$repo/$rel');
  if (f.existsSync()) {
    final text = f.readAsStringSync().replaceAll(RegExp(r'\n+$'), '');
    f.writeAsStringSync('$text\n\n$body\n');
  } else {
    put(repo, rel, '# $cap Specification\n\n## Requirements\n\n$body\n');
  }
}

/// Moves a change to `changes/archive/<date>-<name>/` and syncs its deltas.
void archiveOne(
  String repo,
  String name, {
  String date = _date,
  bool marker = false,
}) {
  final src = Directory('$repo/openspec/changes/$name');
  final dst = Directory('$repo/openspec/changes/archive/$date-$name');
  dst.parent.createSync(recursive: true);
  src.renameSync(dst.path);
  final specs = Directory('${dst.path}/specs');
  if (specs.existsSync()) {
    final found =
        specs
            .listSync(recursive: true)
            .whereType<File>()
            .where((f) => f.path.endsWith('spec.md'))
            .toList()
          ..sort((a, b) => a.path.compareTo(b.path));
    for (final f in found) {
      final rel = _posix(f.path).substring(_posix(specs.path).length + 1);
      if (rel == 'spec.md') continue;
      final cap = rel.substring(0, rel.length - '/spec.md'.length);
      syncDelta(repo, cap, f.readAsStringSync());
    }
  }
  if (marker) {
    put(
      repo,
      'openspec/changes/archive/$date-$name/specwright-change.yaml',
      'code_changes: none\n',
    );
  }
}

/// Archives [names]; commits the move when [commitIt]. Returns the commit.
String? archive(
  String repo,
  List<String> names, {
  bool commitIt = false,
  bool marker = false,
}) {
  for (final n in names) {
    archiveOne(repo, n, marker: marker);
  }
  if (!commitIt) return null;
  return commitAll(repo, 'chore(${names.join(', ')}): archive change');
}

/// What `sw finish` would print and exit with.
class _Out {
  _Out(this.code, this.doc);

  final int code;
  final Map<String, Object?> doc;
}

/// A stub tool first on `PATH`: it logs its arguments (and
/// `$GIT_TERMINAL_PROMPT`) to `$STUB_LOG`, then exits `$STUB_EXIT`.
const String _stubTool = r'''#!/bin/sh
printf '%s|%s\n' "$*" "${GIT_TERMINAL_PROMPT-unset}" >> "$STUB_LOG"
if [ -n "$STUB_OUT" ]; then printf "$STUB_OUT"; fi
exit "${STUB_EXIT:-1}"
''';

void main() {
  useExeShim();
  final bash = findBash();
  final skip = bash == null ? 'no bash installed' : false;
  late Directory tmp;

  setUp(() {
    tmp = Directory.systemTemp.createTempSync('claude-ncf-g3-');
    // the planner checks the version of the project it plans in, also for a
    // directory that holds no repository
    stamp(tmp.path);
  });
  tearDown(() => tmp.deleteSync(recursive: true));

  FinishContext context({Map<String, String>? environment, bool? windows}) =>
      FinishContext(environment: environment, windows: windows);

  FinishContext readerCtx(
    Future<Map<String, Object?>> Function(String, String?, String?) reader,
  ) => FinishContext(stateReader: reader);

  Future<_Out> plan(UndoRequest request, [FinishContext? ctx]) async {
    try {
      return _Out(0, await undoArchivePlan(request, ctx ?? context()));
    } on VcsStop catch (stop) {
      return _Out(stop.code, stop.object());
    }
  }

  UndoRequest request(
    String dir, {
    String? change = 'x',
    String? archived = '2026-01-01-x',
    String? prefix = 'openspec',
    String? main = 'main',
    String? branch,
    String? type,
    String? code,
  }) => UndoRequest(
    dir: dir,
    change: change,
    archived: archived,
    prefix: prefix,
    main: main,
    branch: branch,
    type: type,
    code: code,
  );

  String git(String dir, List<String> args) {
    final r = Process.runSync('git', args, workingDirectory: dir);
    if (r.exitCode != 0) fail('git ${args.join(' ')}: ${r.stderr}');
    return (r.stdout as String).trim();
  }

  /// A work tree on `main` with one commit.
  String makeRepo([String name = 'work']) {
    final dir = Directory('${tmp.path}/$name')..createSync();
    git(dir.path, ['init', '-q', '-b', 'main']);
    for (final kv in [
      ['user.name', 'T'],
      ['user.email', 't@example.com'],
      ['commit.gpgsign', 'false'],
      ['core.autocrlf', 'false'],
    ]) {
      git(dir.path, ['config', kv[0], kv[1]]);
    }
    File('${dir.path}/README.md').writeAsStringSync('# demo\n');
    // the version the running sw checks, committed in the first commit so it
    // is never dirty-tree evidence
    put(dir.path, 'openspec/.specwright/VERSION', '$buildVersion\n');
    for (final cap in ['a', 'b']) {
      put(dir.path, 'openspec/specs/$cap/spec.md', baseSpec(cap));
    }
    git(dir.path, ['add', '-A']);
    git(dir.path, ['commit', '-q', '-m', 'initial']);
    return dir.path;
  }

  group('entry checks (task 3.2)', () {
    test('missing --main is a usage stop', () async {
      final r = await plan(request(tmp.path, main: null));
      expect(r.code, 2);
      expect(r.doc, {
        'ok': false,
        'error': 'usage',
        'message': 'undo-archive-plan needs --main',
      });
    });

    test('each missing option names itself, in finish.sh order', () async {
      final cases = <(UndoRequest, String)>[
        (UndoRequest(dir: tmp.path), 'undo-archive-plan needs --change'),
        (
          UndoRequest(dir: tmp.path, change: 'x'),
          'undo-archive-plan needs --archived-name',
        ),
        (
          UndoRequest(dir: tmp.path, change: 'x', archived: 'a'),
          'undo-archive-plan needs --prefix',
        ),
        (
          UndoRequest(dir: tmp.path, change: 'x', archived: 'a', prefix: 'p'),
          'undo-archive-plan needs --main',
        ),
      ];
      for (final (req, message) in cases) {
        final r = await plan(req);
        expect(r.code, 2, reason: message);
        expect(r.doc['error'], 'usage');
        expect(r.doc['message'], message);
      }
    });

    test('an empty option value is given, not missing', () async {
      final r = await plan(request(tmp.path, main: ''));
      expect(r.doc['error'], 'not_a_repo');
    });

    test('a directory outside a work tree is not_a_repo', () async {
      final r = await plan(request(tmp.path));
      expect(r.code, 1);
      expect(r.doc, {
        'ok': false,
        'error': 'not_a_repo',
        'message': '${tmp.path} is not inside a git work tree',
      });
    }, skip: skip);

    test('a missing directory is not_a_repo too', () async {
      final missing = '${tmp.path}/nope';
      final r = await plan(request(missing));
      expect(r.code, 1);
      expect(r.doc['error'], 'not_a_repo');
      expect(r.doc['message'], '$missing is not inside a git work tree');
    }, skip: skip);

    test('a repository with no commit is not_a_repo', () async {
      final dir = Directory('${tmp.path}/empty')..createSync();
      git(dir.path, ['init', '-q', '-b', 'main']);
      stamp(dir.path);
      final r = await plan(request(dir.path));
      expect(r.code, 1);
      expect(r.doc, {
        'ok': false,
        'error': 'not_a_repo',
        'message': 'the repository has no commit',
      });
    }, skip: skip);

    test('a main that is no commit is bad_ref', () async {
      final repo = makeRepo();
      final r = await plan(request(repo, main: 'nope'));
      expect(r.code, 1);
      expect(r.doc, {
        'ok': false,
        'error': 'bad_ref',
        'message': 'nope is not a commit',
      });
    }, skip: skip);

    test('a detached HEAD without --branch is a usage stop', () async {
      final repo = makeRepo();
      git(repo, ['checkout', '-q', '--detach']);
      final r = await plan(request(repo));
      expect(r.code, 2);
      expect(r.doc, {
        'ok': false,
        'error': 'usage',
        'message': '--branch is required on a detached HEAD',
      });
    }, skip: skip);

    test('a stop from the state read keeps its error and message', () async {
      final repo = makeRepo();
      final r = await plan(
        request(repo, code: '${_posix(tmp.path)}/not/there'),
      );
      expect(r.code, 1);
      expect(r.doc, {
        'ok': false,
        'error': 'not_repository',
        'message': '--repo and --code must name existing directories',
      });
    }, skip: skip);

    test(
      'a relative --code is joined to the top before the state read',
      () async {
        final repo = makeRepo();
        Directory('$repo/codedir').createSync();
        // Relative to the test process it names nothing: only the join to the
        // work tree's top lets the state read find the directory.
        expect(Directory('codedir').existsSync(), isFalse);
        final r = await plan(request(repo, main: 'nope', code: 'codedir'));
        expect(r.doc['error'], 'bad_ref');
        expect(r.doc['message'], 'nope is not a commit');
      },
      skip: skip,
    );

    test('a relative --code that names nothing is not_repository', () async {
      final repo = makeRepo();
      final r = await plan(request(repo, code: 'codedir'));
      expect(r.doc['error'], 'not_repository');
    }, skip: skip);

    test('git runs with GIT_TERMINAL_PROMPT=0 unless it is set', () async {
      final stubs = Directory('${tmp.path}/stubs')..createSync();
      final stub = File('${stubs.path}/git')..writeAsStringSync(_stubTool);
      if (!Platform.isWindows) Process.runSync('chmod', ['+x', stub.path]);
      shimExe(stub.path);
      final log = File('${tmp.path}/git.log');
      final sep = Platform.isWindows ? ';' : ':';
      Map<String, String> env([String? prompt]) => {
        for (final e in Platform.environment.entries)
          if (e.key != 'GIT_TERMINAL_PROMPT') e.key: e.value,
        'PATH': '${stubs.path}$sep${Platform.environment['PATH'] ?? ''}',
        'STUB_LOG': _posix(log.path),
        'STUB_EXIT': '1',
        'GIT_TERMINAL_PROMPT': ?prompt,
      };
      var r = await plan(request(tmp.path), context(environment: env()));
      expect(r.doc['error'], 'not_a_repo');
      expect(
        log.readAsStringSync().trim(),
        '--literal-pathspecs --no-replace-objects rev-parse --show-toplevel|0',
      );
      log.deleteSync();
      r = await plan(request(tmp.path), context(environment: env('1')));
      expect(r.doc['error'], 'not_a_repo');
      expect(
        log.readAsStringSync().trim(),
        '--literal-pathspecs --no-replace-objects rev-parse --show-toplevel|1',
      );
    }, skip: skip);

    test('a git that cannot start (exit 127) is not_a_repo', () async {
      final empty = Directory('${tmp.path}/nobin')..createSync();
      final r = await plan(
        request(tmp.path),
        context(
          environment: {
            for (final e in Platform.environment.entries)
              if (e.key != 'PATH') e.key: e.value,
            'PATH': empty.path,
          },
        ),
      );
      expect(r.code, 1);
      expect(r.doc['error'], 'not_a_repo');
    }, skip: skip);
  });

  group('--dir and --code paths (task 3.2, D6)', () {
    late Directory stubs;
    late File log;
    Map<String, String> env({String out = '', int exit = 1}) {
      final sep = Platform.isWindows ? ';' : ':';
      return {
        ...Platform.environment,
        'PATH': '${stubs.path}$sep${Platform.environment['PATH'] ?? ''}',
        'STUB_LOG': _posix(log.path),
        'STUB_OUT': out,
        'STUB_EXIT': '$exit',
      };
    }

    setUp(() {
      stubs = Directory('${tmp.path}/stubs')..createSync();
      log = File('${tmp.path}/tool.log');
      final stub = File('${stubs.path}/git')..writeAsStringSync(_stubTool);
      if (!Platform.isWindows) Process.runSync('chmod', ['+x', stub.path]);
      shimExe(stub.path);
    });

    test('an MSYS-form --dir is used as given, not converted', () async {
      final r = await plan(
        request('/c/sw-none/dir'),
        context(environment: env()),
      );
      expect(r.code, 1);
      expect(r.doc['error'], 'not_a_repo');
      expect(r.doc['message'], '/c/sw-none/dir is not inside a git work tree');
    }, skip: skip);

    test('an MSYS-form --code is no bad_path stop', () async {
      final r = await plan(
        request('C:/no/such/dir', code: '/c/sw-none/code'),
        context(environment: env()),
      );
      expect(r.doc['error'], isNot('bad_path'));
    }, skip: skip);

    test('a usage stop comes before any git call', () async {
      final r = await plan(
        request('/no/such/dir', main: null),
        context(environment: env()),
      );
      expect(r.code, 2);
      expect(r.doc['error'], 'usage');
      expect(log.existsSync(), isFalse);
    }, skip: skip);
  });

  group('doc comments (task 3.2)', () {
    test('undoArchivePlan carries C2, C4 and C8', () {
      final src = File('lib/src/finish/undo_plan.dart').readAsStringSync();
      final at = src.indexOf('Future<Map<String, Object?>> undoArchivePlan(');
      expect(at, greaterThan(0));
      final doc = src
          .substring(0, at)
          .split('\n')
          .reversed
          .takeWhile((l) => l.startsWith('///') || l.trim().isEmpty)
          .toList()
          .reversed
          .join('\n');
      expect(doc, contains('no deadline and no byte bound'));
      expect(doc, contains('ADR 0012'));
      expect(doc, contains('Line-anchored patterns anchor at'));
      expect(doc, contains('os.walk'));
      expect(doc, contains('never `Directory.list()`'));
      expect(doc, contains('GitButler parity'));
      expect(doc, contains('#154'));
      // ADR 0043 and C36
      expect(doc, contains('ADR 0043'));
      expect(doc, contains('does not prove that the project'));
    });

    String docAbove(String file, String declaration) {
      final lines = File(file).readAsLinesSync();
      final at = lines.indexWhere((l) => l.startsWith(declaration));
      expect(at, greaterThan(0), reason: '$declaration in $file');
      final doc = <String>[];
      for (var i = at - 1; i >= 0 && lines[i].startsWith('///'); i--) {
        doc.insert(0, lines[i].substring(3).trim());
      }
      return doc.join(' ');
    }

    test('undoArchivePlan carries C28, C44 and C45', () {
      final doc = docAbove(
        'lib/src/finish/undo_plan.dart',
        'Future<Map<String, Object?>> undoArchivePlan(',
      );
      expect(doc, contains('C28:'));
      expect(
        doc,
        contains('`check clean` is emitted only for a committed archive'),
      );
      expect(doc, contains('C44:'));
      expect(doc, contains('`for-each-ref` leaves out a broken ref'));
      expect(doc, contains('reports `no_archive` rather than `vcs_error`'));
      expect(doc, contains('C45:'));
      expect(doc, contains('scans the whole index for assume-unchanged'));
      expect(doc, contains('never collects the whole output'));
    });

    /// The doc comment above the local declaration that starts with
    /// [signature] once its indentation is ignored.
    String docOfLocal(String file, String signature) {
      final lines = File(file).readAsLinesSync();
      final at = lines.indexWhere((l) => l.trimLeft().startsWith(signature));
      expect(at, greaterThan(0), reason: '$signature in $file');
      final doc = <String>[];
      for (
        var i = at - 1;
        i >= 0 && lines[i].trimLeft().startsWith('///');
        i--
      ) {
        doc.insert(0, lines[i].trimLeft().substring(3).trim());
      }
      return doc.join(' ');
    }

    test('undoArchivePlan carries C39 and C41', () {
      final doc = docAbove(
        'lib/src/finish/undo_plan.dart',
        'Future<Map<String, Object?>> undoArchivePlan(',
      );
      expect(doc, contains('C39:'));
      expect(doc, contains('though an unset applies no conversion'));
      expect(doc, contains('Rejected: allowing the rendered value `unset`'));
      expect(doc, contains('C41:'));
      expect(doc, contains('apply to Git resumes only'));
      expect(doc, contains('a stored symlink is read as its link text'));
    });

    test('undoArchivePlan carries C30, C42 and the no-file-change line', () {
      final doc = docAbove(
        'lib/src/finish/undo_plan.dart',
        'Future<Map<String, Object?>> undoArchivePlan(',
      );
      expect(doc, contains('The plan changes no file'));
      expect(
        doc,
        contains("jj's own working-copy snapshot and Git ref import"),
      );
      expect(doc, contains('C30:'));
      expect(doc, contains('only a committed archive'));
      expect(doc, contains('`bad_path`'));
      expect(doc, contains('C42:'));
      expect(doc, contains('`ambiguous_branch`'));
      expect(doc, contains('Rejected: reading with `--ignore-working-copy`'));
    });

    test('rerun carries C33', () {
      final doc = docOfLocal(
        'lib/src/finish/undo_plan.dart',
        'final rerun = [',
      );
      expect(doc, contains('C33:'));
      expect(doc, contains('is made once, at planning'));
      expect(doc, contains('are outside the contract and are not guarded'));
      expect(doc, contains('Rejected: a per-member digest guard'));
    });

    test('uniqueMembers carries C40', () {
      final doc = docOfLocal(
        'lib/src/finish/undo_plan.dart',
        'void uniqueMembers(',
      );
      expect(doc, contains('C40:'));
      expect(doc, contains('`duplicate_member` on every file system'));
      expect(doc, contains('names that differ only by Unicode normalization'));
    });

    test('README Step 1 names the Git 2.40 floor of a resuming undo', () {
      final text = File('../README.md').readAsStringSync();
      final step1 = text.substring(
        text.indexOf('Step 1 - Check prerequisites'),
      );
      final line = step1.substring(0, step1.indexOf('Step 2 - Choose targets'));
      expect(
        line.replaceAll(RegExp(r'\s+'), ' '),
        contains(
          'a Git undo that resumes the archive branch needs Git 2.40 or later',
        ),
      );
    });

    test('undoArchivePlan carries C32 and C51', () {
      final doc = docAbove(
        'lib/src/finish/undo_plan.dart',
        'Future<Map<String, Object?>> undoArchivePlan(',
      );
      expect(doc, contains('C32:'));
      expect(doc, contains('never deleted without a copy'));
      expect(doc, contains('before the undo\'s first index change'));
      expect(doc, contains('C51:'));
      expect(doc, contains('outside this change\'s threat model'));
      expect(doc, contains('Rejected: diffing the whole branch switch'));
    });

    test('_Planner carries C34', () {
      final doc = docAbove('lib/src/finish/undo_plan.dart', 'class _Planner');
      expect(doc, contains('C34:'));
      expect(doc, contains('never asks Git for a filtered read'));
      expect(doc, contains('a user\'s own filter driver is their code'));
      expect(
        doc,
        contains('Rejected: refusing every repository with a filter driver'),
      );
    });

    test('_detectMain carries C43', () {
      final doc = docAbove(
        'lib/src/pr/settings_commands.dart',
        'Future<String> _detectMain(',
      );
      expect(doc, contains('C43:'));
      expect(doc, contains('keeps today\'s rule'));
      expect(doc, contains('no emitted guard catches it'));
      expect(doc, contains('Rejected: a strict lookup on the planner\'s path'));
    });

    test('checkIndex carries the state read and lazy fetch parts of C19', () {
      final doc = docOfLocal(
        'lib/src/finish/undo_step.dart',
        'Future<void> checkIndex(',
      );
      expect(doc, contains('first state read'));
      expect(doc, contains("keeps today's error name, `git_error`"));
      expect(doc, contains('GIT_NO_LAZY_FETCH'));
      expect(doc, contains('the only barrier'));
    });

    test('runUndoStep carries the gitlink and batching parts of C46', () {
      final doc = docAbove(
        'lib/src/finish/undo_step.dart',
        'Future<int> runUndoStep(',
      );
      expect(doc, contains('index records as a gitlink'));
      expect(doc, contains('same inventory feeds'));
      expect(doc, contains('lossless foreign-assignment check'));
      expect(doc, contains('every batch of a phase passes before'));
    });
  });

  group('the plan (task 3.3)', () {
    const ad = 'openspec/changes/archive/$_date-add-x';
    const specA = 'openspec/specs/a/spec.md';
    const specB = 'openspec/specs/b/spec.md';

    String topOf(String repo) => git(repo, ['rev-parse', '--show-toplevel']);
    String backupOf(String repo) =>
        '${git(repo, ['rev-parse', '--absolute-git-dir'])}/specwright-undo/$_date-add-x';
    String sq(String s) => shellQuote(s);
    UndoRequest rq(String repo, {String? branch, String? code}) => request(
      repo,
      change: 'add-x',
      archived: '$_date-add-x',
      branch: branch,
      code: code,
    );

    /// A repo on `feat/x` with change `add-x` (delta on a) committed.
    String branchRepo({
      String verdict = 'DEFERRED',
      String branch = 'feat/x',
      String name = 'work',
      Map<String, String> deltas = const {'a': 'New thing'},
      String tasks = '# Tasks\n\n- [ ] 1.1 do it\n',
    }) {
      final repo = makeRepo(name);
      git(repo, ['checkout', '-q', '-b', branch]);
      makeChange(repo, 'add-x', verdict: verdict, deltas: deltas, tasks: tasks);
      return repo;
    }

    Future<Map<String, Object?>> ok(
      String repo, {
      String? branch,
      String? type,
      String? code,
      FinishContext? ctx,
      String change = 'add-x',
      String? archived,
    }) async {
      final r = await plan(
        request(
          repo,
          change: change,
          archived: archived ?? '$_date-$change',
          branch: branch,
          type: type,
          code: code,
        ),
        ctx,
      );
      expect(r.code, 0, reason: '${r.doc}');
      expect(r.doc['ok'], true);
      return r.doc;
    }

    Future<_Out> stop(String repo, {String? branch, String change = 'add-x'}) =>
        plan(
          request(
            repo,
            change: change,
            archived: '$_date-$change',
            branch: branch,
          ),
        );

    test(
      'a committed single archive, exactly as finish.sh prints it',
      () async {
        final repo = branchRepo();
        final a = archive(repo, ['add-x'], commitIt: true)!;
        final top = topOf(repo);
        final backup = backupOf(repo);
        final doc = await ok(repo);
        expect(doc.keys.toList(), [
          'ok',
          'mode',
          'archive_commit',
          'branch',
          'head',
          'members',
          'main_specs',
          'amended',
          'carried_edits',
          'backup_dir',
          'steps',
          'after_rerun_steps',
          'warnings',
        ]);
        expect(doc['mode'], 'committed');
        expect(doc['archive_commit'], a);
        expect(doc['branch'], 'feat/x');
        expect(doc['head'], a);
        expect(doc['members'], [
          {
            'name': 'add-x',
            'archived_name': '$_date-add-x',
            'deferred': true,
            'waiting_on_user': <String>[],
          },
        ]);
        expect(doc['main_specs'], {
          'modified': [specA],
          'created': <String>[],
        });
        expect(doc['amended'], <String>[]);
        expect(doc['carried_edits'], <String>[]);
        expect(doc['backup_dir'], backup);
        expect(doc['after_rerun_steps'], <Object?>[]);
        expect(doc.containsKey('script'), isFalse);
        expect(doc.containsKey('after_rerun'), isFalse);
        for (final s in doc['steps']! as List) {
          expect((s as Map)['cwd'], top);
        }
        List<String> u(List<String> rest) => undoStep(top, rest);
        final parent = git(repo, ['rev-parse', '$a^']);
        expect(
          argvsOf(doc['steps']),
          containsAllInOrder([
            preflightStep(repo),
            u(['check', 'branch', 'feat/x', '--backend', 'git']),
            u(['check', 'tip', 'HEAD', a]),
            u(['check', 'index']),
            u(['check', 'absent', backup]),
            u([
              'mkdir',
              '$backup/amended/openspec/specs/a',
              '$backup/base/openspec/specs/a',
            ]),
            u(['write-blob', a, specA, '$backup/base/$specA']),
            u(['copy', specA, '$backup/amended/$specA']),
            [..._g, 'rm', '-r', '-q', '--cached', '--', ad],
            [..._g, 'read-tree', '--prefix=openspec/changes/add-x/', '$a:$ad'],
            [..._g, 'restore', '--source=$parent', '--staged', '--', specA],
            [..._g, 'commit', '-q', '-m', 'feat(add-x): undo archive of add-x'],
            u(['move', ad, 'openspec/changes/add-x']),
            [..._g, 'restore', '--source=$parent', '--worktree', '--', specA],
          ]),
        );
        expect(doc['warnings'], [
          'Do not edit files after this plan is printed, and do not start a '
              'merge, cherry-pick, revert or rebase while the steps run.',
          'The index must not be changed by other commands or hooks while the '
              'steps run.',
          'If a step fails after the steps began changing the index and before '
              'they commit, the index entries of $ad openspec/changes/add-x '
              "$specA may be partly changed, and a resume plan's checkout may "
              'already have happened. Unstage those paths yourself and move or '
              'delete the backup directory $backup, then plan again; the '
              'working tree is untouched until the commit.',
          'Base and amended copies of the synced main specs are saved in '
              '$backup; no step reads or deletes them.',
        ]);
      },
      skip: skip,
    );

    test('an unexpected planner failure is internal_error', () async {
      final repo = branchRepo();
      archive(repo, ['add-x'], commitIt: true);
      final out = <int>[];
      final code = await runFinishCommand(
        [
          '--dir',
          repo,
          'undo-archive-plan',
          '--change',
          'add-x',
          '--archived-name',
          '$_date-add-x',
          '--prefix',
          'openspec',
          '--main',
          'main',
        ],
        writeOut: out.addAll,
        planner: (request, ctx) => undoArchivePlan(
          request,
          FinishContext(
            stateReader: (top, code, branch) async => throw StateError('boom'),
          ),
        ),
      );
      expect(code, 1);
      final doc = jsonDecode(utf8.decode(out)) as Map<String, Object?>;
      expect(doc['ok'], false);
      expect(doc['error'], 'internal_error');
      expect(doc.containsKey('steps'), isFalse);
    }, skip: skip);

    test('non-ASCII digits are not a user-task id', () async {
      final repo = branchRepo(
        verdict: 'APPROVE',
        tasks: '# Tasks\n\n- [ ] \u{661}.\u{661} [user] Check it\n',
      );
      archive(repo, ['add-x']);
      final doc = await ok(repo);
      expect(doc['mode'], 'uncommitted');
      final member = (doc['members']! as List).single as Map;
      expect(member['waiting_on_user'], <String>[]);
      expect(member['deferred'], false);
      // no waiting member: the rerun steps archive it again
      expect(
        argvsOf(doc['after_rerun_steps']),
        containsAllInOrder([
          ['openspec', 'archive', 'add-x', '--yes'],
        ]),
      );
      expect(doc.containsKey('script'), isFalse);
    }, skip: skip);

    test('non-ASCII digits are not a date prefix', () async {
      final repo = makeRepo();
      git(repo, ['checkout', '-q', '-b', 'feat/x']);
      makeChange(repo, 'add-x', deltas: {'a': 'A thing'});
      const full =
          '\u{ff12}\u{ff10}\u{ff12}\u{ff16}-\u{ff11}\u{ff11}-\u{ff10}\u{ff17}-add-z';
      makeChange(repo, full);
      archive(repo, ['add-x']);
      Directory('$repo/openspec/changes/$full')
          .renameSync('$repo/openspec/changes/archive/$full');
      final top = topOf(repo);
      final doc = await ok(repo);
      final members = (doc['members']! as List).cast<Map<String, Object?>>();
      expect(members.map((m) => m['name']), ['add-x', full]);
      // nothing is stripped: the folder goes back to the name it has
      expect(
        argvsOf(doc['steps']),
        hasStep(
          undoStep(top, [
            'move',
            'openspec/changes/archive/$full',
            'openspec/changes/$full',
          ]),
        ),
      );
      expect(doc.containsKey('script'), isFalse);
    }, skip: skip);

    test('an ASCII user task waits and keeps the rerun away', () async {
      final repo = branchRepo(
        verdict: 'APPROVE',
        tasks: '# Tasks\n\n- [ ] 1.1 [user] Check it\n- [x] 1.2 [user] Done\n',
      );
      archive(repo, ['add-x']);
      final doc = await ok(repo);
      final member = (doc['members']! as List).single as Map;
      expect(member['waiting_on_user'], ['1.1']);
      expect(doc['after_rerun_steps'], <Object?>[]);
    }, skip: skip);

    test('an uncommitted bulk archive with nested specs and carried edits', () async {
      final repo = makeRepo();
      git(repo, ['checkout', '-q', '-b', 'feat/x']);
      makeChange(repo, 'add-x', deltas: {'a': 'A thing', 'area/id': 'Deep'});
      makeChange(repo, 'add-y', verdict: 'APPROVE', deltas: {'b': 'B thing'});
      archive(repo, ['add-x', 'add-y'], marker: true);
      put(repo, '$ad/design.md', '# Design\n\nEdited after archive.\n');
      final top = topOf(repo);
      final backup = backupOf(repo);
      final head = git(repo, ['rev-parse', 'HEAD']);
      final doc = await ok(repo);
      expect(doc['mode'], 'uncommitted');
      expect(doc['archive_commit'], isNull);
      expect(doc['head'], head);
      expect(doc['members'], [
        {
          'name': 'add-x',
          'archived_name': '$_date-add-x',
          'deferred': true,
          'waiting_on_user': <String>[],
        },
        {
          'name': 'add-y',
          'archived_name': '$_date-add-y',
          'deferred': false,
          'waiting_on_user': <String>[],
        },
      ]);
      expect(doc['main_specs'], {
        'modified': [specA, specB],
        'created': ['openspec/specs/area/id/spec.md'],
      });
      // the edited design.md and the new marker files (not at HEAD)
      expect((doc['carried_edits']! as List).cast<String>().toSet(), {
        '$ad/design.md',
        '$ad/specwright-change.yaml',
        'openspec/changes/archive/$_date-add-y/specwright-change.yaml',
      });
      final steps = argvsOf(doc['steps']);
      List<String> u(List<String> rest) => undoStep(top, rest);
      final at = steps.indexWhere(
        (s) => s.length > 5 && s[5] == 'move' && s[6] == ad,
      );
      expect(at, greaterThan(0));
      expect(
        steps.sublist(at),
        containsAllInOrder([
          u(['move', ad, 'openspec/changes/add-x']),
          u(['remove', 'openspec/changes/add-x/specwright-change.yaml']),
          u([
            'move',
            'openspec/changes/archive/$_date-add-y',
            'openspec/changes/add-y',
          ]),
          u(['remove', 'openspec/changes/add-y/specwright-change.yaml']),
          [
            ..._g,
            'restore',
            '--source=$head',
            '--worktree',
            '--',
            specA,
            specB,
          ],
          u(['remove', 'openspec/specs/area/id/spec.md']),
          u(['rmdir-if-empty', 'openspec/specs/area/id']),
        ]),
      );
      expect(steps.expand((s) => s), isNot(contains('commit')));
      expect(steps.expand((s) => s), isNot(contains('write-blob')));
      expect(
        argvsOf(doc['after_rerun_steps']),
        containsAllInOrder([
          ['openspec', 'archive', 'add-y', '--yes'],
        ]),
      );
      expect(
        doc['warnings'],
        containsAllInOrder([
          'The synced main specs are copied to $backup/amended/ before they '
              'are restored or removed; a sync and your own edit in one file '
              'cannot be told apart, so that copy is the only one of your edit.',
          'This archive holds add-x, add-y. The whole archive is undone, never '
              "only the deferred change's files; run the archive again without "
              'the deferred change.',
          'Do not edit files after this plan is printed, and do not start a '
              'merge, cherry-pick, revert or rebase while the steps run.',
          'The index must not be changed by other commands or hooks while the '
              'steps run.',
          'Run after_rerun_steps after steps: they archive add-y again.',
        ]),
      );
    }, skip: skip);

    test('uncommitted members are ordered by code point', () async {
      final repo = makeRepo();
      git(repo, ['checkout', '-q', '-b', 'feat/x']);
      makeChange(repo, 'add-x', deltas: {'a': 'A thing'});
      final hi = 'z\u{10000}';
      final lo = 'z\u{e000}';
      makeChange(repo, hi, deltas: {'b': 'B thing'});
      makeChange(repo, lo);
      archive(repo, ['add-x', hi, lo]);
      final doc = await ok(repo);
      final names = [
        for (final m in doc['members']! as List) (m as Map)['name'],
      ];
      expect(names, ['add-x', lo, hi]);
    }, skip: skip);

    test('a change named with a date is archived under that name', () async {
      final repo = makeRepo();
      git(repo, ['checkout', '-q', '-b', 'feat/x']);
      makeChange(repo, 'add-x', deltas: {'a': 'A thing'});
      makeChange(repo, '2026-09-01-dated');
      archive(repo, ['add-x']);
      Directory('$repo/openspec/changes/2026-09-01-dated')
          .renameSync('$repo/openspec/changes/archive/2026-09-01-dated');
      final doc = await ok(repo);
      final members = (doc['members']! as List).cast<Map<String, Object?>>();
      expect(members.map((m) => m['name']), ['add-x', '2026-09-01-dated']);
      expect(members.map((m) => m['archived_name']), [
        '$_date-add-x',
        '2026-09-01-dated',
      ]);
    }, skip: skip);

    test(
      'a committed bulk archive: amendments are merged for the rerun',
      () async {
        final repo = makeRepo();
        git(repo, ['checkout', '-q', '-b', 'feat/x']);
        makeChange(repo, 'add-x', deltas: {'a': 'A thing'});
        makeChange(repo, 'add-y', verdict: 'APPROVE', deltas: {'b': 'B thing'});
        final a = archive(repo, ['add-x', 'add-y'], commitIt: true)!;
        File('$repo/$specA')
            .writeAsStringSync('${read(repo, specA)}\nmine a\n');
        File('$repo/$specB')
            .writeAsStringSync('${read(repo, specB)}\nmine b\n');
        final top = topOf(repo);
        final backup = backupOf(repo);
        final doc = await ok(repo);
        expect(doc['amended'], [specA, specB]);
        expect(doc['archive_commit'], a);
        expect(
          argvsOf(doc['after_rerun_steps']),
          containsAllInOrder([
            ['openspec', 'archive', 'add-y', '--yes'],
            undoStep(top, [
              'merge-back',
              specB,
              '$backup/base/$specB',
              '$backup/amended/$specB',
            ]),
          ]),
        );
        final warnings = (doc['warnings']! as List).cast<String>();
        expect(warnings.sublist(warnings.length - 2), [
          'Run after_rerun_steps after steps: they archive add-y again and merges '
              'the saved amendments into $specB. On a conflict it stops with '
              'markers in the file; both copies stay in $backup.',
          'Amendments to $specA were made on top of the deferred change\'s '
              'synced content, so they are saved in $backup/amended/ and never '
              'merged automatically; review them by hand.',
        ]);
      },
      skip: skip,
    );

    test('a spec deleted after the archive is left deleted', () async {
      final repo = makeRepo();
      git(repo, ['checkout', '-q', '-b', 'feat/x']);
      makeChange(repo, 'add-x', deltas: {'a': 'A thing', 'c': 'C thing'});
      makeChange(repo, 'add-y', verdict: 'APPROVE', deltas: {'c': 'C more'});
      archive(repo, ['add-x', 'add-y'], commitIt: true);
      File('$repo/openspec/specs/c/spec.md').deleteSync();
      commitAll(repo, 'drop c');
      final doc = await ok(repo);
      expect(doc['main_specs'], {
        'modified': [specA],
        'created': <String>[],
      });
      final top = topOf(repo);
      expect(
        argvsOf(doc['after_rerun_steps']),
        containsAllInOrder([
          undoStep(top, [
            'check',
            'absent',
            'openspec/specs/c/spec.md',
            '--message',
            'openspec/specs/c/spec.md exists; after_rerun_steps would '
                'delete it. Move it away, then run again.',
          ]),
          ['openspec', 'archive', 'add-y', '--yes'],
          undoStep(top, ['remove', 'openspec/specs/c/spec.md']),
        ]),
      );
      final warnings = (doc['warnings']! as List).cast<String>();
      expect(
        warnings,
        contains(
          'openspec/specs/c/spec.md was deleted on feat/x after the archive; '
          'the undo leaves it deleted; after_rerun_steps archive add-y again, and a later '
          'step deletes it again.',
        ),
      );
    }, skip: skip);

    test('carried edits of a committed archive are the dirty paths', () async {
      final repo = branchRepo();
      archive(repo, ['add-x'], commitIt: true);
      put(repo, '$ad/design.md', 'edited\n');
      put(repo, '$ad/notes.md', 'new\n');
      final doc = await ok(repo);
      expect((doc['carried_edits']! as List).cast<String>().toSet(), {
        '$ad/design.md',
        '$ad/notes.md',
      });
    }, skip: skip);

    test('carried edits keep their byte order in steps', () async {
      final repo = makeRepo();
      git(repo, ['checkout', '-q', '-b', 'feat/x']);
      for (final f in ['b.md', 'a.md', 'a/z.md', 'sub/c.md']) {
        put(repo, 'openspec/changes/add-x/$f', 'original $f\n');
      }
      makeChange(repo, 'add-x');
      archive(repo, ['add-x']);
      for (final f in ['b.md', 'a.md', 'a/z.md', 'sub/c.md']) {
        put(repo, '$ad/$f', 'edited $f\n');
      }
      final doc = await ok(repo);
      expect(doc['mode'], 'uncommitted');
      expect((doc['carried_edits']! as List).cast<String>(), [
        '$ad/a.md',
        '$ad/a/z.md',
        '$ad/b.md',
        '$ad/sub/c.md',
      ]);
      expect(doc['steps'], isA<List<Object?>>());
      expect(doc.containsKey('script'), isFalse);
    }, skip: skip);

    // A regression guard: it passes on the `find` walk and on the native one.
    test(
      'linked files are planned as regular files in steps',
      () async {
        final repo = branchRepo(deltas: {'foo': 'Foo thing'});
        put(repo, 'openspec/changes/add-x/notes.md', 'original notes\n');
        commitAll(repo, 'docs(add-x): notes');
        archive(repo, ['add-x']);
        final outside = Directory('${tmp.path}/outside')..createSync();
        File('${outside.path}/spec.md')
            .writeAsStringSync(deltaText('Foo thing'));
        File('${outside.path}/notes.md').writeAsStringSync('edited notes\n');
        File('${outside.path}/inside.md').writeAsStringSync('inside\n');
        File('$repo/$ad/specs/foo/spec.md').deleteSync();
        Link('$repo/$ad/specs/foo/spec.md')
            .createSync('${outside.path}/spec.md');
        File('$repo/$ad/notes.md').deleteSync();
        Link('$repo/$ad/notes.md').createSync('${outside.path}/notes.md');
        Link('$repo/$ad/linkeddir').createSync(outside.path);
        final doc = await ok(repo);
        expect((doc['main_specs']! as Map)['created'], [
          'openspec/specs/foo/spec.md',
        ]);
        expect((doc['carried_edits']! as List).cast<String>(), [
          '$ad/notes.md',
        ]);
        // the linked spec.md is restored as a regular file's capability, and
        // the linked directory is not entered
        final steps = argvsOf(doc['steps']);
        expect(
          steps,
          hasStep(
            undoStep(topOf(repo), ['remove', 'openspec/specs/foo/spec.md']),
          ),
        );
        expect(
          steps.expand((s) => s).any((x) => x.contains('linkeddir')),
          isFalse,
        );
        expect(doc.containsKey('script'), isFalse);
      },
      skip: bash == null
          ? 'no bash installed'
          : Platform.isWindows
          ? 'links need developer mode on Windows; POSIX only'
          : false,
    );

    test(
      'a non-UTF-8 name in the archive walk is not_utf8',
      () async {
        final repo = branchRepo();
        archive(repo, ['add-x']);
        final name = Uint8List.fromList([
          ..._b('$repo/$ad/a'),
          0xff,
          ..._b('.txt'),
        ]);
        File.fromRawPath(name).writeAsStringSync('x');
        final r = await stop(repo);
        expect(r.code, 1, reason: '${r.doc}');
        expect(r.doc['error'], 'not_utf8');
        expect(r.doc['message'], contains(r'a\xFF.txt'));
        expect(r.doc.containsKey('script'), isFalse);
      },
      skip: bash == null
          ? 'no bash installed'
          : Platform.isLinux
          ? false
          : 'Linux only: macOS refuses names that are not valid UTF-8, and '
                'Windows names are UTF-16',
    );

    group('destinations, markers and line sizing (group 12)', () {
      /// Units a printed step takes on a Windows command line, with the
      /// terminating NUL.
      int units(List<String> argv) => commandLineUnits(argv) + 1;

      bool isGit(List<String> s, String sub) =>
          s.isNotEmpty && s[0] == 'git' && s.contains(sub);

      bool isUndo(List<String> s, String kind, [String? name]) =>
          s.length > 6 &&
          s[3] == 'finish' &&
          s[4] == 'undo-step' &&
          s[5] == kind &&
          (name == null || s[6] == name);

      /// `add-x` deferred (delta on a) and `add-y` eligible (delta on [cap]),
      /// both archived and committed on `feat/x`.
      String bulkRepo(String cap) {
        final repo = branchRepo();
        makeChange(repo, 'add-y', verdict: 'APPROVE', deltas: {cap: 'Y thing'});
        archive(repo, ['add-x', 'add-y'], commitIt: true);
        return repo;
      }

      test('a rerun plan warns that it writes specs in place', () async {
        final doc = await ok(bulkRepo('b'));
        expect(doc['after_rerun_steps'], isNotEmpty);
        final warnings = (doc['warnings']! as List).cast<String>();
        expect(
          warnings.where(
            (w) => w.contains('in place') && w.contains('hard link'),
          ),
          hasLength(1),
          reason: '$warnings',
        );
        final single = branchRepo(name: 'single');
        archive(single, ['add-x'], commitIt: true);
        final plain = await ok(single);
        expect(plain['after_rerun_steps'], isEmpty);
        expect(
          (plain['warnings']! as List).cast<String>().where(
            (w) => w.contains('in place'),
          ),
          isEmpty,
        );
      }, skip: skip);

      test('the rerun starts with a destination check', () async {
        final repo = bulkRepo('b');
        final after = argvsOf((await ok(repo))['after_rerun_steps']);
        expect(
          isUndo(after.first, 'check', 'destinations'),
          isTrue,
          reason: '${after.first}',
        );
        expect(
          indexOfStep(after, ['openspec', 'archive', 'add-y', '--yes']),
          greaterThan(0),
        );
      }, skip: skip);

      test('the rerun archive runs from the selected OpenSpec root', () async {
        // the planning root is `planning/openspec`: its parent, `planning/`,
        // is the root `openspec archive` must run in, and a same-named change
        // active under the top-level `openspec/` must be left alone
        final repo = makeRepo();
        const nested = 'planning/openspec';
        Directory('$repo/$nested').createSync(recursive: true);
        git(repo, ['mv', 'openspec/specs', '$nested/specs']);
        commitAll(repo, 'chore: nest the planning root');
        git(repo, ['checkout', '-q', '-b', 'feat/x']);
        makeChange(repo, 'add-x', deltas: {'a': 'X thing'});
        makeChange(repo, 'add-y', verdict: 'APPROVE', deltas: {'b': 'Y thing'});
        git(repo, ['mv', 'openspec/changes', '$nested/changes']);
        commitAll(repo, 'chore: nest the changes');
        for (final n in ['add-x', 'add-y']) {
          Directory('$repo/$nested/changes/archive').createSync();
          Directory('$repo/$nested/changes/$n')
              .renameSync('$repo/$nested/changes/archive/$_date-$n');
        }
        final b = '$nested/specs/b/spec.md';
        put(repo, b, '${read(repo, b)}\nY thing synced.\n');
        put(repo, 'openspec/changes/add-y/.openspec.yaml', 'schema: x\n');
        commitAll(repo, 'chore(add-x, add-y): archive change');
        final r = await plan(
          request(
            repo,
            change: 'add-x',
            archived: '$_date-add-x',
            prefix: nested,
          ),
        );
        expect(r.code, 0, reason: '${r.doc}');
        final top = topOf(repo);
        final after = (r.doc['after_rerun_steps']! as List)
            .cast<Map<String, Object?>>();
        final archives = [
          for (final s in after)
            if ((s['argv']! as List).first == 'openspec') s,
        ];
        expect(archives, isNotEmpty);
        for (final s in archives) {
          expect(s['cwd'], '$top/planning', reason: '$s');
        }
        final others = [
          for (final s
              in (r.doc['steps']! as List).cast<Map<String, Object?>>())
            s['cwd'],
          for (final s in after)
            if ((s['argv']! as List).first != 'openspec') s['cwd'],
        ];
        expect(others.toSet(), {top});
      }, skip: skip);

      test(
        'a marker the undo removes is copied into the backup first',
        () async {
          final repo = branchRepo();
          archive(repo, ['add-x'], commitIt: true, marker: true);
          final doc = await ok(repo);
          final steps = argvsOf(doc['steps']);
          final top = topOf(repo);
          final backup = backupOf(repo);
          final copy = indexOfStep(
            steps,
            undoStep(top, [
              'copy',
              '--if-present',
              '$ad/specwright-change.yaml',
              '$backup/markers/add-x/specwright-change.yaml',
            ]),
          );
          expect(copy, greaterThan(0), reason: '$steps');
          final mkdir = steps.indexWhere(
            (s) => isUndo(s, 'mkdir') && s.contains('$backup/markers/add-x'),
          );
          expect(mkdir, greaterThanOrEqualTo(0));
          expect(mkdir, lessThan(copy));
          final firstIndexChange = steps.indexWhere(
            (s) => isGit(s, '--cached'),
          );
          expect(copy, lessThan(firstIndexChange));
          expect(
            (doc['warnings']! as List).cast<String>().where(
              (w) => w.contains('$backup/markers'),
            ),
            isNotEmpty,
          );
        },
        skip: skip,
      );

      test('a resume checks destinations, tracked files and inputs after the '
          'checkout', () async {
        final repo = branchRepo();
        archive(repo, ['add-x'], commitIt: true);
        git(repo, ['checkout', '-q', 'main']);
        final top = topOf(repo);
        final steps = argvsOf((await ok(repo, branch: 'feat/x'))['steps']);
        int at(bool Function(List<String>) test, String what) {
          final i = steps.indexWhere(test);
          expect(i, greaterThanOrEqualTo(0), reason: '$what in $steps');
          return i;
        }

        final checkout = at((s) => isGit(s, 'checkout'), 'the checkout');
        final destinations = at(
          (s) => isUndo(s, 'check', 'destinations'),
          'check destinations',
        );
        final absent = indexOfStep(
          steps,
          undoStep(top, ['check', 'absent', backupOf(repo)]),
        );
        final tracked = at(
          (s) => isUndo(s, 'check', 'tracked') && s.contains(ad),
          'check tracked',
        );
        final inputs = at(
          (s) => isUndo(s, 'check', 'inputs') && s.contains(ad),
          'check inputs',
        );
        final backupStep = at((s) => isUndo(s, 'mkdir'), 'the backup');
        final firstWrite = at((s) => isGit(s, '--cached'), 'an index change');
        expect(absent, greaterThan(-1), reason: '$steps');
        for (final i in [destinations, absent, tracked, inputs]) {
          expect(i, greaterThan(checkout));
          expect(i, lessThan(backupStep));
          expect(i, lessThan(firstWrite));
        }
      }, skip: skip);

      test('each restore destination is checked absent after the checkout and '
          'before the backup', () async {
        final repo = branchRepo();
        archive(repo, ['add-x'], commitIt: true);
        final top = topOf(repo);
        final here = argvsOf((await ok(repo))['steps']);
        final absent = undoStep(top, [
          'check',
          'absent',
          'openspec/changes/add-x',
        ]);
        expect(indexOfStep(here, absent), greaterThan(-1), reason: '$here');
        expect(
          indexOfStep(here, absent),
          lessThan(here.indexWhere((s) => isUndo(s, 'mkdir'))),
        );
        git(repo, ['checkout', '-q', 'main']);
        final steps = argvsOf((await ok(repo, branch: 'feat/x'))['steps']);
        final i = indexOfStep(steps, absent);
        expect(i, greaterThan(steps.indexWhere((s) => isGit(s, 'checkout'))));
        expect(i, lessThan(steps.indexWhere((s) => isUndo(s, 'mkdir'))));
        expect(i, lessThan(steps.indexWhere((s) => isGit(s, '--cached'))));
      }, skip: skip);

      test('a linked archive directory names the member path', () async {
        final repo = branchRepo(deltas: const {});
        archive(repo, ['add-x'], commitIt: true);
        final outside = Directory('${tmp.path}/outside')..createSync();
        Directory('$repo/openspec/changes/archive/$_date-add-x')
            .renameSync('${outside.path}/$_date-add-x');
        Directory('$repo/openspec/changes/archive').deleteSync();
        try {
          Link('$repo/openspec/changes/archive').createSync(outside.path);
        } on FileSystemException {
          markTestSkipped(
            'platform: this account cannot create symbolic links',
          );
          return;
        }
        final r = await stop(repo);
        expect(r.code, 1, reason: '${r.doc}');
        expect(r.doc['error'], 'unsupported_entry', reason: '${r.doc}');
        expect(
          r.doc['message'],
          contains('openspec/changes/archive/$_date-add-x'),
        );
        expect(r.doc.containsKey('steps'), isFalse);
      }, skip: skip);

      test('a bulk plan reads its specs in batches, not one Git process per '
          'spec', () async {
        final repo = branchRepo(
          deltas: {for (var i = 0; i < 120; i++) 'cap-$i': 'Thing $i'},
        );
        archive(repo, ['add-x'], commitIt: true);
        final listings = <List<String>>[];
        final doc = await ok(
          repo,
          ctx: FinishContext(
            runner: (cwd, command, env) {
              if (command.contains('ls-tree')) listings.add(command);
              return runTool(cwd, command, environment: env);
            },
          ),
        );
        expect((doc['main_specs']! as Map)['created'], hasLength(120));
        // before batching each spec cost several listings of its own
        expect(listings.length, lessThan(20), reason: '${listings.length}');
      }, skip: skip);

      for (final caps in [
        {'a': 'New thing'},
        {'a': 'New thing', 'c': 'C thing'},
      ]) {
        test('a CRLF checkout is no amendment when ${caps.length} spec(s) are '
            'read in one batch', () async {
          final repo = branchRepo(deltas: caps);
          archive(repo, ['add-x'], commitIt: true);
          git(repo, ['config', 'core.autocrlf', 'true']);
          for (final f in git(repo, ['ls-files']).split('\n')) {
            File('$repo/$f').deleteSync();
          }
          git(repo, ['checkout', '--', '.']);
          expect(
            File('$repo/$specA').readAsBytesSync().contains(0x0d),
            isTrue,
            reason: 'the checkout holds CRLF',
          );
          final doc = await ok(repo);
          expect(doc['amended'], isEmpty);
          expect(doc['carried_edits'], isEmpty);
        }, skip: skip);
      }

      test('a gitlink above a rerun spec is unsupported_entry', () async {
        final repo = bulkRepo('foo');
        final commit = git(repo, ['rev-parse', 'HEAD']);
        git(repo, ['rm', '-r', '-q', '--cached', 'openspec/specs/foo']);
        Directory('$repo/openspec/specs/foo').deleteSync(recursive: true);
        git(repo, [
          'update-index',
          '--add',
          '--cacheinfo',
          '160000,$commit,openspec/specs/foo',
        ]);
        Directory('$repo/openspec/specs/foo').createSync();
        git(repo, ['commit', '-q', '-m', 'chore: nest a repository']);
        // the fixture holds a gitlink where the rerun would write a spec
        expect(
          git(repo, ['ls-tree', 'HEAD', '--', 'openspec/specs/foo']),
          startsWith('160000 commit'),
        );
        final head = git(repo, ['rev-parse', 'HEAD']);
        final r = await stop(repo);
        expect(r.code, 1, reason: '${r.doc}');
        expect(r.doc['error'], 'unsupported_entry', reason: '${r.doc}');
        expect(r.doc['message'], contains('openspec/specs/foo'));
        expect(r.doc.containsKey('steps'), isFalse);
        expect(git(repo, ['rev-parse', 'HEAD']), head);
      }, skip: skip);

      test('a rerun spec blocked by an existing directory is '
          'unsupported_entry', () async {
        final repo = bulkRepo('c');
        File('$repo/openspec/specs/c/spec.md').deleteSync();
        put(repo, 'openspec/specs/c/spec.md/b/spec.md', 'mine\n');
        commitAll(repo, 'docs: a directory where the spec was');
        final head = git(repo, ['rev-parse', 'HEAD']);
        final r = await stop(repo);
        expect(r.code, 1, reason: '${r.doc}');
        expect(r.doc['error'], 'unsupported_entry', reason: '${r.doc}');
        expect(r.doc['message'], contains('openspec/specs/c/spec.md'));
        expect(r.doc.containsKey('steps'), isFalse);
        expect(git(repo, ['rev-parse', 'HEAD']), head);
        expect(git(repo, ['status', '--porcelain']), isEmpty);
      }, skip: skip);

      test('two absent rerun specs, one under the other, are '
          'unsupported_entry', () async {
        final repo = branchRepo();
        makeChange(repo, 'add-y', verdict: 'APPROVE', deltas: {'q': 'Y thing'});
        makeChange(
          repo,
          'add-z',
          verdict: 'APPROVE',
          deltas: {'q/spec.md/b': 'Z thing'},
        );
        // moved without syncing, so main holds neither spec
        Directory('$repo/openspec/changes/archive').createSync(recursive: true);
        for (final n in ['add-x', 'add-y', 'add-z']) {
          Directory('$repo/openspec/changes/$n')
              .renameSync('$repo/openspec/changes/archive/$_date-$n');
        }
        commitAll(repo, 'chore(add-x, add-y, add-z): archive change');
        final head = git(repo, ['rev-parse', 'HEAD']);
        final r = await stop(repo);
        expect(r.code, 1, reason: '${r.doc}');
        expect(r.doc['error'], 'unsupported_entry', reason: '${r.doc}');
        expect(
          r.doc['message'],
          contains('openspec/specs/q/spec.md and openspec/specs/q/spec.md/b/'),
        );
        expect(r.doc.containsKey('steps'), isFalse);
        expect(git(repo, ['rev-parse', 'HEAD']), head);
      }, skip: skip);

      test(
        'an archive member holding an entry named like .git is refused',
        () async {
          final repo = branchRepo();
          archive(repo, ['add-x'], commitIt: true);
          put(repo, '$ad/scratch/.GIT', 'gitdir: elsewhere\n');
          final r = await stop(repo);
          expect(r.code, 1, reason: '${r.doc}');
          expect(r.doc['error'], 'unsupported_entry', reason: '${r.doc}');
          expect(r.doc['message'], contains('scratch/.GIT'));
          expect(r.doc.containsKey('steps'), isFalse);
        },
        skip: skip,
      );

      test(
        'a Git plan splits a per-path step into runs under the line limit',
        () async {
          final caps = [for (var i = 0; i < 40; i++) 'capability-number-$i'];
          final repo = branchRepo(
            deltas: {for (final c in caps) c: 'Thing $c'},
          );
          archive(repo, ['add-x'], commitIt: true);
          final plain = argvsOf(
            (await ok(repo, ctx: context(windows: true)))['steps'],
          );
          bool perPath(List<String> s) =>
              s.where((a) => a.contains('/specs/capability-number-')).length >
              1;
          final fixed = plain
              .where((s) => !perPath(s))
              .map(units)
              .reduce((a, b) => a > b ? a : b);
          final limit = fixed + 100;
          expect(
            plain.where((s) => units(s) > limit),
            isNotEmpty,
            reason: 'the fixture needs a step past the limit',
          );
          final doc = await ok(
            repo,
            ctx: FinishContext(windows: true, lineLimit: limit),
          );
          final steps = argvsOf(doc['steps']);
          for (final s in steps) {
            expect(units(s), lessThanOrEqualTo(limit), reason: '$s');
          }
          final made = [
            for (final s in steps)
              if (isUndo(s, 'mkdir')) ...s.sublist(6),
          ];
          for (final c in caps) {
            expect(
              made.where((d) => d.endsWith('/amended/openspec/specs/$c')),
              hasLength(1),
              reason: c,
            );
          }
          expect(steps.where((s) => isUndo(s, 'mkdir')).length, greaterThan(1));
        },
        skip: skip,
      );

      test(
        'a step that cannot be split stops the plan with plan_too_large',
        () async {
          final repo = branchRepo();
          archive(repo, ['add-x'], commitIt: true);
          final r = await plan(
            rq(repo),
            FinishContext(windows: true, lineLimit: 150),
          );
          expect(r.code, 1, reason: '${r.doc}');
          expect(r.doc['error'], 'plan_too_large');
          expect(r.doc.containsKey('steps'), isFalse);
        },
        skip: skip,
      );

      test('a long member list keeps every line within the limit', () async {
        final repo = makeRepo();
        git(repo, ['checkout', '-q', '-b', 'feat/x']);
        makeChange(repo, 'add-x', commit: false);
        final names = ['add-x'];
        for (var i = 0; i < 30; i++) {
          final n = 'docs-${i.toString().padLeft(2, '0')}-${'q' * 40}';
          makeChange(repo, n, verdict: 'APPROVE', commit: false);
          names.add(n);
        }
        commitAll(repo, 'docs: planning artifacts');
        archive(repo, names, commitIt: true);
        expect(names.join(', ').length, greaterThan(1000));
        final doc = await ok(repo, ctx: context(windows: true));
        final steps = argvsOf(doc['steps']);
        for (final s in steps) {
          expect(units(s), lessThanOrEqualTo(32767), reason: '$s');
        }
        final commit = steps.singleWhere((s) => isGit(s, 'commit'));
        final subject = commit.last;
        expect(subject.length, lessThanOrEqualTo(1000));
        expect(subject, contains('add-x'));
        expect(subject, contains('${names.length}'));
      }, skip: skip);
    });

    test('a marker file in the archive commit is removed again', () async {
      final repo = branchRepo();
      archive(repo, ['add-x'], commitIt: true, marker: true);
      final steps = argvsOf((await ok(repo))['steps']);
      final top = topOf(repo);
      final head = git(repo, ['rev-parse', 'HEAD']);
      final marker = 'openspec/changes/add-x/specwright-change.yaml';
      final read = indexOfStep(steps, [
        ..._g,
        'read-tree',
        '--prefix=openspec/changes/add-x/',
        '$head:$ad',
      ]);
      expect(read, greaterThan(0));
      expect(steps[read + 1], [..._g, 'rm', '-q', '--cached', '--', marker]);
      final move = indexOfStep(
        steps,
        undoStep(top, ['move', ad, 'openspec/changes/add-x']),
      );
      expect(move, greaterThan(read));
      expect(steps[move + 1], undoStep(top, ['remove', marker]));
    }, skip: skip);

    test('a created main spec is removed by the steps', () async {
      final repo = branchRepo(deltas: {'n': 'New cap'});
      archive(repo, ['add-x'], commitIt: true);
      final doc = await ok(repo);
      expect(doc['main_specs'], {
        'modified': <String>[],
        'created': ['openspec/specs/n/spec.md'],
      });
      final steps = argvsOf(doc['steps']);
      final top = topOf(repo);
      expect(
        steps,
        hasStep([
          ..._g,
          'rm',
          '-q',
          '--cached',
          '--',
          'openspec/specs/n/spec.md',
        ]),
      );
      final rm = indexOfStep(
        steps,
        undoStep(top, ['remove', 'openspec/specs/n/spec.md']),
      );
      expect(rm, greaterThan(0));
      expect(
        steps[rm + 1],
        undoStep(top, ['rmdir-if-empty', 'openspec/specs/n']),
      );
      expect(steps.expand((s) => s), isNot(contains('--worktree')));
    }, skip: skip);

    test('a change with no main spec backs up nothing', () async {
      final repo = branchRepo(deltas: const {});
      archive(repo, ['add-x'], commitIt: true);
      final doc = await ok(repo);
      final backup = backupOf(repo);
      expect(
        argvsOf(doc['steps']),
        hasStep(undoStep(topOf(repo), ['mkdir', backup])),
      );
      expect(
        (doc['warnings']! as List).cast<String>().any(
          (w) => w.startsWith('Base and amended'),
        ),
        isFalse,
      );
    }, skip: skip);

    test('the commit type comes from the branch prefix or --type', () async {
      for (final (branch, want) in [
        ('bugfix/x', 'fix'),
        ('feat/x', 'feat'),
        ('plain', 'chore'),
      ]) {
        final repo = branchRepo(branch: branch, name: 'r-$want');
        archive(repo, ['add-x'], commitIt: true);
        final steps = argvsOf((await ok(repo))['steps']);
        expect(
          steps,
          hasStep([
            ..._g,
            'commit',
            '-q',
            '-m',
            '$want(add-x): undo archive of add-x',
          ]),
        );
      }
      final repo = branchRepo();
      archive(repo, ['add-x'], commitIt: true);
      final steps = argvsOf((await ok(repo, type: 'docs'))['steps']);
      expect(
        steps,
        hasStep([
          ..._g,
          'commit',
          '-q',
          '-m',
          'docs(add-x): undo archive of add-x',
        ]),
      );
    }, skip: skip);

    test('resuming from another branch checks it out first', () async {
      final repo = branchRepo();
      final a = archive(repo, ['add-x'], commitIt: true)!;
      git(repo, ['checkout', '-q', 'main']);
      final top = topOf(repo);
      final doc = await ok(repo, branch: 'feat/x');
      expect(doc['branch'], 'feat/x');
      expect(doc['head'], a);
      expect(
        argvsOf(doc['steps']),
        containsAllInOrder([
          preflightStep(repo),
          undoStep(top, ['check', 'clean']),
          undoStep(top, ['check', 'tip', 'refs/heads/feat/x', a]),
          undoStep(top, [
            'check',
            'attributes',
            a,
            '--',
            '$ad/review.md',
            '$ad/tasks.md',
          ]),
          [
            ..._g,
            'checkout',
            '-q',
            '--no-overwrite-ignore',
            '--no-recurse-submodules',
            'feat/x',
            '--',
          ],
          undoStep(top, ['check', 'branch', 'feat/x', '--backend', 'git']),
          undoStep(top, ['check', 'tip', 'HEAD', a]),
        ]),
      );
      expect(doc['carried_edits'], <String>[]);
    }, skip: skip);

    test('a resume from main passes a guard on each side of its one '
        'checkout', () async {
      final repo = branchRepo();
      archive(repo, ['add-x'], commitIt: true);
      git(repo, ['checkout', '-q', 'main']);
      final top = topOf(repo);
      final steps = argvsOf((await ok(repo, branch: 'feat/x'))['steps']);
      final checkouts = [
        for (var i = 0; i < steps.length; i++)
          if (steps[i].first == 'git' && steps[i].contains('checkout')) i,
      ];
      expect(checkouts, hasLength(1), reason: '$steps');
      final checkout = checkouts.single;
      final source = indexOfStep(
        steps,
        undoStep(top, ['check', 'branch', 'main', '--backend', 'git']),
      );
      expect(source, inInclusiveRange(0, checkout - 1), reason: '$steps');
      // the recorded view is read again right after the checkout, before
      // anything else reads the archive branch's configuration
      expect(steps[checkout + 1], preflightStep(repo), reason: '$steps');
      expect(
        steps.indexWhere(
          (s) => equals(preflightStep(repo)).matches(s, {}),
          checkout + 2,
        ),
        -1,
      );
      expect(
        steps[checkout + 2],
        undoStep(top, ['check', 'branch', 'feat/x', '--backend', 'git']),
      );
    }, skip: skip);

    test(
      'a detached resume pins the commit HEAD is at before the checkout',
      () async {
        final repo = branchRepo();
        archive(repo, ['add-x'], commitIt: true);
        git(repo, ['checkout', '-q', '--detach', 'main']);
        final head = git(repo, ['rev-parse', 'HEAD']);
        final top = topOf(repo);
        final steps = argvsOf((await ok(repo, branch: 'feat/x'))['steps']);
        final checkout = steps.indexWhere(
          (s) => s.first == 'git' && s.contains('checkout'),
        );
        expect(checkout, greaterThan(0), reason: '$steps');
        final source = indexOfStep(
          steps,
          undoStep(top, ['check', 'branch', '', '--backend', 'git']),
        );
        final pin = indexOfStep(
          steps,
          undoStep(top, ['check', 'tip', 'HEAD', head]),
        );
        expect(source, inInclusiveRange(0, checkout - 1), reason: '$steps');
        expect(pin, inInclusiveRange(0, checkout - 1), reason: '$steps');
      },
      skip: skip,
    );

    test('an environment that names another checkout is git_env', () async {
      final repo = branchRepo();
      archive(repo, ['add-x'], commitIt: true);
      final other = '${tmp.path}/other';
      Process.runSync('git', ['clone', '-q', repo, other]);
      git(other, ['branch', 'main', 'origin/main']);
      expect(
        git(other, ['ls-tree', '-r', '--name-only', 'HEAD', '--', ad]),
        isNotEmpty,
        reason: 'the other checkout holds the same archive, so it would plan',
      );
      final r = await plan(
        rq(repo),
        context(
          environment: {
            ...Platform.environment,
            'GIT_DIR': '$other/.git',
            'GIT_WORK_TREE': other,
          },
        ),
      );
      expect(r.code, 1, reason: '${r.doc}');
      expect(r.doc['error'], 'git_env', reason: '${r.doc}');
      expect(r.doc.containsKey('steps'), isFalse);
    }, skip: skip);

    test(
      'an uncommitted archive warns when --branch is not the current one',
      () async {
        final repo = branchRepo();
        archive(repo, ['add-x']);
        final doc = await ok(repo, branch: 'other');
        expect(doc['branch'], 'feat/x');
        expect(
          (doc['warnings']! as List).first,
          'The archive is uncommitted, so the plan guards the current branch '
          'feat/x, not other.',
        );
      },
      skip: skip,
    );

    group('refusals', () {
      Future<void> expectStop(
        _Out r,
        String error,
        String message, [
        Map<String, Object?> extra = const {},
      ]) async {
        expect(r.code, 1, reason: '${r.doc}');
        expect(r.doc, {
          'ok': false,
          'error': error,
          'message': message,
          ...extra,
        });
      }

      test('no_archive: nothing archived', () async {
        final repo = branchRepo();
        await expectStop(
          await stop(repo),
          'no_archive',
          'No archive of add-x ($ad) found in the working tree or on feat/x',
          {'commits': <String>[]},
        );
      }, skip: skip);

      test('no_archive: the archive was reverted', () async {
        final repo = branchRepo();
        final a = archive(repo, ['add-x'], commitIt: true)!;
        git(repo, ['revert', '--no-edit', a]);
        await expectStop(
          await stop(repo),
          'no_archive',
          'The archive commit(s) ${a.substring(0, 9)} of add-x were reverted: '
              '$ad is not on feat/x',
          {
            'commits': [a],
          },
        );
      }, skip: skip);

      test('staged_changes', () async {
        final repo = branchRepo();
        archive(repo, ['add-x'], commitIt: true);
        put(repo, 'src.txt', 'x\n');
        git(repo, ['add', 'src.txt']);
        await expectStop(
          await stop(repo),
          'staged_changes',
          'The index differs from HEAD: src.txt. Unstage or commit them first.',
        );
      }, skip: skip);

      test('staged_changes of an uncommitted archive', () async {
        final repo = branchRepo();
        archive(repo, ['add-x']);
        put(repo, 'src.txt', 'x\n');
        git(repo, ['add', 'src.txt']);
        await expectStop(
          await stop(repo),
          'staged_changes',
          'The index differs from HEAD: src.txt. Unstage or commit them first.',
        );
      }, skip: skip);

      test('target_exists', () async {
        final repo = branchRepo();
        archive(repo, ['add-x'], commitIt: true);
        put(repo, 'openspec/changes/add-x/new.md', 'x\n');
        await expectStop(
          await stop(repo),
          'target_exists',
          'openspec/changes/add-x already exists; merge or move it first',
          {'path': 'openspec/changes/add-x'},
        );
      }, skip: skip);

      test('backup_exists', () async {
        final repo = branchRepo();
        archive(repo, ['add-x'], commitIt: true);
        Directory(backupOf(repo)).createSync(recursive: true);
        await expectStop(
          await stop(repo),
          'backup_exists',
          '${backupOf(repo)} exists; move or delete it, then plan again',
          {'path': backupOf(repo)},
        );
      }, skip: skip);

      test('member_missing', () async {
        final repo = makeRepo();
        git(repo, ['checkout', '-q', '-b', 'feat/x']);
        makeChange(repo, 'add-x', deltas: {'a': 'A thing'});
        makeChange(repo, 'add-y', verdict: 'APPROVE', deltas: {'b': 'B thing'});
        archive(repo, ['add-x', 'add-y'], commitIt: true);
        const ay = 'openspec/changes/archive/$_date-add-y';
        Directory('$repo/$ay').deleteSync(recursive: true);
        commitAll(repo, 'drop the archive of add-y');
        await expectStop(
          await stop(repo),
          'member_missing',
          'Archive directories of this archive were deleted on feat/x after '
              'it: $ay. Restore them (or undo the archive by hand), then plan '
              'again.',
          {
            'paths': [ay],
          },
        );
      }, skip: skip);

      test('duplicate_member', () async {
        final repo = branchRepo();
        archive(repo, ['add-x']);
        put(repo, 'openspec/changes/archive/2026-10-18-add-x/old.md', 'x\n');
        await expectStop(
          await stop(repo),
          'duplicate_member',
          '$_date-add-x and 2026-10-18-add-x both restore to '
              'openspec/changes/add-x; move one out of '
              'openspec/changes/archive/, then plan again',
          {
            'path': 'openspec/changes/add-x',
            'archived_names': ['$_date-add-x', '2026-10-18-add-x'],
          },
        );
      }, skip: skip);

      test(
        'dirty_tree: a synced main spec deleted from the working tree',
        () async {
          final repo = branchRepo();
          archive(repo, ['add-x']);
          File('$repo/$specA').deleteSync();
          await expectStop(
            await stop(repo),
            'dirty_tree',
            'Deleted in the working tree: $specA. Restore them with `git '
                'restore -- $specA` (or commit the deletion), then plan again.',
            {
              'files': [specA],
            },
          );
        },
        skip: skip,
      );

      test(
        'dirty_tree: a resume on another branch with a dirty tree',
        () async {
          final repo = branchRepo();
          archive(repo, ['add-x'], commitIt: true);
          git(repo, ['checkout', '-q', 'main']);
          put(repo, 'junk.txt', 'x\n');
          await expectStop(
            await stop(repo, branch: 'feat/x'),
            'dirty_tree',
            'The working tree is dirty, so the branch cannot be checked out: '
                '?? junk.txt',
            {
              'files': ['junk.txt'],
            },
          );
        },
        skip: skip,
      );

      test('bad_ref for a branch that is no commit (committed mode)', () async {
        final repo = branchRepo();
        archive(repo, ['add-x'], commitIt: true);
        await expectStop(
          await stop(repo, branch: 'nowhere'),
          'no_archive',
          'No archive of add-x ($ad) found in the working tree or on nowhere',
          {'commits': <String>[]},
        );
      }, skip: skip);
    });

    group('status and staged reads (D2)', () {
      ToolResult fakeResult(
        List<int> stdout, {
        int code = 0,
        List<int> stderr = const [],
      }) => ToolResult(
        code,
        Uint8List.fromList(stdout),
        Uint8List.fromList(stderr),
      );

      List<int> z(List<String> fields) => [
        for (final f in fields) ...[...utf8.encode(f), 0],
      ];

      bool isStatus(List<String> c) => c.contains('status');
      bool isCarried(List<String> c) => isStatus(c) && c.contains('--');
      bool isResumeStatus(List<String> c) => isStatus(c) && !c.contains('--');
      // the planner's staged-index read, before and after its command changed
      bool isStaged(List<String> c) =>
          c.contains('--cached') && c.contains('--name-only');

      /// A context whose runner answers a command with [answer] when it gives
      /// one and runs every other command for real; [calls] logs each command
      /// with the environment it ran in.
      FinishContext faking(
        ToolResult? Function(List<String> command) answer, {
        List<(List<String>, Map<String, String>)>? calls,
      }) => FinishContext(
        runner: (cwd, command, env) async {
          calls?.add((command, env));
          return answer(command) ??
              await runTool(cwd, command, environment: env);
        },
      );

      Future<_Out> resumeOn(String repo, FinishContext ctx) async {
        archive(repo, ['add-x'], commitIt: true);
        git(repo, ['checkout', '-q', 'main']);
        return plan(rq(repo, branch: 'feat/x'), ctx);
      }

      void expectOneStop(_Out r, String error, {int code = 1}) {
        expect(r.code, code, reason: '${r.doc}');
        expect(r.doc['ok'], false);
        expect(r.doc['error'], error, reason: '${r.doc}');
        expect(r.doc.containsKey('steps'), isFalse);
      }

      test('a failed resume status read is vcs_error', () async {
        final repo = branchRepo();
        final r = await resumeOn(
          repo,
          faking((c) => isResumeStatus(c) ? fakeResult([], code: 1) : null),
        );
        expectOneStop(r, 'vcs_error');
        expect(r.doc['message'], contains('git status'));
        expect(r.doc['message'], contains('exit status 1'));
      }, skip: skip);

      test('a failed resume status read holds git stderr', () async {
        final repo = branchRepo();
        final r = await resumeOn(
          repo,
          faking(
            (c) => isResumeStatus(c)
                ? fakeResult(
                    [],
                    code: 128,
                    stderr: utf8.encode('fatal: boom\n'),
                  )
                : null,
          ),
        );
        expectOneStop(r, 'vcs_error');
        expect(r.doc['message'], contains('git status'));
        expect(r.doc['message'], contains('fatal: boom'));
      }, skip: skip);

      test('a resume status read that writes to stderr is vcs_error', () async {
        final repo = branchRepo();
        final r = await resumeOn(
          repo,
          faking(
            (c) => isResumeStatus(c)
                ? fakeResult(
                    [],
                    stderr: utf8.encode('warning: could not open directory\n'),
                  )
                : null,
          ),
        );
        expectOneStop(r, 'vcs_error');
        expect(r.doc['message'], contains('could not open directory'));
      }, skip: skip);

      test('a failed carried-edits read is vcs_error', () async {
        final repo = branchRepo();
        archive(repo, ['add-x'], commitIt: true);
        final r = await plan(
          rq(repo),
          faking((c) => isCarried(c) ? fakeResult([], code: 1) : null),
        );
        expectOneStop(r, 'vcs_error');
        expect(r.doc['message'], contains('git status'));
      }, skip: skip);

      test('a failed staged-index read is vcs_error', () async {
        final repo = branchRepo();
        archive(repo, ['add-x'], commitIt: true);
        final r = await plan(
          rq(repo),
          faking((c) => isStaged(c) ? fakeResult([], code: 128) : null),
        );
        expectOneStop(r, 'vcs_error');
        expect(r.doc['message'], contains('git diff-index --cached'));
      }, skip: skip);

      test('a failed staged-index read on an uncommitted archive', () async {
        final repo = branchRepo();
        archive(repo, ['add-x']);
        final r = await plan(
          rq(repo),
          faking((c) => isStaged(c) ? fakeResult([], code: 128) : null),
        );
        expectOneStop(r, 'vcs_error');
        expect(r.doc['message'], contains('git diff-index --cached'));
      }, skip: skip);

      test('both status reads are read-only and list every untracked file', () async {
        final repo = branchRepo();
        archive(repo, ['add-x'], commitIt: true);
        final calls = <(List<String>, Map<String, String>)>[];
        await plan(rq(repo), faking((_) => null, calls: calls));
        git(repo, ['checkout', '-q', 'main']);
        await plan(
          rq(repo, branch: 'feat/x'),
          faking((_) => null, calls: calls),
        );
        final statuses = [
          for (final c in calls)
            if (isStatus(c.$1)) c,
        ];
        expect(statuses.length, 2, reason: '$calls');
        for (final (command, env) in statuses) {
          expect(
            command,
            containsAllInOrder([
              '-c',
              'core.fsmonitor=false',
              '--no-optional-locks',
              'status',
              '--porcelain=v1',
              '-z',
              '--untracked-files=all',
            ]),
          );
          expect(env['GIT_OPTIONAL_LOCKS'], '0');
        }
        // the calls that cannot refresh the index keep the caller's environment
        expect(
          [
            for (final c in calls)
              if (!isStatus(c.$1)) c.$2['GIT_OPTIONAL_LOCKS'],
          ].where((v) => v == '0'),
          isEmpty,
        );
      }, skip: skip);

      test(
        'the resume report holds each path whole, a rename with both ends',
        () async {
          final repo = branchRepo();
          final r = await resumeOn(
            repo,
            faking(
              (c) => isResumeStatus(c)
                  ? fakeResult(
                      z([' M README.md', 'R  b.md', 'a.md', r'?? c\d.md']),
                    )
                  : null,
            ),
          );
          expectOneStop(r, 'dirty_tree');
          expect(r.doc['files'], ['README.md', 'b.md', 'a.md', r'c\d.md']);
        },
        skip: skip,
      );

      test(
        'the dirty_tree message reads as it did for ordinary names',
        () async {
          final repo = branchRepo();
          final r = await resumeOn(
            repo,
            faking(
              (c) => isResumeStatus(c)
                  ? fakeResult(z([' M README.md', '?? new.txt']))
                  : null,
            ),
          );
          expect(
            r.doc['message'],
            'The working tree is dirty, so the branch cannot be checked out: '
            'M README.md; ?? new.txt',
          );
        },
        skip: skip,
      );

      test(
        'the message shows a rename as source -> path, a tab as \\t',
        () async {
          final repo = branchRepo();
          final r = await resumeOn(
            repo,
            faking(
              (c) => isResumeStatus(c)
                  ? fakeResult(z(['R  b.md', 'a.md', '?? x\ty.md']))
                  : null,
            ),
          );
          expect(r.doc['message'], endsWith(r'R a.md -> b.md; ?? x\ty.md'));
          expect(r.doc['files'], ['b.md', 'a.md', 'x\ty.md']);
        },
        skip: skip,
      );

      test(
        'the message keeps a trailing space and shows a CR as \\r',
        () async {
          final repo = branchRepo();
          final r = await resumeOn(
            repo,
            faking(
              (c) => isResumeStatus(c) ? fakeResult(z(['?? x\ry.md '])) : null,
            ),
          );
          expect(r.doc['message'], endsWith('?? x\\ry.md '));
          expect(r.doc['files'], ['x\ry.md ']);
        },
        skip: skip,
      );

      test(
        'a dirty resume path that is not UTF-8 is not_utf8, with no steps',
        () async {
          final repo = branchRepo();
          final r = await resumeOn(
            repo,
            faking(
              (c) => isResumeStatus(c)
                  ? fakeResult([...utf8.encode('?? bad'), 0xff, 0])
                  : null,
            ),
          );
          expectOneStop(r, 'not_utf8');
        },
        skip: skip,
      );

      test(
        'a carried edit that is a rename reports both names, in byte order',
        () async {
          final repo = branchRepo();
          archive(repo, ['add-x'], commitIt: true);
          final r = await plan(
            rq(repo),
            faking(
              (c) => isCarried(c)
                  ? fakeResult(
                      z([
                        'R  $ad/new.md',
                        '$ad/a/old.md',
                        ' M $ad/b.md',
                        '?? $ad/a.md',
                      ]),
                    )
                  : null,
            ),
          );
          expect(r.code, 0, reason: '${r.doc}');
          expect((r.doc['carried_edits']! as List).cast<String>(), [
            '$ad/a.md',
            '$ad/a/old.md',
            '$ad/b.md',
            '$ad/new.md',
          ]);
        },
        skip: skip,
      );

      test('a carried-edits record outside the members is dropped before it is decoded', () async {
        final repo = branchRepo();
        archive(repo, ['add-x'], commitIt: true);
        final r = await plan(
          rq(repo),
          faking(
            (c) => isCarried(c)
                ? fakeResult([
                    ...utf8.encode('?? openspec/changes/archive/older/bad'),
                    0xff,
                    0,
                    ...z([' M $ad/design.md']),
                  ])
                : null,
          ),
        );
        expect(r.code, 0, reason: '${r.doc}');
        expect((r.doc['carried_edits']! as List).cast<String>(), [
          '$ad/design.md',
        ]);
      }, skip: skip);

      test(
        'a carried-edits member name that is not UTF-8 is not_utf8',
        () async {
          final repo = branchRepo();
          archive(repo, ['add-x'], commitIt: true);
          final r = await plan(
            rq(repo),
            faking(
              (c) => isCarried(c)
                  ? fakeResult([...utf8.encode('?? $ad/bad'), 0xff, 0])
                  : null,
            ),
          );
          expectOneStop(r, 'not_utf8');
        },
        skip: skip,
      );

      test('a usage stop from the state read exits 2', () async {
        final repo = branchRepo();
        final r = await plan(
          rq(repo),
          readerCtx(
            (top, code, branch) async =>
                throw VcsStop('usage', 'missing --branch', code: 2),
          ),
        );
        expectOneStop(r, 'usage', code: 2);
        expect(r.doc['message'], 'missing --branch');
      }, skip: skip);

      test('an injected usage VcsStop is one usage document, exit 2', () async {
        final repo = branchRepo();
        final r = await plan(
          rq(repo),
          readerCtx(
            (top, code, branch) async =>
                throw VcsStop('usage', 'bad option', code: 2),
          ),
        );
        expect(r.code, 2);
        expect(r.doc, {'ok': false, 'error': 'usage', 'message': 'bad option'});
      }, skip: skip);

      test(
        'any other stop from the state read stays exit 1, bad_setting too',
        () async {
          final repo = branchRepo();
          for (final (error, code) in [
            ('bad_setting', 2),
            ('not_repository', 1),
            ('git_error', 1),
          ]) {
            final r = await plan(
              rq(repo),
              readerCtx(
                (top, c, branch) async => throw VcsStop(error, 'm', code: code),
              ),
            );
            expect(r.code, 1, reason: error);
            expect(r.doc['error'], error);
          }
        },
        skip: skip,
      );

      test('a failed branch lookup in the state read is git_error', () async {
        final repo = branchRepo();
        final r = await plan(
          rq(repo),
          readerCtx(
            (top, code, branch) async =>
                throw VcsStop('git_error', 'fatal: no branch'),
          ),
        );
        expectOneStop(r, 'git_error');
        expect(r.doc['message'], 'fatal: no branch');
      }, skip: skip);
    });

    group('Git guards (D2, group 10)', () {
      Map<String, String> envWith(Map<String, String> extra) => {
        ...Platform.environment,
        ...extra,
      };

      String gitDirOf(String repo) =>
          git(repo, ['rev-parse', '--absolute-git-dir']);

      ToolResult failed(int code, [List<int> stdout = const []]) =>
          ToolResult(code, Uint8List.fromList(stdout), Uint8List(0));

      FinishContext faking(
        ToolResult? Function(List<String> command) answer, {
        List<List<String>>? calls,
      }) => FinishContext(
        runner: (cwd, command, env) async {
          calls?.add(command);
          return answer(command) ??
              await runTool(cwd, command, environment: env);
        },
      );

      Future<void> refuses(
        String repo,
        String error, {
        FinishContext? ctx,
        String? branch,
        String? says,
      }) async {
        final r = await plan(rq(repo, branch: branch), ctx);
        expect(r.code, 1, reason: '${r.doc}');
        expect(r.doc['error'], error, reason: '${r.doc}');
        expect(r.doc.containsKey('steps'), isFalse);
        if (says != null) expect(r.doc['message'], contains(says));
      }

      test('the first step is check preflight with the planned view', () async {
        final repo = branchRepo();
        archive(repo, ['add-x'], commitIt: true);
        final gd = gitDirOf(repo);
        final doc = await ok(repo);
        expect(argvsOf(doc['steps']).first, [
          Platform.resolvedExecutable,
          '--project',
          topOf(repo),
          'finish',
          'undo-step',
          'check',
          'preflight',
          '--git-dir',
          gd,
          '--common-dir',
          git(repo, [
            'rev-parse',
            '--path-format=absolute',
            '--git-common-dir',
          ]),
          '--index',
          git(repo, [
            'rev-parse',
            '--path-format=absolute',
            '--git-path',
            'index',
          ]),
          '--objects',
          git(repo, [
            'rev-parse',
            '--path-format=absolute',
            '--git-path',
            'objects',
          ]),
        ]);
      }, skip: skip);

      test(
        'emitted Git steps carry the safety options and the checkout flags',
        () async {
          final repo = branchRepo();
          final a = archive(repo, ['add-x'], commitIt: true)!;
          git(repo, ['checkout', '-q', 'main']);
          final doc = await ok(repo, branch: 'feat/x');
          const safe = ['git', '--literal-pathspecs', '--no-replace-objects'];
          final git_ = [
            for (final s in argvsOf(doc['steps']))
              if (s.first == 'git') s,
          ];
          expect(git_, isNotEmpty);
          for (final s in git_) {
            expect(s.take(3), safe, reason: '$s');
          }
          expect(git_.first, [
            ...safe,
            'checkout',
            '-q',
            '--no-overwrite-ignore',
            '--no-recurse-submodules',
            'feat/x',
            '--',
          ]);
          final restore = git_.firstWhere((s) => s[3] == 'restore');
          final parent = git(repo, ['rev-parse', '$a^']);
          expect(restore, contains('--source=$parent'));
          expect(restore.any((x) => x.contains('^')), isFalse);
        },
        skip: skip,
      );

      for (final name in [
        'GIT_GLOB_PATHSPECS',
        'GIT_NOGLOB_PATHSPECS',
        'GIT_ICASE_PATHSPECS',
      ]) {
        test('the plan refuses a true $name', () async {
          final repo = branchRepo();
          archive(repo, ['add-x'], commitIt: true);
          await refuses(
            repo,
            'git_env',
            ctx: context(environment: envWith({name: '1'})),
            says: name,
          );
        });
      }

      for (final name in [
        'GIT_NAMESPACE',
        'GIT_ALTERNATE_OBJECT_DIRECTORIES',
      ]) {
        test('the plan refuses a non-empty $name', () async {
          final repo = branchRepo();
          archive(repo, ['add-x'], commitIt: true);
          await refuses(
            repo,
            'git_env',
            ctx: context(environment: envWith({name: 'x'})),
            says: name,
          );
        });
      }

      test('the plan refuses an index routed elsewhere', () async {
        final repo = branchRepo();
        archive(repo, ['add-x'], commitIt: true);
        final other = '${gitDirOf(repo)}/other-index';
        File(
          other,
        ).writeAsBytesSync(File('${gitDirOf(repo)}/index').readAsBytesSync());
        await refuses(
          repo,
          'git_env',
          ctx: context(environment: envWith({'GIT_INDEX_FILE': other})),
          says: 'index',
        );
      });

      test('the plan refuses a grafts file, a partial clone and a sparse '
          'checkout', () async {
        final repo = branchRepo();
        archive(repo, ['add-x'], commitIt: true);
        final gd = gitDirOf(repo);
        Directory('$gd/info').createSync(recursive: true);
        File('$gd/info/grafts').writeAsStringSync('\n');
        await refuses(repo, 'git_env', says: 'grafts');
        File('$gd/info/grafts').deleteSync();
        git(repo, ['config', 'remote.origin.promisor', 'true']);
        await refuses(repo, 'git_env', says: 'partial clone');
        git(repo, ['config', '--unset', 'remote.origin.promisor']);
        git(repo, ['config', 'core.sparseCheckout', 'true']);
        await refuses(repo, 'git_env', says: 'sparse checkout');
      });

      test('the plan refuses a workspace holding GitButler metadata', () async {
        final repo = branchRepo();
        archive(repo, ['add-x'], commitIt: true);
        Directory('${gitDirOf(repo)}/gitbutler').createSync();
        await refuses(repo, 'gitbutler_workspace');
      });

      for (final marker in ['MERGE_HEAD', 'rebase-merge', 'sequencer']) {
        test('the plan refuses while $marker exists', () async {
          final repo = branchRepo();
          archive(repo, ['add-x'], commitIt: true);
          final path = '${gitDirOf(repo)}/$marker';
          if (marker == 'MERGE_HEAD') {
            File(path)
                .writeAsStringSync('${git(repo, ['rev-parse', 'HEAD'])}\n');
          } else {
            Directory(path).createSync();
          }
          await refuses(repo, 'operation_in_progress');
        });
      }

      test(
        'a staged gitlink that diff.ignoreSubmodules hides is staged_changes',
        () async {
          final repo = branchRepo();
          archive(repo, ['add-x'], commitIt: true);
          git(repo, ['config', 'diff.ignoreSubmodules', 'all']);
          git(repo, [
            'update-index',
            '--add',
            '--cacheinfo',
            '160000,${git(repo, ['rev-parse', 'HEAD'])},sub',
          ]);
          await refuses(repo, 'staged_changes');
        },
        skip: skip,
      );

      test(
        'a resume refuses an assume-unchanged file anywhere in the index',
        () async {
          final repo = branchRepo();
          archive(repo, ['add-x'], commitIt: true);
          git(repo, ['checkout', '-q', 'main']);
          git(repo, ['update-index', '--assume-unchanged', 'README.md']);
          File('$repo/README.md').writeAsStringSync('hidden edit\n');
          await refuses(repo, 'git_env', branch: 'feat/x', says: 'README.md');
          expect(File('$repo/README.md').readAsStringSync(), 'hidden edit\n');
        },
      );

      test(
        'a plan that does not switch branches scans only what it touches',
        () async {
          final repo = branchRepo();
          archive(repo, ['add-x'], commitIt: true);
          git(repo, ['update-index', '--assume-unchanged', 'README.md']);
          await ok(repo);
          git(repo, ['update-index', '--no-assume-unchanged', 'README.md']);
          git(repo, [
            'update-index',
            '--skip-worktree',
            'openspec/specs/a/spec.md',
          ]);
          await refuses(repo, 'git_env', says: 'openspec/specs/a/spec.md');
        },
      );

      test('the tip lookup is an exact branch lookup', () async {
        final repo = branchRepo();
        archive(repo, ['add-x'], commitIt: true);
        git(repo, ['checkout', '-q', 'main']);
        git(repo, ['tag', 'refs/heads/feat/x', 'feat/x']);
        git(repo, ['tag', 'feat/x', 'feat/x']);
        git(repo, ['branch', '-D', 'feat/x']);
        final r = await plan(rq(repo, branch: 'feat/x'));
        expect(r.code, 1, reason: '${r.doc}');
        expect(r.doc['error'], 'no_archive');
      });

      test('a failed archive-presence read is vcs_error', () async {
        final repo = branchRepo();
        archive(repo, ['add-x'], commitIt: true);
        await refuses(
          repo,
          'vcs_error',
          ctx: faking(
            (c) =>
                c.contains('ls-tree') &&
                    c.contains('--name-only') &&
                    !c.contains('-z')
                ? failed(128)
                : null,
          ),
        );
      }, skip: skip);

      test('a failed archive diff read is vcs_error', () async {
        final repo = branchRepo();
        archive(repo, ['add-x'], commitIt: true);
        await refuses(
          repo,
          'vcs_error',
          ctx: faking((c) => c.contains('diff-tree') ? failed(128) : null),
        );
      }, skip: skip);

      test('a failed content read of a member file is vcs_error', () async {
        final repo = branchRepo();
        archive(repo, ['add-x'], commitIt: true);
        // a resume reads the tip's blobs; on the current branch the decision
        // files come from the work tree (D2)
        git(repo, ['checkout', '-q', 'main']);
        await refuses(
          repo,
          'vcs_error',
          branch: 'feat/x',
          ctx: faking(
            (c) => c.contains('cat-file') && c.contains('blob')
                ? failed(128)
                : null,
          ),
        );
      }, skip: skip);

      test(
        'a member replaced by a file is vcs_error naming the path',
        () async {
          final repo = branchRepo();
          makeChange(repo, 'add-y', deltas: {'b': 'Other thing'});
          archive(repo, ['add-x', 'add-y'], commitIt: true);
          const dir = 'openspec/changes/archive/$_date-add-y';
          git(repo, ['rm', '-r', '-q', dir]);
          Directory('$repo/$dir').parent.createSync(recursive: true);
          File('$repo/$dir').writeAsStringSync('now a file\n');
          commitAll(repo, 'replace the member with a file');
          await refuses(repo, 'vcs_error', says: dir);
        },
        skip: skip,
      );

      test('an unlistable delta directory is vcs_error (POSIX)', () async {
        final repo = branchRepo();
        archive(repo, ['add-x']);
        final specs = '$repo/openspec/changes/archive/$_date-add-x/specs';
        Process.runSync('chmod', ['000', specs]);
        addTearDown(() => Process.runSync('chmod', ['755', specs]));
        await refuses(repo, 'vcs_error');
      }, skip: Platform.isWindows ? 'platform: no POSIX permissions' : false);

      test('ignored content under the archive root is git_env', () async {
        final repo = branchRepo();
        archive(repo, ['add-x']);
        File('$repo/.git/info/exclude').writeAsStringSync('*-add-y/\n');
        put(repo, 'openspec/changes/archive/$_date-add-y/proposal.md', 'old\n');
        await refuses(repo, 'git_env', says: '$_date-add-y');
      }, skip: skip);

      test('the plan warns about the index, edits and operations', () async {
        final repo = branchRepo();
        archive(repo, ['add-x'], commitIt: true);
        final doc = await ok(repo);
        final warnings = (doc['warnings']! as List).cast<String>();
        expect(
          warnings,
          contains(
            'Do not edit files after this plan is printed, and do not start a '
            'merge, cherry-pick, revert or rebase while the steps run.',
          ),
        );
        expect(
          warnings,
          contains(
            'The index must not be changed by other commands or hooks while '
            'the steps run.',
          ),
        );
        final recovery = warnings.firstWhere(
          (w) => w.startsWith('If a step fails after the steps began'),
        );
        expect(recovery, contains(backupOf(repo)));
        expect(recovery, contains('openspec/changes/add-x'));
        expect(recovery, isNot(contains('git restore')));
        expect(recovery, isNot(contains('`')));
      }, skip: skip);

      test('a resume warns to check Git before switching back', () async {
        final repo = branchRepo();
        archive(repo, ['add-x'], commitIt: true);
        git(repo, ['checkout', '-q', 'main']);
        final doc = await ok(repo, branch: 'feat/x');
        expect(
          (doc['warnings']! as List).cast<String>(),
          contains(
            "If a step stops after the checkout, check Git's effective work "
            'tree and index before switching back to main, never switch '
            'blindly.',
          ),
        );
      }, skip: skip);
    });

    group('Rerun eligibility from the restored copy (D2, group 11)', () {
      const tasksPath = '$ad/tasks.md';
      const tasksOfY = 'openspec/changes/archive/$_date-add-y/tasks.md';
      const pending = '# Tasks\n\n- [ ] 1.1 do it\n- [ ] 1.2 [user] check it\n';

      /// A smudge driver that records each run in a sentinel file; returns the
      /// sentinel's path. The clean side is the identity, so a tracked file
      /// stays clean under the attribute.
      String sentinel(String repo, [String driver = 'sentinel']) {
        final path = _posix('${tmp.path}/$driver-ran.txt');
        git(repo, [
          'config',
          'filter.$driver.smudge',
          'echo ran >> "$path"; cat',
        ]);
        git(repo, ['config', 'filter.$driver.clean', 'cat']);
        return path;
      }

      /// `feat/x` with `add-x` archived (and `add-y` too when [bulk]); on the
      /// archive branch alone `openspec/.gitattributes` holds [rules]; back on
      /// a clean `main`.
      String attrRepo(String rules, {bool bulk = false}) {
        final repo = branchRepo();
        if (bulk) {
          makeChange(
            repo,
            'add-y',
            verdict: 'APPROVE',
            deltas: {'b': 'B thing'},
            tasks: pending,
          );
        }
        archive(repo, ['add-x', if (bulk) 'add-y'], commitIt: true);
        put(repo, 'openspec/.gitattributes', rules);
        commitAll(repo, 'chore: attributes of the archive branch');
        git(repo, ['checkout', '-q', 'main']);
        expect(git(repo, ['status', '--porcelain']), '');
        return repo;
      }

      Future<Map<String, Object?>> refused(
        String repo,
        String error, {
        String? branch,
        List<String> says = const [],
        FinishContext? ctx,
      }) async {
        final r = await plan(rq(repo, branch: branch), ctx);
        expect(r.code, 1, reason: '${r.doc}');
        expect(r.doc['error'], error, reason: '${r.doc}');
        expect(r.doc.containsKey('steps'), isFalse);
        for (final s in says) {
          expect(r.doc['message'], contains(s));
        }
        return r.doc;
      }

      Map<String, Object?> member(Map<String, Object?> doc, String name) =>
          ((doc['members']! as List).cast<Map<String, Object?>>()).firstWhere(
            (m) => m['name'] == name,
          );

      test('a checkout filter on a rerun input is unsupported_filter and '
          'never runs', () async {
        final repo = attrRepo('tasks.md filter=sentinel\n', bulk: true);
        final ran = sentinel(repo);
        expect(
          git(repo, [
            'check-attr',
            '--source=feat/x',
            'filter',
            '--',
            tasksPath,
          ]),
          '$tasksPath: filter: sentinel',
        );
        await refused(
          repo,
          'unsupported_filter',
          branch: 'feat/x',
          says: [tasksPath, 'filter'],
        );
        expect(File(ran).existsSync(), isFalse);
      }, skip: skip);

      for (final (rule, shown, attribute) in [
        ('-filter', 'filter: unset', 'filter'),
        (
          '-working-tree-encoding',
          'working-tree-encoding: unset',
          'working-tree-encoding',
        ),
      ]) {
        test('an explicit "$rule" is unsupported_filter although no '
            'conversion would apply', () async {
          final repo = attrRepo('tasks.md $rule\n');
          expect(
            git(repo, [
              'check-attr',
              '--source=feat/x',
              '--all',
              '--',
              tasksPath,
            ]),
            '$tasksPath: $shown',
          );
          await refused(
            repo,
            'unsupported_filter',
            branch: 'feat/x',
            says: [tasksPath, attribute],
          );
        }, skip: skip);
      }

      test('a filter whose name is unspecified is unsupported_filter and '
          'the driver never runs', () async {
        final repo = attrRepo('tasks.md filter=unspecified\n');
        final ran = sentinel(repo, 'unspecified');
        expect(
          git(repo, [
            'check-attr',
            '--source=feat/x',
            '--all',
            '--',
            tasksPath,
          ]),
          '$tasksPath: filter: unspecified',
        );
        await refused(
          repo,
          'unsupported_filter',
          branch: 'feat/x',
          says: [tasksPath],
        );
        expect(File(ran).existsSync(), isFalse);
      }, skip: skip);

      test('a line-ending conversion alone is accepted', () async {
        final repo = attrRepo('tasks.md text eol=crlf\n');
        final doc = await plan(rq(repo, branch: 'feat/x'));
        expect(doc.code, 0, reason: '${doc.doc}');
      }, skip: skip);

      test('an untracked attributes file in the work tree is '
          'unsupported_filter before any checkout', () async {
        final repo = branchRepo();
        archive(repo, ['add-x'], commitIt: true);
        git(repo, ['checkout', '-q', 'main']);
        File('$repo/.git/info/exclude').writeAsStringSync('.gitattributes\n');
        put(repo, 'openspec/.gitattributes', 'tasks.md filter=sentinel\n');
        final ran = sentinel(repo);
        expect(git(repo, ['status', '--porcelain']), '');
        expect(
          git(repo, ['check-ignore', 'openspec/.gitattributes']),
          'openspec/.gitattributes',
        );
        final calls = <List<String>>[];
        await refused(
          repo,
          'unsupported_filter',
          branch: 'feat/x',
          says: ['openspec/.gitattributes'],
          ctx: FinishContext(
            runner: (cwd, command, env) {
              calls.add(command);
              return runTool(cwd, command, environment: env);
            },
          ),
        );
        expect(git(repo, ['branch', '--show-current']), 'main');
        expect(File(ran).existsSync(), isFalse);
        expect(calls.where((c) => c.contains('checkout')), isEmpty);
      }, skip: skip);

      test('a current-branch filter on an unchanged decision file is '
          'unsupported_filter naming HEAD', () async {
        final repo = branchRepo();
        archive(repo, ['add-x'], commitIt: true);
        git(repo, ['checkout', '-q', 'main']);
        git(repo, ['checkout', 'feat/x', '--', tasksPath]);
        put(repo, 'openspec/.gitattributes', 'tasks.md filter=sentinel\n');
        commitAll(repo, 'chore: main holds the same tasks.md');
        final ran = sentinel(repo);
        expect(
          git(repo, ['rev-parse', 'HEAD:$tasksPath']),
          git(repo, ['rev-parse', 'feat/x:$tasksPath']),
          reason: 'the same blob on both branches',
        );
        expect(
          git(repo, [
            'check-attr',
            '--source=feat/x',
            '--all',
            '--',
            tasksPath,
          ]),
          '',
          reason: 'the archive branch gives no attribute',
        );
        expect(git(repo, ['status', '--porcelain']), '');
        await refused(
          repo,
          'unsupported_filter',
          branch: 'feat/x',
          says: [tasksPath, 'HEAD'],
        );
        expect(File(ran).existsSync(), isFalse);
      }, skip: skip);

      test('a decision file committed as a symlink is unsupported_filter '
          'naming the path', () async {
        final repo = branchRepo();
        archive(repo, ['add-x'], commitIt: true);
        File('${tmp.path}/link-text.txt').writeAsStringSync('elsewhere.md');
        final oid = git(repo, [
          'hash-object',
          '-w',
          '${tmp.path}/link-text.txt',
        ]);
        File('$repo/$tasksPath').deleteSync();
        git(repo, [
          'update-index',
          '--add',
          '--cacheinfo',
          '120000,$oid,$tasksPath',
        ]);
        git(repo, ['commit', '-q', '-m', 'chore: tasks.md becomes a link']);
        expect(
          git(repo, ['ls-tree', 'feat/x', '--', tasksPath]),
          startsWith('120000 blob'),
        );
        git(repo, ['checkout', '-q', 'main']);
        expect(git(repo, ['status', '--porcelain']), '');
        await refused(
          repo,
          'unsupported_filter',
          branch: 'feat/x',
          says: [tasksPath, 'symlink'],
        );
      }, skip: skip);

      test('a main spec whose type the archive changed is unsupported_entry '
          'naming it', () async {
        final repo = branchRepo();
        // the parent of the archive commit tracks the spec as a symlink; the
        // archive commit writes it as a regular file
        File('${tmp.path}/link-text.txt').writeAsStringSync('b/spec.md');
        final oid = git(repo, [
          'hash-object',
          '-w',
          '${tmp.path}/link-text.txt',
        ]);
        git(repo, ['update-index', '--cacheinfo', '120000,$oid,$specA']);
        git(repo, ['commit', '-q', '-m', 'chore: spec a becomes a link']);
        archive(repo, ['add-x']);
        // staged by plumbing: `git add` keeps a link's mode where
        // core.symlinks is false
        final synced = git(repo, ['hash-object', '-w', '$repo/$specA']);
        git(repo, ['update-index', '--cacheinfo', '100644,$synced,$specA']);
        commitAll(repo, 'chore(add-x): archive change');
        expect(
          git(repo, [
            'diff-tree',
            '-r',
            '--no-commit-id',
            '--name-status',
            'HEAD',
          ]),
          contains('T\t$specA'),
          reason: 'the archive commit changes the type of the spec',
        );
        await refused(repo, 'unsupported_entry', says: [specA]);
      }, skip: skip);

      test('a tag named like the archive branch does not make a read '
          'ambiguous', () async {
        final repo = branchRepo();
        final a = archive(repo, ['add-x'], commitIt: true)!;
        git(repo, ['checkout', '-q', 'main']);
        // another commit under the branch's short name, as a tag
        git(repo, ['tag', 'feat/x', 'main']);
        final r = await plan(rq(repo, branch: 'feat/x'));
        expect(r.code, 0, reason: '${r.doc}');
        expect(r.doc['archive_commit'], a);
      }, skip: skip);

      test('a failed lookup of the archive branch is vcs_error, not '
          'no_archive', () async {
        final repo = branchRepo();
        archive(repo, ['add-x'], commitIt: true);
        git(repo, ['checkout', '-q', 'main']);
        // Git ignores the broken ref with a warning, which the lookup reads
        // as a failure
        File('$repo/.git/refs/heads/feat/x').writeAsStringSync('garbage\n');
        await refused(repo, 'vcs_error', branch: 'feat/x');
      }, skip: skip);

      test('a resume under a git older than 2.40 is tool_too_old, and a plan '
          'that does not resume is not', () async {
        final repo = branchRepo();
        archive(repo, ['add-x'], commitIt: true);
        git(repo, ['checkout', '-q', 'main']);
        final old = FinishContext(
          runner: (cwd, command, env) async => command.last == 'version'
              ? ToolResult(
                  0,
                  Uint8List.fromList(
                    utf8.encode('git version 2.39.1.windows.1\n'),
                  ),
                  Uint8List(0),
                )
              : await runTool(cwd, command, environment: env),
        );
        await refused(
          repo,
          'tool_too_old',
          branch: 'feat/x',
          ctx: old,
          says: ['git check-attr --source', '2.40', '2.39.1'],
        );
        git(repo, ['checkout', '-q', 'feat/x']);
        expect((await plan(rq(repo), old)).code, 0);
      }, skip: skip);

      test('a tasks file deleted from the work tree is decided as absent, '
          'not from the committed copy', () async {
        final repo = branchRepo();
        makeChange(
          repo,
          'add-y',
          verdict: 'APPROVE',
          deltas: {'b': 'B thing'},
          tasks: pending,
        );
        archive(repo, ['add-x', 'add-y'], commitIt: true);
        File('$repo/$tasksOfY').deleteSync();
        expect(git(repo, ['show', 'HEAD:$tasksOfY']), contains('[user]'));
        final doc = await ok(repo);
        expect(member(doc, 'add-y')['waiting_on_user'], <String>[]);
        expect(
          argvsOf(doc['after_rerun_steps']),
          contains(equals(['openspec', 'archive', 'add-y', '--yes'])),
        );
      }, skip: skip);

      test('a member deferred after its archive commit is restored and not '
          'archived again', () async {
        final repo = branchRepo();
        makeChange(repo, 'add-y', verdict: 'APPROVE', deltas: {'b': 'B thing'});
        makeChange(repo, 'add-z', verdict: 'APPROVE', deltas: {'a': 'Z thing'});
        archive(repo, ['add-x', 'add-y', 'add-z'], commitIt: true);
        put(
          repo,
          'openspec/changes/archive/$_date-add-y/review.md',
          '# Review\n\nVERDICT: DEFERRED\n',
        );
        final doc = await ok(repo);
        expect(member(doc, 'add-y')['deferred'], isTrue);
        expect(member(doc, 'add-z')['deferred'], isFalse);
        expect(
          argvsOf(doc['after_rerun_steps']),
          containsAllInOrder([
            ['openspec', 'archive', 'add-z', '--yes'],
          ]),
        );
      }, skip: skip);

      test(
        'a dangling link at a decision file is vcs_error, not absence',
        () async {
          final repo = branchRepo();
          archive(repo, ['add-x'], commitIt: true);
          File('$repo/$tasksPath').deleteSync();
          try {
            Link('$repo/$tasksPath').createSync('missing-target.md');
          } on FileSystemException {
            markTestSkipped(
              'platform: this account cannot create symbolic links',
            );
            return;
          }
          await refused(repo, 'vcs_error', says: ['tasks.md']);
        },
        skip: skip,
      );

      test('an unreadable work-tree tasks file is vcs_error', () async {
        final repo = branchRepo();
        archive(repo, ['add-x'], commitIt: true);
        final file = '$repo/$tasksPath';
        Process.runSync('chmod', ['000', file]);
        addTearDown(() => Process.runSync('chmod', ['644', file]));
        if (Process.runSync('sh', [
              '-c',
              'cat "$file" >/dev/null 2>&1',
            ]).exitCode ==
            0) {
          markTestSkipped('platform: this account reads every file');
          return;
        }
        await refused(repo, 'vcs_error', says: ['tasks.md']);
      }, skip: Platform.isWindows ? 'platform: no POSIX permissions' : skip);

      test(
        'a rerun delta that only the work-tree copy holds is re-deleted',
        () async {
          final repo = makeRepo();
          git(repo, ['checkout', '-q', '-b', 'feat/x']);
          makeChange(repo, 'add-x', deltas: {'a': 'A thing', 'c': 'C thing'});
          makeChange(
            repo,
            'add-y',
            verdict: 'APPROVE',
            deltas: {'b': 'B thing'},
          );
          archive(repo, ['add-x', 'add-y'], commitIt: true);
          File('$repo/openspec/specs/c/spec.md').deleteSync();
          commitAll(repo, 'drop c');
          put(
            repo,
            'openspec/changes/archive/$_date-add-y/specs/c/spec.md',
            deltaText('C more'),
          );
          final doc = await ok(repo);
          expect(
            argvsOf(doc['after_rerun_steps']),
            contains(
              equals(
                undoStep(topOf(repo), ['remove', 'openspec/specs/c/spec.md']),
              ),
            ),
          );
        },
        skip: skip,
      );

      test(
        'members whose names differ only by case are duplicate_member',
        () async {
          final repo = makeRepo();
          git(repo, ['checkout', '-q', '-b', 'feat/x']);
          for (final dir in ['$_date-add-x', '2026-10-18-Add-X']) {
            put(
              repo,
              'openspec/changes/archive/$dir/review.md',
              '# R\n\nVERDICT: DEFERRED\n',
            );
          }
          commitAll(repo, 'chore(add-x): archive change');
          final doc = await refused(repo, 'duplicate_member');
          expect(doc['archived_names'], ['$_date-add-x', '2026-10-18-Add-X']);
        },
        skip: skip,
      );

      test('members that sigma and final sigma tell apart only by upper case '
          'are duplicate_member', () async {
        final probe = Directory('${tmp.path}/probe-σ')..createSync();
        if (!Directory('${tmp.path}/probe-ς').existsSync()) {
          probe.deleteSync();
          markTestSkipped('platform: this volume is case-sensitive');
          return;
        }
        final repo = makeRepo();
        git(repo, ['checkout', '-q', '-b', 'feat/x']);
        for (final dir in ['2026-10-18-add-σ', '2026-10-19-add-ς']) {
          put(
            repo,
            'openspec/changes/archive/$dir/review.md',
            '# R\n\nVERDICT: DEFERRED\n',
          );
        }
        commitAll(repo, 'chore(add): archive change');
        final r = await plan(
          request(
            repo,
            change: 'add-σ',
            archived: '2026-10-18-add-σ',
            prefix: 'openspec',
          ),
        );
        expect(r.code, 1, reason: '${r.doc}');
        expect(r.doc['error'], 'duplicate_member');
        expect(r.doc['archived_names'], [
          '2026-10-18-add-σ',
          '2026-10-19-add-ς',
        ]);
      }, skip: skip);

      test(
        'a task file hidden by an index flag is git_env naming it',
        () async {
          final repo = branchRepo();
          makeChange(
            repo,
            'add-y',
            verdict: 'APPROVE',
            deltas: {'b': 'B thing'},
            tasks: pending,
          );
          archive(repo, ['add-x', 'add-y'], commitIt: true);
          git(repo, ['update-index', '--skip-worktree', tasksOfY]);
          File('$repo/$tasksOfY').deleteSync();
          expect(git(repo, ['status', '--porcelain']), '');
          await refused(repo, 'git_env', says: [tasksOfY]);
        },
        skip: skip,
      );

      for (final resume in [false, true]) {
        test('a gitlink under an archived member is unsupported_entry '
            '(${resume ? 'on resume' : 'on the current branch'})', () async {
          final repo = branchRepo();
          archive(repo, ['add-x'], commitIt: true);
          const sub = '$ad/specs/sub';
          Directory('$repo/$sub').createSync(recursive: true);
          git(repo, [
            'update-index',
            '--add',
            '--cacheinfo',
            '160000,${_headOf(repo, 'feat/x')},$sub',
          ]);
          git(repo, ['commit', '-q', '-m', 'chore: a submodule in the member']);
          expect(
            git(repo, ['ls-tree', '-r', 'feat/x', '--', ad]),
            contains('160000 commit'),
          );
          if (resume) git(repo, ['checkout', '-q', 'main']);
          expect(git(repo, ['status', '--porcelain']), '');
          await refused(
            repo,
            'unsupported_entry',
            branch: resume ? 'feat/x' : null,
            says: [sub],
          );
        }, skip: skip);
      }

      test('GIT_ATTR_SOURCE and attr.tree are git_env at planning', () async {
        final repo = branchRepo();
        archive(repo, ['add-x'], commitIt: true);
        await refused(
          repo,
          'git_env',
          ctx: context(
            environment: {...Platform.environment, 'GIT_ATTR_SOURCE': 'HEAD'},
          ),
          says: ['GIT_ATTR_SOURCE'],
        );
        git(repo, ['config', 'attr.tree', 'HEAD']);
        await refused(repo, 'git_env', says: ['attr.tree']);
      }, skip: skip);

      test('a resume emits one attribute guard per member right before the '
          'checkout', () async {
        final repo = attrRepo('tasks.md text\n', bulk: true);
        final a = _headOf(repo, 'feat/x');
        final doc = await ok(repo, branch: 'feat/x');
        final steps = argvsOf(doc['steps']);
        final top = topOf(repo);
        final guards = [
          for (final m in ['add-x', 'add-y'])
            undoStep(top, [
              'check',
              'attributes',
              a,
              '--',
              'openspec/changes/archive/$_date-$m/review.md',
              'openspec/changes/archive/$_date-$m/tasks.md',
            ]),
        ];
        final checkout = steps.indexWhere(
          (s) => s.length > 3 && s[3] == 'checkout',
        );
        expect(checkout, greaterThan(0));
        expect(steps.sublist(checkout - 2, checkout), guards);
        expect(
          indexOfStep(
            steps,
            undoStep(top, ['check', 'tip', 'refs/heads/feat/x', a]),
          ),
          lessThan(checkout - 2),
        );
      }, skip: skip);

      test('the plan warns not to edit files after it is printed', () async {
        final repo = branchRepo();
        archive(repo, ['add-x'], commitIt: true);
        final doc = await ok(repo);
        final warnings = (doc['warnings']! as List).cast<String>();
        expect(
          warnings,
          contains(
            'Do not edit files after this plan is printed, and do not start a '
            'merge, cherry-pick, revert or rebase while the steps run.',
          ),
        );
        expect(
          warnings.where((w) => w.contains('Do not edit files')),
          hasLength(1),
        );
      }, skip: skip);
    });

    group('GitButler', () {
      FinishContext gbCtx({bool applied = true}) => readerCtx(
        (top, code, branch) async => {
          'ok': true,
          'backend': 'gitbutler',
          'main': 'main',
          'branch': applied ? 'feat/x' : '',
          'applied': applied,
        },
      );

      test('--branch is required', () async {
        final repo = branchRepo();
        archive(repo, ['add-x'], commitIt: true);
        final r = await plan(rq(repo), gbCtx());
        expect(r.code, 2);
        expect(r.doc, {
          'ok': false,
          'error': 'usage',
          'message':
              '--branch is required on GitButler: HEAD is the '
              'workspace commit, not the change branch',
        });
      }, skip: skip);

      test('the branch must be applied', () async {
        final repo = branchRepo();
        archive(repo, ['add-x'], commitIt: true);
        final r = await plan(rq(repo, branch: 'feat/x'), gbCtx(applied: false));
        expect(r.code, 1);
        expect(r.doc, {
          'ok': false,
          'error': 'branch_not_applied',
          'message':
              'feat/x is not applied in the GitButler workspace; '
              'Specwright never applies one (it can conflict with the other '
              'branches): apply it yourself, then plan again',
          'branch': 'feat/x',
        });
      }, skip: skip);

      test('a branch that is no local branch is bad_ref', () async {
        final repo = branchRepo();
        archive(repo, ['add-x'], commitIt: true);
        final r = await plan(request(repo, branch: 'ghost'), gbCtx());
        expect(r.code, 1);
        expect(r.doc['error'], 'bad_ref');
        expect(r.doc['message'], 'ghost is not a local branch');
      }, skip: skip);

      test(
        'the committed plan guards through vcs.sh and commits through it',
        () async {
          final repo = branchRepo();
          final a = archive(repo, ['add-x'], commitIt: true)!;
          final top = topOf(repo);
          final backup = backupOf(repo);
          final doc = (await plan(rq(repo, branch: 'feat/x'), gbCtx())).doc;
          expect(doc['ok'], true);
          final touched = [ad, 'openspec/changes/add-x', specA];
          List<String> u(List<String> rest) => undoStep(top, rest);
          expect(
            argvsOf(doc['steps']),
            containsAllInOrder([
              u(['check', 'branch', 'feat/x', '--backend', 'gitbutler']),
              u(['check', 'tip', 'refs/heads/feat/x', a]),
              u([
                'check',
                'unchanged',
                a,
                '--message',
                'another applied branch changes a path the undo restores',
                '--',
                ...touched,
              ]),
              u(['check', 'clean', '--', ...touched]),
              u(['check', 'absent', backup]),
              u([
                'mkdir',
                '$backup/amended/openspec/specs/a',
                '$backup/base/openspec/specs/a',
              ]),
              u(['write-blob', a, specA, '$backup/base/$specA']),
              u(['copy', specA, '$backup/amended/$specA']),
              u(['move', ad, 'openspec/changes/add-x']),
              u(['write-blob', '$a^', specA, specA]),
              u([
                'write-text',
                '$backup/commit-message.txt',
                'feat(add-x): undo archive of add-x',
              ]),
              swStep(top, [
                'vcs',
                'commit',
                '--repo',
                top,
                '--role',
                'code',
                '--branch',
                'feat/x',
                '--message-file',
                '$backup/commit-message.txt',
                '--',
                '$ad/',
                'openspec/changes/add-x/',
                specA,
              ]),
            ]),
          );
          final warnings = (doc['warnings']! as List).cast<String>();
          expect(
            warnings[1],
            startsWith(
              'The steps move and rewrite files in the shared GitButler',
            ),
          );
          expect(warnings[1], contains('(`but commit -b feat/x`)'));
          expect(doc['after_rerun_steps'], <Object?>[]);
          expect(
            argvsOf(doc['steps'])
                .expand((s) => s)
                .any((x) => x.contains('vcs.sh') || x == 'bash'),
            isFalse,
          );
        },
        skip: skip,
      );

      test('the branch guard is a check step on the named branch', () async {
        final repo = branchRepo();
        archive(repo, ['add-x'], commitIt: true);
        final doc = (await plan(rq(repo, branch: 'feat/x'), gbCtx())).doc;
        expect(
          argvsOf(doc['steps']).first,
          undoStep(topOf(repo), [
            'check',
            'branch',
            'feat/x',
            '--backend',
            'gitbutler',
          ]),
        );
      }, skip: skip);

      test(
        'the uncommitted plan has no commit step and no status guard',
        () async {
          final repo = branchRepo();
          archive(repo, ['add-x']);
          final doc = (await plan(rq(repo, branch: 'feat/x'), gbCtx())).doc;
          final flat = argvsOf(doc['steps']).expand((s) => s).toList();
          expect(flat, isNot(contains('clean')));
          expect(flat, isNot(contains('commit')));
          expect(
            argvsOf(doc['steps']),
            hasStep(
              undoStep(topOf(repo), [
                'write-blob',
                git(repo, ['rev-parse', 'HEAD']),
                specA,
                specA,
              ]),
            ),
          );
        },
        skip: skip,
      );

      /// The GitButler state read, with the assigned paths of other branches
      /// answered by [foreign].
      FinishContext gbForeign(
        List<(String, String)> foreign, {
        Map<String, String>? environment,
        bool? windows,
        Future<ToolResult> Function(String, List<String>, Map<String, String>)?
        runner,
      }) => FinishContext(
        environment: environment,
        windows: windows,
        runner: runner,
        foreignReader: (top, branch) async => foreign,
        stateReader: (top, code, branch) async => {
          'ok': true,
          'backend': 'gitbutler',
          'main': 'main',
          'branch': 'feat/x',
          'applied': true,
          'dirty_paths': <String>[],
        },
      );

      test(
        'the destination check runs on GitButler, naming the branch',
        () async {
          final repo = branchRepo();
          archive(repo, ['add-x'], commitIt: true);
          final top = topOf(repo);
          final doc = (await plan(
            rq(repo, branch: 'feat/x'),
            gbForeign([]),
          )).doc;
          expect(
            argvsOf(doc['steps']),
            containsAllInOrder([
              undoStep(top, [
                'check',
                'destinations',
                '--gitbutler',
                'feat/x',
                '--member',
                ad,
                '--dir',
                'openspec/changes/add-x',
              ]),
              undoStep(top, [
                'check',
                'destinations',
                '--gitbutler',
                'feat/x',
                '--',
                specA,
              ]),
            ]),
          );
        },
        skip: skip,
      );

      for (final (name, path) in [
        ('a spec the undo writes', specA),
        ('a file under a member directory', '$ad/design.md'),
        ('a file under the restore directory', 'openspec/changes/add-x/n.md'),
      ]) {
        test(
          "another applied branch's edit to $name is path_owned_elsewhere",
          () async {
            final repo = branchRepo();
            archive(repo, ['add-x'], commitIt: true);
            final r = await plan(
              rq(repo, branch: 'feat/x'),
              gbForeign([(path, 'other')]),
            );
            expect(r.code, 1, reason: '${r.doc}');
            expect(r.doc['error'], 'path_owned_elsewhere');
            expect(r.doc['path'], path);
            expect(r.doc['branch'], 'other');
          },
          skip: skip,
        );
      }

      test(
        'an edit of another branch elsewhere does not stop the plan',
        () async {
          final repo = branchRepo();
          archive(repo, ['add-x'], commitIt: true);
          final r = await plan(
            rq(repo, branch: 'feat/x'),
            gbForeign([('src/unrelated.txt', 'other')]),
          );
          expect(r.code, 0, reason: '${r.doc}');
        },
        skip: skip,
      );

      test('a committed undo refuses a path its commit would refuse', () async {
        final repo = branchRepo(deltas: {'a[1]': 'New thing'});
        archive(repo, ['add-x'], commitIt: true);
        final r = await plan(rq(repo, branch: 'feat/x'), gbForeign([]));
        expect(r.code, 1, reason: '${r.doc}');
        expect(r.doc['error'], 'bad_path');
        expect(r.doc['path'], 'openspec/specs/a[1]/spec.md');
      }, skip: skip);

      test('an uncommitted undo has no commit, so no bad_path (C30)', () async {
        final repo = branchRepo(deltas: {'a[1]': 'New thing'});
        archive(repo, ['add-x']);
        final r = await plan(rq(repo, branch: 'feat/x'), gbForeign([]));
        expect(r.code, 0, reason: '${r.doc}');
      }, skip: skip);

      test(
        'windows: but.cmd payload over 8,191 is plan_too_large',
        () async {
          final caps = {
            for (var i = 0; i < 90; i++)
              'c${i.toString().padLeft(3, '0')}${'q' * 100}': 'Thing $i',
          };
          final repo = branchRepo(deltas: caps);
          archive(repo, ['add-x'], commitIt: true);
          // a `but.cmd` is the only `but` on this PATH, so the planner sizes the
          // line `but commit` runs as a batch line
          final bin = Directory('${tmp.path}/bin')..createSync();
          File('${bin.path}/but.cmd').writeAsStringSync('@echo off\n');
          final r = await plan(
            rq(repo, branch: 'feat/x'),
            gbForeign(
              [],
              windows: true,
              environment: {'PATH': '${bin.path}/', 'PATHEXT': '.CMD'},
              runner: (cwd, command, env) => runTool(cwd, command),
            ),
          );
          expect(r.code, 1, reason: '${r.doc}');
          expect(r.doc['error'], 'plan_too_large');
          expect(r.doc['message'], contains('8191'));
          // the same undo with a `but.exe` has no batch line to size
          File('${bin.path}/but.cmd').deleteSync();
          final exe = await plan(
            rq(repo, branch: 'feat/x'),
            gbForeign(
              [],
              windows: true,
              environment: {'PATH': '${bin.path}/', 'PATHEXT': '.CMD'},
              runner: (cwd, command, env) => runTool(cwd, command),
            ),
          );
          expect(exe.code, 0, reason: '${exe.doc}');
        },
        skip: Platform.isWindows
            ? skip
            : 'platform: a but.cmd batch line is Windows only',
      );
    });

    group('jj', () {
      /// A context whose state read is [read] and whose `jj` reads answer one
      /// bookmark, conflicted or not; every other command runs for real.
      FinishContext jjCtx(
        Future<Map<String, Object?>> Function(String, String?, String?) read, {
        bool conflict = false,
        String bookmark = 'feat/x',
        List<List<String>>? seen,
        bool? windows,
        Map<String, String>? environment,
      }) => FinishContext(
        windows: windows,
        environment: environment,
        stateReader: read,
        runner: (cwd, command, env) async {
          if (command.first != 'jj') {
            return runTool(cwd, command, environment: env);
          }
          seen?.add(command);
          final line = jsonEncode({
            'name': bookmark,
            'conflict': conflict,
            'target': [null],
          });
          return ToolResult(
            0,
            utf8.encode('$line${String.fromCharCode(10)}'),
            Uint8List(0),
          );
        },
      );

      Future<Map<String, Object?>> Function(String, String?, String?) reader({
        List<String> dirty = const [],
        List<Map<String, Object?>> entries = const [],
        String current = 'feat/x',
      }) =>
          (top, code, branch) async => {
            'ok': true,
            'backend': 'jj',
            'main': 'main',
            'branch': current,
            'dirty_paths': dirty,
            'dirty': entries,
          };

      test('the branch guard is a check step on the planned branch', () async {
        final repo = branchRepo();
        archive(repo, ['add-x'], commitIt: true);
        final doc = (await plan(rq(repo), jjCtx(reader()))).doc;
        expect(
          argvsOf(doc['steps']).first,
          undoStep(topOf(repo), [
            'check',
            'branch',
            'feat/x',
            '--backend',
            'jj',
          ]),
        );
      }, skip: skip);

      test(
        'the committed plan works the working copy and commits with jj',
        () async {
          final repo = branchRepo();
          final a = archive(repo, ['add-x'], commitIt: true)!;
          final top = topOf(repo);
          final backup = backupOf(repo);
          final fileset = [
            for (final f in [ad, 'openspec/changes/add-x', specA]) 'root:"$f"',
          ];
          final fs = fileset.map(sq).join(' ');
          final doc = (await plan(rq(repo), jjCtx(reader()))).doc;
          List<String> u(List<String> rest) => undoStep(top, rest);
          expect(
            argvsOf(doc['steps']),
            containsAllInOrder([
              u(['check', 'branch', 'feat/x', '--backend', 'jj']),
              u(['check', 'tip', 'HEAD', a]),
              u(['check', 'clean', '--jj', '--', ...fileset]),
              u(['check', 'absent', backup]),
              u([
                'mkdir',
                '$backup/amended/openspec/specs/a',
                '$backup/base/openspec/specs/a',
              ]),
              u(['write-blob', a, specA, '$backup/base/$specA']),
              u(['copy', specA, '$backup/amended/$specA']),
              u(['move', ad, 'openspec/changes/add-x']),
              ['jj', 'restore', '--from', '$a-', 'root:"$specA"'],
              [
                'jj',
                'commit',
                '-m',
                'feat(add-x): undo archive of add-x',
                ...fileset,
              ],
              ['jj', 'bookmark', 'set', 'feat/x', '-r', '@-'],
            ]),
          );
          for (final s in doc['steps']! as List) {
            expect((s as Map)['cwd'], top);
          }
          final warnings = (doc['warnings']! as List).cast<String>();
          expect(
            warnings[1],
            startsWith(
              'If a step fails after the steps began changing the working copy',
            ),
          );
          expect(warnings[1], contains('`jj restore $fs`'));
        },
        skip: skip,
      );

      test(
        '--code is passed to the state read and printed when given',
        () async {
          final repo = branchRepo();
          archive(repo, ['add-x'], commitIt: true);
          Directory('$repo/codedir').createSync();
          String? seenCode;
          final doc = (await plan(
            rq(repo, code: 'codedir'),
            jjCtx((top, code, branch) async {
              seenCode = code;
              return reader()(top, code, branch);
            }),
          )).doc;
          expect(seenCode, 'codedir');
          // the store role is named in the branch check, and the sw steps
          // select the code checkout's project
          final top = topOf(repo);
          final steps = argvsOf(doc['steps']);
          expect(
            steps.first,
            // the project is the first directory with a `.git` at or above
            // the code directory: the repo itself
            swStep(top, [
              'finish',
              'undo-step',
              'check',
              'branch',
              'feat/x',
              '--backend',
              'jj',
              '--code',
              'codedir',
            ]),
          );
        },
        skip: skip,
      );

      test(
        'dirty paths under the touched ones are a warning and carried',
        () async {
          final repo = branchRepo();
          archive(repo, ['add-x'], commitIt: true);
          final doc = (await plan(
            rq(repo),
            jjCtx(reader(dirty: ['$ad/design.md', 'other.txt'])),
          )).doc;
          expect(doc['carried_edits'], ['$ad/design.md']);
          final warnings = (doc['warnings']! as List).cast<String>();
          expect(
            warnings.any(
              (w) => w.startsWith(
                '@ already holds changes under the touched paths',
              ),
            ),
            isTrue,
            reason: '$warnings',
          );
        },
        skip: skip,
      );

      test('another branch needs an empty @', () async {
        final repo = branchRepo();
        archive(repo, ['add-x'], commitIt: true);
        git(repo, ['checkout', '-q', 'main']);
        final dirty = await plan(
          rq(repo, branch: 'feat/x'),
          jjCtx(reader(dirty: ['junk.txt'], current: 'main')),
        );
        expect(dirty.code, 1);
        expect(dirty.doc, {
          'ok': false,
          'error': 'dirty_tree',
          'message':
              'The working copy @ is not empty, so it cannot move onto '
              'feat/x with jj new: junk.txt',
          'files': ['junk.txt'],
        });
        final clean = await plan(
          rq(repo, branch: 'feat/x'),
          jjCtx(reader(current: 'main')),
        );
        expect(clean.code, 0, reason: '${clean.doc}');
        final top = topOf(repo);
        final steps = argvsOf(clean.doc['steps']);
        expect(
          steps,
          containsAllInOrder([
            // the settings and the role branch are checked before anything
            // reads or moves the working copy
            undoStep(top, ['check', 'branch', 'main', '--backend', 'jj']),
            undoStep(top, ['check', 'clean', '--jj']),
            undoStep(top, [
              'check',
              'tip',
              'refs/heads/feat/x',
              _headOf(repo, 'feat/x'),
            ]),
            ['jj', 'new', 'feat/x'],
          ]),
        );
      }, skip: skip);

      test(
        'an uncommitted archive reads the added files from the state',
        () async {
          final repo = branchRepo();
          archive(repo, ['add-x']);
          final doc = (await plan(
            rq(repo),
            jjCtx(
              reader(
                entries: [
                  {'status': 'A', 'path': '$ad/proposal.md'},
                  {'status': 'M', 'path': 'src.txt'},
                ],
              ),
            ),
          )).doc;
          expect(doc['mode'], 'uncommitted');
          final steps = argvsOf(doc['steps']);
          expect(
            steps.any(
              (s) =>
                  s[0] == 'jj' &&
                  s[1] == 'restore' &&
                  s[3] == git(repo, ['rev-parse', 'HEAD']),
            ),
            isTrue,
          );
          expect(steps.any((s) => s[0] == 'jj' && s[1] == 'commit'), isFalse);
        },
        skip: skip,
      );

      test('a conflicted requested bookmark is ambiguous_branch, read by '
          'exact name', () async {
        final repo = branchRepo();
        archive(repo, ['add-x'], commitIt: true);
        final seen = <List<String>>[];
        final r = await plan(
          rq(repo),
          jjCtx(reader(), conflict: true, seen: seen),
        );
        expect(r.code, 1, reason: '${r.doc}');
        expect(r.doc['error'], 'ambiguous_branch');
        expect(seen.single, [
          'jj',
          'bookmark',
          'list',
          exactPattern('feat/x'),
          '-T',
          bookmarkTemplate,
        ]);
      }, skip: skip);

      test('a conflicted bookmark that is not the resume target', () async {
        final repo = branchRepo();
        archive(repo, ['add-x'], commitIt: true);
        final seen = <List<String>>[];
        // `team/feat/x` is conflicted, but the exact-name lookup of `feat/x`
        // does not list it, as jj would not
        final r = await plan(
          rq(repo),
          FinishContext(
            stateReader: reader(),
            runner: (cwd, command, env) async {
              if (command.first != 'jj') {
                return runTool(cwd, command, environment: env);
              }
              seen.add(command);
              final listed = command[3] == exactPattern('team/feat/x');
              final line = jsonEncode({
                'name': 'team/feat/x',
                'conflict': true,
                'target': [null],
              });
              return ToolResult(
                0,
                listed ? utf8.encode('$line\n') : Uint8List(0),
                Uint8List(0),
              );
            },
          ),
        );
        expect(r.code, 0, reason: '${r.doc}');
        expect(seen.single[3], exactPattern('feat/x'));
      }, skip: skip);

      test('the jj bookmark lookup fails', () async {
        final repo = branchRepo();
        archive(repo, ['add-x'], commitIt: true);
        final r = await plan(
          rq(repo),
          FinishContext(
            stateReader: reader(),
            runner: (cwd, command, env) async => command.first == 'jj'
                ? ToolResult(1, Uint8List(0), utf8.encode('boom'))
                : runTool(cwd, command, environment: env),
          ),
        );
        expect(r.code, 1, reason: '${r.doc}');
        expect(r.doc['error'], 'vcs_error');
        expect(r.doc['message'], contains('boom'));
      }, skip: skip);

      test('the destination check runs on jj too', () async {
        final repo = branchRepo();
        archive(repo, ['add-x'], commitIt: true);
        final top = topOf(repo);
        final doc = (await plan(rq(repo), jjCtx(reader()))).doc;
        final steps = argvsOf(doc['steps']);
        expect(
          steps,
          containsAllInOrder([
            undoStep(top, [
              'check',
              'destinations',
              '--member',
              ad,
              '--dir',
              'openspec/changes/add-x',
            ]),
            undoStep(top, ['check', 'destinations', '--', specA]),
          ]),
        );
      }, skip: skip);

      test('a large environment is not counted', () async {
        final repo = branchRepo();
        archive(repo, ['add-x'], commitIt: true);
        // the environment alone passes the 32,766-byte budget, the commit line
        // does not
        final big = {...Platform.environment, 'SW_BIG_ENV': 'x' * 40000};
        final r = await plan(
          rq(repo),
          jjCtx(reader(), windows: false, environment: big),
        );
        expect(r.code, 0, reason: '${r.doc}');
        final commits = [
          for (final s in argvsOf(r.doc['steps']))
            if (s[0] == 'jj' && s[1] == 'commit') s,
        ];
        expect(commits, hasLength(1));
      }, skip: Platform.isWindows ? 'posix: a 40,000-byte variable' : skip);

      test(
        'posix: a jj fileset over 32,766 UTF-8 bytes is plan_too_large',
        () async {
          // 150 two-byte letters per name: the fileset is well over the limit
          // in bytes and well under it in characters
          final caps = {
            for (var i = 0; i < 150; i++)
              'c${i.toString().padLeft(3, '0')}${'\u00e9' * 100}': 'Thing $i',
          };
          final repo = branchRepo(deltas: caps);
          archive(repo, ['add-x'], commitIt: true);
          final r = await plan(rq(repo), jjCtx(reader(), windows: false));
          expect(r.code, 1, reason: '${r.doc}');
          expect(r.doc['error'], 'plan_too_large');
          expect(r.doc['message'], contains('jj commit'));
        },
        skip: skip,
      );

      test('a bookmark that is not a revset symbol is quoted', () async {
        final repo = branchRepo(branch: 'feat/x+y');
        archive(repo, ['add-x'], commitIt: true);
        final doc = (await plan(
          rq(repo),
          jjCtx(reader(current: 'feat/x+y')),
        )).doc;
        expect(
          argvsOf(doc['steps']),
          hasStep(['jj', 'bookmark', 'set', '"feat/x+y"', '-r', '@-']),
        );
      }, skip: skip);
    });

    group('the version check and the project root (ADR 0043)', () {
      FinishContext counting(List<List<String>> calls) => FinishContext(
        runner: (cwd, command, env) async {
          calls.add(command);
          return runTool(cwd, command, environment: env);
        },
      );

      /// The value of the leading `--project` of every step that carries one.
      Set<String> projectsOf(Map<String, Object?> doc) => {
        for (final key in ['steps', 'after_rerun_steps'])
          for (final argv in argvsOf(doc[key]))
            if (argv.length > 2 && argv[1] == '--project') argv[2],
      };

      String physical(String dir) =>
          Directory(dir).resolveSymbolicLinksSync().replaceAll(r'\', '/');

      /// A store on `feat/x` whose archive is committed, and a code checkout.
      (String, String) storeAndCode() {
        final store = branchRepo(name: 'store');
        archive(store, ['add-x'], commitIt: true);
        return (store, makeRepo('code'));
      }

      test('a checkout of another version is sw_mismatch before any Git '
          'read', () async {
        final repo = branchRepo();
        archive(repo, ['add-x'], commitIt: true);
        stamp(repo, '9.9.9');
        final calls = <List<String>>[];
        final r = await plan(rq(repo), counting(calls));
        expect(r.code, 1);
        expect(r.doc['error'], 'sw_mismatch');
        expect(r.doc['message'], contains('9.9.9'));
        expect(r.doc.containsKey('steps'), isFalse);
        expect(calls, isEmpty);
      }, skip: skip);

      test('an empty --code is not_repository, whatever the version '
          'checked', () async {
        final repo = branchRepo();
        stamp(repo, '9.9.9');
        final r = await plan(rq(repo, code: ''));
        expect(r.code, 1);
        expect(r.doc['error'], 'not_repository');
        expect(r.doc.containsKey('steps'), isFalse);
      }, skip: skip);

      test('a missing --code is not_repository, not sw_mismatch', () async {
        final repo = branchRepo();
        stamp(repo, '9.9.9');
        final calls = <List<String>>[];
        final r = await plan(rq(repo, code: 'missing'), counting(calls));
        expect(r.doc['error'], 'not_repository');
        expect(calls, isEmpty);
      }, skip: skip);

      test('an omitted --code in a checkout of another version is '
          'sw_mismatch', () async {
        final repo = branchRepo();
        stamp(repo, '9.9.9');
        final r = await plan(rq(repo));
        expect(r.doc['error'], 'sw_mismatch');
      }, skip: skip);

      test('the code checkout decides the version and every step names its '
          'root', () async {
        final (store, code) = storeAndCode();
        stamp(store, '9.9.9');
        final doc = await ok(store, code: code);
        expect(projectsOf(doc), {physical(code)});
        expect(argvsOf(doc['steps']), isNotEmpty);
      }, skip: skip);

      test('a relative --code starts at the planning root', () async {
        final (store, code) = storeAndCode();
        stamp(store, '9.9.9');
        // `../code` from the store is the code checkout; from this process it
        // names nothing
        final doc = await ok(store, code: '../code');
        expect(projectsOf(doc), {physical(code)});
      }, skip: skip);

      test(
        'only the code checkout being of another version stops the plan',
        () async {
          final (store, code) = storeAndCode();
          stamp(code, '9.9.9');
          final r = await plan(rq(store, code: code));
          expect(r.doc['error'], 'sw_mismatch');
          expect(r.doc['message'], contains('9.9.9'));
        },
        skip: skip,
      );

      test(
        '--project chooses the version, and every step carries it',
        () async {
          final (store, code) = storeAndCode();
          stamp(code, '9.9.9');
          final r = await undoArchivePlan(
            UndoRequest(
              dir: store,
              change: 'add-x',
              archived: '$_date-add-x',
              prefix: 'openspec',
              main: 'main',
              code: code,
              project: store,
            ),
            context(),
          );
          expect(projectsOf(r), {topOf(store)});
        },
        skip: skip,
      );

      group('the archive branch stamp (C36)', () {
        /// A resume from `main` of `feat/x`, whose archive commit is followed
        /// by [change] on that branch.
        String resumable(void Function(String repo) change) {
          final repo = branchRepo();
          archive(repo, ['add-x'], commitIt: true);
          change(repo);
          git(repo, ['checkout', '-q', 'main']);
          return repo;
        }

        test('another committed version is sw_mismatch naming it, with no '
            'steps', () async {
          final repo = resumable((r) {
            stamp(r, '0.0.1');
            commitAll(r, 'chore: another stamp');
          });
          final out = await plan(rq(repo, branch: 'feat/x'));
          expect(out.code, 1, reason: '${out.doc}');
          expect(out.doc['error'], 'sw_mismatch');
          expect(out.doc['message'], contains('0.0.1'));
          expect(out.doc.containsKey('steps'), isFalse);
        }, skip: skip);

        test('a stamp the archive branch deletes is sw_mismatch', () async {
          final repo = resumable((r) {
            File('$r/openspec/.specwright/VERSION').deleteSync();
            commitAll(r, 'chore: drop the stamp');
          });
          final out = await plan(rq(repo, branch: 'feat/x'));
          expect(out.doc['error'], 'sw_mismatch');
          expect(out.doc['message'], contains('absent'));
        }, skip: skip);

        test('a stamp over the limit is refused from its size, without '
            'reading the blob', () async {
          final repo = resumable((r) {});
          final reads = <List<String>>[];
          final ctx = FinishContext(
            runner: (cwd, command, env) async {
              if (command.contains('cat-file') && command.contains('-s')) {
                return ToolResult(
                  0,
                  Uint8List.fromList(utf8.encode('10485760\n')),
                  Uint8List(0),
                );
              }
              // a blob named by its id alone, not by `<tree>:<path>`
              if (command.contains('cat-file') &&
                  command.contains('blob') &&
                  !command.last.contains(':')) {
                reads.add(command);
              }
              return runTool(cwd, command, environment: env);
            },
          );
          final out = await plan(rq(repo, branch: 'feat/x'), ctx);
          expect(out.doc['error'], 'sw_mismatch', reason: '${out.doc}');
          expect(reads, isEmpty);
        }, skip: skip);

        test('a stamp the archive branch keeps still plans', () async {
          final repo = resumable((r) {});
          final doc = await ok(repo, branch: 'feat/x');
          expect(doc['mode'], 'committed');
        }, skip: skip);
      });

      group('a work-tree target that is not a regular file', () {
        test(
          'a settings path that is a directory is vcs_error naming it',
          () async {
            final repo = branchRepo();
            archive(repo, ['add-x'], commitIt: true);
            Directory('$repo/openspec/specwright.yaml').createSync();
            final r = await plan(rq(repo));
            expect(r.code, 1, reason: '${r.doc}');
            expect(r.doc['error'], 'vcs_error');
            expect(r.doc['message'], contains('openspec/specwright.yaml'));
            expect(r.doc.containsKey('steps'), isFalse);
          },
          skip: skip,
        );

        test(
          'a settings link to a FIFO does not block (POSIX)',
          () async {
            if (Platform.isWindows) {
              markTestSkipped('no FIFO on Windows');
              return;
            }
            final repo = branchRepo();
            archive(repo, ['add-x'], commitIt: true);
            Process.runSync('mkfifo', ['${tmp.path}/pipe']);
            Link('$repo/openspec/specwright.yaml')
                .createSync('${tmp.path}/pipe');
            final r = await plan(rq(repo));
            expect(r.doc['error'], 'vcs_error', reason: '${r.doc}');
            expect(r.doc['message'], contains('openspec/specwright.yaml'));
          },
          skip: skip,
          timeout: const Timeout(Duration(seconds: 60)),
        );

        test(
          'a work-tree tasks.md that links to a FIFO does not block '
          '(POSIX)',
          () async {
            if (Platform.isWindows) {
              markTestSkipped('no FIFO on Windows');
              return;
            }
            final repo = branchRepo();
            archive(repo, ['add-x']);
            final tasks =
                '$repo/openspec/changes/archive/$_date-add-x/tasks.md';
            File(tasks).deleteSync();
            Process.runSync('mkfifo', ['${tmp.path}/pipe']);
            Link(tasks).createSync('${tmp.path}/pipe');
            final r = await plan(rq(repo));
            expect(r.code, 1, reason: '${r.doc}');
            expect(r.doc['error'], 'vcs_error');
            expect(r.doc['message'], contains('tasks.md'));
            expect(r.doc.containsKey('steps'), isFalse);
          },
          skip: skip,
          timeout: const Timeout(Duration(seconds: 60)),
        );
      });
    });
  });

  group('DEFERRED_RX (task 3.1)', () {
    test('a line "VERDICT: DEFERRED" with trailing blanks matches', () {
      expect(isDeferredVerdict('VERDICT: DEFERRED'), isTrue);
      expect(isDeferredVerdict('# Review\n\nVERDICT: DEFERRED \t\n'), isTrue);
    });

    test('a CRLF line end and a final CR match', () {
      expect(isDeferredVerdict('a\r\nVERDICT: DEFERRED\r\nb'), isTrue);
      expect(isDeferredVerdict('VERDICT: DEFERRED\r'), isTrue);
    });

    test('a lone CR does not end a line', () {
      expect(isDeferredVerdict('a\rVERDICT: DEFERRED'), isFalse);
      expect(isDeferredVerdict('VERDICT: DEFERRED\rb'), isFalse);
    });

    test('U+2028 and U+2029 do not end a line', () {
      expect(isDeferredVerdict('a\u{2028}VERDICT: DEFERRED'), isFalse);
      expect(isDeferredVerdict('a\u{2029}VERDICT: DEFERRED'), isFalse);
      expect(isDeferredVerdict('VERDICT: DEFERRED\u{2028}'), isFalse);
      expect(isDeferredVerdict('VERDICT: DEFERRED\u{2029}\n'), isFalse);
    });

    test('other text on the line, or two CRs, do not match', () {
      expect(isDeferredVerdict('VERDICT: DEFERRED now'), isFalse);
      expect(isDeferredVerdict(' VERDICT: DEFERRED'), isFalse);
      expect(isDeferredVerdict('VERDICT: DEFERRED\r\r\n'), isFalse);
      expect(isDeferredVerdict('VERDICT: APPROVE'), isFalse);
    });
  });

  group('USER_TASK_RX (task 3.1)', () {
    test('unticked user tasks are listed in file order', () {
      final text =
          '# Tasks\n\n- [ ] 1.1 [user] A\n- [ ] 1.2 do\n'
          '  - [ ] 2.10 [user]\n- [-] 3.1 [user] x\n- [] 4.1 [user]\n';
      expect(waitingOnUser(_b(text)), ['1.1', '2.10', '3.1', '4.1']);
    });

    test('the box is done only for x or X after a Python strip', () {
      final text =
          '- [x] 1.1 [user] a\n- [X] 1.2 [user] b\n- [ x ] 1.3 [user] c\n'
          '- [\u{a0}x\u{3000}] 1.4 [user] d\n- [xx] 1.5 [user] e\n- [y] 1.6 [user] f\n';
      expect(waitingOnUser(_b(text)), ['1.5', '1.6']);
    });

    test('[user] must be followed by a blank or the line end', () {
      expect(waitingOnUser(_b('- [ ] 1.1 [user]')), ['1.1']);
      expect(waitingOnUser(_b('- [ ] 1.1 [user]\r\n')), ['1.1']);
      expect(waitingOnUser(_b('- [ ] 1.1 [user]\t x')), ['1.1']);
      expect(waitingOnUser(_b('- [ ] 1.1 [user]x\n')), isEmpty);
      expect(waitingOnUser(_b('- [ ] 1.1 [users]\n')), isEmpty);
    });

    test('a lone CR or U+2028 does not start a line', () {
      expect(waitingOnUser(_b('a\r- [ ] 1.1 [user] x')), isEmpty);
      expect(waitingOnUser(_b('a\u{2028}- [ ] 1.1 [user] x')), isEmpty);
      expect(waitingOnUser(_b('a\u{2029}- [ ] 1.1 [user] x')), isEmpty);
      expect(waitingOnUser(_b('- [ ] 1.1 [user]\r- [ ] 1.2 [user]')), isEmpty);
      expect(waitingOnUser(_b('a\n- [ ] 1.1 [user] x')), ['1.1']);
    });

    test('the box cannot span a CR or newline', () {
      expect(waitingOnUser(_b('- [ \r] 1.1 [user]')), isEmpty);
      expect(waitingOnUser(_b('- [ \n] 1.1 [user]')), isEmpty);
    });

    test('ids are ASCII digits only', () {
      expect(
        waitingOnUser(_b('- [ ] \u{661}.\u{661} [user] Check it')),
        isEmpty,
      );
      expect(waitingOnUser(_b('- [ ] \u{ff11}.\u{ff11} [user] x')), isEmpty);
      expect(waitingOnUser(_b('- [ ] 1.\u{661} [user] x')), isEmpty);
    });

    test('no tasks.md is no waiting task', () {
      expect(waitingOnUser(null), isEmpty);
      expect(waitingOnUser(const <int>[]), isEmpty);
    });

    test('invalid UTF-8 is replaced, not an error', () {
      expect(waitingOnUser([0xff, 0x0a, ..._b('- [ ] 1.1 [user]')]), ['1.1']);
    });
  });

  group('DATE_RX (task 3.1)', () {
    test('a leading ASCII date and dash is removed, once', () {
      expect(stripDatePrefix('2026-01-01-x'), 'x');
      expect(stripDatePrefix('2026-01-01-2026-01-01-x'), '2026-01-01-x');
      expect(stripDatePrefix('2026-01-01-'), '');
    });

    test('anything else is left alone', () {
      expect(stripDatePrefix('x-2026-01-01-y'), 'x-2026-01-01-y');
      expect(stripDatePrefix('2026-1-01-x'), '2026-1-01-x');
      expect(stripDatePrefix('2026-01-01x'), '2026-01-01x');
      expect(stripDatePrefix('\n2026-01-01-x'), '\n2026-01-01-x');
    });

    test('non-ASCII digits are not a date', () {
      expect(
        stripDatePrefix(
          '\u{662}\u{660}\u{662}\u{666}-\u{660}\u{661}-\u{660}\u{661}-x',
        ),
        '\u{662}\u{660}\u{662}\u{666}-\u{660}\u{661}-\u{660}\u{661}-x',
      );
    });
  });

  group('sorted() by code point (task 3.1)', () {
    test('a name above U+FFFF sorts after one in U+E000-U+FFFF', () {
      expect(sortedByCodePoint(['\u{10000}a', '\u{e000}a', '\u{ffff}a']), [
        '\u{e000}a',
        '\u{ffff}a',
        '\u{10000}a',
      ]);
      expect(compareCodePoints('\u{10000}', '\u{ffff}') > 0, isTrue);
      expect(compareCodePoints('\u{ffff}', '\u{10000}') < 0, isTrue);
    });

    test('an escaped byte (U+DC80) sorts as the code point it is', () {
      expect(sortedByCodePoint(['\u{10000}', '\udc80', '\u{e000}', 'a']), [
        'a',
        '\udc80',
        '\u{e000}',
        '\u{10000}',
      ]);
    });

    test('a prefix sorts first and equal strings compare 0', () {
      expect(sortedByCodePoint(['ab', 'a', 'B', 'b']), ['B', 'a', 'ab', 'b']);
      expect(compareCodePoints('x', 'x'), 0);
    });

    test('the input is not changed and duplicates are kept', () {
      final input = ['b', 'a', 'b'];
      expect(sortedByCodePoint(input), ['a', 'b', 'b']);
      expect(input, ['b', 'a', 'b']);
    });
  });
}
