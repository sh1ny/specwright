import 'dart:convert';

import 'package:specwright_cli/src/pr/text.dart';
import 'package:test/test.dart';

void main() {
  group('command substitution', () {
    test('drops every trailing newline and nothing else', () {
      expect(dropTrailingNewlines('a\n\n\n'), 'a');
      expect(dropTrailingNewlines('a\nb \n'), 'a\nb ');
      expect(dropTrailingNewlines('\n\n'), '');
    });
  });

  group('grep -q', () {
    test('any line matching is enough', () {
      expect(grepQuiet(RegExp(r'^[1-9][0-9]*$'), '0x\n12'), isTrue);
      expect(grepQuiet(RegExp(r'^[1-9][0-9]*$'), '0\n1x'), isFalse);
    });
  });

  group('paste', () {
    test('joins columns lines with commas and pads the last row', () {
      expect(paste(['a', 'b', 'c', 'd'], 3), ['a,b,c', 'd,,']);
      expect(paste(['a', 'b'], 2), ['a,b']);
      expect(paste([], 2), isEmpty);
    });

    test('sed strips the trailing commas', () {
      expect(stripTrailingCommas('d,,'), 'd');
      expect(stripTrailingCommas('a,b'), 'a,b');
    });
  });

  group('reaction re-check batches', () {
    List<String> idList(int n) => [for (var i = 1; i <= n; i++) 'I$i'];

    test('no ids give no batch', () {
      expect(recheckBatches(const []), isEmpty);
    });

    test('a few ids are one batch', () {
      expect(recheckBatches(idList(3)), ['"I1","I2","I3"']);
    });

    test('25 ids to a line and 4 lines to a batch: 100 ids a query', () {
      final batches = recheckBatches(idList(101));
      expect(batches, hasLength(2));
      expect(batches.first.split(','), hasLength(100));
      expect(batches.first.split(',').first, '"I1"');
      expect(batches.first.split(',').last, '"I100"');
      expect(batches.last, '"I101"');
    });

    test('exactly 100 ids are one batch and 125 two', () {
      expect(recheckBatches(idList(100)), hasLength(1));
      final two = recheckBatches(idList(125));
      expect(two.map((b) => b.split(',').length), [100, 25]);
    });
  });

  group('the Date header', () {
    test('is the value of the first Date line, CR removed', () {
      const raw =
          'HTTP/2.0 200 OK\r\nContent-Type: x\r\nDate: Mon, 02 Nov 2026 10:00:00 GMT\r\n\r\n{}';
      expect(dateHeaderOf(raw), 'Mon, 02 Nov 2026 10:00:00 GMT');
    });

    test('is case-insensitive on the first letter only, and first only', () {
      expect(dateHeaderOf('date: a\nDate: b'), 'a');
      expect(dateHeaderOf('DATE: a'), '');
      expect(dateHeaderOf('x-date: a'), '');
    });
  });

  group('head -n 1 | tr -d \\r', () {
    test('is the first line without a carriage return', () {
      expect(firstLine('one\r\ntwo\n'), 'one');
      expect(firstLine('only'), 'only');
      expect(firstLine(''), '');
    });
  });

  group('tail -n 80', () {
    List<int> lines(int n, {bool end = true}) => utf8.encode(
      [for (var i = 1; i <= n; i++) 'l$i'].join('\n') + (end ? '\n' : ''),
    );

    test('keeps the last 80 lines', () {
      final out = utf8.decode(tailLines(lines(100), 80)).split('\n');
      expect(out.first, 'l21');
      expect(out[79], 'l100');
      expect(out.last, '');
    });

    test('keeps a shorter input whole', () {
      expect(tailLines(lines(3), 80), lines(3));
      expect(tailLines(lines(80), 80), lines(80));
      expect(tailLines(const [], 80), isEmpty);
    });

    test(
      'a last line with no newline counts as a line and stays without one',
      () {
        final out = utf8.decode(tailLines(lines(81, end: false), 80));
        expect(out.startsWith('l2\n'), isTrue);
        expect(out.endsWith('l81'), isTrue);
      },
    );
  });
}
