import '../process/launch.dart' show Unrepresentable;
import 'codec.dart';

/// A stop `vcs.sh` reports as one document: [error], [message], the exit [code]
/// (1 by default, 2 for a usage error, 3 for a fence refusal) and any [extra]
/// fields after the message.
class VcsStop implements Exception {
  VcsStop(
    this.error,
    this.message, {
    this.code = 1,
    this.extra = const <String, Object?>{},
  });

  /// A name `sw` acts on or reports was not valid UTF-8: `not_utf8`, exit 1,
  /// with a message that asks for a rename.
  factory VcsStop.notUtf8(NotUtf8 e) =>
      VcsStop('not_utf8', '${e.message}; rename it');

  /// The launcher refused input it cannot hand to a tool whole (a NUL, a lone
  /// surrogate, a command line past the Windows limit): `not_utf8`, exit 1,
  /// naming the command and the input (D5).
  factory VcsStop.unrepresentable(Unrepresentable e) => VcsStop(
    'not_utf8',
    'cannot start ${e.command}: its ${e.what} cannot be represented',
  );

  final String error;
  final String message;
  final int code;
  final Map<String, Object?> extra;

  /// The document: `ok` false, `error`, `message`, then the extras in order.
  Map<String, Object?> object() => {
    'ok': false,
    'error': error,
    'message': message,
    ...extra,
  };

  @override
  String toString() => '$error: $message';
}
