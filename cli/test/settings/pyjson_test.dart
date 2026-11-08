import 'dart:convert';
import 'dart:io';

import 'package:specwright_cli/src/settings/pyjson.dart';
import 'package:test/test.dart';

// The expected values and positions come from CPython 3.14 `json.loads`: what it accepts is accepted, what it refuses
// is refused with the position of its `JSONDecodeError` (`pos`, `lineno`, `colno`). The words of the message are ours
// (design D4, D11).

void main() {
  group('pyJsonDecode accepts what json.loads accepts', () {
    test('NaN, Infinity and -Infinity are read as doubles', () {
      expect((pyJsonDecode('NaN') as double).isNaN, true);
      expect(pyJsonDecode('Infinity'), double.infinity);
      expect(pyJsonDecode('-Infinity'), double.negativeInfinity);
      final list = pyJsonDecode('[NaN, Infinity, -Infinity]') as List<Object?>;
      expect((list[0]! as double).isNaN, true);
      expect(list[1], double.infinity);
      expect(list[2], double.negativeInfinity);
    });

    test('integers keep every digit: int up to 64 bits, BigInt beyond', () {
      expect(pyJsonDecode('9223372036854775807'), 9223372036854775807);
      expect(pyJsonDecode('-9223372036854775808'), -9223372036854775808);
      expect(
        pyJsonDecode('9223372036854775808'),
        BigInt.parse('9223372036854775808'),
      );
      expect(
        pyJsonDecode('-9223372036854775809'),
        BigInt.parse('-9223372036854775809'),
      );
      expect(
        pyJsonDecode('12345678901234567890123'),
        BigInt.parse('12345678901234567890123'),
      );
      expect(pyJsonDecode('0'), 0);
      expect(pyJsonDecode('-0'), 0);
      expect(pyJsonDecode('-0'), isA<int>());
    });

    test('numbers with a fraction or exponent are doubles', () {
      expect(pyJsonDecode('1.5'), 1.5);
      expect(pyJsonDecode('1E5'), 100000.0);
      expect(pyJsonDecode('1E5'), isA<double>());
      expect(pyJsonDecode('0.5e-3'), 0.0005);
      expect(pyJsonDecode('[1e5, 1E+5, 1.0e-5, 0.0]'), [
        100000.0,
        100000.0,
        1e-5,
        0.0,
      ]);
      expect(pyJsonDecode('1e999'), double.infinity);
      expect(pyJsonDecode('-1e999'), double.negativeInfinity);
      expect(pyJsonDecode('1e-400'), 0.0);
      final negZero = pyJsonDecode('-0.0') as double;
      expect(negZero == 0 && negZero.isNegative, true);
    });

    test('the last of two duplicate keys wins, at the first key\'s place', () {
      final m = pyJsonDecode('{"a":1,"b":2,"a":3}') as Map<String, Object?>;
      expect(m, {'a': 3, 'b': 2});
      expect(m.keys.toList(), ['a', 'b']);
      expect(pyJsonDecode('{"k": "v", "k": {"x": 1}, "k": [1]}'), {
        'k': [1],
      });
    });

    test('objects, arrays, literals and JSON whitespace', () {
      expect(pyJsonDecode(' \t\r\n[1]\n '), [1]);
      expect(pyJsonDecode('[[], {}, [{}], {"a": []}]'), [
        <Object?>[],
        <String, Object?>{},
        [<String, Object?>{}],
        {'a': <Object?>[]},
      ]);
      expect(pyJsonDecode('[true, false, null]'), [true, false, null]);
      expect(pyJsonDecode('{"": 1, " ": 2}'), {'': 1, ' ': 2});
    });

    test(
      'strings: escapes, surrogate pairs, lone surrogates, raw non-ASCII',
      () {
        expect(
          pyJsonDecode(r'"\u00e9\ud83d\ude00\n\/\b\f\r\t\\\""'),
          '\u00e9\u{1F600}\n/\b\f\r\t\\"',
        );
        expect(pyJsonDecode('"\u00e9 \u{1F600}"'), '\u00e9 \u{1F600}');
        expect(pyJsonDecode(r'"\ud800"'), String.fromCharCode(0xd800));
        expect(pyJsonDecode(r'"\ud800A"'), '${String.fromCharCode(0xd800)}A');
        expect(pyJsonDecode(r'"\ude00"'), String.fromCharCode(0xde00));
        expect(
          pyJsonDecode('"\x7f"'),
          '\x7f',
          reason: 'only controls below U+0020 are refused',
        );
      },
    );

    test('nesting a hundred deep is fine', () {
      final text = '${'[' * 100}${']' * 100}';
      Object? v = pyJsonDecode(text);
      var depth = 0;
      while (v is List && v.isNotEmpty) {
        v = v.first;
        depth++;
      }
      expect(depth, 99);
    });
  });

  group('pyJsonDecode refuses what json.loads refuses', () {
    for (final (text, pos, line, column) in _refused) {
      test('refuses ${jsonEncode(text)} at char $pos', () {
        try {
          pyJsonDecode(text, file: 'cfg.json');
          fail('should be refused');
        } on PyJsonException catch (e) {
          expect(e.message, startsWith('cfg.json: '));
          expect(e.message, endsWith('line $line column $column (char $pos)'));
          expect(e.file, 'cfg.json');
          expect(e.position, pos);
          expect(e.line, line);
          expect(e.column, column);
        }
      });
    }

    test('a message without a file name has no prefix', () {
      try {
        pyJsonDecode('[');
        fail('should be refused');
      } on PyJsonException catch (e) {
        expect(
          e.message,
          matches(RegExp(r'^[A-Za-z].*line 1 column 2 \(char 1\)$')),
        );
        expect(e.file, isNull);
      }
    });

    test('nesting past the reader\'s limit is refused, not a crash', () {
      final text = '${'[' * 20000}${']' * 20000}';
      expect(
        () => pyJsonDecode(text, file: 'deep.json'),
        throwsA(isA<PyJsonException>()),
      );
      final objects = '{"a":' * 20000;
      expect(() => pyJsonDecode(objects), throwsA(isA<PyJsonException>()));
    });
  });

  group('pyJsonReadFile', () {
    late Directory tmp;
    setUp(() => tmp = Directory.systemTemp.createTempSync('claude-g3-json-'));
    tearDown(() => tmp.deleteSync(recursive: true));

    File write(String name, List<int> bytes) =>
        File('${tmp.path}/$name')..writeAsBytesSync(bytes);

    test('reads a file', () {
      final f = write('ok.json', utf8.encode('{"a": [1, NaN]}\n'));
      final v = pyJsonReadFile(f.path) as Map<String, Object?>;
      expect((v['a']! as List)[0], 1);
      expect(((v['a']! as List)[1] as double).isNaN, true);
    });

    test('a missing file names the path and the OS error', () {
      final path = '${tmp.path}/absent.json';
      try {
        pyJsonReadFile(path);
        fail('should fail');
      } on PyJsonException catch (e) {
        expect(e.message, startsWith('$path: cannot read: '));
        expect(e.message.length, greaterThan('$path: cannot read: '.length));
      }
    });

    test('invalid UTF-8 names the path', () {
      final f = write('bad.json', [0x22, 0xff, 0x22]);
      try {
        pyJsonReadFile(f.path);
        fail('should fail');
      } on PyJsonException catch (e) {
        expect(e.message, startsWith('${f.path}: not valid UTF-8'));
      }
    });

    test('a refused document names the path and the position', () {
      final f = write('syntax.json', utf8.encode('[1,\n 2,]'));
      try {
        pyJsonReadFile(f.path);
        fail('should fail');
      } on PyJsonException catch (e) {
        expect(e.message, startsWith('${f.path}: '));
        expect(e.message, endsWith('line 2 column 3 (char 6)'));
      }
    });

    test(
      'a byte-order mark is refused as json.loads of the decoded text does',
      () {
        final f = write('bom.json', [0xef, 0xbb, 0xbf, ...utf8.encode('[1]')]);
        try {
          pyJsonReadFile(f.path);
          fail('should fail');
        } on PyJsonException catch (e) {
          expect(e.message, startsWith('${f.path}: '));
          expect(e.message, endsWith('line 1 column 1 (char 0)'));
        }
      },
    );
  });
}

final _refused = <(String, int, int, int)>[
  ('', 0, 1, 1),
  (' \n ', 3, 2, 2),
  ('nul', 0, 1, 1),
  ('tru', 0, 1, 1),
  ('True', 0, 1, 1),
  ('nan', 0, 1, 1),
  ('+1', 0, 1, 1),
  ('01', 1, 1, 2),
  ('-01', 2, 1, 3),
  ('1.', 1, 1, 2),
  ('.5', 0, 1, 1),
  ('-', 0, 1, 1),
  ('1e', 1, 1, 2),
  ('1e+', 1, 1, 2),
  ('0x10', 1, 1, 2),
  ('\'a\'', 0, 1, 1),
  ('[1,]', 2, 1, 3),
  ('[,1]', 1, 1, 2),
  ('[1,,2]', 3, 1, 4),
  ('{"a":1,}', 6, 1, 7),
  ('{a:1}', 1, 1, 2),
  ('{"a" 1}', 5, 1, 6),
  ('{"a":}', 5, 1, 6),
  ('{"a":1 "b":2}', 7, 1, 8),
  ('{1:2}', 1, 1, 2),
  ('["a" "b"]', 5, 1, 6),
  ('"abc', 0, 1, 1),
  ('"a\nb"', 2, 1, 3),
  ('"a\tb"', 2, 1, 3),
  ('"\\x"', 1, 1, 2),
  ('"\\u12"', 2, 1, 3),
  ('"\\u12g4"', 2, 1, 3),
  ('"\\ud800\\u12"', 8, 1, 9),
  ('[1] x', 4, 1, 5),
  ('\u{feff}[1]', 0, 1, 1),
  ('/* c */ 1', 0, 1, 1),
  ('1 2', 2, 1, 3),
  ('[', 1, 1, 2),
  ('{', 1, 1, 2),
  ('[1', 2, 1, 3),
  ('{"a":1', 6, 1, 7),
  ('{"a"', 4, 1, 5),
  ('{"a":', 5, 1, 6),
  ('-infinity', 0, 1, 1),
  ('Infinit', 0, 1, 1),
  ('NaN1', 3, 1, 4),
  ('[1 2]', 3, 1, 4),
  ('1_0', 1, 1, 2),
  ('\u{663}', 0, 1, 1),
  ('\u{b}1', 0, 1, 1),
  ('\u{a0}1', 0, 1, 1),
  ('[\n  1,\n  x\n]', 9, 3, 3),
  ('{"a": [1, 2,\n  3,]}', 16, 2, 4),
  ('{"a":1}\n}', 8, 2, 1),
  ('"\\', 0, 1, 1),
  ('\u{e9}', 0, 1, 1),
  ('\u{1f600} 1', 0, 1, 1),
  ('[1, \u{1f600}]', 4, 1, 5),
  ('-Infinity1', 9, 1, 10),
  ('--1', 0, 1, 1),
  ('[]]', 2, 1, 3),
  ('"a" "b"', 4, 1, 5),
  ('nullx', 4, 1, 5),
  ('[nul]', 1, 1, 2),
  ('{"a":1,,}', 7, 1, 8),
  ('\u{0}', 0, 1, 1),
  ('1\u{0}', 1, 1, 2),
];
