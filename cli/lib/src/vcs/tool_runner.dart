import '../process/launch.dart';
import 'codec.dart';
import 'stop.dart';

export '../process/launch.dart' show LaunchResult, Unrepresentable;
export '../process/missing_directory.dart' show missingDirectoryText, pyRepr;

/// What a tool run produced: the exit code and the raw output bytes. Decoding
/// is the caller's choice (see codec.dart). It is the [LaunchResult] of
/// `launch`.
typedef ToolResult = LaunchResult;

/// Runs `command` (tool name first) in [cwd] without a shell ([launch]) and
/// returns its exit code and raw output. [cwd] is absolute (a relative one is
/// taken from this process's directory). [input], if any, is written on the
/// tool's stdin, which is then closed. The environment is the parent's, or
/// [environment] when non-empty. When [cwd] is not a directory, or the tool is
/// not found or cannot start, nothing runs: exit 127, empty stdout and the
/// reason on stderr ([LaunchResult.startFailed]). Input the launcher cannot
/// represent (a NUL, a lone surrogate) is an [Unrepresentable] the caller maps.
///
/// Constraint C2: there is no deadline and no byte bound, matching `vcs.sh`,
/// whose only bound is `but`'s output cap ([runToolCapped]). Adding bounds is
/// a behaviour change for its own change.
///
/// Constraint C3: arguments reach a native tool unchanged, because `launch`
/// hands them to the operating system without a shell, so nothing expands
/// braces or wildcards on Windows and nothing re-reads a byte on POSIX.
Future<ToolResult> runTool(
  String cwd,
  List<String> command, {
  List<int>? input,
  Map<String, String>? environment,
}) => launch(command, cwd: cwd, input: input, environment: environment);

/// [runTool] for `but`: no input, and once stdout holds more than [cap] bytes
/// the child is killed and [ToolResult.outputTooLarge] is set (`but_run`'s
/// `but_output_too_large`). A missing [cwd], a missing tool or a start that
/// fails is the `tool_missing` [VcsStop], `<tool> could not run: <text>`.
Future<ToolResult> runToolCapped(
  String cwd,
  List<String> command, {
  required int cap,
  Map<String, String>? environment,
}) async {
  final r = await launch(
    command,
    cwd: cwd,
    stdoutCap: cap,
    environment: environment,
  );
  if (r.startFailed) {
    var said = decodeText(r.stderr);
    if (said.endsWith('\n')) said = said.substring(0, said.length - 1);
    throw VcsStop('tool_missing', '${command.first} could not run: $said');
  }
  return r;
}
