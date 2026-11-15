// Checks assumption A1 of native-cli-release (ADR 0037) before any version
// matcher relies on it: Unicode mode refuses Python-only syntax, and a
// multiline `$` matches before the `\r` of a CRLF line end.
import 'package:test/test.dart';

RegExp compile(String pattern) =>
    RegExp(pattern, multiLine: true, unicode: true);

void main() {
  group('Unicode mode refuses Python-only syntax', () {
    for (final pattern in [r'(?P<v>\d+)', r'\A1', r'1\Z', '(?i)x']) {
      test(pattern, () {
        expect(() => compile(pattern), throwsFormatException);
      });
    }
  });

  test(r'a multiline $ matches before the \r of a CRLF', () {
    final match = compile(r'^(\d+\.\d+\.\d+)$').firstMatch('0.4.2\r\n');
    expect(match, isNotNull);
    expect(match!.group(1), '0.4.2');
    expect(match.start, 0);
    expect(match.end, 5);
  });
}
