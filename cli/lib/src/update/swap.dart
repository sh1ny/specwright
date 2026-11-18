import 'dart:io';
import 'dart:math';

import 'inflight.dart' show inflightEntries;
import 'journal.dart';
import 'lifecycle.dart';
import 'options.dart' show updateInterface;
import 'plan.dart' show workflowUpdate;
import 'stage.dart';
import 'stop.dart';
import 'store.dart' show readStoreRecord, storeRecordPath;
import 'store_gate.dart';
import 'text.dart';

// swap, note-config and finish of `scripts/update.sh`, with what swap and
// recover share: the renames of the swap loop, the store gate lock, the store
// checks and the store files a rollback restores (design D1, D5, D9 of
// native-cli-update).

/// The store's gate lock as this run holds it: [path] is the lock directory
/// (empty while this run knows of none) and [held] says that this run made it
/// or took it over, so it must release it.
class Gate {
  String path = '';
  bool held = false;
}

/// `gate_release`: removes the lock this run holds; a failure stops.
void gateRelease(UpdateRun r, Gate g) {
  if (!g.held) return;
  g.held = false;
  try {
    r.ops.remove(g.path);
  } on FileSystemException {
    throw UpdateDie(
      'gate_release_failed',
      'could not remove the store gate lock ${g.path}',
    );
  }
}

/// `mkdir GATE || gate_stop_locked`, then the lock is this run's.
void gateTake(UpdateRun r, Gate g) {
  if (!r.ops.mkdirExclusive(g.path)) {
    throw UpdateDie.from(gateStopLocked(g.path, r.options.code));
  }
  g.held = true;
}

/// The `from` a gate owner file names: `none` for a first install.
String _fromWord(Journal j) {
  final from = j.data['from'];
  return from is String && from.isNotEmpty ? from : 'none';
}

/// A move whose failure is `rename_failed` with [why].
void moveOrDie(UpdateRun r, String from, String to, String why) {
  try {
    r.ops.rename(from, to);
  } on FileSystemException {
    throw UpdateDie('rename_failed', why);
  }
}

void _removeOrDie(UpdateRun r, String path) {
  try {
    r.ops.remove(path);
  } on FileSystemException {
    throw UpdateDie('rename_failed', 'could not remove $path');
  }
}

/// `swap_loop`: the renames of every target, from the journal and the disk;
/// it ends with phase swapped. Every state change is written first.
void swapLoop(UpdateRun r, Journal j) {
  final made = <String>{};
  for (final t in j.targets) {
    final newPath = t.newPath, oldPath = t.oldPath, tgt = t.targetPath;
    void aside() {
      j.setTargetState(t.gid, t.name, 'old-moved');
      r.flush(j);
      if (made.add('${t.staging}/old')) r.ops.mkdir('${t.staging}/old');
      moveOrDie(
        r,
        tgt,
        oldPath,
        'could not move $tgt to $oldPath (a directory held open by another '
        'program?)',
      );
    }

    if (t.type == 'remove') {
      // a pack's skill that is no longer enabled: target -> old/<name>
      if (existsOrLink(tgt)) {
        if (existsOrLink(oldPath)) {
          throw UpdateDie(
            'inconsistent',
            '${t.name}: $tgt and $oldPath both exist',
          );
        }
        aside();
      }
      if (!(t.state == 'swapped' && !exists(tgt))) {
        j.setTargetState(t.gid, t.name, 'swapped');
        r.flush(j);
      }
      continue;
    }
    if (!exists(newPath)) {
      // already swapped (a rerun after an interruption)
      if (!exists(tgt)) {
        throw UpdateDie(
          'inconsistent',
          '${t.name}: neither $newPath nor $tgt exists',
        );
      }
      if (t.state != 'swapped') {
        j.setTargetState(t.gid, t.name, 'swapped');
        r.flush(j);
      }
      continue;
    }
    if (exists(tgt)) {
      if (existsOrLink(oldPath)) {
        throw UpdateDie(
          'inconsistent',
          '${t.name}: $tgt, $newPath and $oldPath all exist',
        );
      }
      aside();
    }
    j.setTargetState(t.gid, t.name, 'swapped');
    r.flush(j);
    if (made.add(t.dir)) r.ops.mkdir(t.dir);
    moveOrDie(
      r,
      newPath,
      tgt,
      'could not move $newPath to $tgt (a directory held open by another '
      'program?)',
    );
    if (!(exists(tgt) && !exists(newPath))) {
      throw UpdateDie(
        'inconsistent',
        '${t.name}: the rename to $tgt did not take effect',
      );
    }
  }
  j.set('phase', 'swapped');
  r.flush(j);
}

/// `store_finish`: after the swap loop, the STORE record is written (once),
/// then the gate lock is released.
void storeFinish(UpdateRun r, Journal j, Gate g) {
  if (j.str('store_state') == 'pending') {
    final staging = j.str('store_staging');
    final record = j.str('store_record');
    r.ops.mkdir(_dirname(record));
    File('$staging/STORE.new').writeAsStringSync(
      'version: ${_text(j.data['to'])}\nowner: ${j.str('owner_id')}\n',
    );
    moveOrDie(r, '$staging/STORE.new', record, 'could not write $record');
    j.set('store_state', 'written');
    r.flush(j);
  }
  gateRelease(r, g);
}

String _text(Object? v) => v == null ? 'null' : '$v';

String _dirname(String path) {
  final i = path.lastIndexOf('/');
  return i <= 0 ? '/' : path.substring(0, i);
}

/// `restore_store_files`: the store's previous config.yaml and STORE (or
/// their absence), saved in the schema staging.
void restoreStoreFiles(UpdateRun r, Journal j) {
  final prev = '${j.str('store_staging')}/prev';
  final cfg = '${r.options.root}/openspec/config.yaml';
  final record = j.str('store_record');
  void put(String source, String target) {
    try {
      r.ops.copy(source, _dirname(target));
    } on FileSystemException {
      throw UpdateDie('rename_failed', 'could not restore $target');
    }
  }

  if (j.str('prev_config') == 'present') {
    if (FileSystemEntity.isFileSync('$prev/config.yaml')) {
      put('$prev/config.yaml', cfg);
    }
  } else if (j.str('config_sha').isNotEmpty && exists(cfg)) {
    r.ops.remove(cfg); // absent before the update: the merge created it
  }
  if (j.str('prev_store') == 'present') {
    if (FileSystemEntity.isFileSync('$prev/STORE')) put('$prev/STORE', record);
  } else {
    r.ops.remove(record);
  }
}

String _fileSha(String path) => sha256Hex(File(path).readAsBytesSync());

/// `restore_local_config`: a repo-local install's config.yaml as it was
/// before the update. Returns the note for the recovery message, or null.
String? restoreLocalConfig(UpdateRun r, Journal j, String schemaStaging) {
  final prev = '$schemaStaging/prev/config.yaml';
  final cfg = '${r.options.root}/openspec/config.yaml';
  final pc = j.str('prev_config');
  final written = j.str('config_sha');
  const kept = 'config.yaml kept: it was edited after note-config';
  if (pc.isEmpty) return null; // never saved: the swap did not get that far
  if (pc == 'present') {
    if (!FileSystemEntity.isFileSync(prev)) return null;
    if (exists(cfg)) {
      final cur = _fileSha(cfg);
      if (cur != written && cur != _fileSha(prev)) return kept;
    }
    try {
      r.ops.copy(prev, _dirname(cfg));
    } on FileSystemException {
      throw UpdateDie('rename_failed', 'could not restore $cfg');
    }
  } else if (written.isNotEmpty && exists(cfg)) {
    // absent before the update: the merge created it
    if (_fileSha(cfg) == written) {
      r.ops.remove(cfg);
    } else {
      return kept;
    }
  }
  return null;
}

/// What the store check allows the swap to do.
enum StoreMode { write, codeOnly, rollback }

({int major, int minor}) _majorMinor(String v) {
  final p = v.split('.');
  return (major: int.parse(p[0]), minor: int.parse(p[1]));
}

/// `written_by_update`: allowed(path) for a recovery run: the update's
/// staging, the schema it swapped in (each file as the manifest has it), the
/// STORE it wrote and the config.yaml the prompt merged and noted, each still
/// with the recorded content.
bool Function(String) writtenByUpdate(Journal j, String top) {
  final groups = {for (final g in j.groups) g['id']: g};
  final staging = [
    for (final g in j.groups) ?relToTop(top, g['staging'] as String),
  ];
  final schema = groups['schema'];
  final schemaRel = schema == null
      ? null
      : relToTop(top, '${schema['dir']}/specwright');
  final manifest = {
    for (final m in j.manifest)
      if (m['group'] == 'schema') m['path'] as String: m['sha256'],
  };
  final recordRel = relToTop(top, j.str('store_record'));
  final configRel = relToTop(top, '${j.str('root')}/openspec/config.yaml');
  final wantRecord =
      'version: ${_text(j.data['to'])}\nowner: ${j.str('owner_id')}\n';
  final prevConfig = j.data['store_staging'] != null
      ? '${j.str('store_staging')}/prev/config.yaml'
      : null;
  final configOk = <String>{
    if (j.str('config_sha').isNotEmpty) j.str('config_sha'),
    if (prevConfig != null && FileSystemEntity.isFileSync(prevConfig))
      _fileSha(prevConfig),
  };
  return (String path) {
    if (under(path, staging)) return true;
    if (schemaRel != null && under(path, [schemaRel])) {
      final sub = 'specwright/${path.substring(schemaRel.length + 1)}';
      final f = '$top/$path';
      return FileSystemEntity.isFileSync(f)
          ? _fileSha(f) == manifest[sub]
          : !manifest.containsKey(sub);
    }
    if (path == recordRel) {
      final f = '$top/$path';
      return FileSystemEntity.isFileSync(f) &&
          decodeLossy(File(f).readAsBytesSync()).replaceAll('\r', '') ==
              wantRecord;
    }
    if (path == configRel) {
      final f = '$top/$path';
      return FileSystemEntity.isFileSync(f) && configOk.contains(_fileSha(f));
    }
    return false;
  };
}

bool _treesEqual(String a, String b) {
  if (!(Directory(a).existsSync() && Directory(b).existsSync())) return false;
  final fa = filesUnder(a), fb = filesUnder(b);
  if (fa.length != fb.length) return false;
  final sa = fa.toList()..sort(), sb = fb.toList()..sort();
  for (var i = 0; i < sa.length; i++) {
    if (sa[i] != sb[i]) return false;
    final x = File('$a/${sa[i]}').readAsBytesSync();
    final y = File('$b/${sb[i]}').readAsBytesSync();
    if (x.length != y.length) return false;
    for (var k = 0; k < x.length; k++) {
      if (x[k] != y[k]) return false;
    }
  }
  return true;
}

/// `cmd_store_check`: under the store gate lock (design D5 steps 1-2). In
/// swap mode STORE must not name another owner now, and the store must be
/// free; a busy store allows a patch whose staged schema is byte-identical
/// (code-only). In rollback mode the recovery rule applies. A stop throws.
Future<(StoreMode, String?)> storeCheck(
  UpdateRun r,
  Journal j, {
  required bool swapMode,
}) async {
  final planning = await r.repo.planningRepo();
  if (planning == null) {
    throw UpdateDie(
      'store_unavailable',
      "the store's git directory could not be found when the update was staged",
    );
  }
  final top = planning.top;
  final me = j.str('owner_id');
  final read = readStoreRecord(j.str('store_record'));
  if (read.problem != null) {
    throw UpdateDie(
      'store_record_unreadable',
      "the store's record is unreadable: ${read.problem}",
    );
  }
  final rec = read.record;
  final role = j.str('role');
  final to = j.str('to');
  if (swapMode) {
    if (rec != null && rec.owner != me) {
      if (role == 'claim') {
        throw UpdateDie(
          'store_claimed',
          'the store was claimed by ${rec.owner} (version ${rec.version}) '
              'after this update was planned: only the owner replaces its '
              'schema, and nothing was written. Rerun the update to plan it '
              'again',
        );
      }
      throw UpdateDie(
        'store_owner_changed',
        "the store's schema is now owned by ${rec.owner} (version "
            '${rec.version}), not by $me; nothing was written. Rerun the '
            'update to plan it again',
      );
    }
    // checkouts of one repository share the owner id, so a record another
    // checkout wrote since this claim was planned passes the owner test
    if (role == 'claim' && rec != null && rec.version != to) {
      throw UpdateDie(
        'store_claimed',
        'the store was claimed by ${rec.owner} (version ${rec.version}) '
            'after this update was planned to claim it at $to: only the owner '
            'replaces its schema, and nothing was written. Rerun the update '
            'to plan it again',
      );
    }
    if (role == 'owner' &&
        rec != null &&
        rec.version != j.data['store_version']) {
      throw UpdateDie(
        'store_version_changed',
        'the store now records version ${rec.version} (owner ${rec.owner}), '
            'not the ${_text(j.data['store_version'])} this update was '
            'planned against; nothing was written. Rerun the update to plan '
            'it again',
      );
    }
    final staging = [
      for (final g in j.groups) ?relToTop(top, g['staging'] as String),
    ];
    final (reason, _) = await storeBusyReason(
      r.options,
      r.repo,
      top,
      (p) => under(p, staging),
    );
    if (reason == null) return (StoreMode.write, null);
    if (!workflowUpdate(j.data['from'] as String?, to)) {
      final sg = j.groups.firstWhere((g) => g['kind'] == 'schema');
      if (_treesEqual(
        '${sg['staging']}/new/specwright',
        '${sg['dir']}/specwright',
      )) {
        return (StoreMode.codeOnly, reason);
      }
    }
    throw UpdateDie(
      'store_busy',
      '$reason. A store schema is swapped only on a free store: finish that '
          'change first (merge or archive it, so the store is back on its '
          'main with nothing uncommitted), then rerun the update. Nothing was '
          'written',
    );
  }
  if (rec != null && rec.owner != me) {
    throw UpdateDie(
      'store_owner_changed',
      "the store's schema is now owned by ${rec.owner}, not by $me; the "
          'swapped state and the journal are kept',
    );
  }
  if (j.data['store_state'] == 'written' &&
      (rec == null || rec.version != to)) {
    throw UpdateDie(
      'store_owner_changed',
      "the store's record no longer reads version: $to owned by $me; the "
          'swapped state and the journal are kept',
    );
  }
  final (reason, _) = await storeBusyReason(
    r.options,
    r.repo,
    top,
    writtenByUpdate(j, top),
  );
  if (reason != null) {
    throw UpdateDie(
      'store_busy',
      '$reason. The rollback stops before any rename and the swapped state '
          'and the journal are kept; the store stays on $to. Finish that '
          'change, then run the rollback again',
    );
  }
  return (StoreMode.rollback, null);
}

/// `cmd_swap_check`: before the first rename of a workflow update, the
/// changes in flight are collected and validated again against the staged
/// schema; a difference from what stage recorded stops.
Future<void> swapCheck(UpdateRun r, Journal j) async {
  final inflight = j.data['inflight'];
  final rec = inflight is Map ? inflight : const <String, Object?>{};
  if (rec['checked'] != true) return;
  final schema =
      '${j.groups.firstWhere((g) => g['kind'] == 'schema')['staging']}/new/specwright';
  final found = await inflightEntries(
    repo: r.repo,
    ops: r.ops,
    run: r.openspec,
    download: r.download,
    stateDir: r.state,
    to: j.str('to'),
    schemaDir: schema,
    role: j.str('role').isEmpty ? 'none' : j.str('role'),
  );
  String key(Map<Object?, Object?> e) =>
      '${e['name']}\x00${e['source']}\x00${e['status']}';
  final was = {
    for (final e in (rec['changes'] as List? ?? const []))
      key(e as Map<Object?, Object?>): (e).cast<String, Object?>(),
  };
  final now = {for (final e in found.entries) key(e): e};
  final diffs = <String>[];
  for (final entry in now.entries) {
    if (was.containsKey(entry.key)) continue;
    final e = entry.value;
    final status = e['status'];
    if (status == 'invalid') {
      diffs.add(
        "${e['name']} (${e['source']}) fails validation against "
        "${j.str('to')}: ${e['error']}${e['note'] ?? ''}",
      );
    } else if (status == 'other project') {
      diffs.add(
        "${e['name']} (${e['source']}) belongs to another project and is in "
        'flight in the store',
      );
    } else {
      diffs.add(
        "${e['name']} (${e['source']}) was not in flight when the update was "
        'planned',
      );
    }
  }
  for (final entry in was.entries) {
    if (now.containsKey(entry.key)) continue;
    final e = entry.value;
    diffs.add(
      "${e['name']} (${e['source']}) was in flight when the update was "
      'planned and is not now',
    );
  }
  if (diffs.isEmpty) return;
  throw UpdateDie(
    'inflight_changed',
    'the changes in flight differ from the plan, so nothing was swapped: '
        '${diffs.join('; ')}',
    extra: {'differences': diffs},
  );
}

/// `cmd_store_recheck`: before the first rename of role other (no gate lock),
/// STORE is read again; its major.minor must still be the update's target.
void storeRecheck(UpdateRun r, Journal j) {
  final path = storeRecordPath(r.options.root);
  final read = readStoreRecord(path);
  var problem = read.problem;
  if (read.record == null && problem == null) problem = '$path does not exist';
  final to = j.str('to');
  final want = _majorMinor(to);
  final String why;
  if (problem != null) {
    why = "the store's record is now unreadable: $problem";
  } else if (_majorMinor(read.record!.version) == want) {
    return;
  } else {
    why =
        'the store now records version ${read.record!.version} and its '
        'schema is owned by ${read.record!.owner}';
  }
  throw UpdateDie(
    'other_store_version',
    "$why, which is not the ${want.major}.${want.minor} line this project's "
        'update to $to was planned for, and only the owner replaces the '
        "store's schema. Nothing was written. Rerun the update to plan it "
        'again',
  );
}

/// `swap_refused`: a swap refused before its first rename (design D7): this
/// update's staging and journal go, then the refusal.
Never _refuse(UpdateRun r, Journal j, UpdateDie stop) {
  recoverCleanup(r, j);
  throw stop;
}

String _token() {
  final rng = Random.secure();
  String word(int v) => v.toRadixString(16).padLeft(8, '0');
  return word((rng.nextInt(1 << 15) << 15) | rng.nextInt(1 << 15)) +
      word((rng.nextInt(1 << 15) << 15) | rng.nextInt(1 << 15)) +
      word(pid);
}

/// `swap_store_prepare`: the store half of the swap up to the first rename;
/// every stop releases the gate lock.
Future<void> _swapStorePrepare(UpdateRun r, Journal j, Gate g) async {
  final gate = j.str('store_lock');
  if (gate.isEmpty) {
    throw UpdateDie(
      'store_unavailable',
      "the store's git directory could not be found when the update was staged",
    );
  }
  final token = _token();
  j.set('token', token); // the token reaches the journal first
  r.flush(j);
  g.path = gate;
  gateTake(r, g); // then the lock
  gateWriteOwner(gate, _fromWord(j), j.str('to'), r.options.code, token);
  // under the lock: 1. STORE read again, 2. the store is free
  final StoreMode mode;
  try {
    (mode, _) = await storeCheck(r, j, swapMode: true);
  } on UpdateDie catch (e) {
    gateRelease(r, g);
    _refuse(r, j, e);
  }
  final mismatches = verifyStaged(j);
  if (mismatches != null) {
    gateRelease(r, g);
    _refuse(r, j, verificationFailed(mismatches));
  }
  if (mode == StoreMode.codeOnly) {
    // a busy store, schema unchanged: leave the store alone
    _removeOrDie(r, j.str('store_staging'));
    j.data['groups'] = [
      for (final x in j.groups)
        if (x['kind'] != 'schema') x,
    ];
    j.data['targets'] = [
      for (final x in j.list('targets'))
        if (x['gid'] != 'schema') x,
    ];
    j.data['manifest'] = [
      for (final x in j.manifest)
        if (x['group'] != 'schema') x,
    ];
    j.data['store_state'] = 'current';
    r.flush(j);
    gateRelease(r, g);
    return;
  }
  // 3. the changes in flight again, 4. the store's config.yaml and STORE
  // saved for a rollback
  try {
    await swapCheck(r, j);
  } on UpdateDie catch (e) {
    gateRelease(r, g);
    _refuse(r, j, e);
  }
  final staging = j.str('store_staging');
  final cfg = '${r.options.root}/openspec/config.yaml';
  final record = j.str('store_record');
  r.ops.mkdir('$staging/prev');
  var prevConfig = 'absent', prevStore = 'absent';
  if (FileSystemEntity.isFileSync(cfg)) {
    r.ops.copy(cfg, '$staging/prev');
    prevConfig = 'present';
  }
  if (FileSystemEntity.isFileSync(record)) {
    r.ops.copy(record, '$staging/prev');
    prevStore = 'present';
  }
  j.set('prev_config', prevConfig);
  j.set('prev_store', prevStore);
}

/// `save_local_config`: role none, the config.yaml (or its absence) before
/// the update, in the schema group's staging.
void _saveLocalConfig(UpdateRun r, Journal j) {
  final cfg = '${r.options.root}/openspec/config.yaml';
  for (final t in j.targets) {
    if (t.gid != 'schema') continue;
    var prev = 'absent';
    r.ops.mkdir('${t.staging}/prev');
    if (FileSystemEntity.isFileSync(cfg)) {
      try {
        r.ops.copy(cfg, '${t.staging}/prev');
      } on FileSystemException {
        throw UpdateDie('rename_failed', 'could not save $cfg');
      }
      prev = 'present';
    }
    j.set('prev_config', prev);
    r.flush(j);
    return;
  }
}

/// `sw update swap`: the document and its exit status.
Future<(Map<String, Object?>, int)> swapUpdate(UpdateRun r) async {
  // settings edited since stage stop here, before the lock, the journal or
  // the store gate: every role, also one whose swap never asks a VCS question
  r.repo;
  r.acquireLock();
  try {
    final j = r.readJournal();
    if (j == null) {
      throw UpdateDie(
        'no_journal',
        'no staged update is recorded in ${r.journalPath}; run stage first',
      );
    }
    final phase = j.str('phase');
    if (!const ['staged', 'swapping', 'swapped'].contains(phase)) {
      throw UpdateDie(
        'not_staged',
        "the recorded update is in phase '$phase', not staged; run recover "
            'first',
      );
    }
    final role = j.str('role');
    final storeful = role == 'owner' || role == 'claim';
    if (phase != 'staged') {
      throw UpdateDie(
        'swap_interrupted',
        "this update's swap was started (phase $phase); run recover from this "
            'checkout to finish or undo it',
      );
    }
    final gate = Gate();
    if (storeful) {
      await _swapStorePrepare(r, j, gate);
    } else {
      final mismatches = verifyStaged(j);
      if (mismatches != null) _refuse(r, j, verificationFailed(mismatches));
      try {
        await swapCheck(r, j);
      } on UpdateDie catch (e) {
        _refuse(r, j, e);
      }
      if (role == 'none') _saveLocalConfig(r, j);
      if (role == 'other') {
        // no gate lock for another project (D5): STORE read again just
        // before the first rename
        try {
          storeRecheck(r, j);
        } on UpdateDie catch (e) {
          _refuse(r, j, e);
        }
      }
    }
    j.set('phase', 'swapping');
    r.flush(j);
    swapLoop(r, j);
    if (storeful) storeFinish(r, j, gate);
    return (await reportDocument(r, 'swap', j, r.lockExtra), 0);
  } finally {
    r.releaseLock();
  }
}

/// `sw update note-config`: records the merged config.yaml right after the
/// prompt's Step 5, so a rollback accepts it.
Future<(Map<String, Object?>, int)> noteConfig(UpdateRun r) async {
  r.acquireLock();
  try {
    final j = r.readJournal();
    if (j == null) {
      throw UpdateDie(
        'no_journal',
        'no update is recorded in ${r.journalPath}; run stage and swap first',
      );
    }
    if (j.str('phase') != 'swapped') {
      throw UpdateDie(
        'not_swapped',
        "the recorded update is in phase '${j.str('phase')}', not swapped; "
            'note-config runs after swap, right after Step 5',
      );
    }
    final cfg = '${r.options.root}/openspec/config.yaml';
    if (!FileSystemEntity.isFileSync(cfg)) {
      throw UpdateDie(
        'config_missing',
        '$cfg does not exist; run Step 5 first',
      );
    }
    final sum = _fileSha(cfg);
    j.set('config_sha', sum);
    r.flush(j);
    return (
      await reportDocument(r, 'note-config', j, {'config': cfg, 'sha256': sum}),
      0,
    );
  } finally {
    r.releaseLock();
  }
}

/// `sw update finish`: after the stamp, the journal and the staging go.
Future<(Map<String, Object?>, int)> finishUpdate(UpdateRun r) async {
  r.acquireLock();
  try {
    final j = r.readJournal();
    if (j == null) {
      return (
        {
          'ok': true,
          'interface': updateInterface,
          'subcommand': 'finish',
          'state': 'done',
          'finished': false,
          'message': 'no update is in progress',
        },
        0,
      );
    }
    final to = j.str('to');
    final phase = j.str('phase');
    final now = r.stamp();
    if (now != to) {
      throw UpdateDie(
        'not_stamped',
        "VERSION reads '${now.isEmpty ? 'missing' : now}', not $to; finish "
            'runs after the stamp',
      );
    }
    if (phase != 'swapped') {
      throw UpdateDie(
        'not_swapped',
        "the recorded update is in phase '$phase', not swapped; run recover "
            'first',
      );
    }
    final doc = await reportDocument(r, 'finish', j, {
      'state': 'done',
      'finished': true,
    });
    removeStaging(r, stagingOf(j));
    r.ops.remove(r.journalTempPath);
    r.ops.remove(r.journalPath);
    return (doc, 0);
  } finally {
    r.releaseLock();
  }
}
