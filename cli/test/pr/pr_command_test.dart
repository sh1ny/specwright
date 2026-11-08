import 'dart:convert';

import 'package:specwright_cli/src/commands/pr.dart';
import 'package:specwright_cli/src/pr/context.dart';
import 'package:test/test.dart';

import 'pr_support.dart';

List<int> records(List<String> parts) => [
  for (final p in parts) ...[...utf8.encode(p), 0],
];

void main() {
  late Fixture f;
  setUp(() => f = Fixture());
  tearDown(() => f.dispose());

  Future<int> run(List<String> args, List<int> stdin) => runPrCommand(
    args,
    writeOut: f.out.addAll,
    writeErr: f.err.addAll,
    readStdin: () async => stdin,
    context: (scripts, bash) => f.ctx,
  );

  test('only the handoff commands with --args-stdin are commands', () async {
    for (final args in [
      <String>[],
      ['snapshot'],
      ['reply'],
      ['watch', '--args-stdin'],
      ['snapshot', 'x'],
    ]) {
      f.err.clear();
      expect(await run(args, records(['s', 'b'])), 2, reason: '$args');
      expect(
        f.stderr,
        'usage: sw pr snapshot|reply|identity|vcs|tier|context|policy --args-stdin\n',
      );
    }
  });

  test('a handoff that is not NUL-terminated records exits 2', () async {
    expect(await run(['reply', '--args-stdin'], utf8.encode('s\u0000b')), 2);
    expect(
      f.stderr,
      startsWith(
        'usage: sw pr snapshot|reply|identity|vcs|tier|context|policy --args-stdin (stdin:',
      ),
    );
    f.err.clear();
    expect(await run(['reply', '--args-stdin'], records(['only one'])), 2);
  });

  test('reply gets the script arguments, and its own exit code', () async {
    expect(await run(['reply', '--args-stdin'], records(['s', 'b', '7'])), 1);
    expect(f.stderr, 'pr-reply.sh: line 50: 2: thread|comment|resolve\n');
  });

  test('snapshot with no argument is a handoff too', () async {
    f.onGh = (args) => answer('', exit: 3, stderr: 'no repo\n');
    expect(await run(['snapshot', '--args-stdin'], records(['s', 'b'])), 3);
    expect(f.stderr, 'no repo\n');
    expect(f.ghCalls.first.take(2), ['repo', 'view']);
  });

  test('the settings and policy commands take the handoff too', () async {
    for (final (name, message) in [
      ('identity', 'identity <dir>'),
      ('vcs', 'missing --code'),
      ('tier', 'missing --code'),
      ('context', 'missing --code'),
      ('policy', 'missing --repo'),
    ]) {
      f.out.clear();
      expect(await run([name, '--args-stdin'], records(['s', 'b'])), 2);
      expect(jsonDecode(f.stdout), {
        'ok': false,
        'error': 'usage',
        'message': message,
      }, reason: name);
    }
  });

  test('parsePrHandoff splits the records', () {
    final h = parsePrHandoff(records(['d', 'b', 'a', '']))!;
    expect(
      [h.scriptsDir, h.bash, h.args],
      [
        'd',
        'b',
        ['a', ''],
      ],
    );
  });
}
