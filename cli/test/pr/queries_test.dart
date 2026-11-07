import 'dart:io';

import 'package:specwright_cli/src/pr/queries.dart';
import 'package:test/test.dart';

/// The frozen oracle scripts (design D12): the text in `queries.dart` is theirs,
/// byte for byte (constraint C4).
String oracle(String name) {
  var dir = Directory.current;
  while (!File('${dir.path}/evals/pr-pair/oracle/$name').existsSync()) {
    final parent = dir.parent;
    if (parent.path == dir.path) {
      fail('no evals/pr-pair/oracle/$name above cwd');
    }
    dir = parent;
  }
  return File('${dir.path}/evals/pr-pair/oracle/$name').readAsStringSync();
}

/// The body of `<<'TAG'` as `read -r -d ''` keeps it: no leading or trailing
/// white space.
String heredoc(String source, String tag) {
  final open = source.indexOf("<<'$tag'");
  final start = source.indexOf('\n', open) + 1;
  final end = source.indexOf('\n$tag\n', start);
  return source.substring(start, end + 1).trim();
}

void main() {
  final snap = oracle('pr-snapshot.sh');
  final reply = oracle('pr-reply.sh');

  group('pr-snapshot.sh text', () {
    test('the GraphQL heredoc is the oracle QUERY', () {
      expect(snapshotQuery, heredoc(snap, 'GQL'));
    });

    test('the jq heredoc is the oracle SHAPE', () {
      expect(snapshotShape, heredoc(snap, 'JQ'));
    });

    test('every single-quoted program is in the oracle as written', () {
      for (final (name, text) in {
        'fullQuery': fullQuery,
        'fullJq': fullJq,
        'cfgQuery': cfgQuery,
        'cfgJq': cfgJq,
        'reactionJq': reactionJq,
        'repoViewJq': repoViewJq,
      }.entries.map((e) => (e.key, e.value))) {
        expect(snap, contains("'$text'"), reason: name);
      }
    });

    test('the reaction query is the double-quoted text with the ids in it', () {
      expect(snap, contains('"${reactionQuery(r'$ids')}"'));
      expect(reactionQuery('"A","B"'), contains('nodes(ids:["A","B"]) {'));
    });

    test('--jq .number is the oracle one', () {
      expect(snap, contains('--jq $prNumberJq'));
    });
  });

  group('pr-reply.sh text', () {
    test('every single-quoted program is in the oracle as written', () {
      for (final (name, text) in {
        'pendingQuery': pendingQuery,
        'pendingJq': pendingJq,
        'revQuery': revQuery,
        'revJq': revJq,
        'reactNodeQuery': reactNodeQuery,
        'reactNodeJq': reactNodeJq,
        'reactRestJq': reactRestJq,
        'resolveQuery': resolveQuery,
        'resolveJq': resolveJq,
        'repoViewJq': repoViewJq,
        'htmlUrlJq': htmlUrlJq,
      }.entries.map((e) => (e.key, e.value))) {
        expect(reply, contains("'$text'"), reason: name);
      }
    });
  });

  group('cfg text', () {
    test('the default and the built cfg are the oracle text', () {
      expect(snap, contains("CFG='$cfgDefault'"));
      // prepare_cfg builds its CFG in a double-quoted string
      final built = cfgFor(
        logins: r'$logins',
        oid: r'$oid',
        pushed: r'$pushed',
        cutoff: r'$cutoff',
        date: r'$date',
      );
      expect(snap, contains('CFG="${built.replaceAll('"', r'\"')}"'));
    });

    test('the pushed and cutoff pieces are the oracle text', () {
      expect(
        snap,
        contains(
          'pushed="${pushedAtJq(r'$pushed_at').replaceAll('"', r'\"')}"',
        ),
      );
      expect(
        snap,
        contains(
          'cutoff="${cutoffJq('push', r'$pushed').replaceAll('"', r'\"')}"',
        ),
      );
      expect(
        snap,
        contains(
          'pushed="${firstSeenJq(r'$seen_date').replaceAll('"', r'\"')}"',
        ),
      );
      expect(
        snap,
        contains(
          'cutoff="${cutoffJq(r'$seen_src', r'$pushed').replaceAll('"', r'\"')}"',
        ),
      );
    });

    test('the activity program is the oracle text', () {
      expect(snap, contains('"${activityJq(r'$oid').replaceAll('"', r'\"')}"'));
    });

    test('query_pr puts cfg, rtimes and the shape on lines of their own', () {
      expect(prJq('C', 'R'), 'C\nR\n$snapshotShape');
    });
  });
}
