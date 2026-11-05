import 'dart:convert';
import 'dart:io';

import 'frame.dart';

/// What the helper's identity frame says about itself: its creation time on
/// Windows, `-` on POSIX (see `platformHello`).
typedef HelloSource = HelloFrame Function();

/// What the helper's containment step reports: `setsid()` on POSIX, nothing to
/// set up on Windows, where the parent assigns the helper to its job (see
/// `platformContainment`).
typedef Containment = Future<ReadyFrame> Function();

HelloFrame noHello() => const HelloFrame.none();

Future<ReadyFrame> noContainment() async => const ReadyFrame.ok();

/// Test hook `SPECWRIGHT_TEST_HOLD_START=<point>:<file>`: the helper polls
/// while the file exists, at `prehello` (before its hello frame), `before`
/// (after the hello, before it contains itself and writes its ready frame) or
/// `after` (after its ready frame, before it reads the go byte). It can only
/// delay the start, never loosen a limit. While a hold is configured the
/// helper also writes its PID to `<file>.pid` when it reaches the hold, and
/// its exit status to `<file>.exit` when it ends, so a test can find and judge
/// it. Returns the path to hold at [point], or null.
String? holdFile(String point, Map<String, String> env) {
  final value = env['SPECWRIGHT_TEST_HOLD_START'];
  if (value == null || !value.startsWith('$point:')) return null;
  final path = value.substring(point.length + 1);
  return path.isEmpty ? null : path;
}

/// The file `SPECWRIGHT_TEST_HOLD_START` names, whatever the point.
String? _anyHoldFile(Map<String, String> env) {
  final value = env['SPECWRIGHT_TEST_HOLD_START'];
  if (value == null) return null;
  final colon = value.indexOf(':');
  if (colon < 0) return null;
  final path = value.substring(colon + 1);
  return path.isEmpty ? null : path;
}

Future<void> _hold(String? path) async {
  if (path == null) return;
  try {
    File('$path.pid').writeAsStringSync('$pid');
  } on FileSystemException {
    // a test aid only
  }
  while (File(path).existsSync()) {
    await Future<void>.delayed(const Duration(milliseconds: 20));
  }
}

/// `sw __exec -- <cmd...>`: the helper side of the startup protocol.
///
/// It writes its identity frame as the first bytes on stderr, contains itself
/// (`setsid()` on POSIX), writes the ready frame, and blocks on one byte of
/// stdin. It starts the command only on `g`, with all three streams inherited
/// (the command reads the rest of the control pipe as its stdin). End-of-file
/// or any other byte exits 125 and starts nothing, and so does a failed write
/// of a frame (the parent is gone). A command that cannot start exits 127 with
/// the reason on stderr. The helper exits with the command's status.
Future<int> runExecHelper(
  List<String> args, {
  HelloSource hello = noHello,
  Containment contain = noContainment,
  Map<String, String>? env,
}) async {
  final environment = env ?? Platform.environment;
  final code = await _run(args, hello, contain, environment);
  final record = _anyHoldFile(environment);
  if (record != null) {
    try {
      File('$record.exit').writeAsStringSync('$code');
    } on FileSystemException {
      // a test aid only
    }
  }
  return code;
}

Future<int> _run(
  List<String> args,
  HelloSource hello,
  Containment contain,
  Map<String, String> environment,
) async {
  if (args.isEmpty || args.first != '--') return 2;
  final command = args.sublist(1);
  if (command.isEmpty) return 2;

  await _hold(holdFile('prehello', environment));
  try {
    stderr.add(hello().encode());
    await stderr.flush();
  } on Object {
    return 125; // the parent is gone
  }
  await _hold(holdFile('before', environment));
  try {
    stderr.add((await contain()).encode());
    await stderr.flush();
  } on Object {
    return 125;
  }
  if (environment['SPECWRIGHT_TEST_HELPER_EXIT'] == 'after-ready') return 3;
  await _hold(holdFile('after', environment));

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
