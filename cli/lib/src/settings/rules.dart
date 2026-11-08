import 'dart:io';

import '../commit/task_cover.dart' show isPySpace, pyStrip;
import 'yaml.dart';

// The setting rules of `pr-pair.sh`: `duration`, `settle_of`, `reviewers_of`, `merge_mode`, `merge_options`, `repo_ctx`
// and `contexts` (pr-pair.sh:788-797, 861-912, 952-1028), plus the reads of the `vcs` and `tier` subcommands
// (pr-pair.sh:1252-1291). They are pure: git results (the detected main branch) come in as a callback, and a problem
// the settings get wrong is collected in a list the caller passes. Every JSON field is the script's, in its order
// (design D11); message text after a fixed prefix is ours.

/// The most reviewers one set may hold; more is `too_many_reviewers` (reported only: the whole set is still read).
const int maxReviewers = 20;

/// A problem with a setting, reported as `{error, key, why}` and as `key: why` in `settings_problem`.
class SettingProblem {
  SettingProblem(this.key, this.why, [this.error = 'bad_setting']);

  final String error;
  final String key;
  final String why;

  Map<String, Object?> toJson() => {'error': error, 'key': key, 'why': why};

  /// `problem_text`.
  String get text => '$key: $why';
}

/// A stop of the settings rules: the script's `Stop(error, message, code=...)`.
class SettingsStop implements Exception {
  SettingsStop(this.error, this.message, {this.code = 1});

  final String error;
  final String message;
  final int code;

  @override
  String toString() => '$error: $message';
}

/// One reviewer of a set, as `reviewers_of` reads it. [timeout] is an integer, or the boolean a `timeout: yes` reads as
/// (Python's `bool` is an `int`).
class Reviewer {
  Reviewer(this.role, this.timeout, this.request, this.report);

  final String role;
  final Object timeout;
  final String request;
  final Map<String, String> report;

  /// `{role, timeout, request, report}`, the order the script writes.
  Map<String, Object?> toJson() => {
    'role': role,
    'timeout': timeout,
    'request': request,
    'report': report,
  };
}

Map<String, Object?> _map(Object? v) => v is Map<String, Object?>
    ? v
    : v is Map
    ? v.cast<String, Object?>()
    : const <String, Object?>{};

/// `str(v or fallback)`.
String _strOr(Object? v, [String fallback = '']) =>
    pyTruthy(v) ? pyStr(v) : fallback;

const Map<String, int> _unit = {'': 1, 's': 1, 'm': 60, 'h': 3600};

bool _isDigit(int rune) => pyDecimalValue(String.fromCharCode(rune)) != null;

/// `duration`: an integer is itself (a boolean too), `<int>[s|m|h]` after strip with Python's `\d` and `\s` is that
/// many seconds, and anything else, unset and empty included, is [fallback]. The result is an `int`, a [BigInt] past
/// 64 bits, or a `bool`.
Object duration(Object? v, Object fallback) {
  if (v == null || v == '') return fallback;
  if (v is int || v is BigInt || v is bool) return v;
  if (v is! String) return fallback; // str() of a list or map never matches
  final runes = pyStrip(v).runes.toList();
  var i = 0;
  while (i < runes.length && _isDigit(runes[i])) {
    i++;
  }
  if (i == 0) return fallback;
  final number = pyDecimalValue(String.fromCharCodes(runes.sublist(0, i)))!;
  while (i < runes.length && isPySpace(runes[i])) {
    i++;
  }
  var suffix = '';
  if (i < runes.length &&
      (runes[i] == 0x73 || runes[i] == 0x6d || runes[i] == 0x68)) {
    suffix = String.fromCharCode(runes[i]);
    i++;
  }
  if (i != runes.length) return fallback;
  return pyIntNormal(number * BigInt.from(_unit[suffix]!));
}

/// `settle_of`: `pr.settle` strictly `<int><s|m|h>`, 1m to 1h. Unset is 300. A bad value is 300 and a problem.
({int seconds, SettingProblem? problem}) settleOf(Map<String, Object?> pr) {
  final v = pr['settle'];
  if (v == null || v == '') return (seconds: 300, problem: null);
  final m = v is String ? RegExp(r'^([0-9]+)([smh])$').firstMatch(v) : null;
  if (m != null) {
    final seconds = BigInt.parse(m.group(1)!) * BigInt.from(_unit[m.group(2)]!);
    if (seconds >= BigInt.from(60) && seconds <= BigInt.from(3600)) {
      return (seconds: seconds.toInt(), problem: null);
    }
  }
  return (
    seconds: 300,
    problem: SettingProblem(
      'pr.settle',
      '${settingText(pr, 'settle')} must be a duration of 1m to 1h written as <number>s, <number>m or <number>h',
    ),
  );
}

/// `report_of`: a reviewer's `report` as a map of strings, and why it is not one. Unknown keys stay as read: the
/// snapshot's evaluator validates keys and patterns.
(Map<String, String>, String?) _reportOf(Object? v) {
  if (v == null || v == '') return (<String, String>{}, null);
  if (v is! Map) {
    return (<String, String>{}, 'must be a mapping of keys to strings');
  }
  for (final e in v.entries) {
    if (e.value is! String) {
      return (
        <String, String>{},
        '${pyStr(e.key)} must be a string (quote it if it looks like a number or a boolean)',
      );
    }
  }
  return ({for (final e in v.entries) pyStr(e.key): e.value as String}, null);
}

/// `re.sub(r"\[bot\]$", "", login)`: Python's `$` also matches before a final newline.
String stripBot(String login) {
  if (login.endsWith('[bot]')) return login.substring(0, login.length - 5);
  if (login.endsWith('[bot]\n')) {
    return '${login.substring(0, login.length - 6)}\n';
  }
  return login;
}

/// `reviewers_of`: the reviewer set of a settings map, by login with a trailing `[bot]` dropped. A set or a `report` the
/// settings get wrong is appended to [problems] (when given); a set over [maxReviewers] is still read whole.
Map<String, Reviewer> reviewersOf(
  Object? raw, {
  List<SettingProblem>? problems,
  String where = 'pr.reviewers',
}) {
  final out = <String, Reviewer>{};
  if (problems != null && raw is Map && raw.length > maxReviewers) {
    problems.add(
      SettingProblem(
        where,
        '${raw.length} reviewers is too_many_reviewers (at most $maxReviewers)',
        'too_many_reviewers',
      ),
    );
  }
  if (raw is! Map) return out;
  for (final e in raw.entries) {
    final cfg = _map(e.value);
    final name = stripBot(pyStr(e.key));
    final (report, why) = _reportOf(cfg['report']);
    if (why != null && problems != null) {
      problems.add(SettingProblem('$where.$name.report', why));
    }
    out[name] = Reviewer(
      _strOr(cfg['role'], 'required'),
      duration(cfg['timeout'], 1200),
      _strOr(cfg['request']),
      report,
    );
  }
  return out;
}

/// `merge_mode`: `pr.merge` as the policy reads it. Anything else is `user`, with a note naming the value as written.
({String mode, String? note}) mergeMode(Map<String, Object?> pr) {
  final merge = pr['merge'];
  String? note;
  if (merge != null && merge != '' && merge != 'user' && merge != 'agent') {
    note =
        'pr.merge: ${settingText(pr, 'merge')} is not user or agent; treated as user';
  }
  return (mode: merge == 'agent' ? 'agent' : 'user', note: note);
}

/// `merge_options`: `pr.merge_method` and `pr.delete_branch` with their defaults; a bad value is exit 2 `bad_setting`.
({String method, bool deleteBranch}) mergeOptions(Map<String, Object?> pr) {
  final Object method = pr['merge_method'] ?? 'merge';
  if (method != 'merge' && method != 'squash' && method != 'rebase') {
    throw SettingsStop(
      'bad_setting',
      'pr.merge_method: ${settingText(pr, 'merge_method')} must be merge, squash or rebase',
      code: 2,
    );
  }
  final Object delete = pr['delete_branch'] ?? true;
  if (delete is! bool) {
    throw SettingsStop(
      'bad_setting',
      'pr.delete_branch: ${settingText(pr, 'delete_branch')} must be true or false',
      code: 2,
    );
  }
  return (method: method as String, deleteBranch: delete);
}

/// The `github.review_request` part of a repo context.
class ReviewRequest {
  ReviewRequest(this.body, this.login, this.afterFixes);

  final String body;
  final String login;
  final bool afterFixes;

  Map<String, Object?> toJson() => {
    'body': body,
    'login': login,
    'after_fixes': afterFixes,
  };
}

/// One repo's context, as `repo_ctx` builds it.
class RepoContext {
  RepoContext({
    required this.dir,
    required this.reviewRequest,
    required this.requestAs,
    required this.login,
    required this.main,
    required this.validate,
    required this.reviewers,
    required this.requestsDisabled,
    required this.mergeReady,
    required this.mergeReason,
  });

  final String dir;
  final ReviewRequest reviewRequest;
  final String requestAs;
  final String login;
  final String main;
  final String validate;
  final Map<String, Reviewer> reviewers;
  final bool requestsDisabled;
  final bool mergeReady;

  /// `no_required_reviewer`, or null when ready.
  final String? mergeReason;

  /// The fields in the script's order. The `context` command adds `repo` and `reviewer_config` after them.
  Map<String, Object?> toJson() => {
    'dir': dir,
    'review_request': reviewRequest.toJson(),
    'request_as': requestAs,
    'login': login,
    'main': main,
    'validate': validate,
    'reviewers': {for (final e in reviewers.entries) e.key: e.value.toJson()},
    'requests_disabled': requestsDisabled,
    'merge_ready': mergeReady,
    'merge_reason': mergeReason,
  };
}

/// `repo_ctx`: the context of the code repo (`which` is `code`) or the store (`store`) in [dir]. [detectMain] answers
/// the repo's main branch name (a git lookup) and is asked only when the settings do not name one.
RepoContext repoContext(
  Map<String, Object?> s,
  String dir,
  String which, {
  required String Function(String dir) detectMain,
  List<SettingProblem>? problems,
}) {
  final g = _map(s['github']);
  final pr = _map(s['pr']);
  final ps = _map(s['planning_store']);
  final rr = _map(g['review_request']);
  final String login;
  final String main;
  final String validate;
  final Map<String, Reviewer> reviewers;
  final bool disabled;
  if (which == 'store') {
    login = _strOr(ps['login'], _strOr(g['login']));
    main = pyTruthy(ps['main_branch'])
        ? pyStr(ps['main_branch'])
        : detectMain(dir);
    validate = _strOr(ps['validate']);
    final own = ps['reviewers'];
    reviewers = own is Map
        ? reviewersOf(
            own,
            problems: problems,
            where: 'planning_store.reviewers',
          )
        : reviewersOf(pr['reviewers'], problems: problems);
    disabled = own is Map && own.isEmpty;
  } else {
    login = _strOr(g['login']);
    main = pyTruthy(s['main_branch'])
        ? pyStr(s['main_branch'])
        : detectMain(dir);
    validate = _strOr(pr['validate']);
    reviewers = reviewersOf(pr['reviewers'], problems: problems);
    disabled = false;
  }
  final ready = reviewers.values.any((r) => r.role == 'required');
  return RepoContext(
    dir: dir.replaceAll(r'\', '/'),
    reviewRequest: ReviewRequest(
      _strOr(rr['body']),
      _strOr(rr['login']),
      pyTruthy(rr['after_fixes']),
    ),
    requestAs: _strOr(pr['request_as']),
    login: login,
    main: main,
    validate: validate,
    reviewers: reviewers,
    requestsDisabled: disabled,
    mergeReady: ready,
    mergeReason: ready ? null : 'no_required_reviewer',
  );
}

/// Both repos' contexts and the pair-wide settings, as `contexts` builds them.
class Contexts {
  Contexts({
    required this.code,
    required this.store,
    required this.finish,
    required this.maxFixRounds,
    required this.afterLimit,
    required this.react,
    required this.pollInterval,
    required this.settle,
    required this.merge,
    required this.mergeNote,
    required this.mergeMethod,
    required this.deleteBranch,
  });

  final RepoContext code;
  final RepoContext? store;
  final String finish;

  /// `int()` of an integer setting (a boolean reads as 1 or 0), else 2: an `int` or a [BigInt].
  final Object maxFixRounds;
  final String afterLimit;
  final bool react;
  final Object pollInterval;
  final int settle;
  final String merge;
  final String? mergeNote;
  final String mergeMethod;
  final bool deleteBranch;

  /// The fields in the script's order (`merge_note` only when there is one).
  Map<String, Object?> toJson() => {
    'code': code.toJson(),
    'store': store?.toJson(),
    'finish': finish,
    'max_fix_rounds': maxFixRounds,
    'after_limit': afterLimit,
    'react': react,
    'poll_interval': pollInterval,
    'settle': settle,
    'merge': merge,
    if (mergeNote != null) 'merge_note': mergeNote,
    'merge_method': mergeMethod,
    'delete_branch': deleteBranch,
  };
}

/// `contexts`: [s] is the settings map. [problems] collects what the settings get wrong in `pr.settle` and the
/// reviewer sets. With [checkMerge] and `pr.merge: agent`, a bad `merge_method` or `delete_branch` throws
/// [SettingsStop] (`bad_setting`, exit 2).
Contexts contexts(
  Map<String, Object?> s,
  String code,
  String? store, {
  required String Function(String dir) detectMain,
  bool checkMerge = true,
  List<SettingProblem>? problems,
}) {
  final pr = _map(s['pr']);
  final settle = settleOf(pr);
  if (settle.problem != null) problems?.add(settle.problem!);
  final codeContext = repoContext(
    s,
    code,
    'code',
    detectMain: detectMain,
    problems: problems,
  );
  final storeContext = store != null && store.isNotEmpty
      ? repoContext(
          s,
          store,
          'store',
          detectMain: detectMain,
          problems: problems,
        )
      : null;
  final rounds = pr['max_fix_rounds'];
  final merge = mergeMode(pr);
  var method = 'merge';
  var delete = true;
  if (merge.mode == 'agent' && checkMerge) {
    final o = mergeOptions(pr);
    method = o.method;
    delete = o.deleteBranch;
  }
  return Contexts(
    code: codeContext,
    store: storeContext,
    finish: _strOr(s['finish']),
    maxFixRounds: rounds is bool
        ? (rounds ? 1 : 0)
        : (rounds is int || rounds is BigInt ? rounds! : 2),
    afterLimit: _strOr(pr['after_limit'], 'ask'),
    react: pyTruthy(pr['react']),
    pollInterval: duration(pr['poll_interval'], 300),
    settle: settle.seconds,
    merge: merge.mode,
    mergeNote: merge.note,
    mergeMethod: method,
    deleteBranch: delete,
  );
}

/// The backends the `vcs` subcommand reads (`cmd_vcs`): the code repo's and the store's. A value the script refuses
/// throws [SettingsStop] with its error (`unknown_vcs`, `unsupported_vcs`, `unsupported_combination`).
({String code, String store}) vcsChoices(Map<String, Object?> s) {
  final store = _map(s['planning_store']);

  String selected(
    Map<String, Object?> section,
    String name,
    List<String> accepted,
  ) {
    final value = section['vcs'];
    if (value == null) return 'git';
    if (value is! String || !accepted.contains(value)) {
      throw SettingsStop(
        'unknown_vcs',
        'unknown $name VCS ${pyRepr(value)}; accepted values: ${accepted.join(', ')}',
      );
    }
    return value;
  }

  final code = selected(s, 'code', ['git', 'jj', 'gitbutler']);
  if (store['vcs'] == 'gitbutler') {
    throw SettingsStop(
      'unsupported_vcs',
      'planning_store.vcs: gitbutler is not supported; a store accepts git or jj',
    );
  }
  final storeChoice = selected(store, 'planning_store', ['git', 'jj']);
  if (code == 'gitbutler' && s['finish'] != 'pr') {
    final finish = s['finish'] != null
        ? settingText(s, 'finish')
        : 'absent, which counts as local';
    throw SettingsStop(
      'unsupported_combination',
      'vcs: gitbutler runs only with finish: pr (finish is $finish)',
    );
  }
  return (code: code, store: storeChoice);
}

/// `cmd_tier`: `{ok, cheap_tier}` and a `note` when `cheap_tier` is not a mapping holding `enabled: true|false`.
Map<String, Object?> tierChoice(Map<String, Object?> s) {
  final out = <String, Object?>{'ok': true, 'cheap_tier': false};
  final section = s['cheap_tier'];
  if (section == null) return out;
  if (section is! Map) {
    out['note'] = 'cheap_tier must hold enabled: true|false; treated as false';
    return out;
  }
  final v = section['enabled'];
  if (v == true) {
    out['cheap_tier'] = true;
  } else if (v != false && v != null) {
    out['note'] =
        'cheap_tier.enabled: ${settingText(section, 'enabled')} is not true or false; treated as false';
  }
  return out;
}

/// `settings_text`: the text of `openspec/specwright.yaml` under the first of [bases] that holds the file (the work
/// tree directory, then its top level), or null when none does. UTF-8 with U+FFFD for bad bytes and Python's
/// text-mode newlines (`\r\n` and `\r` read as `\n`), a byte-order mark kept.
String? readSettingsText(Iterable<String> bases) {
  for (final base in bases) {
    final f = File('$base/openspec/specwright.yaml');
    if (f.existsSync()) {
      return pyUtf8Decode(f.readAsBytesSync())
          .replaceAll('\r\n', '\n')
          .replaceAll('\r', '\n');
    }
  }
  return null;
}

/// `load_settings` for the text `readSettingsText` gave: the lenient read, or an empty map when there is no file.
Map<String, Object?> loadSettings(String? text) =>
    text == null ? YamlMap() : parseYaml(text);
