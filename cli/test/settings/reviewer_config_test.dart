import 'dart:convert';
import 'dart:io';

import 'package:specwright_cli/src/settings/reviewer_config.dart';
import 'package:specwright_cli/src/settings/rules.dart';
import 'package:test/test.dart';

// The expected bytes and digests come from CPython 3.14 running the frozen `reviewer_config_bytes` with `"format": 2`
// in place of 1 (design D10): `json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`, encoded
// with `errors="replace"`. The sets are those of `evals/pr-pair/test_pr_pair.py` (`rv(...)`, `config_bytes(...)`).

Reviewer _rv(
  String role, {
  Object timeout = 1200,
  String request = '',
  Map<String, String> report = const {},
}) => Reviewer(role, timeout, request, report);

String _text(List<int> bytes) => utf8.decode(bytes);

const _codex = 'chatgpt-codex-connector';

void main() {
  group('reviewerConfigBytes', () {
    test('format 2, sorted by login, sorted keys, compact, no request', () {
      final bytes = reviewerConfigBytes({
        'kody-ai': _rv('advisory', timeout: 900, request: '@kody review'),
        _codex: _rv('required', request: '@codex review'),
        'check-bot': _rv('required', report: {'check': 'Bot Code Review'}),
      });
      expect(
        _text(bytes),
        '{"format":2,"reviewers":[{"login":"chatgpt-codex-connector","report":{},"role":"required","timeout":1200},'
        '{"login":"check-bot","report":{"check":"Bot Code Review"},"role":"required","timeout":1200},'
        '{"login":"kody-ai","report":{},"role":"advisory","timeout":900}]}',
      );
      expect(
        sha256Hex(bytes),
        'd4d13cf05d0495d5b359fa29eae32cb786bb4c944db06487cb102183fc9c8b8e',
      );
    });

    test('an empty set', () {
      final bytes = reviewerConfigBytes({});
      expect(_text(bytes), '{"format":2,"reviewers":[]}');
      expect(
        sha256Hex(bytes),
        'f02f2bf617c0d213bc56f47c59c76c31d8dee60f0fb0e79e9be405417d8564ff',
      );
    });

    test('a pattern keeps its backslashes, quotes and backticks', () {
      const pattern =
          r'Reviewed commit: `([0-9a-f]{7,40})` \\ "quoted" it'
          "'"
          r's: done\*';
      final bytes = reviewerConfigBytes({
        'rev-bot': _rv('required', report: {'sha_pattern': pattern}),
      });
      expect(
        _text(bytes),
        r'''{"format":2,"reviewers":[{"login":"rev-bot","report":{"sha_pattern":"Reviewed commit: `([0-9a-f]{7,40})` \\\\ \"quoted\" it's: done\\*"},"role":"required","timeout":1200}]}''',
      );
      expect(
        sha256Hex(bytes),
        'f25e5e1497b46cdf39ff351a5b5e001eef0ace2dace835b80b6483038628dc9f',
      );
      // the file reads back as the same pattern
      final back = jsonDecode(_text(bytes)) as Map<String, Object?>;
      final entry = (back['reviewers']! as List).single as Map<String, Object?>;
      expect((entry['report']! as Map)['sha_pattern'], pattern);
    });

    test('logins sort by code point, not by UTF-16 unit', () {
      final bytes = reviewerConfigBytes({
        '\u{10000}': _rv('required'),
        'z': _rv('required'),
        '\u{e000}': _rv('required'),
        '\u{e9}': _rv('required'),
      });
      final logins = [
        for (final e
            in (jsonDecode(_text(bytes))['reviewers'] as List<Object?>))
          (e! as Map)['login'],
      ];
      expect(logins, ['z', '\u{e9}', '\u{e000}', '\u{10000}']);
      expect(
        sha256Hex(bytes),
        '1b146d21d5356f3ed86835a731a8cc7a66c30ef3444455956b3cda141567385e',
      );
    });

    test('report keys sort by code point too, and non-ASCII stays raw', () {
      final bytes = reviewerConfigBytes({
        'x': _rv(
          'required',
          report: {
            '\u{10000}': '4',
            'zeta': '1',
            '\u{e000}': '3',
            'alpha': '2',
          },
        ),
      });
      expect(
        _text(bytes),
        '{"format":2,"reviewers":[{"login":"x","report":{"alpha":"2","zeta":"1","\u{e000}":"3","\u{10000}":"4"},'
        '"role":"required","timeout":1200}]}',
      );
      expect(
        sha256Hex(bytes),
        '1a52cd6677b3436e509f8a4dbcd7ae7cd020410374bfd8091b930db62de19a89',
      );
    });

    test('a lone surrogate encodes as ? (errors="replace")', () {
      final bytes = reviewerConfigBytes({
        'a${String.fromCharCode(0xd800)}b': _rv('required'),
      });
      expect(
        _text(bytes),
        '{"format":2,"reviewers":[{"login":"a?b","report":{},"role":"required","timeout":1200}]}',
      );
      expect(
        sha256Hex(bytes),
        '3f44a412a18e289b35fe4ebe799ed6103bad7e3838281b8d135dff8402434154',
      );
    });

    test('U+2028 stays raw and a timeout past 64 bits keeps its digits', () {
      final bytes = reviewerConfigBytes({
        'x': _rv('a\u{2028}b', timeout: BigInt.two.pow(70)),
      });
      expect(
        _text(bytes),
        '{"format":2,"reviewers":[{"login":"x","report":{},"role":"a\u{2028}b","timeout":1180591620717411303424}]}',
      );
      expect(
        sha256Hex(bytes),
        '14ca437060bb2844f03f9849ec9514ac4214641a85cc5f71e132745468e0dc63',
      );
    });
  });

  group('compareCodePoints', () {
    test('orders by code point', () {
      expect(compareCodePoints('a', 'b'), lessThan(0));
      expect(compareCodePoints('b', 'a'), greaterThan(0));
      expect(compareCodePoints('a', 'a'), 0);
      expect(compareCodePoints('a', 'ab'), lessThan(0));
      expect(compareCodePoints('\u{e000}', '\u{10000}'), lessThan(0));
      expect(
        '\u{e000}'.compareTo('\u{10000}'),
        greaterThan(0),
        reason: 'UTF-16 order is the other way',
      );
    });
  });

  group('sha256Hex', () {
    test('matches the FIPS 180 vectors', () {
      expect(
        sha256Hex(utf8.encode('')),
        'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
      );
      expect(
        sha256Hex(utf8.encode('abc')),
        'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad',
      );
      expect(
        sha256Hex(utf8.encode('a' * 1000)),
        '41edece42d63e8d9bf515a9ba6932e1c20cbc9f5a5d134645adb5db1b9737ea3',
      );
      expect(
        sha256Hex(
          utf8.encode(
            'abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq',
          ),
        ),
        '248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1',
      );
    });

    test('pads across the 55/56/64 byte boundaries', () {
      // from hashlib.sha256(b"a" * n)
      const want = {
        55: '9f4390f8d30c2dd92ec9f095b65e2b9ae9b0a925a5258e241c9f1e910f734318',
        56: 'b35439a4ac6f0948b6d6f9e3c6af0f5f590ce20f1bde7090ef7970686ec6738a',
        63: '7d3e74a05d7db15bce4ad9ec0658ea98e3f06eeecf16b4c6fff2da457ddc2f34',
        64: 'ffe054fe7ae0cb6dc65c3af9b61d5209f439851db43d0ba5997337df154668eb',
        65: '635361c48bb9eab14198e76ea8ab7f1a41685d6ad62aa9146d301d4f17eb0ae0',
      };
      for (final e in want.entries) {
        expect(
          sha256Hex(utf8.encode('a' * e.key)),
          e.value,
          reason: '${e.key}',
        );
      }
    });
  });

  group('writeReviewerConfig', () {
    late Directory tmp;
    late String state;
    late String sys;

    setUp(() {
      tmp = Directory.systemTemp.createTempSync('claude-g3-config-');
      state = '${tmp.path}/state';
      sys = '${tmp.path}/systmp';
      Directory(sys).createSync();
    });
    tearDown(() => tmp.deleteSync(recursive: true));

    String norm(String p) => p.replaceAll(r'\', '/');

    final set = {
      'kody-ai': _rv('advisory', timeout: 900),
      _codex: _rv('required'),
    };

    test(
      'names the file by the SHA-256 of its bytes under <state>/reviewers',
      () {
        final r = writeReviewerConfig(
          set,
          environment: {'SPECWRIGHT_STATE_DIR': state},
          tempDirectory: sys,
        );
        final bytes = reviewerConfigBytes(set);
        final digest = sha256Hex(bytes);
        expect(r.digest, digest);
        expect(r.problem, isNull);
        expect(r.path, '${norm(state)}/reviewers/$digest.json');
        expect(File(r.path!).readAsBytesSync(), bytes);
        expect(
          Directory('$state/reviewers').listSync().map((e) => norm(e.path)),
          [r.path],
          reason: 'no temp file is left behind',
        );
      },
    );

    test('uses ~/.cache/specwright when no state directory is set', () {
      final home = '${tmp.path}/home';
      final r = writeReviewerConfig(
        set,
        environment: {'HOME': home, 'USERPROFILE': home},
        tempDirectory: sys,
      );
      expect(
        r.path,
        '${norm(home)}/.cache/specwright/reviewers/${r.digest}.json',
      );
      expect(File(r.path!).existsSync(), true);
    });

    test('an empty SPECWRIGHT_STATE_DIR counts as unset', () {
      final home = '${tmp.path}/home';
      final r = writeReviewerConfig(
        set,
        environment: {
          'SPECWRIGHT_STATE_DIR': '',
          'HOME': home,
          'USERPROFILE': home,
        },
        tempDirectory: sys,
      );
      expect(r.path, startsWith('${norm(home)}/.cache/specwright/'));
    });

    test('reuses an existing file with the same bytes', () {
      final env = {'SPECWRIGHT_STATE_DIR': state};
      final first = writeReviewerConfig(
        set,
        environment: env,
        tempDirectory: sys,
      );
      final file = File(first.path!);
      final old = DateTime.utc(2001, 2, 3);
      file.setLastModifiedSync(old);
      final second = writeReviewerConfig(
        set,
        environment: env,
        tempDirectory: sys,
      );
      expect(second.path, first.path);
      expect(second.digest, first.digest);
      expect(file.lastModifiedSync().toUtc(), old, reason: 'not rewritten');
      expect(Directory('$state/reviewers').listSync(), hasLength(1));
    });

    test('replaces a file of that name whose bytes differ', () {
      final env = {'SPECWRIGHT_STATE_DIR': state};
      final digest = sha256Hex(reviewerConfigBytes(set));
      File('$state/reviewers/$digest.json')
        ..createSync(recursive: true)
        ..writeAsStringSync('garbage');
      final r = writeReviewerConfig(set, environment: env, tempDirectory: sys);
      expect(File(r.path!).readAsBytesSync(), reviewerConfigBytes(set));
      expect(Directory('$state/reviewers').listSync(), hasLength(1));
    });

    test('falls back to <temp>/specwright/reviewers when the state directory is not usable', () {
      final blocker = File('${tmp.path}/blocker')
        ..writeAsStringSync('a file, so nothing can be created below it');
      final r = writeReviewerConfig(
        set,
        environment: {'SPECWRIGHT_STATE_DIR': '${blocker.path}/state'},
        tempDirectory: sys,
      );
      expect(r.path, '${norm(sys)}/specwright/reviewers/${r.digest}.json');
      expect(File(r.path!).readAsBytesSync(), reviewerConfigBytes(set));
      expect(r.problem, isNull);
    });

    test(
      'the temp directory comes from TMPDIR, TEMP or TMP when not given',
      () {
        final blocker = File('${tmp.path}/blocker')..writeAsStringSync('x');
        final r = writeReviewerConfig(
          set,
          environment: {
            'SPECWRIGHT_STATE_DIR': '${blocker.path}/state',
            'TMPDIR': '${tmp.path}/not-a-dir',
            'TEMP': sys,
            'TMP': '${tmp.path}/other',
          },
        );
        expect(r.path, '${norm(sys)}/specwright/reviewers/${r.digest}.json');
      },
    );

    test(
      'the path is null when neither place is writable, and no temp file stays',
      () {
        final blocker = File('${tmp.path}/blocker')..writeAsStringSync('x');
        final r = writeReviewerConfig(
          set,
          environment: {'SPECWRIGHT_STATE_DIR': '${blocker.path}/state'},
          tempDirectory: '${blocker.path}/tmp',
        );
        expect(r.path, isNull);
        expect(r.digest, sha256Hex(reviewerConfigBytes(set)));
        expect(r.problem, isNull);
      },
    );

    test('a directory in the way of the file fails the place and cleans its temp file', () {
      final digest = sha256Hex(reviewerConfigBytes(set));
      final inTheWay = Directory('$state/reviewers/$digest.json')
        ..createSync(recursive: true);
      final r = writeReviewerConfig(
        set,
        environment: {'SPECWRIGHT_STATE_DIR': state},
        tempDirectory: sys,
      );
      expect(
        r.path,
        '${norm(sys)}/specwright/reviewers/$digest.json',
        reason: 'the temp directory takes it',
      );
      expect(
        Directory('$state/reviewers').listSync().map((e) => norm(e.path)),
        [norm(inTheWay.path)],
        reason: 'the .tmp-*.json beside the target was removed',
      );
    });

    group('the 64 KiB bound', () {
      Reviewer withReport(int n) => _rv('required', report: {'k': 'x' * n});

      test('a config under 64 KiB has no problem', () {
        final base = reviewerConfigBytes({'x': withReport(0)}).length;
        final set = {'x': withReport(maxConfigBytes - 1 - base)};
        expect(reviewerConfigBytes(set), hasLength(maxConfigBytes - 1));
        final r = writeReviewerConfig(
          set,
          environment: {'SPECWRIGHT_STATE_DIR': state},
          tempDirectory: sys,
        );
        expect(r.problem, isNull);
        expect(r.path, isNotNull);
      });

      test(
        '64 KiB or more is a problem, and the file is still written in full',
        () {
          final base = reviewerConfigBytes({'x': withReport(0)}).length;
          final set = {'x': withReport(maxConfigBytes - base)};
          final bytes = reviewerConfigBytes(set);
          expect(bytes, hasLength(maxConfigBytes));
          final r = writeReviewerConfig(
            set,
            environment: {'SPECWRIGHT_STATE_DIR': state},
            tempDirectory: sys,
          );
          expect(r.problem, isNotNull);
          expect(r.problem!.error, 'bad_setting');
          expect(r.problem!.key, 'reviewer config');
          expect(
            r.problem!.why,
            startsWith('65536 bytes is over the 64 KB limit'),
          );
          expect(r.path, isNotNull);
          expect(File(r.path!).readAsBytesSync(), bytes);
          expect(r.digest, sha256Hex(bytes));
        },
      );
    });
  });
}
