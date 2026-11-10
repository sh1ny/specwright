import 'dart:io';

import 'package:specwright_cli/src/pr/gh.dart' show GhResult;
import 'package:specwright_cli/src/pr/queries.dart';
import 'package:specwright_cli/src/pr/reply.dart';
import 'package:test/test.dart';

import 'pr_support.dart';

/// Which `gh` call [args] is.
String kindOf(List<String> args) {
  final text = args.join(' ');
  if (args.first == 'repo') return 'repo';
  if (args.first == 'pr') return 'comment';
  if (text.contains('reviews(states:PENDING')) return 'pending';
  if (text.contains('node(id:\$id)')) return 'rev';
  if (text.contains('addReaction')) return 'react-node';
  if (text.contains('resolveReviewThread')) return 'resolve';
  if (text.contains('/reactions')) return 'react-rest';
  if (text.contains('/replies')) return 'post';
  return 'other';
}

void main() {
  late Fixture f;
  late File body;
  var gone = <String>[];

  /// The usual answers; [overrides] by kind.
  void answers([
    Map<String, GhResult Function(List<String>)> overrides = const {},
  ]) {
    f.onGh = (args) {
      final kind = kindOf(args);
      final custom = overrides[kind];
      if (custom != null) return custom(args);
      return switch (kind) {
        'repo' => answer('o/n\n'),
        'pending' => answer('0\n'),
        'rev' => answer('5@2026-11-01T10:00:00Z\n'),
        'post' => answer('https://github.com/o/n/pull/7#r1\n'),
        'comment' => answer('https://github.com/o/n/pull/7#issuecomment-1\n'),
        'resolve' => answer('resolved: true\n'),
        'react-node' => answer('reacted: THUMBS_UP\n'),
        'react-rest' => answer('reacted: +1\n'),
        _ => throw StateError('unexpected gh call $args'),
      };
    };
  }

  List<String> kinds() => [for (final c in f.ghCalls) kindOf(c)];

  Future<int> reply(List<String> args) => runReply(f.ctx, args);

  setUp(() {
    f = Fixture();
    body = f.file('body.md', 'done');
    answers();
    gone = [];
  });
  tearDown(() => f.dispose());

  group('the option rule', () {
    test('the equals form matches the two-word form', () async {
      expect(
        await reply([
          '7',
          'resolve',
          'T',
          '--repo=o/n',
          '--rev=5@2026-11-01T10:00:00Z',
        ]),
        0,
        reason: f.stderr,
      );
      expect(kinds(), ['pending', 'rev', 'resolve']);
      f.ghCalls.clear();
      expect(
        await reply([
          '7',
          'comment',
          'C',
          body.path,
          '--react=-1',
          '--repo=o/n',
        ]),
        0,
        reason: f.stderr,
      );
      expect(kinds().last, 'react-node');
    });

    test('a single-dash positional and a dash value keep working', () async {
      expect(await reply(['7', 'react', 'C', '-1', '--repo', 'o/n']), 0);
      expect(
        await reply([
          '7',
          'comment',
          'C',
          body.path,
          '--react',
          '-1',
          '--repo',
          'o/n',
        ]),
        0,
        reason: f.stderr,
      );
    });

    test('an abbreviated or unknown option is a usage stop, exit 4', () async {
      for (final extra in [
        ['--rep', 'o/n'],
        ['--re=5'],
        ['--bogus'],
      ]) {
        f.err.clear();
        f.ghCalls.clear();
        expect(
          await reply(['7', 'resolve', 'T', ...extra]),
          4,
          reason: '$extra',
        );
        expect(f.ghCalls, isEmpty, reason: '$extra');
      }
    });

    test('an option before the positionals is a usage stop, exit 4', () async {
      expect(await reply(['7', 'resolve', '--repo', 'o/n', 'T']), 4);
      expect(await reply(['7', 'react', '--repo', 'o/n', 'C', '-1']), 4);
      expect(await reply(['7', 'thread', '--resolve', 'T', '1', body.path]), 4);
      expect(f.ghCalls, isEmpty);
    });
  });

  group('refused before any gh call (exit 4)', () {
    void refused(List<String> args, String message) {
      test('${args.join(' ')} -> $message', () async {
        expect(await reply(args), 4);
        expect(f.stderr, contains(message));
        expect(
          f.ghCalls,
          isEmpty,
          reason: 'no gh call, the repo lookup included',
        );
        expect(f.tempCalls, isEmpty);
      });
    }

    refused(
      ['7', 'thread', 'T', '1', 'missing.md'],
      'pr-reply: body file missing.md is missing, unreadable or empty; nothing was posted',
    );
    refused([
      '7',
      'comment',
      'C',
      'missing.md',
    ], 'pr-reply: body file missing.md is missing, unreadable or empty');
    refused(['7', 'thread', 'T', '1', '.'], 'is missing, unreadable or empty');
    refused([
      '7',
      'thread',
      'T',
      '1',
      'x',
      '--react',
      'x',
    ], 'pr-reply: --react must be +1 or -1');
    refused([
      '7',
      'thread',
      'T',
      '1',
      'x',
      '--waiting',
      '--resolve',
    ], 'pr-reply: --waiting takes neither --resolve nor --react');
    refused([
      '7',
      'thread',
      'T',
      '1',
      'x',
      '--waiting',
      '--react',
      '+1',
    ], 'pr-reply: --waiting takes neither --resolve nor --react');
    refused(
      ['7', 'thread', 'T', '1'],
      'usage: pr-reply.sh <PR> thread <thread-id> <root-comment-id> <body-file> [--resolve] [--react +1|-1]',
    );
    refused(
      ['7', 'comment', 'C'],
      'usage: pr-reply.sh <PR> comment <source-id> <body-file> [--react +1|-1]',
    );
    refused([
      '7',
      'react',
      'C',
    ], 'usage: pr-reply.sh <PR> react <comment-id> +1|-1');
    refused(['7', 'react', 'C', 'up'], 'pr-reply: reaction must be +1 or -1');
    refused(['7', 'resolve'], 'usage: pr-reply.sh <PR> resolve <thread-id>');
    refused([
      '7',
      'bogus',
      'x',
    ], 'pr-reply: kind must be thread, comment, react or resolve');

    test('an empty body file is refused too', () async {
      final empty = f.file('empty.md', '');
      expect(await reply(['7', 'comment', 'C', empty.path]), 4);
      expect(f.stderr, contains('is missing, unreadable or empty'));
      expect(f.ghCalls, isEmpty);
    });
  });

  group(
    'a missing positional argument stops with bash\'s message (exit 1)',
    () {
      test('no PR', () async {
        expect(await reply([]), 1);
        expect(f.stderr, 'pr-reply.sh: line 50: 1: PR\n');
      });

      test('no kind', () async {
        expect(await reply(['7']), 1);
        expect(f.stderr, 'pr-reply.sh: line 50: 2: thread|comment|resolve\n');
      });

      test(
        'an option without its value is a usage stop, an empty one is not',
        () async {
          for (final option in ['--repo', '--react', '--rev']) {
            f.err.clear();
            expect(
              await reply(['7', 'resolve', 'T', option]),
              4,
              reason: option,
            );
          }
          f.err.clear();
          expect(await reply(['7', 'resolve', 'T', '--repo', '']), 1);
          expect(
            f.stderr,
            'pr-reply.sh: line 54: 2: --repo needs owner/name\n',
          );
          f.err.clear();
          expect(await reply(['7', 'resolve', 'T', '--react', '']), 1);
          expect(f.stderr, 'pr-reply.sh: line 56: 2: --react needs +1 or -1\n');
          f.err.clear();
          expect(await reply(['7', 'resolve', 'T', '--rev', '']), 1);
          expect(
            f.stderr,
            'pr-reply.sh: line 58: 2: --rev needs the item rev\n',
          );
          expect(f.ghCalls, isEmpty);
        },
      );
    },
  );

  group('a thread reply', () {
    test('posts the body and its marker, resolves and reacts', () async {
      f.onGh = (args) {
        if (kindOf(args) == 'post') {
          final path = args
              .firstWhere((a) => a.startsWith('body=@'))
              .substring(6);
          expect(
            File(path).readAsStringSync(),
            'done\n\n<!-- specwright:handled T resolve rev=5@2026-11-01T10:00:00Z -->\n',
          );
          gone.add(path);
        }
        return switch (kindOf(args)) {
          'pending' => answer('0\n'),
          'rev' => answer('5@2026-11-01T10:00:00Z\n'),
          'post' => answer('https://github.com/o/n/pull/7#r1\n'),
          'resolve' => answer('resolved: true\n'),
          'react-rest' => answer('reacted: +1\n'),
          _ => throw StateError('$args'),
        };
      };
      final code = await reply([
        '7',
        'thread',
        'T',
        '55',
        body.path,
        '--resolve',
        '--react',
        '+1',
        '--rev',
        '5@2026-11-01T10:00:00Z',
        '--repo',
        'o/n',
      ]);
      expect(code, 0, reason: f.stderr);
      expect(kinds(), [
        'pending',
        'rev',
        'post',
        'pending',
        'resolve',
        'react-rest',
      ]);
      expect(f.ghCalls[2], [
        'api',
        '--method',
        'POST',
        'repos/o/n/pulls/7/comments/55/replies',
        '-F',
        'body=@${gone.single}',
        '--jq',
        htmlUrlJq,
      ]);
      expect(
        f.stdout,
        'https://github.com/o/n/pull/7#r1\nresolved: true\nreacted: +1\n',
      );
      expect(f.stderr, isEmpty);
      expect(
        File(gone.single).existsSync(),
        isFalse,
        reason: 'the body file is removed',
      );
    });

    test(
      'with no --rev there is no re-read and the marker has no rev',
      () async {
        f.onGh = (args) {
          if (kindOf(args) == 'post') {
            final path = args
                .firstWhere((a) => a.startsWith('body=@'))
                .substring(6);
            expect(
              File(path).readAsStringSync(),
              endsWith('\n\n<!-- specwright:handled T -->\n'),
            );
          }
          return switch (kindOf(args)) {
            'pending' => answer('0\n'),
            'post' => answer('url\n'),
            _ => throw StateError('$args'),
          };
        };
        expect(
          await reply(['7', 'thread', 'T', '55', body.path, '--repo', 'o/n']),
          0,
        );
        expect(kinds(), ['pending', 'post', 'pending']);
      },
    );

    test('--waiting writes a waiting marker', () async {
      f.onGh = (args) {
        if (kindOf(args) == 'post') {
          final path = args
              .firstWhere((a) => a.startsWith('body=@'))
              .substring(6);
          expect(
            File(path).readAsStringSync(),
            endsWith('<!-- specwright:waiting T -->\n'),
          );
        }
        return kindOf(args) == 'pending' ? answer('0\n') : answer('url\n');
      };
      expect(
        await reply([
          '7',
          'thread',
          'T',
          '55',
          body.path,
          '--waiting',
          '--repo',
          'o/n',
        ]),
        0,
      );
    });

    test('a failed resolution prints the retry line and exits 1', () async {
      answers({'resolve': (_) => answer('', exit: 1, stderr: 'boom\n')});
      final code = await reply([
        '7',
        'thread',
        'T',
        '55',
        body.path,
        '--resolve',
        '--react',
        '-1',
        '--repo',
        'o/n',
      ]);
      expect(code, 1);
      expect(kinds().last, 'react-rest', reason: 'the reaction is still tried');
      expect(
        f.stderr,
        'boom\npr-reply: reply posted but resolution failed; retry only the resolution: pr-reply.sh 7 resolve T\n',
      );
    });

    test('with --rev the retry line asks for the fresh rev', () async {
      answers({
        'rev': (_) => answer('R\n'),
        'resolve': (_) => answer('', exit: 1),
      });
      expect(
        await reply([
          '7',
          'thread',
          'T',
          '55',
          body.path,
          '--resolve',
          '--rev',
          'R',
          '--repo',
          'o/n',
        ]),
        1,
      );
      expect(
        f.stderr,
        'pr-reply: reply posted but resolution failed; retry only the resolution, with the thread\'s rev from a fresh '
        'snapshot that lists it resolve_pending (your reply changed it): pr-reply.sh 7 resolve T --rev <rev>\n',
      );
    });

    test('a failed reaction prints the retry line and exits 1', () async {
      answers({'react-rest': (_) => answer('', exit: 1, stderr: 'nope\n')});
      expect(
        await reply([
          '7',
          'thread',
          'T',
          '55',
          body.path,
          '--react',
          '+1',
          '--repo',
          'o/n',
        ]),
        1,
      );
      expect(
        f.stderr,
        'nope\npr-reply: reply posted but the reaction failed; retry only the reaction: pr-reply.sh 7 react 55 +1\n',
      );
    });

    test('a numeric id is reacted to through REST', () async {
      expect(
        await reply([
          '7',
          'thread',
          'T',
          '55',
          body.path,
          '--react',
          '-1',
          '--repo',
          'o/n',
        ]),
        0,
      );
      expect(f.ghCalls.last, [
        'api',
        '--method',
        'POST',
        'repos/o/n/pulls/comments/55/reactions',
        '-f',
        'content=-1',
        '--jq',
        reactRestJq,
      ]);
    });

    test('a failed post stops with gh\'s status, after its stderr', () async {
      answers({'post': (_) => answer('', exit: 1, stderr: 'HTTP 422\n')});
      expect(
        await reply([
          '7',
          'thread',
          'T',
          '55',
          body.path,
          '--resolve',
          '--repo',
          'o/n',
        ]),
        1,
      );
      expect(kinds(), ['pending', 'post']);
      expect(f.stderr, 'HTTP 422\n');
    });

    test('a limit on the post prints its line and exits 124', () async {
      answers({
        'post': (_) => answer(
          '',
          exit: 124,
          limitLine: 'bounded: deadline_exceeded: gh api\n',
        ),
      });
      expect(
        await reply(['7', 'thread', 'T', '55', body.path, '--repo', 'o/n']),
        124,
      );
      expect(f.stderr, 'bounded: deadline_exceeded: gh api\n');
    });
  });

  group('a comment reply', () {
    test('goes through gh pr comment with the body file and reacts', () async {
      f.onGh = (args) {
        if (kindOf(args) == 'comment') {
          final path = args[args.indexOf('--body-file') + 1];
          expect(
            File(path).readAsStringSync(),
            'done\n\n<!-- specwright:handled IC_1 -->\n',
          );
        }
        return switch (kindOf(args)) {
          'pending' => answer('0\n'),
          'comment' => answer('https://x/1\n'),
          'react-node' => answer('reacted: THUMBS_DOWN\n'),
          _ => throw StateError('$args'),
        };
      };
      expect(
        await reply([
          '7',
          'comment',
          'IC_1',
          body.path,
          '--react',
          '-1',
          '--repo',
          'o/n',
        ]),
        0,
      );
      expect(kinds(), ['pending', 'comment', 'react-node']);
      expect(f.ghCalls[1].sublist(0, 6), [
        'pr',
        'comment',
        '7',
        '-R',
        'o/n',
        '--body-file',
      ]);
      expect(f.stdout, 'https://x/1\nreacted: THUMBS_DOWN\n');
    });
  });

  group('react and resolve', () {
    test('react alone checks the pending review and reacts', () async {
      expect(await reply(['7', 'react', 'PRRC_1', '+1', '--repo', 'o/n']), 0);
      expect(kinds(), ['pending', 'react-node']);
      expect(f.tempCalls, isEmpty);
    });

    test('react with a failing gh stops with its status', () async {
      answers({'react-node': (_) => answer('', exit: 1)});
      expect(await reply(['7', 'react', 'PRRC_1', '+1', '--repo', 'o/n']), 1);
    });

    test('resolve re-reads the thread when --rev is given', () async {
      expect(
        await reply([
          '7',
          'resolve',
          'T',
          '--rev',
          '5@2026-11-01T10:00:00Z',
          '--repo',
          'o/n',
        ]),
        0,
      );
      expect(kinds(), ['pending', 'rev', 'resolve']);
      expect(f.stdout, 'resolved: true\n');
    });
  });

  group('the repository', () {
    test('is looked up when --repo is not given, after the checks', () async {
      expect(await reply(['7', 'resolve', 'T']), 0);
      expect(f.ghCalls.first, [
        'repo',
        'view',
        '--json',
        'owner,name',
        '--jq',
        repoViewJq,
      ]);
      expect(f.ghCalls[1].contains('owner=o'), isTrue);
      expect(f.ghCalls[1].contains('name=n'), isTrue);
    });

    test('a failed lookup stops with gh\'s status', () async {
      answers({'repo': (_) => answer('', exit: 1, stderr: 'no repo\n')});
      expect(await reply(['7', 'resolve', 'T']), 1);
      expect(f.stderr, 'no repo\n');
    });
  });

  group('the pending review', () {
    test('exits 2 before anything is posted', () async {
      answers({'pending': (_) => answer('1\n')});
      expect(
        await reply(['7', 'thread', 'T', '55', body.path, '--repo', 'o/n']),
        2,
      );
      expect(
        f.stderr,
        'pr-reply: you have a pending (unsubmitted) review on #7; replies may be hidden in it. '
        'Submit or discard it first.\n',
      );
      expect(kinds(), ['pending']);
      expect(f.leftovers, ['body.md'], reason: 'the body file is removed');
    });

    test('is checked again after the post', () async {
      var n = 0;
      answers({'pending': (_) => answer(++n == 1 ? '0\n' : '1\n')});
      expect(
        await reply([
          '7',
          'thread',
          'T',
          '55',
          body.path,
          '--resolve',
          '--repo',
          'o/n',
        ]),
        2,
      );
      expect(kinds(), ['pending', 'post', 'pending']);
    });
  });

  group('the revision check', () {
    Future<int> withRev() => reply([
      '7',
      'thread',
      'T',
      '55',
      body.path,
      '--rev',
      '900@2026-11-01T10:00:00Z',
      '--resolve',
      '--repo',
      'o/n',
    ]);

    test('a stale revision exits 5 and posts nothing', () async {
      answers({'rev': (_) => answer('901@2026-11-02T09:00:00Z\n')});
      expect(await withRev(), 5);
      expect(
        f.stderr,
        'pr-reply: T changed since it was judged (judged 900@2026-11-01T10:00:00Z, now 901@2026-11-02T09:00:00Z); '
        'nothing was posted. Take a fresh snapshot and judge it again.\n',
      );
      expect(kinds(), ['pending', 'rev']);
    });

    test('an unreadable item exits 3', () async {
      answers({'rev': (_) => answer('', exit: 1, stderr: 'boom\n')});
      expect(await withRev(), 3);
      expect(
        f.stderr,
        'boom\npr-reply: cannot read T to check its revision; nothing was posted\n',
      );
    });

    test('an empty answer exits 3 too', () async {
      answers({'rev': (_) => answer('\n')});
      expect(await withRev(), 3);
    });

    test('a thread of more than one page exits 3', () async {
      answers({'rev': (_) => answer('long:130\n')});
      expect(await withRev(), 3);
      expect(
        f.stderr,
        'pr-reply: T has 130 comments, more than one read returns, so its revision cannot be checked; nothing was '
        'posted. Answer it on GitHub.\n',
      );
    });
  });

  group('the temp file', () {
    test('no temp file exits 4 before any post', () async {
      f.tempFails = true;
      expect(
        await reply(['7', 'thread', 'T', '55', body.path, '--repo', 'o/n']),
        4,
      );
      expect(
        f.stderr,
        'pr-reply: no temp file for body file ${body.path}; nothing was posted\n',
      );
      expect(f.ghCalls, isEmpty);
    });

    test('a temp file that cannot be written exits 4 before any gh call', () async {
      f.fixedTemp = '${f.tempDir.path}/no-such-dir/reply.md';
      expect(await reply(['7', 'comment', 'C', body.path, '--repo', 'o/n']), 4);
      expect(
        f.stderr,
        'pr-reply: the reply for body file ${body.path} could not be written in full; nothing was posted\n',
      );
      expect(f.ghCalls, isEmpty);
    });

    test('is removed on every exit', () async {
      answers({'pending': (_) => answer('1\n')});
      await reply(['7', 'comment', 'C', body.path, '--repo', 'o/n']);
      answers({'rev': (_) => answer('other\n')});
      await reply([
        '7',
        'comment',
        'C',
        body.path,
        '--rev',
        'x',
        '--repo',
        'o/n',
      ]);
      expect(f.leftovers, ['body.md']);
    });
  });
}
