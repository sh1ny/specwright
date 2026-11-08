import 'dart:convert';
import 'dart:typed_data';

import '../commit/task_cover.dart' show isPySpace, pyStrip;
import '../settings/pyjson.dart';
import '../settings/reviewer_config.dart';
import '../settings/rules.dart';
import '../settings/yaml.dart';
import '../vcs/codec.dart';
import '../vcs/document.dart';
import 'context.dart';
import 'gh.dart';
import 'pair.dart';

// `sw pr policy`: `pr-pair.sh policy` (pr-pair.sh:2732-2914). The merge policy as the default branch holds it, read
// from GitHub and never from the work tree (ADR 0020), with the head's copy compared for drift, and whether each
// repository's snapshot reports its required reviewers under the rules of that set. The reads are strict (design D7, C3):
// a file that cannot be read whole is `lookup_failed`, exit 3, never a best-effort parse. Every JSON field, error code and
// exit status is the script's; message text after `merge policy unknown:` is ours (D11).

/// `policy_unknown`.
Never _unknown(String reason) => throw PairStop(
  'lookup_failed',
  'merge policy unknown: $reason',
  code: 3,
  extra: {'unknown': true},
);

/// The contents of one `gh api` read that was refused: the reason the script's `ValueError` gave.
class _Unreadable implements Exception {
  _Unreadable(this.why);

  final String why;

  @override
  String toString() => why;
}

/// `quote(ref, safe='')`: everything but letters, digits and `_.-~` as percent-escaped UTF-8.
String _quote(String ref) {
  final out = StringBuffer();
  for (final b in utf8.encode(ref)) {
    final c = String.fromCharCode(b);
    if (b < 0x80 && RegExp(r'[A-Za-z0-9_.\-~]').hasMatch(c)) {
      out.write(c);
    } else {
      out.write('%${b.toRadixString(16).toUpperCase().padLeft(2, '0')}');
    }
  }
  return out.toString();
}

/// `http_status`.
int? _httpStatus(GhResult r) {
  final m = RegExp(r'\(HTTP (\d{3})\)').firstMatch(decodeReplacing(r.stderr));
  return m == null ? null : int.parse(m.group(1)!);
}

/// `reply_message`: gh's own `message`, else what it printed, else its exit status.
String _replyMessage(GhResult r) {
  final stdout = decodeReplacing(r.stdout);
  Object? message = '';
  try {
    final body = pyJsonDecode(stdout);
    if (body is Map && pyTruthy(body['message'])) message = body['message'];
  } on FormatException {
    message = '';
  }
  if (pyTruthy(message)) return pyStr(message);
  final stderr = decodeReplacing(r.stderr);
  final said = pyStrip(stderr.isNotEmpty ? stderr : stdout);
  return said.isNotEmpty ? said : 'gh exited ${r.exitCode}';
}

/// `policy_gh`: one `gh` read, with `sw`'s environment minus `GH_REPO`. A failure or a limit is unknown, a 404 is null.
Future<String?> _policyGh(PrContext ctx, List<String> args) async {
  final r = await ctx.gh(args, environment: {...ctx.env}..remove('GH_REPO'));
  if (r.limit != null) _unknown('${r.limit!.label}: gh ${args.first}');
  if (r.exitCode != 0) {
    if (_httpStatus(r) == 404) return null;
    _unknown(_replyMessage(r));
  }
  return decodeReplacing(r.stdout);
}

final RegExp _b64Alphabet = RegExp(r'^[A-Za-z0-9+/]*={0,2}$');

/// `base64.b64decode(text, validate=True)`: ASCII only, the standard alphabet, and the padding that completes the last
/// group. Dart's own decoder takes URL-safe characters and missing padding (D7).
Uint8List _strictBase64(String text) {
  if (text.codeUnits.any((u) => u > 0x7f)) {
    throw _Unreadable('string argument should contain only ASCII characters');
  }
  if (!_b64Alphabet.hasMatch(text)) {
    throw _Unreadable('Non-base64 digit found');
  }
  final pad = text.length - text.replaceAll('=', '').length;
  final data = text.length - pad;
  final ok = switch (data % 4) {
    0 => pad == 0,
    2 => pad == 2,
    3 => pad == 1,
    _ => false,
  };
  if (!ok) throw _Unreadable('Incorrect padding');
  const alphabet =
      'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
  final out = BytesBuilder();
  var acc = 0;
  var bits = 0;
  for (var i = 0; i < data; i++) {
    acc = (acc << 6) | alphabet.indexOf(text[i]);
    bits += 6;
    if (bits >= 8) {
      bits -= 8;
      out.addByte((acc >> bits) & 0xff);
      acc &= (1 << bits) - 1;
    }
  }
  return out.takeBytes();
}

/// `bytes.decode('utf-8-sig')`: one leading byte-order mark dropped, and bytes that are not UTF-8 refused.
String _utf8Sig(Uint8List bytes) {
  bool bomAt(int i) =>
      bytes.length >= i + 3 &&
      bytes[i] == 0xef &&
      bytes[i + 1] == 0xbb &&
      bytes[i + 2] == 0xbf;
  final start = bomAt(0) ? 3 : 0;
  // Dart's decoder drops a leading mark itself: a second one is put back, as Python keeps it as U+FEFF
  final second = bomAt(start);
  try {
    final text = utf8.decode(bytes.sublist(start + (second ? 3 : 0)));
    return second ? '${String.fromCharCode(0xfeff)}$text' : text;
  } on FormatException catch (e) {
    throw _Unreadable('not valid UTF-8: ${e.message}');
  }
}

/// `policy_file`: the settings at [ref] from the contents API, or null when the file is not there (404).
Future<Map<String, Object?>?> _policyFile(
  PrContext ctx,
  String repo,
  String ref,
) async {
  final out = await _policyGh(ctx, [
    'api',
    'repos/$repo/contents/openspec/specwright.yaml?ref=${_quote(ref)}',
  ]);
  if (out == null) return null;
  try {
    final body = pyJsonDecode(out);
    if (body is! Map ||
        body['type'] != 'file' ||
        body['encoding'] != 'base64') {
      throw _Unreadable('not a base64 file');
    }
    final content = body.containsKey('content') ? body['content'] : '';
    final compact = String.fromCharCodes(
      pyStr(content).codeUnits.where((u) => !isPySpace(u)),
    );
    final text = _utf8Sig(_strictBase64(compact));
    final why = yamlProblem(text);
    if (why != null) throw _Unreadable(why);
    return parseYaml(text);
  } on FormatException catch (e) {
    _unknown('unreadable openspec/specwright.yaml at $ref: ${e.message}');
  } on _Unreadable catch (e) {
    _unknown('unreadable openspec/specwright.yaml at $ref: ${e.why}');
  }
}

Map<String, Object?> _section(Map<String, Object?> src, String name) {
  final v = src[name];
  return v is Map<String, Object?>
      ? v
      : v is Map
      ? v.cast<String, Object?>()
      : const <String, Object?>{};
}

Map<String, Object?> _reviewersJson(Map<String, Reviewer> set) => {
  for (final e in set.entries) e.key: e.value.toJson(),
};

/// The policy keys of one settings file (`policy_side`), normalized so only a real difference compares unequal.
class _Side {
  _Side(this.values, this.note, this.pr, this.invalid, this.problems);

  /// The setting names to their values, in the script's order.
  final Map<String, Object?> values;
  final String? note;
  final Map<String, Object?> pr;
  final List<Map<String, Object?>> invalid;
  final List<SettingProblem> problems;

  late final Map<String, Reviewer> codeSet;

  /// `planning_store.reviewers` when the file names its own set, else null (the store inherits `pr.reviewers`).
  Map<String, Reviewer>? storeSet;
}

_Side _policySide(Map<String, Object?> s, bool withStore) {
  final pr = _section(s, 'pr');
  final merge = mergeMode(pr);
  final method = pr['merge_method'];
  final delete = pr['delete_branch'];
  Object? raw = pr['reviewers'];
  final invalid = <Map<String, Object?>>[];
  final problems = <SettingProblem>[];
  if (raw != null && raw is! Map) {
    // a string or a list: no reviewers, so it authorizes nothing
    invalid.add({'key': 'pr.reviewers', 'value': settingText(pr, 'reviewers')});
    raw = null;
  }
  final codeSet = reviewersOf(raw, problems: problems);
  final values = <String, Object?>{
    'pr.merge': merge.mode,
    'pr.merge_method': method ?? 'merge',
    'pr.delete_branch': delete ?? true,
    'pr.reviewers': _reviewersJson(codeSet),
    // seconds; a bad value counts as the default, and main's stops `policy`
    'pr.settle': settleOf(pr).seconds,
  };
  Map<String, Reviewer>? storeSet;
  if (withStore) {
    final own = _section(s, 'planning_store')['reviewers'];
    storeSet = own is Map
        ? reviewersOf(
            own,
            problems: problems,
            where: 'planning_store.reviewers',
          )
        : null;
    values['planning_store.reviewers'] = storeSet == null
        ? null
        : _reviewersJson(storeSet);
  }
  return _Side(values, merge.note, pr, invalid, problems)
    ..codeSet = codeSet
    ..storeSet = storeSet;
}

/// `json.dumps(v, sort_keys=True)`'s view of a value, so two settings compare equal by type as well as value: Python has
/// 1 == True, but `delete_branch: 1` is not `true`.
Object? _canonical(Object? v) {
  if (v is Map) {
    final keys = v.keys.cast<String>().toList()..sort(compareCodePoints);
    return {for (final k in keys) k: _canonical(v[k])};
  }
  if (v is List) return [for (final e in v) _canonical(e)];
  return v;
}

bool _sameSetting(Object? a, Object? b) =>
    documentText(_canonical(a)) == documentText(_canonical(b));

bool _hasRequired(Map<String, Reviewer> set) =>
    set.values.any((r) => r.role == 'required');

final RegExp _commit = RegExp(r'^[0-9a-f]{7,40}$');

/// `same_commit`: two commit ids are the same when equal, or when one (7 to 40 hex digits) is a prefix of the other.
bool _sameCommit(Object? a, Object? b) {
  final x = pyStr(pyTruthy(a) ? a : '').toLowerCase();
  final y = pyStr(pyTruthy(b) ? b : '').toLowerCase();
  return _commit.hasMatch(x) &&
      _commit.hasMatch(y) &&
      (x.startsWith(y) || y.startsWith(x));
}

/// `reported_check`: whether the snapshot is of the reviewed head, ran with the rules of this set (its `reviewer_config`
/// digest equals the set's) and every required reviewer of the set reported in it. A set with no required reviewer
/// authorizes nothing: not ok.
Map<String, Object?> _reportedCheck(
  Object? snapshot,
  String reviewed,
  Map<String, Reviewer> reviewers,
  String digest,
) {
  final map = snapshot is Map ? snapshot : null;
  final got = map?['head_oid'];
  final mismatch = !_sameCommit(got, reviewed);
  final state = <String, bool>{};
  final listed = map?['reviewers'];
  if (pyTruthy(listed)) {
    if (listed is! Map && listed is! List && listed is! String) {
      throw ArgumentError("'${listed.runtimeType}' object is not iterable");
    }
    for (final r in listed is List ? listed : const []) {
      if (r is Map && r['login'] is String) {
        final login = stripBot(r['login'] as String).toLowerCase();
        state[login] = (state[login] ?? false) || r['state'] == 'reported';
      }
    }
  }
  final required = [
    for (final e in reviewers.entries)
      if (e.value.role == 'required') e.key,
  ];
  final missing = [
    for (final l in required)
      if (!(state[l.toLowerCase()] ?? false)) l,
  ];
  final rules = !(map != null && map['reviewer_config'] == digest);
  return {
    'ok': required.isNotEmpty && missing.isEmpty && !mismatch && !rules,
    'missing': missing,
    'head_mismatch': mismatch,
    'rules_mismatch': rules,
    'snapshot_head': got,
    'reviewed_head': reviewed,
  };
}

final RegExp _hex = RegExp(r'^[0-9a-fA-F]{7,40}$');

/// `read_snapshots`: the `--snapshot code=<file>` and `store=<file>` arguments, each a JSON document.
Future<Map<String, Object?>> _readSnapshots(PrContext ctx, PairArgs a) async {
  final out = <String, Object?>{};
  for (final spec in a.lists['snapshot'] ?? const <String>[]) {
    final eq = spec.indexOf('=');
    final name = eq < 0 ? spec : spec.substring(0, eq);
    final path = eq < 0 ? '' : spec.substring(eq + 1);
    if ((name != 'code' && name != 'store') || path.isEmpty) {
      pairUsage('--snapshot is code=<file> or store=<file>');
    }
    try {
      out[name] = pyJsonReadFile(await ctx.native(path));
    } on FormatException catch (e) {
      throw PairStop('snapshot_unreadable', e.message, code: 2);
    }
  }
  return out;
}

/// `cmd_policy`.
Future<int> runPolicy(
  PrContext ctx,
  List<String> argv,
) => runPairCommand(ctx, () async {
  final withStore = argv.contains('--store');
  final a = parsePairArgs(
    [
      for (final t in argv)
        if (t != '--store') t,
    ],
    const {
      '--repo': 'repo',
      '--head': 'head',
      '--snapshot': '+snapshot',
      '--reviewed-head': '+reviewed',
    },
  );
  needArgs(a, ['repo', 'head']);
  final repo = a['repo']!;
  final head = a['head']!;
  if (!_hex.hasMatch(head)) {
    pairUsage(
      '--head must be a commit id of 7 to 40 hex digits, got ${pyRepr(head)}',
    );
  }
  final reviewed = <String, String>{};
  for (final spec in a.lists['reviewed'] ?? const <String>[]) {
    final eq = spec.indexOf('=');
    final name = eq < 0 ? spec : spec.substring(0, eq);
    final sha = eq < 0 ? '' : spec.substring(eq + 1);
    if ((name != 'code' && name != 'store') || !_hex.hasMatch(sha)) {
      pairUsage(
        '--reviewed-head is code=<sha> or store=<sha> (7 to 40 hex digits)',
      );
    }
    reviewed[name] = sha;
  }
  reviewed.putIfAbsent('code', () => head);
  final sides = withStore ? ['code', 'store'] : ['code'];
  final snaps = await _readSnapshots(ctx, a);
  for (final side in sides) {
    if (!snaps.containsKey(side)) {
      pairUsage('missing --snapshot $side=<file>');
    }
  }
  if (withStore && !reviewed.containsKey('store')) {
    pairUsage('--store needs --reviewed-head store=<sha>');
  }
  if (!withStore &&
      (snaps.containsKey('store') || reviewed.containsKey('store'))) {
    pairUsage('--snapshot store= and --reviewed-head store= need --store');
  }

  final body = await _policyGh(ctx, ['api', 'repos/$repo']);
  final String defaultBranch;
  try {
    if (body == null) throw _Unreadable('no body');
    final doc = pyJsonDecode(body);
    final v = doc is Map ? doc['default_branch'] : null;
    if (v is! String || v.isEmpty) throw _Unreadable('no default branch');
    defaultBranch = v;
  } on FormatException {
    _unknown('cannot read the default branch of $repo');
  } on _Unreadable {
    _unknown('cannot read the default branch of $repo');
  }
  final mainSettings =
      await _policyFile(ctx, repo, defaultBranch) ?? <String, Object?>{};
  final headSettings = await _policyFile(ctx, repo, head);
  if (headSettings == null) {
    _unknown('no openspec/specwright.yaml readable at $head');
  }
  final main = _policySide(mainSettings, withStore);
  final headSide = _policySide(headSettings, withStore);
  // main's policy: a bad value stops here, a bad head value is only the head's
  final settleBad = settleOf(main.pr).problem;
  final bads = [?settleBad, ...main.problems];
  if (bads.isNotEmpty) {
    throw PairStop(bads.first.error, bads.first.text, code: 2);
  }
  final drift = [
    for (final k in main.values.keys)
      if (!_sameSetting(main.values[k], headSide.values[k]))
        {'key': k, 'main': main.values[k], 'head': headSide.values[k]},
  ];
  final invalid = <Map<String, Object?>>[
    for (final (who, bad) in [
      ('main', main.invalid),
      ('head', headSide.invalid),
    ])
      for (final b in bad) {'side': who, ...b},
    for (final b in headSide.problems)
      {
        'side': 'head',
        'key': b.key,
        'value': b.error == 'too_many_reviewers' ? b.error : b.why,
      },
  ];
  final out = <String, Object?>{
    'ok': true,
    'repo': repo,
    'default_branch': defaultBranch,
    'main': main.values,
    'head': headSide.values,
    'drift': drift,
    'invalid': invalid,
    'merge': main.values['pr.merge'],
    'merge_method': 'merge',
    'delete_branch': true,
    'settle': main.values['pr.settle'],
  };
  if (out['merge'] == 'agent') {
    // only the agent merge reads them, as context does; a bad value on main stops here
    try {
      final o = mergeOptions(main.pr);
      out['merge_method'] = o.method;
      out['delete_branch'] = o.deleteBranch;
    } on SettingsStop catch (e) {
      throw PairStop(e.error, e.message, code: e.code);
    }
  }
  final ready = <String, bool>{'code': _hasRequired(main.codeSet)};
  if (withStore) {
    final own = main.storeSet;
    ready['store'] = own == null ? ready['code']! : _hasRequired(own);
  }
  out['merge_ready'] = ready;
  final reported = <String, Object?>{};
  final configs = <String, Object?>{};
  out['reported'] = reported;
  out['reviewer_config'] = configs;
  for (final (which, side) in [('main', main), ('head', headSide)]) {
    final sets = <String, Map<String, Reviewer>>{'code': side.codeSet};
    if (withStore) sets['store'] = side.storeSet ?? side.codeSet;
    final reportedSide = reported[which] = <String, Object?>{};
    final configSide = configs[which] = <String, Object?>{};
    for (final e in sets.entries) {
      final written = writeReviewerConfig(e.value, environment: ctx.env);
      final big = written.problem;
      if (big != null && which == 'main') {
        throw PairStop('bad_setting', big.text, code: 2);
      }
      if (big != null) {
        invalid.add({'side': 'head', 'key': big.key, 'value': big.why});
      }
      configSide[e.key] = written.path;
      reportedSide[e.key] = _reportedCheck(
        snaps[e.key],
        reviewed[e.key]!,
        e.value,
        written.digest,
      );
    }
  }
  out['merge_reason'] = {
    for (final e in ready.entries)
      e.key: e.value ? null : 'no_required_reviewer',
  };
  if (main.note != null) out['merge_note'] = main.note;
  return out;
});
