import 'package:specwright_cli/src/settings/reader.dart';
import 'package:specwright_cli/src/settings/values.dart';
import 'package:test/test.dart';

Matcher refusedAt(int line, [Pattern? why]) => throwsA(
  isA<SettingsRefused>()
      .having((e) => e.line, 'line', line)
      .having((e) => e.why, 'why', why == null ? anything : contains(why)),
);

/// [n] nested `[` opened one per line, each on its own line (the first after `k:`), then closed.
String _stackedFlow(int n) => 'k: [\n${' [\n' * (n - 1)}${' ]\n' * n}';

void main() {
  group('readSettingsYaml', () {
    test('a tab in indentation is refused naming its line', () {
      const text =
          'pr:\n'
          '  merge: user\n'
          '  reviewers:\n'
          '    codex:\n'
          '      role: a\n'
          '      request: b\n'
          '\tkey: v\n';
      expect(() => readSettingsYaml(text), refusedAt(7));
    });

    test('empty, blank and comment-only documents are an empty mapping', () {
      for (final text in ['', '\n\n', '  \n', '# c\n\n# d\n']) {
        final got = readSettingsYaml(text);
        expect(got, isA<YamlMap>(), reason: text);
        expect(got, isEmpty, reason: text);
      }
    });

    test('a leading document marker is read', () {
      final got = readSettingsYaml('---\npr:\n  merge: user\n');
      expect((got['pr'] as Map)['merge'], 'user');
    });

    test('true and false read as booleans', () {
      final got = readSettingsYaml(
        'review:\n  preship: false\npr:\n  react: true\n',
      );
      expect((got['review'] as Map)['preship'], false);
      expect((got['pr'] as Map)['react'], true);
    });

    test('a quoted yes is a string', () {
      final got = readSettingsYaml(
        "a: 'yes'\nb: \"no\"\nc: on\nd: off\ne: y\nf: n\ng: 'Yes'\n",
      );
      expect(got['a'], 'yes');
      expect(got['b'], 'no');
      expect(got['c'], 'on');
      expect(got['d'], 'off');
      expect(got['e'], 'y');
      expect(got['f'], 'n');
      expect(got['g'], 'Yes');
    });

    for (final word in ['yes', 'No', 'YES', 'nO']) {
      test('a plain $word is refused naming its line, true and false', () {
        final text = 'a: 1\npr:\n  react: $word\n';
        expect(() => readSettingsYaml(text), refusedAt(3, 'true'));
        expect(() => readSettingsYaml(text), refusedAt(3, 'false'));
        expect(() => readSettingsYaml(text), refusedAt(3, word));
      });
    }

    test('a plain yes in a list or a flow collection is refused', () {
      expect(
        () => readSettingsYaml('a:\n  - x\n  - yes\n'),
        refusedAt(3, 'true'),
      );
      expect(() => readSettingsYaml('a: [x, No]\n'), refusedAt(1, 'false'));
      expect(() => readSettingsYaml('a: {b: yes}\n'), refusedAt(1, 'true'));
    });

    test('a duplicate key in a nested mapping is refused naming its line', () {
      const text =
          'pr:\n'
          '  reviewers:\n'
          '    codex:\n'
          '      role: a\n'
          '      request: b\n'
          '      role: c\n'
          '    claude:\n'
          '      role: d\n';
      expect(() => readSettingsYaml(text), refusedAt(6));
    });

    test('a duplicate top-level key is refused naming its line', () {
      expect(
        () => readSettingsYaml('pr:\n  a: 1\nx: 1\npr:\n  b: 2\n'),
        refusedAt(4),
      );
    });

    test('more than one document is refused', () {
      expect(() => readSettingsYaml('a: 1\n---\nb: 2\n'), refusedAt(2));
    });

    group('anchors, aliases and tags are refused', () {
      test('an anchor and an alias on scalars name the anchor line', () {
        expect(() => readSettingsYaml('a: &r x\nb: *r\n'), refusedAt(1));
      });

      test('an anchor on a reviewer mapping and its alias', () {
        const text =
            'pr:\n'
            '  reviewers:\n'
            '    codex: &r\n'
            '      role: a\n'
            '    claude: *r\n';
        expect(() => readSettingsYaml(text), refusedAt(3));
      });

      test('an anchor on a flow mapping is refused', () {
        expect(() => readSettingsYaml('a: &r {x: 1}\n'), refusedAt(1));
      });

      test('an anchor on a list is refused', () {
        expect(() => readSettingsYaml('a: &r [x]\n'), refusedAt(1));
      });

      test('tags are refused', () {
        expect(() => readSettingsYaml('a: 1\nk: !!str x\n'), refusedAt(2));
        expect(() => readSettingsYaml('a: 1\nk: !tag x\n'), refusedAt(2));
        expect(() => readSettingsYaml('a: 1\nk: !!map {b: 1}\n'), refusedAt(2));
      });

      test('an alias without an anchor is refused', () {
        expect(() => readSettingsYaml('a: *r\n'), refusedAt(1));
      });
    });

    test('four-level reviewer nesting reads', () {
      final got = readSettingsYaml(
        'pr:\n'
        '  reviewers:\n'
        '    codex:\n'
        '      report:\n'
        '        check: ci\n',
      );
      final check =
          ((((got['pr'] as Map)['reviewers'] as Map)['codex'] as Map)['report']
              as Map)['check'];
      expect(check, 'ci');
    });

    test('block sequences read like flow sequences', () {
      final block = readSettingsYaml(
        'review:\n  order:\n    - codex\n    - claude\n    - omp\n',
      );
      final same = readSettingsYaml(
        'review:\n  order:\n  - codex\n  - claude\n  - omp\n',
      );
      final flow = readSettingsYaml('review:\n  order: [codex, claude, omp]\n');
      final want = ['codex', 'claude', 'omp'];
      expect((block['review'] as Map)['order'], want);
      expect((same['review'] as Map)['order'], want);
      expect((flow['review'] as Map)['order'], want);
    });

    test(
      'block and flow collections and block scalars read as YAML defines',
      () {
        final got = readSettingsYaml(
          'a: {b: 1, c: [x, y]}\nd: |\n  one\n  two\ne: >-\n  f\n  g\nh: "q: 1"\n',
        );
        expect(got['a'], {
          'b': 1,
          'c': ['x', 'y'],
        });
        expect(got['d'], 'one\ntwo\n');
        expect(got['e'], 'f g');
        expect(got['h'], 'q: 1');
      },
    );

    group('flow depth (D2)', () {
      test('65 literal [ in a block scalar are read whole', () {
        final got = readSettingsYaml('k: |\n  ${'[' * 65}\nz: 1\n');
        expect(got['k'], '${'[' * 65}\n');
        expect(got['z'], 1);
      });

      test('65 literal [ in a folded block scalar are read whole', () {
        final got = readSettingsYaml('k: >-\n  ${'[' * 65}\n  {{{\nz: 1\n');
        expect(got['k'], '${'[' * 65} {{{');
        expect(got['z'], 1);
      });

      test(
        '65 literal [ in a plain scalar in block context are read whole',
        () {
          final got = readSettingsYaml('k: a${'[' * 65}\nz: 1\n');
          expect(got['k'], 'a${'[' * 65}');
          expect(got['z'], 1);
        },
      );

      test(
        '65 literal [ on a plain scalar continuation line are read whole',
        () {
          final got = readSettingsYaml(
            'notes: text\n  ${'[' * 65}\n\n  more\nz: 1\n',
          );
          expect(got['notes'], 'text ${'[' * 65}\nmore');
          expect(got['z'], 1);
          final item = readSettingsYaml('l:\n  - text\n    ${'{' * 65}\n');
          expect(item['l'], ['text ${'{' * 65}']);
        },
      );

      test('a flow collection after a plain scalar ends is still counted', () {
        expect(
          () => readSettingsYaml('notes: text\n${_stackedFlow(65)}'),
          refusedAt(66, '64'),
        );
      });

      test('65 nested flow sequences are refused naming the 65th opening', () {
        expect(() => readSettingsYaml(_stackedFlow(65)), refusedAt(65, '64'));
      });

      test('65 nested flow mappings on one line are refused', () {
        final text = 'k: ${'{a: ' * 65}1${'}' * 65}\n';
        expect(() => readSettingsYaml(text), refusedAt(1, '64'));
      });

      test('64 nested flow sequences are read', () {
        var v = readSettingsYaml(_stackedFlow(64))['k'];
        var depth = 0;
        while (v is List && v.isNotEmpty) {
          v = v.first;
          depth++;
        }
        expect(depth, 63);
      });

      test('a [ in quoted scalars and comments is not counted', () {
        final b = '[' * 100;
        final got = readSettingsYaml(
          '# $b\n'
          'a: "$b"\n'
          "b: '$b'\n"
          'c: 1 # $b\n'
          'd: ["$b", \'$b\', x] # $b\n'
          "e: 'it''s $b'\n"
          'f:\n'
          '  - "$b"\n',
        );
        expect(got['a'], b);
        expect(got['b'], b);
        expect(got['c'], 1);
        expect(got['d'], [b, b, 'x']);
        expect(got['e'], "it's $b");
        expect(got['f'], [b]);
      });

      test('a multi-line quoted scalar is not counted', () {
        final b = '[' * 100;
        final got = readSettingsYaml('a: "$b\n  $b"\nz: 1\n');
        expect(got['a'], '$b $b');
        expect(got['z'], 1);
      });

      test('block nesting past the stack is refused by the backstop', () {
        // `- ` prefixes are block nesting, which the scan does not count.
        expect(
          () => readSettingsYaml('k:\n  ${'- ' * 100000}x\n'),
          refusedAt(1, 'nested too deeply'),
        );
      });

      test('a leading byte-order mark does not hide the first line', () {
        expect(readSettingsYaml('\uFEFFa: 1\n'), {'a': 1});
        expect(
          () => readSettingsYaml('\uFEFFk: ${'[' * 65}${']' * 65}\n'),
          refusedAt(1, '64'),
        );
      });

      test('100,000 nested flow collections are refused without a crash', () {
        final text = 'k: ${'[' * 100000}${']' * 100000}\n';
        expect(() => readSettingsYaml(text), refusedAt(1, '64'));
        final map = 'k: ${'{a: ' * 100000}1${'}' * 100000}\n';
        expect(() => readSettingsYaml(map), refusedAt(1, '64'));
      });
    });

    group('numbers (D3)', () {
      test('a 21-digit decimal integer stays exact', () {
        final got = readSettingsYaml(
          'n: 123456789012345678901\nm: -123456789012345678901\n',
        );
        expect(got['n'], isA<BigInt>());
        expect(got['n'], pyIntNormal(BigInt.parse('123456789012345678901')));
        expect(got['m'], pyIntNormal(BigInt.parse('-123456789012345678901')));
      });

      test('64-bit edges follow pyIntNormal', () {
        final got = readSettingsYaml(
          'a: 9223372036854775807\nb: 9223372036854775808\nc: 18446744073709551616\n',
        );
        expect(got['a'], 9223372036854775807);
        expect(got['b'], pyIntNormal(BigInt.parse('9223372036854775808')));
        expect(got['c'], BigInt.parse('18446744073709551616'));
      });

      test('a small integer is an int, also negative', () {
        final got = readSettingsYaml('a: 5\nb: -5\nc: 007\nd: 0\ne: +7\n');
        expect(got['e'], 7);
        expect(got['a'], 5);
        expect(got['b'], -5);
        expect(got['c'], 7);
        expect(got['d'], 0);
        expect(got['a'], isA<int>());
      });

      test('hex is 16, a float is a double', () {
        final got = readSettingsYaml('a: 0x10\nb: 1.5\n');
        expect(got['a'], 16);
        expect(got['b'], 1.5);
        expect(got['b'], isA<double>());
      });

      test('Arabic-Indic digits are a string', () {
        final got = readSettingsYaml('a: \u0661\u0662\n');
        expect(got['a'], '\u0661\u0662');
      });

      test('a quoted integer is a string', () {
        expect(readSettingsYaml("a: '5'\nb: \"123456789012345678901\"\n"), {
          'a': '5',
          'b': '123456789012345678901',
        });
      });
    });

    group('keys and the top level', () {
      test('a non-string key is refused naming its line', () {
        expect(() => readSettingsYaml('1: a\n'), refusedAt(1));
        expect(() => readSettingsYaml('x: 1\n[a]: b\n'), refusedAt(2));
        expect(() => readSettingsYaml('x: 1\nnull: b\n'), refusedAt(2));
        expect(() => readSettingsYaml('x: 1\ny:\n  true: b\n'), refusedAt(3));
      });

      test('a plain yes as a key is a string key', () {
        expect(readSettingsYaml('yes: 1\n'), {'yes': 1});
      });

      test('an explicit null root is refused', () {
        expect(() => readSettingsYaml('null\n'), refusedAt(1));
        expect(() => readSettingsYaml('~\n'), refusedAt(1));
      });

      test('a list root is refused naming line 1', () {
        expect(() => readSettingsYaml('- pr\n'), refusedAt(1));
        expect(() => readSettingsYaml('# c\n- pr\n'), refusedAt(2));
        expect(() => readSettingsYaml('[a, b]\n'), refusedAt(1));
      });

      test('a scalar root is refused', () {
        expect(() => readSettingsYaml('hello\n'), refusedAt(1));
        expect(() => readSettingsYaml('5\n'), refusedAt(1));
      });

      test('an empty value is null', () {
        final got = readSettingsYaml('a:\nb: null\nc: ~\n');
        expect(got.containsKey('a'), isTrue);
        expect(got['a'], isNull);
        expect(got['b'], isNull);
        expect(got['c'], isNull);
      });
    });

    group('plain scalar text for settingText', () {
      test('a plain value keeps its text', () {
        final got = readSettingsYaml('merge: Agent\nn: 007\nb: true\n');
        expect(settingText(got, 'merge'), 'Agent');
        expect(settingText(got, 'n'), '007');
        expect(settingText(got, 'b'), 'true');
      });

      test('nested mappings keep text too', () {
        final got = readSettingsYaml(
          'pr:\n  merge: Agent  # c\n  reviewers:\n    codex:\n      role: Lead\n',
        );
        final pr = got['pr'] as Map;
        expect(pr, isA<YamlMap>());
        expect(settingText(pr, 'merge'), 'Agent');
        final codex = (pr['reviewers'] as Map)['codex'];
        expect(codex, isA<YamlMap>());
        expect(settingText(codex, 'role'), 'Lead');
      });

      test('quoted and flow values keep their text as written', () {
        final got = readSettingsYaml(
          "merge_method: ''\nd: \"x\"\nreviewers: [a, b]\nm: { role: required }\n",
        );
        expect(settingText(got, 'merge_method'), "''");
        expect(settingText(got, 'd'), '"x"');
        expect(settingText(got, 'reviewers'), '[a, b]');
        expect(settingText(got, 'm'), '{ role: required }');
      });

      test('a flow mapping value keeps its entries text', () {
        final got = readSettingsYaml('a: {b: Agent}\n');
        expect(settingText(got['a'], 'b'), 'Agent');
      });
    });

    test('non-finite numbers are refused naming their line', () {
      for (final v in ['.nan', '.NaN', '.inf', '-.inf', '+.INF']) {
        expect(
          () => readSettingsYaml('pr:\n  delete_branch: $v\n'),
          refusedAt(2, 'not a finite number'),
          reason: v,
        );
      }
      expect(
        () => readSettingsYaml('pr:\n  reviewers:\n    a: {timeout: -.inf}\n'),
        refusedAt(3, 'not a finite number'),
      );
      expect(readSettingsYaml('a: 1.5\nb: \'.inf\'\n'), {
        'a': 1.5,
        'b': '.inf',
      });
    });

    group('values and stops kept from the old reader', () {
      test('block scalars: literal, strip, fold and keep', () {
        final got = readSettingsYaml(
          'notes: |\n  line1\n    indented\n  line3\n\n'
          'folded: >-\n  one\n  two\n\n  three\n'
          'keep: |+\n  x\n\n'
          'after: 1\n',
        );
        expect(got['notes'], 'line1\n  indented\nline3\n');
        expect(got['folded'], 'one two\nthree');
        expect(got['keep'], 'x\n\n');
        expect(got['after'], 1);
      });

      test('a quoted key keeps its characters and its escapes decode', () {
        final got = readSettingsYaml(
          '"a b": 1\n\'c\'\'d\': 2\n"e\\u00e9": 3\n',
        );
        expect(got.keys.toList(), ['a b', "c'd", 'eé']);
      });

      test('quoted scalars decode their escapes', () {
        final got = readSettingsYaml("a: '42'\nb: 'it''s'\nc: \"4\\x41\\n\"\n");
        expect(got['a'], '42');
        expect(got['b'], "it's");
        expect(got['c'], '4A\n');
      });

      test('flow collections read as maps and lists', () {
        final got = readSettingsYaml(
          'a: {x: 1, y: [p, q], z: }\nb: [1, \'two\']\n',
        );
        expect(got['a'], {
          'x': 1,
          'y': ['p', 'q'],
          'z': null,
        });
        expect(got['b'], [1, 'two']);
      });

      test('null, ~ and Null are null; an empty value is null', () {
        final got = readSettingsYaml('a: ~\nb: null\nc:\nd: Null\n');
        expect(got['a'], isNull);
        expect(got['b'], isNull);
        expect(got.containsKey('c'), true);
        expect(got['c'], isNull);
        expect(got['d'], isNull, reason: 'the package reads Null as null');
      });

      test('a line of another indentation is refused naming its line', () {
        expect(() => readSettingsYaml('a: 1\n  b: 2\nc: 3\n'), refusedAt(2));
      });

      test('a line that is not key: value is refused', () {
        expect(
          () => readSettingsYaml('a: 1\nplain text\n'),
          throwsA(isA<SettingsRefused>()),
        );
      });

      test('a control character or an unterminated quote is refused', () {
        expect(() => readSettingsYaml('a: 1\nb: x\u{1}y\n'), refusedAt(2));
        expect(
          () => readSettingsYaml('a: 1\nb: "x\n'),
          throwsA(isA<SettingsRefused>()),
        );
      });

      test('U+2028 does not end a line, so the line is refused', () {
        expect(
          () => readSettingsYaml('x: 1 y: 2\n'),
          throwsA(isA<SettingsRefused>()),
        );
      });
    });
  });
}
