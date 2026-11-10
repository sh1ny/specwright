/// What a tool run printed, decoded as `vcs.sh`'s `run` read it: UTF-8 with
/// surrogate escapes and universal newlines (`decodeText`).
class TextResult {
  TextResult(this.code, this.stdout, this.stderr);

  final int code;
  final String stdout;
  final String stderr;
}
