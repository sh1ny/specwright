import 'dart:convert';
import 'dart:io';

import 'package:specwright_cli/src/cli.dart';
import 'package:specwright_cli/src/commands/vcs.dart';
import 'package:specwright_cli/src/vcs/args.dart';
import 'package:specwright_cli/src/vcs/codec.dart';
import 'package:specwright_cli/src/vcs/document.dart';
import 'package:specwright_cli/src/vcs/stop.dart';
import 'package:test/test.dart';

List<int> _records(List<String> records) => [
  for (final r in records) ...[...utf8.encode(r), 0],
];

VcsStop _stopOf(void Function() body) {
  try {
    body();
  } on VcsStop catch (e) {
    return e;
  }
  fail('expected a VcsStop');
}

void main() {
  late Directory repo;
  late Directory other;
  setUp(() {
    repo = Directory.systemTemp.createTempSync('claude-ncv-g2-repo-');
    other = Directory.systemTemp.createTempSync('claude-ncv-g2-code-');
  });
  tearDown(() {
    repo.deleteSync(recursive: true);
    other.deleteSync(recursive: true);
  });

  group('parseHandoff', () {
    test('reads the scripts dir, the bash and the operation', () {
      final h = parseHandoff(
        _records(['/s', '/bin/bash', 'state', '--repo', '/r']),
        handoffUsage,
      );
      expect(h.scriptsDir, '/s');
      expect(h.bash, '/bin/bash');
      expect(h.argv, ['state', '--repo', '/r']);
    });

    test('keeps empty records', () {
      final h = parseHandoff(
        _records(['/s', '/b', 'commit', '']),
        handoffUsage,
      );
      expect(h.argv, ['commit', '']);
    });

    test(r'a record that is not UTF-8 is NotUtf8 naming it with \xHH', () {
      expect(
        () => parseHandoff([
          ..._records(['/s', '/b', 'commit', '']),
          0x61,
          0xff,
          0,
        ], handoffUsage),
        throwsA(
          isA<NotUtf8>()
              .having((e) => e.what, 'what', 'argument 3')
              .having((e) => e.shown, 'shown', r'a\xFF'),
        ),
      );
    });

    test('the scripts directory and the bash path are named as such', () {
      for (final (index, what) in [
        (0, 'scripts directory'),
        (1, 'bash path'),
      ]) {
        final records = [
          for (var i = 0; i < 4; i++)
            if (i == index) [0x61, 0xff, 0] else [...utf8.encode('x$i'), 0],
        ].expand((r) => r).toList();
        expect(
          () => parseHandoff(records, handoffUsage),
          throwsA(isA<NotUtf8>().having((e) => e.what, 'what', what)),
        );
      }
    });

    test('fewer than three records is a usage stop with exit 2', () {
      for (final input in [
        <int>[],
        _records(['/s']),
        _records(['/s', '/b']),
      ]) {
        final stop = _stopOf(() => parseHandoff(input, handoffUsage));
        expect(stop.error, 'usage');
        expect(stop.message, handoffUsage);
        expect(stop.code, 2);
      }
    });

    test('a stop carries the usage text the caller passed', () {
      final stop = _stopOf(() => parseHandoff(<int>[], 'usage: sw commit'));
      expect(stop.message, 'usage: sw commit');
    });

    test('an unterminated last record is a usage stop with exit 2', () {
      final stop = _stopOf(
        () => parseHandoff([
          ..._records(['/s', '/b']),
          ...utf8.encode('state'),
        ], handoffUsage),
      );
      expect(stop.error, 'usage');
      expect(stop.code, 2);
    });
  });

  group('parseVcsArguments', () {
    VcsRequest parse(List<String> extra) => parseVcsArguments([
      'state',
      '--repo',
      repo.path,
      '--role',
      'code',
      ...extra,
    ]);

    test('reads every option and flag into the request', () {
      final r = parseVcsArguments([
        'commit',
        '--repo',
        repo.path,
        '--role',
        'store',
        '--code',
        other.path,
        '--branch',
        'feat/a',
        '--message-file',
        'm.txt',
        '--scope',
        's',
        '--operation',
        'op',
        '--login',
        'bot',
        '--main',
        'trunk',
        '--prefix',
        'p',
        '--merged-commit',
        'abc',
        '--force',
        '--no-tags',
        '--quiet',
        '--remote-branch',
        '--',
        'a b.txt',
        '--force',
        '--',
      ]);
      expect(r.command, 'commit');
      expect(r.repo, repo.path);
      expect(r.role, 'store');
      expect(r.code, other.path);
      expect(r.branch, 'feat/a');
      expect(r.messageFile, 'm.txt');
      expect(r.scope, 's');
      expect(r.operation, 'op');
      expect(r.login, 'bot');
      expect(r.main, 'trunk');
      expect(r.prefix, 'p');
      expect(r.mergedCommit, 'abc');
      expect([
        r.force,
        r.noTags,
        r.quiet,
        r.remoteBranch,
      ], everyElement(isTrue));
      expect(r.paths, ['a b.txt', '--force', '--']);
    });

    test('flags default to false and options to null', () {
      final r = parse([]);
      expect([
        r.force,
        r.noTags,
        r.quiet,
        r.remoteBranch,
      ], everyElement(isFalse));
      expect(r.branch, isNull);
      expect(r.paths, isEmpty);
    });

    test('--code defaults to --repo for the code role', () {
      expect(parse([]).code, repo.path);
    });

    test('an empty --code also defaults to --repo for the code role', () {
      expect(parse(['--code', '']).code, repo.path);
    });

    test('a later option wins', () {
      final r = parse(['--branch', 'a', '--branch', 'b']);
      expect(r.branch, 'b');
    });

    test('an option value may be --', () {
      expect(parse(['--branch', '--']).branch, '--');
    });

    test('a missing command is a usage stop', () {
      final stop = _stopOf(() => parseVcsArguments([]));
      expect(
        (stop.error, stop.message, stop.code),
        ('usage', 'missing command', 2),
      );
    });

    test('an unknown option is a usage stop', () {
      for (final extra in [
        ['--bogus'],
        ['--bran', 'x'],
        ['-x'],
      ]) {
        final stop = _stopOf(() => parse(extra));
        expect((stop.error, stop.code), ('usage', 2), reason: '$extra');
      }
    });

    test('a value-taking option at the end needs a value', () {
      final stop = _stopOf(() => parse(['--branch']));
      expect((stop.error, stop.code), ('usage', 2));
    });

    test('the equals form matches the two-word form', () {
      final r = parseVcsArguments([
        'state',
        '--repo=${repo.path}',
        '--role=code',
        '--branch=--force',
      ]);
      expect((r.repo, r.role, r.branch), (repo.path, 'code', '--force'));
    });

    test('a word before -- is a usage stop', () {
      for (final extra in [
        ['stray', '--', 'a.txt'],
        ['stray'],
        ['--branch', 'b', 'stray', '--', 'a.txt'],
        ['--prefix', '--', 'a.txt'],
      ]) {
        final stop = _stopOf(() => parse(extra));
        expect((stop.error, stop.code), ('usage', 2), reason: '$extra');
      }
    });

    test('a -- that is an option value is not the separator', () {
      expect(parse(['--prefix', '--', '--', 'a.txt']).paths, ['a.txt']);
      final r = parse(['--message-file', '--prefix', '--', 'a.txt']);
      expect(r.messageFile, '--prefix');
      expect(r.paths, ['a.txt']);
    });

    test('an unknown command is a usage stop', () {
      final stop = _stopOf(
        () => parseVcsArguments([
          'frobnicate',
          '--repo',
          repo.path,
          '--role',
          'code',
        ]),
      );
      expect(
        (stop.error, stop.message, stop.code),
        ('usage', 'unknown command: frobnicate', 2),
      );
    });

    test('option errors come before the unknown-command error', () {
      final stop = _stopOf(() => parseVcsArguments(['frobnicate', '--bogus']));
      expect((stop.error, stop.code), ('usage', 2));
      expect(stop.message, isNot('unknown command: frobnicate'));
    });

    test('every known command is accepted', () {
      for (final c in [
        'probe',
        'state',
        'branch-create',
        'switch',
        'commit',
        'merge',
        'delete-branch',
        'fetch-main',
        'pull',
        'push',
        'advance',
        'plan',
      ]) {
        final r = parseVcsArguments([c, '--repo', repo.path, '--role', 'code']);
        expect(r.command, c);
      }
    });

    const usageLine =
        'usage: vcs.sh <command> --repo <dir> --role code|store '
        '[--code <dir>] [options] [-- paths...]';

    test('a missing --repo or a bad --role gives the usage line', () {
      for (final args in [
        ['state', '--role', 'code'],
        ['state', '--repo', '', '--role', 'code'],
        ['state', '--repo', 'x'],
        ['state', '--repo', 'x', '--role', 'other'],
      ]) {
        final stop = _stopOf(() => parseVcsArguments(args));
        expect((stop.error, stop.message, stop.code), ('usage', usageLine, 2));
      }
    });

    test('the store role needs --code', () {
      for (final extra in [
        <String>[],
        ['--code', ''],
      ]) {
        final stop = _stopOf(
          () => parseVcsArguments([
            'state',
            '--repo',
            repo.path,
            '--role',
            'store',
            ...extra,
          ]),
        );
        expect(
          (stop.error, stop.message, stop.code),
          ('usage', '--code is required when --role store', 2),
        );
      }
    });

    test('a --repo or --code that is not a directory is not_repository', () {
      final missing = '${repo.path}${Platform.pathSeparator}no-such-dir';
      for (final args in [
        ['state', '--repo', missing, '--role', 'code'],
        ['state', '--repo', repo.path, '--role', 'store', '--code', missing],
        ['state', '--repo', repo.path, '--role', 'code', '--code', missing],
      ]) {
        final stop = _stopOf(() => parseVcsArguments(args));
        expect(
          (stop.error, stop.message, stop.code),
          (
            'not_repository',
            '--repo and --code must name existing directories',
            1,
          ),
        );
      }
    });

    test('a file is not a directory', () {
      final file = File('${repo.path}${Platform.pathSeparator}f')
        ..writeAsStringSync('');
      final stop = _stopOf(
        () =>
            parseVcsArguments(['state', '--repo', file.path, '--role', 'code']),
      );
      expect(stop.error, 'not_repository');
    });
  });

  group('VcsStop', () {
    test('object has ok false, the error and message, then the extras', () {
      final stop = VcsStop('path_not_tracked', 'm', extra: {'path': 'a'});
      expect(stop.code, 1);
      expect(
        documentText(stop.object()),
        '{"ok":false,"error":"path_not_tracked","message":"m","path":"a"}',
      );
    });
  });

  group('sw vcs through runCli', () {
    Future<(int, List<int>, String)> run(
      List<String> args,
      List<int> stdin, {
      Map<String, VcsHandler>? handlers,
    }) async {
      final out = <int>[];
      final err = StringBuffer();
      final code = await runCli(
        args,
        out: StringBuffer(),
        err: err,
        outBytes: out.addAll,
        readStdin: () async => stdin,
        vcsHandlers: handlers,
      );
      return (code, out, err.toString());
    }

    Map<String, Object?> doc(List<int> bytes) =>
        jsonDecode(utf8.decode(bytes)) as Map<String, Object?>;

    test(
      'a valid call reaches the handler with the request and header',
      () async {
        VcsContext? seen;
        final (code, out, _) = await run(
          ['vcs', '--args-stdin'],
          _records([
            '/scripts',
            '/bin/bash',
            'state',
            '--repo',
            repo.path,
            '--role',
            'code',
          ]),
          handlers: {
            'state': (ctx) async {
              seen = ctx;
              return {'ok': true, 'backend': 'git'};
            },
          },
        );
        expect(code, 0);
        expect(utf8.decode(out), '{"ok":true,"backend":"git"}\n');
        expect(seen!.scriptsDir, '/scripts');
        expect(seen!.bash, '/bin/bash');
        expect(seen!.request.command, 'state');
        expect(seen!.request.code, repo.path);
      },
    );

    test('a handler VcsStop prints its document with its exit code', () async {
      final (code, out, _) = await run(
        ['vcs', '--args-stdin'],
        _records(['/s', '/b', 'push', '--repo', repo.path, '--role', 'code']),
        handlers: {
          'push': (_) async => throw VcsStop('fence', 'refused', code: 3),
        },
      );
      expect(code, 3);
      expect(doc(out), {'ok': false, 'error': 'fence', 'message': 'refused'});
    });

    test('an unknown subcommand is a usage document with exit 2', () async {
      final (code, out, err) = await run(
        ['vcs', '--args-stdin'],
        _records([
          '/s',
          '/b',
          'frobnicate',
          '--repo',
          repo.path,
          '--role',
          'code',
        ]),
      );
      expect(code, 2);
      expect(doc(out), {
        'ok': false,
        'error': 'usage',
        'message': 'unknown command: frobnicate',
      });
      expect(err, isEmpty);
    });

    test(
      'an uncaught exception is internal_error with exit 1, no trace',
      () async {
        final (code, out, err) = await run(
          ['vcs', '--args-stdin'],
          _records([
            '/s',
            '/b',
            'state',
            '--repo',
            repo.path,
            '--role',
            'code',
          ]),
          handlers: {'state': (_) async => throw StateError('boom')},
        );
        expect(code, 1);
        expect(doc(out), {
          'ok': false,
          'error': 'internal_error',
          'message': 'boom',
        });
        expect(utf8.decode(out), isNot(contains('StateError')));
        expect(utf8.decode(out), isNot(contains('#0')));
        expect(err, isEmpty);
      },
    );

    test('a document that cannot be encoded becomes internal_error', () async {
      final (code, out, _) = await run(
        ['vcs', '--args-stdin'],
        _records(['/s', '/b', 'state', '--repo', repo.path, '--role', 'code']),
        handlers: {
          'state': (_) async => {'ok': true, 'x': '\ud800'},
        },
      );
      expect(code, 1);
      expect(doc(out)['error'], 'internal_error');
    });

    test('a known command with no handler yet is internal_error', () async {
      final (code, out, _) = await run(
        ['vcs', '--args-stdin'],
        _records(['/s', '/b', 'probe', '--repo', repo.path, '--role', 'code']),
        handlers: const {},
      );
      expect(code, 1);
      expect(doc(out)['error'], 'internal_error');
      expect(doc(out)['message'], contains('not ported yet'));
    });

    test('too few records is a usage document with exit 2', () async {
      final (code, out, _) = await run([
        'vcs',
        '--args-stdin',
      ], _records(['/s', '/b']));
      expect(code, 2);
      expect(doc(out)['error'], 'usage');
    });

    test('anything else on argv is a usage document with exit 2', () async {
      final valid = _records([
        '/s',
        '/b',
        'state',
        '--repo',
        repo.path,
        '--role',
        'code',
      ]);
      for (final args in [
        ['vcs'],
        ['vcs', 'state'],
        ['vcs', '--args-stdin', 'state'],
        ['vcs', '--args-stdin', '--repo', repo.path],
        ['vcs', '--bogus'],
      ]) {
        final (code, out, _) = await run(args, valid);
        expect(code, 2, reason: '$args');
        expect(doc(out)['error'], 'usage', reason: '$args');
      }
    });

    test('the top-level usage names vcs', () async {
      final err = StringBuffer();
      final code = await runCli([], out: StringBuffer(), err: err);
      expect(code, 2);
      expect(err.toString(), contains('vcs'));
    });
  });
}
