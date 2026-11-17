import 'dart:convert';
import 'dart:io';

import '../settings/values.dart' show pyRepr;
import '../vcs/document.dart' show decodeJson;
import 'inflight.dart' show firstError, scratchName;
import 'lifecycle.dart';
import 'options.dart';
import 'packs.dart';
import 'text.dart';

// pack-verify of `scripts/update.sh` (design D5 and D8 of the pack-mechanism
// change): the merged config.yaml is checked through OpenSpec, which is asked
// what an agent would be told. It copies the config.yaml, the download's
// schema and an empty change into a scratch root
// `<download>/.update-scratch/pack-verify/` (removed before it returns) and
// runs `openspec instructions <artifact> --change pack-verify --json` for
// every artifact of the schema and for apply and archive. Nothing else is
// written.

const Duration _deadline = Duration(seconds: 120); // one `openspec` run
const String _change = 'pack-verify';

/// The lines of `context: |` in the download's templates/openspec/config.yaml:
/// the core lines every install delivers.
List<String> _templateContextLines(String download) {
  final file = File('$download/templates/openspec/config.yaml');
  if (!file.existsSync()) return [];
  final out = <String>[];
  var inside = false;
  for (final ln in const LineSplitter().convert(
    utf8.decode(file.readAsBytesSync()),
  )) {
    if (RegExp(r'^context:\s*\|').hasMatch(ln)) {
      inside = true;
    } else if (inside && ln.startsWith('  ')) {
      final t = pyStrip(ln);
      if (t.isNotEmpty && !t.startsWith('#')) out.add(t);
    } else if (inside && pyStrip(ln).isNotEmpty) {
      break;
    }
  }
  return out;
}

List<String> _texts(Object? v) => v is List
    ? [
        for (final x in v)
          if (x is String) x,
      ]
    : const [];

/// `{target: [lines]}` of a manifest: `context`, `rules.<artifact>`,
/// `operations.<op>`; non-lists and non-strings are skipped.
Map<String, List<String>> _manifestTargets(Map<String, Object?> data) {
  final t = <String, List<String>>{'context': _texts(data['context'])};
  final rules = data['rules'];
  if (rules is Map) {
    for (final e in rules.entries) {
      t['rules.${e.key}'] = _texts(e.value);
    }
  }
  final operations = data['operations'];
  if (operations is Map) {
    for (final e in operations.entries) {
      final v = e.value;
      t['operations.${e.key}'] = _texts(v is Map ? v['guidance'] : null);
    }
  }
  return {
    for (final e in t.entries)
      if (e.value.isNotEmpty) e.key: e.value,
  };
}

Map<String, Object?> _error(String code, String message) => {
  'ok': false,
  'interface': updateInterface,
  'subcommand': 'pack-verify',
  'error': code,
  'message': message,
  'problems': <Object?>[],
};

/// `sw update pack-verify`: the document and its exit status (0 when there
/// is no problem).
Future<(Map<String, Object?>, int)> packVerify(UpdateRun r) async {
  final o = r.options;
  final download = r.download;
  final problems = <Map<String, Object?>>[];
  final previous = o.previous.toSet().toList()..sort();

  void problem(
    String code,
    String? pack,
    String? line,
    String? target,
    String message,
  ) {
    problems.add({
      'code': code,
      'pack': pack,
      'line': line,
      'target': target,
      'message': message,
    });
  }

  final artifacts = schemaArtifactIds(download);
  if (artifacts == null) {
    return (
      _error(
        'schema_missing',
        '$download/schemas/specwright/schema.yaml does not exist',
      ),
      1,
    );
  }
  final cfg = '${o.root}/openspec/config.yaml';
  if (!FileSystemEntity.isFileSync(cfg)) {
    return (
      _error('config_missing', '$cfg does not exist; run Step 5 first'),
      1,
    );
  }
  final read = readPackRecord(r.state);
  if (read.problem != null) {
    return (
      _error(
        'packs_record_unreadable',
        'openspec/.specwright/packs.json ${read.problem}',
      ),
      1,
    );
  }
  final enabled = read.record == null
      ? <String>[]
      : (read.record!.keys.toList()..sort());
  // (target, "[pack:<n>] <line>") -> (pack, line, how often the manifest lists it)
  final expected = <(String, String), (String, String, int)>{};
  for (final n in enabled) {
    final m = readManifest('$download/packs/$n');
    if (m.data == null) {
      problem(
        'pack_unreadable',
        n,
        null,
        null,
        'pack $n is enabled but its manifest in the download is unreadable: '
            '${m.problem}',
      );
      continue;
    }
    for (final e in _manifestTargets(m.data!).entries) {
      for (final t in e.value) {
        // trimmed like the delivered lines below
        final key = (e.key, pyStrip('[pack:$n] $t'));
        final was = expected[key];
        expected[key] = (n, t, was == null ? 1 : was.$3 + 1);
      }
    }
  }
  final core = _templateContextLines(download);
  final stale = [
    for (final n in previous)
      if (!enabled.contains(n)) '[pack:$n] ',
  ];

  final base = '$download/$scratchName';
  var runs = 0;
  final delivered = <String, List<String>>{};
  List<String>? context;
  void drop() {
    try {
      if (Directory(base).existsSync()) r.ops.remove(base);
    } on FileSystemException {
      // ignore_errors, as the scratch removal always was
    }
  }

  try {
    drop();
    final scratch = '$base/$_change';
    r.ops.mkdir('$scratch/openspec/changes/$_change');
    r.ops.mkdir('$scratch/openspec/specs');
    r.ops.mkdir('$scratch/openspec/schemas');
    r.ops.copy('$download/schemas/specwright', '$scratch/openspec/schemas');
    File('$scratch/openspec/changes/$_change/.openspec.yaml')
        .writeAsStringSync('schema: specwright\n');
    r.ops.copy(cfg, '$scratch/openspec');
    final asks = [
      for (final a in artifacts) (a, 'rules', 'rules.$a'),
      for (final op in packOperations)
        (op, 'operationGuidance', 'operations.$op'),
    ];
    for (final (what, field, target) in asks) {
      runs++;
      final result = await r.openspec(
        ['instructions', what, '--change', _change, '--json'],
        scratch,
        timeout: _deadline,
      );
      Map<String, Object?>? doc;
      List<Object?>? got;
      try {
        final decoded = decodeJson(result.stdout);
        if (decoded is Map) {
          doc = Map<String, Object?>.from(decoded);
          final field0 = doc[field];
          final value =
              field0 == null ||
                  field0 == false ||
                  (field0 is List && field0.isEmpty)
              ? <Object?>[]
              : field0;
          if (value is List) got = value.cast<Object?>();
        }
      } on FormatException {
        doc = null;
      }
      if (doc == null || got == null || result.code != 0) {
        problem(
          'openspec_failed',
          null,
          null,
          target,
          'openspec instructions $what: '
              '${firstError('${result.stderr}\n${result.stdout}')}',
        );
        if (result.code == 127) break;
        continue;
      }
      delivered[target] = [
        for (final x in got)
          if (x is String) pyStrip(x),
      ];
      if (context == null && artifacts.contains(what)) {
        final c = doc['context'];
        final text = c == null || c == '' || c == false ? '' : '$c';
        context = [
          for (final x in const LineSplitter().convert(text)) pyStrip(x),
        ];
      }
    }
  } finally {
    drop();
  }
  if (context != null) delivered['context'] = context;
  final keys = expected.keys.toList()
    ..sort(
      (a, b) => a.$1 != b.$1 ? a.$1.compareTo(b.$1) : a.$2.compareTo(b.$2),
    );
  for (final key in keys) {
    final (target, full) = key;
    final (n, line, count) = expected[key]!;
    final lines = delivered[target];
    if (lines == null)
      continue; // its run failed: that run is already a problem
    final have = lines.where((l) => l == full).length;
    if (have < count) {
      problem(
        'missing',
        n,
        line,
        target,
        '${pyRepr(full)} is expected $count time(s) in $target and $have '
            'reached OpenSpec',
      );
    } else if (have > count) {
      problem(
        'duplicate',
        n,
        line,
        target,
        '${pyRepr(full)} reaches OpenSpec $have times in $target; expected '
            '$count',
      );
    }
  }
  final targets = delivered.keys.toList()..sort();
  for (final target in targets) {
    for (final ln in delivered[target]!) {
      if (stale.any(ln.startsWith)) {
        final pn = ln.substring('[pack:'.length, ln.indexOf('] '));
        problem(
          'not_enabled',
          pn,
          ln.substring('[pack:$pn] '.length),
          target,
          '${pyRepr(ln)} in $target belongs to pack $pn, which is no longer '
              'enabled',
        );
      }
    }
  }
  final deliveredContext = delivered['context'];
  if (deliveredContext != null) {
    for (final c in core) {
      if (!deliveredContext.contains(c)) {
        problem(
          'core_context_missing',
          null,
          c,
          'context',
          'a Specwright context line does not reach OpenSpec (is context over '
              '50 KB?)',
        );
      }
    }
  }
  return (
    {
      'ok': problems.isEmpty,
      'interface': updateInterface,
      'subcommand': 'pack-verify',
      'checked': {
        'packs': enabled,
        'previous': previous,
        'lines': expected.values.fold<int>(0, (a, v) => a + v.$3),
        'core_lines': core.length,
        'runs': runs,
      },
      'problems': problems,
    },
    problems.isEmpty ? 0 : 1,
  );
}
