import 'dart:async';
import 'dart:io';
import 'dart:typed_data';

import 'frame.dart';
import 'limit_line.dart';
import 'limits.dart';
import 'tree_stop.dart';

/// What a bounded run ended in. Exactly one of [limit], [startError],
/// [helperExited] or [exitCode] describes the end; the output is the
/// command's own and is only meant to be passed on when there is no limit,
/// no start failure, and [pipesHeld] is false.
class BoundedResult {
  const BoundedResult({
    this.exitCode,
    this.limit,
    this.startError,
    this.helperExited = false,
    this.helperNotStopped = false,
    this.pipesHeld = false,
    this.stdout = const [],
    this.stderr = const [],
  });

  /// The command's own exit status (the helper exits with it).
  final int? exitCode;

  /// The limit that ended the run, if one did.
  final BoundedLimit? limit;

  /// Why the command could not be started (exit 127), if it could not.
  final String? startError;

  /// The helper could not be identified, or exited, before the go (exit 127).
  final bool helperExited;

  /// A limit hit before the helper announced itself and it neither announced
  /// itself nor exited within the stop wait; it was left running (C12). Set
  /// together with [limit].
  final bool helperNotStopped;

  /// A pipe held after command exit fails a review even though BoundedRun keeps
  /// the command's own exit status; callers that pass output on must check
  /// [pipesHeld].
  final bool pipesHeld;

  final List<int> stdout;
  final List<int> stderr;
}

/// One bounded run of a command: its deadline, a byte bound on each of stdout
/// and stderr, and the stop of its whole process tree.
///
/// The helper's frames, `\x00sw-hello ...\n` (its identity) and then
/// `\x00sw-ready ...\n`, are internal: the parent strips both before counting
/// or passing on stderr, and the command starts only after the go byte.
///
/// A [BoundedRun] owns the helper process (`sw __exec -- <command>`), a state
/// machine over its stream subscriptions and its exit future:
///
/// * Starting: the parent reads and strips the hello frame (the tree checks
///   the helper's identity), then the ready frame (the tree contains the
///   helper), then writes `g`, the transport bytes and closes the pipe. A
///   limit before the go stops the helper first and closes the pipe second,
///   and waits for the helper's exit, so the command never starts. A limit
///   before the hello closes the pipe and waits at most [stopWait] for the
///   hello or the exit, else leaves the helper (C12). A missing or malformed
///   frame is a start error; a helper that cannot be identified or exited
///   before the go is `helperExited`.
/// * Running: every chunk is counted per stream into memory (never disk); past
///   the bound both subscriptions are cancelled and the tree is stopped. The
///   exit future races a deadline timer on a monotonic [Stopwatch]: an exit
///   recorded before the deadline keeps its result even if handled later.
/// * Exited: the readers get [readerGrace]; then the tree is stopped if the
///   pipes are still held, setting [BoundedResult.pipesHeld]; the command's own
///   result stands.
/// * Stopping: at most [stopWait] for the helper and pipes, then let go.
class BoundedRun {
  BoundedRun({
    required this.command,
    required this.limits,
    required this.treeFor,
    this.stdinBytes = const [],
    this.rawLine = false,
    List<String>? helperCommand,
    this.preGoFile,
    this.environment,
    this.workingDirectory,
    void Function(String line)? note,
  }) : helperCommand = helperCommand ?? [Platform.resolvedExecutable, '__exec'],
       _note = note ?? stderr.write;

  /// The command and its arguments, as the helper starts them.
  final List<String> command;
  final RunLimits limits;

  /// Bytes written on the command's stdin right after the go byte.
  final List<int> stdinBytes;

  /// [command] is an application and its exact Windows command line (see
  /// `LaunchPlan.rawLine`): the helper is started with `--cmdline`.
  final bool rawLine;

  /// The helper's own command line up to (not including) `--`.
  final List<String> helperCommand;

  final ProcessTreeFactory treeFor;

  /// Test hook `SPECWRIGHT_TEST_PRE_GO`: once the ready frame is consumed, the
  /// parent creates `<file>.reached` and defers the go byte while the file
  /// exists. The deadline keeps running, so it can only delay the start.
  final String? preGoFile;

  /// Constraint C12: when given, this is the whole environment of the helper
  /// and so of the command it starts, with nothing inherited from `sw`: a name
  /// absent from the map is absent in the command, which `includeParentEnvironment`
  /// with overrides cannot do. The helper starts the command with no environment
  /// of its own, so the command inherits the helper's, the map. Null (what
  /// `sw run --bounded` passes) keeps the helper and the command on `sw`'s own
  /// environment.
  final Map<String, String>? environment;

  /// The directory the helper starts in, and so the command it starts, which
  /// takes it from the helper (the helper's `Process.start` and
  /// `CreateProcessW` name no directory of their own). Null: `sw`'s own.
  final String? workingDirectory;

  final void Function(String line) _note;

  Future<BoundedResult> run() async {
    final clock = Stopwatch()..start();
    final firstLimit = Completer<BoundedLimit>();
    void hit(BoundedLimit limit) {
      if (!firstLimit.isCompleted) firstLimit.complete(limit);
    }

    Duration? exitAt;
    final deadline = limits.deadline;
    final deadlineTimer = deadline == null
        ? null
        : Timer(deadline, () {
            final at = exitAt;
            if (at != null && at < deadline) return; // the exit came first
            hit(BoundedLimit.deadlineExceeded);
          });

    final tree = treeFor();
    final Process helper;
    try {
      helper = await Process.start(
        helperCommand.first,
        [...helperCommand.skip(1), if (rawLine) '--cmdline', '--', ...command],
        environment: environment,
        includeParentEnvironment: environment == null,
        workingDirectory: workingDirectory,
      );
    } on ProcessException catch (e) {
      deadlineTimer?.cancel();
      tree.dispose();
      return BoundedResult(startError: 'cannot start the helper: ${e.message}');
    }
    tree.started(helper);

    final out = BytesBuilder(copy: false);
    final err = BytesBuilder(copy: false);
    final parser = FrameParser();
    final helloSettled = Completer<void>(); // hello read, or no hello will come
    final frameSettled = Completer<void>(); // ready read, or no frame will come
    final outDone = Completer<void>();
    final errDone = Completer<void>();
    final readersDone = Future.wait([outDone.future, errDone.future]);
    void settle(Completer<void> c) {
      if (!c.isCompleted) c.complete();
    }

    void count(BytesBuilder buffer, List<int> chunk, int? bound) {
      buffer.add(chunk);
      if (bound != null && buffer.length > bound) {
        hit(BoundedLimit.responseTooLarge);
      }
    }

    final outBound = limits.stdoutCap ?? limits.maxBytes;
    final outSub = helper.stdout.listen(
      (chunk) => count(out, chunk, outBound),
      onError: (Object _) => settle(outDone),
      onDone: () => settle(outDone),
    );
    final errSub = helper.stderr.listen(
      (chunk) {
        final rest = parser.add(chunk);
        if (parser.hello != null) settle(helloSettled);
        if (parser.state == FrameState.ready ||
            parser.state == FrameState.malformed) {
          settle(helloSettled);
          settle(frameSettled);
        }
        if (rest.isNotEmpty) count(err, rest, limits.maxBytes);
      },
      onError: (Object _) => settle(errDone),
      onDone: () {
        parser.close();
        settle(helloSettled);
        settle(frameSettled);
        settle(errDone);
      },
    );

    final exited = Completer<int>();
    unawaited(
      helper.exitCode.then((code) {
        final at = clock.elapsed;
        exitAt = at;
        if (deadline != null && at >= deadline) {
          hit(BoundedLimit.deadlineExceeded);
        }
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

    Future<void> waitForExit() => Future.any<Object?>([
      exited.future,
      Future<int>.delayed(stopWait, () => -1),
    ]);

    // After the go: stop the tree, give the helper at most [stopWait], let go.
    Future<void> stopAndLetGo() async {
      await tree.stop();
      await waitForExit();
    }

    // Before the go the helper is the whole tree: stop it first and close the
    // pipe second, so it cannot exit on end-of-file and free its PID first.
    Future<BoundedResult> limitBeforeGo() async {
      await tree.stop();
      closeControlPipe(); // without the go byte
      await cancelReaders();
      await waitForExit();
      return BoundedResult(limit: await firstLimit.future);
    }

    var letGo = false; // a helper that was never identified: do not signal it
    try {
      // Starting: the hello frame, or a limit.
      await Future.any<Object?>([helloSettled.future, firstLimit.future]);
      if (parser.hello == null && parser.state != FrameState.malformed) {
        // A limit before the helper announced itself: close the pipe without
        // the go, and give the helper the stop wait to announce itself or
        // exit. Nothing is signalled that has not been identified (C12).
        closeControlPipe();
        await Future.any<Object?>([
          helloSettled.future,
          exited.future,
          Future<void>.delayed(stopWait),
        ]);
        final hello = parser.hello;
        if (hello != null && tree.hello(hello)) {
          await tree.stop();
          await waitForExit();
        } else if (hello == null && !exited.isCompleted) {
          letGo = true;
        }
        await cancelReaders();
        return BoundedResult(
          limit: await firstLimit.future,
          helperNotStopped: letGo,
        );
      }
      if (parser.hello == null) {
        // malformed before any hello: another binary answered
        closeControlPipe();
        await cancelReaders();
        await tree.stop(); // acts only on an identified helper (C2, C11)
        return BoundedResult(
          startError: '${parser.problem}: ${parser.received}',
        );
      }
      if (!tree.hello(parser.hello!)) {
        // The helper cannot be identified, or is gone: nothing is assigned or
        // terminated, and no go is written.
        closeControlPipe();
        await cancelReaders();
        if (firstLimit.isCompleted) {
          return BoundedResult(limit: await firstLimit.future);
        }
        return const BoundedResult(helperExited: true);
      }
      if (firstLimit.isCompleted) return await limitBeforeGo();

      // The ready frame, or a limit, or the helper's end.
      await Future.any<Object?>([
        frameSettled.future,
        firstLimit.future,
        exited.future,
      ]);
      if (firstLimit.isCompleted) return await limitBeforeGo();
      if (parser.state != FrameState.ready) {
        closeControlPipe();
        await cancelReaders();
        await tree.stop(); // acts only on an identified helper (C2, C11)
        if (parser.state != FrameState.malformed || parser.missing) {
          // The helper ended between its hello and its ready frame.
          return const BoundedResult(helperExited: true);
        }
        return BoundedResult(
          startError:
              '${parser.problem}'
              '${parser.received.isEmpty ? '' : ': ${parser.received}'}',
        );
      }
      final noJob = tree.ready(parser.ready!);
      if (noJob != null) _note('bounded: no job object: $noJob\n');

      final hold = preGoFile;
      if (hold != null) {
        try {
          File('$hold.reached').writeAsStringSync('');
        } on FileSystemException {
          // a test aid only
        }
        while (!firstLimit.isCompleted &&
            !exited.isCompleted &&
            File(hold).existsSync()) {
          await Future.any<Object?>([
            firstLimit.future,
            exited.future,
            Future<void>.delayed(const Duration(milliseconds: 20)),
          ]);
        }
      }
      if (firstLimit.isCompleted) return await limitBeforeGo();
      if (exited.isCompleted || tree.helperGone) {
        // The helper ended after its frames and before the go: nothing is
        // written to it, and the command never starts.
        closeControlPipe();
        await cancelReaders();
        return const BoundedResult(helperExited: true);
      }

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
      final pipesHeld = !(outDone.isCompleted && errDone.isCompleted);
      if (pipesHeld) {
        // A process started by the command still holds a pipe; mark it in the
        // result while preserving the command's own exit status.
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
          return BoundedResult(limit: limit, pipesHeld: pipesHeld);
        }
      }
      await cancelReaders();
      return BoundedResult(
        exitCode: await exited.future,
        stdout: out.takeBytes(),
        stderr: err.takeBytes(),
        pipesHeld: pipesHeld,
      );
    } finally {
      deadlineTimer?.cancel();
      if (!exited.isCompleted && !letGo) await tree.stop();
      tree.dispose();
    }
  }
}
