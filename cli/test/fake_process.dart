// A scripted stand-in for `dart:io`'s `Process`, for the tests of what the
// launchers do with a pipe error (C49). It starts nothing, so no real process
// or PID is ever involved: tests inject it through the `startProcess:` seam
// and a `NoopTree`, which never signals anything.
import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:specwright_cli/src/process/frame.dart';
import 'package:specwright_cli/src/process/tree_stop.dart';

/// Records what is written to the process's stdin.
class FakeStdin implements IOSink {
  final bytes = <int>[];
  final _done = Completer<void>();
  bool closed = false;

  @override
  Encoding encoding = utf8;

  @override
  void add(List<int> data) => bytes.addAll(data);

  @override
  void write(Object? object) => bytes.addAll(encoding.encode('$object'));

  @override
  Future<void> close() async {
    closed = true;
    if (!_done.isCompleted) _done.complete();
  }

  @override
  Future<void> get done => _done.future;

  @override
  Future<void> flush() async {}

  @override
  dynamic noSuchMethod(Invocation invocation) => null;
}

class FakeProcess implements Process {
  FakeProcess({this.pid = 4242});

  @override
  final int pid;

  final stdoutController = StreamController<List<int>>();
  final stderrController = StreamController<List<int>>();
  final fakeStdin = FakeStdin();
  final _exit = Completer<int>();

  @override
  Stream<List<int>> get stdout => stdoutController.stream;

  @override
  Stream<List<int>> get stderr => stderrController.stream;

  @override
  IOSink get stdin => fakeStdin;

  @override
  Future<int> get exitCode => _exit.future;

  /// The process exits with [code].
  void exit(int code) {
    if (!_exit.isCompleted) _exit.complete(code);
  }

  @override
  bool kill([ProcessSignal signal = ProcessSignal.sigterm]) {
    exit(-1);
    return true;
  }

  /// The go byte (`g`) has been written to stdin.
  bool get goWritten => fakeStdin.bytes.contains(0x67);

  /// The helper's frames: identity, then ready.
  void frames() {
    stderrController.add(const HelloFrame.none().encode());
    stderrController.add(const ReadyFrame.ok().encode());
  }

  /// Waits (bounded) until the go byte has been written.
  Future<void> untilGo() async {
    for (var i = 0; i < 200 && !goWritten; i++) {
      await Future<void>.delayed(const Duration(milliseconds: 10));
    }
    if (!goWritten) throw StateError('the go byte was never written');
  }

  /// Gives the parent a moment to act, for "nothing was written" checks.
  Future<void> settle() =>
      Future<void>.delayed(const Duration(milliseconds: 150));
}

/// A tree that records its calls and acts on nothing.
class NoopTree implements ProcessTree {
  final calls = <String>[];

  @override
  void started(Process helper) => calls.add('started');

  @override
  bool hello(HelloFrame frame) {
    calls.add('hello');
    return true;
  }

  @override
  String? ready(ReadyFrame frame) {
    calls.add('ready');
    return null;
  }

  @override
  bool get helperGone => false;

  @override
  Future<void> stop() async => calls.add('stop');

  @override
  void dispose() => calls.add('dispose');
}

/// A `startProcess:` seam that returns [process] and records the start.
class FakeStarter {
  FakeStarter(this.process);

  final FakeProcess process;
  final starts = <(String, List<String>)>[];

  Future<Process> call(
    String executable,
    List<String> arguments, {
    Map<String, String>? environment,
    bool includeParentEnvironment = true,
    String? workingDirectory,
  }) async {
    starts.add((executable, arguments));
    return process;
  }
}
