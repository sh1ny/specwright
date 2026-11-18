import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import '../settings/values.dart' show pyStr, pyTruthy;
import 'file_ops.dart';
import 'openspec.dart';
import 'repo.dart';
import 'store.dart';
import 'text.dart';

/// The directory under the download that holds the scratch roots of the
/// changes in flight; removed before `plan` returns.
const String scratchName = '.update-scratch';

/// One change in flight: its [name], where it was found ([source] is
/// `working tree` or the local branch) and the git [ref] to read it from
/// (null for the working tree).
class InflightItem {
  const InflightItem(this.name, this.source, this.ref);

  final String name;
  final String source;
  final String? ref;
}

/// The changes in flight and the warnings about those found only on a remote.
typedef Collected = ({
  List<InflightItem> items,
  List<Map<String, Object?>> warnings,
});

/// Every change in flight (`collect`): each change directory of
/// `<root>/openspec/changes/` other than `archive`, then every local branch
/// `<prefix>/<name>` of the planning repo whose tree holds the change while
/// the planning main has no archive of that name. The working tree wins over
/// a branch. A remote-tracking `origin/<prefix>/<name>` with no local branch
/// is a warning `in_flight_elsewhere`: never validated, never a refusal, no
/// fetch.
Future<Collected> collectInflight(UpdateRepo repo) async {
  final items = <InflightItem>[];
  final warnings = <Map<String, Object?>>[];
  final seen = <String>{};
  final changes = Directory('${repo.root}/openspec/changes');
  if (changes.existsSync()) {
    final names = <String>[
      for (final entry in changes.listSync(followLinks: false))
        if (FileSystemEntity.isDirectorySync(entry.path))
          entry.uri.pathSegments.where((s) => s.isNotEmpty).last,
    ]..sort();
    for (final name in names) {
      if (name == 'archive') continue;
      items.add(InflightItem(name, 'working tree', null));
      seen.add(name);
    }
  }
  final planning = await repo.planningRepo();
  if (planning == null) return (items: items, warnings: warnings);
  final top = planning.top;
  final base = planning.planning;
  final main = await repo.planningMain(top);
  final archived = main == null
      ? const <String>[]
      : await repo.gitLines(top, [
          'ls-tree',
          '--name-only',
          '$main:$base/changes/archive',
        ]);
  bool isArchived(String name) => archived.any(
    (a) =>
        a == name ||
        RegExp('^\\d{4}-\\d{2}-\\d{2}-${RegExp.escape(name)}\$').hasMatch(a),
  );
  Future<bool> holds(String ref, String name) async {
    final r = await repo.git(top, [
      'cat-file',
      '-t',
      '$ref:$base/changes/$name',
    ]);
    return r.ok && pyStrip(r.text) == 'tree';
  }

  final local = <String>{};
  final branches =
      await repo.gitLines(top, [
          'for-each-ref',
          '--format=%(refname:short)',
          'refs/heads/',
        ])
        ..sort();
  for (final short in branches) {
    local.add(short);
    final parts = UpdateRepo.branchParts(short);
    if (parts != null &&
        !seen.contains(parts.$2) &&
        await holds('refs/heads/$short', parts.$2) &&
        !isArchived(parts.$2)) {
      items.add(InflightItem(parts.$2, short, 'refs/heads/$short'));
      seen.add(parts.$2);
    }
  }
  const remotePrefix = 'refs/remotes/origin/';
  final remotes =
      await repo.gitLines(top, [
          'for-each-ref',
          '--format=%(refname)',
          remotePrefix,
        ])
        ..sort();
  for (final full in remotes) {
    final short = full.substring(remotePrefix.length);
    final parts = UpdateRepo.branchParts(short);
    if (parts != null &&
        !local.contains(short) &&
        !seen.contains(parts.$2) &&
        await holds(full, parts.$2) &&
        !isArchived(parts.$2)) {
      warnings.add({
        'code': 'in_flight_elsewhere',
        'name': parts.$2,
        'ref': 'origin/$short',
        'message':
            '${parts.$2} on origin/$short: in flight elsewhere, not validated',
      });
    }
  }
  return (items: items, warnings: warnings);
}

/// A change that cannot be read from its branch.
class _CannotRead implements Exception {
  _CannotRead(this.message);

  final String message;

  @override
  String toString() => message;
}

/// Puts the change of branch [item] and the branch's `specs` into
/// `<scratch>/openspec/`: the branch's own specs, as validated. The files are
/// read from git object by object (`ls-tree`, then one `cat-file --batch`),
/// so no archive format is needed; a symlink or a submodule is left out, as
/// the archive reader left out everything that is not a file or a directory.
Future<void> extractBranch(
  UpdateRepo repo,
  UpdateFileOps ops,
  InflightItem item,
  String scratch,
) async {
  final planning = (await repo.planningRepo())!;
  final base = planning.planning;
  final tree = await repo.git(planning.top, [
    'ls-tree',
    '-r',
    '-z',
    item.ref!,
    '--',
    '$base/changes/${item.name}',
    '$base/specs',
  ]);
  if (!tree.ok) throw _CannotRead('git archive ${item.ref} failed');
  final files = <(String sha, String path)>[];
  for (final entry in decodeLossy(tree.stdout).split('\x00')) {
    final tab = entry.indexOf('\t');
    if (tab < 0) continue;
    final fields = entry.substring(0, tab).split(' ');
    final path = entry.substring(tab + 1);
    // 100644 and 100755 are files; 120000 is a link and 160000 a submodule
    if (fields.length != 3 || fields[1] != 'blob' || fields[0] == '120000') {
      continue;
    }
    if (!path.startsWith('$base/') || path.split('/').contains('..')) continue;
    files.add((fields[2], path));
  }
  if (files.isEmpty) return;
  final batch = await repo.git(planning.top, [
    'cat-file',
    '--batch',
  ], input: utf8.encode('${files.map((f) => f.$1).join('\n')}\n'));
  if (!batch.ok) throw _CannotRead('git archive ${item.ref} failed');
  final out = batch.stdout;
  var at = 0;
  for (final (_, path) in files) {
    final newline = out.indexOf(10, at);
    if (newline < 0) throw _CannotRead('git archive ${item.ref} failed');
    final header = ascii
        .decode(out.sublist(at, newline), allowInvalid: true)
        .split(' ');
    final size = header.length == 3 ? int.tryParse(header[2]) : null;
    if (size == null || newline + 1 + size > out.length) {
      throw _CannotRead('git archive ${item.ref} failed');
    }
    final dest = '$scratch/openspec/${path.substring(base.length + 1)}';
    final parent = dest.substring(0, dest.lastIndexOf('/'));
    if (!Directory(parent).existsSync()) ops.mkdir(parent);
    File(dest).writeAsBytesSync(
      Uint8List.sublistView(out, newline + 1, newline + 1 + size),
    );
    at = newline + 1 + size + 1;
  }
}

final RegExp _lineBreak = RegExp('\r\n|[\n\r\v\f\x1c\x1d\x1e\x85  ]');

/// `first_error`: the first line of [text] that starts with `error`, else
/// the first line (a `Note:` line and blank lines are skipped), else
/// `no output`.
String firstError(String text) {
  final lines = [
    for (final line in text.split(_lineBreak))
      if (pyStrip(line).isNotEmpty && !pyStrip(line).startsWith('Note:'))
        pyStrip(line),
  ];
  for (final line in lines) {
    if (line.toLowerCase().startsWith('error')) return line;
  }
  return lines.isEmpty ? 'no output' : lines.first;
}

/// The failure of one change: the [step] that found it (`schema`, `validate`
/// or `status`, or `error` when an `openspec` run failed without a result
/// that says the change fails) and the first [error] as text.
typedef ChangeFailure = ({String step, String error});

Map<String, Object?>? _object(Object? value) =>
    value is Map ? Map<String, Object?>.from(value) : null;

Object? _decode(String text) {
  try {
    return jsonDecode(text);
  } on FormatException {
    return _notJson;
  }
}

const Object _notJson = Object();

/// The three checks of design D4 for [name] in the scratch root [scratch],
/// run with `cwd` the scratch root: `openspec schema validate specwright`,
/// `openspec validate NAME --json` and `openspec status --change NAME
/// --json`. Null when the change passes.
Future<ChangeFailure?> checkChange(
  OpenspecRunner run,
  String scratch,
  String name,
) async {
  var r = await run(['schema', 'validate', 'specwright'], scratch);
  if (r.code != 0) {
    return (
      step: 'schema',
      error:
          'openspec schema validate specwright: '
          '${firstError('${r.stdout}\n${r.stderr}')}',
    );
  }
  r = await run(['validate', name, '--json'], scratch);
  final validated = _decode(r.stdout);
  Map<String, Object?>? item;
  if (validated is Map && validated['items'] is List) {
    final items = validated['items'] as List;
    if (items.isNotEmpty) item = _object(items.first);
  }
  if (item != null) {
    // a failed run fails whatever its item says
    if (r.code != 0 && item['valid'] == true) {
      return (
        step: 'error',
        error:
            'openspec validate $name: ${firstError('${r.stderr}\n${r.stdout}')}',
      );
    }
    final valid = item.containsKey('valid') ? item['valid'] : r.code == 0;
    if (!pyTruthy(valid)) {
      final issues = item['issues'];
      final first = issues is List && issues.isNotEmpty
          ? (_object(issues.first) ?? <String, Object?>{})
          : <String, Object?>{};
      final path = first['path'];
      return (
        step: 'validate',
        error:
            'openspec validate $name: '
            '${pyTruthy(path) ? '${pyStr(path)}: ' : ''}'
            '${first.containsKey('message') ? pyStr(first['message']) : 'invalid'}',
      );
    }
  } else if (r.code != 0) {
    return (
      step: 'error',
      error:
          'openspec validate $name: ${firstError('${r.stdout}\n${r.stderr}')}',
    );
  }
  r = await run(['status', '--change', name, '--json'], scratch);
  if (r.code != 0) {
    // a failed run fails the check even when its output parses as JSON
    return (
      step: 'error',
      error: 'openspec status $name: ${firstError('${r.stderr}\n${r.stdout}')}',
    );
  }
  final decoded = _decode(r.stdout);
  final status = decoded is Map ? Map<String, Object?>.from(decoded) : null;
  if (status == null) {
    return (
      step: 'error',
      error: 'openspec status $name: ${firstError('${r.stderr}\n${r.stdout}')}',
    );
  }
  final listed = status['status'];
  final bad = listed is List
      ? [
          for (final x in listed)
            if (_object(x)?['severity'] == 'error') _object(x)!,
        ]
      : const <Map<String, Object?>>[];
  if (bad.isNotEmpty) {
    final first = bad.first;
    return (
      step: 'status',
      error:
          'openspec status $name: '
          '${pyStr(first.containsKey('message') ? first['message'] : (first.containsKey('code') ? first['code'] : 'error'))}',
    );
  }
  final artifacts = <String, Map<String, Object?>>{};
  final given = status['artifacts'];
  if (given is List) {
    for (final a in given) {
      final map = _object(a);
      if (map != null && map['id'] is String) {
        artifacts[map['id'] as String] = map;
      }
    }
  }
  final paths = _object(status['artifactPaths']) ?? const <String, Object?>{};
  for (final a in artifacts.values) {
    final existing = _object(paths[a['id']])?['existingOutputPaths'];
    if (a['status'] == 'done' || pyTruthy(existing)) {
      final requires = a['requires'];
      for (final required in requires is List ? requires : const []) {
        final other = artifacts[required];
        final state = other?['status'];
        if (state != 'done' && state != 'skipped') {
          return (
            step: 'status',
            error:
                'openspec status $name: artifact ${a['id']} exists but its '
                'dependency $required is ${state == null ? 'missing' : pyStr(state)}',
          );
        }
      }
    }
  }
  return null;
}

/// Design D8: after a change failed against the target, check it again
/// against the installed schema, in its own scratch root. The note `; it
/// already fails on `<installed>` (`<error>`), so the update to `<to>` did not
/// cause it` is given only when the installed schema passes `openspec schema
/// validate` and the change then fails validate or status; otherwise the
/// note is empty (no installed VERSION, no schema directory, an invalid
/// installed schema, a failed run, or a pass).
Future<String> installedNote({
  required UpdateRepo repo,
  required UpdateFileOps ops,
  required OpenspecRunner run,
  required String scratch,
  required String stateDir,
  required String name,
  required String to,
  required String role,
}) async {
  final source = '${repo.root}/openspec/schemas/specwright';
  String? label = _readVersion('$stateDir/VERSION');
  if (role == 'owner' || role == 'claim') {
    // the schema on disk is the owner's: the store's recorded version names it
    final record = readStoreRecord(storeRecordPath(repo.root)).record;
    label = record?.version ?? label;
  }
  if (label == null ||
      !semver.hasMatch(label) ||
      !File('$source/schema.yaml').existsSync()) {
    return '';
  }
  final installed = '$scratch-installed';
  final ChangeFailure? failure;
  try {
    ops.mkdir('$installed/openspec');
    for (final part in ['changes', 'specs', 'config.yaml']) {
      final from = '$scratch/openspec/$part';
      if (FileSystemEntity.typeSync(from) != FileSystemEntityType.notFound) {
        ops.copy(from, '$installed/openspec');
      }
    }
    ops.mkdir('$installed/openspec/schemas');
    ops.copy(source, '$installed/openspec/schemas');
    failure = await checkChange(run, installed, name);
  } on FileSystemException {
    return '';
  }
  // a confirmed failure only: never an invalid schema or a failed run
  if (failure == null ||
      (failure.step != 'validate' && failure.step != 'status')) {
    return '';
  }
  return '; it already fails on $label (${failure.error}), so the update to $to '
      'did not cause it';
}

/// The stamped version in [path], trimmed; null when there is no such file.
String? _readVersion(String path) {
  try {
    return pyStrip(pyDecode(File(path).readAsBytesSync()));
  } on FileSystemException {
    return null;
  }
}

String pyDecode(List<int> bytes) => decodeLossy(bytes);

/// For a workflow update: every change in flight, validated against
/// [schemaDir] in its own scratch root under `<download>/.update-scratch/`
/// (removed on the way out). An entry has `name`, `source`, `status`
/// (`validated`, `not on specwright`, `invalid` or `other project`),
/// `validated_against` and, when invalid, `error` and `note`. In a store
/// (role `owner` or `claim`) a change this project has no branch for belongs
/// to another project: status `other project`, not validated.
Future<
  ({List<Map<String, Object?>> entries, List<Map<String, Object?>> warnings})
>
inflightEntries({
  required UpdateRepo repo,
  required UpdateFileOps ops,
  required OpenspecRunner run,
  required String download,
  required String stateDir,
  required String to,
  required String schemaDir,
  String role = 'none',
}) async {
  final found = await collectInflight(repo);
  final base = '$download/$scratchName';
  final entries = <Map<String, Object?>>[];
  final inStore = role == 'owner' || role == 'claim';
  final branches = inStore
      ? (await repo.gitLines(await repo.codeTop(), [
          'for-each-ref',
          '--format=%(refname:short)',
          'refs/heads/',
        ])).toSet()
      : const <String>{};
  bool ownChange(String name) =>
      changePrefixes.any((p) => branches.contains('$p/$name'));
  try {
    var number = 0;
    for (final item in found.items) {
      number++;
      final scratch = '$base/$number-${item.name}';
      final entry = <String, Object?>{
        'name': item.name,
        'source': item.source,
        'status': 'validated',
        'validated_against': to,
      };
      if (inStore && !ownChange(item.name)) {
        entry
          ..['status'] = 'other project'
          ..['validated_against'] = null;
        entries.add(entry);
        continue;
      }
      try {
        ops.mkdir('$scratch/openspec');
        if (item.ref == null) {
          final root = '${repo.root}/openspec';
          ops.mkdir('$scratch/openspec/changes');
          ops.copy('$root/changes/${item.name}', '$scratch/openspec/changes');
          if (Directory('$root/specs').existsSync()) {
            ops.copy('$root/specs', '$scratch/openspec');
          }
        } else {
          await extractBranch(repo, ops, item, scratch);
        }
        final meta = File(
          '$scratch/openspec/changes/${item.name}/.openspec.yaml',
        );
        final match = meta.existsSync()
            ? RegExp(
                r'''^schema:\s*['"]?([^\s'"#]+)''',
                multiLine: true,
              ).firstMatch(decodeLossy(meta.readAsBytesSync()))
            : null;
        if (match == null || match.group(1) != 'specwright') {
          entry
            ..['status'] = 'not on specwright'
            ..['validated_against'] = null;
        } else {
          ops.mkdir('$scratch/openspec/schemas');
          ops.copy(schemaDir, '$scratch/openspec/schemas');
          File('$scratch/openspec/config.yaml')
              .writeAsStringSync('schema: specwright\n');
          ops.mkdir('$scratch/openspec/specs');
          final failure = await checkChange(run, scratch, item.name);
          if (failure != null) {
            entry
              ..['status'] = 'invalid'
              ..['error'] = failure.error
              ..['note'] = await installedNote(
                repo: repo,
                ops: ops,
                run: run,
                scratch: scratch,
                stateDir: stateDir,
                name: item.name,
                to: to,
                role: role,
              );
          }
        }
      } on FileSystemException catch (e) {
        entry
          ..['status'] = 'invalid'
          ..['error'] = 'could not read the change: ${e.message}';
      } on _CannotRead catch (e) {
        entry
          ..['status'] = 'invalid'
          ..['error'] = 'could not read the change: ${e.message}';
      }
      entries.add(entry);
    }
  } finally {
    try {
      ops.remove(base);
    } on FileSystemException {
      // ignore_errors, as the scratch removal always was
    }
  }
  return (entries: entries, warnings: found.warnings);
}
