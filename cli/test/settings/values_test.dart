import 'package:specwright_cli/src/settings/reader.dart';
import 'package:specwright_cli/src/settings/values.dart';
import 'package:test/test.dart';

// The expected values come from CPython 3.14 running `str`, truthiness, `int` and `setting_text` of
// skills/specwright-pr/scripts/pr-pair.sh.

void main() {
  test('pyStr writes what str() writes', () {
    expect(pyStr(true), 'True');
    expect(pyStr(false), 'False');
    expect(pyStr(null), 'None');
    expect(pyStr(5), '5');
    expect(pyStr(BigInt.parse('99999999999999999999')), '99999999999999999999');
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
    final m = readSettingsYaml('a: true\nb: "q"\nc: 7\n');
    expect(settingText(m, 'a'), 'true');
    expect(settingText(m, 'b'), '"q"');
    expect(settingText(m, 'c'), '7');
    // a plain map has no text: a boolean is str(bool).lower()
    expect(settingText({'a': true}, 'a'), 'true');
    expect(settingText({'a': false}, 'a'), 'false');
    expect(settingText({'a': 5}, 'a'), '5');
    expect(settingText({'a': null}, 'a'), 'None');
    expect(settingText(m, 'absent'), 'None');
  });

  test('pyDecimalValue converts every Unicode decimal digit', () {
    expect(pyDecimalValue('123'), BigInt.from(123));
    expect(pyDecimalValue('٣١'), BigInt.from(31));
    expect(pyDecimalValue('१२'), BigInt.from(12));
    expect(pyDecimalValue('\u{1D7D9}\u{1D7DA}'), BigInt.from(12));
    expect(pyDecimalValue('\u{1D7FF}'), BigInt.from(9));
    expect(pyDecimalValue(''), isNull);
    expect(pyDecimalValue('1a'), isNull);
    expect(pyDecimalValue('²'), isNull, reason: 'superscript two is No');
  });

  test('pyIntNormal is an int up to 64 bits, else a BigInt', () {
    expect(pyIntNormal(BigInt.from(7)), 7);
    expect(
      pyIntNormal(BigInt.parse('9223372036854775807')),
      9223372036854775807,
    );
    final big = BigInt.parse('9223372036854775808');
    expect(pyIntNormal(big), big);
  });

  test('pyUtf8Decode replaces bad bytes and keeps a leading BOM', () {
    expect(pyUtf8Decode([0x61, 0xff, 0x62]), 'a�b');
    expect(pyUtf8Decode([0xef, 0xbb, 0xbf, 0x61]), '﻿a');
  });
}
