import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:path/path.dart' as p;
import 'package:specwright_cli/src/process/resolve.dart';
import 'package:specwright_cli/src/review/run.dart';
import 'package:specwright_cli/src/review/stop.dart';
import 'package:test/test.dart';

import '../helper_support.dart';

const revise = 'VERDICT: REVISE\nCHANGES_APPLIED: n/a\n';
const conditional =
    'VERDICT: APPROVE_WITH_CHANGES\nCHANGES_APPLIED: no\n\n'
    '## Required Changes\nWait for exit.\n';
const approve = 'VERDICT: APPROVE\nCHANGES_APPLIED: n/a\n';

void main() {
  late Directory built;
  late List<String> helper;
  late Directory work;
  late Directory repo;
  late File review;
  late File design;
  late File selection;
  late String branch;

  setUpAll(() async {
    built = Directory.systemTemp.createTempSync('sw-publication-helper-');
    helper = await buildHelper(built);
  });
  tearDownAll(() => built.deleteSync(recursive: true));

  Future<Map<String, Object?>> command(
    List<String> argv, {
    CommandResolver? resolve,
    File Function(String)? createFile,
  }) => IOOverrides.runZoned(
    () => runReviewOperation(
      argv: argv,
      environment: {
        ...Platform.environment,
        'SPECWRIGHT_STATE_DIR': p.join(work.path, 'state'),
      },
      helperCommand: helper,
      resolve: resolve,
    ),
    getCurrentDirectory: () => repo,
    createFile: createFile,
  );

  setUp(() async {
    work = Directory.systemTemp.createTempSync('sw-review-publication-');
    addTearDown(() => work.deleteSync(recursive: true));
    repo = Directory(p.join(work.path, 'repo'))..createSync();
    branch = 'feat/example';
    final gitEnv = {
      ...Platform.environment,
      'GIT_CONFIG_NOSYSTEM': '1',
      'GIT_CONFIG_GLOBAL': Platform.isWindows ? 'NUL' : '/dev/null',
    };
    Future<void> git(List<String> args) async {
      final result = await Process.run(
        'git',
        args,
        workingDirectory: repo.path,
        environment: gitEnv,
      );
      expect(result.exitCode, 0, reason: '${result.stderr}');
    }

    await git(['init', '-q', '-b', branch]);
    await git([
      '-c',
      'user.email=review@example.invalid',
      '-c',
      'user.name=Review Test',
      '-c',
      'commit.gpgsign=false',
      'commit',
      '--allow-empty',
      '-qm',
      'initial',
    ]);
    File(p.join(repo.path, 'openspec', 'specwright.yaml'))
      ..createSync(recursive: true)
      ..writeAsStringSync(
        'review:\n  cross_model: false\n  design_max_rounds: 1\n',
      );
    final change = Directory(
      p.join(repo.path, 'openspec', 'changes', 'example'),
    )..createSync(recursive: true);
    review = File(p.join(change.path, 'review.md'));
    design = File(p.join(change.path, 'design.md'))
      ..writeAsStringSync('TIER: FULL\nOriginal design.\n');
    File(p.join(change.path, 'proposal.md')).writeAsStringSync('Proposal.\n');
    selection = File(p.join(work.path, 'selection.json'))
      ..writeAsStringSync(
        jsonEncode(
          await command([
            'select',
            '--change-review',
            '--runtime',
            'other',
            '--branch',
            branch,
          ]),
        ),
      );
  });

  List<String> recordArgs() => [
    'record',
    '--kind',
    'design',
    '--change-review',
    '--change',
    'example',
    '--branch',
    branch,
    '--out',
    review.path,
    '--selection',
    selection.path,
  ];

  Future<Map<String, Object?>> start({bool recheck = false}) =>
      command([...recordArgs(), '--scratch', if (recheck) '--recheck']);

  List<String> result(Map<String, Object?> attempt, String verdict) {
    final scratch = attempt['scratch']! as String;
    File(scratch).writeAsStringSync(verdict);
    return [
      ...recordArgs(),
      '--route',
      'subagent',
      '--result',
      scratch,
      '--attempt',
      attempt['attempt']! as String,
    ];
  }

  Future<void> scope() => command([
    'design-step',
    '--branch',
    branch,
    '--out',
    review.path,
    '--round',
    '1',
    '--choice',
    'scoped-pass',
    '--detail',
    'Only the requested wait.',
  ]);

  test(
    'Git deadline during publication preserves the verdict and scoped pass',
    () async {
      await command(result(await start(), revise));
      await scope();
      final attempt = result(await start(), approve);
      final recorded = review.readAsBytesSync();
      var arm = false;
      var fired = false;
      await expectLater(
        runZoned(
          () => command(
            attempt,
            resolve: (name, env, {workingDirectory}) {
              if (name == 'git' && !fired) arm = true;
              return resolveCommand(
                name,
                env,
                workingDirectory: workingDirectory,
              );
            },
          ),
          zoneSpecification: ZoneSpecification(
            createTimer: (self, parent, zone, delay, callback) {
              // The first Git read of this record call starts under the real lock.
              // Fire its newly armed timer before the helper can process that read.
              if (arm) {
                arm = false;
                fired = true;
                callback();
                return parent.createTimer(zone, delay, () {});
              }
              return parent.createTimer(zone, delay, callback);
            },
          ),
        ),
        throwsA(
          isA<ReviewStop>().having(
            (e) => e.error,
            'error',
            'design_git_timeout',
          ),
        ),
      );
      expect(fired, isTrue);
      expect(review.readAsBytesSync(), recorded);
      await command(result(await start(), approve));
      final verdict = await command([
        'design-step',
        '--branch',
        branch,
        '--out',
        review.path,
      ]);
      expect(verdict['status'], 'pass');
    },
    timeout: const Timeout(Duration(minutes: 3)),
  );

  test(
    'a failed report write leaves the original conditional baseline usable',
    () async {
      await command(result(await start(), conditional));
      await scope();
      final recorded = review.readAsBytesSync();
      design.writeAsStringSync('TIER: FULL\nWait for exit.\n');
      final attempt = result(await start(), conditional);
      final outside = Zone.current;
      await expectLater(
        command(
          attempt,
          createFile: (path) {
            if (path.startsWith('${review.path}.') && path.endsWith('.tmp')) {
              throw FileSystemException('injected failed publication', path);
            }
            return outside.run(() => File(path));
          },
        ),
        throwsA(isA<FileSystemException>()),
      );
      expect(review.readAsBytesSync(), recorded);
      final recheck = await start(recheck: true);
      final prior = recheck['prior_artifacts']! as Map<String, Object?>;
      expect(
        File(prior['design']! as String).readAsStringSync(),
        contains('Original design.'),
      );
      await command(result(recheck, conditional.replaceFirst('no', 'yes')));
      expect(review.readAsStringSync(), contains('CHANGES_APPLIED: yes'));
    },
    timeout: const Timeout(Duration(minutes: 3)),
  );
}
