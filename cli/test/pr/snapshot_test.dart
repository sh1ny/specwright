import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:specwright_cli/src/pr/context.dart' show PrContext;
import 'package:specwright_cli/src/pr/gh.dart' show GhResult;
import 'package:specwright_cli/src/process/limit_line.dart' show BoundedLimit;
import 'package:specwright_cli/src/pr/queries.dart';
import 'package:specwright_cli/src/pr/snapshot.dart';
import 'package:test/test.dart';

import 'pr_support.dart';

final oid = 'a' * 40;
const date = 'Mon, 02 Nov 2026 10:00:00 GMT';
const pushed = '2026-11-02T09:00:00Z';

/// A snapshot as the jq program prints it, reduced to the members `sw` reads.
String snapJson({
  String sig = 's1',
  String attn = 'a1',
  bool complete = true,
  String recheck = '',
  String failRuns = '',
  String extra = '',
}) =>
    '{"head_oid":"$oid","recheck":[$recheck],"complete":$complete,"sig":"$sig","attn":"$attn",'
    '"fail_names":[],"fail_run_ids":[$failRuns]$extra}';

/// Which `gh` call [args] is.
String kindOf(List<String> args) {
  final text = args.join(' ');
  if (args.first == 'repo') return 'repo';
  if (args.first == 'pr') return 'prnum';
  if (args.first == 'run') return 'logs';
  if (text.contains('node(id:\$id)')) return 'full';
  if (text.contains('headRefOid headRefName headRepository')) return 'cfg';
  if (text.contains('rate_limit')) return 'rate';
  if (text.contains('/activity?')) return 'activity';
  if (text.contains('nodes(ids:[')) return 'recheck';
  if (text.contains('statusCheckRollup')) return 'snapshot';
  return 'other';
}

void main() {
  late Fixture f;
  late Directory state;
  late String material;
  var results = <String>[];
  var evaluated = 0;
  var materials = <String>[];

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
        'prnum' => answer('7\n'),
        'cfg' => answer('$oid feature o/n\n'),
        'rate' => answer('HTTP/2.0 200 OK\r\nDate: $date\r\n\r\n{}'),
        'activity' => answer('$pushed\n'),
        'snapshot' => answer('$material\n'),
        'logs' => answer('log line\n'),
        _ => throw StateError('unexpected gh call $args'),
      };
    };
    f.onBounded = (command) {
      final path = command[command.indexOf('--material') + 1];
      materials.add(File(path).readAsStringSync());
      final text =
          results[evaluated < results.length ? evaluated : results.length - 1];
      evaluated++;
      return answer('$text\n');
    };
  }

  List<String> kinds() => [for (final c in f.ghCalls) kindOf(c)];

  Future<int> snapshot(List<String> args) => runSnapshot(f.ctx, args);

  /// The claim files of PR 7.
  List<String> claims() {
    final dir = Directory('${state.path}/watch/v2/o/n/7');
    if (!dir.existsSync()) return [];
    return [for (final e in dir.listSync()) e.uri.pathSegments.last];
  }

  setUp(() {
    state = Directory.systemTemp.createTempSync('sw-state-');
    f = Fixture(
      environment: {'SPECWRIGHT_STATE_DIR': state.path, 'HOME': state.path},
    );
    material = snapJson(extra: ',"material":{}');
    results = [snapJson()];
    evaluated = 0;
    materials = [];
    answers();
  });
  tearDown(() {
    f.dispose();
    state.deleteSync(recursive: true);
  });

  group('arguments', () {
    test('an unknown argument exits 2 before any call', () async {
      expect(await snapshot(['--nope']), 2);
      expect(f.stderr, startsWith('pr-snapshot: '));
      expect(f.ghCalls, isEmpty);
    });

    test('the equals form matches the two-word form', () async {
      expect(await snapshot(['--wait', '--until=quiet']), 2);
      expect(f.stderr, contains("bad --until 'quiet'"));
      f.err.clear();
      expect(await snapshot(['--interval=0']), 2);
      expect(f.stderr, contains("bad --interval '0'"));
      expect(f.ghCalls, isEmpty);
    });

    test('an abbreviated option is a usage stop', () async {
      expect(await snapshot(['--rep', 'o/n', '7']), 2);
      expect(await snapshot(['--wai']), 2);
      expect(await snapshot(['--interv', '5']), 2);
      expect(f.ghCalls, isEmpty);
    });

    test('--reviewer is gone and names the new flag', () async {
      expect(await snapshot(['--reviewer', 'a:b:1']), 2);
      expect(f.stderr, contains('--reviewer-config FILE'));
      expect(f.ghCalls, isEmpty);
    });

    test('--interval wants whole seconds above zero', () async {
      for (final bad in ['0', 'x', '1.5', '-3']) {
        f.err.clear();
        expect(await snapshot(['--interval', bad]), 2, reason: bad);
        expect(
          f.stderr,
          "pr-snapshot: bad --interval '$bad' (want whole seconds > 0)\n",
        );
      }
    });

    test('--until takes attention, and only with --wait', () async {
      expect(await snapshot(['--wait', '--until', 'quiet']), 2);
      expect(f.stderr, "pr-snapshot: bad --until 'quiet' (want attention)\n");
      f.err.clear();
      expect(await snapshot(['--until', 'attention']), 2);
      expect(f.stderr, 'pr-snapshot: --until needs --wait\n');
      expect(f.ghCalls, isEmpty);
    });

    test('an option with no value is a usage stop; an empty value stops as bash does', () async {
      for (final key in [
        '--repo',
        '--reviewer-config',
        '--full',
        '--timeout',
        '--until',
        '--interval',
      ]) {
        f.err.clear();
        expect(await snapshot([key]), 2, reason: key);
        f.err.clear();
        expect(
          await snapshot([key, '']),
          1,
          reason: '$key with an empty value',
        );
      }
      expect(f.ghCalls, isEmpty);
    });

    test('a pull request URL gives the repository and the number', () async {
      expect(await snapshot(['https://github.com/Own/Nm/pull/12/files']), 0);
      expect(kinds(), ['cfg', 'rate', 'activity', 'snapshot']);
      final query = f.ghCalls.last;
      expect(query, containsAllInOrder(['owner=Own', 'name=Nm', 'pr=12']));
    });

    test('a number is the PR, and --repo names the repository', () async {
      expect(await snapshot(['--repo', 'a/b', '9']), 0);
      expect(kinds(), ['cfg', 'rate', 'activity', 'snapshot']);
      expect(f.ghCalls.last, containsAllInOrder(['owner=a', 'name=b', 'pr=9']));
    });
  });

  group('--full', () {
    test('reads one node and prints it', () async {
      f.onGh = (args) {
        expect(kindOf(args), 'full');
        expect(args, [
          'api',
          'graphql',
          '-f',
          'id=PRRC_1=',
          '-f',
          'query=$fullQuery',
          '--jq',
          fullJq,
        ]);
        return answer('{"ok":true,"id":"PRRC_1="}\n');
      };
      expect(await snapshot(['--full', 'PRRC_1=']), 0);
      expect(f.stdout, '{"ok":true,"id":"PRRC_1="}\n');
      expect(
        f.tempCalls,
        isEmpty,
        reason: 'no temp file, no claim, no snapshot',
      );
    });

    test('an unknown id prints not_found and exits 1', () async {
      f.onGh = (_) => answer('{"ok":false,"error":"not_found"}\n');
      expect(await snapshot(['--full', 'X']), 1);
      expect(f.stdout, '{"ok":false,"error":"not_found"}\n');
    });

    test(
      'an unknown id exits 1 however the document is spaced or ordered',
      () async {
        for (final doc in [
          '{"ok": false, "error": "not_found"}',
          '{"error": "not_found", "ok": false}',
        ]) {
          f.out.clear();
          f.onGh = (_) => answer('$doc\n');
          expect(await snapshot(['--full', 'X']), 1, reason: doc);
          expect(f.stdout, '$doc\n');
        }
        f.out.clear();
        f.onGh = (_) =>
            answer('{"ok": true, "body": "\\"error\\":\\"not_found\\""}\n');
        expect(await snapshot(['--full', 'X']), 0);
      },
    );

    test('a bad id exits 2 before any call', () async {
      expect(await snapshot(['--full', 'a b']), 2);
      expect(f.stderr, "pr-snapshot: bad --full id 'a b'\n");
      expect(f.ghCalls, isEmpty);
    });

    test('a failed read exits 3, its own stderr first', () async {
      f.onGh = (_) => answer('', exit: 1, stderr: 'boom\n');
      expect(await snapshot(['--full', 'X']), 3);
      expect(f.stderr, 'boom\npr-snapshot: cannot read X\n');
    });

    test('a limit exits 3 and names the limit', () async {
      f.onGh = (_) => answer(
        '',
        exit: 124,
        limitLine: 'bounded: deadline_exceeded: gh api\n',
      );
      expect(await snapshot(['--full', 'X']), 3);
      expect(
        f.stderr,
        'bounded: deadline_exceeded: gh api\npr-snapshot: cannot read X\n',
      );
    });
  });

  group('the reviewer config', () {
    /// A reviewer config file in the fixture's directory; [logins] are the reviewers' logins.
    String configFile(List<String> logins, [String name = 'cfg.json']) {
      final doc = {
        'format': 2,
        'reviewers': [
          for (final login in logins)
            {
              'login': login,
              'role': 'required',
              'timeout': 60,
              'report': <String, Object>{},
            },
        ],
      };
      return f.file(name, jsonEncode(doc)).path;
    }

    test('is checked in this process before any gh call, and a bad one exits 2 with its line', () async {
      final bad = f.file('cfg.json', '{not json').path;
      expect(await snapshot(['--reviewer-config', bad]), 2);
      expect(f.stderr, startsWith('reviewers.py: '));
      expect(f.stderr, contains('cfg.json'));
      expect(f.stderr, contains('not valid JSON'));
      expect('\n'.allMatches(f.stderr), hasLength(1));
      expect(f.ghCalls, isEmpty);
      expect(f.boundedCalls, isEmpty);
      expect(f.tempCalls, isEmpty);
    });

    test('a missing file exits 2 the same way', () async {
      expect(
        await snapshot(['--reviewer-config', '${f.tempDir.path}/none.json']),
        2,
      );
      expect(f.stderr, startsWith('reviewers.py: '));
      expect(f.ghCalls, isEmpty);
    });

    test('its logins reach the cfg and the evaluator gets the file', () async {
      final path = configFile(['a', 'b']);
      expect(await snapshot(['--reviewer-config', path]), 0);
      final jq = f.ghCalls.last.last;
      expect(
        jq,
        contains(
          'def cfg: {logins: ["a","b"], head: "$oid", pushed: "$pushed"',
        ),
      );
      expect(f.boundedCalls.single, contains('--config'));
      expect(
        f.boundedCalls.single[f.boundedCalls.single.indexOf('--config') + 1],
        path,
      );
    });

    test(
      'a name that is not UTF-8 reaches the evaluator as a UTF-8 copy',
      () async {
        final name = [
          ...utf8.encode('${f.tempDir.path}/reviewers-'),
          0xff,
          ...utf8.encode('.json'),
        ];
        File.fromRawPath(Uint8List.fromList(name)).writeAsStringSync(
          jsonEncode({
            'format': 2,
            'reviewers': [
              {
                'login': 'a',
                'role': 'required',
                'timeout': 60,
                'report': <String, Object>{},
              },
            ],
          }),
        );
        // The copy is read while the evaluator runs: cleanup removes it once the snapshot ends.
        final evaluate = f.onBounded!;
        String? copied;
        f.onBounded = (command) {
          copied = File(command[command.indexOf('--config') + 1])
              .readAsStringSync();
          return evaluate(command);
        };
        final escaped = '${f.tempDir.path}/reviewers-\uDCFF.json';
        expect(await snapshot(['--reviewer-config', escaped]), 0);
        final config = f.boundedCalls.single;
        final given = config[config.indexOf('--config') + 1];
        expect(given, isNot(escaped));
        expect(given.codeUnits.any((u) => u >= 0xdc80 && u <= 0xdcff), isFalse);
        expect(copied, contains('"login":"a"'));
        expect(
          f.leftovers.where((n) => n.startsWith('tmp.')),
          isEmpty,
          reason: 'the copy is removed with the material file',
        );
      },
      skip: Platform.isLinux
          ? false
          : 'a file name that is not UTF-8 needs Linux',
    );
  });

  group('one snapshot', () {
    test('looks up the repository and PR, then reads cfg, the clock, the push and the PR', () async {
      expect(await snapshot([]), 0);
      expect(kinds(), ['repo', 'prnum', 'cfg', 'rate', 'activity', 'snapshot']);
      expect(f.ghCalls[0], [
        'repo',
        'view',
        '--json',
        'owner,name',
        '--jq',
        repoViewJq,
      ]);
      expect(f.ghCalls[1], [
        'pr',
        'view',
        '--json',
        'number',
        '--jq',
        prNumberJq,
      ]);
      final cfg = cfgFor(
        logins: '',
        oid: oid,
        pushed: pushedAtJq(pushed),
        cutoff: cutoffJq('push', pushedAtJq(pushed)),
        date: date,
      );
      expect(f.ghCalls.last, [
        'api',
        'graphql',
        '-f',
        'query=$snapshotQuery',
        '-f',
        'owner=o',
        '-f',
        'name=n',
        '-F',
        'pr=7',
        '--jq',
        prJq(cfg, 'def rtimes: {};'),
      ]);
      expect(f.ghCalls[4], [
        'api',
        'repos/o/n/activity?ref=refs/heads/feature&per_page=100',
        '--jq',
        activityJq(oid),
      ]);
    });

    test(
      'prints the evaluator\'s snapshot and removes the material file',
      () async {
        results = [snapJson(sig: 'final')];
        expect(await snapshot([]), 0);
        expect(f.stdout, '${snapJson(sig: 'final')}\n');
        expect(materials, ['$material\n']);
        final call = f.boundedCalls.single;
        expect(
          [...call.take(4), ...call.skip(5)],
          [
            Platform.resolvedExecutable,
            'pr',
            'reviewers',
            '--material',
            '--head',
            oid,
          ],
        );
        expect(f.leftovers, isEmpty, reason: 'the material file is gone');
      },
    );

    test('the material file is removed when the evaluator fails', () async {
      f.onBounded = (_) => answer('', exit: 1, stderr: 'broken\n');
      expect(await snapshot([]), 1);
      expect(f.stderr, 'broken\n');
      expect(f.leftovers, isEmpty);
    });

    test('a limit on the evaluator names reviewers.py, not sw', () async {
      f.onBounded = (_) => answer(
        '',
        exit: 124,
        limitLine: 'bounded: deadline_exceeded: python3 -I\n',
      );
      // the limit comes from the result's own limit, which the fixture does not set; use the real field
      f.onBounded = (_) => GhResult(
        exitCode: 124,
        limit: BoundedLimit.deadlineExceeded,
        limitLine: 'x',
        stdout: answer('').stdout,
        stderr: answer('').stderr,
      );
      expect(await snapshot([]), 124);
      expect(f.stderr, 'bounded: deadline_exceeded: reviewers.py python3\n');
      expect(f.stdout, isEmpty);
    });

    test('a failed PR query exits 1 with gh\'s stderr', () async {
      answers({'snapshot': (_) => answer('', exit: 4, stderr: 'no\n')});
      expect(await snapshot([]), 1);
      expect(f.stderr, 'no\n');
      expect(f.stdout, isEmpty);
    });

    test(
      'a temp file that cannot be made exits 1 after the lookups, before cfg',
      () async {
        f.tempFails = true;
        expect(await snapshot([]), 1);
        expect(
          f.stderr,
          'pr-snapshot: cannot create a temp file for the reviewer evaluator\n',
        );
        expect(kinds(), ['repo', 'prnum']);
      },
    );

    test('a failed repository lookup exits with gh\'s status', () async {
      answers({'repo': (_) => answer('', exit: 7, stderr: 'nope\n')});
      expect(await snapshot([]), 7);
      expect(f.stderr, 'nope\n');
    });
  });

  group('the reaction re-check', () {
    test('reads the reaction times of the listed items and runs the query again with them', () async {
      material = snapJson(recheck: '"A","B"');
      answers({
        'recheck': (args) {
          expect(args.join(' '), contains('nodes(ids:["A","B"])'));
          return answer('{"A":"2026-11-02T11:00:00Z"}\n');
        },
      });
      expect(await snapshot([]), 0);
      expect(kinds().sublist(kinds().indexOf('snapshot')), [
        'snapshot',
        'recheck',
        'snapshot',
      ]);
      expect(
        f.ghCalls.last.last,
        contains('def rtimes: ({"A":"2026-11-02T11:00:00Z"});'),
      );
    });

    test('100 ids to a query, the answers joined with +', () async {
      final ids = [for (var i = 0; i < 101; i++) '"I$i"'].join(',');
      material = snapJson(recheck: ids);
      var n = 0;
      answers({
        'recheck': (args) {
          n++;
          return answer('{"k$n":"t"}\n');
        },
      });
      expect(await snapshot([]), 0);
      expect(n, 2);
      expect(
        f.ghCalls.last.last,
        contains('def rtimes: ({"k1":"t"} + {"k2":"t"});'),
      );
    });

    test('a failed re-check fails the snapshot', () async {
      material = snapJson(recheck: '"A"');
      answers({'recheck': (_) => answer('', exit: 1, stderr: 'x\n')});
      expect(await snapshot([]), 1);
      expect(f.stdout, isEmpty);
    });
  });

  group('the head cutoff', () {
    test('without a push in the log it is the first sighting, kept in the head record', () async {
      answers({'activity': (_) => answer('')});
      expect(await snapshot([]), 0);
      final jq = f.ghCalls.last.last;
      expect(
        jq,
        contains('cutoff: {source: "first_seen", at: ("$date" | strptime('),
      );
      expect(
        File('${state.path}/heads/o/n/7/$oid').readAsStringSync(),
        '$date\n',
      );
    });

    test('a record that cannot be published is first_seen_unsaved', () async {
      answers({'activity': (_) => answer('')});
      // a directory in the record's place: the no-clobber link fails, and nothing reads as a date
      Directory('${state.path}/heads/o/n/7/$oid').createSync(recursive: true);
      expect(await snapshot([]), 0);
      expect(f.ghCalls.last.last, contains('source: "first_seen_unsaved"'));
    });

    test('a repository the head is not in (a fork that is gone) has no activity lookup', () async {
      answers({'cfg': (_) => answer('$oid feature -\n')});
      expect(await snapshot([]), 0);
      expect(kinds(), ['repo', 'prnum', 'cfg', 'rate', 'snapshot']);
    });
  });

  group('a failing cfg', () {
    test('never fails a snapshot without a reviewer', () async {
      answers({'cfg': (_) => answer('', exit: 1, stderr: 'e\n')});
      expect(await snapshot([]), 0);
      expect(f.ghCalls.last.last, contains(cfgDefault));
    });

    test('fails one with a reviewer', () async {
      answers({'cfg': (_) => answer('', exit: 1, stderr: 'e\n')});
      final path = f
          .file(
            'c.json',
            '{"format":2,"reviewers":[{"login":"a","role":"required","timeout":60,"report":{}}]}',
          )
          .path;
      expect(await snapshot(['--reviewer-config', path]), 1);
    });

    test('a limit on any lookup fails the snapshot, in every mode, and names the limit', () async {
      answers({
        'cfg': (_) => answer(
          '',
          exit: 124,
          limitLine: 'bounded: deadline_exceeded: gh api\n',
        ),
      });
      expect(await snapshot([]), 1);
      expect(f.stderr, 'bounded: deadline_exceeded: gh api\n');
    });

    test(
      'the clock lookup names its limit itself, its stderr being discarded',
      () async {
        answers({
          'rate': (_) => answer(
            '',
            exit: 125,
            limitLine: 'bounded: response_too_large: gh api\n',
          ),
        });
        expect(await snapshot([]), 1);
        expect(f.stderr, 'bounded: response_too_large: gh api rate_limit\n');
      },
    );

    test('the activity lookup names its limit itself', () async {
      answers({
        'activity': (_) => answer(
          '',
          exit: 124,
          limitLine: 'bounded: deadline_exceeded: gh api\n',
        ),
      });
      expect(await snapshot([]), 1);
      expect(
        f.stderr,
        'bounded: deadline_exceeded: gh api repos/o/n/activity\n',
      );
    });

    test('a clock that is not a date leaves cfg unset', () async {
      answers({'rate': (_) => answer('no headers')});
      expect(await snapshot([]), 0);
      expect(f.ghCalls.last.last, contains(cfgDefault));
    });

    test(
      'a failed clock lookup that is not a limit leaves cfg unset',
      () async {
        answers({'rate': (_) => answer('', exit: 1)});
        expect(await snapshot([]), 0);
        expect(f.ghCalls.last.last, contains(cfgDefault));
        expect(f.stderr, isEmpty, reason: 'its stderr is discarded');
      },
    );
  });

  group('--wait', () {
    const first = '{"wake"';
    List<String> wakes() => [
      for (final l in f.stdout.split('\n'))
        if (l.startsWith(first)) l,
    ];

    test('wakes "changed" when the signature changes, and the claim is gone at the end', () async {
      results = [snapJson(sig: 's1'), snapJson(sig: 's2')];
      f.onSleep = (_) => expect(claims(), hasLength(1));
      expect(
        await snapshot(['--wait', '--timeout', '600', '--interval', '300']),
        0,
      );
      expect(f.sleeps, [300]);
      expect(
        f.stdout,
        '{"wake":"changed","waited":300,"filtered":0,"snapshot":${snapJson(sig: 's2')}}\n',
      );
      expect(claims(), isEmpty);
      expect(f.leftovers, isEmpty);
    });

    test('the default pause waits in process, with no sleep started', () async {
      final real = PrContext(
        scriptsDir: 's',
        bash: 'bash',
        writeOut: (_) {},
        writeErr: (_) {},
      );
      final clock = Stopwatch()..start();
      await real.sleep(1);
      expect(clock.elapsedMilliseconds, greaterThanOrEqualTo(900));
    });

    test('times out when nothing changes, never sleeping past the timeout', () async {
      expect(
        await snapshot(['--wait', '--timeout', '600', '--interval', '400']),
        0,
      );
      expect(f.sleeps, [400, 200]);
      expect(
        f.stdout,
        '{"wake":"timeout","waited":600,"filtered":0,"snapshot":${snapJson()}}\n',
      );
    });

    test('an incomplete first snapshot wakes at once, with no sleep', () async {
      results = [snapJson(complete: false)];
      expect(await snapshot(['--wait']), 0);
      expect(f.sleeps, isEmpty);
      expect(wakes().single, startsWith('{"wake":"incomplete","waited":0,'));
    });

    test(
      'a timeout that is not a whole number ends the wait at once',
      () async {
        expect(await snapshot(['--wait', '--timeout', 'soon']), 0);
        expect(f.sleeps, isEmpty);
        expect(wakes().single, startsWith('{"wake":"timeout","waited":0,'));
      },
    );

    test(
      'every poll\'s calls carry one deadline, and --logs calls do not',
      () async {
        results = [snapJson(failRuns: '11')];
        expect(await snapshot(['--wait', '--timeout', '0', '--logs']), 0);
        final polled = [
          for (var i = 0; i < f.ghCalls.length; i++)
            if (!{'repo', 'prnum', 'logs'}.contains(kindOf(f.ghCalls[i])))
              f.ghEnvs[i],
        ];
        expect(polled, isNotEmpty);
        for (final env in polled) {
          expect(
            env!['SPECWRIGHT_NET_DEADLINE_AT'],
            matches(RegExp(r'^[0-9]+\.[0-9]{6}$')),
          );
        }
        expect(f.boundedEnvs.single!['SPECWRIGHT_NET_DEADLINE_AT'], isNotNull);
        final logsAt = kinds().indexOf('logs');
        expect(f.ghEnvs[logsAt]?['SPECWRIGHT_NET_DEADLINE_AT'], isNull);
      },
    );

    test(
      'a newer claim takes over: exit 4, and only the own claim is removed',
      () async {
        f.onSleep = (_) =>
            File('${state.path}/watch/v2/o/n/7/99-newer').createSync();
        expect(await snapshot(['--wait', '--timeout', '600']), 4);
        expect(
          f.stderr,
          'pr-snapshot: a newer watcher took over PR 7; this one stops\n',
        );
        expect(claims(), ['99-newer']);
        expect(f.stdout, isEmpty);
      },
    );

    test(
      'a watcher taken over during the last poll stops, with no timeout report',
      () async {
        var polls = 0;
        answers({
          'snapshot': (_) {
            if (++polls == 2) {
              File('${state.path}/watch/v2/o/n/7/99-newer').createSync();
            }
            return answer('$material\n');
          },
        });
        expect(
          await snapshot(['--wait', '--timeout', '300', '--interval', '300']),
          4,
        );
        expect(wakes(), isEmpty);
      },
    );

    test(
      'a state directory that cannot be made polls unowned and says so',
      () async {
        final file = File('${state.path}/file')..writeAsStringSync('x');
        f.dispose();
        f = Fixture(environment: {'SPECWRIGHT_STATE_DIR': file.path});
        answers();
        expect(await snapshot(['--wait', '--timeout', '0']), 0);
        expect(
          f.stderr,
          'pr-snapshot: cannot create the watch state directory; ownership is off for PR 7 (this watcher polls unowned)\n',
        );
        expect(wakes(), hasLength(1));
      },
    );

    test('a failed last poll exits 1 and prints nothing', () async {
      var polls = 0;
      answers({
        'snapshot': (_) => ++polls == 1
            ? answer('$material\n')
            : answer('', exit: 1, stderr: 'x\n'),
      });
      expect(
        await snapshot(['--wait', '--timeout', '300', '--interval', '300']),
        1,
      );
      expect(
        f.stderr,
        endsWith('pr-snapshot: the last poll failed; GitHub state unknown\n'),
      );
      expect(wakes(), isEmpty);
    });

    test(
      'a failed first poll has no base: the first good poll becomes it',
      () async {
        var polls = 0;
        answers({
          'snapshot': (_) =>
              ++polls == 1 ? answer('', exit: 1) : answer('$material\n'),
        });
        expect(
          await snapshot(['--wait', '--timeout', '600', '--interval', '300']),
          0,
        );
        expect(f.sleeps, [300, 300]);
        expect(wakes().single, startsWith('{"wake":"timeout","waited":600,'));
      },
    );

    group('--until attention', () {
      test(
        'keeps waiting while only checks change and a CI check is pending',
        () async {
          results = [
            snapJson(sig: 's1'),
            snapJson(sig: 's2', extra: ',"checks":{"ci_pending":1}'),
            snapJson(sig: 's3', extra: ',"checks":{"ci_pending":2}'),
          ];
          expect(
            await snapshot([
              '--wait',
              '--until',
              'attention',
              '--timeout',
              '600',
              '--interval',
              '300',
            ]),
            0,
          );
          expect(
            wakes().single,
            startsWith('{"wake":"timeout","waited":600,"filtered":2,'),
          );
        },
      );

      test(
        'wakes when attn changes, DIRTY, a new failure, or no CI is pending',
        () async {
          final cases = {
            'attn': snapJson(
              sig: 's2',
              attn: 'a2',
              extra: ',"checks":{"ci_pending":1}',
            ),
            'dirty': snapJson(
              sig: 's2',
              extra: ',"merge_state":"DIRTY","checks":{"ci_pending":1}',
            ),
            'newfail': snapJson(
              sig: 's2',
              extra: ',"fail_names":["Yg=="],"checks":{"ci_pending":1}',
            ).replaceFirst('"fail_names":[],', ''),
            'idle': snapJson(sig: 's2', extra: ',"checks":{"ci_pending":0}'),
          };
          for (final e in cases.entries) {
            f.out.clear();
            evaluated = 0;
            results = [snapJson(sig: 's1'), e.value];
            expect(
              await snapshot([
                '--wait',
                '--until',
                'attention',
                '--timeout',
                '600',
                '--interval',
                '300',
              ]),
              0,
              reason: e.key,
            );
            expect(
              wakes().single,
              startsWith('{"wake":"changed","waited":300,"filtered":0,'),
              reason: e.key,
            );
          }
        },
      );

      test('a failure that was failing in the base is not new', () async {
        const failing = ',"checks":{"ci_pending":1}';
        results = [
          snapJson(sig: 's1')
              .replaceFirst('"fail_names":[]', '"fail_names":["Yg=="]'),
          snapJson(
            sig: 's2',
            extra: failing,
          ).replaceFirst('"fail_names":[]', '"fail_names":["Yg=="]'),
        ];
        expect(
          await snapshot([
            '--wait',
            '--until',
            'attention',
            '--timeout',
            '300',
            '--interval',
            '300',
          ]),
          0,
        );
        expect(
          wakes().single,
          startsWith('{"wake":"timeout","waited":300,"filtered":1,'),
        );
      });
    });
  });

  group('documents are parsed, not matched', () {
    /// The same document with a space after every `:` and `,` (the fixtures hold no string with either).
    String spaced(String compact) =>
        compact.replaceAll(':', ': ').replaceAll(',', ', ');

    test('evaluator output that is not a document fails the poll', () async {
      for (final bad in [
        'not json',
        '',
        '{"sig": "s1"',
        '{"sig": "s1"} {"sig": "s2"}',
        '[1, 2]',
      ]) {
        f.out.clear();
        f.err.clear();
        f.onBounded = (_) => answer('$bad\n');
        expect(await snapshot([]), 1, reason: 'output: $bad');
        expect(f.stdout, isEmpty, reason: 'no snapshot printed from: $bad');
        expect(f.leftovers, isEmpty, reason: 'the material file is gone');
      }
      f.out.clear();
      f.onBounded = (_) => answer('not json\n');
      expect(await snapshot(['--wait', '--timeout', '0']), 1);
      expect(f.stdout, isEmpty, reason: 'a failed poll prints no wake either');
    });

    test(
      'spaced snapshot and evaluator documents read the same as compact ones',
      () async {
        // the head and the re-check ids of the PR query's line
        material = spaced(snapJson(recheck: '"A","B"'));
        results = [spaced(snapJson())];
        answers({
          'recheck': (args) {
            expect(args.join(' '), contains('nodes(ids:["A","B"])'));
            return answer('{"A":"2026-11-02T11:00:00Z"}\n');
          },
        });
        expect(await snapshot([]), 0);
        expect(kinds().sublist(kinds().indexOf('snapshot')), [
          'snapshot',
          'recheck',
          'snapshot',
        ]);
        final call = f.boundedCalls.last;
        expect(call[call.indexOf('--head') + 1], oid);
        expect(f.stdout, '${spaced(snapJson())}\n');

        // the failing run ids of the evaluator's document
        f.ghCalls.clear();
        f.out.clear();
        material = snapJson();
        results = [spaced(snapJson(failRuns: '11,22'))];
        evaluated = 0;
        expect(await snapshot(['--logs']), 0);
        expect(
          [
            for (final c in f.ghCalls)
              if (c.first == 'run') c[2],
          ],
          ['11', '22'],
        );

        // sig, attn, the merge state, pending CI checks, failing names and completeness, while waiting
        List<String> wakes() => [
          for (final l in f.stdout.split('\n'))
            if (l.startsWith('{"wake"')) l,
        ];
        Future<void> waiting(
          List<String> docs,
          String wake, {
          String? reason,
        }) async {
          f.out.clear();
          evaluated = 0;
          results = [for (final d in docs) spaced(d)];
          expect(
            await snapshot([
              '--wait',
              '--until',
              'attention',
              '--timeout',
              '600',
              '--interval',
              '300',
            ]),
            0,
            reason: reason,
          );
          expect(wakes().single, startsWith(wake), reason: reason);
        }

        const pending = ',"checks":{"ci_pending":1}';
        await waiting(
          [snapJson(sig: 's1'), snapJson(sig: 's2', extra: pending)],
          '{"wake":"timeout","waited":600,"filtered":2,',
          reason: 'only checks changed and a CI check is pending',
        );
        await waiting(
          [
            snapJson(sig: 's1'),
            snapJson(sig: 's2', extra: ',"merge_state":"DIRTY"$pending'),
          ],
          '{"wake":"changed","waited":300,"filtered":0,',
          reason: 'DIRTY wakes',
        );
        await waiting(
          [
            snapJson(sig: 's1'),
            snapJson(sig: 's2', attn: 'a2', extra: pending),
          ],
          '{"wake":"changed","waited":300,"filtered":0,',
          reason: 'attn changed',
        );
        await waiting(
          [
            snapJson(sig: 's1'),
            snapJson(
              sig: 's2',
              extra: pending,
            ).replaceFirst('"fail_names":[]', '"fail_names":["Yg=="]'),
          ],
          '{"wake":"changed","waited":300,"filtered":0,',
          reason: 'a new failing check wakes',
        );
        await waiting(
          [snapJson(complete: false)],
          '{"wake":"incomplete","waited":0,',
          reason: 'a cut-off first snapshot wakes at once',
        );
      },
    );
  });

  group('--logs', () {
    test(
      'appends the failed log of each failing run, the last 80 lines',
      () async {
        results = [snapJson(failRuns: '11,22')];
        final long = [for (var i = 1; i <= 100; i++) 'line $i'].join('\n');
        answers({'logs': (args) => answer('$long\n')});
        expect(await snapshot(['--logs']), 0);
        final out = f.stdout;
        expect(out, contains('\n===== failed log: run 11 =====\n'));
        expect(out, contains('\n===== failed log: run 22 =====\n'));
        expect(out, isNot(contains('line 20\n')));
        expect(out, contains('line 21\nline 22\n'));
        expect(out, endsWith('line 100\n'));
        final runs = f.ghCalls.where((c) => c.first == 'run').toList();
        expect(runs, [
          ['run', 'view', '11', '-R', 'o/n', '--log-failed'],
          ['run', 'view', '22', '-R', 'o/n', '--log-failed'],
        ]);
      },
    );

    test('a failed log does not fail the snapshot', () async {
      results = [snapJson(failRuns: '11')];
      answers({'logs': (_) => answer('partial\n', exit: 1, stderr: 'oops\n')});
      expect(await snapshot(['--logs']), 0);
      expect(f.stdout, endsWith('partial\noops\n'));
    });

    test('a limit prints the limit line in the log, names it on stderr and exits 1 after the snapshot', () async {
      results = [snapJson(failRuns: '11')];
      answers({
        'logs': (_) => GhResult(
          exitCode: 124,
          limit: BoundedLimit.deadlineExceeded,
          limitLine: 'bounded: deadline_exceeded: gh run view\n',
          stdout: answer('').stdout,
          stderr: answer('').stderr,
        ),
      });
      expect(await snapshot(['--logs']), 1);
      expect(f.stdout, startsWith('${snapJson(failRuns: '11')}\n'));
      expect(
        f.stdout,
        endsWith(
          '===== failed log: run 11 =====\nbounded: deadline_exceeded: gh run view\n',
        ),
      );
      expect(f.stderr, 'bounded: deadline_exceeded: gh run view 11\n');
    });
  });
}
