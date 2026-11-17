import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart' show sha256;

import 'inflight.dart' show scratchName;
import 'journal.dart';
import 'lifecycle.dart';
import 'plan.dart';
import 'stop.dart';
import 'store.dart' show storeRecordPath;
import 'store_gate.dart' show gateLockPath;

// `sw update stage`: copies every new skill directory, agent file and the schema
// into a staging directory beside its target, verifies the staged copy against
// a SHA-256 manifest and records it all in the journal (design D1, D2 of
// native-cli-update), ported from `do_stage` and the helper's `journal-new`,
// `ops`, `carry` and `verify` of `scripts/update.sh`. Installed files are never
// touched. Every file operation goes through [UpdateFileOps] (C1).

/// The SHA-256 of [bytes] as 64 hex digits.
String sha256Hex(List<int> bytes) => sha256.convert(bytes).toString();

/// The `model:` line (as the bytes of its text) in the frontmatter of an agent
/// file, or null.
String? _modelLine(String latin) {
  if (!latin.startsWith('---')) return null;
  final end = latin.indexOf('\n---', 3);
  final region = end > 0 ? latin.substring(0, end) : latin;
  final match = RegExp(
    r'^model:[^\r\n]*',
    multiLine: true,
  ).firstMatch(region);
  return match?.group(0);
}

/// The downloaded agent file with the installed file's `model:` line (the
/// user's choice, kept); [data] unchanged when there is none to carry.
List<int> carryModel(List<int> data, String installed) {
  if (!FileSystemEntity.isFileSync(installed)) return data;
  final text = latin1.decode(data);
  final fresh = _modelLine(text);
  final old = _modelLine(latin1.decode(File(installed).readAsBytesSync()));
  if (fresh == null || old == null || fresh == old) return data;
  final at = text.indexOf(fresh);
  return latin1.encode(
    text.substring(0, at) + old + text.substring(at + fresh.length),
  );
}

/// The files under [dir] as relative posix paths, in the order Python sorts
/// `Path` objects (by path part). A link counts when it points at a file.
List<String> filesUnder(String dir) {
  final out = <String>[];
  final root = Directory(dir);
  if (!root.existsSync()) return out;
  for (final e in root.listSync(recursive: true, followLinks: false)) {
    final isFile = e is File || (e is Link && FileSystemEntity.isFileSync(e.path));
    if (!isFile) continue;
    out.add(_forward(e.path).substring(_forward(dir).length + 1));
  }
  out.sort(_comparePathParts);
  return out;
}

String _forward(String path) =>
    Platform.isWindows ? path.replaceAll(r'\', '/') : path;

int _comparePathParts(String a, String b) {
  final x = a.split('/');
  final y = b.split('/');
  for (var i = 0; i < x.length && i < y.length; i++) {
    final c = x[i].compareTo(y[i]);
    if (c != 0) return c;
  }
  return x.length.compareTo(y.length);
}

/// The items stage copies: a `remove` item has no source (the swap moves its
/// target aside and nothing is staged).
List<Map<String, Object?>> stageItems(Map<String, Object?> group) => [
  for (final it in (group['items'] as List).cast<Map<String, Object?>>())
    if (it['type'] != 'remove') it,
];

/// The manifest a staged copy is verified against: `{group, path, sha256}`
/// for each file of each staged item, from the download's bytes (an agent
/// file with the installed `model:` line carried).
List<Map<String, Object?>> expectedManifest(
  List<Map<String, Object?>> groups,
) {
  final out = <Map<String, Object?>>[];
  for (final g in groups) {
    for (final it in stageItems(g)) {
      final data = it['data'];
      if (data != null) {
        out.add({
          'group': g['id'],
          'path': it['name'],
          'sha256': sha256Hex(data as List<int>),
        });
        continue;
      }
      final src = '${it['src']}';
      if (it['type'] == 'dir') {
        for (final rel in filesUnder(src)) {
          out.add({
            'group': g['id'],
            'path': '${it['name']}/$rel',
            'sha256': sha256Hex(File('$src/$rel').readAsBytesSync()),
          });
        }
      } else {
        List<int> bytes = File(src).readAsBytesSync();
        if (g['kind'] == 'agents') {
          bytes = carryModel(bytes, '${g['dir']}/${it['name']}');
        }
        out.add({
          'group': g['id'],
          'path': it['name'],
          'sha256': sha256Hex(bytes),
        });
      }
    }
  }
  return out;
}

/// `cmd_verify`: the staged copy against the manifest. Null when every file
/// of every group's `new/` is as listed and nothing else is there, else the
/// mismatches `{group, path, file, problem}` with problem `missing`,
/// `changed` or `unexpected`.
List<Map<String, Object?>>? verifyStaged(Journal j) {
  final manifest = j.manifest;
  final want = {for (final m in manifest) '${m['group']}\x00${m['path']}'};
  final mismatches = <Map<String, Object?>>[];
  for (final g in j.groups) {
    final newDir = '${g['staging']}/new';
    for (final m in manifest.where((m) => m['group'] == g['id'])) {
      final file = '$newDir/${m['path']}';
      if (!FileSystemEntity.isFileSync(file)) {
        mismatches.add({
          'group': g['id'],
          'path': m['path'],
          'file': file,
          'problem': 'missing',
        });
      } else if (sha256Hex(File(file).readAsBytesSync()) != m['sha256']) {
        mismatches.add({
          'group': g['id'],
          'path': m['path'],
          'file': file,
          'problem': 'changed',
        });
      }
    }
    for (final rel in filesUnder(newDir)) {
      if (!want.contains('${g['id']}\x00$rel')) {
        mismatches.add({
          'group': g['id'],
          'path': rel,
          'file': '$newDir/$rel',
          'problem': 'unexpected',
        });
      }
    }
  }
  return mismatches.isEmpty ? null : mismatches;
}

/// The verification stop: names up to five mismatches.
UpdateDie verificationFailed(List<Map<String, Object?>> mismatches) {
  final shown = [
    for (final m in mismatches.take(5)) '${m['path']} (${m['problem']})',
  ].join(', ');
  final more = mismatches.length > 5 ? ' and ${mismatches.length - 5} more' : '';
  return UpdateDie(
    'verification_failed',
    'the staged copy differs from the download: $shown$more',
    extra: {'mismatches': mismatches},
  );
}

/// `cmd_verify_swap`: the paths that are not as the manifest lists them,
/// wherever the swap left them (in `new/` or already swapped in); empty when
/// every staged file matches.
List<String> verifySwapped(Journal j) {
  final groups = {for (final g in j.groups) g['id']: g};
  final manifest = j.manifest;
  final want = {for (final m in manifest) '${m['group']}\x00${m['path']}'};
  final bad = <String>[];
  for (final m in manifest) {
    final g = groups[m['group']]!;
    final path = '${m['path']}';
    final top = path.split('/').first;
    var file = '${g['staging']}/new/$path';
    if (!exists('${g['staging']}/new/$top')) file = '${g['dir']}/$path';
    if (!FileSystemEntity.isFileSync(file) ||
        sha256Hex(File(file).readAsBytesSync()) != m['sha256']) {
      bad.add(path);
    }
  }
  for (final g in j.groups) {
    final newDir = '${g['staging']}/new';
    for (final rel in filesUnder(newDir)) {
      if (!want.contains('${g['id']}\x00$rel')) bad.add(rel);
    }
  }
  // a swapped-in entry may hold files the download does not
  final seen = <String>{};
  for (final m in manifest) {
    final g = groups[m['group']]!;
    final top = '${m['path']}'.split('/').first;
    if (seen.add('${g['id']}\x00$top') &&
        !exists('${g['staging']}/new/$top')) {
      final d = '${g['dir']}/$top';
      for (final rel in filesUnder(d)) {
        if (!want.contains('${g['id']}\x00$top/$rel')) bad.add('$top/$rel');
      }
    }
  }
  return bad;
}

/// `sw update stage`: the document and its exit status.
Future<(Map<String, Object?>, int)> stageUpdate(UpdateRun r) async {
  final o = r.options;
  final plan = await makePlan(
    o,
    check: true,
    repo: r.repo,
    ops: r.ops,
    run: r.openspec,
    environment: r.environment,
  );
  final planDoc = plan.doc;
  // a refusal is the answer: nothing is written, not even the lock
  if (planDoc['ok'] != true) return (planDoc, 1);
  final groups = plan.groups;
  r.acquireLock();
  try {
    final pending = r.readJournal();
    if (pending != null) {
      throw UpdateDie(
        'journal_pending',
        'an unfinished update to ${pending.str('to')} is recorded in '
            '${r.journalPath}; run recover first',
      );
    }
    if (exists(r.journalTempPath)) r.ops.remove(r.journalTempPath);
    final scratch = '${r.download}/$scratchName';
    if (exists(scratch)) r.ops.remove(scratch);
    removeStaging(r, [for (final g in groups) '${g['staging']}']);
    final journal = await _newJournal(r, planDoc, groups);
    r.flush(journal);
    for (final g in groups) {
      final staged = '${g['staging']}/new';
      r.ops.mkdir(staged);
      for (final it in stageItems(g)) {
        final data = it['data'];
        if (data != null) {
          // the record has no source to copy: it is written straight into
          // staging
          File('$staged/${it['name']}').writeAsBytesSync(data as List<int>);
        } else {
          r.ops.copy('${it['src']}', staged);
        }
      }
    }
    // the installed `model:` line of each agent file goes into the staged copy
    final byId = {for (final g in journal.groups) g['id']: g};
    for (final t in journal.targets) {
      if (byId[t.gid]?['kind'] != 'agents') continue;
      final staged = File(t.newPath);
      if (staged.existsSync()) {
        final data = staged.readAsBytesSync();
        final out = carryModel(data, t.targetPath);
        if (!_sameBytes(out, data)) staged.writeAsBytesSync(out);
      }
    }
    final mismatches = verifyStaged(journal);
    if (mismatches != null) {
      // the journal still says "staging": installed files were never touched
      removeStaging(r, stagingOf(journal));
      r.ops.remove(r.journalPath);
      throw verificationFailed(mismatches);
    }
    journal.moveTargetStates('pending', 'staged');
    r.flush(journal);
    journal.set('phase', 'staged');
    r.flush(journal);
    return (await reportDocument(r, 'stage', journal, r.lockExtra), 0);
  } finally {
    r.releaseLock();
  }
}

bool _sameBytes(List<int> a, List<int> b) {
  if (a.length != b.length) return false;
  for (var i = 0; i < a.length; i++) {
    if (a[i] != b[i]) return false;
  }
  return true;
}

/// `journal-new`: the journal of this plan, in phase `staging`.
Future<Journal> _newJournal(
  UpdateRun r,
  Map<String, Object?> plan,
  List<Map<String, Object?>> groups,
) async {
  final role = plan['role'];
  final storeful = role == 'owner' || role == 'claim';
  final store = plan['store'] as Map<String, Object?>? ?? const {};
  final warnings = [
    for (final w in (plan['warnings'] as List).cast<Map<String, Object?>>())
      if (w['code'] == 'in_flight_elsewhere') w,
  ];
  final schema = groups.where((g) => g['kind'] == 'schema').firstOrNull;
  return Journal({
    'format': 2,
    'from': plan['from'],
    'to': plan['to'],
    'ref': r.options.ref,
    'kind': plan['kind'],
    'role': role,
    'code': r.options.code,
    'root': r.options.root,
    'inflight': {
      'checked': plan['inflight_checked'] ?? false,
      'changes': plan['inflight'] ?? <Object?>[],
      'warnings': warnings,
    },
    'owner_id': store['id'],
    'store_owner': store['owner'],
    'store_version': store['version'],
    'store_record': storeful ? storeRecordPath(r.options.root) : null,
    'store_lock': storeful ? await gateLockPath(r.repo) : null,
    'store_staging': storeful && schema != null ? schema['staging'] : null,
    'store_state': storeful ? 'pending' : 'none',
    'token': null,
    'prev_config': null,
    'prev_store': null,
    'config_sha': null,
    'prev_packs': plan['packs_previous'],
    'phase': 'staging',
    'groups': [
      for (final g in groups)
        {
          for (final e in g.entries)
            if (e.key != 'items') e.key: e.value,
        },
    ],
    'targets': [
      for (final g in groups)
        for (final it in (g['items'] as List).cast<Map<String, Object?>>())
          {
            'gid': g['id'],
            'name': it['name'],
            'type': it['type'],
            'dir': g['dir'],
            'staging': g['staging'],
            'installed': it['installed'],
            'state': 'pending',
          },
    ],
    'manifest': expectedManifest(groups),
  });
}
