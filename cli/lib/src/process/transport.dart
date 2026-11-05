import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'limit_line.dart' show stem;

/// What is marked at the end of the transported arguments.
const String argvEndMarker = '__SW_ARGV_END__';

/// Shell text put in front of the script of a transported `bash -c`: it reads
/// the NUL-separated arguments from stdin back into `"$@"`, checks the end
/// marker (a missing marker exits 126 without running the script) and empties
/// stdin.
const String argvPrelude =
    r'mapfile -d "" -t __sw_in; __sw_n=${#__sw_in[@]}; '
    r'if [ "$__sw_n" -eq 0 ] || [ "${__sw_in[__sw_n-1]}" != '
    '$argvEndMarker ]; then '
    r'echo "bounded: argument transport failed" >&2; exit 126; fi; '
    r'unset "__sw_in[__sw_n-1]"; set -- "${__sw_in[@]}"; '
    r'unset __sw_in __sw_n; exec </dev/null';

/// A command line, and the bytes to write on the command's stdin right after
/// the go byte.
class Transport {
  const Transport(this.command, this.stdinBytes);

  final List<String> command;
  final List<int> stdinBytes;
}

/// Git Bash cuts a command-line argument at 8,186 characters, so on Windows a
/// `bash -c script name args...` keeps its script and `name` on the command
/// line and sends the arguments after `name` on stdin as UTF-8, each followed
/// by a NUL, then an end marker. Nothing reaches disk. Every other command is
/// returned unchanged with no bytes.
Transport transportFor(List<String> command, {bool? windows}) {
  final win = windows ?? Platform.isWindows;
  if (!win ||
      command.length < 4 ||
      command[1] != '-c' ||
      stem(command[0], windows: true) != 'bash') {
    return Transport(command, const []);
  }
  final bytes = BytesBuilder(copy: false);
  for (final arg in [...command.skip(4), argvEndMarker]) {
    bytes
      ..add(utf8.encode(arg))
      ..addByte(0);
  }
  return Transport([
    command[0],
    '-c',
    '$argvPrelude; ${command[2]}',
    command[3],
  ], bytes.takeBytes());
}
