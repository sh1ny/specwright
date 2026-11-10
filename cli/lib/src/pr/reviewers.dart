import 'dart:convert';
import 'dart:typed_data';

import '../commit/task_cover.dart' show pyStrip;
import '../finish/undo_plan.dart' show prefixOf;
import '../options.dart';
import '../settings/reviewer_config.dart' show sha256Hex;
import '../settings/yaml.dart' show pyDecimalValue, pyStr;
import '../vcs/document.dart';

// `sw pr reviewers`: the port of `reviewers.py`, the reviewer-detection evaluator behind the pr snapshot (design D5).
//
//   sw pr reviewers --config FILE --material FILE --head OID
//   sw pr reviewers --check-config FILE
//
// Exit 0 ok; 1 the material is unreadable or malformed, or --head is not its head; 2 a usage or config problem (one
// stderr line, nothing on stdout). Every stderr line starts with `reviewers.py: `, as the script's did (D11).
//
// Report patterns (`sha_pattern`, `ignore`) are JavaScript regular expressions in Unicode mode (ADR 0030): they are
// compiled with `RegExp(p, unicode: true)`, case-sensitive and not multiline, and searched. Python-only syntax
// (`(?P<`, `\A`, `\Z`, `(?i)`, `{,3}`) does not compile. The config is `"format": 2` (D10).
//
// A regex in Dart cannot be interrupted, so this runs as a child of `sw pr snapshot` under the poll's deadline, never
// in the snapshot's own process (ADR 0022, C1).

const String _name = 'reviewers.py';
const int _maxReviewers = 20;
const int _maxText = 500;
const int _maxEvidence = 10;
const int _maxExcerpt = 300;
const List<String> _reviewerKeys = ['login', 'role', 'timeout', 'report'];
const List<String> _reportKeys = ['sha_pattern', 'check', 'marker', 'ignore'];
const List<String> _ruleKeys = ['sha_pattern', 'check', 'marker'];
const Set<String> _removed = {
  'material',
  'checks_all',
  'cfg',
  'sig_base',
  'attn_base',
};

// Python's `$` also matches before a final newline, so a login or hex digit string may end in one.
final RegExp _loginRe = RegExp(r'^[A-Za-z0-9][A-Za-z0-9-]*\n?$');
final RegExp _hexRe = RegExp(r'^[0-9a-fA-F]{7,40}\n?$');
final RegExp _isoRe = RegExp(
  r'^(\p{Nd}{4})-(\p{Nd}{2})-(\p{Nd}{2})[Tt ](\p{Nd}{2}):(\p{Nd}{2}):(\p{Nd}{2})'
  r'(?:\.(\p{Nd}+))?(Z|z|[+-]\p{Nd}{2}:?\p{Nd}{2})?$',
  unicode: true,
);

class _ConfigError implements Exception {
  _ConfigError(this.message);
  final String message;
}

class _MaterialError implements Exception {
  _MaterialError(this.message);
  final String message;
}

class _Reviewer {
  _Reviewer(this.login, this.role, this.timeout, this.report);

  final String login;
  final String role;
  final int timeout;
  final Map<String, String> report;
}

/// `sw pr reviewers <args>`. Returns the exit status; [writeOut] and [writeErr] take the bytes.
int runReviewers(
  List<String> args, {
  required void Function(List<int> bytes) writeOut,
  required void Function(List<int> bytes) writeErr,
}) {
  void emit(Object? document) =>
      writeOut(_utf8Replace('${documentText(document)}\n'));
  void say(String text) => writeErr(_utf8Replace('$_name: $text\n'));

  final String? checkConfig;
  final String? config;
  final String? material;
  final String? head;
  final List<_Reviewer> reviewers;
  final String? digest;
  try {
    final opts = _parseArgs(args);
    checkConfig = opts['check-config'];
    config = opts['config'];
    material = opts['material'];
    head = opts['head'];
    if (_given(checkConfig)) {
      if (_given(config) || _given(material) || _given(head)) {
        throw _ConfigError('usage: --check-config takes no other option');
      }
      final loaded = _loadConfig(checkConfig!);
      emit({
        'ok': true,
        'digest': loaded.digest,
        'logins': [for (final r in loaded.reviewers) r.login],
      });
      return 0;
    }
    if (!_given(material) || !_given(head)) {
      throw _ConfigError('usage: --material and --head are required');
    }
    if (_given(config)) {
      final loaded = _loadConfig(config!);
      reviewers = loaded.reviewers;
      digest = loaded.digest;
    } else {
      reviewers = const [];
      digest = null;
    }
  } on _ConfigError catch (e) {
    say(e.message);
    return 2;
  }
  try {
    final mat = readJsonFile(material!);
    emit(_evaluate(mat, reviewers, digest, head!));
    return 0;
  } on JsonInputException catch (e) {
    say(e.message);
    return 1;
  } on _MaterialError catch (e) {
    say('$material: ${e.message}');
    return 1;
  } on Object catch (e) {
    // anything the script's own checks did not name ended it with a traceback and status 1
    say('$material: ${e.runtimeType}');
    return 1;
  }
}

bool _given(String? v) => v != null && v.isNotEmpty;

// ---------------------------------------------------------------- arguments

/// The four options, each with one value, under the one option rule (`options.dart`): `--opt VALUE` or `--opt=VALUE`, no
/// abbreviations, the last of a repeated option wins. Anything else is a usage error.
Map<String, String> _parseArgs(List<String> args) {
  final parsed = parseOptions(
    args,
    values: const ['config', 'material', 'head', 'check-config'],
    usage: (message) => throw _ConfigError('usage: $message'),
  );
  if (parsed.rest.isNotEmpty) {
    throw _ConfigError(
      'usage: unrecognized arguments: ${parsed.rest.join(' ')}',
    );
  }
  return {
    for (final name in parsed.options)
      if (parsed.wasParsed(name)) name: parsed.option(name)!,
  };
}

// ------------------------------------------------------------------- config

/// `<file>: <what>` with Python's wording kept for the three words a caller reads.
({List<_Reviewer> reviewers, String digest}) _loadConfig(String path) {
  final Object? cfg;
  final List<int>
  raw; // one read: the digest is of the bytes the rules came from
  try {
    raw = readBounded(path);
    cfg = decodeJson(decodeJsonBytes(raw, path), file: path);
  } on JsonInputException catch (e) {
    throw _ConfigError(e.message);
  }
  return (reviewers: _validateConfig(cfg, path), digest: sha256Hex(raw));
}

_ConfigError _bad(String login, String? key, String why) =>
    _ConfigError(key != null ? '$login: $key: $why' : '$login: $why');

List<_Reviewer> _validateConfig(Object? cfg, String fname) {
  _ConfigError top(String why) => _ConfigError('$fname: $why');

  if (cfg is! Map<String, Object?>) throw top('config must be a JSON object');
  for (final key in cfg.keys) {
    if (key != 'format' && key != 'reviewers') throw top('unknown key $key');
  }
  final format = cfg['format'];
  if (format is! num || format != 2) throw top('format must be 2');
  final revs = cfg['reviewers'];
  if (revs is! List<Object?>) throw top('reviewers must be a list');
  if (revs.length > _maxReviewers) {
    throw top('reviewers: more than $_maxReviewers reviewers');
  }
  final out = <_Reviewer>[];
  final seen = <String>{};
  for (final r in revs) {
    if (r is! Map<String, Object?>) {
      throw top('reviewers: each reviewer must be an object');
    }
    final login = r['login'];
    if (login is! String || !_loginRe.hasMatch(login)) {
      throw _bad(
        login is String ? login : '?',
        'login',
        r'must match ^[A-Za-z0-9][A-Za-z0-9-]*$',
      );
    }
    for (final key in r.keys) {
      if (!_reviewerKeys.contains(key)) throw _bad(login, key, 'unknown key');
    }
    if (!seen.add(login.toLowerCase())) {
      throw _bad(login, 'login', 'listed twice');
    }
    final role = r['role'];
    if (role != 'required' && role != 'advisory') {
      throw _bad(login, 'role', 'must be required or advisory');
    }
    final timeout = r['timeout'];
    if (timeout is! int || timeout < 0) {
      throw _bad(login, 'timeout', 'must be a non-negative integer');
    }
    out.add(
      _Reviewer(
        login,
        role as String,
        timeout,
        r.containsKey('report') ? _validateReport(login, r['report']) : {},
      ),
    );
  }
  return out;
}

Map<String, String> _validateReport(String login, Object? report) {
  if (report is! Map<String, Object?>) {
    throw _bad(login, 'report', 'must be an object');
  }
  final out = <String, String>{};
  for (final MapEntry(:key, value: val) in report.entries) {
    if (!_reportKeys.contains(key)) {
      throw _bad(login, 'report.$key', 'unknown key');
    }
    if (val is! String || val.isEmpty) {
      throw _bad(login, 'report.$key', 'must be a non-empty string');
    }
    if (val.runes.length > _maxText) {
      throw _bad(login, 'report.$key', 'longer than $_maxText characters');
    }
    if (key == 'sha_pattern' || key == 'ignore') {
      final RegExp rx;
      try {
        rx = RegExp(val, unicode: true);
      } on FormatException catch (e) {
        throw _bad(login, 'report.$key', 'does not compile: ${e.message}');
      }
      if (key == 'sha_pattern' && groupCount(rx) < 1) {
        throw _bad(
          login,
          'report.$key',
          'needs a capture group for the commit SHA',
        );
      }
    }
    out[key] = val;
  }
  return out;
}

/// The number of capture groups of [pattern]. A Dart `RegExp` shows none before a match, so the pattern is wrapped in
/// a non-capturing group with an empty alternative, which always matches the empty string, and its match is counted.
int groupCount(RegExp pattern) {
  final probe = RegExp(
    '(?:${pattern.pattern})|',
    unicode: pattern.isUnicode,
    caseSensitive: pattern.isCaseSensitive,
    multiLine: pattern.isMultiLine,
  );
  return probe.firstMatch('')!.groupCount;
}

// --------------------------------------------------------------- evaluation

bool _truthy(Object? v) => switch (v) {
  null => false,
  bool b => b,
  int n => n != 0,
  double d => d != 0,
  String s => s.isNotEmpty,
  List<Object?> l => l.isNotEmpty,
  Map<Object?, Object?> m => m.isNotEmpty,
  _ => true,
};

/// Python's `a or b`.
Object? _or(Object? a, Object? b) => _truthy(a) ? a : b;

/// `d.get(key)` of a value that must be an object.
Object? _get(Object? d, String key) {
  if (d is Map<String, Object?>) return d[key];
  throw _MaterialError("'${_typeName(d)}' object has no attribute 'get'");
}

String _typeName(Object? v) => switch (v) {
  null => 'NoneType',
  bool() => 'bool',
  int() => 'int',
  double() => 'float',
  String() => 'str',
  List() => 'list',
  _ => 'dict',
};

/// `(v or "")` where a string must come out: a body, a name.
String _text(Object? v) {
  if (!_truthy(v)) return '';
  if (v is String) return v;
  throw _MaterialError('expected string, got ${_typeName(v)}');
}

/// Seconds since the epoch of an ISO 8601 string, or null (`parse_iso`).
double? _parseIso(Object? s) {
  if (s is! String) return null;
  final m = _isoRe.firstMatch(pyStrip(s));
  if (m == null) return null;
  int n(int g) => pyDecimalValue(m[g]!)!.toInt();
  final year = n(1);
  final month = n(2);
  if (year < 1 || month < 1 || month > 12) return null;
  // calendar.timegm: the day, hour, minute and second are not range-checked, they carry over
  final days = _daysFromCivil(year, month, 1) + n(3) - 1;
  var t = (((days * 24 + n(4)) * 60 + n(5)) * 60 + n(6)).toDouble();
  final frac = m[7];
  if (frac != null) {
    final digits = pyDecimalValue(frac)
        .toString()
        .padLeft(frac.runes.length, '0');
    t += double.parse('0.$digits');
  }
  final tz = m[8];
  if (tz != null && tz != 'Z' && tz != 'z') {
    final sign = tz[0] == '+' ? 1 : -1;
    final d = tz.substring(1).replaceAll(':', '');
    final hh = pyDecimalValue(d.substring(0, 2))!.toInt();
    final mm = pyDecimalValue(d.substring(2))!.toInt();
    t -= sign * (hh * 3600 + mm * 60);
  }
  return t;
}

/// Days from 1970-01-01 to the given proleptic Gregorian date.
int _daysFromCivil(int year, int month, int day) {
  final y = month <= 2 ? year - 1 : year;
  final era = (y >= 0 ? y : y - 399) ~/ 400;
  final yoe = y - era * 400;
  final doy = (153 * (month + (month > 2 ? -3 : 9)) + 2) ~/ 5 + day - 1;
  final doe = yoe * 365 + yoe ~/ 4 - yoe ~/ 100 + doy;
  return era * 146097 + doe - 719468;
}

/// `time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch))`.
String _formatIso(num epoch) {
  if (epoch is double && !epoch.isFinite) {
    throw _MaterialError('cfg.now is not a finite number');
  }
  final secs = epoch.floor();
  if (secs.abs() > 253402300799 + 86400) {
    throw _MaterialError('year out of range');
  }
  final rest = secs % 86400; // never negative in Dart
  final z = (secs - rest) ~/ 86400 + 719468;
  final era = (z >= 0 ? z : z - 146096) ~/ 146097;
  final doe = z - era * 146097;
  final yoe = (doe - doe ~/ 1460 + doe ~/ 36524 - doe ~/ 146096) ~/ 365;
  final doy = doe - (365 * yoe + yoe ~/ 4 - yoe ~/ 100);
  final mp = (5 * doy + 2) ~/ 153;
  final day = doy - (153 * mp + 2) ~/ 5 + 1;
  final month = mp < 10 ? mp + 3 : mp - 9;
  final year = yoe + era * 400 + (month <= 2 ? 1 : 0);
  if (year < 1 || year > 9999) throw _MaterialError('year out of range');
  String two(int v) => v.toString().padLeft(2, '0');
  return '${year.toString().padLeft(4, '0')}-${two(month)}-${two(day)}'
      'T${two(rest ~/ 3600)}:${two(rest % 3600 ~/ 60)}:${two(rest % 60)}Z';
}

class _Item {
  _Item(this.map, this.time, this.body);

  final Map<String, Object?> map;
  final double? time;
  final String body;

  /// Whether the reviewer's `ignore` pattern matches the body.
  bool ignored = false;
}

class _Evidence {
  _Evidence(this.time, this.fields);
  final double? time;
  final Map<String, Object?> fields;
}

/// `s[:300]`.
String _excerpt(Object? s) => prefixOf(_text(s), _maxExcerpt);

Map<String, Object?> _evaluateReviewer(
  _Reviewer rev,
  List<Object?> rawItems,
  List<Map<String, Object?>> checksAll,
  String head,
  double? cutoff,
  num now,
) {
  final report = rev.report;
  final ignore = report.containsKey('ignore')
      ? RegExp(report['ignore']!, unicode: true)
      : null;
  final shaRx = report.containsKey('sha_pattern')
      ? RegExp(report['sha_pattern']!, unicode: true)
      : null;
  final checkName = report['check'];
  final marker = report['marker'];
  final hasRule = _ruleKeys.any(report.containsKey);
  final headLower = head.toLowerCase();

  final prepared = <_Item>[];
  for (final i in rawItems) {
    if (_get(i, 'kind') == 'review' && _get(i, 'state') == 'PENDING') continue;
    final m = i as Map<String, Object?>;
    final item = _Item(
      m,
      _parseIso(_or(m['edited'], m['created'])),
      _text(m['body']),
    );
    item.ignored = ignore != null && ignore.hasMatch(item.body);
    prepared.add(item);
  }

  bool afterCutoff(_Item i) =>
      cutoff != null && i.time != null && i.time! >= cutoff;
  bool onHead(_Item i) => i.map['kind'] == 'review' && i.map['commit'] == head;

  final live = [
    for (final i in prepared)
      if (!i.ignored) i,
  ];
  final ownChecks = [
    for (final c in checksAll)
      if (checkName != null && _owns(rev, c)) c,
  ];

  String? by;
  if (live.any(onHead)) {
    by = 'review';
  } else if (!hasRule) {
    if (live.any(afterCutoff)) by = 'output';
  } else {
    if (shaRx != null &&
        live.any((i) => _shaMatches(shaRx, i.body, headLower))) {
      by = 'sha_pattern';
    } else if (checkName != null &&
        ownChecks.any((c) => c['state'] != 'pending')) {
      by = 'check';
    } else if (marker != null &&
        live.any((i) => i.body.contains(marker) && afterCutoff(i))) {
      by = 'marker';
    }
  }

  final String state;
  if (by != null) {
    state = 'reported';
  } else if (cutoff != null && now - cutoff >= rev.timeout) {
    state = 'timed_out';
  } else {
    state = 'waiting';
  }

  final evidence = <_Evidence>[
    for (final i in prepared)
      if (onHead(i) || afterCutoff(i))
        _Evidence(i.time, {
          'kind': i.map['kind'],
          'at': _or(i.map['edited'], i.map['created']),
          'state': i.map['state'],
          'excerpt': prefixOf(i.body, _maxExcerpt),
        }),
    for (final c in ownChecks)
      _Evidence(_parseIso(c['at']), {
        'kind': 'check',
        'at': c['at'],
        'state': c['state'],
        'excerpt': _excerpt(c['name']),
      }),
  ];
  // newest first; equal times (and every unknown time) keep their order, as a stable reverse sort does
  final order = List<int>.generate(evidence.length, (i) => i)
    ..sort((a, b) {
      final x = evidence[a].time ?? double.negativeInfinity;
      final y = evidence[b].time ?? double.negativeInfinity;
      final c = y.compareTo(x);
      return c != 0 ? c : a.compareTo(b);
    });
  return {
    'login': rev.login,
    'role': rev.role,
    'timeout': rev.timeout,
    'state': state,
    'by': by,
    'evidence': [for (final i in order.take(_maxEvidence)) evidence[i].fields],
  };
}

/// Whether check [c] is reviewer [rev]'s `report.check`: the exact name, from a check run of the reviewer's own GitHub
/// App (its slug equals the login, case-insensitively). A same-named check from another app, or a commit status (no
/// app), can be posted by anyone with access to the head, so it never stands for the reviewer.
bool _owns(_Reviewer rev, Map<String, Object?> c) {
  final name = rev.report['check'];
  final app = c['app'];
  return name != null &&
      c['name'] == name &&
      app is String &&
      app.toLowerCase() == rev.login.toLowerCase();
}

bool _shaMatches(RegExp rx, String body, String headLower) {
  for (final m in rx.allMatches(body)) {
    final g = m.group(1);
    if (g != null &&
        g.isNotEmpty &&
        _hexRe.hasMatch(g) &&
        headLower.startsWith(g.toLowerCase())) {
      return true;
    }
  }
  return false;
}

Map<String, Object?> _evaluate(
  Object? mat,
  List<_Reviewer> reviewers,
  String? digest,
  String head,
) {
  if (mat is! Map<String, Object?> || mat['head_oid'] != head) {
    throw _MaterialError("--head does not match the material's head_oid");
  }
  final cfg = _or(mat['cfg'], <String, Object?>{});
  final cutoff = _parseIso(_get(cfg, 'since'));
  final now = _get(cfg, 'now');
  if (now is bool || now is! num) {
    throw _MaterialError('cfg.now missing');
  }
  final nowNumber = now;
  final checksRaw = _or(mat['checks_all'], <Object?>[]);
  if (checksRaw is! List<Object?>) {
    throw _MaterialError(
      "'${_typeName(checksRaw)}' object is not a list of checks",
    );
  }
  final checksAll = [
    for (final c in checksRaw)
      if (c is Map<String, Object?>)
        c
      else
        throw _MaterialError("'${_typeName(c)}' object has no attribute 'get'"),
  ];
  final material = _or(mat['material'], <String, Object?>{});

  final results = <Map<String, Object?>>[];
  for (final r in reviewers) {
    final mine = _get(material, r.login);
    if (_truthy(mine) && mine is! List<Object?>) {
      throw _MaterialError(
        "'${_typeName(mine)}' object is not a list of items",
      );
    }
    results.add(
      _evaluateReviewer(
        r,
        _truthy(mine) ? List<Object?>.of(mine as List<Object?>) : const [],
        checksAll,
        head,
        cutoff,
        nowNumber,
      ),
    );
  }
  final stateOf = {
    for (var i = 0; i < reviewers.length; i++)
      reviewers[i].login: results[i]['state'],
  };

  final pending = [
    for (final c in checksAll)
      if (c['state'] == 'pending') c,
  ];
  var advisory = 0;
  var ci = 0;
  for (final c in pending) {
    final own = [
      for (final r in reviewers)
        if (_owns(r, c)) r,
    ];
    if (own.isEmpty) {
      ci++;
    } else if (own.every(
      (r) =>
          r.role == 'advisory' &&
          (stateOf[r.login] == 'reported' || stateOf[r.login] == 'timed_out'),
    )) {
      advisory++;
    }
  }

  Map<String, Object?> counts() => {
    'pending': pending.length - advisory,
    'advisory_pending': advisory,
    'ci_pending': ci,
  };
  final out = <String, Object?>{};
  for (final MapEntry(:key, :value) in mat.entries) {
    if (_removed.contains(key)) continue;
    var v = value;
    if (key == 'checks' && v is Map<String, Object?>) {
      final checks = <String, Object?>{};
      final base = {
        for (final e in v.entries)
          if (e.key != 'pending' &&
              e.key != 'advisory_pending' &&
              e.key != 'ci_pending')
            e.key: e.value,
      };
      if (!base.containsKey('total')) checks.addAll(counts());
      for (final e in base.entries) {
        checks[e.key] = e.value;
        if (e.key == 'total') checks.addAll(counts());
      }
      v = checks;
    }
    out[key] = v;
  }
  if (!out.containsKey('checks')) out['checks'] = counts();
  out['reviewers'] = results;
  out['now'] = _formatIso(nowNumber);
  out['reviewer_config'] = digest;
  final joined = [for (final x in results) '${x['login']}:${x['state']}']
      .join(',');
  for (final field in const ['sig', 'attn']) {
    final base = _or(mat['${field}_base'], '');
    out[field] = base64.encode(_utf8Strict('${pyStr(base)}|$joined'));
  }
  return out;
}

// ------------------------------------------------------------------- output

/// `text.encode("utf-8", "replace")`: a lone surrogate becomes `?`.
Uint8List _utf8Replace(String text) => Uint8List.fromList(
  utf8.encode(String.fromCharCodes(_loneSurrogatesTo(text, 0x3f))),
);

/// `text.encode("utf-8")`: a lone surrogate is an error.
Uint8List _utf8Strict(String text) {
  final replaced = _loneSurrogatesTo(text, -1);
  if (replaced.contains(-1)) {
    throw _MaterialError("'utf-8' codec can't encode a lone surrogate");
  }
  return Uint8List.fromList(utf8.encode(text));
}

List<int> _loneSurrogatesTo(String text, int replacement) {
  final units = text.codeUnits;
  final out = <int>[];
  for (var i = 0; i < units.length; i++) {
    final u = units[i];
    if (u >= 0xd800 && u <= 0xdbff) {
      if (i + 1 < units.length &&
          units[i + 1] >= 0xdc00 &&
          units[i + 1] <= 0xdfff) {
        out
          ..add(u)
          ..add(units[i + 1]);
        i++;
      } else {
        out.add(replacement);
      }
    } else if (u >= 0xdc00 && u <= 0xdfff) {
      out.add(replacement);
    } else {
      out.add(u);
    }
  }
  return out;
}
