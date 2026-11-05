/// The limits of one bounded run, resolved from the environment.
///
/// Defaults live here only. The environment can lower them (for tests and for
/// a caller's own budget) but never raise them; a value that is not a
/// non-negative number leaves the default.
library;

const int defaultDeadlineSeconds = 120;
const int defaultPagedDeadlineSeconds = 300;
const int defaultMaxBytes = 32 * 1024 * 1024;

/// How long the readers get to reach end-of-file after the command exited.
const Duration readerGrace = Duration(seconds: 2);

/// How long to wait for the pipes to close after the tree was stopped.
const Duration stopWait = Duration(seconds: 5);

class RunLimits {
  const RunLimits({required this.deadline, required this.maxBytes});

  /// Time from the start of the run until the deadline. Already capped by
  /// `SPECWRIGHT_NET_DEADLINE_AT`.
  final Duration deadline;

  /// Bound on the bytes of stdout, and separately of stderr.
  final int maxBytes;
}

/// Parses [text] as a non-negative number; null when it is not one.
double? _nonNegative(String? text) {
  if (text == null) return null;
  final value = double.tryParse(text.trim());
  if (value == null || value.isNaN || value < 0) return null;
  return value;
}

int? _nonNegativeInt(String? text) {
  if (text == null) return null;
  final value = int.tryParse(text.trim());
  if (value == null || value < 0) return null;
  return value;
}

/// Resolves the limits for a run from [env].
///
/// [epochSeconds] returns the current wall time in epoch seconds; it is read
/// once, so a later clock step cannot move the deadline.
RunLimits resolveLimits(
  Map<String, String> env, {
  required bool paged,
  double Function()? epochSeconds,
}) {
  final defaultDeadline = paged
      ? defaultPagedDeadlineSeconds
      : defaultDeadlineSeconds;
  var seconds = defaultDeadline.toDouble();
  final lowered = _nonNegative(
    env[paged ? 'SPECWRIGHT_NET_PAGED_DEADLINE' : 'SPECWRIGHT_NET_DEADLINE'],
  );
  if (lowered != null && lowered < seconds) seconds = lowered;

  var maxBytes = defaultMaxBytes;
  final loweredBytes = _nonNegativeInt(env['SPECWRIGHT_NET_MAX_BYTES']);
  if (loweredBytes != null && loweredBytes < maxBytes) maxBytes = loweredBytes;

  final at = _nonNegative(env['SPECWRIGHT_NET_DEADLINE_AT']);
  if (at != null) {
    final now =
        (epochSeconds ?? () => DateTime.now().microsecondsSinceEpoch / 1e6)();
    final left = at - now;
    final remaining = left < 0 ? 0.0 : left;
    if (remaining < seconds) seconds = remaining;
  }
  return RunLimits(
    deadline: Duration(microseconds: (seconds * 1e6).round()),
    maxBytes: maxBytes,
  );
}
