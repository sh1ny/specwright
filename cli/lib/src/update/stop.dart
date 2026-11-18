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

/// A stop of the update lifecycle (stage, swap, note-config, finish, recover
/// and the recovery `plan` runs first), reported as `update.sh`'s `die` did:
/// the base members of every report (`ok`, `interface`, `installed`,
/// `unchanged`), then `error`, `message` and [extra]. A [plain] stop has no
/// base members: it is the one the journal reader reports, and it never says
/// whether an installed file changed.
class UpdateDie extends UpdateStop {
  UpdateDie(
    super.code,
    super.message, {
    this.extra = const {},
    this.plain = false,
  });

  /// A [stop] reported as a die.
  factory UpdateDie.from(UpdateStop stop) =>
      stop is UpdateDie ? stop : UpdateDie(stop.code, stop.message);

  final Map<String, Object?> extra;
  final bool plain;
}
