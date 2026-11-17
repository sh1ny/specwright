import 'dart:io';

import 'file_ops.dart';
import 'journal.dart';
import 'lock.dart';
import 'openspec.dart';
import 'options.dart';
import 'plan.dart';
import 'repo.dart';
import 'settings.dart';
import 'stop.dart';
import 'text.dart';

// What the lifecycle subcommands share (stage, swap, note-config, finish,
// recover): the run's context, the journal's accessors and the reports, ported
// from `scripts/update.sh` (design D1, D2, D9 of native-cli-update).

/// One run of a lifecycle subcommand: the options, the one counting wrapper
/// every file operation goes through (C1), the `openspec` runner and the
/// repository questions (settings are read when first asked).
class UpdateRun {
  UpdateRun(
    this.options, {
    Map<String, String>? environment,
    UpdateFileOps? ops,
    OpenspecRunner? openspec,
    this._repo,
  }) : environment = environment ?? Platform.environment,
       ops = ops ?? UpdateFileOps(environment: environment),
       openspec =
           openspec ??
           ((args, cwd, {timeout}) => runOpenspec(
             args,
             cwd,
             timeout: timeout,
             environment: environment,
           ));

  final UpdateOptions options;
  final Map<String, String> environment;
  final UpdateFileOps ops;
  final OpenspecRunner openspec;
  UpdateRepo? _repo;

  /// Where the checkout stands in git; reading the settings is deferred to
  /// the first question, so a run that never asks never reads them.
  UpdateRepo get repo =>
      _repo ??= UpdateRepo.of(options, loadUpdateSettings(options.code));

  String get state => stateDirOf(options);
  String get download => options.download ?? options.code;
  String get journalPath => '$state/update.json';
  String get journalTempPath => '$state/update.json.tmp';
  String get versionPath => '$state/VERSION';

  late final JournalFile journalFile = JournalFile(state, ops);
  late final UpdateLock lock = UpdateLock(state, ops);

  /// Takes the update lock, or stops `locked`.
  void acquireLock() {
    try {
      lock.acquire();
    } on UpdateLocked catch (e) {
      throw UpdateDie(e.code, e.message);
    }
  }

  void releaseLock() => lock.release();

  /// `{lock_replaced: ...}` when this run took over a stale lock, else empty.
  Map<String, Object?> get lockExtra {
    final replaced = lock.replaced;
    return replaced == null ? const {} : {'lock_replaced': replaced};
  }

  /// The journal, or null when there is no file. A journal that cannot be
  /// read stops the run as `journal_unreadable`, with nothing touched.
  Journal? readJournal() {
    try {
      return journalFile.read();
    } on JournalUnreadable catch (e) {
      throw UpdateDie(e.code, e.message, plain: true);
    }
  }

  /// The members every report starts with.
  Map<String, Object?> baseDoc(bool ok) => {
    'ok': ok,
    'interface': updateInterface,
    'installed': readVersion(versionPath).$1,
    'unchanged': installedUnchanged(options, ops),
  };

  /// The first line of the VERSION stamp as `read -r` takes it ('' when none).
  String stamp() => firstLine(versionPath);

  /// Writes [journal] (to its temporary file, then the counted rename).
  void flush(Journal journal) => journalFile.write(journal);
}

/// The document of a stop (`update.sh`'s `die`).
Map<String, Object?> dieDocument(UpdateRun r, UpdateDie stop) {
  final doc = stop.plain
      ? <String, Object?>{'ok': false, 'interface': updateInterface}
      : r.baseDoc(false);
  doc
    ..['error'] = stop.code
    ..['message'] = stop.message
    ..addAll(stop.extra);
  return doc;
}

/// The first line of [path] with a trailing carriage return and the blanks
/// `read -r` strips removed; '' when there is no file.
String firstLine(String path) {
  final file = File(path);
  if (!file.existsSync()) return '';
  var text = decodeLossy(file.readAsBytesSync());
  final end = text.indexOf('\n');
  if (end >= 0) text = text.substring(0, end);
  text = text.replaceAll('\r', '');
  return text.replaceAll(RegExp(r'^[ \t]+|[ \t]+$'), '');
}

/// `-e path`: it exists, links followed.
bool exists(String path) =>
    FileSystemEntity.typeSync(path) != FileSystemEntityType.notFound;

/// `-e path || -L path`: it exists, or is a link (a dangling one included).
bool existsOrLink(String path) =>
    FileSystemEntity.typeSync(path, followLinks: false) !=
    FileSystemEntityType.notFound;

/// One entry of the journal's `targets`.
class JournalTarget {
  JournalTarget(this.raw)
    : gid = raw['gid'] as String,
      name = raw['name'] as String,
      type = raw['type'] as String,
      dir = raw['dir'] as String,
      staging = raw['staging'] as String,
      installed = raw['installed'] as bool,
      state = raw['state'] as String;

  final Map<String, Object?> raw;
  final String gid;
  final String name;
  final String type;
  final String dir;
  final String staging;
  final bool installed;
  final String state;

  String get newPath => '$staging/new/$name';
  String get oldPath => '$staging/old/$name';
  String get targetPath => '$dir/$name';
}

/// Reads the journal's members as `update.sh`'s `jstr`, `jfield` and
/// `jset_field` did.
extension JournalView on Journal {
  /// A member as text; '' when it is null or missing.
  String str(String key) {
    final v = data[key];
    return v == null ? '' : (v is String ? v : '$v');
  }

  /// Replaces an existing member; stops `journal_unreadable` when the journal
  /// has none.
  void set(String key, Object? value) {
    if (!data.containsKey(key)) {
      throw UpdateDie('journal_unreadable', 'update.json has no $key member');
    }
    data[key] = value;
  }

  List<Map<String, Object?>> list(String key) => [
    for (final e in (data[key] as List?) ?? const <Object?>[])
      (e as Map).cast<String, Object?>(),
  ];

  List<Map<String, Object?>> get groups => list('groups');
  List<Map<String, Object?>> get manifest => list('manifest');

  /// The targets; a line this reader cannot take is `journal_unreadable`.
  List<JournalTarget> get targets {
    try {
      return [for (final t in list('targets')) JournalTarget(t)];
    } on TypeError {
      throw UpdateDie(
        'journal_unreadable',
        'update.json has a target line this script cannot read',
      );
    }
  }

  /// `jwrite_target`: the state of one target, in memory.
  void setTargetState(String gid, String name, String state) {
    for (final t in list('targets')) {
      if (t['gid'] == gid && t['name'] == name) t['state'] = state;
    }
  }

  /// `jwrite_all_targets`: every target in state [from] to state [to].
  void moveTargetStates(String from, String to) {
    for (final t in list('targets')) {
      if (t['state'] == from) t['state'] = to;
    }
  }
}

/// `remove_staging`: removes each staging directory that exists.
void removeStaging(UpdateRun r, Iterable<String> directories) {
  for (final d in directories) {
    if (d.isNotEmpty && exists(d)) r.ops.remove(d);
  }
}

/// The staging directories of a journal.
List<String> stagingOf(Journal j) => [
  for (final g in j.groups) g['staging'] as String,
];

/// `recover_cleanup`: staging first, journal last.
void recoverCleanup(UpdateRun r, Journal j) {
  removeStaging(r, stagingOf(j));
  r.ops.remove(r.journalTempPath);
  r.ops.remove(r.journalPath);
}

/// `rel_to`: [path] relative to the planning repo's [top], or null.
String? relToTop(String top, String path) =>
    relativeTo(top, resolvePosix(path));

/// The success document of stage, swap and finish, from the journal
/// (`cmd_report`).
Future<Map<String, Object?>> reportDocument(
  UpdateRun r,
  String sub,
  Journal j, [
  Map<String, Object?> extra = const {},
]) async {
  final inflight = j.data['inflight'];
  final inflightMap = inflight is Map ? inflight : const <String, Object?>{};
  final doc = r.baseDoc(true);
  final targets = j.list('targets');
  doc.addAll({
    'subcommand': sub,
    'state': j.data['phase'],
    'from': j.data['from'],
    'to': j.data['to'],
    'ref': j.data['ref'],
    'kind': j.data['kind'],
    'role': j.data['role'],
    'files': j.manifest.length,
    'inflight_checked': inflightMap['checked'] ?? false,
    'inflight': inflightMap['changes'] ?? <Object?>[],
    'warnings': inflightMap['warnings'] ?? <Object?>[],
    'groups': [
      for (final g in j.groups)
        {
          'id': g['id'],
          'kind': g['kind'],
          'dir': g['dir'],
          'staging': g['staging'],
          'targets': targets.where((t) => t['gid'] == g['id']).length,
        },
    ],
  });
  if (sub == 'swap') {
    doc['store_written'] = j.data['store_state'] == 'written';
    final store = await storeReport(r, j);
    if (store != null) doc['store'] = store;
    final from = j.data['from'];
    if (from is String && from.isNotEmpty) {
      doc['restart'] =
          'Agent sessions started before this update still run $from; '
          'restart them before they continue a change on ${j.data['to']}.';
    }
  }
  doc.addAll(extra);
  return doc;
}

/// The `store` object of the swap document (`store_report`): what happened to
/// the store, for the prompt's Steps 5 and 7.
Future<Map<String, Object?>?> storeReport(UpdateRun r, Journal j) async {
  final role = j.data['role'];
  if (role == null || role == 'none') return null;
  final state = j.data['store_state'];
  final me = j.data['owner_id'];
  final planning = await r.repo.planningRepo();
  final top = planning?.top;
  final out = <String, Object?>{
    'role': role,
    'id': me,
    'owner': j.data['store_owner'],
    'version': j.data['store_version'],
    'written': state == 'written',
    'claimed': role == 'claim' && state == 'written',
  };
  if (state == 'written') {
    out['owner'] = me;
    out['version'] = j.data['to'];
    final schema = j.groups.where((g) => g['kind'] == 'schema').firstOrNull;
    final record = j.data['store_record'];
    out['uncommitted'] = [
      if (top != null && record is String) ?relToTop(top, record),
      if (top != null && schema != null)
        ?relToTop(top, '${schema['dir']}/specwright'),
    ];
    if (out['claimed'] == true) {
      out['message'] =
          '$me now owns the store\'s schema (version ${j.data['to']}); STORE '
          'and the new schema are left uncommitted in the store, commit them '
          'there';
    } else {
      out['message'] =
          'the store\'s schema and STORE now read ${j.data['to']} (owner $me); '
          'they are left uncommitted in the store';
    }
  } else if (state == 'current') {
    out['message'] = 'store schema already current';
  } else if (role == 'other') {
    out['message'] = 'store config managed by owner ${j.data['store_owner']}';
  } else {
    out['message'] = 'the store schema has not been swapped';
  }
  return out;
}
