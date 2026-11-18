import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart' show sha256;

import '../settings/values.dart' show pyRepr;
import 'file_ops.dart';
import 'inflight.dart';
import 'journal.dart';
import 'openspec.dart';
import 'options.dart';
import 'packs.dart';
import 'repo.dart';
import 'settings.dart';
import 'store.dart';
import 'sw_install.dart';
import 'text.dart';

// `sw update plan`: what the update would do, read only (design D1, D4, D5, D9
// of native-cli-update), ported from `make_plan` of `scripts/update.sh`. Every
// refusal message is the shell's, word for word.

/// The name of the pack record file.
const String recordName = 'packs.json';

/// The state directory of a checkout, `<code>/openspec/.specwright`.
String stateDirOf(UpdateOptions o) => '${o.code}/openspec/.specwright';

/// The text of a version file, stripped, and whether the file exists.
(String?, bool) readVersion(String path) {
  final file = File(path);
  try {
    return (pyStrip(utf8.decode(file.readAsBytesSync())), true);
  } on FileSystemException {
    return (null, false);
  } on FormatException {
    // a file that is not UTF-8 is not a version, but it exists
    return (null, true);
  }
}

/// `workflow`, `patch`, `reinstall`, `downgrade` or `fresh`.
String kindOf(String? from, String to) {
  if (from == null) return 'fresh';
  final a = versionTuple(from);
  final b = versionTuple(to);
  final c = compareVersions(a, b);
  if (c == 0) return 'reinstall';
  if (c > 0) return 'downgrade';
  return a.$1 != b.$1 || a.$2 != b.$2 ? 'workflow' : 'patch';
}

/// A workflow update: no installed VERSION, or a different major or minor.
bool workflowUpdate(String? from, String to) {
  if (from == null) return true;
  final a = versionTuple(from);
  final b = versionTuple(to);
  return a.$1 != b.$1 || a.$2 != b.$2;
}

/// First 12 hex digits of SHA-256 over the code path (forward slashes,
/// lower-cased on Windows): keys the store staging directory per checkout.
String checkoutId(String code, {bool? windows}) {
  var c = code.replaceAll(r'\', '/');
  while (c.endsWith('/')) {
    c = c.substring(0, c.length - 1);
  }
  final lower = (windows ?? Platform.isWindows) ? c.toLowerCase() : c;
  return sha256.convert(utf8.encode(lower)).toString().substring(0, 12);
}

/// One group of targets, as `mk_group` makes it: [id], [kind], [dir], its
/// staging directory and its items. An item is `{name, type, src,
/// installed}`, plus `pack` for a pack item and `data` for the record.
Map<String, Object?> makeGroup(
  String id,
  String kind,
  String dir,
  List<(String, String, String?)> items, {
  String suffix = '',
}) {
  var d = dir.replaceAll(r'\', '/');
  while (d.endsWith('/')) {
    d = d.substring(0, d.length - 1);
  }
  final at = d.lastIndexOf('/');
  final parent = at < 0 ? '' : d.substring(0, at);
  final base = at < 0 ? d : d.substring(at + 1);
  return {
    'id': id,
    'kind': kind,
    'dir': d,
    'staging': '$parent/.specwright-update-$base$suffix',
    'items': [
      for (final (name, type, src) in items)
        {
          'name': name,
          'type': type,
          'src': src,
          'installed':
              FileSystemEntity.typeSync('$d/$name') !=
              FileSystemEntityType.notFound,
        },
    ],
  };
}

/// The groups of an update and the orphans (`build_groups`), refusing a
/// download without skills or schema and an update with no target; the pack
/// items follow each skills group.
Future<
  ({List<Map<String, Object?>> groups, List<Map<String, Object?>> orphans})
>
buildGroups(
  UpdateOptions o,
  UpdateRepo repo,
  List<Map<String, Object?>> refusals, {
  bool withSchema = true,
  bool store = false,
  PackPlan? pk,
  List<int>? record,
}) async {
  final dl = o.download ?? o.code;
  final groups = <Map<String, Object?>>[];
  final orphans = <Map<String, Object?>>[];
  final skillsDir = Directory('$dl/skills');
  final names = skillsDir.existsSync()
      ? ([
          for (final e in skillsDir.listSync(followLinks: false))
            if (_base(e.path).startsWith('specwright-') &&
                FileSystemEntity.isDirectorySync(e.path))
              _base(e.path),
        ]..sort())
      : <String>[];
  if (names.isEmpty) {
    refusals.add({
      'code': 'download_incomplete',
      'message': 'the download has no skills/specwright-* directory',
    });
  }
  if (!File('$dl/schemas/specwright/schema.yaml').existsSync()) {
    refusals.add({
      'code': 'download_incomplete',
      'message': 'the download has no schemas/specwright/schema.yaml',
    });
  }
  if (o.skills.isEmpty && o.agents.isEmpty) {
    refusals.add({
      'code': 'no_targets',
      'message': 'no --skills or --agents directory was given',
    });
  }
  for (var i = 0; i < o.skills.length; i++) {
    final g = makeGroup('skills-${i + 1}', 'skills', o.skills[i], [
      for (final n in names) (n, 'dir', '$dl/skills/$n'),
    ]);
    groups.add(g);
    final dir = Directory('${g['dir']}');
    if (dir.existsSync()) {
      final found = [
        for (final e in dir.listSync(followLinks: false))
          if (_base(e.path).startsWith('specwright-') &&
              FileSystemEntity.isDirectorySync(e.path) &&
              !names.contains(_base(e.path)))
            _base(e.path),
      ]..sort();
      for (final n in found) {
        orphans.add({'group': g['id'], 'dir': g['dir'], 'name': n});
      }
    }
    if (pk != null) {
      await addPackSkillItems(o, repo, g, pk, refusals, orphans);
    }
  }
  for (var i = 0; i < o.agents.length; i++) {
    final spec = o.agents[i];
    final eq = spec.indexOf('=');
    final kind = eq < 0 ? spec : spec.substring(0, eq);
    final d = eq < 0 ? '' : spec.substring(eq + 1);
    final adir = '$dl/agents/$kind';
    if (d.isEmpty || !Directory(adir).existsSync()) {
      refusals.add({
        'code': 'agent_kind',
        'message': '--agents $spec: the download has no agents/$kind',
      });
      continue;
    }
    final files = [
      for (final e in Directory(adir).listSync(followLinks: false))
        if (_base(e.path).endsWith('.md')) _base(e.path),
    ]..sort();
    final g = makeGroup('agents-${i + 1}-$kind', 'agents', d, [
      for (final n in files) (n, 'file', '$adir/$n'),
    ]);
    g['agent_kind'] = kind;
    groups.add(g);
    final dir = Directory('${g['dir']}');
    if (dir.existsSync()) {
      final found = [
        for (final e in dir.listSync(followLinks: false))
          if (_base(e.path).startsWith('specwright-') &&
              _base(e.path).endsWith('.md') &&
              FileSystemEntity.isFileSync(e.path) &&
              !files.contains(_base(e.path)))
            _base(e.path),
      ]..sort();
      for (final n in found) {
        orphans.add({'group': g['id'], 'dir': g['dir'], 'name': n});
      }
    }
  }
  if (withSchema) {
    // another project's update leaves the store's schema alone
    groups.add(
      makeGroup('schema', 'schema', '${o.root}/openspec/schemas', [
        ('specwright', 'dir', '$dl/schemas/specwright'),
      ], suffix: store ? '-${checkoutId(o.code)}' : ''),
    );
  }
  if (record != null) {
    // packs.json: the last group, so the swap writes it after every skill
    // rename
    final state = stateDirOf(o);
    final g = makeGroup('record', 'record', state, [
      (recordName, 'file', null),
    ]);
    (g['items'] as List).first['data'] = record;
    final at = state.lastIndexOf('/');
    g['staging'] = '${state.substring(0, at)}/.specwright-update-record';
    groups.add(g);
  }
  return (groups: groups, orphans: orphans);
}

String _base(String path) {
  final at = path.lastIndexOf(RegExp(r'[/\\]'));
  return at < 0 ? path : path.substring(at + 1);
}

/// The plan: the document and the groups.
typedef Plan = ({Map<String, Object?> doc, List<Map<String, Object?>> groups});

/// `installed_unchanged`: true while no installed file has been replaced
/// (no journal, or one that has not started the swap).
bool installedUnchanged(UpdateOptions o, UpdateFileOps ops) {
  try {
    final j = JournalFile(stateDirOf(o), ops).read();
    return j == null || const ['staging', 'staged'].contains(j.data['phase']);
  } on JournalUnreadable {
    return false;
  }
}

final RegExp _swTag = RegExp(r'^v\d+\.\d+\.\d+$');

/// `make_plan`. [check] (the `plan` subcommand) also collects and validates
/// the changes in flight of a workflow update against the download's schema;
/// every other caller reuses the verdict. [run] replaces the `openspec`
/// runner (tests).
Future<Plan> makePlan(
  UpdateOptions o, {
  bool check = false,
  UpdateRepo? repo,
  UpdateFileOps? ops,
  OpenspecRunner? run,
  Map<String, String>? environment,
  List<String>? helperCommand,
}) async {
  final settings = repo?.settings ?? loadUpdateSettings(o.code);
  final r = repo ?? UpdateRepo.of(o, settings);
  final files = ops ?? UpdateFileOps(environment: environment);
  final env = environment ?? Platform.environment;
  final download = o.download ?? o.code;
  final state = stateDirOf(o);
  final refusals = <Map<String, Object?>>[];
  final warnings = <Map<String, Object?>>[];
  var (inst, exists) = readVersion('$state/VERSION');
  if (exists && !(inst != null && semver.hasMatch(inst))) {
    refusals.add({
      'code': 'installed_version_invalid',
      'message':
          'openspec/.specwright/VERSION holds ${pyRepr(inst)}, not '
          'MAJOR.MINOR.PATCH',
    });
    inst = null;
  }
  var (to, _) = readVersion('$download/VERSION');
  if (!(to != null && semver.hasMatch(to))) {
    refusals.add({
      'code': 'download_version_invalid',
      'message':
          "the download's VERSION holds ${pyRepr(to)}, not MAJOR.MINOR.PATCH",
    });
    to = null;
  }
  Map<String, Object?>? journal;
  try {
    final j = JournalFile(state, files).read();
    if (j != null) {
      journal = {
        'from': j.data['from'],
        'to': j.data['to'],
        'phase': j.data['phase'],
        'format': j.data['format'],
      };
    }
  } on JournalUnreadable catch (e) {
    refusals.add({'code': 'journal_unreadable', 'message': e.message});
  }
  final info = await storeInfo(r);
  final role = info.role;
  final rec = info.record;
  if (info.problem != null) {
    refusals.add({
      'code': 'store_record_unreadable',
      'message':
          "the store's record is unreadable: ${info.problem}. Fix or remove "
          'it, then rerun the update; nothing was written',
    });
  }
  if (role == 'other' && to != null) {
    final sv = versionTuple(rec!.version);
    final tv = versionTuple(to);
    if (tv.$1 != sv.$1 || tv.$2 != sv.$2) {
      final found = await highestTag(
        o,
        sv.$1,
        sv.$2,
        environment: environment,
        helperCommand: helperCommand,
        git: r.git,
      );
      final tag = found.tag;
      final named = tag != null
          ? 'the highest ${sv.$1}.${sv.$2} release is $tag'
          : 'the highest ${sv.$1}.${sv.$2} release could not be named '
                '(${found.problem})';
      refusals.add({
        'code': 'store_version',
        'message':
            'the store records version ${rec.version} and its schema is owned '
            'by ${rec.owner}, so this project\'s update to $to would leave '
            "that version, and only the owner replaces the store's schema. "
            'Nothing was written. ${named[0].toUpperCase()}${named.substring(1)}: '
            'update this project to ${tag ?? 'it'} instead, or have '
            '${rec.owner} update the store first',
      });
    }
  }
  final wt = await r.otherWorktree();
  if (wt != null) {
    refusals.add({
      'code': 'root_other_worktree',
      'message':
          '--root is in the worktree ${wt.$1}, another worktree of the code '
          "repo's worktree ${wt.$2}; commits there would land on that "
          "worktree's branch. Nothing was written. Run the update from the "
          'worktree that holds --root, or give a --root in this worktree or '
          'in a separate planning repo',
    });
  }
  final pk = await planPacks(o, r, state, role, refusals);
  final groupsFound = await buildGroups(
    o,
    r,
    refusals,
    withSchema: role != 'other',
    store: role == 'claim' || role == 'owner',
    pk: pk,
    record: to != null ? await packRecordBytes(o, r, to, pk) : null,
  );
  final groups = groupsFound.groups;
  final inflight = <Map<String, Object?>>[];
  var checked = false;
  if (check &&
      to != null &&
      refusals.isEmpty &&
      workflowUpdate(inst, to) &&
      role != 'other') {
    checked = true;
    final found = await inflightEntries(
      repo: r,
      ops: files,
      run: run ?? runOpenspec,
      download: download,
      stateDir: state,
      to: to,
      schemaDir: '$download/schemas/specwright',
      role: role ?? 'none',
    );
    warnings.addAll(found.warnings);
    for (final e in found.entries) {
      final status = e['status'];
      if (status == 'other project') {
        refusals.add({
          'code': 'other_project_change',
          'change': e['name'],
          'ref': e['source'],
          'message':
              'change ${e['name']} (${e['source']}) in flight in the store '
              'belongs to another project (this project has no local branch '
              '<prefix>/${e['name']}), so the store\'s schema is not '
              'replaced until it is archived',
        });
      } else if (status == 'invalid') {
        final where = e['source'] == 'working tree' ? '' : ' on ${e['source']}';
        refusals.add({
          'code': 'change_invalid',
          'change': e['name'],
          'ref': where.isEmpty ? null : e['source'],
          'message':
              'change ${e['name']}${where.isEmpty ? ' (working tree)' : where} '
              'fails validation against $to: ${e['error']}${e['note'] ?? ''}',
        });
      } else {
        inflight.add(e);
      }
    }
  }
  final doc = <String, Object?>{
    'ok': refusals.isEmpty,
    'interface': updateInterface,
    'installed': inst,
    'unchanged': installedUnchanged(o, files),
    'from': inst,
    'to': to,
    'ref': o.ref,
    'kind': to != null ? kindOf(inst, to) : null,
    'role': role,
    'targets': [
      for (final g in groups)
        for (final it
            in (g['items'] as List<Object?>).cast<Map<String, Object?>>())
          {
            'group': g['id'],
            'kind': g['kind'],
            'dir': g['dir'],
            'name': it['name'],
            'installed': it['installed'],
            if (it['pack'] != null) 'pack': it['pack'],
            if (it['type'] == 'remove') 'type': 'remove',
          },
    ],
    'packs': [
      for (final pn in pk.order)
        {
          'name': pn,
          'version': to,
          'requires': pk.manifests[pn]!['requires'] ?? <Object?>[],
          'skills': pk.manifests[pn]!['skills'] ?? <Object?>[],
          'adopted': pk.adopted[pn] ?? <Object?>[],
          'documents': pk.documents[pn] ?? <Object?>[],
        },
    ],
    'packs_previous': pk.previous,
    'orphans': groupsFound.orphans,
    'journal': journal,
    'inflight_checked': checked,
    'inflight': inflight,
    'refusals': refusals,
    'warnings': warnings,
  };
  if (role == 'claim' || role == 'owner' || role == 'other') {
    doc['store'] = {
      'root': o.root,
      'version': rec?.version,
      'owner': rec?.owner,
      'id': info.id,
    };
  }
  final ref = o.ref;
  if (ref != null && _swTag.hasMatch(ref)) {
    // a tag ref only: main and a download without this field ship no sw (C12)
    final target = swHostTarget(env);
    doc['sw'] = target != null
        ? {'asset': swAssetName(target), 'target': target}
        : {'asset': null, 'reason': 'unsupported_platform'};
  }
  if (refusals.isNotEmpty) {
    // unchanged: false only while a readable journal shows a started swap
    // (phase swapping or swapped); an unreadable journal is not proof of one
    final pending =
        journal != null &&
        const ['swapping', 'swapped'].contains(journal['phase']);
    doc
      ..['error'] = 'refused'
      ..['message'] = refusals.first['message']
      ..['unchanged'] = !pending;
  }
  return (doc: doc, groups: groups);
}

/// A recovery of an interrupted update that `plan` runs first (design D4): it
/// returns the members to add to the plan document (`recovered`, a lock
/// member, `packs_previous`). The recovery itself belongs to the recover
/// task; until it is wired [planDocument] runs none.
typedef PlanRecovery = Future<Map<String, Object?>?> Function(
  UpdateOptions options,
);

/// `sw update plan`: the document and its exit status (0 when ok, else 1).
Future<(Map<String, Object?>, int)> planDocument(
  UpdateOptions o, {
  Map<String, String>? environment,
  UpdateRepo? repo,
  OpenspecRunner? run,
  UpdateFileOps? ops,
  PlanRecovery? recover,
  List<String>? helperCommand,
}) async {
  final extra = recover == null ? null : await recover(o);
  final plan = await makePlan(
    o,
    check: true,
    repo: repo,
    run: run,
    ops: ops,
    environment: environment,
    helperCommand: helperCommand,
  );
  final doc = plan.doc;
  if (extra != null) doc.addAll(extra);
  return (doc, doc['ok'] == true ? 0 : 1);
}
