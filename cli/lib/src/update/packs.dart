import 'dart:convert';
import 'dart:io';

import 'package:path/path.dart' as p;

import '../settings/values.dart' show pyRepr, pySpaceClass;
import '../vcs/document.dart' show decodeJson, decodeJsonBytes, readBounded;
import 'options.dart';
import 'repo.dart';
import 'text.dart';

// Packs in `sw update`: the checks of `pack-check` and plan's pack refusals
// (design D6 of pack-mechanism, ADR 0023), ported from `scripts/update.sh`.
// The structural checks are the guarantee; the term lists are a deliberately
// crude second net. `packs/README.md` lists the same terms;
// `evals/packs/test_pack_check.py` keeps the two equal.

const List<String> gateTerms = [
  'triage',
  't1',
  't2',
  't3',
  't4',
  't5',
  't6',
  'tier',
  'verdict',
  'review',
  'verify',
  'verification',
  'gate',
  'pre-ship',
  'preship',
  'test-first',
];
const List<String> gateTermsCapitals = ['LIGHT', 'FULL'];
const List<String> relaxingTerms = [
  'skip',
  'skips',
  'skipped',
  'waive',
  'waived',
  'relax',
  'bypass',
  'exempt',
  'ignore',
  'omit',
  'downgrade',
  'optional',
  'not required',
  'need not',
  'no need',
];
const List<String> negatedOnlyTerms = ['trip'];
const List<String> negators = ['not', 'never', "n't"];
const List<String> reservedPackNames = ['specwright', 'openspec', 'opsx'];
const List<String> packFields = [
  'format',
  'name',
  'description',
  'requires',
  'skills',
  'context',
  'rules',
  'operations',
  'documents',
  'init',
  'signals',
];
const List<String> packOperations = ['apply', 'archive'];
const int maxLineChars = 500;
const int maxPackLines = 40;
const int maxContextBytes = 2048;
const String linePrefix = '[pack:';

/// The pack and skill name rule `^[a-z][a-z0-9-]*$` (Python's `$` also
/// matches before one trailing newline).
final RegExp _packName = RegExp(r'^[a-z][a-z0-9-]*\n?$');
final RegExp _unsafePath = RegExp(r'^([/\\]|[A-Za-z]:)');
final RegExp _pathSeparators = RegExp(r'[/\\]');

bool isPackName(Object? value) => value is String && _packName.hasMatch(value);

RegExp _term(String term, {bool ignoreCase = false}) => RegExp(
  '(?<![A-Za-z0-9_])'
  '${RegExp.escape(term).replaceAll(' ', '[$pySpaceClass]+')}'
  '(?![A-Za-z0-9_])',
  caseSensitive: !ignoreCase,
  unicode: true,
);

final List<RegExp> _gateRes = [
  for (final t in gateTerms) _term(t, ignoreCase: true),
  for (final t in gateTermsCapitals) _term(t),
];

final List<RegExp> _relaxRes = [
  for (final t in relaxingTerms) _term(t, ignoreCase: true),
  // `trip` relaxes only after a negator: "must trip T4" passes, "do not trip
  // T2" does not. Whole-word negators need a word boundary before them;
  // `n't` attaches to the word before it.
  for (final t in negatedOnlyTerms)
    RegExp(
      '(?:${[for (final n in negators) '${n.startsWith("n'") ? '' : '(?<![A-Za-z0-9_])'}'
            '${RegExp.escape(n).replaceAll("'", "['’]")}'].join('|')})'
      '[$pySpaceClass]+${RegExp.escape(t)}(?![A-Za-z0-9_])',
      caseSensitive: false,
      unicode: true,
    ),
];

/// True when [line] pairs a gate term with a relaxing term.
bool relaxesGate(String line) =>
    _gateRes.any((r) => r.hasMatch(line)) &&
    _relaxRes.any((r) => r.hasMatch(line));

bool _oneLine(Object? v) =>
    v is String &&
    pyStrip(v).isNotEmpty &&
    !v.contains('\n') &&
    !v.contains('\r');

bool _isFile(String path) => File(path).existsSync();

/// The `id`s of the artifacts in the download's schema, or null when the
/// download has no schema.
List<String>? schemaArtifactIds(String download) {
  final file = File('$download/schemas/specwright/schema.yaml');
  if (!file.existsSync()) return null;
  return [
    for (final m in RegExp(
      r'^  - id: (\S+)\s*$',
      multiLine: true,
    ).allMatches(utf8.decode(file.readAsBytesSync())))
      m.group(1)!,
  ];
}

/// The manifest of `packs/<name>/pack.json`, or the problem with it.
({Map<String, Object?>? data, String? problem}) readManifest(String packDir) {
  final path = '$packDir/pack.json';
  if (!_isFile(path)) return (data: null, problem: 'pack.json is missing');
  final Object? data;
  try {
    data = decodeJson(decodeJsonBytes(readBounded(path), path));
  } on FormatException catch (e) {
    return (data: null, problem: 'pack.json is not valid JSON: ${e.message}');
  } on FileSystemException catch (e) {
    return (data: null, problem: 'pack.json is not valid JSON: ${e.message}');
  }
  if (data is! Map) {
    return (data: null, problem: 'pack.json must be a JSON object');
  }
  return (data: Map<String, Object?>.from(data), problem: null);
}

/// The refusals of one pack, in a stable order. [allNames] is every pack
/// directory of the download.
List<Map<String, Object?>> checkPack(
  String name,
  String packDir,
  Map<String, Object?> data,
  List<String> allNames,
  List<String> artifacts,
) {
  final out = <Map<String, Object?>>[];
  void refuse(
    String code,
    String message, [
    Map<String, Object?> extra = const {},
  ]) {
    out.add({'code': code, 'pack': name, ...extra, 'message': message});
  }

  bool isList(String field, Object? v) {
    if (v is! List) {
      refuse('manifest_invalid', '$field must be a list', {'field': field});
    }
    return v is List;
  }

  if (data.containsKey('source')) {
    refuse(
      'external_pack_unsupported',
      'source is not supported: v1 installs only packs shipped in the Specwright download',
      {'field': 'source'},
    );
  }
  for (final k in data.keys) {
    if (!packFields.contains(k) && k != 'source') {
      refuse('manifest_invalid', 'unknown field $k', {'field': k});
    }
  }
  final fmt = data['format'];
  if (!data.containsKey('format')) {
    refuse('manifest_invalid', 'format is missing', {'field': 'format'});
  } else if (fmt is bool || fmt != 1) {
    refuse(
      'format_unsupported',
      'format ${jsonDumps(fmt)} is not supported; this Specwright reads format 1',
      {'field': 'format'},
    );
  }
  final given = data['name'];
  if (given is! String) {
    refuse('manifest_invalid', 'name is missing or not a string', {
      'field': 'name',
    });
  } else if (given != name) {
    refuse(
      'name_mismatch',
      'name ${pyRepr(given)} does not equal the directory name ${pyRepr(name)}',
      {'field': 'name'},
    );
  }
  if (!isPackName(name) ||
      reservedPackNames.any((r) => name == r || name.startsWith('$r-'))) {
    refuse(
      'manifest_invalid',
      'pack name ${pyRepr(name)} must match ^[a-z][a-z0-9-]*\$ and not be or start with '
          '${reservedPackNames.map((r) => '$r-').join(', ')}',
      {'field': 'name'},
    );
  }
  if (!_oneLine(data['description'])) {
    refuse(
      'manifest_invalid',
      'description is missing or not a non-empty single-line string',
      {'field': 'description'},
    );
  }

  if (data.containsKey('requires') && isList('requires', data['requires'])) {
    final requires = data['requires'] as List;
    for (var i = 0; i < requires.length; i++) {
      final r = requires[i];
      if (!isPackName(r)) {
        refuse('manifest_invalid', 'requires[$i] must be a pack name', {
          'field': 'requires',
          'index': i,
        });
      } else if (!allNames.contains(r)) {
        refuse(
          'pack_requires',
          '$name requires $r, which the download does not have',
          {'field': 'requires', 'index': i, 'requires': r},
        );
      }
    }
  }

  final listed = <String>[];
  if (data.containsKey('skills') && isList('skills', data['skills'])) {
    final skills = data['skills'] as List;
    for (var i = 0; i < skills.length; i++) {
      final s = skills[i];
      if (!isPackName(s)) {
        refuse(
          'skill_name',
          'skills[$i] must be a skill name (^[a-z][a-z0-9-]*\$)',
          {'field': 'skills', 'index': i},
        );
        continue;
      }
      final skill = s as String;
      listed.add(skill);
      String? owner;
      for (final p in allNames) {
        if (skill.startsWith('$p-') &&
            (owner == null || p.length > owner.length)) {
          owner = p;
        }
      }
      if (!skill.startsWith('$name-')) {
        refuse(
          'skill_name',
          'skill $skill does not start with $name-'
              '${owner != null ? '; it belongs to pack $owner' : ''}',
          {'field': 'skills', 'index': i, 'skill': skill, 'owner': ?owner},
        );
      } else if (owner != name) {
        refuse(
          'skill_name',
          'skill $skill belongs to pack $owner, whose prefix $owner- is longer than $name-',
          {'field': 'skills', 'index': i, 'skill': skill, 'owner': owner},
        );
      } else if (!_isFile('$packDir/skills/$skill/SKILL.md')) {
        refuse('skill_missing', 'skill $skill has no skills/$skill/SKILL.md', {
          'field': 'skills',
          'index': i,
          'skill': skill,
        });
      }
    }
  }
  final skillsDir = Directory('$packDir/skills');
  if (skillsDir.existsSync()) {
    final dirs = [
      for (final e in skillsDir.listSync(followLinks: false))
        if (FileSystemEntity.isDirectorySync(e.path)) _basename(e.path),
    ]..sort();
    for (final d in dirs) {
      if (!listed.contains(d)) {
        refuse('skill_unlisted', 'skills/$d is not listed in skills', {
          'field': 'skills',
          'skill': d,
        });
      }
    }
  }

  // (field, index, text) of every well-formed entry, for the count and the
  // gate check
  final lines = <(String, int, String)>[];
  void take(String field, Object? v) {
    if (v is! List) {
      refuse('manifest_invalid', '$field must be a list of lines', {
        'field': field,
      });
      return;
    }
    for (var i = 0; i < v.length; i++) {
      final text = v[i];
      String? why;
      if (text is! String) {
        why = 'is not a string';
      } else if (pyStrip(text).isEmpty) {
        why = 'is empty';
      } else if (text.contains('\n') || text.contains('\r')) {
        why = 'holds a newline';
      } else if (text.runes.length > maxLineChars) {
        why = 'is ${text.runes.length} characters long (at most $maxLineChars)';
      } else if (pyLstrip(text).startsWith(linePrefix)) {
        why = 'starts with $linePrefix (the installer adds the prefix)';
      }
      if (why != null) {
        refuse('line_invalid', '$field[$i] $why', {'field': field, 'index': i});
      } else {
        lines.add((field, i, text as String));
      }
    }
  }

  if (data.containsKey('context')) take('context', data['context']);
  if (data.containsKey('rules')) {
    final rules = data['rules'];
    if (rules is! Map) {
      refuse(
        'manifest_invalid',
        'rules must be an object of artifact id -> list of lines',
        {'field': 'rules'},
      );
    } else {
      for (final e in rules.entries) {
        final k = '${e.key}';
        if (!artifacts.contains(k)) {
          refuse(
            'unknown_artifact',
            'rules.$k: the schema has no artifact $k (it has ${artifacts.join(', ')})',
            {'field': 'rules.$k'},
          );
        } else {
          take('rules.$k', e.value);
        }
      }
    }
  }
  if (data.containsKey('operations')) {
    final operations = data['operations'];
    if (operations is! Map) {
      refuse(
        'manifest_invalid',
        'operations must be an object of apply|archive -> {guidance: [lines]}',
        {'field': 'operations'},
      );
    } else {
      for (final e in operations.entries) {
        final k = '${e.key}';
        final v = e.value;
        if (!packOperations.contains(k)) {
          refuse(
            'unknown_operation',
            'operations.$k: only ${packOperations.join(' and ')} take guidance',
            {'field': 'operations.$k'},
          );
        } else if (v is! Map || v.length != 1 || !v.containsKey('guidance')) {
          refuse(
            'manifest_invalid',
            'operations.$k must be an object holding only guidance',
            {'field': 'operations.$k'},
          );
        } else {
          take('operations.$k', v['guidance']);
        }
      }
    }
  }
  if (lines.length > maxPackLines) {
    refuse(
      'too_many_lines',
      '${lines.length} lines across context, rules and operations (at most $maxPackLines)',
      {'count': lines.length},
    );
  }
  final context = lines
      .where((l) => l.$1 == 'context')
      .fold<int>(0, (n, l) => n + utf8.encode(l.$3).length);
  if (context > maxContextBytes) {
    refuse(
      'context_too_large',
      'context holds $context bytes in UTF-8 (at most $maxContextBytes)',
      {'field': 'context', 'count': context},
    );
  }
  for (final (field, index, text) in lines) {
    if (relaxesGate(text)) {
      refuse(
        'relaxes_gate',
        '$field[$index] pairs a gate term with a relaxing term: $text',
        {'field': field, 'index': index, 'line': text},
      );
    }
  }

  if (data.containsKey('documents')) {
    final docs = data['documents'];
    if (docs is! Map) {
      refuse(
        'document_invalid',
        'documents must be an object of id -> {path, template}',
        {'field': 'documents'},
      );
    } else {
      for (final e in docs.entries) {
        final k = '${e.key}';
        final v = e.value;
        final path = v is Map ? v['path'] : null;
        final template = v is Map ? v['template'] : null;
        String? why;
        if (!RegExp(r'^[a-z][a-z0-9_-]*\n?$').hasMatch(k)) {
          why = 'the id must match ^[a-z][a-z0-9_-]*\$';
        } else if (v is! Map ||
            v.length != 2 ||
            !v.containsKey('path') ||
            !v.containsKey('template')) {
          why = 'an entry holds exactly path and template';
        } else if (!_oneLine(path) ||
            _unsafePath.hasMatch(path as String) ||
            path.split(_pathSeparators).contains('..') ||
            path.endsWith('/') ||
            path.endsWith(r'\')) {
          why = 'path ${pyRepr(path)} must be a relative file path without ..';
        } else if (!_oneLine(template) ||
            _unsafePath.hasMatch(template as String) ||
            template.split(_pathSeparators).contains('..')) {
          why =
              'template ${pyRepr(template)} must be a relative path inside the pack';
        } else if (!_isFile('$packDir/$template')) {
          why = 'template $template does not exist in the pack';
        }
        if (why != null) {
          refuse('document_invalid', 'documents.$k: $why', {
            'field': 'documents.$k',
          });
        }
      }
    }
  }
  if (data.containsKey('init')) {
    final init = data['init'];
    if (init is! Map ||
        init.length != 1 ||
        !init.containsKey('questions') ||
        init['questions'] is! List) {
      refuse(
        'init_invalid',
        'init must be an object holding only questions, a list of single-line strings',
        {'field': 'init'},
      );
    } else {
      final questions = init['questions'] as List;
      for (var i = 0; i < questions.length; i++) {
        if (!_oneLine(questions[i])) {
          refuse(
            'init_invalid',
            'init.questions[$i] must be a non-empty single-line string',
            {'field': 'init.questions', 'index': i},
          );
        }
      }
    }
  }
  if (data.containsKey('signals')) {
    final signals = data['signals'];
    if (signals is! List) {
      refuse(
        'signals_invalid',
        'signals must be a list of non-empty single-line strings',
        {'field': 'signals'},
      );
    } else {
      for (var i = 0; i < signals.length; i++) {
        if (!_oneLine(signals[i])) {
          refuse(
            'signals_invalid',
            'signals[$i] must be a non-empty single-line string',
            {'field': 'signals', 'index': i},
          );
        }
      }
    }
  }
  return out;
}

String _basename(String path) {
  final at = path.lastIndexOf(RegExp(r'[/\\]'));
  return at < 0 ? path : path.substring(at + 1);
}

/// The cycle through [start] as a list of pack names ([start] first), or
/// null.
List<String>? requiresCycle(String start, Map<String, List<String>> graph) {
  List<String>? walk(String node, List<String> path) {
    for (final next in graph[node] ?? const <String>[]) {
      if (next == start) return path;
      if (graph.containsKey(next) && !path.contains(next)) {
        final found = walk(next, [...path, next]);
        if (found != null) return found;
      }
    }
    return null;
  }

  return walk(start, [start]);
}

/// The result of checking packs of a download: the pack list `{name, ok}` and
/// every refusal.
class PackCheck {
  PackCheck(this.packs, this.refusals);

  final List<Map<String, Object?>> packs;
  final List<Map<String, Object?>> refusals;
}

/// The packs of the download's `packs/` named in [wanted] (every pack when
/// empty), checked against the download's schema; null when the download has
/// no schema. One pass for `pack-check` and for `plan`, so a pack is judged
/// the same way in both.
PackCheck? checkPacks(String download, List<String> wanted) {
  final artifacts = schemaArtifactIds(download);
  if (artifacts == null) return null;
  final packsDir = Directory('$download/packs');
  final allNames = packsDir.existsSync()
      ? ([
          for (final e in packsDir.listSync(followLinks: false))
            if (FileSystemEntity.isDirectorySync(e.path)) _basename(e.path),
        ]..sort())
      : <String>[];
  final graph = <String, List<String>>{};
  for (final n in allNames) {
    final m =
        readManifest('${packsDir.path}/$n').data ?? const <String, Object?>{};
    final requires = m['requires'];
    graph[n] = requires is List
        ? [
            for (final r in requires)
              if (r is String) r,
          ]
        : [];
  }
  final packs = <Map<String, Object?>>[];
  final refusals = <Map<String, Object?>>[];
  final names = wanted.toSet().toList()..sort();
  for (final n in names.isEmpty ? allNames : names) {
    final List<Map<String, Object?>> found;
    if (!allNames.contains(n)) {
      found = [
        {
          'code': 'pack_unknown',
          'pack': n,
          'available': allNames,
          'message':
              'the download has no pack $n; it has: '
              '${allNames.isNotEmpty ? allNames.join(', ') : 'none'}',
        },
      ];
    } else {
      final read = readManifest('${packsDir.path}/$n');
      if (read.data == null) {
        found = [
          {'code': 'manifest_invalid', 'pack': n, 'message': read.problem},
        ];
      } else {
        found = checkPack(
          n,
          '${packsDir.path}/$n',
          read.data!,
          allNames,
          artifacts,
        );
        final cycle = requiresCycle(n, graph);
        if (cycle != null) {
          found.add({
            'code': 'pack_cycle',
            'pack': n,
            'cycle': cycle,
            'message': 'requires form a cycle: ${[...cycle, n].join(' -> ')}',
          });
        }
      }
    }
    packs.add({'name': n, 'ok': found.isEmpty});
    refusals.addAll(found);
  }
  return PackCheck(packs, refusals);
}

/// `sw update pack-check`: the packs of the download (all, or those named
/// with `--pack`) checked, read only. Returns the document and its exit
/// code: 0 when every pack passes, 1 otherwise.
(Map<String, Object?>, int) packCheckDocument(UpdateOptions options) {
  final download = options.download ?? options.code;
  final result = checkPacks(download, options.packs);
  if (result == null) {
    return (
      {
        'ok': false,
        'subcommand': 'pack-check',
        'packs': <Object?>[],
        'refusals': [
          {
            'code': 'schema_missing',
            'pack': null,
            'message':
                '$download/schemas/specwright/schema.yaml does not exist',
          },
        ],
      },
      1,
    );
  }
  return (
    {
      'ok': result.refusals.isEmpty,
      'subcommand': 'pack-check',
      'packs': result.packs,
      'refusals': result.refusals,
    },
    result.refusals.isEmpty ? 0 : 1,
  );
}

// ---- packs in plan (design D3, D4, D7, D8, D9 of pack-mechanism) ------------
//
// `plan --pack NAME ...` runs the pack checks on the enabled packs, adds
// their skill directories to every skills group, and decides who owns each
// skill directory from the record `openspec/.specwright/packs.json` (format
// 1, written by the swap).

/// True when [path] is [top] or below it, judged by identity: links
/// resolved, case-insensitive file systems.
bool within(String path, String top) {
  // links are followed in the part of the path that exists; the rest is
  // folded as text, as Python's non-strict `resolve` does
  var existing = p.normalize(p.absolute(path));
  final rest = <String>[];
  while (FileSystemEntity.typeSync(existing) == FileSystemEntityType.notFound) {
    final parent = p.dirname(existing);
    if (parent == existing) break;
    rest.insert(0, p.basename(existing));
    existing = parent;
  }
  final resolved = rest.isEmpty
      ? resolvePosix(existing)
      : p.joinAll([resolvePosix(existing), ...rest]);
  return pathWithin(posixPath(resolved), resolvePosix(top));
}

/// The record of `packs.json`: every pack and its recorded skills.
typedef PackRecord = Map<String, List<String>>;

/// `read_pack_record`: the record at `<code>/openspec/.specwright/packs.json`
/// as `{pack: skills}`, null when there is none; the problem is set when the
/// file is unreadable.
({PackRecord? record, String? problem}) readPackRecord(String stateDir) {
  final path = '$stateDir/packs.json';
  if (!_isFile(path)) return (record: null, problem: null);
  final Object? data;
  try {
    data = decodeJson(decodeJsonBytes(readBounded(path), path));
  } on FormatException catch (e) {
    return (record: null, problem: 'is not readable JSON (${e.message})');
  } on FileSystemException catch (e) {
    return (record: null, problem: 'is not readable JSON (${e.message})');
  }
  final format = data is Map ? data['format'] : null;
  if (data is! Map ||
      !(format == 1 || format == true) ||
      data['packs'] is! Map) {
    return (
      record: null,
      problem: 'is not a format 1 record with a packs object',
    );
  }
  final packs = <String, List<String>>{};
  for (final e in (data['packs'] as Map).entries) {
    final v = e.value;
    final skills = v is Map
        ? (v.containsKey('skills') ? v['skills'] : <Object?>[])
        : null;
    if (v is! Map || skills is! List) {
      return (
        record: null,
        problem: 'lists pack ${e.key} without a skills list',
      );
    }
    if (isPackName(e.key)) {
      // a name that could leave the skills directory is never trusted
      packs['${e.key}'] = [
        for (final s in {
          for (final s in skills)
            if (isPackName(s)) s as String,
        })
          s,
      ]..sort();
    }
  }
  return (record: packs, problem: null);
}

/// The packs enabled before this update (design D5): a pending journal's
/// `prev_packs`, else the record's, else none.
List<String> previousPacks(String stateDir, PackRecord? record) {
  final file = File('$stateDir/update.json');
  if (file.existsSync()) {
    Object? data;
    try {
      data = decodeJson(decodeJsonBytes(readBounded(file.path), file.path));
    } on FormatException {
      data = null;
    } on FileSystemException {
      data = null;
    }
    if (data is Map && data['prev_packs'] is List) {
      return [
        for (final n in data['prev_packs'] as List)
          if (n is String) n,
      ];
    }
  }
  return record == null ? [] : (record.keys.toList()..sort());
}

/// Dependencies first, then by name.
List<String> installOrder(
  Set<String> enabled,
  Map<String, List<String>> requires,
) {
  final order = <String>[];
  final seen = <String>{};
  void visit(String n) {
    if (!seen.add(n)) return;
    for (final r in [...?requires[n]]..sort()) {
      if (enabled.contains(r)) visit(r);
    }
    order.add(n);
  }

  for (final n in enabled.toList()..sort()) {
    visit(n);
  }
  return order;
}

/// Why a pack document path is refused (design D8), or null.
String? docPathProblem(String top, String path) {
  if (pyStrip(path).isEmpty) return 'is empty';
  if (_unsafePath.hasMatch(path)) return 'is absolute';
  if (path.split(_pathSeparators).contains('..')) return 'contains ..';
  if (path.endsWith('/') || path.endsWith(r'\')) return 'names a directory';
  final full = '$top/$path';
  if (!within(full, top)) return 'leaves the code checkout';
  if (FileSystemEntity.isDirectorySync(full)) return 'names a directory';
  return null;
}

/// What `plan` knows about packs: the enabled packs in install order with
/// their manifests, the record, `packs_previous`, the documents and the
/// adopted skills.
class PackPlan {
  final List<String> order = [];
  final Map<String, Map<String, Object?>> manifests = {};
  PackRecord? record;
  List<String> previous = [];
  final Map<String, List<Map<String, Object?>>> documents = {};
  final Map<String, List<Map<String, Object?>>> adopted = {};
  bool ok = false;
}

/// `pack_plan`: reads and checks the enabled packs ([UpdateOptions.packs]),
/// appends every pack refusal to [refusals], and writes nothing. [role] is
/// the project's store role.
Future<PackPlan> planPacks(
  UpdateOptions options,
  UpdateRepo repo,
  String stateDir,
  String? role,
  List<Map<String, Object?>> refusals,
) async {
  final pk = PackPlan();
  final read = readPackRecord(stateDir);
  if (read.problem != null) {
    refusals.add({
      'code': 'packs_record_unreadable',
      'message':
          'openspec/.specwright/packs.json ${read.problem}. Nothing was '
          'written; fix or remove the file, then rerun the update',
    });
  }
  pk.record = read.record;
  pk.previous = previousPacks(stateDir, read.record);
  final want = options.packs.toSet().toList()..sort();
  final start = refusals.length;
  final top = await repo.codeTop();
  final download = options.download ?? options.code;
  if (want.isNotEmpty) {
    if (role == 'claim' || role == 'owner' || role == 'other') {
      refusals.add({
        'code': 'packs_on_store',
        'packs': want,
        'message':
            'packs (${want.join(', ')}) are not supported while the planning '
            'root is a store (role $role): the pack lines in the store\'s '
            'config.yaml would apply to every project that uses it. Remove '
            'packs: from openspec/specwright.yaml or use a repo-local '
            'planning root. Nothing was written',
      });
    }
    for (final dir in options.skills) {
      if (!within(dir, top)) {
        refusals.add({
          'code': 'packs_user_level',
          'dir': dir,
          'message':
              'packs (${want.join(', ')}) need skills directories inside the '
              'code checkout, and $dir is outside $top: several projects '
              'would share, and remove, the same pack skills. Choose '
              'project-level skills directories or remove packs: from '
              'openspec/specwright.yaml. Nothing was written',
        });
      }
    }
    final checked = checkPacks(download, want);
    // a missing schema is download_incomplete
    refusals.addAll([
      for (final f in checked?.refusals ?? const <Map<String, Object?>>[])
        if (f['code'] != 'schema_missing') f,
    ]);
    final packsDir = '$download/packs';
    final manifests = <String, Map<String, Object?>>{};
    for (final p in checked?.packs ?? const <Map<String, Object?>>[]) {
      if (p['ok'] == true) {
        manifests['${p['name']}'] =
            readManifest('$packsDir/${p['name']}').data ?? {};
      }
    }
    for (final n in manifests.keys.toList()..sort()) {
      final requires = manifests[n]!['requires'];
      for (final r in requires is List ? requires : const []) {
        if (!want.contains(r) && Directory('$packsDir/$r').existsSync()) {
          refusals.add({
            'code': 'pack_requires',
            'pack': n,
            'requires': r,
            'message':
                '$n requires $r, which packs: does not enable; enable $r too '
                '(it is never enabled on its own), or remove $n. Nothing was '
                'written',
          });
        }
      }
    }
    // no schema: build_groups refuses it as download_incomplete
    pk.ok = refusals.length == start && checked != null;
    if (pk.ok) {
      pk.manifests.addAll(manifests);
      pk.order.addAll(
        installOrder(want.toSet(), {
          for (final e in manifests.entries)
            e.key: [
              if (e.value['requires'] is List)
                for (final r in e.value['requires'] as List) '$r',
            ],
        }),
      );
    }
  }
  final overrides = <(String, String), String>{};
  for (final spec in options.packDocs) {
    final eq = spec.indexOf('=');
    final key = eq < 0 ? spec : spec.substring(0, eq);
    final path = eq < 0 ? '' : spec.substring(eq + 1);
    final dot = key.indexOf('.');
    final pack = dot < 0 ? key : key.substring(0, dot);
    final did = dot < 0 ? '' : key.substring(dot + 1);
    if (eq < 0 || dot < 0 || pack.isEmpty || did.isEmpty) {
      refusals.add({
        'code': 'pack_doc_invalid',
        'message': '--pack-doc ${pyRepr(spec)} is not <pack>.<id>=<path>',
      });
    } else if (!want.contains(pack)) {
      refusals.add({
        'code': 'pack_doc_unknown',
        'pack': pack,
        'document': did,
        'message': '--pack-doc $spec: pack $pack is not enabled',
      });
    } else if (pk.ok && !_declares(pk.manifests[pack]!, did)) {
      refusals.add({
        'code': 'pack_doc_unknown',
        'pack': pack,
        'document': did,
        'message': '--pack-doc $spec: pack $pack declares no document $did',
      });
    } else {
      overrides[(pack, did)] = path;
    }
  }
  for (final pn in pk.order) {
    final found = <Map<String, Object?>>[];
    final docs = pk.manifests[pn]!['documents'];
    for (final e
        in docs is Map ? docs.entries : const <MapEntry<Object?, Object?>>[]) {
      final did = '${e.key}';
      final path = overrides[(pn, did)] ?? '${(e.value as Map)['path']}';
      final why = docPathProblem(top, path);
      if (why != null) {
        refusals.add({
          'code': 'pack_doc_path',
          'pack': pn,
          'document': did,
          'path': path,
          'message':
              'document $did of pack $pn: the path $path $why. Nothing was written',
        });
      } else {
        found.add({'id': did, 'path': path, 'exists': _isFile('$top/$path')});
      }
    }
    pk.documents[pn] = found;
  }
  return pk;
}

bool _declares(Map<String, Object?> manifest, String id) {
  final docs = manifest['documents'];
  return docs is Map && docs.containsKey(id);
}

/// True when directories [a] and [b] hold the same files with the same
/// bytes. A link in either is never the same: an adopted directory is
/// replaced whole, so a link the user added would be lost.
bool sameTree(String a, String b) {
  if (!Directory(a).existsSync() || !Directory(b).existsSync()) return false;
  Map<String, File>? files(String dir) {
    final out = <String, File>{};
    for (final e in Directory(
      dir,
    ).listSync(recursive: true, followLinks: false)) {
      if (e is Link) return null;
      if (e is File) {
        out[resolvePosix(e.path).substring(resolvePosix(dir).length + 1)] = e;
      }
    }
    return out;
  }

  final fa = files(a);
  final fb = files(b);
  if (fa == null || fb == null) return false;
  if (fa.length != fb.length) return false;
  for (final k in fa.keys) {
    final other = fb[k];
    if (other == null) return false;
    final x = fa[k]!.readAsBytesSync();
    final y = other.readAsBytesSync();
    if (x.length != y.length) return false;
    for (var i = 0; i < x.length; i++) {
      if (x[i] != y[i]) return false;
    }
  }
  return true;
}

void _addItem(
  Map<String, Object?> group,
  String name,
  String type,
  String? src,
  String pack,
) {
  (group['items'] as List<Map<String, Object?>>).add({
    'name': name,
    'type': type,
    'src': src,
    'installed':
        FileSystemEntity.typeSync(
          '${group['dir']}/$name',
          followLinks: false,
        ) !=
        FileSystemEntityType.notFound,
    'pack': pack,
  });
}

/// Pack items of one skills group (design D3, D4): the enabled packs' skills
/// (adopted when byte-identical and not recorded, `unmanaged_skill`
/// otherwise), orphans among their recorded skills, and `remove` items for
/// the recorded skills of packs no longer enabled, only where this directory
/// holds them. Unrecorded directories of other packs are never looked at.
Future<void> addPackSkillItems(
  UpdateOptions options,
  UpdateRepo repo,
  Map<String, Object?> group,
  PackPlan pk,
  List<Map<String, Object?>> refusals,
  List<Map<String, Object?>> orphans,
) async {
  final download = options.download ?? options.code;
  final dir = '${group['dir']}';
  final record = pk.record ?? const <String, List<String>>{};
  final shipped = <String>{};
  for (final pn in pk.order) {
    final skills = [
      if (pk.manifests[pn]!['skills'] is List)
        for (final s in pk.manifests[pn]!['skills'] as List) '$s',
    ];
    final recorded = (record[pn] ?? const <String>[]).toSet();
    shipped.addAll(skills);
    for (final s in skills) {
      final src = '$download/packs/$pn/skills/$s';
      final target = '$dir/$s';
      final present =
          FileSystemEntity.typeSync(target, followLinks: false) !=
          FileSystemEntityType.notFound;
      if (present && !recorded.contains(s)) {
        if (sameTree(target, src)) {
          (pk.adopted[pn] ??= []).add({
            'group': group['id'],
            'dir': dir,
            'name': s,
            'path': target,
          });
        } else {
          refusals.add({
            'code': 'unmanaged_skill',
            'pack': pn,
            'skill': s,
            'group': group['id'],
            'path': target,
            'message':
                '$target is a skill directory named like pack $pn\'s skill $s, '
                'but Specwright did not install it and it differs from the '
                'download\'s. Move or remove it, then rerun the update. Nothing '
                'was written',
          });
        }
      }
      _addItem(group, s, 'dir', src, pn);
    }
    // recorded, and the download no longer ships it
    for (final s in recorded.difference(skills.toSet()).toList()..sort()) {
      if (Directory('$dir/$s').existsSync()) {
        orphans.add({'group': group['id'], 'dir': dir, 'name': s});
      }
    }
  }
  final enabled = options.packs.toSet();
  // packs install only inside the checkout, so nothing of theirs is outside it
  if (!within(dir, await repo.codeTop())) return;
  for (final pn in record.keys.toList()..sort()) {
    if (enabled.contains(pn)) continue;
    // only a skill named like its pack: an edited record cannot name an
    // unrelated skill
    for (final s in record[pn]!) {
      if (!shipped.contains(s) &&
          s.startsWith('$pn-') &&
          FileSystemEntity.typeSync('$dir/$s', followLinks: false) !=
              FileSystemEntityType.notFound) {
        _addItem(group, s, 'remove', null, pn);
      }
    }
  }
}

/// The content of the new `packs.json` (design D4): every enabled pack with
/// the download's [version], its skills, its resolved document paths and its
/// init questions, then the catalogue of every pack in the download. Written
/// on every install.
Future<List<int>> packRecordBytes(
  UpdateOptions options,
  UpdateRepo repo,
  String version,
  PackPlan pk,
) async {
  final download = options.download ?? options.code;
  final packsDir = Directory('$download/packs');
  final record = pk.record ?? const <String, List<String>>{};
  final top = await repo.codeTop();
  final packs = <String, Object?>{};
  for (final pn in pk.order) {
    final m = pk.manifests[pn]!;
    final skills = [
      if (m['skills'] is List)
        for (final s in m['skills'] as List) '$s',
    ];
    // a recorded skill the download no longer ships, still on disk (an orphan
    // the user kept), stays the pack's, so it is reported again and removed
    // with the pack
    for (final s in record[pn] ?? const <String>[]) {
      if (!skills.contains(s) &&
          s.startsWith('$pn-') &&
          options.skills.any(
            (sd) => within(sd, top) && Directory('$sd/$s').existsSync(),
          )) {
        skills.add(s);
      }
    }
    final init = m['init'];
    final questions = init is Map && init['questions'] is List
        ? [for (final q in init['questions'] as List) q]
        : <Object?>[];
    packs[pn] = {
      'version': version,
      'skills': skills,
      'documents': {
        for (final d in pk.documents[pn] ?? const <Map<String, Object?>>[])
          '${d['id']}': d['path'],
      },
      'init': {'questions': questions},
    };
  }
  final catalogue = <Map<String, Object?>>[];
  if (packsDir.existsSync()) {
    final names = [
      for (final e in packsDir.listSync(followLinks: false))
        if (FileSystemEntity.isDirectorySync(e.path)) _basename(e.path),
    ]..sort();
    for (final d in names) {
      final m = readManifest('${packsDir.path}/$d').data;
      if (m == null) continue; // a pack that cannot be read is not offered
      List<Object?> texts(Object? v) => [
        if (v is List)
          for (final x in v)
            if (x is String) x,
      ];
      catalogue.add({
        'name': d,
        'description': m['description'] is String ? m['description'] : '',
        'requires': texts(m['requires']),
        'signals': texts(m['signals']),
      });
    }
  }
  final doc = {'format': 1, 'packs': packs, 'catalogue': catalogue};
  return utf8.encode('${const JsonEncoder.withIndent('  ').convert(doc)}\n');
}
