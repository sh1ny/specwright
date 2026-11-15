/// A named release stop: one JSON document with `ok: false`, an `error` name,
/// a `message` and the stop's own fields, and the exit [code] (1 a stop, 2
/// usage, 3 a git or network failure).
class ReleaseStop implements Exception {
  ReleaseStop(this.error, this.message, {this.code = 1, this.extra = const {}});

  final String error;
  final String message;
  final int code;
  final Map<String, Object?> extra;

  Map<String, Object?> toJson() => {
    'ok': false,
    'error': error,
    'message': message,
    ...extra,
  };

  @override
  String toString() => '$error: $message';
}
