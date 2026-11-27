import 'dart:convert';

import 'package:specwright_cli/src/commands/pr.dart';
import 'package:test/test.dart';

import 'pr_support.dart';

void main() {
  const commands =
      'snapshot|reply|identity|vcs|tier|context|policy|discover|ensure-pr|link|expected|pair-state|rounds|closing-check|closed-check|merge|delete-remote|item-issues|pass|cleanup-plan|branch-check|pair';
  late Fixture f;
  setUp(() => f = Fixture());
  tearDown(() => f.dispose());

  Future<int> run(List<String> args) => runPrCommand(
    args,
    writeOut: f.out.addAll,
    writeErr: f.err.addAll,
    context: () => f.ctx,
  );

  test('only the listed commands are commands', () async {
    for (final args in [
      <String>[],
      ['watch'],
      ['watch', 'x'],
    ]) {
      f.err.clear();
      expect(await run(args), 2, reason: '$args');
      expect(f.stderr, 'usage: sw pr reviewers|$commands [arguments]\n');
    }
  });

  test('reply gets the arguments, and its own exit code', () async {
    expect(await run(['reply', '7']), 1);
    expect(f.stderr, 'pr-reply.sh: line 50: 2: thread|comment|resolve\n');
  });

  test('snapshot with no argument reads the current branch', () async {
    f.onGh = (args) => answer('', exit: 3, stderr: 'no repo\n');
    expect(await run(['snapshot']), 3);
    expect(f.stderr, 'no repo\n');
    expect(f.ghCalls.single.take(7), [
      'pr',
      'view',
      'feature',
      '--repo',
      'o/n',
      '--json',
      'number',
    ]);
  });

  test(
    'the settings and policy commands take their arguments directly',
    () async {
      for (final (name, message) in [
        ('identity', 'identity <dir>'),
        ('vcs', 'missing --code'),
        ('tier', 'missing --code'),
        ('context', 'missing --code'),
        ('policy', 'missing --repo'),
      ]) {
        f.out.clear();
        expect(await run([name]), 2);
        expect(jsonDecode(f.stdout), {
          'ok': false,
          'error': 'usage',
          'message': message,
        }, reason: name);
      }
    },
  );

  test(
    'internal pair dispatch keeps original public usage for invalid calls',
    () async {
      for (final args in [
        <String>[],
        ['bogus', 'a b', '', r'$x *', 'é'],
      ]) {
        f.out.clear();
        expect(await run(['pair', ...args]), 2);
        final doc = jsonDecode(f.stdout) as Map;
        expect(doc['ok'], false);
        expect(doc['error'], 'usage');
        expect(
          (doc['message'] as String)
              .substring('subcommand: '.length)
              .split(' | '),
          [
            'identity',
            'context',
            'tier',
            'vcs',
            'discover',
            'expected',
            'ensure-pr',
            'closing-check',
            'closed-check',
            'link',
            'pair-state',
            'rounds',
            'pass',
            'cleanup-plan',
            'branch-check',
            'merge',
            'delete-remote',
            'policy',
            'item-issues',
          ],
        );
        expect(f.ghCalls, isEmpty);
        expect(f.stderr, isEmpty);
      }
    },
  );
}
