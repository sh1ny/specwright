import 'dart:io';
import 'dart:math';

import '../settings/values.dart' show pyUtf8Decode;
import '../update/exclusive_mkdir.dart' show createDirectoryExclusive;

// The store gate lock, shared by `sw gate` and `sw update` (design D6 of
// native-cli-retire-scripts): a directory made exclusively, holding an `owner`
// file of `time:`, `change:`, `code:` and `token:` lines. The form is the one
// the inline shell lock and `sw update` already use (invariant C1).

/// The fields of a gate lock's `owner` file.
class GateOwner {
  const GateOwner({
    this.change = '',
    this.code = '',
    this.token = '',
    this.time = '',
  });

  final String change;
  final String code;
  final String token;
  final String time;

  /// `gate_holder`.
  String get holder =>
      '${change.isEmpty ? 'an unknown holder' : change}'
      '${code.isEmpty ? '' : ' (from $code)'}'
      '${time.isEmpty ? '' : ', taken $time'}';

  Map<String, Object?> toJson() => {
    'time': time,
    'change': change,
    'code': code,
    'token': token,
  };
}

/// `gate_read`: the fields of `<dir>/owner` (all empty when there is none).
GateOwner gateRead(String dir) {
  final file = File('$dir/owner');
  if (!file.existsSync()) return const GateOwner();
  var change = '', code = '', token = '', time = '';
  for (var line in pyUtf8Decode(file.readAsBytesSync()).split('\n')) {
    if (line.endsWith('\r')) line = line.substring(0, line.length - 1);
    if (line.startsWith('change: ')) change = line.substring(8);
    if (line.startsWith('code: ')) code = line.substring(6);
    if (line.startsWith('token: ')) token = line.substring(7);
    if (line.startsWith('time: ')) time = line.substring(6);
  }
  return GateOwner(change: change, code: code, token: token, time: time);
}

/// A fresh random token: 16 hex digits and the process id.
String gateToken() {
  final rng = Random.secure();
  String word(int v) => v.toRadixString(16).padLeft(8, '0');
  return word((rng.nextInt(1 << 15) << 15) | rng.nextInt(1 << 15)) +
      word((rng.nextInt(1 << 15) << 15) | rng.nextInt(1 << 15)) +
      word(pid);
}

String _ownerText(String change, String code, String token) {
  final now = DateTime.now().toUtc().toIso8601String().replaceFirst(
    RegExp(r'\.\d+Z$'),
    'Z',
  );
  return 'time: $now\nchange: $change\ncode: $code\ntoken: $token\n';
}

/// `gate_write_owner`: the owner file of a lock a store update holds.
void gateWriteOwner(
  String gate,
  String from,
  String to,
  String code,
  String token,
) {
  File('$gate/owner').writeAsStringSync(
    _ownerText('specwright-update $from -> $to', code, token),
  );
}

Map<String, Object?> _fail(String error, String message, GateOwner owner) => {
  'ok': false,
  'error': error,
  'message': message,
  'owner': owner.toJson(),
};

/// `sw gate lock`: makes [lock] exclusively, then places its owner file whole
/// by renaming a finished temporary file into it. [beforeRename] runs between
/// the two (a test stands in for a kill there).
(Map<String, Object?>, int) gateLock(
  String lock,
  String branch,
  String code, {
  void Function()? beforeRename,
}) {
  if (!createDirectoryExclusive(lock)) {
    final o = gateRead(lock);
    return (
      _fail(
        'gate_locked',
        'the store gate lock $lock is held by ${o.holder}',
        o,
      ),
      1,
    );
  }
  final token = gateToken();
  final temporary = File('$lock/owner.$token.tmp')
    ..writeAsStringSync(_ownerText(branch, code, token));
  beforeRename?.call();
  temporary.renameSync('$lock/owner');
  return (
    {
      'ok': true,
      'lock': lock,
      'token': token,
      'owner': gateRead(lock).toJson(),
    },
    0,
  );
}

/// `sw gate show`: whether [lock] exists and, when it does, its owner.
Map<String, Object?> gateShow(String lock) {
  final held = Directory(lock).existsSync();
  return {
    'ok': true,
    'lock': lock,
    'held': held,
    if (held) 'owner': gateRead(lock).toJson(),
  };
}

/// `sw gate unlock`: removes [lock] when its owner token is [token]. With
/// [stale] it is the user's word that the lock is left over: [ownerless] stands
/// for a lock without a token, and a store update's lock is refused. The check
/// and the removal are not atomic, as the `rm -r` they replace was not.
(Map<String, Object?>, int) gateUnlock(
  String lock, {
  String? token,
  bool stale = false,
  bool ownerless = false,
}) {
  if (!Directory(lock).existsSync()) {
    return ({'ok': true, 'lock': lock, 'removed': false}, 0);
  }
  final o = gateRead(lock);
  if (stale && o.change.startsWith('specwright-update')) {
    final doc = _fail(
      'gate_update_held',
      'the store gate lock is held by a store update from '
          '${o.code.isEmpty ? 'another checkout' : o.code}; rerun the update '
          'there',
      o,
    );
    return (doc..['code'] = o.code, 1);
  }
  final mine = ownerless ? o.token.isEmpty : o.token == token;
  if (!mine) {
    return (
      _fail(
        'gate_not_owner',
        'the store gate lock is held by ${o.holder}, not by the given token',
        o,
      ),
      1,
    );
  }
  Directory(lock).deleteSync(recursive: true);
  return ({'ok': true, 'lock': lock, 'removed': true}, 0);
}
