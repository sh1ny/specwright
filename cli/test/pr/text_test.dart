import 'dart:convert';

import 'package:specwright_cli/src/pr/text.dart';
import 'package:test/test.dart';

String ids(int n) => [for (var i = 1; i <= n; i++) '"I$i"'].join(',');

void main() {
  group('command substitution', () {
    test('drops every trailing newline and nothing else', () {
      expect(dropTrailingNewlines('a\n\n\n'), 'a');
      expect(dropTrailingNewlines('a\nb \n'), 'a\nb ');
      expect(dropTrailingNewlines('\n\n'), '');
    });
  });

  group('grep -o', () {
    test('prints each match on a line of its own, line by line', () {
      expect(grepOnly(RegExp(r'[0-9]+'), 'a1b22\nc333'), ['1', '22', '333']);
    });

    test('a pattern with no match prints nothing', () {
      expect(grepOnly(RegExp(r'x'), 'abc'), isEmpty);
    });

    test('quiet: any line matching is enough', () {
      expect(grepQuiet(RegExp(r'^[1-9][0-9]*$'), '0x\n12'), isTrue);
      expect(grepQuiet(RegExp(r'^[1-9][0-9]*$'), '0\n1x'), isFalse);
    });
  });

  group('head oid', () {
    test('is the first "head_oid" value of the snapshot', () {
      final oid = 'a' * 40;
      expect(headOidOf('{"x":1,"head_oid":"$oid","y":"head_oid"}'), oid);
    });

    test('is empty with no head_oid, or an empty one', () {
      expect(headOidOf('{"x":1}'), '');
      expect(headOidOf('{"head_oid":""}'), '');
    });

    test('a body that quotes the key does not count', () {
      expect(headOidOf(r'{"body":"\"head_oid\":\"abc\""}'), '');
    });
  });

  group('sed -n logins', () {
    test('is the list body of the check output', () {
      expect(loginsOf('{"ok":true,"logins":["a","b"],"x":1}\n'), '"a","b"');
    });

    test('takes the last "logins" of a line, as the greedy pattern does', () {
      expect(loginsOf('{"logins":["a"],"z":{"logins":["b"]}}'), '"b"');
    });

    test('is empty when there is none', () {
      expect(loginsOf('{"ok":true}'), '');
      expect(loginsOf('{"logins":[]}'), '');
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
    String snapshot(int n) => '{"x":1,"recheck":[${ids(n)}],"y":2}';

    test('no recheck list or an empty one gives no batch', () {
      expect(recheckBatches('{"x":1}'), isEmpty);
      expect(recheckBatches('{"recheck":[]}'), isEmpty);
    });

    test('a few ids are one batch', () {
      expect(recheckBatches(snapshot(3)), ['"I1","I2","I3"']);
    });

    test('25 ids to a line and 4 lines to a batch: 100 ids a query', () {
      final batches = recheckBatches(snapshot(101));
      expect(batches, hasLength(2));
      expect(batches.first.split(','), hasLength(100));
      expect(batches.first.split(',').first, '"I1"');
      expect(batches.first.split(',').last, '"I100"');
      expect(batches.last, '"I101"');
    });

    test('exactly 100 ids are one batch and 125 two', () {
      expect(recheckBatches(snapshot(100)), hasLength(1));
      final two = recheckBatches(snapshot(125));
      expect(two.map((b) => b.split(',').length), [100, 25]);
    });

    test('an id with other characters is not an id', () {
      expect(recheckBatches(r'{"recheck":["A_b=-9","a b"]}'), ['"A_b=-9"']);
    });
  });

  group('sig, attn and fail names', () {
    const snap =
        '{"sig":"abc","attn":"d e","fail_names":["Zm9v","YmFy"],'
        r'"body":"\"sig\":\"no\""}';

    test('a member is its first quoted form', () {
      expect(memberOf(snap, 'sig'), '"sig":"abc"');
      expect(memberOf(snap, 'attn'), '"attn":"d e"');
      expect(memberOf('{}', 'sig'), '');
    });

    test('the failing check names are the quoted base64 strings', () {
      expect(failNamesOf(snap), ['"Zm9v"', '"YmFy"']);
      expect(failNamesOf('{"fail_names":[]}'), isEmpty);
    });

    test('the failing run ids are the numbers of the list', () {
      expect(failRunIdsOf('{"fail_run_ids":[12,345],"x":[6]}'), ['12', '345']);
      expect(failRunIdsOf('{"fail_run_ids":[]}'), isEmpty);
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
