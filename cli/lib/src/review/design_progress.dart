part of 'run.dart';

const _progressMarker = '<!-- specwright-design-progress -->';
const _progressJoin = '\n\n$_progressMarker\n';
final _progressBoundary = RegExp('\r?\n\r?\n$_progressMarker\r?\n');
const _choiceNames = ['scoped-pass', 'scope-change', 'stop'];
final _lineBreak = RegExp(r'\r\n|[\r\n\v\f\u001c-\u001e\u0085\u2028\u2029]');

String _designQuote(String value) => jsonEncode(value).replaceAllMapped(
  _lineBreak,
  (match) => '\\u${match[0]!.codeUnitAt(0).toRadixString(16).padLeft(4, '0')}',
);

class _DesignHistory {
  _DesignHistory({
    this.round = 0,
    this.scopeRound = 0,
    this.artifacts = '',
    this.rules = '',
    this.extended = false,
    List<Map<String, Object?>>? history,
  }) : history = history ?? [];

  int round;
  int scopeRound;
  String artifacts;
  String rules;
  bool extended;
  final List<Map<String, Object?>> history;

  Map<String, Object?>? get choice {
    if (history.isEmpty) return null;
    final last = history.last;
    return last['round'] == round && last.containsKey('choice') ? last : null;
  }

  String footer() {
    final payload = base64Url.encode(
      utf8.encode(
        jsonEncode({
          'version': 1,
          'round': round,
          'scope_round': scopeRound,
          'artifacts': artifacts,
          'rules': rules,
          'extended': extended,
          'history': history,
        }),
      ),
    );
    final out = StringBuffer(_progressJoin)
      ..writeln('<!-- $payload -->')
      ..writeln()
      ..writeln('## Review progress')
      ..writeln()
      ..writeln('- Validated round: $round (scope round $scopeRound)');
    for (final item in history) {
      final detail = item['detail'] as String?;
      if (item.containsKey('choice')) {
        out.writeln(
          '- Owner round ${item['round']}: `${item['choice']}`${detail == null ? '' : ' — ${_designQuote(detail)}'}',
        );
      } else {
        out.writeln(
          '- Repairs before round ${item['round']}: ${_designQuote(detail!)}',
        );
      }
    }
    final result = out.toString();
    if (utf8.encode(result).length > _maxAnswer) {
      throw ReviewStop(
        'design_progress_too_large',
        'FULL review progress exceeds 2 MiB; previous report retained',
      );
    }
    return result;
  }

  static _DesignHistory parse(String footer) {
    try {
      final line = footer.substring(_progressJoin.length).split('\n').first;
      if (!line.startsWith('<!-- ') || !line.endsWith(' -->')) {
        throw const FormatException();
      }
      final obj = jsonDecode(
        utf8.decode(base64Url.decode(line.substring(5, line.length - 4))),
      ) as Map<String, Object?>;
      if (obj['version'] != 1) throw const FormatException();
      final result = _DesignHistory(
        round: obj['round'] as int,
        scopeRound: obj['scope_round'] as int,
        artifacts: obj['artifacts'] as String,
        rules: obj['rules'] as String,
        extended: obj['extended'] as bool,
        history: (obj['history'] as List).cast<Map<String, Object?>>(),
      );
      if (result.round < 1 ||
          result.scopeRound < 1 ||
          result.scopeRound > result.round) {
        throw const FormatException();
      }
      for (final item in result.history) {
        final round = item['round'];
        final detail = item['detail'];
        if (round is! int ||
            round < 1 ||
            round > result.round ||
            (detail != null && detail is! String)) {
          throw const FormatException();
        }
        if (item.containsKey('choice') &&
            !_choiceNames.contains(item['choice'])) {
          throw const FormatException();
        }
      }
      if (result.footer() != footer) throw const FormatException();
      return result;
    } on Object {
      throw ReviewStop(
        'bad_design_progress',
        'FULL design review has a malformed progress footer; recover the recorded state before continuing',
      );
    }
  }
}

class _DesignReport {
  _DesignReport(
    this.raw,
    this.identity,
    this.body,
    this.history,
    this.verdict,
    this.applied,
    this.managed,
  );
  final String raw;
  final String identity;
  final String body;
  final _DesignHistory history;
  final String? verdict;
  final String? applied;
  final bool managed;
  bool get unresolved =>
      verdict == 'REVISE' ||
      (verdict == 'APPROVE_WITH_CHANGES' && applied == 'no');
  bool get passing => verdict == 'APPROVE';
  bool get needsFull =>
      managed || unresolved || passing || verdict == 'APPROVE_WITH_CHANGES';

  static _DesignReport read(String path, {bool legacyRound = true}) {
    final type = FileSystemEntity.typeSync(path, followLinks: false);
    if (type == FileSystemEntityType.notFound) {
      return _DesignReport('', '', '', _DesignHistory(), null, null, false);
    }
    if (type != FileSystemEntityType.file) {
      throw ReviewStop(
        'bad_design_progress',
        '$path is not a regular review record',
      );
    }
    final bytes = readRegularFile(path, limit: 2 * _maxAnswer + 1)!;
    if (bytes.length > 2 * _maxAnswer) {
      throw ReviewStop(
        'bad_design_progress',
        '$path exceeds the full review record limit',
      );
    }
    final raw = utf8.decode(bytes);
    final boundary = _progressBoundary.firstMatch(raw);
    final managed = boundary != null;
    final body = managed ? raw.substring(0, boundary.start) : raw;
    if (body.split(_lineBreak).contains(_progressMarker)) {
      throw ReviewStop(
        'bad_design_progress',
        '$path has an invalid FULL progress marker',
      );
    }
    final verdict = _designLine(body, 'VERDICT');
    final applied = _designLine(body, 'CHANGES_APPLIED');
    final history = managed
        ? _DesignHistory.parse(
            raw.substring(boundary.start).replaceAll('\r\n', '\n'),
          )
        : _DesignHistory();
    final result = _DesignReport(
      raw,
      sha256.convert(bytes).toString(),
      body,
      history,
      verdict,
      applied,
      managed,
    );
    if (managed && _validateDesign(body) != null) {
      throw ReviewStop(
        'bad_design_progress',
        '$path has an invalid reviewer verdict',
      );
    }
    if (!managed && legacyRound && result.unresolved) {
      final rows = RegExp(
        r'^- \*\*Round:\*\*\s*([1-9][0-9]*)[ \t]*\r?$',
        multiLine: true,
      ).allMatches(body).toList();
      final round = rows.length == 1 ? int.tryParse(rows.single[1]!) : null;
      if (round == null) {
        throw ReviewStop(
          'bad_design_progress',
          'recover the previous review Round in $path before continuing',
        );
      }
      history.round = history.scopeRound = round;
    }
    return result;
  }
}

String? _designLine(String text, String key) {
  String? value;
  for (final line in text.split(_lineBreak)) {
    final next = _lineValue(line, key);
    if (next == null) continue;
    if (value != null) return null;
    value = next;
  }
  return value;
}

String _canonicalReview(String path) {
  final absolute = p.normalize(p.absolute(path));
  final parent = Directory(p.dirname(absolute));
  return p.join(parent.resolveSymbolicLinksSync(), p.basename(absolute));
}

bool _lightDesign(String out) {
  final path = p.join(p.dirname(out), 'design.md');
  final bytes = readRegularFile(path, limit: _designArtifactBytes + 1);
  if (bytes == null || bytes.length > _designArtifactBytes) return false;
  return _designLine(utf8.decode(bytes), 'TIER') == 'LIGHT';
}

class _DesignController {
  _DesignController(Map<String, String> args)
    : out = _canonicalReview(args['out']!) {
    state = Directory(
      p.join(
        _stateDirectory(),
        'change-review',
        _designHash(Platform.isWindows ? out.toLowerCase() : out),
      ),
    );
  }

  final String out;
  late final Directory state;
  Directory get slots => Directory(p.join(state.path, 'attempts'));
  File get lastFailed => File(p.join(state.path, 'last-failed'));

  Future<T> locked<T>(Future<T> Function() use) async {
    state.createSync(recursive: true);
    final file = File(p.join(state.path, 'publication.lock'))
        .openSync(mode: FileMode.append);
    try {
      try {
        file.lockSync();
      } on FileSystemException {
        throw ReviewStop(
          'review_record_busy',
          'another FULL review operation is publishing $out',
        );
      }
      return await use();
    } finally {
      file.closeSync();
    }
  }

  Future<_DesignState> load(
    Map<String, String> args, {
    bool render = false,
    _DesignProject? project,
  }) async {
    project ??= await _DesignProject.read(args);
    final limit = project.limit;
    final rules = await project.rules(render: render);
    final report = _DesignReport.read(out);
    final artifacts = _designArtifactsIdentity(File(out).parent);
    return _DesignState(project, limit, rules, report, artifacts);
  }

  Future<Map<String, Object?>> step(
    Map<String, String> args, {
    bool light = false,
  }) async {
    if (light) {
      final report = _DesignReport.read(out, legacyRound: false);
      return {
        'ok': true,
        'status': report.needsFull || !_lightDesign(out)
            ? 'full_required'
            : 'light',
      };
    }
    Future<Map<String, Object?>> examine() async {
      final state = await load(args);
      final history = state.report.history;
      final choice = args['choice'];
      if (choice == null) return state.document();
      if (state.status != 'owner_checkpoint' ||
          int.tryParse(args['round'] ?? '') != history.round) {
        throw ReviewStop(
          'no_owner_checkpoint',
          'choice must name the current unresolved checkpoint round',
        );
      }
      final detail = args['detail'];
      if (!_choiceNames.contains(choice) ||
          (choice != 'stop' && (detail == null || detail.trim().isEmpty)) ||
          (detail != null && utf8.encode(detail).length > 8192)) {
        throw ReviewStop(
          'usage',
          'choose scoped-pass with scope, scope-change with reason, or stop',
          code: 2,
        );
      }
      history.history.add({
        'round': history.round,
        'choice': choice,
        'detail': ?detail,
        if (choice == 'scope-change') 'at_artifacts': state.artifacts,
      });
      _atomicWrite(out, state.report.body + history.footer());
      return state.document();
    }

    return args.containsKey('choice') ? locked(examine) : examine();
  }

  Future<Map<String, Object?>> recordLight(String resultPath) =>
      locked(() async {
        if (_DesignReport.read(out, legacyRound: false).needsFull ||
            !_lightDesign(out)) {
          throw ReviewStop(
            'full_required',
            'LIGHT cannot publish over a FULL design or review',
          );
        }
        _DesignController.rejectOrdinarySource(resultPath);
        final text = _readResult(resultPath);
        if (text == null ||
            text.split(_lineBreak).contains(_progressMarker) ||
            (_designLine(text, 'VERDICT') != 'SKIPPED_LIGHT' &&
                text.split(_lineBreak).any((l) => l.startsWith('VERDICT:'))) ||
            (_designLine(text, 'VERDICT') == 'SKIPPED_LIGHT' &&
                _designLine(text, 'CHANGES_APPLIED') != 'n/a')) {
          throw ReviewStop(
            'invalid_output',
            'expected LIGHT recheck findings or SKIPPED_LIGHT/n/a',
            code: 3,
          );
        }
        _atomicWrite(out, text);
        if (!_sameFile(resultPath, out)) File(resultPath).deleteSync();
        return {'ok': true, 'status': 'ok', 'out': _normal(out)};
      });

  Future<_DesignAttempt> prepare(
    Map<String, String> args,
    String route, {
    _DesignProject? project,
  }) async {
    Future<_DesignAttempt> start() async {
      final state = await load(args, render: true, project: project);
      state.project.checkSelection(args, route);
      final status = state.status;
      if (const [
        'owner_checkpoint',
        'stopped',
        'scope_unchanged',
      ].contains(status)) {
        throw ReviewStop(
          status,
          'FULL design review cannot start: $status; read $out',
          extra: {'round': state.report.history.round},
        );
      }
      final repair = args['repairs'] ?? 'none';
      if (repair.trim().isEmpty ||
          _lineBreak.hasMatch(repair) ||
          utf8.encode(repair).length > 8192) {
        throw ReviewStop(
          'usage',
          '--repairs needs a one-line summary of actual repairs or none',
          code: 2,
        );
      }
      Directory? dir;
      if (route == 'subagent') {
        slots.createSync(recursive: true);
        final occupied = slots.listSync(followLinks: false);
        if (occupied.length >= 2) {
          throw ReviewStop(
            'design_attempt_limit',
            'two unfinished subagent attempts must be resolved first',
            extra: {'attempts': occupied.map((e) => _normal(e.path)).toList()},
          );
        }
        dir = slots.createTempSync('attempt-');
      }
      final choice = state.report.history.choice;
      final attempt = _DesignAttempt(
        this,
        route,
        state.fingerprint,
        repair,
        dir: dir,
        section: state.rules.section,
        round: state.report.history.round + 1,
        scope: choice?['choice'] == 'scoped-pass'
            ? choice!['detail'] as String
            : null,
      );
      if (dir != null) {
        try {
          File(p.join(dir.path, 'attempt.json')).writeAsStringSync(
            jsonEncode({'fingerprint': attempt.fingerprint, 'repairs': repair}),
          );
        } on Object {
          dir.deleteSync(recursive: true);
          rethrow;
        }
      }
      return attempt;
    }

    return route == 'subagent' ? locked(start) : start();
  }

  _DesignAttempt resume(Map<String, String> args) {
    _need(args, const ['result', 'attempt']);
    final scratch = p.normalize(p.absolute(args['result']!));
    final dir = File(scratch).parent;
    if (!p.equals(p.absolute(slots.path), p.dirname(dir.path)) ||
        !p.basename(dir.path).startsWith('attempt-') ||
        p.basename(scratch) != 'result.md') {
      throw ReviewStop(
        'bad_design_attempt',
        'result is not an active FULL change scratch',
      );
    }
    final meta = File(p.join(dir.path, 'attempt.json'));
    if (!meta.existsSync()) {
      throw ReviewStop(
        'bad_design_attempt',
        'FULL scratch reservation is not active',
      );
    }
    final obj = jsonDecode(meta.readAsStringSync()) as Map<String, Object?>;
    final attempt = _DesignAttempt(
      this,
      'subagent',
      obj['fingerprint'] as String,
      obj['repairs'] as String,
      dir: dir,
    );
    if (attempt.token != args['attempt']) {
      throw ReviewStop(
        'bad_design_attempt',
        'FULL scratch does not match its starting attempt',
      );
    }
    return attempt;
  }

  static void rejectOrdinary(String path) {
    final output = File(p.absolute(path));
    var resolved = p.normalize(output.path);
    if (output.parent.existsSync()) resolved = _canonicalReview(resolved);
    if (FileSystemEntity.typeSync(resolved, followLinks: false) ==
        FileSystemEntityType.link) {
      resolved = output.resolveSymbolicLinksSync();
    }
    if (_activeReviewPath(resolved) ||
        (FileSystemEntity.typeSync(resolved) == FileSystemEntityType.file &&
            _hasDesignFooter(resolved))) {
      throw ReviewStop(
        'full_required',
        'use the FULL or LIGHT design workflow for $resolved',
      );
    }
  }

  static bool _activeReviewPath(String path) =>
      p.basename(path).toLowerCase() == 'review.md' &&
      p.basename(p.dirname(p.dirname(path))).toLowerCase() == 'changes';

  static bool _hasDesignFooter(String path) {
    final bytes = readRegularFile(path, limit: 2 * _maxAnswer);
    return bytes != null &&
        _progressBoundary.hasMatch(utf8.decode(bytes, allowMalformed: true));
  }

  static void rejectOrdinarySource(String path) {
    if (FileSystemEntity.typeSync(path, followLinks: false) !=
        FileSystemEntityType.file) {
      throw ReviewStop(
        'bad_design_artifact',
        '$path is not a regular scratch file',
      );
    }
    rejectOrdinary(path);
  }
}

class _DesignState {
  _DesignState(
    this.project,
    this.limit,
    this.rules,
    this.report,
    this.artifacts,
  );
  final _DesignProject project;
  final int limit;
  final _DesignRules rules;
  final _DesignReport report;
  final String artifacts;

  String get fingerprint => _designHash([
    project.identity,
    project.tip,
    rules.identity,
    limit,
    report.identity,
    artifacts,
  ]);
  String get status {
    final history = report.history;
    final choice = history.choice;
    if (choice?['choice'] == 'stop') return 'stopped';
    if (choice?['choice'] == 'scope-change' &&
        choice?['at_artifacts'] == artifacts) {
      return 'scope_unchanged';
    }
    if (report.verdict == 'USER_OVERRIDE' && !report.managed) return 'pass';
    if (report.managed &&
        report.passing &&
        history.rules == rules.identity &&
        history.artifacts == artifacts) {
      return 'pass';
    }
    if (report.unresolved &&
        choice == null &&
        (history.scopeRound >= limit || history.extended)) {
      return 'owner_checkpoint';
    }
    return 'review';
  }

  Map<String, Object?> document() => {
    'ok': true,
    'status': status,
    'round': report.history.round,
    'scope_round': report.history.scopeRound,
    'limit': limit,
    'verdict': ?report.verdict,
    'choice': ?report.history.choice?['choice'],
  };
}

class _DesignAttempt {
  _DesignAttempt(
    this.controller,
    this.route,
    this.fingerprint,
    this.repairs, {
    this.dir,
    this.section,
    this.round,
    this.scope,
  });

  final _DesignController controller;
  final String route;
  final String fingerprint;
  final String repairs;
  final Directory? dir;
  final String? section;
  final int? round;
  final String? scope;

  String get scratch => p.join(dir!.absolute.path, 'result.md');
  String get token => _designHash([scratch, fingerprint, repairs]);
  Map<String, Object?> instructions() => {
    'ok': true,
    'scratch': _normal(scratch),
    'attempt': token,
    'standing_requirements': ?section,
    'round': ?round,
    'scope': ?scope,
  };

  String get packet {
    final result = StringBuffer(
      '\n\nReview round: $round. Use the full checklist.\n',
    );
    if (scope != null) {
      result.writeln(
        'Owner-authorized scope of this additional pass: ${_designQuote(scope!)}',
      );
    }
    if (section != null) {
      result
        ..writeln()
        ..write(section);
    }
    return result.toString();
  }

  (String?, String?) _readScratch() {
    final path = scratch;
    final bytes =
        FileSystemEntity.typeSync(path, followLinks: false) ==
            FileSystemEntityType.file
        ? readRegularFile(path, limit: _maxAnswer + 1)
        : null;
    if (bytes == null) return (null, 'expected a regular FULL scratch reply');
    if (bytes.length > _maxAnswer) return (null, 'output too large');
    try {
      return (utf8.decode(bytes), null);
    } on FormatException {
      return (null, 'FULL scratch reply is not valid UTF-8');
    }
  }

  Future<Map<String, Object?>> publish(
    Map<String, String> args, {
    String? text,
    Map<String, Object?>? receipt,
  }) => controller.locked(() async {
    Object? originalError;
    Map<String, Object?>? published;
    try {
      final state = await controller.load(args);
      state.project.checkSelection(args, route);
      if (state.fingerprint != fingerprint) {
        throw ReviewStop(
          'stale_review',
          'review inputs changed; the prior review was not replaced',
        );
      }
      String? inputProblem;
      if (dir != null) {
        (text, inputProblem) = _readScratch();
        receipt = _makeReceipt(
          route: route,
          skipped: _loadSelection(args['selection'], route),
          requestedModel: null,
          requestedThinking: null,
          version: null,
          started: _now(),
          actualModel: 'unknown',
          actualThinking: 'unknown',
          processGroup: 'session',
        );
      }
      final answer = text;
      final problem =
          inputProblem ??
          (answer == null ? 'output too large' : _validateDesign(answer));
      final applied = answer == null
          ? null
          : _designLine(answer, 'CHANGES_APPLIED');
      if (problem != null ||
          applied == 'yes' ||
          answer!.split(_lineBreak).contains(_progressMarker)) {
        final extra = <String, Object?>{
          'status': 'invalid',
          'route': route,
          'receipt': receipt,
        };
        if (answer != null && utf8.encode(answer).length <= _maxAnswer) {
          try {
            controller.lastFailed.writeAsStringSync(answer, flush: true);
            extra['diagnostic'] = _normal(controller.lastFailed.absolute.path);
          } on FileSystemException catch (error) {
            extra['diagnostic_error'] = error.message;
          }
        }
        throw ReviewStop(
          'invalid_output',
          problem ?? 'use APPROVE after reviewing the complete revised design',
          code: 3,
          extra: extra,
        );
      }
      final history = state.report.history;
      final choice = history.choice?['choice'];
      history.scopeRound = choice == 'scope-change' || !state.report.unresolved
          ? 1
          : history.scopeRound + 1;
      history.round++;
      history.artifacts = state.artifacts;
      history.rules = state.rules.identity;
      history.extended =
          choice == 'scoped-pass' || history.scopeRound >= state.limit;
      history.history.add({'round': history.round, 'detail': repairs});
      _atomicWrite(controller.out, answer + history.footer());
      return published = {
        'ok': true,
        'status': 'ok',
        'out': _normal(controller.out),
        'route': route,
        'receipt': receipt,
      };
    } on Object catch (error) {
      originalError = error;
      rethrow;
    } finally {
      final scratchDir = dir;
      if (scratchDir != null) {
        try {
          scratchDir.deleteSync(recursive: true);
        } on FileSystemException catch (error) {
          final previous = originalError;
          final cleanup = {
            'cleanup_error': error.message,
            'attempt_dir': _normal(scratchDir.path),
          };
          if (published != null) {
            published.addAll(cleanup);
          } else {
            throw ReviewStop(
              previous is ReviewStop
                  ? previous.error
                  : 'scratch_cleanup_failed',
              previous is ReviewStop
                  ? previous.message
                  : 'could not remove FULL scratch attempt',
              code: previous is ReviewStop ? previous.code : 1,
              extra: {
                if (previous is ReviewStop) ...previous.extra,
                ...cleanup,
              },
            );
          }
        }
      }
    }
  });
}
