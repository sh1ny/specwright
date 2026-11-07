import 'package:specwright_cli/src/finish/script_text.dart';
import 'package:test/test.dart';

/// Expected texts are fixed strings: `shlex.quote` (Python 3.8 and 3.12 agree)
/// and `dq` of finish.sh.
void main() {
  group('shellQuote', () {
    final cases = <String, String>{
      '': "''",
      'abc_DEF-1.2/x:y,z@a%b+c=d': 'abc_DEF-1.2/x:y,z@a%b+c=d',
      'a b': "'a b'",
      "it's": "'it'\"'\"'s'",
      "'": "''\"'\"''",
      r'$HOME': "'\$HOME'",
      'café': "'café'",
      '日本': "'日本'",
      'say "hi"': "'say \"hi\"'",
      r'a\b': r"'a\b'",
      'a\nb': "'a\nb'",
      'a;b': "'a;b'",
    };
    cases.forEach((input, want) {
      test('quotes ${input.codeUnits}', () {
        expect(shellQuote(input), want);
      });
    });
  });

  group('jjString', () {
    final cases = <String, String>{
      '': '""',
      'plain': '"plain"',
      'a b': '"a b"',
      'say "hi"': r'"say \"hi\""',
      r'a\b': r'"a\\b"',
      r'\"': r'"\\\""',
      'café': '"café"',
    };
    cases.forEach((input, want) {
      test('quotes ${input.codeUnits}', () {
        expect(jjString(input), want);
      });
    });
  });
}
