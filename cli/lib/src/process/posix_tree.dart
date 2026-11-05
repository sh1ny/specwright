import 'dart:io';

import '../native/libc.dart' as libc;
import 'frame.dart';
import 'tree_stop.dart';

/// The POSIX tree of one run: the helper calls `setsid()` and so leads a new
/// session and process group whose ID is its PID; a limit sends SIGKILL to
/// that group (D6).
///
/// Dart exposes no process handle and reaps its children itself, so the
/// helper's PID cannot be pinned (C11). The tree signals the group and the PID
/// only while it has not yet seen the helper exit (the group exists once the
/// helper has called `setsid()`; a PID is never handed out while it names a
/// live process group), and the group alone afterwards.
///
/// When the test hook `SPECWRIGHT_TEST_SPAWN_DIR` names a directory, an empty
/// file named after the helper's PID is created there after the ready frame
/// and before the go, so the eval runner's sweep can stop the group if the
/// test file is interrupted. A failed write is ignored; without the variable
/// nothing is written.
class PosixTree implements ProcessTree {
  PosixTree(Map<String, String> env)
    : _spawnDir = env['SPECWRIGHT_TEST_SPAWN_DIR'];

  final String? _spawnDir;
  Process? _helper;
  bool _exited = false;

  @override
  void started(Process helper) {
    _helper = helper;
    helper.exitCode.then((_) => _exited = true);
  }

  @override
  bool hello(HelloFrame frame) => true;

  @override
  String? ready(ReadyFrame frame) {
    final dir = _spawnDir;
    final helper = _helper;
    if (dir != null && dir.isNotEmpty && helper != null) {
      try {
        File('$dir${Platform.pathSeparator}${helper.pid}').createSync();
      } on FileSystemException {
        // a record is a test aid only
      }
    }
    return frame.jobReason;
  }

  @override
  bool get helperGone => _exited;

  @override
  Future<void> stop() async {
    final helper = _helper;
    if (helper == null) return;
    libc.kill(-helper.pid, libc.sigkill);
    if (!_exited) helper.kill(ProcessSignal.sigkill);
  }

  @override
  void dispose() {}
}
