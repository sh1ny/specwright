import 'dart:io';
import 'dart:typed_data';

import '../commit/paths.dart';
import '../vcs/codec.dart';
import '../vcs/tool_runner.dart';
import 'gh.dart';
import 'text.dart';

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

/// One external tool run through bash (`mktemp`, `ln`, `sleep`, `date`, `python3`).
typedef PrTool = Future<ToolResult> Function(List<String> command);

/// One bounded run of a command that is not `gh` (`reviewers.py`).
typedef PrBounded = Future<GhResult> Function(
  List<String> command, {
  Map<String, String>? environment,
});

/// `mktemp [template]`: its path, usable by `sw` (on Windows in the drive form), or null when it failed.
typedef PrMakeTemp = Future<String?> Function([String? template]);

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
    this._tool,
    this._bounded,
    this._makeTemp,
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
  final PrTool? _tool;
  final PrBounded? _bounded;
  final PrMakeTemp? _makeTemp;
  final int Function()? _seconds;
  final Stopwatch _clock = Stopwatch()..start();
  String? _python;

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
    bash,
    cwd,
    args,
    environment: environment,
    paged: paged,
    helperCommand: helperCommand,
  );

  /// A command that is not `gh` (`reviewers.py`), bounded the same way.
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
    bash,
    cwd,
    command,
    environment: environment,
    helperCommand: helperCommand,
  );

  /// An external tool, unbounded, through bash (D8).
  Future<ToolResult> tool(List<String> command) => (_tool ?? _runTool)(command);

  Future<ToolResult> _runTool(List<String> command) =>
      runTool(bash, cwd, command, environment: environment);

  /// `mktemp [template]` through bash, with the path converted by `cygpath -m` in the same bash call on Windows, so
  /// `sw` and Python can open it. Null when `mktemp` failed.
  Future<String?> makeTemp([String? template]) async {
    final seam = _makeTemp;
    if (seam != null) return seam(template);
    const script =
        r'f=$(mktemp "$@") || exit 1; '
        r'if command -v cygpath >/dev/null 2>&1; then cygpath -m "$f"; '
        r'else printf "%s\n" "$f"; fi';
    final r = await tool([bash, '-c', script, 'mktemp', ?template]);
    if (r.exitCode != 0) return null;
    return dropTrailingNewlines(decodeEscaped(r.stdout));
  }

  /// The first of `python3` and `python` that is Python 3.8 or later (the shim's own probe), or null.
  Future<String?> python() async {
    if (_python != null) return _python;
    for (final c in const ['python3', 'python']) {
      final r = await tool([
        c,
        '-c',
        'import sys; sys.exit(sys.version_info < (3, 8))',
      ]);
      if (r.exitCode == 0) return _python = c;
    }
    return null;
  }

  /// A path argument in the form `sw` can open: on Windows a `/` path goes through `cygpath -m` (D9).
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
