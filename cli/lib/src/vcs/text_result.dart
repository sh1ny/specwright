import 'codec.dart';

/// What a tool run printed, decoded as `vcs.sh`'s `run` read it: invalid bytes
/// become U+FFFD and newlines are universal (`decodeText`). A caller that reads
/// names from the output uses [names] instead, which decodes strictly (D4).
class TextResult {
  TextResult(this.code, this.stdout, this.stderr, {this.stdoutBytes});

  final int code;
  final String stdout;
  final String stderr;

  /// The bytes [stdout] was decoded from; null for a result built from text.
  final List<int>? stdoutBytes;

  /// stdout as a list of names (a `-z` listing, a path list): decoded strictly,
  /// so a name that is not UTF-8 throws [NotUtf8] naming [what] instead of
  /// becoming a U+FFFD look-alike that matches another file. A result built
  /// from text (a test's) returns that text.
  String names(String what) {
    final bytes = stdoutBytes;
    return bytes == null ? stdout : decodeStrict(bytes, what);
  }
}
