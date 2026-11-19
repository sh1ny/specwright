import 'package:specwright_cli/src/commands/vcs.dart';
import 'package:specwright_cli/src/vcs/args.dart';
import 'package:specwright_cli/src/vcs/plan.dart';
import 'package:specwright_cli/src/vcs/probe.dart';
import 'package:specwright_cli/src/vcs/scripts.dart';
import 'package:specwright_cli/src/vcs/stop.dart';
import 'package:test/test.dart';

VcsSession _session({
  String? operation = 'switch',
  String? branch = 'feat/x',
  String repo = '/r',
  String code = '/r',
  String role = 'code',
  String? login,
  String? mergedCommit,
  bool force = false,
  bool remoteBranch = false,
}) {
  final request = VcsRequest(
    command: 'plan',
    repo: repo,
    role: role,
    code: code,
    branch: branch,
    operation: operation,
    login: login,
    mergedCommit: mergedCommit,
    force: force,
    remoteBranch: remoteBranch,
  );
  return VcsSession(
    VcsContext(request, '/s', 'bash', sw: '/opt/sw'),
    repo,
    code,
    ProbeInfo('git', 'main', repo, ''),
    VcsScripts('/s', 'bash'),
  );
}

Future<Object?> _commands(VcsSession s) async =>
    (await planDocument(s))['commands'];

void main() {
  test('shellQuote matches shlex.quote', () {
    expect(shellQuote(''), "''");
    expect(shellQuote('feat/x-1.2_3@%+=:,'), 'feat/x-1.2_3@%+=:,');
    expect(shellQuote('a b'), "'a b'");
    expect(shellQuote("it's"), "'it'\"'\"'s'");
    expect(shellQuote(r'a$b`c"d'), r"""'a$b`c"d'""");
    expect(shellQuote('café'), "'café'");
  });

  test('switch prints one command line', () async {
    final doc = await planDocument(_session());
    expect(doc, {
      'ok': true,
      'backend': 'git',
      'commands': [
        '/opt/sw --project /r vcs switch --repo /r --role code --code /r '
            '--branch feat/x',
      ],
    });
  });

  test('the command is the running sw when none is given', () async {
    final s = _session();
    final plain = VcsSession(
      VcsContext(s.request, '/s', 'bash'),
      s.repo,
      s.code,
      s.info,
      s.scripts,
    );
    final commands = (await planDocument(plain))['commands'] as List;
    expect(commands.single, isNot(contains('vcs.sh')));
    expect(commands.single, isNot(startsWith('bash')));
    expect(commands.single, contains(' --project /r vcs switch '));
  });

  test('delete-branch carries the options and quotes odd values', () async {
    final s = _session(
      operation: 'delete-branch',
      repo: '/my repo',
      code: '/my repo',
      force: true,
      remoteBranch: true,
      login: 'bot',
      mergedCommit: 'abcdef1',
    );
    expect(await _commands(s), [
      "/opt/sw --project '/my repo' vcs delete-branch --repo '/my repo' "
          "--role code --code '/my repo' --branch feat/x --force "
          '--remote-branch --login bot --merged-commit abcdef1',
    ]);
  });

  test('an unknown operation is a usage stop', () async {
    expect(
      () => planDocument(_session(operation: 'merge')),
      throwsA(
        isA<VcsStop>()
            .having((e) => e.code, 'code', 2)
            .having(
              (e) => e.message,
              'message',
              'plan --operation must be switch, pull or delete-branch',
            ),
      ),
    );
  });

  test('a missing branch and a bad commit id are usage stops', () async {
    expect(
      () => planDocument(_session(branch: null)),
      throwsA(isA<VcsStop>().having((e) => e.message, 'm', 'missing --branch')),
    );
    expect(
      () => planDocument(_session(mergedCommit: 'xyz')),
      throwsA(
        isA<VcsStop>()
            .having((e) => e.code, 'code', 2)
            .having(
              (e) => e.message,
              'm',
              '--merged-commit must be a commit id of 7 to 40 hex digits',
            ),
      ),
    );
  });
}
