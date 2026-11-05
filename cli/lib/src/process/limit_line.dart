import 'dart:io';

/// The limits a bounded run can hit.
enum BoundedLimit {
  deadlineExceeded('deadline_exceeded', 124),
  responseTooLarge('response_too_large', 125);

  const BoundedLimit(this.label, this.exitCode);

  /// The name printed in the limit line.
  final String label;

  /// The exit status of `sw run` when this limit hit.
  final int exitCode;
}

/// The one line printed on stderr when a limit hits:
/// `bounded: <limit>: <cmd> <first arg>`. For `sh`/`bash` with `-c` and more
/// than three arguments, it names the command the shell wraps instead: the two
/// arguments after the script (`sh -c 'exec gh "$@"' gh api ...` names
/// `gh api`).
String limitLine(BoundedLimit limit, List<String> cmd, {bool? windows}) =>
    'bounded: ${limit.label}: ${commandLabel(cmd, windows: windows)}\n';

/// How a line names the command: `<cmd> <first arg>`, or for a `sh`/`bash -c`
/// wrapper the command it wraps (see [limitLine]).
String commandLabel(List<String> cmd, {bool? windows}) {
  final named = _isShellWrapper(cmd, windows: windows ?? Platform.isWindows)
      ? cmd.skip(3).take(2)
      : cmd.take(2);
  return named.join(' ');
}

bool _isShellWrapper(List<String> cmd, {required bool windows}) {
  if (cmd.length <= 3 || cmd[1] != '-c') return false;
  return const {'sh', 'bash'}.contains(stem(cmd[0], windows: windows));
}

/// The lower-cased file name of [path] up to its first dot.
String stem(String path, {required bool windows}) {
  final cut = windows
      ? path.lastIndexOf(RegExp(r'[\\/]'))
      : path.lastIndexOf('/');
  final base = cut < 0 ? path : path.substring(cut + 1);
  return base.toLowerCase().split('.').first;
}
