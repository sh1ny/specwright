import 'package:specwright_cli/src/settings/yaml.dart';
import 'package:test/test.dart';

// The expected values come from CPython 3.14 running the frozen `parse_yaml`,
// `scalar` and `yaml_problem` of skills/specwright-pr/scripts/pr-pair.sh.

void main() {
  group('yamlProblem (the strict check)', () {
    for (final (name, text, want) in _strictCases) {
      test(name, () {
        final got = yamlProblem(text);
        if (want == null) {
          expect(got, isNull);
          return;
        }
        final parts = want.split('|');
        expect(got, isNotNull, reason: 'a problem is expected');
        expect(got, startsWith(parts[0]));
        if (parts.length > 1) expect(got, contains(parts[1]));
      });
    }

    test('a lone surrogate is a control character problem', () {
      final got = yamlProblem('a: x${String.fromCharCode(0xd800)}y\n');
      expect(got, startsWith('line 1:'));
      expect(got, contains('U+D800'));
    });

    test('an empty file and a comment-only file have no problem', () {
      expect(yamlProblem(''), isNull);
      expect(yamlProblem('# only a comment\n\n'), isNull);
    });

    test('a character outside the BMP is fine and counts as one', () {
      expect(yamlProblem('a: \u{1F600}\n'), isNull);
      // 1023 astral characters make a key of 1023 characters, not 2046
      expect(yamlProblem('${'\u{1F600}' * 1023}: 1\n'), isNull);
      expect(yamlProblem('${'\u{1F600}' * 1024}: 1\n'), startsWith('line 1:'));
    });
  });

  group('yamlScalar', () {
    test('reads true, yes, false and no in any case', () {
      for (final v in ['true', 'True', 'TRUE', 'yes', 'YES', 'Yes']) {
        expect(yamlScalar(v), true, reason: v);
      }
      for (final v in ['false', 'False', 'no', 'No', 'NO']) {
        expect(yamlScalar(v), false, reason: v);
      }
    });

    test('reads null and ~ only as written, and empty text as null', () {
      expect(yamlScalar('null'), isNull);
      expect(yamlScalar('~'), isNull);
      expect(yamlScalar(''), isNull);
      expect(yamlScalar('   '), isNull);
      expect(yamlScalar('Null'), 'Null');
      expect(yamlScalar('NULL'), 'NULL');
    });

    test('reads Unicode decimal digits as Python int() does', () {
      expect(yamlScalar('\u0663'), 3); // ARABIC-INDIC DIGIT THREE
      expect(yamlScalar('-\u0663'), -3);
      expect(yamlScalar('\u0967\u0968'), 12); // DEVANAGARI 12
      expect(
        yamlScalar('\u{1D7D9}\u{1D7DA}'),
        12,
      ); // MATHEMATICAL DOUBLE-STRUCK
      expect(yamlScalar('\u{1D7FF}'), 9); // the last of the fifty
      expect(yamlScalar('  7  '), 7);
      expect(yamlScalar('007'), 7);
      expect(yamlScalar('-0'), 0);
    });

    test('keeps what is not a whole integer as text', () {
      for (final v in ['0x10', '1.5', '+5', '--5', '-', '\u0663x', '1e3']) {
        expect(yamlScalar(v), v, reason: v);
      }
    });

    test('keeps an integer past 64 bits as a BigInt', () {
      expect(
        yamlScalar('12345678901234567890'),
        BigInt.parse('12345678901234567890'),
      );
      expect(yamlScalar('9223372036854775807'), 9223372036854775807);
      expect(
        yamlScalar('9223372036854775808'),
        BigInt.parse('9223372036854775808'),
      );
      expect(
        yamlScalar('-9223372036854775809'),
        BigInt.parse('-9223372036854775809'),
      );
    });

    test('reads quoted scalars', () {
      expect(yamlScalar("'42'"), '42');
      expect(yamlScalar("'it''s'"), "it's");
      expect(yamlScalar(r'"4\x41\u00e9\n"'), '4A\u00e9\n');
      expect(yamlScalar(r'"\q"'), r'\q');
      expect(yamlScalar('"'), '"');
      expect(yamlScalar("'"), "'");
      expect(yamlScalar('"unterminated'), '"unterminated');
    });

    test('reads flow maps and lists', () {
      expect(yamlScalar('{a: 1, b: [x, y], c: }'), {
        'a': 1,
        'b': ['x', 'y'],
        'c': null,
      });
      expect(yamlScalar("[1, 'two', yes]"), [1, 'two', true]);
      expect(yamlScalar('[]'), <Object?>[]);
      expect(yamlScalar('{}'), <String, Object?>{});
      expect(yamlScalar('{a}'), {'a': null});
      expect(yamlScalar('[a, [b, c]]'), [
        'a',
        ['b', 'c'],
      ]);
      expect(yamlScalar('{a: 1'), '{a: 1');
    });
  });

  group('parseYaml (the lenient reader)', () {
    const sample =
        '# top\n'
        'finish: pr\n'
        'vcs: Git\n'
        'dup: 1\n'
        'dup: yes\n'
        'pr:\n'
        '  settle: 5m\n'
        '  merge: Agent\n'
        '  flag: yes\n'
        '  nested:\n'
        '    deep: "q # not comment" # comment\n'
        "    other: 'a''b'\n"
        '  list: [a, b]\n'
        'notes: |\n'
        '  line1\n'
        '    indented\n'
        '  line3\n'
        '\n'
        'folded: >-\n'
        '  one\n'
        '  two\n'
        '\n'
        '  three\n'
        'keep: |+\n'
        '  x\n'
        '\n'
        'after: 1\n'
        'bad line here\n'
        'empty:\n'
        'tail:\n';

    test('reads maps, scalars, flow lists and block scalars', () {
      expect(parseYaml(sample), {
        'finish': 'pr',
        'vcs': 'Git',
        'dup': true,
        'pr': {
          'settle': '5m',
          'merge': 'Agent',
          'flag': true,
          'nested': {'deep': 'q # not comment', 'other': "a'b"},
          'list': ['a', 'b'],
        },
        'notes': 'line1\n  indented\nline3\n',
        'folded': 'one two\nthree',
        'keep': 'x\n\n',
        'after': 1,
        'empty': null,
        'tail': null,
      });
    });

    test('skips a line it cannot read and the last duplicate wins', () {
      final m = parseYaml(sample);
      expect(m.keys.toList().indexOf('dup'), 2, reason: 'first position kept');
      expect(m['dup'], true);
    });

    test('Map.text keeps each plain scalar as written', () {
      final m = parseYaml(sample);
      expect(m.text, {
        'finish': 'pr',
        'vcs': 'Git',
        'dup': 'yes',
        'after': '1',
      });
      final pr = m['pr']! as YamlMap;
      expect(pr.text, {
        'settle': '5m',
        'merge': 'Agent',
        'flag': 'yes',
        'list': '[a, b]',
      });
    });

    test('Map.text keeps a quoted scalar with its quotes', () {
      final m = parseYaml('a: "x"\nb: [1, 2]\n');
      expect(m.text, {'a': '"x"', 'b': '[1, 2]'});
    });

    test('a later duplicate does not erase the earlier text', () {
      final m = parseYaml('a: yes\na: |\n  block\n');
      expect(m['a'], 'block\n');
      expect(m.text['a'], 'yes', reason: 'the script never clears it');
    });

    test('an empty or comment-only text is an empty map', () {
      expect(parseYaml(''), isEmpty);
      expect(parseYaml('# c\n\n'), isEmpty);
    });

    test('stops at a line of another indentation', () {
      expect(parseYaml('a: 1\n  b: 2\nc: 3\n'), {'a': 1});
      expect(parseYaml('  a: 1\n  b:\n    c: 2\nd: 3\n'), {
        'a': 1,
        'b': {'c': 2},
      });
    });

    test('splits lines as Python does: U+2028, CR and form feed end one', () {
      expect(parseYaml('\x0cx: 1\u2028y: 2\rz: 3\n'), {'x': 1, 'y': 2, 'z': 3});
    });

    test('block scalars: strip, fold and blank lines', () {
      expect(parseYaml('k: |-\n  \n  x\n\n\nz: >\n  a\n\n  b\n  c\n'), {
        'k': '\nx',
        'z': 'a\nb c\n',
      });
    });

    test('a block scalar header with a Unicode digit is still a block', () {
      expect(parseYaml('k: |\u0663\n  x\n'), {'k': 'x\n'});
    });

    test('a quoted key keeps its characters; escapes decode', () {
      final m = parseYaml('"a b": 1\n\'c\'\'d\': 2\n"e\\u00e9": 3\n');
      expect(m.keys.toList(), ['a b', "c'd", 'e\u00e9']);
    });
  });

  group('helpers', () {
    test('pyStr writes what str() writes', () {
      expect(pyStr(true), 'True');
      expect(pyStr(false), 'False');
      expect(pyStr(null), 'None');
      expect(pyStr(5), '5');
      expect(
        pyStr(BigInt.parse('99999999999999999999')),
        '99999999999999999999',
      );
      expect(pyStr('x'), 'x');
      expect(pyStr(['a', 1, true, null]), "['a', 1, True, None]");
      expect(pyStr({'a': 1, 'b': 'x'}), "{'a': 1, 'b': 'x'}");
    });

    test('pyTruthy follows Python truthiness', () {
      for (final v in [null, false, 0, '', <Object?>[], <String, Object?>{}]) {
        expect(pyTruthy(v), false, reason: '$v');
      }
      for (final v in [
        true,
        1,
        -1,
        'false',
        'x',
        ['a'],
        {'a': 1},
      ]) {
        expect(pyTruthy(v), true, reason: '$v');
      }
    });

    test('settingText gives the text as written, else str() of the value', () {
      final m = parseYaml('a: yes\nb: "q"\nc: 7\n');
      expect(settingText(m, 'a'), 'yes');
      expect(settingText(m, 'b'), '"q"');
      expect(settingText(m, 'c'), '7');
      // a flow map has no text: a boolean is str(bool).lower()
      expect(settingText({'a': true}, 'a'), 'true');
      expect(settingText({'a': false}, 'a'), 'false');
      expect(settingText({'a': 5}, 'a'), '5');
      expect(settingText({'a': null}, 'a'), 'None');
      expect(settingText(m, 'absent'), 'None');
    });

    test('pyDecimalValue converts every Unicode decimal digit', () {
      expect(pyDecimalValue('123'), BigInt.from(123));
      expect(pyDecimalValue('\u0663\u0661'), BigInt.from(31));
      expect(pyDecimalValue(''), isNull);
      expect(pyDecimalValue('1a'), isNull);
      expect(pyDecimalValue('\u00b2'), isNull, reason: 'superscript two is No');
    });
  });
}

// Generated from the frozen pr-pair.sh yaml_problem: each case's `line N:` prefix (and the code point of a control) is what Python reports.
final _strictCases = <(String, String, String?)>[
  ('tab in a nested key\'s indentation', 'a:\n\tb: 1\n', 'line 2:'),
  ('tab after spaces in indentation', 'a:\n  \tb: 1\n', 'line 2:'),
  ('a tab-only blank line', 'a: 1\n\t\nb: 2\n', 'line 2:'),
  ('a tab-only blank line inside a block', 'a: |\n  x\n\t\n  y\n', 'line 3:'),
  ('a control character', 'a: 1\nb: x\u{1}y\n', 'line 2:|(U+0001)'),
  ('NUL', 'a: 1\n\nb: \u{0}\n', 'line 3:|(U+0000)'),
  ('U+2028 line separator', 'a: 1\nb: x\u{2028}y\n', 'line 2:|(U+2028)'),
  ('U+2029 paragraph separator', 'a: x\u{2029}y\n', 'line 1:|(U+2029)'),
  ('U+0085 next line', 'a: 1\nb: x\u{85}y\n', 'line 2:|(U+0085)'),
  (
    'a byte-order mark inside the text',
    'a: 1\nb: x\u{feff}y\n',
    'line 2:|(U+FEFF)',
  ),
  ('a form feed', 'a: 1\nb: x\u{c}y\n', 'line 2:|(U+000C)'),
  ('a vertical tab', 'a: 1\nb: 2\nc: x\u{b}y\n', 'line 3:|(U+000B)'),
  (
    'a control after CR line ends',
    'a: 1\rb: 2\rc: \u{1}\r',
    'line 3:|(U+0001)',
  ),
  ('a no-break space', 'a: 1\nb: x\u{a0}y\n', 'line 2:|(U+00A0)'),
  ('an ideographic space', 'a: 1\nb: 2\nc: x\u{3000}y\n', 'line 3:|(U+3000)'),
  ('an en space after CRLF', 'a: 1\r\nb: x\u{2002}y\r\n', 'line 2:|(U+2002)'),
  ('U+1680', 'a:\u{1680} 1\n', 'line 1:|(U+1680)'),
  ('U+202F', 'k: a\u{202f}b\n', 'line 1:|(U+202F)'),
  ('a second --- marker', '---\na: 1\n---\nb: 2\n', 'line 3:'),
  ('--- after a key', 'a: 1\n---\n', 'line 2:'),
  ('a ... marker', 'a: 1\n...\n', 'line 2:'),
  ('... first', '...\na: 1\n', 'line 1:'),
  ('--- with text', '--- a\nb: 1\n', 'line 1:'),
  ('a leading marker is fine', '---\na: 1\n', null),
  ('a nested block sequence', 'a:\n  - x\n  - y\n', 'line 2:'),
  ('a top-level block sequence', '- a\n- b\n', 'line 1:'),
  ('a lone dash', 'a:\n  -\n', 'line 2:'),
  ('a block merge key', 'base: 1\n<<: x\n', 'line 2:'),
  ('a merge key in a nested map', 'a:\n  <<: *x\n', 'line 2:'),
  ('a flow merge key', 'a: {<<: x}\n', 'line 1:'),
  ('a duplicate key', 'a: 1\nb: 2\na: 3\n', 'line 3:'),
  ('a quoted duplicate of a plain key', 'a: 1\n"a": 2\n', 'line 2:'),
  ('a single-quoted duplicate', '\'a\': 1\n\'a\': 2\n', 'line 2:'),
  ('a nested duplicate', 'm:\n  x: 1\n  y: 2\n  x: 3\n', 'line 4:'),
  ('a duplicate in a flow map', 'a: {x: 1, y: 2, x: 3}\n', 'line 1:'),
  ('a duplicate inside a nested flow map', 'a: [{x: 1, x: 2}]\n', 'line 1:'),
  ('same key in sibling maps is fine', 'x:\n  a: 1\ny:\n  a: 2\n', null),
  ('an indentation indicator', 'a: |2\n  x\n', 'line 1:'),
  ('a Unicode digit indicator', 'a: |\u{663}\n  x\n', 'line 1:'),
  ('a bad header', 'a: |x\n  y\n', 'line 1:'),
  ('a keep chomp is fine', 'a: |+\n  x\n\nb: 1\n', null),
  ('a strip fold is fine', 'a: >-\n  x\n  y\nb: 1\n', null),
  (
    'a blank line before the text with more spaces',
    'a: |\n      \n  x\n',
    'line 1:',
  ),
  (
    'a block line indented less than its first',
    'a: |\n    x\n  y\n',
    'line 1:',
  ),
  ('a more-indented line in a fold', 'a: >\n  x\n    y\n', 'line 1:'),
  ('a tab-led line in a fold', 'a: >\n  x\n  \ty\n', 'line 1:'),
  ('a block inside a nested map', 'm:\n  a: |\n    x\n    y\n  b: 1\n', null),
  ('an unterminated flow list', 'a: [1, 2\n', 'line 1:'),
  ('an empty entry', 'a: [1,, 2]\n', 'line 1:'),
  ('a trailing comma', 'a: [1, 2,]\n', 'line 1:'),
  ('a trailing comma in a flow map', 'a: {x: 1,}\n', 'line 1:'),
  ('a flow key colon without a space', 'a: {x:1}\n', 'line 1:'),
  ('a key: value pair in a list', 'a: [x: 1]\n', 'line 1:'),
  ('an anchor', 'a: &x 1\n', 'line 1:'),
  ('an alias', 'a: *x\n', 'line 1:'),
  ('a tag', 'a: !t x\n', 'line 1:'),
  ('text after a closing quote', 'a: \'x\' y\n', 'line 1:'),
  ('text after a closing bracket', 'a: [x] y\n', 'line 1:'),
  ('an unknown escape', 'a: "\\q"\n', 'line 1:'),
  ('an unterminated quote', 'a: "x\n', 'line 1:'),
  ('an unterminated single quote', 'a: \'x\n', 'line 1:'),
  ('a surrogate escape', 'a: "\\ud800"\n', 'line 1:'),
  ('an escape past U+10FFFF', 'a: "\\U00110000"\n', 'line 1:'),
  ('a plain value with a colon and space', 'a: b: c\n', 'line 1:'),
  ('a plain value ending in a colon', 'a: b:\n', 'line 1:'),
  ('a hash after a tab is a comment, fine', 'a: b\t#c\n', null),
  ('a flow entry with a bracket', 'a: [x[y]\n', 'line 1:'),
  ('an unbalanced bracket', 'a: ]\n', 'line 1:'),
  ('a flow map key that is a collection', 'a: {[x]: 1}\n', 'line 1:'),
  (
    'a flow collection nested 33 deep',
    'a: [[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]\n',
    'line 1:',
  ),
  (
    'a flow collection nested 32 deep is fine',
    'a: [[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]\n',
    null,
  ),
  ('a flow question-mark start', 'a: [?x]\n', 'line 1:'),
  ('a flow map with a colon-led key', 'a: {:x}\n', 'line 1:'),
  ('a line that is not key: value', 'a: 1\nplain text\n', 'line 2:'),
  ('unexpected indentation', 'a: 1\n  b: 2\n', 'line 2:'),
  ('a less indented second key', '  a: 1\nb: 2\n', 'line 2:'),
  ('an unterminated quoted key', '"a: 1\n', 'line 1:'),
  ('a key of 1024 characters', '${'k' * 1024}: 1\n', 'line 1:'),
  ('a key of 1023 characters is fine', '${'k' * 1023}: 1\n', null),
  ('a percent start', 'a: %x\n', 'line 1:'),
  ('a bar start in a flow', 'a: [|x]\n', 'line 1:'),
  ('a backtick', 'a: `x\n', 'line 1:'),
  ('an at sign', 'a: @x\n', 'line 1:'),
  ('a dash-space start', 'a: - x\n', 'line 1:'),
  ('a question-mark-space start', 'a: ? x\n', 'line 1:'),
  (
    'a comment after a closed flow is fine',
    'a: [1, 2] # c\nb: {x: \'y\', z: "w"}\n',
    null,
  ),
  (
    'a typical settings file is fine',
    '# c\nfinish: pr\nvcs: git\npr:\n  settle: 5m\n  reviewers:\n    kody-ai: { role: advisory, timeout: 15m }\n    bot:\n      report:\n        check: \'Bot Code Review\'\n  notes: |\n    keep\t this\n    text\nplanning_store:\n  login: me\n',
    null,
  ),
  (
    'mappings nested 32 deep',
    'k:\n k:\n  k:\n   k:\n    k:\n     k:\n      k:\n       k:\n        k:\n         k:\n          k:\n           k:\n            k:\n             k:\n              k:\n               k:\n                k:\n                 k:\n                  k:\n                   k:\n                    k:\n                     k:\n                      k:\n                       k:\n                        k:\n                         k:\n                          k:\n                           k:\n                            k:\n                             k:\n                              k:\n                               k:\n                                v: 1\n',
    'line 33:',
  ),
  (
    'mappings nested 31 deep is fine',
    'k:\n k:\n  k:\n   k:\n    k:\n     k:\n      k:\n       k:\n        k:\n         k:\n          k:\n           k:\n            k:\n             k:\n              k:\n               k:\n                k:\n                 k:\n                  k:\n                   k:\n                    k:\n                     k:\n                      k:\n                       k:\n                        k:\n                         k:\n                          k:\n                           k:\n                            k:\n                             k:\n                              k:\n                               v: 1\n',
    null,
  ),
  (
    'the line number counts comments and blank lines',
    '# c\n\n\na: 1\n# d\nb: [1,\n',
    'line 6:',
  ),
  ('the line number after CRLF', 'a: 1\r\n\r\nb: [\r\n', 'line 3:'),
];
