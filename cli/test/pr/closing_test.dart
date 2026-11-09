import 'package:test/test.dart';
import 'package:specwright_cli/src/pr/closing.dart';

void main() {
  test('entities and links form closing lists; code ends the list', () {
    expect(
      intendedReferences(
        '<p>Fixes &num;12, <a>#13</a> <code>#14</code>, #15</p>',
        'o/r',
      ),
      ['o/r#12', 'o/r#13'],
    );
    expect(
      intendedReferences(
        '<p>Fi<code>x</code>xes #9</p><pre>Fixes #10</pre>',
        'o/r',
      ),
      isEmpty,
    );
  });
  test('newlines and blocks never join closing directives', () {
    expect(
      intendedReferences('<p>Fixes\n#1</p><p>Fixes</p><p>#2</p>', 'o/r'),
      isEmpty,
    );
    expect(intendedReferences('<p>Fixes #1\n#2</p>', 'o/r'), ['o/r#1']);
  });
  test('Unicode keyword boundaries and explicit repository references', () {
    expect(intendedReferences('<p>Fixes #00021</p>', 'o/r'), ['o/r#21']);
    expect(
      intendedReferences(
        '<p>éfixes #1; fixes x/y#2; closes https://github.com/a/b/issues/3</p>',
        'o/r',
      ),
      ['x/y#2', 'a/b#3'],
    );
  });
  test('malformed and misnested tags preserve code exclusion', () {
    expect(
      intendedReferences(
        '<p>Fixes <b><code>#1</b> #2</code></p><p>Closes #3',
        'o/r',
      ),
      ['o/r#3'],
    );
  });
  test('raw table follows standard HTML5 interpretation', () {
    expect(intendedReferences('Fixes <table>#1</table>', 'o/r'), ['o/r#1']);
  });
  test('deep inline DOM traversal is iterative', () {
    final open = List.filled(3000, '<span>').join();
    final close = List.filled(3000, '</span>').join();
    expect(intendedReferences('$open Fixes #7 $close', 'o/r'), ['o/r#7']);
  });
}
