import 'dart:convert';
import 'dart:io';

import 'package:specwright_cli/src/pr/context.dart';
import 'package:specwright_cli/src/pr/settings_commands.dart';
import 'package:specwright_cli/src/settings/reviewer_config.dart';
import 'package:specwright_cli/src/vcs/text_result.dart';
import 'package:test/test.dart';

import '../vcs/bash_support.dart';
import 'pair_support.dart';

// `sw pr vcs`, `tier` and `context` against `pr-pair.sh vcs|tier|context` (pr-pair.sh:1139-1291).

void main() {
  final skip = findBash() == null ? 'needs a bash' : null;
  late Scratch tmp;
  setUp(() => tmp = Scratch());
  tearDown(() => tmp.dispose());

  String code() => '${tmp.path}/code';

  void settings(String text, {String? dir}) {
    final f = File('${dir ?? code()}/openspec/specwright.yaml')
      ..createSync(recursive: true);
    f.writeAsBytesSync(utf8.encode(text));
  }

  Map<String, String> env() => {
    ...Platform.environment,
    'SPECWRIGHT_STATE_DIR': '${tmp.path}/state',
  };

  Future<Ran> run(
    Future<int> Function(PrContext ctx, List<String> argv) fn,
    List<String> argv, {
    Map<String, String>? environment,
  }) async {
    final r = PairRun(env: environment ?? env());
    return r.result(await fn(r.ctx, argv));
  }

  Future<Ran> vcs(List<String> argv) => run(runVcs, argv);
  Future<Ran> tier(List<String> argv) => run(runTier, argv);
  Future<Ran> context(List<String> argv, {Map<String, String>? environment}) =>
      run(runContext, argv, environment: environment);

  group('vcs', () {
    test('a top level that is not UTF-8 is not_utf8, exit 1 (D4)', () async {
      Directory(code()).createSync(recursive: true);
      final out = <int>[];
      final ctx = PrContext(
        scriptsDir: 'scripts',
        bash: 'bash',
        writeOut: out.addAll,
        writeErr: (_) {},
        environment: env(),
        git: (dir, args) async => TextResult(
          0,
          '/r\u{FFFD}',
          '',
          stdoutBytes: [0x2f, 0x72, 0xff, 0x0a],
        ),
      );
      final exit = await runVcs(ctx, ['--code', code()]);
      final doc = jsonDecode(utf8.decode(out)) as Map<String, Object?>;
      expect(exit, 1);
      expect(doc['error'], 'not_utf8');
      expect(doc['message'], contains('repository path'));
    });

    test('absent settings default each backend to git', () async {
      Directory(code()).createSync(recursive: true);
      final r = await vcs(['--code', code()]);
      expect(r.code, 0);
      expect(r.stdout, '{"ok":true,"code":"git","store":"git"}\n');
    });

    test('reads the code backend and the store backend', () async {
      settings('vcs: jj\nplanning_store:\n  vcs: jj\n');
      expect((await vcs(['--code', code()])).json, {
        'ok': true,
        'code': 'jj',
        'store': 'jj',
      });
      settings('vcs: gitbutler\nfinish: pr\n');
      expect((await vcs(['--code', code()])).json, {
        'ok': true,
        'code': 'gitbutler',
        'store': 'git',
      });
    });

    test(
      'reads the settings of the git top level from a subdirectory',
      () async {
        initRepo(code());
        settings('vcs: jj\n');
        final sub = Directory('${code()}/pkg')..createSync();
        expect((await vcs(['--code', sub.path])).json['code'], 'jj');
      },
      skip: skip,
    );

    test(
      'unknown_vcs, unsupported_vcs and unsupported_combination stop',
      () async {
        settings('vcs: svn\n');
        var r = await vcs(['--code', code()]);
        expect(r.code, 1);
        expect(r.json['ok'], false);
        expect(r.json['error'], 'unknown_vcs');
        expect(r.json['message'], startsWith('unknown code VCS'));
        settings('planning_store:\n  vcs: hg\n');
        r = await vcs(['--code', code()]);
        expect(r.json['error'], 'unknown_vcs');
        expect(r.json['message'], startsWith('unknown planning_store VCS'));
        settings('planning_store:\n  vcs: gitbutler\n');
        r = await vcs(['--code', code()]);
        expect((r.code, r.json['error']), (1, 'unsupported_vcs'));
        settings('vcs: gitbutler\n');
        r = await vcs(['--code', code()]);
        expect((r.code, r.json['error']), (1, 'unsupported_combination'));
        expect(r.json['message'], startsWith('vcs: gitbutler runs only with'));
      },
    );

    test('--code is needed', () async {
      final r = await vcs([]);
      expect(
        (r.code, r.json['error'], r.json['message']),
        (2, 'usage', 'missing --code'),
      );
    });
  });

  group('tier', () {
    test('cheap_tier is false unless it holds enabled: true', () async {
      Directory(code()).createSync(recursive: true);
      expect((await tier(['--code', code()])).json, {
        'ok': true,
        'cheap_tier': false,
      });
      settings('cheap_tier:\n  enabled: true\n');
      expect((await tier(['--code', code()])).json, {
        'ok': true,
        'cheap_tier': true,
      });
      settings('cheap_tier:\n  enabled: false\n');
      expect((await tier(['--code', code()])).json['cheap_tier'], false);
    });

    test('a value that is not true or false is false with a note', () async {
      settings('cheap_tier:\n  enabled: maybe\n');
      var r = await tier(['--code', code()]);
      expect(r.code, 0);
      expect(r.json['cheap_tier'], false);
      expect(r.json['note'], startsWith('cheap_tier.enabled: maybe'));
      settings('cheap_tier: on\n');
      r = await tier(['--code', code()]);
      expect(r.json['cheap_tier'], false);
      expect(r.json['note'], startsWith('cheap_tier must hold'));
    });

    test('a bad merge_method does not change it', () async {
      settings(
        'pr:\n  merge: agent\n  merge_method: fast\ncheap_tier:\n  enabled: true\n',
      );
      expect((await tier(['--code', code()])).json['cheap_tier'], true);
    });
  });

  group('context', () {
    const reviewers =
        'github:\n  login: me\npr:\n  reviewers:\n    rev-bot[bot]:\n      role: required\n      timeout: 60\n';

    test('prints the repo context with its config file', () async {
      initRepo(code(), origin: 'https://github.com/o/n');
      settings(reviewers);
      final r = await context(['--code', code()]);
      expect(r.code, 0, reason: r.stdout);
      final doc = r.json;
      expect(doc.keys, [
        'ok',
        'code',
        'store',
        'finish',
        'max_fix_rounds',
        'after_limit',
        'react',
        'poll_interval',
        'settle',
        'merge',
        'merge_method',
        'delete_branch',
      ]);
      expect(doc['store'], isNull);
      final c = doc['code']! as Map<String, Object?>;
      expect(c.keys, [
        'dir',
        'review_request',
        'request_as',
        'login',
        'main',
        'validate',
        'reviewers',
        'requests_disabled',
        'merge_ready',
        'merge_reason',
        'repo',
        'reviewer_config',
      ]);
      expect(c['login'], 'me');
      expect(c['main'], 'main');
      expect(c['repo'], 'o/n');
      expect(c['merge_ready'], true);
      expect(c['reviewers'], {
        'rev-bot': {
          'role': 'required',
          'timeout': 60,
          'request': '',
          'report': <String, Object?>{},
        },
      });
      final bytes = File(c['reviewer_config']! as String).readAsBytesSync();
      expect(
        utf8.decode(bytes),
        '{"format":2,"reviewers":[{"login":"rev-bot","report":{},"role":"required","timeout":60}]}',
      );
      expect(
        (c['reviewer_config']! as String).endsWith('/${sha256Hex(bytes)}.json'),
        isTrue,
      );
      expect(c['reviewer_config'], startsWith('${tmp.path}/state/reviewers/'));
      expect(doc.containsKey('settings_problem'), isFalse);
    }, skip: skip);

    test(
      'a store gets its own context; a repo without origin has repo null',
      () async {
        initRepo(code(), origin: 'https://github.com/o/n');
        initRepo('${tmp.path}/store');
        settings(
          '$reviewers'
          'planning_store:\n  login: bot\n  reviewers: {}\n',
        );
        final r = await context([
          '--code',
          code(),
          '--store',
          '${tmp.path}/store',
        ]);
        final s = r.json['store']! as Map<String, Object?>;
        expect(s['login'], 'bot');
        expect(s['repo'], isNull);
        expect(s['requests_disabled'], true);
        expect(s['merge_ready'], false);
        expect(s['merge_reason'], 'no_required_reviewer');
        expect(s['reviewer_config'], isA<String>());
      },
      skip: skip,
    );

    test('a settings_problem is printed and the exit status stays 0', () async {
      initRepo(code(), origin: 'https://github.com/o/n');
      settings('github:\n  login: me\npr:\n  settle: soon\n');
      var r = await context(['--code', code()]);
      expect(r.code, 0);
      expect(r.json['settings_problem'], startsWith('pr.settle: soon must be'));
      settings('a: 1\nb:\n  c: 1\n  d: 2\ne:\n  f:\n\tg: 1\n');
      r = await context(['--code', code()]);
      expect(r.code, 0);
      expect(r.json['settings_problem'], startsWith('line 7:'));
      expect(r.json['ok'], true);
    }, skip: skip);

    test(
      'the first problem wins: the strict reader over a bad setting',
      () async {
        initRepo(code(), origin: 'https://github.com/o/n');
        settings('pr:\n  settle: soon\n\tx: 1\n');
        final r = await context(['--code', code()]);
        expect(r.json['settings_problem'], startsWith('line 3:'));
      },
      skip: skip,
    );

    test('21 reviewers is too_many_reviewers, still read whole', () async {
      initRepo(code(), origin: 'https://github.com/o/n');
      settings(
        'pr:\n  reviewers:\n${[for (var i = 0; i < 21; i++) '    r$i:\n      role: required\n'].join()}',
      );
      final r = await context(['--code', code()]);
      expect(r.code, 0);
      expect(
        r.json['settings_problem'],
        startsWith('pr.reviewers: 21 reviewers is too_many_reviewers'),
      );
      final c = r.json['code']! as Map<String, Object?>;
      expect((c['reviewers']! as Map).length, 21);
    }, skip: skip);

    test('--only repos skips the merge settings check', () async {
      initRepo(code(), origin: 'https://github.com/o/n');
      settings('pr:\n  merge: agent\n  merge_method: fast\n');
      var r = await context(['--code', code()]);
      expect(r.code, 2);
      expect(r.json['ok'], false);
      expect(r.json['error'], 'bad_setting');
      expect(r.json['message'], startsWith('pr.merge_method: fast'));
      r = await context(['--code', code(), '--only', 'repos']);
      expect(r.code, 0);
      expect(r.json['merge'], 'agent');
      expect(r.json['merge_method'], 'merge');
    }, skip: skip);

    test('usage stops', () async {
      Directory(code()).createSync(recursive: true);
      var r = await context([]);
      expect((r.code, r.json['message']), (2, 'missing --code'));
      r = await context(['--code', code(), '--only', 'all']);
      expect((r.code, r.json['message']), (2, '--only takes repos'));
      r = await context(['--code', code(), '--after-merge']);
      expect((r.code, r.json['message']), (2, '--after-merge needs --branch'));
      r = await context(['--code', code(), '--bogus', 'x']);
      expect((r.code, r.json['error']), (2, 'usage'));
    });

    test(
      'context write failure is internal_error JSON without a stack trace',
      () async {
        initRepo(code(), origin: 'https://github.com/o/n');
        settings(reviewers);
        // no SPECWRIGHT_STATE_DIR and no home directory: the writer throws, as Path.home() did in the script
        final r = await context(
          ['--code', code()],
          environment: {'PATH': Platform.environment['PATH'] ?? ''},
        );
        expect(r.code, 1);
        expect(r.stderr, '');
        expect(r.stdout.trim().split('\n'), hasLength(1));
        final doc = r.json;
        expect(doc['ok'], false);
        expect(doc['error'], 'internal_error');
        expect(doc['message'], startsWith('StateError: '));
        expect(r.stdout, isNot(contains('package:')));
        expect(r.stdout, isNot(contains('#0')));
      },
      skip: skip,
    );
  });

  group('the GitButler pin', () {
    const pinned = 'vcs: gitbutler\nfinish: pr\ngithub:\n  login: me\n';

    void pinnedRepo() {
      initRepo(code(), origin: 'https://github.com/o/n');
      commitFile(code(), 'openspec/specwright.yaml', pinned);
      git(code(), ['branch', 'feat/a']);
    }

    test('a work tree file equal to the branch copy passes', () async {
      pinnedRepo();
      final r = await context(['--code', code(), '--branch', 'feat/a']);
      expect(r.code, 0, reason: r.stdout);
      expect(r.json['ok'], true);
    }, skip: skip);

    test(
      'a different file is settings_not_pinned, naming file and ref',
      () async {
        pinnedRepo();
        settings('$pinned# edited\n');
        final r = await context(['--code', code(), '--branch', 'feat/a']);
        expect(r.code, 1);
        expect(r.json['ok'], false);
        expect(r.json['error'], 'settings_not_pinned');
        expect(r.json['file'], 'openspec/specwright.yaml');
        expect(r.json['ref'], 'refs/heads/feat/a');
        expect(r.json['message'], contains('differs from the copy'));
        expect(r.json['message'], contains('commit the edit on feat/a'));
      },
      skip: skip,
    );

    test('a file only in the work tree, or only on the branch', () async {
      initRepo(code(), origin: 'https://github.com/o/n');
      commitFile(code(), 'README.md', 'x');
      git(code(), ['branch', 'feat/a']);
      settings(pinned);
      var r = await context(['--code', code(), '--branch', 'feat/a']);
      expect(r.json['error'], 'settings_not_pinned');
      expect(r.json['message'], contains('exists in the work tree but not at'));
      git(code(), ['checkout', '-q', 'feat/a']);
      commitFile(code(), 'openspec/specwright.yaml', pinned);
      File('${code()}/openspec/specwright.yaml').deleteSync();
      // with the file gone only a GitButler-managed repo pins
      Directory('${code()}/.git/gitbutler').createSync();
      git(code(), ['config', 'gitbutler.project.targetRef', 'refs/heads/main']);
      r = await context(['--code', code(), '--branch', 'feat/a']);
      expect(r.json['message'], contains('is missing from the work tree'));
    }, skip: skip);

    test('a branch git cannot read is git_error', () async {
      pinnedRepo();
      final r = await context(['--code', code(), '--branch', 'nope']);
      expect(r.code, 1);
      expect(r.json['error'], 'git_error');
    }, skip: skip);

    test(
      'without --branch the merge settings need one; --only repos does not',
      () async {
        pinnedRepo();
        var r = await context(['--code', code()]);
        expect(r.code, 2);
        expect(r.json['error'], 'usage');
        expect(r.json['message'], startsWith('with vcs: gitbutler'));
        r = await context(['--code', code(), '--only', 'repos']);
        expect(r.code, 0);
      },
      skip: skip,
    );

    test('--after-merge compares with the branch while it exists', () async {
      pinnedRepo();
      settings('$pinned# edited\n');
      final r = await context([
        '--code',
        code(),
        '--branch',
        'feat/a',
        '--after-merge',
      ]);
      expect(r.json['error'], 'settings_not_pinned');
      expect(r.json['ref'], 'refs/heads/feat/a');
      expect(r.json['message'], contains('but pull'));
    }, skip: skip);

    test('--after-merge falls back to the target ref, and needs one', () async {
      pinnedRepo();
      var r = await context([
        '--code',
        code(),
        '--branch',
        'gone',
        '--after-merge',
      ]);
      expect(r.code, 1);
      expect(r.json['error'], 'git_error');
      expect(r.json['message'], contains('targetRef'));
      git(code(), ['config', 'gitbutler.project.targetRef', 'refs/heads/main']);
      r = await context([
        '--code',
        code(),
        '--branch',
        'gone',
        '--after-merge',
      ]);
      expect(r.code, 0, reason: r.stdout);
      settings('$pinned# edited\n');
      r = await context([
        '--code',
        code(),
        '--branch',
        'gone',
        '--after-merge',
      ]);
      expect(r.json['error'], 'settings_not_pinned');
      expect(r.json['ref'], 'refs/heads/main');
    }, skip: skip);

    test(
      'a GitButler-managed repo pins without vcs: gitbutler in the file',
      () async {
        initRepo(code(), origin: 'https://github.com/o/n');
        commitFile(
          code(),
          'openspec/specwright.yaml',
          'github:\n  login: me\n',
        );
        git(code(), ['branch', 'feat/a']);
        git(code(), [
          'config',
          'gitbutler.project.targetRef',
          'refs/heads/main',
        ]);
        var r = await context(['--code', code()]);
        expect(r.code, 0, reason: 'a target ref alone is not GitButler');
        Directory('${code()}/.git/gitbutler').createSync();
        r = await context(['--code', code()]);
        expect(r.code, 2);
        expect(r.json['message'], startsWith('with vcs: gitbutler'));
      },
      skip: skip,
    );

    test('other repos accept and ignore --branch', () async {
      initRepo(code(), origin: 'https://github.com/o/n');
      settings('github:\n  login: me\n');
      final r = await context(['--code', code(), '--branch', 'whatever']);
      expect(r.code, 0);
    }, skip: skip);
  });
}
