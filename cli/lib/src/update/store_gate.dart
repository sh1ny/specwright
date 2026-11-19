import 'dart:io';

import '../commands/vcs.dart' show VcsContext, openSession, stateDocument;
import '../gate/lock.dart';
import '../vcs/args.dart' show VcsRequest;
import '../vcs/stop.dart' show VcsStop;
import 'file_ops.dart';
import 'options.dart';
import 'repo.dart';
import 'stop.dart';
import 'text.dart';

export '../gate/lock.dart' show GateOwner, gateRead, gateToken, gateWriteOwner;

// The "is the store free" test of `sw update` (design D5 of the update's store
// roles), ported from `scripts/update.sh`, and its use of the store gate lock.
// The lock itself lives in `../gate/lock.dart`, shared with `sw gate`.

/// `<store git common dir>/specwright-gate.lock`, the lock of
/// `skills/specwright-branch`; null outside a repo.
Future<String?> gateLockPath(UpdateRepo repo) async {
  final planning = await repo.planningRepo();
  if (planning == null) return null;
  final dir = await repo.commonDir(planning.top);
  return dir == null ? null : '$dir/specwright-gate.lock';
}

/// `gate_stop_locked`: the stop when the gate lock is held by someone else.
UpdateStop gateStopLocked(String gate, String code) {
  final o = gateRead(gate);
  if (o.change.startsWith('specwright-update')) {
    if (o.code == code) {
      return UpdateStop(
        'store_locked',
        'the store gate lock $gate is held by an earlier swap of this checkout '
            '(${o.holder}); run recover from this checkout, it takes the lock '
            'over and releases it',
      );
    }
    return UpdateStop(
      'store_locked',
      'the store gate lock $gate is held by an update from '
          '${o.code.isEmpty ? 'another checkout' : o.code} (${o.holder}); '
          'rerun the update there',
    );
  }
  return UpdateStop(
    'store_locked',
    'the store gate lock $gate is held by ${o.holder}; another session is in '
        'its gate or roadmap step for this store. Nothing was written. Wait '
        'for it, or when it is stale confirm that no session uses the store '
        'and remove it with rm -r',
  );
}

/// What `gate_inspect` finds: no lock, this update's own (its token), an
/// owner-less lock while a token is known, or someone else's.
enum GateState { none, ours, unverified, other }

GateState gateInspect(String dir, String token, String code) {
  if (!Directory(dir).existsSync()) return GateState.none;
  final owner = File('$dir/owner');
  if (!owner.existsSync() || owner.lengthSync() == 0) {
    return token.isNotEmpty ? GateState.unverified : GateState.other;
  }
  final o = gateRead(dir);
  return token.isNotEmpty &&
          o.change.startsWith('specwright-update') &&
          o.code == code &&
          o.token == token
      ? GateState.ours
      : GateState.other;
}

/// Takes the gate lock ([ops] makes the directory, so a kill test counts it);
/// stops naming the holder when it is already held.
void gateAcquire(UpdateFileOps ops, String gate, String code) {
  if (!ops.mkdirExclusive(gate)) throw gateStopLocked(gate, code);
}

/// `store_main_name`: the store's main as a local branch name: the one the
/// settings name, else `main`, else `master`; null when none exists.
Future<String?> storeMainName(UpdateRepo repo, String top) async {
  final configured = await repo.configuredMain();
  if (configured != null && configured.isNotEmpty) return configured;
  for (final c in ['main', 'master']) {
    final r = await repo.git(top, [
      'rev-parse',
      '--verify',
      '-q',
      'refs/heads/$c',
    ]);
    if (r.ok) return c;
  }
  return null;
}

String _squash(String text) =>
    text.split(RegExp(r'\s+')).where((w) => w.isNotEmpty).join(' ');

/// `dirty_paths`: the paths `git status --porcelain` lists (every untracked
/// file by name), or the problem when git status failed.
Future<({List<String> paths, String? problem})> dirtyPaths(
  UpdateRepo repo,
  String top,
) async {
  final r = await repo.git(top, [
    'status',
    '--porcelain',
    '-z',
    '--untracked-files=all',
  ]);
  if (!r.ok) {
    final err = _squash(r.errText);
    return (
      paths: <String>[],
      problem:
          'git status failed in the store (exit ${r.code}: '
          '${err.isEmpty ? 'no message' : err})',
    );
  }
  final parts = r.text.split('\x00');
  final found = <String>[];
  var i = 0;
  while (i < parts.length) {
    final e = parts[i++];
    if (e.length < 4) continue;
    found.add(e.substring(3));
    // the original path follows a rename or copy; it is checked too
    if ('RC'.contains(e[0]) && i < parts.length) found.add(parts[i++]);
  }
  return (paths: found, problem: null);
}

/// A store staging directory of the schema, as git lists it.
final RegExp stagingPattern = RegExp(
  r'^(?:.*/)?openspec/\.specwright-update-schemas[^/]*',
);

/// `ignored_staging`: the store staging directories Git ignores, or the
/// problem when git failed.
Future<({List<String> paths, String? problem})> ignoredStaging(
  UpdateRepo repo,
  String top,
) async {
  final r = await repo.git(top, [
    'ls-files',
    '-z',
    '--others',
    '--ignored',
    '--exclude-standard',
    '--directory',
  ]);
  if (!r.ok) {
    final err = _squash(r.errText);
    return (
      paths: <String>[],
      problem:
          'git ls-files failed in the store (exit ${r.code}: '
          '${err.isEmpty ? 'no message' : err})',
    );
  }
  final found = [
    for (final p in r.text.split('\x00'))
      if (p.isNotEmpty) p.replaceFirst(RegExp(r'/+$'), ''),
  ];
  return (
    paths: [
      for (final p in found)
        if (stagingPattern.firstMatch(p)?.group(0) == p) p,
    ],
    problem: null,
  );
}

/// True when [path] is one of [prefixes] or below one.
bool under(String path, List<String> prefixes) =>
    prefixes.any((p) => path == p || path.startsWith('$p/'));

/// The branch of a jj store by the jj rule, read in process through the
/// `sw vcs state` handler (no script runs): the change bookmark at `@-`, else
/// the store's main when main points at `@-`, else empty.
Future<({String? branch, String? problem})> jjStoreBranch(
  UpdateOptions options,
  String top,
) async {
  final request = VcsRequest(
    command: 'state',
    repo: top,
    role: 'store',
    code: options.code,
  );
  try {
    final session = await openSession(VcsContext(request));
    final doc = await stateDocument(session);
    final empty = doc['branch'] == null || doc['branch'] == '';
    final branch = doc['on_main'] == true && empty
        ? doc['main']
        : doc['branch'];
    return (branch: branch is String ? branch : '', problem: null);
  } on VcsStop catch (e) {
    return (
      branch: null,
      problem:
          'sw vcs state failed in the store (${e.code}: '
          '${e.message.isEmpty ? 'no message' : e.message})',
    );
  }
}

/// `store_busy_reason`: why the store is not free, or null. It must be on its
/// main, and `git status` may list only paths for which [allowed] is true.
/// Returns the reason and the branch.
Future<(String?, String)> storeBusyReason(
  UpdateOptions options,
  UpdateRepo repo,
  String top,
  bool Function(String path) allowed,
) async {
  String branch;
  if (repo.settings.storeIsJj) {
    final read = await jjStoreBranch(options, top);
    if (read.problem != null) return (read.problem, '');
    branch = read.branch!;
    if (branch.isEmpty) {
      return (
        'the store is on no branch (a jj store whose @- has neither main nor '
            'a change bookmark)',
        branch,
      );
    }
  } else {
    branch = pyStrip((await repo.git(top, ['branch', '--show-current'])).text);
  }
  final main = await storeMainName(repo, top);
  if (branch.isEmpty) return ('the store has a detached HEAD', branch);
  if (branch != main) {
    return (
      'the store is on $branch, not on its main '
          '(${main ?? 'no main branch found'})',
      branch,
    );
  }
  final status = await dirtyPaths(repo, top);
  if (status.problem != null) return (status.problem, branch);
  final hidden = await ignoredStaging(repo, top);
  if (hidden.problem != null) return (hidden.problem, branch);
  final dirty = [
    for (final p in status.paths)
      if (!allowed(p)) p,
  ];
  final other = <String>[];
  for (final p in [
    ...dirty,
    for (final h in hidden.paths)
      if (!allowed(h)) h,
  ]) {
    final m = stagingPattern.firstMatch(p)?.group(0);
    if (m != null && !other.contains(m)) other.add(m);
  }
  if (other.isNotEmpty) {
    return (
      "another checkout's update is staged in the store: ${other.first}; "
          'finish or recover it by rerunning the update in that checkout',
      branch,
    );
  }
  if (dirty.isNotEmpty) {
    final shown =
        dirty.take(5).join(', ') +
        (dirty.length > 5 ? ' and ${dirty.length - 5} more' : '');
    return ('the store has uncommitted changes: $shown', branch);
  }
  return (null, branch);
}
