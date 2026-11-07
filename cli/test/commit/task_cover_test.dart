import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:specwright_cli/src/commit/context.dart';
import 'package:specwright_cli/src/commit/paths.dart';
import 'package:specwright_cli/src/commit/task_cover.dart';
import 'package:specwright_cli/src/vcs/document.dart';
import 'package:specwright_cli/src/vcs/tool_runner.dart';
import 'package:test/test.dart';

import '../vcs/bash_support.dart';

const String _usage =
    'task-cover.sh --repo <dir> --range <a>..<b> --tasks <tasks.md> '
    '--change <name> [--rev <sha>] [--code <dir>]';

void main() {
  group('pySplitLines', () {
    test('splits on every str.splitlines boundary', () {
      expect(
        pySplitLines('a\nb\rc\r\nd\ve\ff\x1cg\x1dh\x1ei\x85j\u2028k\u2029l'),
        ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l'],
      );
    });

    test('\\x1f and U+3000 are not boundaries', () {
      expect(pySplitLines('a\x1fb\u3000c'), ['a\x1fb\u3000c']);
    });

    test('a final terminator adds no empty line, and CRLF is one', () {
      expect(pySplitLines('a\r\n'), ['a']);
      expect(pySplitLines('a\n\nb\n'), ['a', '', 'b']);
      expect(pySplitLines(''), isEmpty);
      expect(pySplitLines('\r\n\r\n'), ['', '']);
    });
  });

  group('parseTasks', () {
    List<String> ids(String text) => [
      for (final t in parseTasks(text).tasks) t.id,
    ];

    test('every splitlines boundary ends a task line', () {
      expect(
        ids(
          '- [x] 1.1 a\v- [x] 1.2 b\f- [x] 1.3 c\x1c- [x] 1.4 d\x1d'
          '- [x] 1.5 e\x1e- [x] 1.6 f\x85- [x] 1.7 g\u2028- [x] 1.8 h\u2029'
          '- [x] 1.9 i\r- [x] 1.10 j\r\n- [x] 1.11 k',
        ),
        [
          for (final n in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]) '1.$n',
        ],
      );
    });

    test('str.isspace whitespace follows the id and fills the lookahead', () {
      expect(ids('- [x] 1.1\u3000Do it'), ['1.1']);
      expect(ids('- [x] 1.2\x1fDo it'), ['1.2']);
      expect(ids('- [x] 1.3\u00a0Do it'), ['1.3']);
      expect(ids('- [x] 1.4\u2003Do it'), ['1.4']);
      expect(ids('- [x] 1.5'), ['1.5']);
    });

    test('U+FEFF is not whitespace', () {
      expect(ids('- [x] 1.1\ufeffDo it'), isEmpty);
      expect(ids('- [x] 1.1x'), isEmpty);
    });

    test('strip removes the str.isspace set from the box', () {
      bool ticked(String box) =>
          parseTasks('- [$box] 1.1 a').tasks.single.ticked;
      expect(ticked('x'), isTrue);
      expect(ticked('X'), isTrue);
      expect(ticked(' x '), isTrue);
      expect(ticked('\u3000x\u3000'), isTrue);
      expect(ticked('\x1fx'), isTrue);
      expect(ticked('\ufeffx'), isFalse);
    });

    test('the box rule: only x, any case and spacing, is done', () {
      bool ticked(String box) =>
          parseTasks('- [$box] 1.1 a').tasks.single.ticked;
      expect(ticked(''), isFalse);
      expect(ticked(' '), isFalse);
      expect(ticked('xx'), isFalse);
      expect(ticked('-'), isFalse);
      expect(ticked('~'), isFalse);
      expect(ticked('x '), isTrue);
    });

    test('indentation, tabs and CRLF are tolerated', () {
      expect(ids('  \t- \t[x]\t1.1\ta\r\n- [ ] 1.2 b\r\n'), ['1.1', '1.2']);
      expect(ids('-[x] 1.1 a'), isEmpty);
      expect(ids('- [x]1.1 a'), isEmpty);
      expect(ids('* [x] 1.1 a'), isEmpty);
    });

    test('markers: the first token after the id, lowercase only', () {
      String kind(String rest) =>
          parseTasks('- [x] 1.1 $rest').tasks.single.kind;
      expect(kind('[user] do'), 'user');
      expect(kind('[evidence] do'), 'evidence');
      expect(kind('[user]'), 'user');
      expect(kind('[user]\tdo'), 'user');
      expect(kind('[User] do'), 'agent');
      expect(kind('[user]x do'), 'agent');
      expect(kind('do [user]'), 'agent');
      expect(kind('\u3000[user] do'), 'agent');
      expect(kind('[other] do'), 'agent');
    });

    test('headings: first wins, text trimmed of blanks, id as an integer', () {
      final parsed = parseTasks(
        '## 1. First one  \t\n## 1. Second\n##\t2.\tTwo\n## 3.Missing\n'
        '## 4. \n###  5. Deep\n## 07. Seven\n',
      );
      expect(
        {for (final e in parsed.headings.entries) '${e.key}': e.value},
        {'1': 'First one', '2': 'Two', '7': 'Seven'},
      );
    });

    test('a heading line is never also a task', () {
      expect(ids('## 1. - [x] 1.1 a'), isEmpty);
    });

    test('group is the integer of the first number', () {
      final t = parseTasks('- [x] 01.2 a\n- [x] 10.1 b').tasks;
      expect(t.map((e) => e.id), ['01.2', '10.1']);
      expect(t.map((e) => e.group.toInt()), [1, 10]);
    });

    test('duplicate ids are reported once each, in order', () {
      final parsed = parseTasks(
        '- [x] 1.1 a\n- [x] 1.2 b\n- [ ] 1.1 c\n- [ ] 1.2 d\n- [ ] 1.1 e\n',
      );
      expect(parsed.repeated, ['1.1', '1.2']);
      expect(parseTasks('- [x] 1.1 a\n- [x] 1.2 b').repeated, isEmpty);
    });

    test('the text after the id is kept for the evidence check', () {
      expect(parseTasks('- [x] 1.1 a b').texts['1.1'], ' a b');
    });

    test('non-ASCII digit ids are not tasks', () {
      final parsed = parseTasks(
        '- [x] \u0661.\u0661 Do it\n- [x] 1.\u0661 Do it\n'
        '- [x] \u0661.1 Do it\n## \u0661. Heading\n',
      );
      expect(parsed.tasks, isEmpty);
      expect(parsed.headings, isEmpty);
    });
  });

  group('cutField', () {
    test('keeps 64 Ki code points, not UTF-16 units', () {
      final astral = String.fromCharCode(0x1F600);
      final cut = cutField(astral * 70000);
      expect(cut.runes.length, 65536);
      expect(cut.length, 131072);
      expect(cutField('a' * 65536), 'a' * 65536);
      expect(cutField('a' * 65537), 'a' * 65536);
      expect(cutField('abc'), 'abc');
    });
  });

  group('taskCover', () {
    final bash = findBash();
    late Directory root;
    late Directory dir;
    late String tasksPath;
    late List<int> out;
    late CommitContext ctx;

    setUpAll(() {
      root = Directory(
        '${Directory.systemTemp.path}${Platform.pathSeparator}claude-ncc-g3',
      )..createSync();
    });
    tearDownAll(() {
      if (root.existsSync()) root.deleteSync(recursive: true);
    });
    setUp(() {
      dir = root.createTempSync('t-');
      tasksPath = '${dir.path}${Platform.pathSeparator}tasks.md';
      out = <int>[];
      ctx = CommitContext(
        scriptsDir: '',
        bash: bash ?? 'bash',
        writeOut: out.addAll,
        writeErr: (_) {},
      );
    });

    String text() => utf8.decode(out, allowMalformed: true);
    String line(Map<String, Object?> doc) =>
        utf8.decode(documentBytes(doc, escapeLineSeparators: false));
    Map<String, Object?> json() =>
        jsonDecode(text().trim()) as Map<String, Object?>;

    Future<int> run(
      List<String> args, {
      GitTool? git,
      PathConverter? convert,
      Map<String, String> environment = const {},
    }) => taskCover(
      args,
      ctx,
      git: git,
      convert: convert,
      environment: environment,
    );

    GitTool stub(
      Uint8List Function(List<String> argv, List<List<String>> calls) answer, {
      required List<List<String>> calls,
      int Function(List<String> argv)? exit,
      String Function(List<String> argv)? err,
    }) => (argv) async {
      calls.add(argv);
      return ToolResult(
        exit?.call(argv) ?? 0,
        answer(argv, calls),
        Uint8List.fromList(utf8.encode(err?.call(argv) ?? '')),
      );
    };

    Uint8List bytes(String s) => Uint8List.fromList(utf8.encode(s));
    String sub(List<String> argv) => argv[6];

    List<String> baseArgs({String change = 'demo', String range = 'a..b'}) => [
      '--repo',
      dir.path,
      '--range',
      range,
      '--tasks',
      tasksPath,
      '--change',
      change,
    ];

    test('usage error names --code', () async {
      final code = await run(['--repo', dir.path, '--range', 'a..b']);
      expect(code, 2);
      expect(text(), line({'ok': false, 'error': 'usage', 'message': _usage}));
      expect(text(), contains(' [--rev <sha>] [--code <dir>]"'));
    });

    test(
      'a bare option, an unknown option and an empty value are usage',
      () async {
        for (final args in [
          <String>[],
          ['--repo'],
          [...baseArgs(), '--bogus', 'x'],
          [...baseArgs(), 'stray'],
          ['--repo', '', '--range', 'a..b', '--tasks', 't', '--change', 'c'],
        ]) {
          out.clear();
          expect(await run(args), 2, reason: '$args');
          expect(json()['error'], 'usage', reason: '$args');
        }
      },
    );

    test('--code is accepted and ignored', () async {
      File(tasksPath).writeAsStringSync('- [x] 1.1 a\n');
      final calls = <List<String>>[];
      final git = stub(
        (a, c) => bytes(sub(a) == 'rev-list' ? '0\n' : ''),
        calls: calls,
      );
      expect(await run(baseArgs(), git: git), 0);
      final plain = text();
      out.clear();
      expect(await run([...baseArgs(), '--code', '/nowhere'], git: git), 0);
      expect(text(), plain);
      out.clear();
      expect(await run(['--code', '/x', ...baseArgs()], git: git), 0);
      expect(text(), plain);
    });

    test('bad_path: a failed conversion names the path, exit 2', () async {
      File(tasksPath).writeAsStringSync('- [x] 1.1 a\n');
      final calls = <List<String>>[];
      final git = stub((a, c) => bytes(''), calls: calls);
      Future<String> convert(String p) async {
        if (p == '/tmp/t.md') throw BadPathException(p);
        return p;
      }

      final code = await run(
        [...baseArgs().sublist(0, 4), '--tasks', '/tmp/t.md', '--change', 'c'],
        git: git,
        convert: convert,
      );
      expect(code, 2);
      expect(
        text(),
        line({
          'ok': false,
          'error': 'bad_path',
          'message': 'could not convert path: /tmp/t.md',
        }),
      );
      expect(calls, isEmpty);
      // the repo is converted too
      out.clear();
      expect(
        await run(
          ['--repo', '/tmp/t.md', ...baseArgs().sublist(2)],
          git: git,
          convert: convert,
        ),
        2,
      );
      expect(json()['error'], 'bad_path');
      expect(calls, isEmpty);
    });

    test('a converted path is the one used', () async {
      File(tasksPath).writeAsStringSync('- [x] 1.1 a\n');
      final calls = <List<String>>[];
      final git = stub(
        (a, c) => bytes(sub(a) == 'rev-list' ? '0\n' : ''),
        calls: calls,
      );
      expect(
        await run(
          baseArgs().map((a) => a == tasksPath ? '/virtual/t.md' : a).toList(),
          git: git,
          convert: (p) async => p == '/virtual/t.md' ? tasksPath : p,
        ),
        0,
      );
      expect(json()['ok'], true);
    });

    test('no_tasks and tasks_too_large', () async {
      final calls = <List<String>>[];
      final git = stub(
        (a, c) => bytes(sub(a) == 'rev-list' ? '0\n' : ''),
        calls: calls,
      );
      expect(await run(baseArgs(), git: git), 2);
      expect(
        text(),
        line({
          'ok': false,
          'error': 'no_tasks',
          'message': 'no tasks file: $tasksPath',
        }),
      );
      out.clear();
      File(tasksPath).writeAsBytesSync(Uint8List(1024 * 1024 + 1));
      expect(await run(baseArgs(), git: git), 2);
      expect(
        text(),
        line({
          'ok': false,
          'error': 'tasks_too_large',
          'message': 'tasks.md is over 1 MiB',
        }),
      );
      expect(calls, isEmpty);
      out.clear();
      File(tasksPath).writeAsBytesSync(Uint8List(1024 * 1024));
      expect(await run(baseArgs(), git: git), 0);
    });

    test('duplicate_task_ids names every repeated id', () async {
      File(tasksPath).writeAsStringSync(
        '- [x] 1.1 a\n- [x] 1.2 b\n- [ ] 1.1 c\n- [ ] 1.2 d\n',
      );
      final calls = <List<String>>[];
      final git = stub((a, c) => bytes('0\n'), calls: calls);
      expect(await run(baseArgs(), git: git), 2);
      expect(
        text(),
        line({
          'ok': false,
          'error': 'duplicate_task_ids',
          'message': '$tasksPath repeats task ids: 1.1, 1.2',
        }),
      );
      expect(calls, isEmpty);
    });

    test('non-ASCII digit ids are not tasks', () async {
      File(tasksPath)
          .writeAsStringSync('- [x] \u0661.\u0661 Do it\n- [x] 2.1 Real\n');
      final calls = <List<String>>[];
      final git = stub(
        (a, c) => bytes(sub(a) == 'rev-list' ? '0\n' : ''),
        calls: calls,
      );
      expect(await run(baseArgs(), git: git), 0);
      final doc = json();
      expect((doc['tasks'] as List).map((t) => (t as Map)['id']), ['2.1']);
      expect((doc['groups'] as List).map((g) => (g as Map)['group']), [2]);
    });

    group('the git runner', () {
      test('every call carries the fixed prefix and the repo', () async {
        File(tasksPath).writeAsStringSync('- [x] 1.1 a\n');
        final calls = <List<String>>[];
        final git = stub(
          (a, c) => bytes(sub(a) == 'rev-list' ? '0\n' : ''),
          calls: calls,
        );
        expect(await run(baseArgs(), git: git), 0);
        expect(calls.map(sub), ['rev-list', 'log']);
        for (final argv in calls) {
          expect(argv.sublist(0, 6), [
            'git',
            '--no-replace-objects',
            '-c',
            'log.showSignature=false',
            '-C',
            dir.path,
          ]);
        }
        expect(calls.first.sublist(6), ['rev-list', '--count', 'a..b']);
        expect(calls.last.sublist(6).first, 'log');
        expect(calls.last.last, 'a..b');
      });

      test('a started git that fails is git_failed, exit 3', () async {
        File(tasksPath).writeAsStringSync('- [x] 1.1 a\n');
        final calls = <List<String>>[];
        final git = stub(
          (a, c) => bytes(''),
          calls: calls,
          exit: (a) => 128,
          err: (a) => '  fatal: bad range\n',
        );
        expect(await run(baseArgs(), git: git), 3);
        expect(
          text(),
          line({
            'ok': false,
            'error': 'git_failed',
            'message': 'git rev-list failed: fatal: bad range',
          }),
        );
      });

      test('a failed soft call is null, not a stop', () async {
        File(tasksPath).writeAsStringSync('- [x] 1.1 a\n');
        final calls = <List<String>>[];
        final git = stub(
          (a, c) => bytes(''),
          calls: calls,
          exit: (a) => sub(a) == 'rev-parse' ? 0 : 1,
        );
        // rev-parse works; the soft ls-tree fails: no tasks file at the rev
        final code = await run([...baseArgs(), '--rev', 'abc'], git: git);
        expect(code, 2);
        expect(json()['error'], 'no_tasks');
        expect(calls.map(sub), ['rev-parse', 'ls-tree']);
      });

      test('transport exit 127 stops a hard call', () async {
        File(tasksPath).writeAsStringSync('- [x] 1.1 a\n');
        final git = stub(
          (a, c) => bytes(''),
          calls: [],
          exit: (a) => 127,
          err: (a) => 'bash: line 1: exec: git: not found\n',
        );
        expect(await run(baseArgs(), git: git), 3);
        expect(
          text(),
          line({
            'ok': false,
            'error': 'git_failed',
            'message': 'cannot run git: bash: line 1: exec: git: not found',
          }),
        );
      });

      test('transport exit 127 stops a soft call too', () async {
        File(tasksPath).writeAsStringSync('- [x] 1.1 a\n');
        final calls = <List<String>>[];
        final git = stub(
          (a, c) => bytes(''),
          calls: calls,
          exit: (a) => sub(a) == 'rev-parse' ? 0 : 127,
          err: (a) => 'gone',
        );
        expect(await run([...baseArgs(), '--rev', 'abc'], git: git), 3);
        expect(json()['error'], 'git_failed');
        expect(json()['message'], 'cannot run git: gone');
        expect(calls.map(sub), ['rev-parse', 'ls-tree']);
      });

      test('transport exit 127 on a soft evidence read stops', () async {
        File(tasksPath)
            .writeAsStringSync('- [x] 1.1 [evidence] evidence/a.txt\n');
        final calls = <List<String>>[];
        final git = stub(
          (a, c) => bytes(sub(a) == 'rev-list' ? '0\n' : ''),
          calls: calls,
          exit: (a) => sub(a) == 'ls-files' ? 127 : 0,
          err: (a) => 'no git',
        );
        expect(await run(baseArgs(), git: git), 3);
        expect(json()['message'], 'cannot run git: no git');
      });

      test('the default runner starts git through bash with cwd .', () async {
        // a directory that is not a repo: git runs and fails, exit 3
        File(tasksPath).writeAsStringSync('- [x] 1.1 a\n');
        expect(await run(baseArgs()), 3);
        final doc = json();
        expect(doc['error'], 'git_failed');
        expect(doc['message'], startsWith('git rev-list failed: '));
      }, skip: bash == null ? 'no bash' : null);
    });

    test('an uncaught exception is internal_error, exit 1', () async {
      File(tasksPath).writeAsStringSync('- [x] 1.1 a\n');
      Future<ToolResult> git(List<String> a) async => throw StateError('boom');
      expect(await run(baseArgs(), git: git), 1);
      expect(
        text(),
        line({'ok': false, 'error': 'internal_error', 'message': 'boom'}),
      );
    });

    test('an invalid TASK_COVER_MAX_COMMITS is internal_error', () async {
      File(tasksPath).writeAsStringSync('- [x] 1.1 a\n');
      final git = stub((a, c) => bytes('0\n'), calls: []);
      expect(
        await run(
          baseArgs(),
          git: git,
          environment: {'TASK_COVER_MAX_COMMITS': 'x'},
        ),
        1,
      );
      expect(json()['error'], 'internal_error');
    });

    test('rev-list --count is decoded strictly', () async {
      File(tasksPath).writeAsStringSync('- [x] 1.1 a\n');
      Future<ToolResult> git(List<String> a) async =>
          ToolResult(0, Uint8List.fromList([0x31, 0xff]), Uint8List(0));
      expect(await run(baseArgs(), git: git), 1);
      expect(json()['error'], 'internal_error');
    });

    test('range_too_large honours TASK_COVER_MAX_COMMITS', () async {
      File(tasksPath).writeAsStringSync('- [x] 1.1 a\n');
      final calls = <List<String>>[];
      final git = stub(
        (a, c) => bytes(sub(a) == 'rev-list' ? '3\n' : ''),
        calls: calls,
      );
      expect(
        await run(
          baseArgs(),
          git: git,
          environment: {'TASK_COVER_MAX_COMMITS': '2'},
        ),
        1,
      );
      expect(
        text(),
        line({
          'ok': false,
          'error': 'range_too_large',
          'message': 'range a..b has 3 commits, over the bound of 2',
        }),
      );
      expect(calls.map(sub), ['rev-list']);
      out.clear();
      expect(
        await run(
          baseArgs(),
          git: git,
          environment: {'TASK_COVER_MAX_COMMITS': '3'},
        ),
        0,
      );
      out.clear();
      expect(
        await run(
          baseArgs(),
          git: git,
          environment: {'TASK_COVER_MAX_COMMITS': ''},
        ),
        0,
      );
    });

    test('an odd log token count is git_failed', () async {
      File(tasksPath).writeAsStringSync('- [x] 1.1 a\n');
      final git = stub(
        (a, c) => bytes(sub(a) == 'rev-list' ? '1\n' : 'abc\x00subject\x00'),
        calls: [],
      );
      expect(await run(baseArgs(), git: git), 3);
      expect(
        text(),
        line({
          'ok': false,
          'error': 'git_failed',
          'message': 'unexpected git log output',
        }),
      );
    });

    test('log fields are cut at 64 Ki code points', () async {
      File(tasksPath).writeAsStringSync('- [x] 1.1 a\n');
      final padding = String.fromCharCode(0x1F600) * 65536;
      final git = stub(
        (a, c) => bytes(
          sub(a) == 'rev-list'
              ? '1\n'
              : 'abc\x00feat(demo): task 1.1 x\x00$padding\x00\x00',
        ),
        calls: [],
      );
      expect(await run(baseArgs(), git: git), 0);
      final task = ((json()['tasks'] as List).single as Map);
      expect(task['commits'], [
        {'sha': 'abc', 'form': 'subject'},
      ]);
    });

    test('the change name is matched literally', () async {
      File(tasksPath).writeAsStringSync('- [x] 1.1 a\n- [x] 1.2 b\n');
      final git = stub(
        (a, c) => bytes(
          sub(a) == 'rev-list'
              ? '2\n'
              : 'c1\x00feat(a.b+c): task 1.1 x\x00\x00\x00'
                    'c2\x00feat(aXb+c): task 1.2 x\x00\x00\x00',
        ),
        calls: [],
      );
      expect(await run(baseArgs(change: 'a.b+c'), git: git), 0);
      final tasks = json()['tasks'] as List;
      expect((tasks[0] as Map)['commits'], [
        {'sha': 'c1', 'form': 'subject'},
      ]);
      expect((tasks[1] as Map)['commits'], isEmpty);
    });

    test(
      'non-ASCII text and U+2028 are written raw, with the line end',
      () async {
        File(tasksPath).writeAsStringSync('- [x] 1.1 a\n');
        final git = stub(
          (a, c) => bytes(sub(a) == 'rev-list' ? '0\n' : ''),
          calls: [],
        );
        expect(await run(baseArgs(change: 'caf\u00e9\u2028x'), git: git), 0);
        final raw = utf8.decode(out);
        expect(raw, contains('"change": "caf\u00e9\u2028x"'));
        expect(raw, endsWith(documentLineEnd()));
        expect(raw, startsWith('{"ok": true, "change": '));
      },
    );

    group('with a real repository', () {
      late Directory repo;
      late String tasks;

      String git(List<String> args) {
        final r = Process.runSync(
          'git',
          args,
          workingDirectory: repo.path,
          stdoutEncoding: utf8,
          stderrEncoding: utf8,
        );
        if (r.exitCode != 0) fail('git ${args.join(' ')}: ${r.stderr}');
        return (r.stdout as String).trim();
      }

      void write(String rel, String content) {
        final f = File('${repo.path}/$rel')..parent.createSync(recursive: true);
        f.writeAsStringSync(content);
      }

      void commit(String subject, [String? trailers]) => git([
        'commit',
        '-q',
        '--allow-empty',
        '-m',
        subject,
        if (trailers != null) ...['-m', trailers],
      ]);

      late String base;
      late List<String> shas;

      setUp(() {
        repo = Directory('${dir.path}/repo')..createSync();
        tasks = '${repo.path}/chg/tasks.md';
        git(['init', '-q']);
        git(['config', 'user.name', 'T']);
        git(['config', 'user.email', 't@example.com']);
        git(['config', 'commit.gpgsign', 'false']);
        write(
          'chg/tasks.md',
          '## 1. First\n'
              '- [x] 1.1 Alpha\n'
              '- [x] 1.2 Beta\n'
              '- [ ] 1.3 Gamma\n'
              '## 2. Second\n'
              '- [x] 2.1 [user] Check it\n'
              '- [ ] 2.2 [user] Later\n'
              '- [x] 2.3 [evidence] Write evidence/out.txt.\n'
              '- [x] 2.4 [evidence] no path here\n'
              '- [x] 3.1 Orphan group without heading\n',
        );
        write('chg/evidence/out.txt', 'proof\n');
        git(['add', '-A']);
        commit('chore: base');
        base = git(['rev-parse', 'HEAD']);
        commit('feat(demo): task 1.1 alpha', 'Specwright-Task: 1.2');
        commit('feat(demo): task 1.2 beta again');
        commit(
          'feat(demo): group 2 stuff',
          'Specwright-Task: 1.1\nSpecwright-User-Task: 2.1',
        );
        shas = git(['rev-list', '--reverse', '$base..HEAD']).split('\n');
      });

      List<String> args({String? rev, String range = ''}) => [
        '--repo',
        repo.path,
        '--range',
        range.isEmpty ? '$base..HEAD' : range,
        '--tasks',
        tasks,
        '--change',
        'demo',
        if (rev != null) ...['--rev', rev],
      ];

      Map<String, Object?> expected() {
        Map<String, Object?> task(
          String id,
          int group,
          String kind,
          bool ticked,
          List<List<String>> commits,
        ) => {
          'id': id,
          'group': group,
          'kind': kind,
          'ticked': ticked,
          'commits': [
            for (final c in commits) {'sha': c[0], 'form': c[1]},
          ],
        };
        return {
          'ok': true,
          'change': 'demo',
          'range': '$base..HEAD',
          'tasks': [
            task('1.1', 1, 'agent', true, [
              [shas[2], 'trailer'],
              [shas[0], 'subject'],
            ]),
            task('1.2', 1, 'agent', true, [
              [shas[1], 'subject'],
              [shas[0], 'trailer'],
            ]),
            task('1.3', 1, 'agent', false, []),
            task('2.1', 2, 'user', true, [
              [shas[2], 'user_trailer'],
            ]),
            task('2.2', 2, 'user', false, []),
            task('2.3', 2, 'evidence', true, []),
            task('2.4', 2, 'evidence', true, []),
            task('3.1', 3, 'agent', true, []),
          ],
          'groups': [
            {'group': 1, 'heading': 'First'},
            {'group': 2, 'heading': 'Second'},
            {'group': 3, 'heading': null},
          ],
          'pending_groups': [
            {
              'group': 2,
              'tasks': ['2.3', '2.4'],
            },
            {
              'group': 3,
              'tasks': ['3.1'],
            },
          ],
          'uncovered': ['2.3', '2.4', '3.1'],
          'waiting_on_user': ['2.2'],
          'user_uncommitted': <String>[],
          'evidence_missing': ['2.4'],
          'duplicates': [
            {
              'task': '1.1',
              'commits': [shas[2], shas[0]],
            },
            {
              'task': '1.2',
              'commits': [shas[1], shas[0]],
            },
          ],
          'cross_group': [
            {'sha': shas[2], 'task': '1.1', 'group': 2},
          ],
          'missing_headings': [3],
        };
      }

      test('the whole document, byte for byte', () async {
        expect(await run(args()), 0);
        expect(text(), line(expected()));
      }, skip: bash == null ? 'no bash' : null);

      test('with --rev the document is the same', () async {
        expect(await run(args(rev: 'HEAD')), 0);
        expect(text(), line(expected()));
        // the working tree is ignored at --rev
        out.clear();
        File(tasks).writeAsStringSync('- [x] 9.9 changed\n');
        File('${repo.path}/chg/evidence/out.txt').deleteSync();
        expect(await run(args(rev: 'HEAD')), 0);
        expect(text(), line(expected()));
      }, skip: bash == null ? 'no bash' : null);

      test('evidence comes from the index, not the working tree', () async {
        File('${repo.path}/chg/evidence/out.txt').deleteSync();
        expect(await run(args()), 0);
        expect(json()['evidence_missing'], ['2.4']);
        out.clear();
        git(['rm', '-q', '--cached', 'chg/evidence/out.txt']);
        write('chg/evidence/out.txt', 'untracked but present\n');
        expect(await run(args()), 0);
        expect(json()['evidence_missing'], ['2.3', '2.4']);
        out.clear();
        git(['add', '-f', 'chg/evidence/out.txt']);
        write('chg/evidence/out.txt', '');
        git(['add', '-f', 'chg/evidence/out.txt']);
        expect(await run(args()), 0);
        expect(json()['evidence_missing'], ['2.3', '2.4']);
      }, skip: bash == null ? 'no bash' : null);

      test(
        'evidence paths with a drive, a dot segment or a backslash fail',
        () async {
          File(tasks).writeAsStringSync(
            '- [x] 1.1 [evidence] evidence/../tasks.md\n'
            '- [x] 1.2 [evidence] evidence/a:b\n'
            '- [x] 1.3 [evidence] evidence/a\\b\n'
            '- [x] 1.4 [evidence] (evidence/out.txt)\n'
            '- [x] 1.5 [evidence] see "evidence/out.txt", ok\n',
          );
          expect(await run(args()), 0);
          expect(json()['evidence_missing'], ['1.1', '1.2', '1.3']);
        },
        skip: bash == null ? 'no bash' : null,
      );

      test('--rev: a tasks file outside the repo is no_tasks', () async {
        final other = '${dir.path}/other.md';
        File(other).writeAsStringSync('- [x] 1.1 a\n');
        final a = args(rev: 'HEAD');
        a[a.indexOf('--tasks') + 1] = other;
        expect(await run(a), 2);
        expect(json()['error'], 'no_tasks');
        expect(json()['message'], 'tasks file $other is outside the repo');
      }, skip: bash == null ? 'no bash' : null);

      test('--rev: a tasks file absent at the revision is no_tasks', () async {
        write('chg/new.md', '- [x] 1.1 a\n');
        final a = args(rev: 'HEAD');
        a[a.indexOf('--tasks') + 1] = '${repo.path}/chg/new.md';
        expect(await run(a), 2);
        expect(json()['error'], 'no_tasks');
        expect(json()['message'], 'no tasks file chg/new.md at HEAD');
      }, skip: bash == null ? 'no bash' : null);

      test('an empty range answers with no commits', () async {
        expect(await run(args(range: 'HEAD..HEAD')), 0);
        final doc = json();
        expect(doc['duplicates'], isEmpty);
        expect(
          (doc['tasks'] as List).every(
            (t) => ((t as Map)['commits'] as List).isEmpty,
          ),
          isTrue,
        );
      }, skip: bash == null ? 'no bash' : null);

      test('a bad range is git_failed, exit 3', () async {
        expect(await run(args(range: 'nope..HEAD')), 3);
        expect(json()['error'], 'git_failed');
        expect(json()['message'], startsWith('git rev-list failed: '));
      }, skip: bash == null ? 'no bash' : null);
    });
  });
}
