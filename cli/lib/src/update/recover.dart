import 'dart:io';

import 'journal.dart';
import 'lifecycle.dart';
import 'options.dart';
import 'plan.dart' show PlanRecovery;
import 'stage.dart';
import 'stop.dart';
import 'store_gate.dart';
import 'sw_install.dart' show swHome;
import 'swap.dart';

// recover of `scripts/update.sh`: needs the lock. Every step checks the disk
// before it acts, and the journal is removed last, so a rerun after a kill
// during recover decides again from what is left (design D1, D4, D5 of
// native-cli-update).

/// What a recovery did.
class Recovered {
  String action = 'none';
  String message = 'no unfinished update';
  String from = '';
  String to = '';
  bool storeWritten = false;
  String swNote = '';

  /// `rec_json`: the recovered object.
  Map<String, Object?> toJson() => {
    'action': action,
    'message': message,
    'from': from.isEmpty ? null : from,
    'to': to.isEmpty ? null : to,
    'store_written': storeWritten,
    'sw_note': swNote.isEmpty ? null : swNote,
  };
}

/// `cmd_sw_note`: after a rollback to version [v], the note that no sw serves
/// it, or '' when `<home>/.specwright/bin/<v>/` holds one.
String rollbackSwNote(UpdateRun r, String v) {
  if (v.isEmpty) return '';
  final dir = '${swHome(r.environment)}/.specwright/bin/$v';
  if (File('$dir/sw').existsSync() || File('$dir/sw.exe').existsSync()) {
    return '';
  }
  final m = RegExp(r'^(\d+)\.(\d+)\.(\d+)$').firstMatch(v);
  if (m != null &&
      (int.parse(m.group(1)!) == 0 && int.parse(m.group(2)!) < 24)) {
    // binaries ship from 0.24.0 on
    return 'no sw serves $v, which no $v skill needs';
  }
  return 'no sw serves $v: rerun the install prompt for $v to place it';
}

/// `recover_rollback`: the old copies go back, the swapped-in new ones go,
/// the store files or the local config are restored, then staging and journal
/// go. Returns the note for the message, or null.
String? _rollback(UpdateRun r, Journal j) {
  String? sstaging;
  for (final t in j.targets) {
    if (t.gid == 'schema') sstaging = t.staging;
    final newPath = t.newPath, oldPath = t.oldPath, tgt = t.targetPath;
    if (existsOrLink(oldPath)) {
      // the old copy was moved aside: put it back, dropping a new copy that
      // was swapped in
      if (exists(tgt)) _remove(r, tgt, 'could not remove $tgt');
      r.ops.mkdir(t.dir);
      try {
        r.ops.rename(oldPath, tgt);
      } on FileSystemException {
        throw UpdateDie(
          'rename_failed',
          'could not move $oldPath back to $tgt (a directory held open by '
              'another program?)',
        );
      }
    } else if (t.type != 'remove' &&
        !t.installed &&
        !exists(newPath) &&
        exists(tgt)) {
      // first install: the swapped-in copy goes
      _remove(r, tgt, 'could not remove $tgt');
    }
  }
  String? note;
  final combo = '${j.str('role')}/${j.str('store_state')}';
  if (const [
    'owner/pending',
    'owner/written',
    'claim/pending',
    'claim/written',
  ].contains(combo)) {
    restoreStoreFiles(r, j);
  } else if (j.str('role') == 'none' && sstaging != null) {
    note = restoreLocalConfig(r, j, sstaging);
  }
  recoverCleanup(r, j);
  return note;
}

void _remove(UpdateRun r, String path, String why) {
  try {
    r.ops.remove(path);
  } on FileSystemException {
    throw UpdateDie('rename_failed', why);
  }
}

/// `recover_gate`: holds the store gate lock before the store is touched.
Future<void> _recoverGate(
  UpdateRun r,
  Journal j,
  Gate g,
  GateState state, {
  required bool rollback,
}) async {
  switch (state) {
    case GateState.ours:
      return; // held since the interrupted swap: nobody else could have
    case GateState.other:
      throw UpdateDie.from(gateStopLocked(g.path, r.options.code));
    default:
  }
  // none: the swap released it, so the recovery takes it again
  gateTake(r, g);
  final from = j.data['from'];
  gateWriteOwner(
    g.path,
    from is String && from.isNotEmpty ? from : 'none',
    j.str('to'),
    r.options.code,
    j.str('token'),
  );
  if (rollback) {
    // design D5: repeat the store checks; a failure releases the lock and
    // keeps everything
    try {
      await storeCheck(r, j, swapMode: false);
    } on UpdateDie {
      gateRelease(r, g);
      rethrow;
    }
  }
}

/// `recover_core`: decides from the journal and the disk, and acts.
Future<Recovered> recoverCore(UpdateRun r) async {
  final rec = Recovered();
  if (!exists(r.journalPath)) {
    r.ops.remove(r.journalTempPath);
    return rec;
  }
  final j = r.readJournal()!;
  final phase = j.str('phase');
  if (!const ['staging', 'staged', 'swapping', 'swapped'].contains(phase)) {
    throw UpdateDie('journal_unreadable', "update.json has phase '$phase'");
  }
  final to = j.str('to');
  var from = j.str('from');
  if (from == 'null') from = '';
  if (to.isEmpty) {
    throw UpdateDie('journal_unreadable', 'update.json has no target version');
  }
  rec
    ..from = from
    ..to = to;
  final now = r.stamp();
  final targets = j.targets;
  final started = targets.any(
    (t) => t.state == 'old-moved' || t.state == 'swapped',
  );
  final sst = j.str('store_state');
  final role = j.str('role');
  final storeful = role == 'owner' || role == 'claim';
  final gate = Gate();
  var gateState = GateState.none;
  if (storeful && j.str('store_lock').isNotEmpty) {
    // is the store's gate lock this update's own?
    gate.path = j.str('store_lock');
    gateState = gateInspect(gate.path, j.str('token'), r.options.code);
    if (gateState == GateState.ours) gate.held = true;
    if (gateState == GateState.unverified) {
      throw UpdateDie(
        'gate_lock_unverified',
        'the store gate lock ${gate.path} has no owner information (a swap '
            'killed right after creating it, or another session\'s gate '
            'midway through taking it), so this checkout cannot tell whose '
            'it is. Confirm that no session is in a gate or roadmap step on '
            'the store, remove it with rm -r, then rerun the update. The '
            'journal and the staging are kept',
      );
    }
  }
  final rollback = r.options.rollback;
  if (phase == 'swapped' && now == to) {
    if (rollback) {
      throw UpdateDie(
        'rollback_stamped',
        'VERSION already reads $to: the update is complete and cannot be '
            'rolled back',
      );
    }
    if (sst == 'written') rec.storeWritten = true;
    recoverCleanup(r, j);
    rec
      ..action = 'finished'
      ..message = 'finished update to $to';
  } else if (!started) {
    recoverCleanup(r, j);
    rec
      ..action = 'discarded'
      ..message = 'discarded unfinished update to $to';
  } else {
    final resume = !rollback && verifySwapped(j).isEmpty;
    if (resume) {
      if (storeful && sst == 'pending') {
        await _recoverGate(r, j, gate, gateState, rollback: false);
      }
      swapLoop(r, j);
      storeFinish(r, j, gate);
      if (j.str('store_state') == 'written') rec.storeWritten = true;
      final dlv = firstLine('${r.download}/VERSION');
      if (now == to || dlv != to) {
        // nobody will stamp this update: do it here, then finish
        if (now != to) File(r.versionPath).writeAsStringSync('$to\n');
        recoverCleanup(r, j);
      }
      rec
        ..action = 'resumed'
        ..message = 'resumed update to $to';
    } else {
      if (storeful && (sst == 'pending' || sst == 'written')) {
        await _recoverGate(r, j, gate, gateState, rollback: true);
      }
      final note = _rollback(r, j);
      rec
        ..action = 'rolled-back'
        ..message =
            'rolled back to ${from.isEmpty ? 'the state before the first install' : from}'
            '${note == null ? '' : '; $note'}'
        ..swNote = rollbackSwNote(r, from);
    }
  }
  gateRelease(r, gate); // runs after every outcome
  return rec;
}

/// `sw update recover`: the document and its exit status.
Future<(Map<String, Object?>, int)> recoverUpdate(UpdateRun r) async {
  r.acquireLock();
  try {
    final rec = await recoverCore(r);
    final now = r.stamp();
    return (
      {
        'ok': true,
        'interface': updateInterface,
        'subcommand': 'recover',
        'installed': now.isEmpty ? null : now,
        ...rec.toJson(),
        ...r.lockExtra,
      },
      0,
    );
  } finally {
    r.releaseLock();
  }
}

/// The recovery `plan` runs first (design D4): a pending journal is recovered
/// before the plan, and the plan says so in `recovered`. A recovery that
/// finished the swap still owes Step 5 the packs enabled before it.
PlanRecovery planRecovery(UpdateRun r) => (UpdateOptions options) async {
  final Journal? j;
  try {
    j = r.journalFile.read();
  } on JournalUnreadable {
    return null; // an unreadable journal is left to plan's refusal
  }
  if (j == null) return null;
  if (!const [
    'staging',
    'staged',
    'swapping',
    'swapped',
  ].contains(j.str('phase'))) {
    return null;
  }
  final prev = j.data['prev_packs'];
  final packs = prev is List
      ? [
          for (final n in prev)
            if (n is String) n,
        ]
      : null;
  r.acquireLock();
  final Recovered rec;
  try {
    rec = await recoverCore(r);
  } finally {
    r.releaseLock();
  }
  return {
    'recovered': rec.toJson(),
    ...r.lockExtra,
    if ((rec.action == 'finished' || rec.action == 'resumed') &&
        packs != null &&
        !exists(r.journalPath))
      'packs_previous': packs,
  };
};
