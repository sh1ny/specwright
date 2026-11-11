import 'dart:async';
import 'dart:io';
import 'dart:math';
import 'dart:typed_data';

import '../commit/paths.dart';
import '../native/libc.dart' as libc;
import '../vcs/codec.dart';
import '../vcs/scripts.dart' show TextResult, runText;
import 'gh.dart';
import 'text.dart';

const String _tempAlphabet =
    'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';

/// `exit <code>` inside the scripts: unwinds to the command's entry, which runs its cleanup first.
class PrExit implements Exception {
  PrExit(this.code);

  final int code;

  @override
  String toString() => 'exit $code';
}

/// One `gh` call. [environment] is the whole environment of the call (null: `sw`'s own).
typedef PrGh = Future<GhResult> Function(
  List<String> args, {
  Map<String, String>? environment,
  bool paged,
});

/// One bounded run of a command that is not `gh` (`sw pr reviewers`).
typedef PrBounded = Future<GhResult> Function(
  List<String> command, {
  Map<String, String>? environment,
});

/// One `git <args>` run in a directory (the settings commands), its output decoded as text.
typedef PrGit = Future<TextResult> Function(String dir, List<String> args);

/// `mktemp [template]`: its path, usable by `sw` (on Windows in the drive form), or null when it failed.
typedef PrMakeTemp = Future<String?> Function([String? template]);

/// A pause of [seconds] whole seconds (`sleep`).
typedef PrSleep = Future<void> Function(int seconds);

/// What the shim handed `sw pr snapshot` or `sw pr reply` on stdin: the scripts directory, the bash that runs the shim
/// and every argument of the script. Unlike [parseHandoff], no argument at all is a handoff too (`pr-snapshot.sh` with
/// no arguments reads the current branch's PR). Null when the bytes are not NUL-terminated records or hold fewer than
/// two.
({String scriptsDir, String bash, List<String> args})? parsePrHandoff(
  List<int> stdin,
) {
  if (stdin.isNotEmpty && stdin.last != 0) return null;
  final bytes = Uint8List.fromList(stdin);
  final records = <String>[];
  var start = 0;
  for (var i = 0; i < bytes.length; i++) {
    if (bytes[i] == 0) {
      records.add(decodeEscaped(Uint8List.sublistView(bytes, start, i)));
      start = i + 1;
    }
  }
  if (records.length < 2) return null;
  return (scriptsDir: records[0], bash: records[1], args: records.sublist(2));
}

/// Everything one `sw pr` command runs against: the scripts directory and bash of the handoff, the output streams and
/// the four kinds of external call. The seams are what the tests replace; by default a call runs for real.
class PrContext {
  PrContext({
    required this.scriptsDir,
    required this.bash,
    required this.writeOut,
    required this.writeErr,
    this.environment,
    this.helperCommand,
    this._gh,
    this._git,
    this._bounded,
    this._makeTemp,
    this._sleep,
    this._seconds,
    String? cwd,
  }) : cwd = cwd ?? Directory.current.path;

  final String scriptsDir;
  final String bash;
  final void Function(List<int> bytes) writeOut;
  final void Function(List<int> bytes) writeErr;

  /// The whole environment of every call; null keeps `sw`'s own.
  final Map<String, String>? environment;
  final List<String>? helperCommand;
  final String cwd;
  final PrGh? _gh;
  final PrGit? _git;
  final PrBounded? _bounded;
  final PrMakeTemp? _makeTemp;
  final PrSleep? _sleep;
  final int Function()? _seconds;
  final Stopwatch _clock = Stopwatch()..start();

  /// bash's `$SECONDS`: whole seconds on a monotonic clock since the command began.
  int elapsedSeconds() => (_seconds ?? () => _clock.elapsed.inSeconds)();

  /// The environment the commands read (`SPECWRIGHT_STATE_DIR`, `HOME`): the given one, else `sw`'s own.
  Map<String, String> get env => environment ?? Platform.environment;

  void out(String text) => writeOut(encodeEscaped(text));
  void err(String text) => writeErr(encodeEscaped(text));

  /// `gh <args>`, bounded (D6).
  Future<GhResult> gh(
    List<String> args, {
    Map<String, String>? environment,
    bool paged = false,
  }) => (_gh ?? _runGh)(
    args,
    environment: environment ?? this.environment,
    paged: paged,
  );

  Future<GhResult> _runGh(
    List<String> args, {
    Map<String, String>? environment,
    bool paged = false,
  }) => runGh(
    cwd,
    args,
    environment: environment,
    paged: paged,
    helperCommand: helperCommand,
  );

  /// A command that is not `gh` (`sw pr reviewers`), bounded the same way.
  Future<GhResult> bounded(
    List<String> command, {
    Map<String, String>? environment,
  }) => (_bounded ?? _runBounded)(
    command,
    environment: environment ?? this.environment,
  );

  Future<GhResult> _runBounded(
    List<String> command, {
    Map<String, String>? environment,
  }) => runBoundedCommand(
    cwd,
    command,
    environment: environment,
    helperCommand: helperCommand,
  );

  /// `sleep <seconds>` (D8): the poll's pause, in process.
  Future<void> sleep(int seconds) =>
      (_sleep ?? (n) => Future<void>.delayed(Duration(seconds: n)))(seconds);

  /// `git <args>` in [dir] (`pr-pair.sh`'s `git(d, ...)`): through bash like every tool, decoded as text. A directory
  /// that cannot be entered is exit 127.
  Future<TextResult> git(String dir, List<String> args) =>
      (_git ?? _runGit)(dir, args);

  Future<TextResult> _runGit(String dir, List<String> args) =>
      runText(dir, ['git', ...args]);

  /// `mktemp [template]` (D8): a new empty file made with an exclusive create, so no other writer holds it. The
  /// [template] ends in at least three `X`, replaced by random letters and digits; without one the file is
  /// `tmp.XXXXXXXXXX` in the system temp directory. The path is in the drive form with `/` separators on Windows, so
  /// `sw` and Python can open it. Null when no file could be made.
  Future<String?> makeTemp([String? template]) async {
    final seam = _makeTemp;
    if (seam != null) return seam(template);
    final text =
        template ??
        '${Directory.systemTemp.path}${Platform.pathSeparator}tmp.XXXXXXXXXX';
    final x = RegExp(r'X{3,}$').firstMatch(text);
    if (x == null) return null;
    final random = Random.secure();
    for (var attempt = 0; attempt < 100; attempt++) {
      final suffix = String.fromCharCodes([
        for (var i = 0; i < x.end - x.start; i++)
          _tempAlphabet.codeUnitAt(random.nextInt(_tempAlphabet.length)),
      ]);
      final path = '${text.substring(0, x.start)}$suffix';
      try {
        if (!Platform.isWindows) {
          // Owner-only from the first instant, as mktemp made it: the file holds PR content in a shared directory.
          if (libc.createExclusive(encodeEscaped(path), 0x180)) return path;
          // A failed create is a collision when something is there; else nothing can be made here.
          if (FileSystemEntity.typeSync(path, followLinks: false) !=
              FileSystemEntityType.notFound) {
            continue;
          }
          return null;
        }
        File(path).createSync(exclusive: true);
        return path.replaceAll(r'\', '/');
      } on PathExistsException {
        continue;
      } on FileSystemException {
        return null;
      }
    }
    return null;
  }

  /// A path argument in the form `sw` can open: on Windows a `/` path converts by the fixed rules of `nativePath` (D7).
  Future<String> native(String path) async {
    try {
      return await nativePath(path, bash, environment: environment);
    } on BadPathException {
      return path;
    }
  }

  /// What gh's stderr shows the caller: the limit line when a limit ended the call, else gh's own bytes.
  void relayErr(GhResult r) {
    if (r.limitLine != null) {
      err(r.limitLine!);
    } else {
      writeErr(r.stderr);
    }
  }

  /// gh's stdout, passed on as the script's own (a call not captured by `$(...)`).
  void relayOut(GhResult r) => writeOut(r.stdout);

  /// `$(gh ...)`: stdout without its trailing newlines.
  String captured(GhResult r) => dropTrailingNewlines(decodeEscaped(r.stdout));
}

/// The file at [path], whose bytes are not UTF-8 text.
File rawFile(String path) => File.fromRawPath(encodeEscaped(path));

/// The directory at [path], whose bytes are not UTF-8 text.
Directory rawDirectory(String path) =>
    Directory.fromRawPath(encodeEscaped(path));

/// `rm -f`.
void removeFile(String? path) {
  if (path == null || path.isEmpty) return;
  try {
    rawFile(path).deleteSync();
  } on FileSystemException {
    // already gone, or not ours to remove
  }
}

/// The script's `trap cleanup EXIT` also ran when a signal ended it; the exit status is 128 plus the signal number.
List<StreamSubscription<ProcessSignal>> cleanupOnSignals(
  void Function() cleanup,
) {
  if (Platform.isWindows) return const [];
  return [
    for (final (signal, number) in [
      (ProcessSignal.sigint, 2),
      (ProcessSignal.sigterm, 15),
      (ProcessSignal.sighup, 1),
    ])
      signal.watch().listen((_) {
        cleanup();
        exit(128 + number);
      }),
  ];
}
