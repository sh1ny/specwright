/// A named review stop, using the native workflow JSON/error convention.
class ReviewStop implements Exception {
  ReviewStop(this.error, this.message, {this.code = 1, this.extra = const {}});

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
