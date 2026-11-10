import 'dart:async';
import 'dart:io';

import '../process/limit_line.dart';
import '../options.dart';
import '../process/limits.dart';
import '../vcs/codec.dart';
import '../vcs/document.dart';
import 'context.dart';
import 'gh.dart';
import 'queries.dart';
import 'reviewers.dart' show reviewerLogins;
import 'text.dart';
import 'watch_state.dart';

final RegExp _datePattern = RegExp(
  r'^[A-Za-z]{3}, [0-9]{2} [A-Za-z]{3} [0-9]{4} [0-9:]{8} GMT$',
);
final RegExp _pushPattern = RegExp(
  r'^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?Z$',
);

/// `sw pr snapshot`: `pr-snapshot.sh`, ported call for call (design D1, D6, D7, D8). [argv] is the script's own argument
/// list. The GraphQL and jq texts are the script's (`queries.dart`) and `gh` runs the jq; the text tools between the
/// calls are the Dart functions of `text.dart`.
///
/// Constraint C5: `mktemp`, `ln` and `sleep` run as external commands through bash, because the evals fake them on
/// `PATH`; the evaluator's material file comes from `mktemp` too, and `sw pr reviewers` runs through the bounded helper with
/// its limit named as the script named it. `native-cli-retire-scripts` replaces them together with those hooks. The poll's
/// deadline needs no `date`: the script's `date +%s` fallback covered a bounded helper that printed nothing usable.
///
/// The watch claim and the material file are removed on every exit, and on SIGINT, SIGTERM and SIGHUP where the platform
/// has them (the script's one `EXIT` trap). Exit codes: 0; 1 for any failed read, poll or log; 2 for a bad argument or
/// reviewer config; 3 when `--full` cannot read; 4 when a newer watcher took over.
Future<int> runSnapshot(PrContext ctx, List<String> argv) async {
  final snapshot = _Snapshot(ctx);
  final signals = cleanupOnSignals(snapshot.cleanup);
  try {
    return await snapshot.run(argv);
  } on PrExit catch (e) {
    return e.code;
  } finally {
    for (final s in signals) {
      await s.cancel();
    }
    snapshot.cleanup();
  }
}

class _Result {
  _Result(this.code, [this.out = '', this.doc]);

  final int code;
  final String out;

  /// [out] decoded, once, when it is the document a good poll ends with.
  final Map<String, Object?>? doc;
}

/// [text] as one JSON document with members, or null when it is anything else: not JSON, more than one value, an array or
/// a scalar (design D4, C12). The members are read from the map, never matched in the text.
Map<String, Object?>? _document(String text) {
  try {
    final value = decodeJson(text);
    return value is Map<String, Object?> ? value : null;
  } on JsonInputException {
    return null;
  }
}

String _stringOf(Object? value) => value is String ? value : '';

/// The strings of the list [value], those that match [only] when it is given.
List<String> _stringsOf(Object? value, [RegExp? only]) => [
  if (value is List)
    for (final e in value)
      if (e is String && (only == null || only.hasMatch(e))) e,
];

/// A GraphQL node id, one that can be put in a query text as it is.
final RegExp _nodeId = RegExp(r'^[A-Za-z0-9_=-]+$');
final RegExp _base64Name = RegExp(r'^[A-Za-z0-9+/=]+$');
final RegExp _hexOid = RegExp(r'^[0-9a-f]*$');

/// The head the material is of: `head_oid` of the PR query's line, or '' when it is not hex.
String _headOid(Map<String, Object?> doc) {
  final oid = _stringOf(doc['head_oid']);
  return _hexOid.hasMatch(oid) ? oid : '';
}

/// The ids whose reaction times the re-check reads, `recheck` of the PR query's line.
List<String> _recheckIds(Map<String, Object?> doc) =>
    _stringsOf(doc['recheck'], _nodeId);

/// The ids of the runs that failed, `fail_run_ids` of the evaluator's document.
List<String> _failRunIds(Map<String, Object?> doc) => [
  if (doc['fail_run_ids'] case final List<Object?> ids)
    for (final id in ids)
      if (id is int && id >= 0) '$id',
];

/// The names (base64) of the checks that fail, `fail_names` of the evaluator's document.
List<String> _failNames(Map<String, Object?> doc) =>
    _stringsOf(doc['fail_names'], _base64Name);

/// Does the evaluator's document count a CI check that is still pending?
bool _ciPending(Map<String, Object?> doc) {
  final checks = doc['checks'];
  if (checks is! Map<String, Object?>) return false;
  final pending = checks['ci_pending'];
  return pending is num && pending >= 1;
}

bool _incomplete(Map<String, Object?> doc) => doc['complete'] == false;

class _Snapshot {
  _Snapshot(this.ctx);

  final PrContext ctx;
  String pr = '';
  String repo = '';
  String full = '';
  bool logs = false;
  bool wait = false;
  String timeout = '1800';
  String interval = '300';
  String rcfg = '';
  bool rcfgSet = false;
  String until = '';
  String rcfgArg = '';
  String logins = '';
  String owner = '';
  String name = '';
  String? matFile;
  String? cfgCopy;
  WatchClaim? claim;

  // `prepare_cfg`'s state, kept across polls.
  String cfg = cfgDefault;
  String pushedOid = '';
  String pushedAt = '';
  String firstSeen = '';
  String seenSrc = '';
  String seenDate = '';

  /// The environment of a poll's calls: `SPECWRIGHT_NET_DEADLINE_AT` is set for the poll and unset right after.
  Map<String, String>? pollEnv;

  Never stop(String message, int code) {
    ctx.err('$message\n');
    throw PrExit(code);
  }

  /// `${n:?message}`.
  String need(String? value, int n, String message, int line) {
    if (value != null && value.isNotEmpty) return value;
    ctx.err('pr-snapshot.sh: line $line: $n: $message\n');
    throw PrExit(1);
  }

  void cleanup() {
    removeFile(matFile);
    matFile = null;
    removeFile(cfgCopy);
    cfgCopy = null;
    claim?.release();
  }

  /// [path], or a temp copy of its file when the name is not UTF-8. `sw pr reviewers` takes the path in its argv, and
  /// the Dart VM does not start on an argument that is not UTF-8, so such a name never reaches it. The copy holds the
  /// same bytes, so the digest is the same; it is removed with the material file. A file that cannot be read keeps its
  /// own path, and the check reports it.
  Future<String> utf8Named(String path) async {
    if (!hasEscapedBytes(path)) return path;
    final List<int> bytes;
    try {
      bytes = rawFile(path).readAsBytesSync();
    } on FileSystemException {
      return path;
    }
    final copy = await ctx.makeTemp();
    if (copy == null || copy.isEmpty) {
      stop(
        'pr-snapshot: cannot create a temp file for the reviewer evaluator',
        1,
      );
    }
    cfgCopy = copy;
    try {
      rawFile(copy).writeAsBytesSync(bytes);
    } on FileSystemException {
      stop(
        'pr-snapshot: cannot create a temp file for the reviewer evaluator',
        1,
      );
    }
    return copy;
  }

  Future<GhResult> gh(List<String> args) => ctx.gh(args, environment: pollEnv);

  Future<int> run(List<String> argv) async {
    // The one option rule (`options.dart`): `--opt VALUE` or `--opt=VALUE`, no abbreviations. A missing value or an unknown
    // option is a usage stop, exit 2; an empty value still stops as bash's `${n:?}` did.
    final parsed = parseOptions(
      argv,
      values: const [
        'repo',
        'reviewer',
        'reviewer-config',
        'full',
        'timeout',
        'until',
        'interval',
      ],
      flags: const ['logs', 'wait'],
      usage: (message) => stop('pr-snapshot: usage: $message', 2),
    );
    String? given(String name) =>
        parsed.wasParsed(name) ? (parsed.option(name) ?? '') : null;
    if (given('reviewer') != null) {
      stop(
        "pr-snapshot: '--reviewer' is gone; pass the reviewers as --reviewer-config FILE (pr-pair.sh context writes it)",
        2,
      );
    }
    if (given('repo') != null) {
      repo = need(given('repo'), 2, '--repo needs owner/name', 89);
    }
    if (given('reviewer-config') != null) {
      rcfg = need(
        given('reviewer-config'),
        2,
        '--reviewer-config needs a file',
        91,
      );
      rcfgSet = true;
    }
    if (given('full') != null) {
      full = need(given('full'), 2, '--full needs a node id', 93);
    }
    if (given('timeout') != null) {
      timeout = need(given('timeout'), 2, '--timeout needs seconds', 95);
    }
    if (given('until') != null) {
      until = need(given('until'), 2, '--until needs a mode (attention)', 96);
    }
    if (given('interval') != null) {
      interval = need(given('interval'), 2, '--interval needs seconds', 98);
      if (!grepQuiet(RegExp(r'^[1-9][0-9]*$'), interval)) {
        stop(
          "pr-snapshot: bad --interval '$interval' (want whole seconds > 0)",
          2,
        );
      }
    }
    logs = parsed.flag('logs');
    wait = parsed.flag('wait');
    for (final arg in parsed.rest) {
      if (RegExp(r'^https://.*/pull/').hasMatch(arg)) {
        repo = arg.replaceFirstMapped(
          RegExp(r'https://[^/]+/([^/]+/[^/]+)/pull/.*'),
          (m) => m[1]!,
        );
        pr = arg.replaceFirstMapped(
          RegExp(r'.*/pull/([0-9]+).*'),
          (m) => m[1]!,
        );
      } else if (RegExp(r'^[0-9]').hasMatch(arg)) {
        pr = arg;
      } else {
        stop("pr-snapshot: unknown argument '$arg'", 2);
      }
    }
    if (until.isNotEmpty) {
      if (until != 'attention') {
        stop("pr-snapshot: bad --until '$until' (want attention)", 2);
      }
      if (!wait) stop('pr-snapshot: --until needs --wait', 2);
    }
    if (full.isNotEmpty) return await readFull();

    // The reviewer config is checked here, in this process, before any gh call: a bad one prints its one line and exits 2
    // (design D3). Only the evaluator child takes the file by name, so only it needs a UTF-8 named copy.
    if (rcfgSet) {
      final path = await ctx.native(rcfg);
      final checked = reviewerLogins(path);
      final error = checked.error;
      if (error != null) stop(error, 2);
      logins = [for (final login in checked.logins) documentText(login)]
          .join(',');
      rcfgArg = await utf8Named(path);
    }
    if (repo.isEmpty) {
      final r = await gh([
        'repo',
        'view',
        '--json',
        'owner,name',
        '--jq',
        repoViewJq,
      ]);
      ctx.relayErr(r);
      if (r.exitCode != 0) throw PrExit(r.exitCode);
      repo = ctx.captured(r);
    }
    if (pr.isEmpty) {
      final r = await gh([
        'pr',
        'view',
        '--json',
        'number',
        '--jq',
        prNumberJq,
      ]);
      ctx.relayErr(r);
      if (r.exitCode != 0) throw PrExit(r.exitCode);
      pr = ctx.captured(r);
    }
    final slash = repo.indexOf('/');
    owner = slash < 0 ? repo : repo.substring(0, slash);
    name = slash < 0 ? repo : repo.substring(slash + 1);

    // The evaluator's material file, in the system temp directory (D8).
    final mat = await ctx.makeTemp();
    if (mat == null || mat.isEmpty) {
      stop(
        'pr-snapshot: cannot create a temp file for the reviewer evaluator',
        1,
      );
    }
    matFile = mat;

    String snap;
    Map<String, Object?> snapDoc;
    final startedAt = ctx.elapsedSeconds();
    var waited = 0;
    var wake = '';
    var filtered = 0;
    if (wait) {
      final r = await watch();
      snap = r.snapshot;
      snapDoc = r.doc;
      wake = r.wake;
      filtered = r.filtered;
      waited = ctx.elapsedSeconds() - startedAt;
      ctx.out(
        '{"wake":"$wake","waited":$waited,"filtered":$filtered,"snapshot":$snap}\n',
      );
    } else {
      final c = await prepareCfg();
      if (c != 0) throw PrExit(c);
      final s = await snapshot();
      if (s.code != 0) throw PrExit(s.code);
      snap = dropTrailingNewlines(s.out);
      snapDoc = s.doc!;
      ctx.out('$snap\n');
    }

    if (logs) {
      var limited = false;
      for (final id in _failRunIds(snapDoc)) {
        ctx.out('\n===== failed log: run $id =====\n');
        final r = await ctx.gh(['run', 'view', id, '-R', repo, '--log-failed']);
        // `2>&1 | tail -n 80`: what the call printed, stdout then stderr, or the limit line the helper printed
        final bytes = r.limitLine != null
            ? encodeEscaped(r.limitLine!)
            : [...r.stdout, ...r.stderr];
        ctx.writeOut(tailLines(bytes, 80));
        if (r.exitCode == 124 || r.exitCode == 125) {
          final label = r.exitCode == 124
              ? 'deadline_exceeded'
              : 'response_too_large';
          ctx.err('bounded: $label: gh run view $id\n');
          limited = true;
        }
      }
      if (limited) throw PrExit(1);
    }
    return 0;
  }

  /// `--full`: one node read whole, no snapshot, no reviewer config, no claim.
  Future<int> readFull() async {
    if (!grepQuiet(RegExp(r'^[A-Za-z0-9_=-]+$'), full)) {
      stop("pr-snapshot: bad --full id '$full'", 2);
    }
    final r = await gh([
      'api',
      'graphql',
      '-f',
      'id=$full',
      '-f',
      'query=$fullQuery',
      '--jq',
      fullJq,
    ]);
    ctx.relayErr(r);
    if (r.exitCode != 0) stop('pr-snapshot: cannot read $full', 3);
    final out = ctx.captured(r);
    ctx.out('$out\n');
    // the document is read, not matched: key order and spacing depend on the evaluator
    return _document(out)?['error'] == 'not_found' ? 1 : 0;
  }

  /// The cfg for the reviewer check (`prepare_cfg`): 0 to go on, else the code the poll or script ends with.
  Future<int> prepareCfg() async {
    final fail = logins.isEmpty ? 0 : 1;
    final info = await gh([
      'api',
      'graphql',
      '-f',
      'owner=$owner',
      '-f',
      'name=$name',
      '-F',
      'pr=$pr',
      '-f',
      'query=$cfgQuery',
      '--jq',
      cfgJq,
    ]);
    ctx.relayErr(info);
    if (info.exitCode != 0) {
      return info.exitCode == 124 || info.exitCode == 125 ? 1 : fail;
    }
    final fields = ctx
        .captured(info)
        .split(RegExp(r'[ \t\n]+'))
        .where((f) => f.isNotEmpty)
        .toList();
    final oid = fields.isNotEmpty ? fields[0] : '';
    final branch = fields.length > 1 ? fields[1] : '';
    final hrepo = fields.length > 2 ? fields.sublist(2).join(' ') : '';

    // stderr is discarded here, and a limit is named by `limit_hit`
    final limit = await gh(['api', '-i', 'rate_limit']);
    var raw = '';
    if (limit.exitCode != 0) {
      if (limitHit(limit.exitCode, 'gh api rate_limit')) return 1;
    } else {
      raw = ctx.captured(limit);
    }
    final date = dateHeaderOf(raw);
    if (!grepQuiet(RegExp(r'^[0-9a-f]{40}$'), oid)) return fail;
    if (!grepQuiet(_datePattern, date)) return fail;
    if (oid != pushedOid) {
      pushedOid = oid;
      pushedAt = '';
      firstSeen = date;
      seenSrc = '';
      seenDate = '';
    }
    // look the push up until found; it can reach the log after the first poll
    if (pushedAt.isEmpty && hrepo != '-') {
      final activity = await gh([
        'api',
        'repos/$hrepo/activity?ref=refs/heads/$branch&per_page=100',
        '--jq',
        activityJq(oid),
      ]);
      if (activity.exitCode != 0) {
        if (limitHit(activity.exitCode, 'gh api repos/$hrepo/activity')) {
          return 1;
        }
        pushedAt = '';
      } else {
        pushedAt = ctx.captured(activity);
      }
      if (!grepQuiet(_pushPattern, pushedAt)) pushedAt = '';
    }
    final String pushed;
    final String cutoff;
    if (pushedAt.isNotEmpty) {
      pushed = pushedAtJq(pushedAt);
      cutoff = cutoffJq('push', pushed);
    } else {
      // decided once per head per process, so the cutoff and timeout start stay fixed
      if (seenSrc.isEmpty) {
        final base = await stateBase(ctx);
        final seen = await resolveFirstSeen(
          ctx,
          dir: headsDirectory(base, owner, name, pr),
          oid: pushedOid,
          firstSeen: firstSeen,
        );
        seenDate = seen.date;
        seenSrc = seen.source;
      }
      pushed = firstSeenJq(seenDate);
      cutoff = cutoffJq(seenSrc, pushed);
    }
    cfg = cfgFor(
      logins: logins,
      oid: oid,
      pushed: pushed,
      cutoff: cutoff,
      date: date,
    );
    return 0;
  }

  /// bounded's exit 124 or 125 on a call whose stderr was discarded: the limit is named here, and the lookup fails.
  bool limitHit(int code, String command) {
    final label = switch (code) {
      124 => 'deadline_exceeded',
      125 => 'response_too_large',
      _ => null,
    };
    if (label == null) return false;
    ctx.err('bounded: $label: $command\n');
    return true;
  }

  Future<GhResult> queryPr(String rtimes) => gh([
    'api',
    'graphql',
    '-f',
    'query=$snapshotQuery',
    '-f',
    'owner=$owner',
    '-f',
    'name=$name',
    '-F',
    'pr=$pr',
    '--jq',
    prJq(cfg, rtimes),
  ]);

  /// The finished snapshot of the material [out] (its document is [material]): `sw pr reviewers` decides the reviewers
  /// and appends their states to sig and attn. It runs as a child of this process under the same deadline and byte bound
  /// as gh; a limit, any other failure, or output that is not one JSON document fails the poll. The material goes
  /// through the temp file, never through an argument.
  ///
  /// The reviewer evaluator stays a separate process killed at the poll deadline, because a Dart regex cannot be
  /// interrupted (ADR 0022). Rejected: evaluating in process, where a backtracking `report.ignore` pattern would hang the
  /// watch with no way to stop it.
  ///
  /// Invariant C1: `sw pr snapshot` must run every user report pattern under the poll's deadline, never in its own
  /// process without a bound.
  Future<_Result> evaluate(String out, Map<String, Object?> material) async {
    try {
      rawFile(matFile!).writeAsBytesSync(encodeEscaped('$out\n'));
    } on FileSystemException {
      return _Result(1);
    }
    final r = await ctx.bounded([
      Platform.resolvedExecutable,
      'pr',
      'reviewers',
      if (rcfgArg.isNotEmpty) ...['--config', rcfgArg],
      '--material',
      matFile!,
      '--head',
      _headOid(material),
    ], environment: pollEnv);
    if (r.limit != null) {
      // the limit line names reviewers.py and python3, as it did when the evaluator was that script, whatever interpreter
      // exists (design D5): the label is a constant
      ctx.err(
        limitLine(r.limit!, [
          'bash',
          '-c',
          'exec "\$@"',
          'reviewers.py',
          'python3',
          '-I',
        ]),
      );
    } else {
      ctx.writeErr(r.stderr);
    }
    if (r.exitCode != 0) return _Result(r.exitCode);
    final text = decodeEscaped(r.stdout);
    final doc = _document(text);
    if (doc == null) {
      ctx.err('pr-snapshot: the reviewer evaluator printed no JSON document\n');
      return _Result(1);
    }
    return _Result(0, text, doc);
  }

  /// One query (~1 point); more only when an item you reacted to was edited since: its reaction times, 100 ids per query
  /// (1-2 points each), then the PR query once more with them.
  Future<_Result> snapshot() async {
    var r = await queryPr('def rtimes: {};');
    ctx.relayErr(r);
    if (r.exitCode != 0) return _Result(1);
    var out = ctx.captured(r);
    var doc = _document(out);
    if (doc == null) return notDocument();
    final batches = recheckBatches(_recheckIds(doc));
    if (batches.isEmpty) return evaluate(out, doc);
    var rt = '';
    for (final ids in batches) {
      if (ids.isEmpty) continue;
      r = await gh([
        'api',
        'graphql',
        '-f',
        'query=${reactionQuery(ids)}',
        '--jq',
        reactionJq,
      ]);
      ctx.relayErr(r);
      if (r.exitCode != 0) return _Result(1);
      rt = '$rt${rt.isEmpty ? '' : ' + '}${ctx.captured(r)}';
    }
    r = await queryPr('def rtimes: ($rt);');
    ctx.relayErr(r);
    if (r.exitCode != 0) return _Result(1);
    out = ctx.captured(r);
    doc = _document(out);
    if (doc == null) return notDocument();
    return evaluate(out, doc);
  }

  /// The PR query's line is not one JSON document: the poll fails.
  _Result notDocument() {
    ctx.err('pr-snapshot: the PR query printed no JSON document\n');
    return _Result(1);
  }

  /// One poll: one deadline for all its gh calls, so a hung poll ends at that deadline and the timeout is still reported on
  /// time. Returns the snapshot and its document, or null when the poll failed.
  Future<({String text, Map<String, Object?> doc})?> poll() async {
    final at =
        DateTime.now().microsecondsSinceEpoch / 1e6 +
        resolveLimits(ctx.env, paged: false).deadline.inMicroseconds / 1e6;
    pollEnv = {...ctx.env, 'SPECWRIGHT_NET_DEADLINE_AT': at.toStringAsFixed(6)};
    try {
      if (await prepareCfg() != 0) return null;
      final s = await snapshot();
      return s.code == 0
          ? (text: dropTrailingNewlines(s.out), doc: s.doc!)
          : null;
    } finally {
      pollEnv = null;
    }
  }

  Never takeOver() {
    stop('pr-snapshot: a newer watcher took over PR $pr; this one stops', 4);
  }

  bool stillOwner() => claim?.stillOwner() ?? true;

  /// `--until attention`: may the poll [snap], which differs from [base], be skipped?
  bool onlyProgress(Map<String, Object?> snap, Map<String, Object?> base) {
    if (_stringOf(snap['attn']) != _stringOf(base['attn'])) return false;
    if (snap['merge_state'] == 'DIRTY') return false;
    if (!_ciPending(snap)) return false;
    final known = _failNames(base);
    for (final f in _failNames(snap)) {
      if (!known.contains(f)) return false;
    }
    return true;
  }

  Future<
    ({String wake, String snapshot, Map<String, Object?> doc, int filtered})
  >
  watch() async {
    final dir = claimDirectory(await stateBase(ctx), owner, name, pr);
    claim = WatchClaim.claim(dir);
    if (claim == null) {
      ctx.err(
        'pr-snapshot: cannot create the watch state directory; ownership is off for PR $pr (this watcher polls unowned)\n',
      );
    }
    // --timeout is elapsed time from here, polls included.
    final start = ctx.elapsedSeconds();
    Map<String, Object?>? base;
    var baseSig = '';
    var snap = '';
    var snapDoc = <String, Object?>{};
    var wake = 'timeout';
    var ok = true;
    var filtered = 0;
    // a failed first snapshot has no base: the first good poll becomes it
    final first = await poll();
    if (first != null) {
      snap = first.text;
      base = snapDoc = first.doc;
    } else {
      ok = false;
    }
    baseSig = _stringOf(base?['sig']);
    // Activity beyond a cut-off page cannot be seen, so do not wait for it.
    if (base != null && _incomplete(base)) wake = 'incomplete';
    while (wake == 'timeout') {
      final elapsed = ctx.elapsedSeconds() - start;
      final limit = int.tryParse(timeout);
      if (limit == null || elapsed >= limit) break;
      final every = int.tryParse(interval) ?? limit;
      final nap = every <= limit - elapsed ? every : limit - elapsed;
      // `set -e` ended the script when `sleep` failed; never poll without the nap
      final slept = await ctx.tool(['sleep', '$nap']);
      if (slept.exitCode != 0) {
        ctx.writeErr(slept.stderr);
        throw PrExit(slept.exitCode);
      }
      if (!stillOwner()) takeOver();
      // keep the last good snapshot; a failed poll never replaces it
      final next = await poll();
      if (next == null) {
        ok = false;
        continue;
      }
      snap = next.text;
      snapDoc = next.doc;
      ok = true;
      if (base == null) {
        base = snapDoc;
        baseSig = _stringOf(snapDoc['sig']);
        if (_incomplete(base)) wake = 'incomplete';
      } else if (_stringOf(snapDoc['sig']) != baseSig) {
        if (until == 'attention' && onlyProgress(snapDoc, base)) {
          filtered++;
        } else {
          wake = 'changed';
        }
      }
    }
    // a watcher taken over during a hung poll stops here, not with a timeout report
    if (wake == 'timeout' && !stillOwner()) takeOver();
    if (!ok) stop('pr-snapshot: the last poll failed; GitHub state unknown', 1);
    return (wake: wake, snapshot: snap, doc: snapDoc, filtered: filtered);
  }
}
