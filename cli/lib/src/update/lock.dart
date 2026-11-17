import 'dart:io' hide pid;
import 'dart:io' as io show pid;

import '../native/kernel32.dart' as k32;
import '../native/libc.dart' as libc;
import 'file_ops.dart';

/// Another update holds the lock (or just took it): reported as `locked`.
class UpdateLocked implements Exception {
  UpdateLocked(this.message);

  final String message;

  String get code => 'locked';

  @override
  String toString() => message;
}

/// How old a lock directory with no complete owner file must be before it is
/// taken over: a run that made the directory is given this long to write its
/// owner file.
const Duration _ownerlessAge = Duration(seconds: 60);

/// The update lock: `<code>/openspec/.specwright/update.lock`, a directory
/// made with `mkdir` that holds an `owner` file of two lines, `pid: <n>` and
/// `host: <name>` (`scripts/update.sh`, which an older prompt may still run on
/// the same checkout). A lock held by a dead pid on this host is replaced and
/// reported in [replaced] as `lock_replaced`; so is a lock with no complete
/// owner file (pid and host) once the directory is older than 60 s (reason
/// `lock_without_owner`); any other holder stops the run with [UpdateLocked].
///
/// Taking over a stale lock is two steps, as in `update.sh`: two runs may
/// judge the same stale lock, and one may take it afresh before the other
/// acts, so the lock is renamed aside first (only one rename succeeds) and the
/// renamed directory is judged again. Still stale: removed, and the `mkdir`
/// is tried again. Taken since: put back, and reported as locked.
///
/// Every file operation goes through [UpdateFileOps], so the interruption
/// matrix sees it. The owner file is written with plain I/O, as the shell
/// script's redirect was.
class UpdateLock {
  /// [hostname], [pid], [isAlive] and [now] are test seams; they default to
  /// the host (`$HOSTNAME`, else the machine's name), this process, the
  /// operating system's process check and the clock.
  UpdateLock(
    this.stateDir,
    this._ops, {
    this._hostname,
    int? pid,
    bool Function(int pid)? isAlive,
    DateTime Function()? now,
  }) : _pid = pid ?? io.pid,
       _isAlive = isAlive ?? processIsAlive,
       _now = now ?? DateTime.now;

  /// `<code>/openspec/.specwright`.
  final String stateDir;

  final UpdateFileOps _ops;
  final String? _hostname;
  final int _pid;
  final bool Function(int pid) _isAlive;
  final DateTime Function() _now;
  bool _held = false;
  Map<String, Object?>? _replaced;

  String get path => '$stateDir/update.lock';

  /// `{pid, host}` of a dead owner whose lock was replaced, or `{pid: null,
  /// host: null, reason: lock_without_owner}` for an ownerless one; null when
  /// the lock was free.
  Map<String, Object?>? get replaced => _replaced;

  /// Takes the lock, or throws [UpdateLocked].
  void acquire() {
    final host = _hostname ?? _localHost();
    _ops.mkdir(stateDir);
    var tries = 0;
    while (!_ops.mkdirExclusive(path)) {
      final (:pid, host: ownerHost) = _readOwner(path);
      tries++;
      final number = pid != null && RegExp(r'^[0-9]+$').hasMatch(pid)
          ? int.tryParse(pid)
          : null;
      if (tries <= 3 &&
          ownerHost == host &&
          number != null &&
          !_isAlive(number)) {
        if (_claimStale(dead: true, pid: pid, host: ownerHost)) {
          _replaced = {'pid': number, 'host': ownerHost};
        }
        continue;
      }
      // lock_without_owner: killed between the mkdir and the owner write.
      // Within the acquisition window (60 s) the lock may be a run midway
      // through taking it, so it stays "locked"; an older ownerless lock is
      // stale and taken over.
      if (tries <= 3 &&
          (pid == null ||
              pid.isEmpty ||
              ownerHost == null ||
              ownerHost.isEmpty) &&
          _isOld(path)) {
        if (_claimStale(dead: false)) {
          _replaced = {
            'pid': null,
            'host': null,
            'reason': 'lock_without_owner',
          };
        }
        continue;
      }
      throw UpdateLocked(_heldMessage(pid, ownerHost));
    }
    _held = true;
    File('$path/owner').writeAsStringSync('pid: $_pid\nhost: $host\n');
  }

  /// Gives the lock up when this run holds it; otherwise does nothing.
  void release() {
    if (!_held) return;
    _held = false;
    _ops.remove(path);
  }

  /// Takes over the stale lock [acquire] just judged. True: it was stale and
  /// is removed (the caller tries the `mkdir` again). False: another run
  /// moved or removed it first (the caller just tries again). Throws
  /// [UpdateLocked] when the renamed lock turns out to be a live run's.
  bool _claimStale({required bool dead, String? pid, String? host}) {
    final aside = '$path.stale.$_pid';
    try {
      _ops.rename(path, aside);
    } on FileSystemException {
      return false;
    }
    final (pid: p, host: h) = _readOwner(aside);
    final bool stale;
    if (dead) {
      stale = p == pid && h == host && !_isAlive(int.parse(p!));
    } else {
      stale =
          (p == null || p.isEmpty || h == null || h.isEmpty) && _isOld(aside);
    }
    if (stale) {
      _ops.remove(aside);
      return true;
    }
    // A third run may have taken the lock meanwhile. The aside copy is then
    // left where it is and that run keeps its lock.
    if (!_putBack(aside)) {
      throw UpdateLocked(
        'another update took $path while this run was replacing a stale '
        'lock; its lock was left at $aside',
      );
    }
    throw UpdateLocked(_heldMessage(p, h));
  }

  bool _putBack(String aside) {
    if (FileSystemEntity.typeSync(path, followLinks: false) !=
        FileSystemEntityType.notFound) {
      return false;
    }
    try {
      _ops.rename(aside, path);
      return true;
    } on FileSystemException {
      return false;
    }
  }

  String _heldMessage(String? pid, String? host) =>
      'another update holds $path '
      '(pid ${pid == null || pid.isEmpty ? 'unknown' : pid} on '
      '${host == null || host.isEmpty ? 'unknown host' : host}); '
      'wait for it to finish';

  bool _isOld(String directory) {
    final stat = FileStat.statSync(directory);
    if (stat.type != FileSystemEntityType.directory) return false;
    return _now().difference(stat.modified) > _ownerlessAge;
  }
}

/// The `pid:` and `host:` lines of [lock]'s owner file (the last of each);
/// null for a line that is not there or no owner file.
({String? pid, String? host}) _readOwner(String lock) {
  String? pid, host;
  final file = File('$lock/owner');
  if (file.existsSync()) {
    for (final line in file.readAsStringSync().split('\n')) {
      if (line.startsWith('pid: ')) pid = line.substring(5);
      if (line.startsWith('host: ')) host = line.substring(6);
    }
  }
  return (pid: pid, host: host);
}

/// `${HOSTNAME:-$(hostname)}`, the name `update.sh` wrote and compared.
String _localHost() {
  final fromEnvironment = Platform.environment['HOSTNAME'];
  return fromEnvironment == null || fromEnvironment.isEmpty
      ? Platform.localHostname
      : fromEnvironment;
}

/// Whether process [pid] is running, as `kill -0` answers on POSIX (a process
/// this user may not signal counts as gone, as it does there) and as a
/// zero-timeout wait on a process handle on Windows.
bool processIsAlive(int pid) {
  if (!Platform.isWindows) return libc.kill(pid, 0);
  final handle = k32.openProcess(
    k32.synchronize | k32.processQueryLimitedInformation,
    pid,
  );
  if (handle == 0) return false;
  try {
    return k32.isProcessRunning(handle);
  } finally {
    k32.closeHandle(handle);
  }
}
