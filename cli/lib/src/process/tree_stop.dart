import 'dart:io';

import 'frame.dart';

/// Stops the helper and everything it started: a job object and a pinned
/// process handle on Windows (`WindowsTree`), a process group on POSIX
/// (`PosixTree`).
///
/// Life cycle: [started] gets the helper, [hello] its identity frame (before
/// anything is done to it), [ready] its ready frame (before the go), and
/// [stop] may be called any time after [hello] (more than once, and after the
/// helper exited). [dispose] ends the run.
abstract interface class ProcessTree {
  /// The helper has started.
  void started(Process helper);

  /// The helper's identity frame has been read. False when the helper cannot
  /// be identified as the process that wrote it (Windows: the PID's creation
  /// time differs, the process cannot be opened, or it has exited): the tree
  /// has closed whatever it opened and will act on nothing.
  bool hello(HelloFrame frame);

  /// The helper's ready frame has been read; the command has not started.
  /// Puts the helper under the tree's containment. Returns the reason the
  /// tree could not contain it (to announce as `bounded: no job object:`), or
  /// null when it did.
  String? ready(ReadyFrame frame);

  /// Whether the helper has exited, as far as the tree can tell.
  bool get helperGone;

  /// Stops the tree. Before the go the helper is the whole tree.
  Future<void> stop();

  /// Releases what the tree holds. It never stops anything.
  void dispose();
}

/// Builds the [ProcessTree] of one run, before its helper starts.
typedef ProcessTreeFactory = ProcessTree Function();
