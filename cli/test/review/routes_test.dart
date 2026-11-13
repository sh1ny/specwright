import 'dart:convert';
import 'dart:io';

import 'package:specwright_cli/src/review/routes.dart';
import 'package:specwright_cli/src/review/stop.dart';
import 'package:specwright_cli/src/settings/rules.dart';
import 'package:test/test.dart';

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
      ({'other': {}}, 'review.routes.other'),
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
      '[windows]\nsandbox = "x\\\" -c y"\n',
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
