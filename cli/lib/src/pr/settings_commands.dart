import 'dart:io';

import '../commit/task_cover.dart' show pyStrip;
import '../entry/project_version.dart' show projectRoot;
import '../settings/reviewer_config.dart';
import '../settings/rules.dart';
import 'context.dart';
import 'identity.dart';
import 'pair.dart';

// `sw pr vcs`, `sw pr tier` and `sw pr context`: `pr-pair.sh vcs|tier|context` (pr-pair.sh:1139-1291). The rules live in
// `settings/`; this reads the work-tree file, asks git for the main branch, the GitButler pin and each repo's identity,
// and prints the answer (design D1). Every JSON field is the script's, in its order; message text after a fixed prefix is
// ours (D11).

PairStop _stopOf(SettingsStop e) => PairStop(e.error, e.message, code: e.code);

/// D8: an integer setting past 64 bits stops the commands that act on it, `bad_setting` with exit 2.
void _stopOnOversized(List<SettingProblem> problems) {
  for (final p in problems) {
    if (p is OversizedSetting) throw PairStop(p.error, p.text, code: 2);
  }
}

/// Settings for native workflow callers, without context's reviewer-file output.
Future<Contexts> workflowContexts(
  PrContext ctx,
  String code,
  String? store,
) async {
  final problems = <SettingProblem>[];
  try {
    final settings = loadSettings(
      readSettingsText([projectRoot(ctx.project ?? code)]),
    );
    final mains = {
      code: await _detectMain(ctx, code, selectedRemote(settings).name),
    };
    if (store != null) {
      mains[store] = await _detectMain(
        ctx,
        store,
        selectedRemote(settings, store: true).name,
      );
    }
    final c = contexts(
      settings,
      code,
      store,
      detectMain: (d) => mains[d] ?? 'main',
      problems: problems,
    );
    _stopOnOversized(problems);
    return c;
  } on SettingsStop catch (e) {
    throw _stopOf(e);
  }
}

/// A direct command uses the requested checkout unless `--project` names the
/// code project. An implicit target in a different work tree is then the store.
Future<({GitHubConnection connection, RemoteSelection remote, String login})>
prGitHubSettings(
  PrContext ctx, {
  String? directory,
  String? code,
  bool? store,
}) async {
  final dir = directory ?? ctx.cwd;
  final project = projectRoot(ctx.project ?? code ?? dir);
  try {
    final settings = loadSettings(readSettingsText([project]));
    String pathKey(String path) =>
        Platform.isWindows ? path.toLowerCase() : path;

    final isStore = store ?? pathKey(project) != pathKey(projectRoot(dir));
    final github = settingSection(settings, 'github', 'github');
    final codeLogin = pyStrip('${github['login'] ?? ''}');
    final storeSettings = isStore
        ? settingSection(settings, 'planning_store', 'planning_store')
        : const <String, Object?>{};
    final storeLogin = pyStrip('${storeSettings['login'] ?? ''}');
    return (
      connection: githubConnection(settings),
      remote: selectedRemote(settings, store: isStore),
      login: storeLogin.isNotEmpty ? storeLogin : codeLogin,
    );
  } on SettingsStop catch (e) {
    throw _stopOf(e);
  }
}

/// `toplevel(d)`: the git top level of [d], else [d].
Future<String> _toplevel(PrContext ctx, String d) async {
  final r = await ctx.git(d, ['rev-parse', '--show-toplevel']);
  // D4: a path, read strictly
  final top = pyStrip(r.names('repository path'));
  return r.code == 0 && top.isNotEmpty ? top : d;
}

/// `settings_text(code)`: the file under [code], else under its top level.
Future<String?> _settingsText(PrContext ctx, String code) async =>
    readSettingsText([code]) ?? readSettingsText([await _toplevel(ctx, code)]);

/// `load_settings(code)`.
Future<Map<String, Object?>> _loadSettings(PrContext ctx, String code) async {
  final text = await _settingsText(ctx, code);
  try {
    return loadSettings(text);
  } on SettingsStop catch (e) {
    throw _stopOf(e);
  }
}

/// `has_ref(d, ref)`.
Future<bool> _hasRef(PrContext ctx, String d, String ref) async =>
    (await ctx.git(d, ['show-ref', '--verify', '--quiet', ref])).code == 0;

/// `main`, else `master`, as a local or selected remote branch.
///
/// C43: default main detection (run eagerly by `readVcsSettings` for every role
/// and used only when that role sets no `main_branch`) keeps today's rule: a
/// `git show-ref --verify --quiet` that does not succeed counts as no such ref,
/// whether the ref is missing, malformed or unreadable. A failed lookup of an
/// existing `main` can therefore make a plan take `master` as main, and no
/// emitted guard catches it: `check branch` compares the current branch and
/// backend, not the detected main. Setting `main_branch` makes the plan use
/// that name instead of the detected one, though the lookups still run. The
/// finish delta names default main detection as an exception to the failed-read
/// rule. Rejected: a strict lookup on the planner's path, which two review
/// rounds showed cannot tell a malformed ref from a missing one through
/// `show-ref` and would stop plans on a role's detection they do not use.
Future<String> _detectMain(PrContext ctx, String d, String remote) async {
  for (final name in const ['main', 'master']) {
    if (await _hasRef(ctx, d, 'refs/heads/$name') ||
        await _hasRef(ctx, d, 'refs/remotes/$remote/$name')) {
      return name;
    }
  }
  return 'main';
}

/// `settings_path(code)`: the settings file `load_settings` reads, resolved, or null.
Future<String?> _settingsPath(PrContext ctx, String code) async {
  for (final base in [code, null]) {
    final dir = base ?? await _toplevel(ctx, code);
    final f = File('$dir/openspec/specwright.yaml');
    if (f.existsSync()) {
      try {
        return f.resolveSymbolicLinksSync().replaceAll(r'\', '/');
      } on FileSystemException {
        return f.absolute.path.replaceAll(r'\', '/');
      }
    }
  }
  return null;
}

String _trimSlash(String p) {
  var s = p.replaceAll(r'\', '/');
  while (s.length > 1 && s.endsWith('/')) {
    s = s.substring(0, s.length - 1);
  }
  return s;
}

/// `path` relative to [top], or null when it is not inside it (Windows compares without case).
String? _relativeTo(String path, String top) {
  final p = _trimSlash(path);
  final t = _trimSlash(top);
  final prefix = '$t/';
  final inside = Platform.isWindows
      ? p.toLowerCase().startsWith(prefix.toLowerCase())
      : p.startsWith(prefix);
  return inside ? p.substring(prefix.length) : null;
}

/// `settings_pinned`: on GitButler the work-tree file must equal the one at [ref] (`hash-object` applies the repo's
/// filters, so a CRLF checkout compares equal). A difference, or the file on one side only, is `settings_not_pinned`; a
/// git failure is `git_error`.
Future<void> _settingsPinned(
  PrContext ctx,
  String code,
  String ref,
  String branch,
  bool afterMerge,
) async {
  final top = await _toplevel(ctx, code);
  final path = await _settingsPath(ctx, code);
  var rel = 'openspec/specwright.yaml';
  if (path != null) {
    String resolvedTop = top;
    try {
      resolvedTop = Directory(top).resolveSymbolicLinksSync();
    } on FileSystemException {
      // keep the top level as git printed it
    }
    rel = _relativeTo(path, resolvedTop) ?? rel;
  }
  String? work;
  if (path != null) {
    final r = await ctx.git(top, ['hash-object', '--path=$rel', path]);
    if (r.code != 0) {
      throw PairStop(
        'git_error',
        'git hash-object $rel failed: ${pyStrip(r.stderr)}',
      );
    }
    work = pyStrip(r.stdout);
  }
  final r = await ctx.git(top, ['ls-tree', ref, '--', rel]);
  if (r.code != 0) {
    throw PairStop(
      'git_error',
      'git ls-tree $ref -- $rel failed: ${pyStrip(r.stderr)}',
    );
  }
  final parts = pyStrip(r.stdout).split(RegExp(r'\s+'));
  final tip = parts.length >= 3 ? parts[2] : null;
  if (work == tip) return;
  final how = afterMerge
      ? 'run `but pull` or undo the edit of $rel in the work tree before acting on it'
      : 'commit the edit on $branch, or undo it, before this step';
  final state = work == null
      ? '$rel is missing from the work tree but present at $ref'
      : tip == null
      ? '$rel exists in the work tree but not at $ref'
      : '$rel in the work tree differs from the copy at $ref';
  throw PairStop(
    'settings_not_pinned',
    '$state; with vcs: gitbutler the settings are those the change branch committed: $how',
    extra: {'file': rel, 'ref': ref},
  );
}

/// `gitbutler_pins`: `vcs: gitbutler` in the work-tree file, or a GitButler-managed repo (`gitbutler/` in the common git
/// directory and `gitbutler.project.targetRef` set). A target ref alone is a Git or jj checkout and does not pin.
Future<bool> _gitbutlerPins(PrContext ctx, String code) async {
  if ((await _loadSettings(ctx, code))['vcs'] == 'gitbutler') return true;
  final r = await ctx.git(code, ['rev-parse', '--git-common-dir']);
  final common = pyStrip(r.names('Git common directory'));
  if (r.code != 0 || common.isEmpty) return false;
  final commonDir = Directory(common).isAbsolute ? common : '$code/$common';
  if (!Directory('$commonDir/gitbutler').existsSync()) return false;
  final t = await ctx.git(code, [
    'config',
    '--get',
    'gitbutler.project.targetRef',
  ]);
  return t.code == 0 && pyStrip(t.stdout).isNotEmpty;
}

/// `pin_ref`: the branch, or after a merge the branch while it exists, else the project's target ref.
Future<String> _pinRef(
  PrContext ctx,
  String code,
  String branch,
  bool afterMerge,
) async {
  if (!afterMerge) return 'refs/heads/$branch';
  if (await _hasRef(ctx, code, 'refs/heads/$branch')) {
    return 'refs/heads/$branch';
  }
  final r = await ctx.git(code, [
    'config',
    '--get',
    'gitbutler.project.targetRef',
  ]);
  final target = r.code == 0 ? pyStrip(r.names('GitButler target ref')) : '';
  if (target.isEmpty) {
    throw PairStop(
      'git_error',
      'gitbutler.project.targetRef is not set, so there is no target to compare the settings with',
    );
  }
  return target;
}

/// What `sw vcs` needs of `pr-pair.sh vcs` and `context --only repos`, read in process (D6): the backend the settings
/// choose for [role], and the main branch and login of that role's repo. No reviewer-config write and no identity
/// lookup. Throws [SettingsStop] as the script stopped.
Future<
  ({
    String backend,
    String main,
    String login,
    GitHubConnection connection,
    RemoteSelection remote,
  })
>
readVcsSettings(
  PrContext ctx, {
  required String code,
  required String repo,
  required String role,
}) async {
  final text = await _settingsText(ctx, code);
  final s = loadSettings(text);
  final v = vcsChoices(s);
  final backend = role == 'code' ? v.code : v.store;
  final store = role == 'store' ? repo : null;
  final selection = selectedRemote(s, store: role == 'store');
  final mains = {
    code: await _detectMain(ctx, code, selectedRemote(s).name),
    if (store != null && store.isNotEmpty)
      store: await _detectMain(ctx, store, selection.name),
  };
  final c = contexts(
    s,
    code,
    store,
    detectMain: (d) => mains[d] ?? 'main',
    checkMerge: false,
  );
  final item = role == 'store' ? c.store : c.code;
  return (
    backend: backend,
    main: item?.main ?? '',
    login: item?.login ?? '',
    connection: c.connection,
    remote: selection,
  );
}

/// `context --only repos --branch <branch>` as far as it checks the pin: on GitButler the work-tree settings must be
/// those of `refs/heads/<branch>`. Throws [PairStop] (`settings_not_pinned` with `file` and `ref`, or `git_error`).
Future<void> requireSettingsPinnedTo(
  PrContext ctx,
  String code,
  String branch,
) async {
  if (await _gitbutlerPins(ctx, code)) {
    await _settingsPinned(
      ctx,
      code,
      await _pinRef(ctx, code, branch, false),
      branch,
      false,
    );
  }
}

/// Backend choices for native workflow callers, without a printed document.
Future<({String code, String store})> workflowVcsChoices(
  PrContext ctx,
  String code,
) async {
  final settings = await _loadSettings(ctx, code);
  try {
    return vcsChoices(settings);
  } on SettingsStop catch (e) {
    throw _stopOf(e);
  }
}

/// `cmd_vcs`.
Future<int> runVcs(PrContext ctx, List<String> argv) =>
    runPairCommand(ctx, () async {
      final a = parsePairArgs(argv, const {'--code': 'code'});
      needArgs(a, ['code']);
      final v = await workflowVcsChoices(ctx, a['code']!);
      return {'ok': true, 'code': v.code, 'store': v.store};
    });

/// `cmd_tier`.
Future<int> runTier(PrContext ctx, List<String> argv) =>
    runPairCommand(ctx, () async {
      final a = parsePairArgs(argv, const {'--code': 'code'});
      needArgs(a, ['code']);
      // D4: a refused file or a wrong-shaped section is a note with the cheap tier off, never a stop.
      final text = await _settingsText(ctx, a['code']!);
      try {
        return tierChoice(loadSettings(text));
      } on SettingsStop catch (e) {
        return {'ok': true, 'cheap_tier': false, 'note': e.message};
      }
    });

/// `cmd_context`.
Future<int> runContext(PrContext ctx, List<String> argv) =>
    runPairCommand(ctx, () async {
      final afterMerge = argv.contains('--after-merge');
      final a = parsePairArgs(
        [
          for (final t in argv)
            if (t != '--after-merge') t,
        ],
        const {
          '--code': 'code',
          '--store': 'store',
          '--only': 'only',
          '--branch': 'branch',
        },
      );
      needArgs(a, ['code']);
      final code = a['code']!;
      final givenStore = a['store'];
      final store = givenStore;
      final branch = a['branch'];
      final only = a['only'];
      if (only != null && only != 'repos') pairUsage('--only takes repos');
      if (afterMerge && (branch == null || branch.isEmpty)) {
        pairUsage('--after-merge needs --branch');
      }
      final hasBranch = branch != null && branch.isNotEmpty;
      if (await _gitbutlerPins(ctx, code)) {
        if (only != 'repos' && !hasBranch) {
          pairUsage(
            'with vcs: gitbutler, context for the merge settings needs --branch <branch>',
          );
        }
        if (hasBranch) {
          await _settingsPinned(
            ctx,
            code,
            await _pinRef(ctx, code, branch, afterMerge),
            branch,
            afterMerge,
          );
        }
      }
      final text = await _settingsText(ctx, code);
      final problems = <SettingProblem>[];
      final Contexts c;
      try {
        final settings = loadSettings(text);
        final mains = {
          code: await _detectMain(ctx, code, selectedRemote(settings).name),
          if (store != null && store.isNotEmpty)
            store: await _detectMain(
              ctx,
              store,
              selectedRemote(settings, store: true).name,
            ),
        };
        c = contexts(
          settings,
          code,
          store,
          detectMain: (d) => mains[d] ?? 'main',
          checkMerge: only != 'repos',
          problems: problems,
        );
        _stopOnOversized(problems);
      } on SettingsStop catch (e) {
        throw _stopOf(e);
      }
      Future<Map<String, Object?>> withRepo(RepoContext rc, String dir) async {
        String? repo;
        try {
          repo =
              (await identityOf(
                    ctx,
                    dir,
                    host: c.connection.host,
                    selection: rc.remote,
                  ))['repo']
                  as String?;
        } on PairStop {
          repo = null;
        }
        final written = writeReviewerConfig(rc.reviewers, environment: ctx.env);
        if (written.problem != null) problems.add(written.problem!);
        return {...rc.toJson(), 'repo': repo, 'reviewer_config': written.path};
      }

      final out = c.toJson();
      out['code'] = await withRepo(c.code, code);
      if (c.store != null) out['store'] = await withRepo(c.store!, store!);
      final first = problems.isNotEmpty ? problems.first.text : null;
      return {
        'ok': true,
        ...out,
        if (first != null && first.isNotEmpty) 'settings_problem': first,
      };
    });
