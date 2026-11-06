import '../commands/vcs.dart';
import 'git_backend.dart';
import 'stop.dart';

/// Python's `shlex.quote`: the text as is when it holds only word characters
/// and `@%+=:,./-`, else single-quoted with each `'` written as `'"'"'`.
String shellQuote(String s) {
  if (s.isEmpty) return "''";
  if (RegExp(r'^[A-Za-z0-9_@%+=:,./-]+$').hasMatch(s)) return s;
  return "'${s.replaceAll("'", "'\"'\"'")}'";
}

/// `vcs.sh`'s `plan`: the one `bash <scripts dir>/vcs.sh ...` line that
/// carries out `--operation` (`switch`, `pull` or `delete-branch`). It runs
/// nothing.
Future<Map<String, Object?>> planDocument(VcsSession s) async {
  final request = s.request;
  final operation = request.operation;
  if (operation != 'switch' &&
      operation != 'pull' &&
      operation != 'delete-branch') {
    throw VcsStop(
      'usage',
      'plan --operation must be switch, pull or delete-branch',
      code: 2,
    );
  }
  final branch = requireBranch(s);
  final args = [
    'bash',
    s.scripts.path('vcs.sh'),
    operation!,
    '--repo',
    s.repo,
    '--role',
    request.role,
    '--code',
    s.code,
    '--branch',
    branch,
  ];
  if (request.force) args.add('--force');
  if (request.remoteBranch) args.add('--remote-branch');
  final login = request.login;
  if (login != null && login.isNotEmpty) args.addAll(['--login', login]);
  final merged = request.mergedCommit;
  if (merged != null && merged.isNotEmpty) {
    if (!RegExp(r'^[0-9a-fA-F]{7,40}$').hasMatch(merged)) {
      throw VcsStop(
        'usage',
        '--merged-commit must be a commit id of 7 to 40 hex digits',
        code: 2,
      );
    }
    args.addAll(['--merged-commit', merged]);
  }
  return {
    'ok': true,
    'backend': s.info.backend,
    'commands': [args.map(shellQuote).join(' ')],
  };
}
