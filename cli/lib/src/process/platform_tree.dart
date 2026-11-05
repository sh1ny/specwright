import 'dart:io';

import '../native/kernel32.dart' as k32;
import '../native/libc.dart' as libc;
import 'exec_helper.dart';
import 'frame.dart';
import 'posix_tree.dart';
import 'tree_stop.dart';
import 'windows_tree.dart';

/// The [ProcessTree] for this operating system.
ProcessTree platformTree(Map<String, String> env) =>
    Platform.isWindows ? WindowsTree.native(env) : PosixTree(env);

/// The helper's identity frame for this operating system: its own creation
/// time on Windows (the 64-bit FILETIME), `-` on POSIX.
HelloSource platformHello() => Platform.isWindows ? _windowsHello : noHello;

HelloFrame _windowsHello() {
  final created = k32.processCreationTime(k32.getCurrentProcess());
  return created == null ? const HelloFrame.none() : HelloFrame('$created');
}

/// The helper's containment step for this operating system. On Windows there
/// is nothing to set up: the parent assigns the helper to its job.
Containment platformContainment() =>
    Platform.isWindows ? noContainment : _posixContainment;

Future<ReadyFrame> _posixContainment() async {
  if (!libc.setsid()) return const ReadyFrame.noJob('setsid failed');
  return const ReadyFrame.ok();
}
