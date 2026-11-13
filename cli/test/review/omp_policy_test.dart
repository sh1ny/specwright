import 'dart:convert';
import 'dart:io';

import 'package:specwright_cli/src/review/omp_policy.dart';
import 'package:test/test.dart';

void main() {
  late Directory work;
  late File module;
  late File runner;
  setUp(() {
    work = Directory.systemTemp.createTempSync('sw-omp-policy-');
    module = OmpLocalPolicy.writeTo(work);
    runner = File('${work.path}/exercise.mjs')..writeAsStringSync(harness);
  });
  tearDown(() => work.deleteSync(recursive: true));

  Future<List<Map<String, Object?>>> probe(
    List<Map<String, Object?>> cases,
  ) async {
    final input = File('${work.path}/cases.json')
      ..writeAsStringSync(jsonEncode(cases));
    final process = await Process.start('node', [
      runner.path,
      module.path,
      input.path,
    ]);
    final stdout = process.stdout.transform(utf8.decoder).join();
    final stderr = process.stderr.transform(utf8.decoder).join();
    var exited = false;
    try {
      final code = await process.exitCode.timeout(const Duration(seconds: 20));
      exited = true;
      final error = await stderr;
      expect(code, 0, reason: error);
      final result = jsonDecode(await stdout) as List;
      return [for (final item in result) (item as Map).cast<String, Object?>()];
    } finally {
      if (!exited) process.kill(ProcessSignal.sigkill);
    }
  }

  Map<String, Object?> call(
    String tool,
    Map<String, Object?> input, {
    bool read = false,
  }) => {'tool': tool, 'input': input, 'cwd': work.path, 'readContent': read};

  for (final tool in ['read', 'grep', 'glob']) {
    test(
      '$tool blocks direct, encoded, compound and aliased remote targets',
      () async {
        final cases = [
          for (final target in remoteTargets)
            call(tool, {
              'path': target,
              if (tool == 'grep') 'pattern': 'needle',
            }),
        ];
        final results = await probe(cases);
        for (var i = 0; i < cases.length; i++) {
          expect(
            results[i]['blocked'],
            isTrue,
            reason: '$tool ${remoteTargets[i]}: ${results[i]}',
          );
          expect(
            results[i]['reason'],
            contains('SPECWRIGHT_OMP_LOCAL_ONLY'),
            reason: remoteTargets[i],
          );
        }
      },
    );
  }

  test(
    'local Unicode and spaced files still return their real contents',
    () async {
      final fixture = File('${work.path}/local spaces \u03bb.txt')
        ..writeAsStringSync('local policy fixture\n');
      final results = await probe([
        call('read', {'path': fixture.path}, read: true),
        call('read', {'path': 'local spaces \u03bb.txt'}, read: true),
      ]);
      for (final result in results) {
        expect(result['blocked'], isFalse);
        expect(result['content'], 'local policy fixture\n');
      }
    },
  );

  test(
    'bare open-ended reads are forced local before native dispatch',
    () async {
      final paths = [
        'README:50-',
        'README:17-:raw',
        'README:raw:17-',
        'README:1,50-',
      ];
      final results = await probe([
        for (final path in paths) call('read', {'path': path}),
      ]);
      for (var i = 0; i < paths.length; i++) {
        expect(results[i]['blocked'], isFalse, reason: '${results[i]}');
        expect(results[i]['effectivePath'], './${paths[i]}');
      }
    },
  );

  test('local selectors, literals and multiple roots retain local execution permission', () async {
    final cases = <Map<String, Object?>>[
      for (final path in [
        './README:1-3:raw',
        'README:12',
        'README:raw',
        'README:1,3',
        'file.dart:2-9',
        'folder with spaces/file.dart',
      ])
        call('read', {'path': path}),
      for (final tool in ['grep', 'glob'])
        for (final path in [
          'src;test',
          'src,test',
          'src test',
          '["src","test"]',
          '!generated;src',
          'folder;literal, name',
          '[ab]*.dart',
          'src/{one,two}/*.dart',
        ])
          call(tool, {
            'path': path,
            if (tool == 'grep') 'pattern': 'http://text-is-not-a-target',
          }),
      call('grep', {'pattern': 'needle'}),
      call('glob', {}),
    ];
    final results = await probe(cases);
    for (var i = 0; i < cases.length; i++) {
      expect(
        results[i]['blocked'],
        isFalse,
        reason: '${cases[i]}: ${results[i]}',
      );
      expect(
        results[i].containsKey('threw'),
        isFalse,
        reason: '${cases[i]}: ${results[i]}',
      );
    }
  });

  test(
    'optional LSP permits navigation but blocks mutations and remote files',
    () async {
      const safe = [
        'diagnostics',
        'definition',
        'type_definition',
        'implementation',
        'references',
        'hover',
        'symbols',
        'status',
        'capabilities',
      ];
      const unsafe = [
        'rename',
        'code_actions',
        'rename_file',
        'reload',
        'request',
        'unknown_action',
      ];
      final cases = [
        for (final action in safe)
          call('lsp', {'action': action, 'file': 'file.dart'}),
        for (final action in unsafe)
          call('lsp', {'action': action, 'file': 'file.dart'}),
        for (final path in [
          'ssh://host/file.dart',
          'fixture-mcp:resource',
          '//host/share/file.dart',
        ])
          call('lsp', {'action': 'definition', 'file': path}),
      ];
      final results = await probe(cases);
      for (var i = 0; i < results.length; i++) {
        expect(
          results[i]['blocked'],
          i >= safe.length,
          reason: '${cases[i]}: ${results[i]}',
        );
      }
    },
  );

  test(
    'known unsafe tools cannot bypass policy by being mounted unexpectedly',
    () async {
      final results = await probe([
        for (final tool in [
          'write',
          'EVAL',
          'task',
          'retain',
          'github',
          'checkpoint',
        ])
          call(tool, {}),
      ]);
      for (final result in results) {
        expect(result['blocked'], isTrue);
        expect(result['reason'], contains('SPECWRIGHT_OMP_LOCAL_ONLY'));
      }
    },
  );

  test(
    'bad target types fail closed instead of escaping the callback',
    () async {
      final cases = [
        call('read', {'path': 7}),
        call('grep', {
          'path': ['local', 'https://example.invalid'],
          'pattern': 'needle',
        }),
        call('glob', {'path': 'bad\u0000path'}),
      ];
      final results = await probe(cases);
      for (final result in results) {
        expect(result['blocked'], isTrue, reason: '$result');
        expect(result['reason'], contains('SPECWRIGHT_OMP_LOCAL_ONLY'));
      }
    },
  );
}

const remoteTargets = [
  'http://127.0.0.1:9/file',
  'https://127.0.0.1:9/file',
  'www.example.invalid/file',
  'ssh://127.0.0.1:9/file',
  'fixture-mcp:resource',
  'issue://1',
  '//server/share/file',
  r'\\server\share\file',
  '/http://127.0.0.1:9/file',
  'folder/http://127.0.0.1:9/file',
  'http:/127.0.0.1:9/file',
  'local;http://127.0.0.1:9/file',
  'README:50-;http://127.0.0.1:9/file',
  'README:50-;other:20-',
  '["README:50-","fixture-mcp:resource"]',
  'local,http://127.0.0.1:9/file',
  'local ssh://127.0.0.1:9/file',
  'local;!ssh://127.0.0.1:9/file',
  '["local","ssh://127.0.0.1:9/file"]',
  r'["local","\u0068ttps://127.0.0.1:9/file"]',
  r'["local","http:\u002f\u002f127.0.0.1:9/file"]',
];

const harness = r'''
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const {default: register} = await import(pathToFileURL(process.argv[2]).href);
let callback;
await register({on(name, fn) {
  if (name !== 'tool_call' || callback) throw new Error('policy must only register one tool_call hook');
  callback = fn;
}});
if (!callback) throw new Error('missing tool_call hook');
const cases = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const results = [];
for (let i = 0; i < cases.length; i++) {
  const item = cases[i];
  try {
    const decision = await callback({type: 'tool_call', toolCallId: String(i), toolName: item.tool, input: item.input}, {cwd: item.cwd});
    const blocked = Boolean(decision?.block);
    const effective = decision?.input ?? item.input;
    const result = {blocked, reason: decision?.reason ?? null, effectivePath: effective.path};
    if (!blocked && item.readContent) result.content = fs.readFileSync(path.resolve(item.cwd, effective.path), 'utf8');
    results.push(result);
  } catch (error) {
    results.push({threw: String(error)});
  }
}
process.stdout.write(JSON.stringify(results));
''';
