import 'dart:io';

import 'scripts.dart';
import 'stop.dart';

/// What `vcs.sh`'s `probe` returns: the backend, the main branch, the Git root
/// (`repo`), the pinned login and, for Git, whether a `.jj` directory exists.
class ProbeInfo {
  ProbeInfo(
    this.backend,
    this.main,
    this.repo,
    this.login, {
    this.jjPresent = false,
  });

  final String backend;
  String main;
  final String repo;
  final String login;
  final bool jjPresent;
}

/// `Path(path).resolve()` for a directory that exists: absolute, `.` and `..`
/// folded, links followed. A path that cannot be resolved is returned as it is
/// (a path with escaped bytes is refused later by the launcher as
/// unrepresentable, and no `pwd -P` runs for it).
Future<String> resolvePath(String path) async {
  try {
    return Directory(path).resolveSymbolicLinksSync();
  } on FileSystemException {
    return path;
  }
}

bool _samePath(String a, String b) =>
    Platform.isWindows ? a.toLowerCase() == b.toLowerCase() : a == b;

bool _exists(String path) =>
    File(path).existsSync() || Directory(path).existsSync();

bool _isDirectory(String path) => Directory(path).existsSync();

String _join(String base, String rel) {
  final absolute =
      rel.startsWith('/') ||
      (Platform.isWindows &&
          (rel.startsWith(r'\') || RegExp(r'^[A-Za-z]:').hasMatch(rel)));
  if (absolute) return rel;
  return base.endsWith('/') || base.endsWith(r'\') ? '$base$rel' : '$base/$rel';
}

final _version = RegExp(r'\b(\d+)\.(\d+)\.(\d+)');

/// `vcs.sh`'s `git_root`.
Future<String> gitRoot(String repo) async {
  final result = await runText(repo, ['git', 'rev-parse', '--show-toplevel']);
  if (result.code != 0) {
    throw VcsStop(
      'not_repository',
      'not inside a Git work tree: ${result.stderr.trim()}',
    );
  }
  return resolvePath(result.names('repository path').trim());
}

/// `vcs.sh`'s `detect_main`.
Future<String> detectMain(String repo, String configured) async {
  if (configured.isNotEmpty) return configured;
  for (final name in const ['main', 'master']) {
    final r = await runText(repo, [
      'git',
      'show-ref',
      '--verify',
      '--quiet',
      'refs/heads/$name',
    ]);
    if (r.code == 0) return name;
  }
  return 'main';
}

/// `vcs.sh`'s `gitbutler_managed`: the target ref, or null when
/// `.git/gitbutler/` or `gitbutler.project.targetRef` is missing.
Future<String?> gitbutlerManaged(String root) async {
  final common = await runText(root, ['git', 'rev-parse', '--git-common-dir']);
  // D4: the common dir is a path; read strictly, a non-UTF-8 one is not_utf8
  // instead of a look-alike that hides the GitButler directory.
  final commonText = common.code == 0
      ? common.names('Git common directory').trim()
      : '';
  final commonDir = commonText.isNotEmpty
      ? _join(root, commonText)
      : _join(root, '.git');
  if (!_isDirectory(_join(commonDir, 'gitbutler'))) return null;
  final target = await runText(root, [
    'git',
    'config',
    '--get',
    'gitbutler.project.targetRef',
  ]);
  if (target.code != 0) return null;
  final ref = target.names('GitButler target ref').trim();
  return ref.isNotEmpty ? ref : null;
}

(int, int, int)? _versionOf(TextResult r) {
  final found = _version.firstMatch(r.stdout + r.stderr);
  if (found == null) return null;
  return (
    int.parse(found.group(1)!),
    int.parse(found.group(2)!),
    int.parse(found.group(3)!),
  );
}

bool _older((int, int, int) v, (int, int, int) min) => v.$1 != min.$1
    ? v.$1 < min.$1
    : v.$2 != min.$2
    ? v.$2 < min.$2
    : v.$3 < min.$3;

Future<ProbeInfo> _probeGitbutler(
  String repo,
  String configuredMain,
  VcsSettings settings,
) async {
  final root = await gitRoot(repo);
  final main = await detectMain(root, configuredMain);
  final target = await gitbutlerManaged(root);
  if (target == null) {
    throw VcsStop(
      'not_managed',
      'vcs: gitbutler selected, but GitButler does not manage this repo (no '
          '.git/gitbutler/ and gitbutler.project.targetRef); open the repo with '
          'GitButler first (the app, or run `but status` yourself); Specwright '
          'never sets it up',
    );
  }
  if (target != 'refs/heads/$main' && target != 'refs/remotes/origin/$main') {
    throw VcsStop(
      'target_mismatch',
      'GitButler target is $target, but the main branch is $main (expected '
          'refs/heads/$main or refs/remotes/origin/$main)',
    );
  }
  // installed skills live inside the code checkout, so ask `but` from outside
  final outside = Directory.systemTemp.createTempSync('swb-probe-');
  final TextResult version;
  try {
    version = await runText(outside.path, ['but', '--version']);
  } finally {
    outside.deleteSync(recursive: true);
  }
  if (version.code == 127) {
    throw VcsStop(
      'tool_missing',
      'vcs: gitbutler is selected but but is not installed or not on PATH: but',
    );
  }
  final current = _versionOf(version);
  if (version.code != 0 || current == null) {
    throw VcsStop(
      'tool_version_unknown',
      'could not determine but version from but --version',
    );
  }
  if (_older(current, (0, 23, 0))) {
    throw VcsStop(
      'tool_too_old',
      'but version ${current.$1}.${current.$2}.${current.$3} is too old; '
          'minimum supported version is 0.23',
    );
  }
  return ProbeInfo('gitbutler', main, root, settings.login);
}

/// `vcs.sh`'s `probe(repo, code, role)`: the backend the settings choose,
/// checked against the repository, with the stops `vcs.sh` gives.
Future<ProbeInfo> probe(
  VcsScripts scripts,
  String repo,
  String code,
  String role,
) async {
  final settings = await readSettings(
    scripts,
    code: code,
    repo: repo,
    role: role,
  );
  final backend = settings.backend;
  if (backend == 'gitbutler') {
    return _probeGitbutler(repo, settings.main, settings);
  }
  if (backend == 'jj') {
    final version = await runText(repo, ['jj', '--version']);
    if (version.code == 127) {
      throw VcsStop(
        'tool_missing',
        'jj is selected but jj is not installed or not on PATH: jj',
      );
    }
    final current = _versionOf(version);
    if (version.code != 0 || current == null) {
      throw VcsStop(
        'tool_version_unknown',
        'could not determine jj version from jj --version',
      );
    }
    if (_older(current, (0, 46, 0))) {
      throw VcsStop(
        'tool_too_old',
        'jj version ${current.$1}.${current.$2}.${current.$3} is too old; '
            'minimum supported version is 0.46',
      );
    }
    final String root;
    try {
      root = await gitRoot(repo);
    } on VcsStop {
      if (_exists(_join(repo, '.jj'))) {
        throw VcsStop(
          'not_colocated',
          'jj workspace has no Git work tree at the same toplevel',
        );
      }
      throw VcsStop(
        'not_managed',
        'vcs: jj selected, but no .jj/ metadata was found',
      );
    }
    if (!_exists(_join(root, '.jj'))) {
      throw VcsStop(
        'not_managed',
        'vcs: jj selected, but the Git work tree has no .jj/ metadata',
      );
    }
    final main = await detectMain(root, settings.main);
    final jroot = await runText(repo, ['jj', 'root']);
    if (jroot.code != 0 ||
        !_samePath(
          await resolvePath(jroot.names('repository path').trim()),
          root,
        )) {
      throw VcsStop(
        'not_colocated',
        'jj workspace and Git work tree do not share the same toplevel',
      );
    }
    return ProbeInfo('jj', main, root, settings.login);
  }
  final root = await gitRoot(repo);
  final main = await detectMain(root, settings.main);
  if (await gitbutlerManaged(root) != null) {
    throw VcsStop(
      'gitbutler_workspace',
      'GitButler manages this repo, and the Git backend must not write in its '
          'workspace: set vcs: gitbutler (with finish: pr) in '
          'openspec/specwright.yaml, or take the repo out of GitButler before '
          'using Git',
    );
  }
  return ProbeInfo(
    'git',
    main,
    root,
    settings.login,
    jjPresent: _exists(_join(root, '.jj')),
  );
}
