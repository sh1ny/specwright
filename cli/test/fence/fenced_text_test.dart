// `fencedText`: the fence run in process for `sw vcs`, its output kept as text
// (native-cli-internal-calls D1, D2). The gh lookups are replaced; the git reads
// and the fenced command run for real through bash.
@Tags(['process'])
@Timeout(Duration(minutes: 2))
library;

import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:specwright_cli/src/fence/fence.dart';
import 'package:specwright_cli/src/fence/fenced_text.dart';
import 'package:specwright_cli/src/pr/gh.dart';
import 'package:specwright_cli/src/vcs/tool_runner.dart';
import 'package:test/test.dart';

import '../vcs/bash_support.dart';

void main() {
  final bash = findBash();
  final skip = bash == null ? 'no bash installed' : false;
  late Directory tmp;
  late String repo;
  late List<List<String>> ghCalls;
  late List<List<String>> launched;

  setUp(() {
    tmp = Directory.systemTemp.createTempSync('sw-fenced-text-');
    final dir = Directory('${tmp.path}/repo')..createSync();
    repo = dir.path.replaceAll(r'\', '/');
    ghCalls = [];
    launched = [];
  });
  tearDown(() => tmp.deleteSync(recursive: true));

  /// A gh that knows `auth token --user` and answers `api user` with [active]
  /// (nothing when null).
  GhCall fakeGh({String? active = 'me'}) => (args, env) async {
    ghCalls.add(args);
    final text = args.contains('--help')
        ? '--user'
        : args.first == 'auth'
        ? 'tok\n'
        : active == null
        ? ''
        : '$active\n';
    return GhResult(
      exitCode: 0,
      stdout: utf8.encode(text),
      stderr: Uint8List(0),
    );
  };

  /// The fence's own git reads, as outside a work tree: nothing to refuse.
  Future<ToolResult> outsideWorkTree(
    List<String> command,
    Map<String, String> env,
  ) async => ToolResult(0, utf8.encode('false\n'), Uint8List(0));

  Map<String, String> env([Map<String, String> more = const {}]) => {
    ...Platform.environment,
    ...more,
  };

  test('--resolve returns the active login on stdout', () async {
    final r = await fencedText(
      repo,
      ['--resolve'],
      environment: env(),
      gh: fakeGh(),
      git: outsideWorkTree,
      launch: (c, e) async => fail('--resolve launches nothing'),
    );
    expect((r.code, r.stdout, r.stderr), (0, 'me\n', ''));
    expect(ghCalls.any((a) => a.first == 'api'), isTrue);
  }, skip: skip);

  test(
    'no active account is a refusal: exit 3 and the as.sh: message',
    () async {
      final r = await fencedText(
        repo,
        ['--resolve'],
        environment: env(),
        gh: fakeGh(active: null),
        git: outsideWorkTree,
      );
      expect(r.code, 3);
      expect(r.stdout, '');
      expect(
        r.stderr,
        startsWith('as.sh: no active gh account for github.com'),
      );
      expect(r.stderr, endsWith('\n'));
    },
    skip: skip,
  );

  test(
    'a refused remote keeps exit 3, the prefix and the masked userinfo',
    () async {
      // `git remote get-url` answers a URL with userinfo: the fence refuses it
      // before the command is launched.
      Future<ToolResult> userinfoRemote(
        List<String> command,
        Map<String, String> e,
      ) async {
        final text = command.contains('--is-inside-work-tree')
            ? 'true\n'
            : command.contains('get-url')
            ? 'https://tok@github.com/o/r.git\n'
            : command.length == 2
            ? 'origin\n'
            : '';
        return ToolResult(0, utf8.encode(text), Uint8List(0));
      }

      final r = await fencedText(
        repo,
        ['me', 'git', 'push', 'origin', 'HEAD'],
        environment: env(),
        gh: fakeGh(),
        git: userinfoRemote,
        launch: (c, e) async {
          launched.add(c);
          return 0;
        },
      );
      expect(r.code, 3);
      expect(r.stderr, startsWith('as.sh:'));
      expect(r.stderr, contains('***'));
      expect(r.stderr, isNot(contains('tok@')));
      expect(launched, isEmpty);
    },
    skip: skip,
  );

  test(
    'the command runs in the repo and its output and exit code are kept',
    () async {
      final r = await fencedText(
        repo,
        ['me', 'bash', '-c', 'pwd; echo err >&2; exit 5'],
        environment: env(),
        gh: fakeGh(),
        git: outsideWorkTree,
      );
      expect(r.code, 5);
      expect(
        r.stdout.trim().replaceAll(r'\', '/').toLowerCase(),
        endsWith('/repo'),
      );
      expect(r.stderr, 'err\n');
    },
    skip: skip,
  );

  test('the fenced command has no deadline', () async {
    final watch = Stopwatch()..start();
    final r = await fencedText(
      repo,
      ['me', 'bash', '-c', 'sleep 3; echo done'],
      environment: env({'SPECWRIGHT_NET_DEADLINE': '1'}),
      gh: fakeGh(),
      git: outsideWorkTree,
    );
    expect((r.code, r.stdout, r.stderr), (0, 'done\n', ''));
    expect(watch.elapsed, greaterThan(const Duration(seconds: 2)));
  }, skip: skip);
}
