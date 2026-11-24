part of 'run.dart';

const _progressMarker = '<!-- specwright-design-progress -->';
const _progressStart = '\n\n$_progressMarker\n';
const _progressMarkerPattern = '$_progressMarker[ \t]*';
final _progressBoundary = RegExp('\r?\n\r?\n$_progressMarkerPattern\r?\n');
final _progressMarkerLine = RegExp('^$_progressMarkerPattern\$');
final _designLines = RegExp(r'\r\n|[\r\n\v\f\u001c-\u001e\u0085\u2028\u2029]');
const _ownerChoices = ['scoped-pass', 'scope-change', 'stop'];

bool _hasProgressMarker(String text) =>
    text.split(_designLines).any(_progressMarkerLine.hasMatch);

const _checkpointReviewInstruction =
    '## Owner checkpoint review\n\n'
    'Run the full checklist on the entire current design, not a confirmation of Required Changes. '
    'The owner may limit the repairs, not your review. Consider all still-applicable open findings '
    'in the previous report before issuing a passing verdict.';

String? _designLine(String text, String key) {
  for (final line in text.split(_designLines)) {
    final value = _lineValue(line, key);
    if (value != null) return value;
  }
  return null;
}

String _progressQuote(String value) => jsonEncode(value).replaceAllMapped(
  _designLines,
  (match) => '\\u${match[0]!.codeUnitAt(0).toRadixString(16).padLeft(4, '0')}',
);

class _DesignCheckpoint {
  _DesignCheckpoint(this.out, Map<String, Object?> settings)
    : limit = _limit(settings);

  final String out;
  final int limit;

  static int _limit(Map<String, Object?> settings) {
    if (!settings.containsKey('design_max_rounds')) return 3;
    final configured = settings['design_max_rounds'];
    if (configured is int && configured > 0) return configured;
    throw ReviewStop(
      'bad_design_setting',
      'review.design_max_rounds must be a positive integer',
    );
  }

  Map<String, Object?> step(Map<String, String> args) {
    final state = _DesignProgress.read(out);
    final action = args['choice'];
    if (action != null) {
      if (state.status(limit) != 'owner_checkpoint' ||
          int.tryParse(args['round'] ?? '') != state.round) {
        throw ReviewStop(
          'no_owner_checkpoint',
          'choose at the current unresolved review round',
        );
      }
      final detail = args['detail'];
      if (!_ownerChoices.contains(action) ||
          (action != 'stop' && (detail == null || detail.trim().isEmpty)) ||
          (detail != null && utf8.encode(detail).length > 8192)) {
        throw ReviewStop(
          'usage',
          'choose scoped-pass with scope, scope-change with reason, or stop',
          code: 2,
        );
      }
      state.log.add({
        'round': state.round,
        'choice': action,
        'detail': ?detail,
      });
      _atomicWrite(out, state.withProgress(state.body));
    }
    return {
      'ok': true,
      'status': state.status(limit),
      'round': state.round,
      'scope_round': state.scopeRound,
      'limit': limit,
      'verdict': ?state.verdict,
      'choice': ?state.choice,
    };
  }

  String? beforeReview() {
    final state = _DesignProgress.read(out);
    _beforeReview(state);
    return state.requiresFullReview ? _checkpointReviewInstruction : null;
  }

  void _beforeReview(_DesignProgress state) {
    final status = state.status(limit);
    if (status == 'owner_checkpoint' || status == 'stopped') {
      throw ReviewStop(
        status,
        'unresolved design review paused at round ${state.round}',
      );
    }
  }

  String record(String text, String? repairs, Never Function(String) invalid) {
    if (_hasProgressMarker(text)) {
      invalid('review reply contains the reserved owner progress marker');
    }
    final state = _DesignProgress.read(out);
    _beforeReview(state);
    if (state.requiresFullReview &&
        _designLine(text, 'CHANGES_APPLIED') == 'yes') {
      invalid(
        'the owner checkpoint requires a full review, not a Required Changes confirmation',
      );
    }
    final choice = state.choice;
    state.scopeRound = choice == 'scope-change' ? 1 : state.scopeRound + 1;
    state.round++;
    state.extended = choice == 'scoped-pass';
    if (repairs != null && repairs.isNotEmpty) {
      state.log.add({'round': state.round, 'repairs': repairs});
    }
    return state.withProgress(text);
  }
}

class _DesignProgress {
  _DesignProgress(this.body, this.verdict, this.unresolved);

  final String body;
  final String? verdict;
  final bool unresolved;
  int round = 0;
  int scopeRound = 0;
  bool extended = false;
  List<Map<String, Object?>> log = [];

  String? get choice {
    if (log.isEmpty || log.last['round'] != round) return null;
    return log.last['choice'] as String?;
  }

  bool get requiresFullReview =>
      choice == 'scoped-pass' || choice == 'scope-change';

  String status(int limit) {
    if (choice == 'stop') return 'stopped';
    if (unresolved && choice == null && (scopeRound >= limit || extended)) {
      return 'owner_checkpoint';
    }
    return 'review';
  }

  String withProgress(String text) {
    final payload = base64Url.encode(
      utf8.encode(
        jsonEncode({
          'version': 1,
          'round': round,
          'scope_round': scopeRound,
          'extended': extended,
          'log': log,
        }),
      ),
    );
    final footer = StringBuffer(
      '$_progressStart<!-- $payload -->\n\n## Review progress\n\n',
    )..writeln('- Validated round: $round (scope round $scopeRound)');
    for (final entry in log) {
      final which = entry['round'];
      final action = entry['choice'];
      final detail = entry['detail'] as String?;
      if (action != null) {
        footer.writeln(
          '- Owner round $which: `$action`${detail == null ? '' : ' — ${_progressQuote(detail)}'}',
        );
      } else {
        footer.writeln(
          '- Repairs before round $which: ${_progressQuote(entry['repairs'] as String)}',
        );
      }
    }
    final progress = footer.toString();
    if (utf8.encode(progress).length > _maxAnswer) {
      throw ReviewStop(
        'design_progress_too_large',
        'design review progress exceeds 2 MiB; previous report retained',
      );
    }
    return text + progress;
  }

  static _DesignProgress read(String out) {
    final bytes = readRegularFile(out, limit: 2 * _maxAnswer + 1);
    if (bytes == null) return _DesignProgress('', null, false);
    if (bytes.length > 2 * _maxAnswer) {
      throw ReviewStop(
        'bad_design_progress',
        '$out exceeds the review record limit',
      );
    }
    final text = utf8.decode(bytes);
    final boundary = _progressBoundary.firstMatch(text);
    if (boundary == null && _hasProgressMarker(text)) {
      throw ReviewStop(
        'bad_design_progress',
        '$out has malformed owner checkpoint progress',
      );
    }
    final body = boundary == null ? text : text.substring(0, boundary.start);
    final verdict = _designLine(body, 'VERDICT');
    final result = _DesignProgress(
      body,
      verdict,
      verdict == 'REVISE' ||
          (verdict == 'APPROVE_WITH_CHANGES' &&
              _designLine(body, 'CHANGES_APPLIED') == 'no'),
    );
    if (boundary == null) {
      if (result.unresolved) {
        final legacyRound = RegExp(
          r'^- \*\*Round:\*\*\s*([1-9][0-9]*)[ \t]*\r?$',
          multiLine: true,
        ).firstMatch(body);
        result.round = result.scopeRound =
            int.tryParse(legacyRound?[1] ?? '') ?? 1;
      }
      return result;
    }
    try {
      final footer = text.substring(boundary.end).split(_designLines).first;
      if (!footer.startsWith('<!-- ') || !footer.endsWith(' -->')) {
        throw const FormatException();
      }
      final data = jsonDecode(
        utf8.decode(base64Url.decode(footer.substring(5, footer.length - 4))),
      ) as Map<String, Object?>;
      if (data['version'] != 1) throw const FormatException();
      result.round = data['round'] as int;
      result.scopeRound = data['scope_round'] as int;
      result.extended = data['extended'] as bool;
      result.log = (data['log'] as List).cast<Map<String, Object?>>();
      if (result.scopeRound < 1 ||
          result.scopeRound > result.round ||
          result.withProgress('') !=
              '$_progressStart${text.substring(boundary.end).replaceAll('\r\n', '\n')}') {
        throw const FormatException();
      }
      return result;
    } on Object {
      throw ReviewStop(
        'bad_design_progress',
        '$out has malformed owner checkpoint progress',
      );
    }
  }
}
