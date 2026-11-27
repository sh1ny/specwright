import '../fence/fence.dart' show originalGitEnvironment;
import '../fence/urls.dart';
import '../pr/context.dart';
import '../pr/identity.dart';
import '../pr/pair.dart' show PairStop;
import '../settings/rules.dart';

import 'scripts.dart';
import 'stop.dart';

/// Git helpers every backend of `vcs.sh` uses (Git reads on a jj or GitButler
/// repo too): `path_text`, `git_checked`, `remote_url`, `is_github_url`,
/// `network_git` and `git_ancestor`.

/// `vcs.sh`'s `path_text`: `\` becomes `/`.
String pathText(String path) => path.replaceAll(r'\', '/');

/// Python's `a or b` on two strings.
String orElse(String a, String b) => a.isNotEmpty ? a : b;

/// `vcs.sh`'s `git(repo, *args)`.
Future<TextResult> git(VcsScripts scripts, String repo, List<String> args) {
  final command = ['git', ...args];
  return runText(
    repo,
    command,
    environment: scripts.environmentFor?.call(command),
  );
}

/// `vcs.sh`'s `git_checked`: a non-zero exit is the stop [error] with git's
/// stderr (else stdout), or `git <args> failed`.
Future<TextResult> gitChecked(
  VcsScripts scripts,
  String repo,
  List<String> args, {
  String error = 'git_error',
}) async {
  final result = await git(scripts, repo, args);
  if (result.code != 0) {
    final said = orElse(result.stderr, result.stdout).trim();
    throw VcsStop(
      error,
      said.isNotEmpty ? said : 'git ${args.join(' ')} failed',
    );
  }
  return result;
}

/// Classify the destinations the actual Git operation uses. A bare Git pull
/// asks Git to expand its default remote without contacting it.
Future<bool> networkUsesFence(
  VcsScripts scripts,
  String repo,
  GitHubConnection connection, {
  required String? remote,
  bool push = false,
}) async {
  final args = remote == null
      ? ['ls-remote', '--get-url']
      : [
          'remote',
          'get-url',
          if (push) ...['--push', '--all'],
          remote,
        ];
  final command = ['git', ...args];
  final result = await runText(
    repo,
    command,
    environment: originalGitEnvironment(scripts.environmentFor?.call(command)),
  );
  final output = result.stdout.trim();
  final kind = push ? 'push' : 'fetch';
  final name = remote ?? 'current upstream';
  if (result.code != 0 || output.isEmpty) {
    throw VcsStop(
      'remote_unreadable',
      "cannot read $kind destination for '$name'",
      code: 3,
    );
  }
  if (!connection.fence) return false;
  if (!push) return ghUrl(output, host: connection.host);
  final urls = output.split(RegExp(r'\r?\n'));
  final onHost = ghUrl(urls.first, host: connection.host);
  for (final url in urls.skip(1)) {
    if (ghUrl(url, host: connection.host) != onHost) {
      throw VcsStop(
        'mixed_push_transport',
        "remote '$name' mixes push URLs on and off ${connection.host}; refusing",
        code: 3,
      );
    }
  }
  return onHost;
}

/// The PR plan binds the destination before validation. Re-read the selected
/// fetch and all push destinations using the environment of the actual child.
Future<TextResult> launchNetwork(
  VcsScripts scripts,
  String repo,
  List<String> command,
  String who, {
  required bool fenced,
  required String host,
  required String? remote,
  String? expectedRepo,
}) async {
  Future<void> checkTarget(Map<String, String>? env) async {
    final planned = expectedRepo!;
    Never changed() => throw VcsStop(
      'pr_destination_changed',
      "the selected remote '$remote' no longer matches the planned PR destination",
      code: 3,
    );
    final parts = planned.split('/');
    if (remote == null ||
        parts.length != 3 ||
        canonicalHost(parts.first) != host ||
        parseRepo('https://$planned', host: host) == null) {
      changed();
    }
    final context = PrContext(
      writeOut: (_) {},
      writeErr: (_) {},
      environment: env,
    );
    try {
      final current = await identityOf(
        context,
        repo,
        host: host,
        selection: RemoteSelection(name: remote),
      );
      if ((current['repo'] as String).toLowerCase() !=
          parts.skip(1).join('/').toLowerCase()) {
        changed();
      }
    } on PairStop {
      changed();
    }
  }

  if (fenced) {
    return runAs(
      scripts,
      repo,
      who,
      command,
      host: host,
      beforeLaunch: expectedRepo == null ? null : checkTarget,
    );
  }
  final environment = originalGitEnvironment(
    scripts.environmentFor?.call(command),
  );
  if (expectedRepo != null) await checkTarget(environment);
  return runText(repo, command, environment: environment);
}

final _notFastForward = RegExp(
  r'not possible to fast-forward|divergent branches',
  caseSensitive: false,
);

/// Runs a Git network operation with the selected transport. A non-fast-forward
/// pull is exit 1. Other failures are `fence_failed` or `git_network_error`.
///
/// Constraint C4: on Git and jj a fenced command's own exit 3 on a GitHub
/// remote is still reported as `fence_failed` (D2); this is a deliberate gap,
/// since a refusal and the command's own exit 3 cannot be told apart by status.
Future<TextResult> networkGit(
  VcsScripts scripts,
  String repo,
  List<String> args,
  String? login, {
  required String? remote,
  required GitHubConnection connection,
  String? expectedRepo,
}) async {
  final github = await networkUsesFence(
    scripts,
    repo,
    connection,
    remote: remote,
    push: args.first == 'push',
  );
  final who = await fenceLogin(
    scripts,
    repo,
    github: github,
    login: login,
    host: connection.host,
  );
  final result = await launchNetwork(
    scripts,
    repo,
    ['git', ...args],
    who,
    fenced: github,
    host: connection.host,
    remote: remote,
    expectedRepo: expectedRepo,
  );
  if (result.code != 0) {
    final said = orElse(result.stderr, result.stdout).trim();
    final message = said.isNotEmpty ? said : 'Git network operation failed';
    if (args[0] == 'pull' && _notFastForward.hasMatch(message)) {
      throw VcsStop('not_fast_forward', message);
    }
    throw VcsStop(
      github && result.code == 3 ? 'fence_failed' : 'git_network_error',
      message,
      code: 3,
    );
  }
  return result;
}

/// `vcs.sh`'s `git_ancestor`: `git merge-base --is-ancestor`; an exit other
/// than 0 or 1 is `git_error`.
Future<bool> gitAncestor(
  VcsScripts scripts,
  String repo,
  String ancestor,
  String descendant,
) async {
  final r = await git(scripts, repo, [
    'merge-base',
    '--is-ancestor',
    ancestor,
    descendant,
  ]);
  if (r.code != 0 && r.code != 1) {
    final said = orElse(r.stderr, r.stdout).trim();
    throw VcsStop(
      'git_error',
      said.isNotEmpty ? said : 'git merge-base --is-ancestor failed',
    );
  }
  return r.code == 0;
}
