import 'dart:convert';
import 'dart:io';

import 'package:specwright_cli/src/process/resolve.dart';
import 'package:specwright_cli/src/review/routes.dart';
import 'package:specwright_cli/src/process/launch.dart' show Unrepresentable;
import 'package:specwright_cli/src/review/run.dart';
import 'package:specwright_cli/src/review/stop.dart';
import 'package:specwright_cli/src/settings/rules.dart';
import 'package:test/test.dart';

import '../helper_support.dart';
import '../line_support.dart';

Matcher stopped(String error, String key) => isA<ReviewStop>()
    .having((e) => e.error, 'error', error)
    .having((e) => e.code, 'code', 1)
    .having((e) => e.message, 'message', contains(key));

void main() {
  late Directory work;
  late String prompt;
  setUp(() {
    work = Directory.systemTemp.createTempSync('sw-review-routes-');
    prompt = File('${work.path}/prompt.txt').absolute.path;
    File(prompt).writeAsStringSync('review the supplied change\n');
  });
  tearDown(() => work.deleteSync(recursive: true));

  ReviewCommand command(
    String route, {
    Object? settings,
    String kind = 'design',
    String? model,
    String? thinking,
    String? schema,
    String? sandbox,
    List<String> dirs = const [],
  }) => buildReviewCommand(
    route: route,
    executable: route,
    config: parseReviewRoutes(settings)[route]!,
    kind: kind,
    workDir: work,
    promptPath: prompt,
    model: model,
    thinking: thinking,
    schemaPath: schema,
    windowsSandbox: sandbox,
    allowedDirs: dirs,
  );

  group('typed route settings', () {
    test('safe OMP replacement retains fixed controls and private policy', () {
      final built = command(
        'omp',
        settings: {
          'omp': {
            'tools': ['read', 'grep', 'glob', 'lsp'],
          },
        },
        model: '@default',
      );
      expect(built.argv, containsAllInOrder(['--tools', 'read,grep,glob,lsp']));
      expect(
        built.argv,
        containsAll(['--no-skills', '--no-extensions', '--no-rules']),
      );
      expect(
        built.argv,
        containsAllInOrder(['--trusted-extension', built.policyPath]),
      );
      expect(File(built.policyPath!).existsSync(), isTrue);
      expect(built.argv.last, '@$prompt');
      expect(built.stdinPath, isNull);
    });

    test(
      'empty OMP tools use the explicit no-tools switch, never CLI defaults',
      () {
        final built = command(
          'omp',
          settings: {
            'omp': {'tools': <String>[]},
          },
        );
        expect(built.argv, contains('--no-tools'));
        expect(built.argv, isNot(contains('--tools')));
        expect(built.argv, contains('--trusted-extension'));
      },
    );

    test('extra disabling is additive and preserves the safe core', () {
      final built = command(
        'codex',
        settings: {
          'codex': {
            'disable': ['apps', 'new_feature'],
          },
        },
      );
      for (final feature in requiredDisables) {
        expect(
          built.argv,
          containsAllInOrder(['--disable', feature]),
          reason: feature,
        );
      }
      expect(built.argv, containsAllInOrder(['--disable', 'new_feature']));
      expect(built.argv, containsAllInOrder(['-s', 'read-only']));
      expect(
        built.argv,
        containsAll(['--ephemeral', '--ignore-rules', '--ignore-user-config']),
      );
      expect(built.argv, containsAllInOrder(['-c', 'web_search="disabled"']));
      expect(built.argv, isNot(contains('--enable')));
    });

    test(
      'harmless extra flags follow fixed controls and preserve prompt input',
      () {
        final built = command(
          'claude',
          settings: {
            'claude': {
              'args': ['--no-session-persistence'],
            },
          },
        );
        expect(
          built.argv,
          containsAllInOrder(['--restricted', '--no-session-persistence']),
        );
        expect(built.stdinPath, prompt);
      },
    );

    for (final (raw, key) in <(Object?, String)>[
      ({'other': <String, Object?>{}}, 'review.routes.other'),
      (
        {
          'codex': {
            'tools': ['read'],
          },
        },
        'review.routes.codex.tools',
      ),
      (
        {
          'omp': {
            'disable': ['apps'],
          },
        },
        'review.routes.omp.disable',
      ),
      (
        {
          'omp': {'tools': 'read,grep'},
        },
        'review.routes.omp.tools',
      ),
      (
        {
          'claude': {
            'args': [true],
          },
        },
        'review.routes.claude.args',
      ),
      (
        {
          'codex': {'disable': false},
        },
        'review.routes.codex.disable',
      ),
      (['omp'], 'review.routes'),
    ]) {
      test('bad shape stops with its setting key: $key $raw', () {
        expect(
          () => parseReviewRoutes(raw),
          throwsA(stopped('bad_route_setting', key)),
        );
      });
    }

    test('wrong-route diagnostics name the accepted keys', () {
      expect(
        () => parseReviewRoutes({
          'codex': {
            'tools': ['read'],
          },
        }),
        throwsA(
          isA<ReviewStop>().having(
            (e) => e.message,
            'accepted keys',
            allOf(contains('disable'), contains('args')),
          ),
        ),
      );
    });
  });

  group('refused capabilities', () {
    for (final tool in [
      'Bash',
      'PowerShell',
      'Edit',
      'MultiEdit',
      'Write',
      'NotebookEdit',
      'WebFetch',
      'WebSearch',
      'Task',
      'Agent',
      'mcp__server__read',
    ]) {
      test('claude refuses $tool regardless of case', () {
        expect(
          () => parseReviewRoutes({
            'claude': {
              'tools': ['Read', tool.toUpperCase()],
            },
          }),
          throwsA(
            stopped('route_setting_unsafe', 'review.routes.claude.tools'),
          ),
        );
      });
    }
    for (final tool in ompUnsafeTools) {
      test('OMP refuses $tool regardless of case', () {
        expect(
          () => parseReviewRoutes({
            'omp': {
              'tools': ['read', tool.toUpperCase()],
            },
          }),
          throwsA(stopped('route_setting_unsafe', 'review.routes.omp.tools')),
        );
      });
    }
    for (final (route, flags) in refusedFlags.entries.map(
      (e) => (e.key, e.value),
    )) {
      for (final flag in flags) {
        test('$route refuses owned/unsafe flag $flag', () {
          expect(
            () => parseReviewRoutes({
              route: {
                'args': [flag],
              },
            }),
            throwsA(
              stopped('route_setting_unsafe', 'review.routes.$route.args'),
            ),
          );
          if (flag.startsWith('--')) {
            expect(
              () => parseReviewRoutes({
                route: {
                  'args': ['$flag=value'],
                },
              }),
              throwsA(
                stopped('route_setting_unsafe', 'review.routes.$route.args'),
              ),
            );
          }
        });
      }
    }
    test('short attached sandbox cannot override the core', () {
      expect(
        () => parseReviewRoutes({
          'codex': {
            'args': ['-sdanger-full-access'],
          },
        }),
        throwsA(stopped('route_setting_unsafe', 'review.routes.codex.args')),
      );
    });
    for (final assignment in [
      ' sandbox_mode = "danger-full-access"',
      'features={apps=true}',
      '"features"."apps"=true',
      "'features'.'apps'=true",
      'windows={sandbox="none"}',
      'sandbox_workspace_write={network_access=true}',
      'permissions={network=true}',
      'tools.web_search=true',
      'mcp_servers.server={command="evil"}',
      'hooks=[]',
      'model="other"',
      'model_reasoning_effort="low"',
      'profile="unsafe"',
      'profiles.unsafe.web_search="live"',
      'profiles={unsafe={web_search="live"}}',
      '"profiles"."unsafe"."features"={apps=true}',
      'notify=["sh","-c","echo unsafe"]',
      'model_provider="owned"',
      'model_providers.owned.auth.command="program"',
      'model_providers={owned={auth={command="program"}}}',
      '"model_providers"."owned"."auth"={command="program",args=["arg"]}',
    ]) {
      for (final args in <List<String>>[
        ['-c', assignment],
        ['--config=$assignment'],
        ['-c$assignment'],
      ]) {
        test('protected configuration cannot be nested/quoted: $args', () {
          expect(
            () => parseReviewRoutes({
              'codex': {'args': args},
            }),
            throwsA(
              stopped('route_setting_unsafe', 'review.routes.codex.args'),
            ),
          );
        });
      }
    }
    test('unprotected Codex configuration is not an allowlist', () {
      final routes = parseReviewRoutes({
        'codex': {
          'args': ['-c', 'unrelated=true'],
        },
      });
      expect(routes['codex']!.args, ['-c', 'unrelated=true']);
    });
  });

  group('reviewer command contracts', () {
    test(
      'OMP overlay disables memory, learning, semantic search and fetching',
      () {
        final built = command('omp');
        final index = built.argv.indexOf('--config');
        final overlay = loadSettings(
          File(built.argv[index + 1]).readAsStringSync(),
        );
        for (final name in ['autolearn', 'memories', 'find', 'fetch']) {
          expect((overlay[name] as Map)['enabled'], isFalse, reason: name);
        }
        expect(built.argv, containsAllInOrder(['--tools', 'read,grep,glob']));
        expect(built.policyId, 'local-only-v1');
        expect(built.policySha256, matches(r'^[0-9a-f]{64}$'));
        expect(built.argv, isNot(contains('find')));
      },
    );
    test('OMP role owns reasoning while provider/id accepts a level', () {
      expect(
        command('omp', model: '@default', thinking: 'high').argv,
        isNot(contains('--thinking')),
      );
      expect(
        command('omp', model: 'provider/model', thinking: 'high').argv,
        containsAllInOrder(['--thinking', 'high']),
      );
    });
    test(
      'Codex consumes bounded JSON events and stdin, never an answer file',
      () {
        final built = command(
          'codex',
          model: 'model-name',
          thinking: 'high',
          sandbox: 'elevated',
        );
        expect(built.argv, containsAllInOrder(['--json', '-m', 'model-name']));
        expect(
          built.argv,
          containsAllInOrder(['-c', 'model_reasoning_effort="high"']),
        );
        expect(
          built.argv,
          containsAllInOrder(['-c', 'windows.sandbox="elevated"']),
        );
        expect(built.argv, isNot(contains('-o')));
        expect(built.argv, isNot(contains('--output-last-message')));
        expect(built.argv.last, '-');
        expect(built.stdinPath, prompt);
      },
    );
    test('preship schemas use native CLI forms', () {
      final schema = File('${work.path}/schema.json')
        ..writeAsStringSync(
          r'{"$schema":"https://json-schema.org/draft/2020-12/schema","type":"object"}',
        );
      final codex = command('codex', kind: 'preship', schema: schema.path);
      expect(codex.argv, containsAllInOrder(['--output-schema', schema.path]));
      final claude = command(
        'claude',
        kind: 'preship',
        schema: schema.path,
        dirs: [work.path],
      );
      final value = jsonDecode(
        claude.argv[claude.argv.indexOf('--json-schema') + 1],
      ) as Map;
      expect(value['type'], 'object');
      expect(value.containsKey(r'$schema'), isFalse);
      expect(claude.argv, containsAllInOrder(['--add-dir', work.path]));
      expect(
        claude.argv,
        containsAll([
          '--safe-mode',
          '--disable-slash-commands',
          '--restricted',
        ]),
      );
    });
    test(
      'OMP version evidence floor is not bypassed by an unparseable version',
      () {
        for (final version in ['18.18.9', 'omp/18.18.9', 'nonsense', '']) {
          expect(ompVersionSupported(version), isFalse, reason: version);
        }
        for (final version in ['18.19.0', 'omp/18.19.0', '19.0.0']) {
          expect(ompVersionSupported(version), isTrue, reason: version);
        }
      },
    );
  });

  group('Codex Windows TOML forwarding', () {
    String configure(String text) {
      File('${work.path}/config.toml').writeAsStringSync(text);
      return work.path;
    }

    test('reads quoted table/key and escaped TOML string as a plain name', () {
      final home = configure('["windows"]\n"sandbox" = "elevated"\n');
      expect(
        readWindowsSandbox(windows: true, environment: {'CODEX_HOME': home}),
        'elevated',
      );
      expect(
        readWindowsSandbox(windows: false, environment: {'CODEX_HOME': home}),
        isNull,
      );
    });
    for (final origin in ['USERPROFILE', 'HOME', 'HOMEDRIVE/HOMEPATH']) {
      test('default profile config uses .codex through $origin', () {
        final profile = Directory('${work.path}/profile')..createSync();
        File('${profile.path}/config.toml')
            .writeAsStringSync('[windows]\nsandbox = "wrong-location"\n');
        Directory('${profile.path}/.codex').createSync();
        File('${profile.path}/.codex/config.toml')
            .writeAsStringSync('[windows]\nsandbox = "elevated"\n');
        final environment = <String, String>{
          'CODEX_HOME': '',
          if (origin != 'HOMEDRIVE/HOMEPATH') origin: profile.path,
          if (origin == 'HOMEDRIVE/HOMEPATH') ...{
            'HOMEDRIVE': work.path,
            'HOMEPATH': '${Platform.pathSeparator}profile',
          },
        };
        expect(
          readWindowsSandbox(windows: true, environment: environment),
          'elevated',
        );
      });
    }

    for (final text in [
      '[windows]\nsandbox = "unterminated\n',
      '[windows]\nsandbox = ["elevated"]\n',
      '[windows]\nsandbox = "x\\" -c y"\n',
      '[other]\nsandbox = "elevated"\n',
    ]) {
      test('bad or non-plain sandbox is not forwarded: $text', () {
        final home = configure(text);
        expect(
          readWindowsSandbox(windows: true, environment: {'CODEX_HOME': home}),
          isNull,
        );
      });
    }
    test('missing and unreadable config do not create a setting', () {
      expect(
        readWindowsSandbox(
          windows: true,
          environment: {'CODEX_HOME': work.path},
        ),
        isNull,
      );
      Directory('${work.path}/config.toml').createSync();
      expect(
        readWindowsSandbox(
          windows: true,
          environment: {'CODEX_HOME': work.path},
        ),
        isNull,
      );
    });
  });

  // D5 / C1: a route probe that cannot start skips the route; it is not an
  // `internal_error`. `runReviewOperation` takes the environment and helper
  // the probes run with (they are `Platform.environment` and `sw` itself today).
  group('route probes on Windows (D5)', () {
    final windowsOnly = Platform.isWindows ? null : 'Windows only';
    late Directory built;
    late List<String> helper;

    // the short `--version` probes start for real, so the helper is `sw`
    setUpAll(() async {
      if (!Platform.isWindows) return;
      built = Directory.systemTemp.createTempSync('sw-routes-helper-');
      helper = await buildHelper(built);
    });
    tearDownAll(() {
      if (Platform.isWindows) built.deleteSync(recursive: true);
    });

    Future<Map<String, Object?>> select(Map<String, String> env, String model) {
      final settings = File('${work.path}\\specwright.yaml')
        ..writeAsStringSync(
          'review:\n  order: [omp, codex]\n  models:\n    omp: "$model"\n',
        );
      return runReviewOperation(
        argv: ['select', '--runtime', 'claude', '--settings', settings.path],
        environment: withEnv(env),
        helperCommand: helper,
      );
    }

    Map<String, String?> reasons(Map<String, Object?> out) => {
      for (final item in out['skipped']! as List<Object?>)
        (item! as Map)['route'] as String: (item as Map)['reason'] as String?,
    };

    test('windows: omp.cmd probe over the batch cap skips the route', () async {
      final bin = Directory('${work.path}\\bin')..createSync();
      File('${bin.path}\\omp.cmd').writeAsStringSync(
        '@echo off\r\nif "%~1"=="--version" echo omp/99.0.0\r\n',
      );
      final out = await select({
        'PATH': bin.path,
        'PATHEXT': '.CMD;.EXE',
      }, 'provider/${'x' * 9000}');
      expect(
        reasons(out)['omp'],
        'unrepresentable command line: ${bin.path}\\omp.cmd',
      );
      expect(out['route'], 'subagent');
    }, skip: windowsOnly);

    test(
      'windows: models find over the limit falls through',
      () async {
        final bin = Directory('${work.path}\\bin')..createSync();
        // a native omp that answers `--version` and nothing else
        final source = File('${work.path}\\omp.dart')
          ..writeAsStringSync("void main() { print('omp/99.0.0'); }\n");
        final compiled = await Process.run(Platform.resolvedExecutable, [
          'compile',
          'exe',
          '-o',
          '${bin.path}\\omp.exe',
          source.path,
        ]);
        expect(compiled.exitCode, 0, reason: '${compiled.stderr}');
        final env = {'PATH': bin.path, 'PATHEXT': '.EXE;.CMD'};
        final exe = '${bin.path}\\omp.exe';

        // over the limit as given: the older check names the resolved path
        var out = await select(env, 'provider/${'x' * 33000}');
        expect(reasons(out)['omp'], 'unrepresentable command line: $exe');
        expect(out['route'], 'subagent');

        // a resolved line of exactly 32,767 units: only the check this change
        // adds refuses it, and the reason is the failed-probe one of before
        final fill =
            32767 - lineUnits([exe, 'models', 'find', 'x', '--json']) + 1;
        out = await select(env, 'provider/${'x' * fill}');
        expect(reasons(out)['omp'], 'probe failed: omp models find exited 127');
        expect(out['route'], 'subagent');
      },
      skip: windowsOnly,
      timeout: const Timeout(Duration(minutes: 3)),
    );
  });

  // D5 / C13: an explicit `--route omp` run keeps today's mapping. An old-check
  // refusal of the `--version` probe line stops the run as `Unrepresentable`
  // (`not_utf8` at the command); a line only a new check refuses is a failed
  // start, a null version and `omp_too_old`. A path long enough to reach the
  // limit cannot exist on disk, so the resolver is injected: nothing starts.
  group('explicit omp run, version probe on Windows (D5)', () {
    final windowsOnly = Platform.isWindows ? null : 'Windows only';

    Future<Map<String, Object?>> runOmp(
      String ompPath,
      Map<String, String> env,
    ) {
      final settings = File('${work.path}\\specwright.yaml')
        ..writeAsStringSync('');
      final promptFile = File('${work.path}\\design.md')
        ..writeAsStringSync('review the design\n');
      return runReviewOperation(
        argv: [
          'run',
          '--kind',
          'design',
          '--route',
          'omp',
          '--out',
          '${work.path}\\review.md',
          '--change',
          'demo-change',
          '--prompt-file',
          promptFile.path,
          '--settings',
          settings.path,
        ],
        environment: withEnv(env),
        helperCommand: const [r'C:\sw\sw.exe', '__exec'],
        resolve: (name, environment, {workingDirectory}) => name == 'omp'
            ? ompPath
            : resolveCommand(
                name,
                environment,
                workingDirectory: workingDirectory,
              ),
      );
    }

    String pathOfProbeLine(int units) {
      final path = r'C:\' + 'p' * (units - 10 - 3);
      expect(lineUnits([path, '--version']), units);
      return path;
    }

    test('test_omp_version_probe_over_the_limit_is_not_utf8', () async {
      await expectLater(
        runOmp(pathOfProbeLine(32768), const {}),
        throwsA(
          isA<Unrepresentable>().having((e) => e.what, 'what', 'command line'),
        ),
      );
    }, skip: windowsOnly);

    test('test_omp_version_probe_of_32767_units_is_omp_too_old', () async {
      await expectLater(
        runOmp(pathOfProbeLine(32767), const {}),
        throwsA(
          isA<ReviewStop>().having((e) => e.error, 'error', 'omp_too_old'),
        ),
      );
    }, skip: windowsOnly);

    test('test_omp_cmd_version_probe_raw_line_is_omp_too_old', () async {
      // COMSPEC names nothing, so the interpreter is under SYSTEMROOT; the
      // short batch payload fits and only the raw line is over the limit
      final env = {
        'COMSPEC': '${work.path}\\no-such-cmd.exe',
        'SYSTEMROOT': r'C:\' + 'r' * 32700,
      };
      await expectLater(
        runOmp(r'C:\shim\omp.cmd', env),
        throwsA(
          isA<ReviewStop>().having((e) => e.error, 'error', 'omp_too_old'),
        ),
      );
    }, skip: windowsOnly);
  });
}

const requiredDisables = [
  'apps',
  'browser_use',
  'browser_use_external',
  'computer_use',
  'in_app_browser',
  'image_generation',
  'memories',
  'hooks',
  'plugins',
  'remote_plugin',
  'tool_suggest',
  'skill_search',
  'skill_mcp_dependency_install',
  'goals',
  'sleep_tool',
];

const ompUnsafeTools = [
  'bash',
  'edit',
  'write',
  'python',
  'notebook',
  'browser',
  'computer',
  'task',
  'web_search',
  'fetch',
  'ask',
  'learn',
  'manage_skill',
  'find',
  'eval',
  'ast_edit',
  'debug',
  'ida',
  'github',
  'security_scan',
  'checkpoint',
  'rewind',
  'context_notes',
  'new_context',
  'memory_edit',
  'retain',
  'recall',
  'reflect',
  'goal',
  'vibe_spawn',
  'vibe_send',
  'vibe_wait',
  'vibe_kill',
  'vibe_list',
];

const refusedFlags = {
  'claude': [
    '-p',
    '--print',
    '--tools',
    '--allowedTools',
    '--allowed-tools',
    '--disallowedTools',
    '--disallowed-tools',
    '--permission-mode',
    '--dangerously-skip-permissions',
    '--add-dir',
    '--settings',
    '--setting-sources',
    '--mcp-config',
    '--plugin-dir',
    '--agents',
    '--restricted',
    '--safe-mode',
    '--disable-slash-commands',
    '--output-format',
    '--json-schema',
    '--model',
    '--effort',
    '-c',
    '--continue',
    '-r',
    '--resume',
    '--fork-session',
  ],
  'omp': [
    '-p',
    '--print',
    '--tools',
    '--no-tools',
    '--no-skills',
    '--no-extensions',
    '--no-rules',
    '--session-dir',
    '--no-session',
    '-c',
    '--continue',
    '-r',
    '--resume',
    '--restore',
    '-e',
    '--extension',
    '--trusted-extension',
    '--hook',
    '--skills',
    '--config',
    '--profile',
    '--mode',
    '--model',
    '--thinking',
    '--goal',
    '--plan-yolo',
    '--prewalk',
    '--prewalk-into',
  ],
  'codex': [
    '-s',
    '--sandbox',
    '--dangerously-bypass-approvals-and-sandbox',
    '--yolo',
    '--dangerously-bypass-hook-trust',
    '--approve-for-me',
    '--not-so-yolo',
    '--full-auto',
    '--enable',
    '-p',
    '--profile',
    '--add-dir',
    '-C',
    '--cd',
    '--worktree',
    '--ephemeral',
    '--ignore-rules',
    '--ignore-user-config',
    '--output-schema',
    '-o',
    '--output-last-message',
    '--json',
    '-m',
    '--model',
  ],
};
