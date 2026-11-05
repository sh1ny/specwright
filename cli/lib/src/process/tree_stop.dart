import 'dart:io';

/// Stops the helper and everything it started. Task group 5 supplies the
/// implementations that cover orphans: a job object on Windows, a process
/// group on POSIX. [PidTree] is the by-PID fallback used until then and for a
/// Windows run without a job.
abstract interface class ProcessTree {
  /// Stops the tree. Safe to call more than once and after it has exited.
  Future<void> stop();
}

/// Builds the [ProcessTree] for a started helper once its ready frame says
/// whether containment holds (`hasJob`). Before the frame arrives, a limit
/// stops the helper alone, which is the whole tree then.
typedef ProcessTreeFactory = ProcessTree Function(Process helper);

/// Stops by PID: `taskkill /T /F` on Windows, SIGKILL elsewhere. It misses a
/// descendant whose parent already exited; containment is what closes that.
class PidTree implements ProcessTree {
  PidTree(this.helper);

  final Process helper;

  @override
  Future<void> stop() async {
    if (Platform.isWindows) {
      try {
        await Process.run('taskkill', ['/T', '/F', '/PID', '${helper.pid}']);
      } on ProcessException {
        // fall through to the direct kill
      }
    }
    helper.kill(ProcessSignal.sigkill);
  }
}
