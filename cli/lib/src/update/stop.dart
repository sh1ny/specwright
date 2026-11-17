/// A stop of a `sw update` step that reports one error code: the JSON document
/// is `{"ok": false, "error": code, "message": message}` and the exit is 1.
/// The codes and messages are those of `scripts/update.sh` (design D9 of
/// native-cli-update).
class UpdateStop implements Exception {
  UpdateStop(this.code, this.message);

  final String code;
  final String message;

  @override
  String toString() => '$code: $message';
}
