import 'git.dart';
import 'options.dart';
import 'settings.dart';
import 'text.dart';

/// The branch prefixes a change branch carries (`<prefix>/<name>`).
const List<String> changePrefixes = [
  'feat',
  'bugfix',
  'refactor',
  'docs',
  'chore',
];

/// Where `sw update` stands in git: the code checkout, the planning root and
/// whether the root is a planning store, as `scripts/update.sh`'s helper
/// worked it out (`planning_repo`, `code_top`, `other_worktree`, `is_store`,
/// `configured_main`, `planning_main`). Answers are asked of git once and
/// kept for the life of the object.
///
/// Paths are forward-slash text, as [UpdateOptions] gives them.
class UpdateRepo {
  UpdateRepo({
    required this.code,
    required this.root,
    required this.settings,
    GitRunner? git,
  }) : git = git ?? runUpdateGit;

  factory UpdateRepo.of(
    UpdateOptions options,
    UpdateSettings settings, {
    GitRunner? git,
  }) => UpdateRepo(
    code: options.code,
    root: options.root,
    settings: settings,
    git: git,
  );

  final String code;
  final String root;
  final UpdateSettings settings;
  final GitRunner git;

  Future<String>? _codeTop;
  Future<({String top, String planning})?>? _planning;
  Future<bool>? _isStore;
  final Map<String, Future<String?>> _common = {};

  /// `git_lines`: the non-blank lines of a git run, empty when it failed.
  Future<List<String>> gitLines(String top, List<String> args) async =>
      (await git(top, args)).lines;

  /// The code checkout's git toplevel, resolved (the `--code` directory when
  /// it is not in a repo).
  Future<String> codeTop() => _codeTop ??= () async {
    final r = await git(code, ['rev-parse', '--show-toplevel']);
    final out = pyStrip(r.text);
    return resolvePosix(r.ok && out.isNotEmpty ? out : code);
  }();

  /// The planning repo's toplevel and `<root>/openspec` relative to it; null
  /// outside a repo or when the root's openspec directory is not inside it.
  Future<({String top, String planning})?> planningRepo() =>
      _planning ??= () async {
        final r = await git(root, ['rev-parse', '--show-toplevel']);
        if (!r.ok) return null;
        final top = resolvePosix(pyStrip(r.text));
        final rel = relativeTo(top, resolvePosix('$root/openspec'));
        return rel == null ? null : (top: top, planning: rel);
      }();

  /// The absolute git common dir of the repo at [path], null outside a repo.
  /// A relative answer is resolved against [path] (no `--path-format`, which
  /// needs git 2.31).
  Future<String?> commonDir(String path) => _common[path] ??= () async {
    final r = await git(path, ['rev-parse', '--git-common-dir']);
    final out = pyStrip(r.text);
    if (!r.ok || out.isEmpty) return null;
    final absolute =
        out.startsWith('/') ||
        out.startsWith(r'\') ||
        RegExp(r'^[A-Za-z]:').hasMatch(out);
    return resolvePosix(absolute ? out : '$path/$out');
  }();

  /// (root toplevel, code toplevel) when `--root` is in another worktree of
  /// the code repo (the same git common dir, another toplevel), else null.
  Future<(String, String)?> otherWorktree() async {
    final planning = await planningRepo();
    final ctop = await codeTop();
    if (planning == null || samePath(planning.top, ctop)) return null;
    final dir = await commonDir(planning.top);
    if (dir == null) return null;
    final other = await commonDir(ctop);
    return other != null && samePath(dir, other) ? (planning.top, ctop) : null;
  }

  /// True when the planning root lives in a git repo other than the code
  /// checkout's (a planning store); another worktree of the code repo is not
  /// one.
  Future<bool> isStore() => _isStore ??= () async {
    final planning = await planningRepo();
    if (planning == null || samePath(planning.top, await codeTop())) {
      return false;
    }
    return await otherWorktree() == null;
  }();

  /// The main branch the settings name: `planning_store.main_branch` for a
  /// store, else `main_branch`; null when unset.
  Future<String?> configuredMain() async =>
      settings.configuredMain(isStore: await isStore());

  /// The planning main of [top]: the configured one first, else `main`, then
  /// `master`, each as `origin/<name>` when present, else the local branch.
  /// The ref, or null.
  Future<String?> planningMain(String top) async {
    final configured = await configuredMain();
    for (final name in [?configured, 'main', 'master']) {
      for (final ref in ['refs/remotes/origin/$name', 'refs/heads/$name']) {
        final r = await git(top, [
          'rev-parse',
          '--verify',
          '-q',
          '$ref^{commit}',
        ]);
        if (r.ok) return ref;
      }
    }
    return null;
  }

  /// `(prefix, name)` of a branch `<prefix>/<name>`, else null.
  static (String, String)? branchParts(String short) {
    final at = short.indexOf('/');
    if (at < 0) return null;
    final prefix = short.substring(0, at);
    final name = short.substring(at + 1);
    return changePrefixes.contains(prefix) &&
            name.isNotEmpty &&
            !name.contains('/')
        ? (prefix, name)
        : null;
  }

  /// This project's id: its origin fetch URL as `host/owner/repo`, else
  /// `path:<code toplevel>`.
  Future<String> ownerId() async {
    final r = await git(code, ['remote', 'get-url', 'origin']);
    if (r.ok) {
      final id = normaliseOrigin(r.text);
      if (id != null) return id;
    }
    return 'path:${await codeTop()}';
  }
}

/// `host/owner/repo` from an origin fetch URL: scheme, userinfo, port, `.git`
/// and a trailing dot on the host are dropped. Null for an origin with no
/// host (a local path, `file://`).
String? normaliseOrigin(String url) {
  final u = pyStrip(url);
  var m = RegExp(
    r'^[A-Za-z][A-Za-z0-9+.\-]*://(?:[^/@]*@)?([^/:]+)(?::\d*)?/(.+)$',
  ).firstMatch(u);
  if (m == null &&
      !u.contains('://') &&
      !RegExp(r'^([A-Za-z]:[\\/]|[/.~])').hasMatch(u)) {
    m = RegExp(r'^(?:[^/@:\s]+@)?([^/:\s]{2,}):(.+)$').firstMatch(u);
  }
  if (m == null) return null;
  var host = m.group(1)!;
  while (host.endsWith('.')) {
    host = host.substring(0, host.length - 1);
  }
  var path = m.group(2)!.replaceAll(RegExp(r'^/+|/+$'), '');
  if (path.endsWith('.git')) path = path.substring(0, path.length - 4);
  return host.isNotEmpty && path.isNotEmpty ? '$host/$path' : null;
}
