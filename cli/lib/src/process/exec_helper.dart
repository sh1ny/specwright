import 'dart:convert';
import 'dart:io';

import 'frame.dart';

/// What the helper's containment step reports. Task group 5 fills this seam
/// with a job-object join (Windows) or `setsid()` (POSIX); until then nothing
/// is contained and the frame says `ok`.
typedef Containment = Future<ReadyFrame> Function(String? jobHandle);

Future<ReadyFrame> noContainment(String? jobHandle) async =>
    const ReadyFrame.ok();

/// `sw __exec [--job-handle <h>] -- <cmd...>`: the helper side of the startup
/// protocol. It contains itself, writes the ready frame as the first bytes on
/// stderr, blocks on one byte of stdin, and starts the command only on `g`,
/// with all three streams inherited (the command reads the rest of the control
/// pipe as its stdin). End-of-file or any other byte exits 125 and starts
/// nothing. A command that cannot start exits 127 with the reason on stderr.
/// The helper exits with the command's status.
Future<int> runExecHelper(
  List<String> args, {
  Containment contain = noContainment,
}) async {
  String? jobHandle;
  var i = 0;
  while (i < args.length && args[i] != '--') {
    if (args[i] == '--job-handle' && i + 1 < args.length) {
      jobHandle = args[i + 1];
      i += 2;
    } else {
      return 2;
    }
  }
  final command = i < args.length ? args.sublist(i + 1) : <String>[];
  if (command.isEmpty) return 2;

  final frame = await contain(jobHandle);
  stderr.add(frame.encode());
  await stderr.flush();

  // Exactly one byte: a buffered read would take the transport bytes that
  // follow it, which belong to the command.
  final go = stdin.readByteSync();
  if (go != 0x67) return 125;

  final Process process;
  try {
    process = await Process.start(
      command.first,
      command.sublist(1),
      mode: ProcessStartMode.inheritStdio,
    );
  } on ProcessException catch (e) {
    stderr.add(
      utf8.encode(
        'bounded: cannot start ${command.first}: ${e.message.trim()}\n',
      ),
    );
    await stderr.flush();
    return 127;
  }
  return process.exitCode;
}
