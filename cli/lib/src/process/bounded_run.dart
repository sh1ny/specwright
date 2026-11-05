import 'dart:async';
import 'dart:io';
import 'dart:typed_data';

import 'frame.dart';
import 'limit_line.dart';
import 'limits.dart';
import 'tree_stop.dart';

/// What a bounded run ended in. Exactly one of [limit], [startError] or
/// [exitCode] describes the end; the output is the command's own and is only
/// meant to be passed on when there is no limit and no start error.
class BoundedResult {
  const BoundedResult({
    this.exitCode,
    this.limit,
    this.startError,
    this.stdout = const [],
    this.stderr = const [],
  });

  /// The command's own exit status (the helper exits with it).
  final int? exitCode;

  /// The limit that ended the run, if one did.
  final BoundedLimit? limit;

  /// Why the command could not be started (exit 127), if it could not.
  final String? startError;

  final List<int> stdout;
  final List<int> stderr;
}

/// One bounded run of a command: its deadline, a byte bound on each of stdout
/// and stderr, and the stop of its whole process tree.
///
/// The helper's ready frame (`\x00sw-ready ...\n`) is internal: the parent
/// strips it before counting or passing on stderr, and the command starts only
/// after the go byte.
///
/// A [BoundedRun] owns the helper process (`sw __exec -- <command>`), a state
/// machine over its stream subscriptions and its exit future:
///
/// * Starting: the parent reads and strips the ready frame, then writes `g`,
///   the transport bytes and closes the pipe. A limit before the go closes the
///   pipe without `g`, kills the helper by PID and waits for its exit, so the
///   command never starts. A missing or malformed frame is a start error.
/// * Running: every chunk is counted per stream into memory (never disk); past
///   the bound both subscriptions are cancelled and the tree is stopped. The
///   exit future races a deadline timer on a monotonic [Stopwatch]: an exit
///   recorded before the deadline keeps its result even if handled later.
/// * Exited: the readers get [readerGrace]; then the tree is stopped if the
///   pipes are still held and the command's own result stands.
/// * Stopping: at most [stopWait] for the helper and pipes, then let go.
class BoundedRun {
  BoundedRun({
    required this.command,
    required this.limits,
    this.stdinBytes = const [],
    List<String>? helperCommand,
    this.treeFor = PidTree.new,
    void Function(String line)? note,
  }) : helperCommand = helperCommand ?? [Platform.resolvedExecutable, '__exec'],
       _note = note ?? stderr.write;

  /// The command and its arguments, as the helper starts them.
  final List<String> command;
  final RunLimits limits;

  /// Bytes written on the command's stdin right after the go byte.
  final List<int> stdinBytes;

  /// The helper's own command line up to (not including) `--`.
  final List<String> helperCommand;

  final ProcessTreeFactory treeFor;
  final void Function(String line) _note;

  Future<BoundedResult> run() async {
    final clock = Stopwatch()..start();
    final firstLimit = Completer<BoundedLimit>();
    void hit(BoundedLimit limit) {
      if (!firstLimit.isCompleted) firstLimit.complete(limit);
    }

    Duration? exitAt;
    final deadlineTimer = Timer(limits.deadline, () {
      final at = exitAt;
      if (at != null && at < limits.deadline) return; // the exit came first
      hit(BoundedLimit.deadlineExceeded);
    });

    final Process helper;
    try {
      helper = await Process.start(helperCommand.first, [
        ...helperCommand.skip(1),
        '--',
        ...command,
      ]);
    } on ProcessException catch (e) {
      deadlineTimer.cancel();
      return BoundedResult(startError: 'cannot start the helper: ${e.message}');
    }
    final tree = treeFor(helper);

    final out = BytesBuilder(copy: false);
    final err = BytesBuilder(copy: false);
    final parser = ReadyFrameParser();
    final frameSettled = Completer<void>();
    final outDone = Completer<void>();
    final errDone = Completer<void>();
    final readersDone = Future.wait([outDone.future, errDone.future]);
    void settle(Completer<void> c) {
      if (!c.isCompleted) c.complete();
    }

    void count(BytesBuilder buffer, List<int> chunk) {
      buffer.add(chunk);
      if (buffer.length > limits.maxBytes) hit(BoundedLimit.responseTooLarge);
    }

    final outSub = helper.stdout.listen(
      (chunk) => count(out, chunk),
      onError: (Object _) => settle(outDone),
      onDone: () => settle(outDone),
    );
    final errSub = helper.stderr.listen(
      (chunk) {
        final rest = parser.add(chunk);
        if (parser.state != FrameState.pending) settle(frameSettled);
        if (rest.isNotEmpty) count(err, rest);
      },
      onError: (Object _) => settle(errDone),
      onDone: () {
        parser.close();
        settle(frameSettled);
        settle(errDone);
      },
    );

    final exited = Completer<int>();
    unawaited(
      helper.exitCode.then((code) {
        final at = clock.elapsed;
        exitAt = at;
        if (at >= limits.deadline) hit(BoundedLimit.deadlineExceeded);
        exited.complete(code);
      }),
    );

    void closeControlPipe() {
      unawaited(helper.stdin.close().catchError((Object _) {}));
      unawaited(helper.stdin.done.catchError((Object _) {}));
    }

    Future<void> cancelReaders() async {
      await Future.wait([
        outSub.cancel().catchError((Object _) {}),
        errSub.cancel().catchError((Object _) {}),
      ]);
    }

    // Stops the tree, gives the helper at most [stopWait] to go, lets go.
    Future<void> stopAndLetGo() async {
      await tree.stop();
      await Future.any<Object?>([
        exited.future,
        Future<int>.delayed(stopWait, () => -1),
      ]);
    }

    try {
      // Starting: the ready frame, or a limit.
      await Future.any<Object?>([frameSettled.future, firstLimit.future]);
      if (firstLimit.isCompleted) {
        closeControlPipe(); // without the go byte
        await cancelReaders();
        await stopAndLetGo();
        return BoundedResult(limit: await firstLimit.future);
      }
      if (parser.state != FrameState.ready) {
        closeControlPipe();
        await cancelReaders();
        await stopAndLetGo();
        return BoundedResult(
          startError:
              '${parser.problem}'
              '${parser.received.isEmpty ? '' : ': ${parser.received}'}',
        );
      }
      final jobReason = parser.frame!.jobReason;
      if (jobReason != null) _note('bounded: no job object: $jobReason\n');

      // Go: no limit has hit, and nothing awaits between this check and the
      // write.
      helper.stdin.add([0x67, ...stdinBytes]);
      closeControlPipe();

      // Running.
      await Future.any<Object?>([firstLimit.future, exited.future]);
      if (firstLimit.isCompleted) {
        final limit = await firstLimit.future;
        await cancelReaders();
        await stopAndLetGo();
        return BoundedResult(limit: limit);
      }

      // Exited before the deadline: the readers get the grace period.
      final grace = Completer<void>();
      final graceTimer = Timer(readerGrace, () => settle(grace));
      await Future.any<Object?>([readersDone, firstLimit.future, grace.future]);
      graceTimer.cancel();
      if (firstLimit.isCompleted) {
        final limit = await firstLimit.future;
        await cancelReaders();
        await stopAndLetGo();
        return BoundedResult(limit: limit);
      }
      if (!(outDone.isCompleted && errDone.isCompleted)) {
        // A process the command started still holds a pipe: stop it. The
        // command's own result stands.
        await tree.stop();
        await Future.any<Object?>([
          readersDone,
          firstLimit.future,
          Future<void>.delayed(stopWait),
        ]);
        if (firstLimit.isCompleted) {
          // stderr passed the bound while the tree was being stopped
          final limit = await firstLimit.future;
          await cancelReaders();
          return BoundedResult(limit: limit);
        }
      }
      await cancelReaders();
      return BoundedResult(
        exitCode: await exited.future,
        stdout: out.takeBytes(),
        stderr: err.takeBytes(),
      );
    } finally {
      deadlineTimer.cancel();
      if (!exited.isCompleted) await tree.stop();
    }
  }
}
