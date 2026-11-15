// Tests of the release settings and version files (cli/lib/src/release/
// settings.dart and versions.dart): the entries, one match per file,
// agreement, CRLF offsets, and the bump write plan.
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:path/path.dart' as p;
import 'package:specwright_cli/src/release/settings.dart';
import 'package:specwright_cli/src/release/stop.dart';
import 'package:specwright_cli/src/release/versions.dart';
import 'package:test/test.dart';

const _plain = r'^(\d+\.\d+\.\d+)$';
const _badge = r'badge/version-(\d+\.\d+\.\d+)-blue';

Matcher stops(String error, [List<String> parts = const []]) => throwsA(
  isA<ReleaseStop>()
      .having((e) => e.error, 'error', error)
      .having((e) => e.message, 'message', allOf(parts.map(contains).toList())),
);

void main() {
  late Directory root;
  setUp(() => root = Directory.systemTemp.createTempSync('sw-versions-'));
  tearDown(() => root.deleteSync(recursive: true));

  String path(String rel) => p.join(root.path, rel);
  void write(String rel, Object content) {
    final file = File(path(rel))..parent.createSync(recursive: true);
    file.writeAsBytesSync(
      content is String ? utf8.encode(content) : content as List<int>,
    );
  }

  Uint8List bytes(String rel) => File(path(rel)).readAsBytesSync();
  String text(String rel) => utf8.decode(bytes(rel));

  // Writes openspec/specwright.yaml with the given version_files and returns
  // the entries the settings read from it.
  List<VersionEntry> entries(Map<String, String> files, {String extra = ''}) {
    final yaml = StringBuffer(
      'release:\n  enabled: true\n$extra  version_files:\n',
    );
    files.forEach((k, v) => yaml.writeln("    \"$k\": '$v'"));
    write('openspec/specwright.yaml', yaml.toString());
    return readReleaseSettings(root.path).entries();
  }

  String git(List<String> args) {
    final r = Process.runSync('git', [
      '-c',
      'user.name=t',
      '-c',
      'user.email=t@t.invalid',
      '-c',
      'commit.gpgsign=false',
      ...args,
    ], workingDirectory: root.path);
    expect(r.exitCode, 0, reason: '${r.stderr}');
    return (r.stdout as String).trim();
  }

  group('settings', () {
    test('a missing file reads as empty, and the gate stops', () async {
      final s = readReleaseSettings(root.path);
      expect(s.enabled, isFalse);
      expect(s.tag, 'v{version}');
      expect(s.githubRelease, isTrue);
      expect(s.mergeMethod, '');
      expect(s.finish, isNull);
      expect(s.mainBranch, isNull);
      expect(() => s.gate(), stops('release_disabled'));
      expect(() => s.entries(), stops('no_version_files'));
    });

    test('values map as the script mapped them', () {
      write('openspec/specwright.yaml', '''
main_branch: trunk
finish: pr
release:
  enabled: true
  tag: "rel-{version}"
  github_release: false
  auto: true
pr:
  merge_method: Rebase
''');
      final s = readReleaseSettings(root.path);
      expect(s.enabled, isTrue);
      expect(s.tag, 'rel-{version}');
      expect(s.githubRelease, isFalse);
      expect(s.auto, isTrue);
      expect(s.mergeMethod, 'rebase');
      expect(s.finish, 'pr');
      expect(s.mainBranch, 'trunk');
      s.gate();
      expect(() => s.gate(rebase: true), stops('rebase_merge'));
    });

    test('release.enabled counts only when it is true', () {
      write('openspec/specwright.yaml', 'release:\n  enabled: "true"\n');
      expect(readReleaseSettings(root.path).enabled, isFalse);
    });

    test('a tag template without {version} stops the gate', () {
      write(
        'openspec/specwright.yaml',
        'release:\n  enabled: true\n  tag: fixed\n',
      );
      expect(
        () => readReleaseSettings(root.path).gate(),
        stops('bad_tag_template', ['fixed']),
      );
    });

    test('a misreadable line is bad_settings naming the line', () {
      write('openspec/specwright.yaml', 'release:\n\tenabled: true\n');
      expect(
        () => readReleaseSettings(root.path),
        stops('bad_settings', ['line 2']),
      );
      write(
        'openspec/specwright.yaml',
        'release:\n  enabled: true\nrelease:\n  enabled: false\n',
      );
      expect(
        () => readReleaseSettings(root.path),
        stops('bad_settings', ['line 3']),
      );
    });

    test('a stop serialises as the script did', () {
      expect(ReleaseStop('x', 'm', code: 3, extra: {'k': 1}).toJson(), {
        'ok': false,
        'error': 'x',
        'message': 'm',
        'k': 1,
      });
    });
  });

  group('entries', () {
    test('the shipped patterns compile with one group each', () {
      final list = entries({
        'VERSION': _plain,
        'README.md': _badge,
        'skills/*/SKILL.md': r'^  version: (\S+)$',
      });
      expect(list.map((e) => e.path), [
        'VERSION',
        'README.md',
        'skills/*/SKILL.md',
      ]);
      expect(list.first.pattern, _plain);
    });

    for (final (name, pattern, hint) in [
      ('no group', r'^\d+$', 'has 0'),
      ('two groups', r'^(\d+)\.(\d+)$', 'has 2'),
      (
        'a named group in the Python dialect',
        r'(?P<v>\d+\.\d+\.\d+)',
        'invalid pattern',
      ),
      ('a Python start anchor', r'\A(\d+)', 'invalid pattern'),
      ('a Python end anchor', r'(\d+)\Z', 'invalid pattern'),
      ('an inline flag', r'(?i)(\d+)', 'invalid pattern'),
    ]) {
      test('$name is bad_version_files naming the entry', () {
        expect(
          () => entries({'VERSION': pattern}),
          stops('bad_version_files', ["entry 'VERSION'", hint]),
        );
      });
    }

    test('a path outside the repository is refused', () {
      for (final bad in ['/etc/x', '../x', 'a/../x', 'C:/x']) {
        expect(() => entries({bad: _plain}), stops('bad_version_files', [bad]));
      }
    });

    test('no entries is no_version_files', () {
      write('openspec/specwright.yaml', 'release:\n  enabled: true\n');
      expect(
        () => readReleaseSettings(root.path).entries(),
        stops('no_version_files'),
      );
    });
  });

  group('reading the work tree', () {
    test('one match per file and one shared version agree', () async {
      write('VERSION', '0.4.2\n');
      write('README.md', '![v](https://x/badge/version-0.4.2-blue)\n');
      write('skills/a/SKILL.md', 'metadata:\n  version: 0.4.2\n');
      final list = entries({
        'VERSION': _plain,
        'README.md': _badge,
        'skills/*/SKILL.md': r'^  version: (\S+)$',
      });
      final got = await agree(WorkTree(root.path), list);
      expect(got.version, '0.4.2');
      expect(got.files, ['README.md', 'VERSION', 'skills/a/SKILL.md']);
    });

    test('a file with two matches stops version_files_invalid', () async {
      write('VERSION', '0.4.2\n0.4.2\n');
      final list = entries({'VERSION': _plain});
      await expectLater(
        agree(WorkTree(root.path), list),
        throwsA(
          isA<ReleaseStop>()
              .having((e) => e.error, 'error', 'version_files_invalid')
              .having(
                (e) => e.message,
                'message',
                allOf(contains('VERSION'), contains('matches 2 times')),
              )
              .having((e) => e.extra['files'], 'files', ['VERSION'])
              .having((e) => e.extra['problems'], 'problems', [
                {
                  'kind': 'match_count',
                  'file': 'VERSION',
                  'entry': 'VERSION',
                  'pattern': _plain,
                  'count': 2,
                },
              ]),
        ),
      );
    });

    test(
      'a file with no match and an entry with no file are problems',
      () async {
        write('VERSION', 'nothing\n');
        final list = entries({'VERSION': _plain, 'MISSING': _plain});
        await expectLater(
          agree(WorkTree(root.path), list),
          stops('version_files_invalid', [
            'matches 0 times',
            "'MISSING' matches no file in the working tree",
          ]),
        );
      },
    );

    test('differing versions stop version_files_disagree', () async {
      write('VERSION', '0.4.2\n');
      write('README.md', 'badge/version-0.4.3-blue');
      final list = entries({'VERSION': _plain, 'README.md': _badge});
      await expectLater(
        agree(WorkTree(root.path), list),
        throwsA(
          isA<ReleaseStop>()
              .having((e) => e.error, 'error', 'version_files_disagree')
              .having(
                (e) => e.message,
                'message',
                contains('0.4.2 in VERSION; 0.4.3 in README.md'),
              )
              .having((e) => e.extra['versions'], 'versions', {
                '0.4.2': ['VERSION'],
                '0.4.3': ['README.md'],
              }),
        ),
      );
    });

    test(
      'CRLF line ends match and the offsets index the original text',
      () async {
        write('VERSION', '0.4.2\r\n');
        final list = entries({'VERSION': _plain});
        final read = await readVersions(WorkTree(root.path), list);
        expect(read.problems, isEmpty);
        final hit = read.files.single.hits.single;
        expect((hit.value, hit.start, hit.end), ('0.4.2', 0, 5));
      },
    );

    test(
      'the version place is found past escapes, classes and other groups',
      () async {
        write('A', 'x(1) [0.4.2] y${'\n'}');
        write('B', 'ver: 0.4.2 0.4.2${'\n'}');
        write('C', 'a 0.4.2 b${'\n'}');
        for (final (file, pattern, start, end) in [
          ('A', r'\(1\) \[(\d+\.\d+\.\d+)\]', 6, 11),
          ('A', r'[(\[]1[)\]] \[(?<v>[\d.]+)\]', 6, 11),
          ('B', r'(?:ver|ver2): (?=\d)(\d+\.\d+\.\d+) \1', 5, 10),
          ('C', r'(?<=a )(\d+\.\d+\.\d+)(?! c)', 2, 7),
        ]) {
          final read = await readVersions(
            WorkTree(root.path),
            entries({file: pattern}),
          );
          final hit = read.files.single.hits.single;
          expect(
            (hit.value, hit.start, hit.end),
            ('0.4.2', start, end),
            reason: pattern,
          );
        }
      },
    );

    test('a malformed file still reads its version', () async {
      write('README.md', [...utf8.encode('badge/version-0.4.2-blue '), 0xff]);
      final got = await agree(
        WorkTree(root.path),
        entries({'README.md': _badge}),
      );
      expect(got.version, '0.4.2');
    });
  });

  group('reading a commit', () {
    test('names and blobs come from the commit, not the work tree', () async {
      git(['init', '-q']);
      write('VERSION', '0.4.2\n');
      write('skills/a/SKILL.md', 'x\n  version: 0.4.2\n');
      write('skills/.dot/SKILL.md', 'x\n  version: 0.4.2\n');
      git(['add', '-A']);
      git(['commit', '-q', '-m', 'one']);
      final commit = git(['rev-parse', 'HEAD']);
      write('VERSION', '0.9.9\n');
      final list = entries({
        'VERSION': _plain,
        'skills/*/SKILL.md': r'^  version: (\S+)$',
      });
      final tree = CommitTree(root.path, commit);
      expect(tree.label, 'commit ${commit.substring(0, 12)}');
      final got = await agree(tree, list);
      expect(got.version, '0.4.2');
      // C4: the commit glob matches the dot-directory the work tree skips.
      expect(got.files, [
        'VERSION',
        'skills/.dot/SKILL.md',
        'skills/a/SKILL.md',
      ]);
      await expectLater(
        agree(WorkTree(root.path), list),
        stops('version_files_disagree'),
      );
    });

    test(
      'a file missing at the commit reads as empty and has no match',
      () async {
        git(['init', '-q']);
        write('OTHER', 'x\n');
        git(['add', '-A']);
        git(['commit', '-q', '-m', 'one']);
        final tree = CommitTree(root.path, git(['rev-parse', 'HEAD']));
        final blobs = await tree.readAll(['VERSION']);
        expect(blobs['VERSION'], isEmpty);
      },
    );

    test('a symlink entry at the commit is refused', () async {
      git(['init', '-q']);
      write('real/VERSION', '0.4.2\n');
      git(['add', '-A']);
      git([
        'update-index',
        '--add',
        '--cacheinfo',
        '120000,${git(['rev-parse', ':real/VERSION'])},alias',
      ]);
      git(['commit', '-q', '-m', 'one']);
      final tree = CommitTree(root.path, git(['rev-parse', 'HEAD']));
      await expectLater(
        tree.files('alias'),
        stops('bad_version_files', ['alias', 'a symlink at commit']),
      );
    });

    test('catBlobs reads several specs in one call', () async {
      git(['init', '-q']);
      write('A', 'aa');
      write('B', 'bbb');
      git(['add', '-A']);
      git(['commit', '-q', '-m', 'one']);
      final commit = git(['rev-parse', 'HEAD']);
      final got = await catBlobs(root.path, [
        '$commit:A',
        '$commit:NOPE',
        '$commit:B',
      ]);
      expect(got.map((b) => b == null ? null : utf8.decode(b)), [
        'aa',
        null,
        'bbb',
      ]);
    });
  });

  group('bump', () {
    test('every file carries the target', () async {
      write('VERSION', '0.4.2\n');
      write('README.md', 'a badge/version-0.4.2-blue b\n');
      final list = entries({'VERSION': _plain, 'README.md': _badge});
      final done = await bump(root.path, list, '0.4.3');
      expect((done.from, done.to), ('0.4.2', '0.4.3'));
      expect(done.changed, ['README.md', 'VERSION']);
      expect(done.files, ['README.md', 'VERSION']);
      expect(text('VERSION'), '0.4.3\n');
      expect(text('README.md'), 'a badge/version-0.4.3-blue b\n');
      expect(
        Directory(root.path).listSync().map((e) => p.basename(e.path)),
        isNot(contains(startsWith('.release-'))),
      );
    });

    test(
      'a capture group with alternatives reads and bumps on either branch',
      () async {
        const alt = r'v=(0\.\d+\.\d+|1\.\d+\.\d+);';
        write('VERSION', 'head v=0.4.2; tail\n');
        final list = entries({'VERSION': alt});
        final first = await bump(root.path, list, '1.0.0');
        expect((first.from, first.to), ('0.4.2', '1.0.0'));
        expect(text('VERSION'), 'head v=1.0.0; tail\n');
        final second = await bump(root.path, list, '1.0.1');
        expect((second.from, second.to), ('1.0.0', '1.0.1'));
        expect(text('VERSION'), 'head v=1.0.1; tail\n');
        final named = entries({'VERSION': r'v=(?<v>0\.\d+\.\d+|1\.\d+\.\d+);'});
        expect((await bump(root.path, named, '1.0.2')).from, '1.0.1');
        expect(text('VERSION'), 'head v=1.0.2; tail\n');
      },
    );

    test('CRLF line ends are kept', () async {
      write('VERSION', '0.4.2\r\nsecond\r\n');
      final list = entries({'VERSION': r'^(\d+\.\d+\.\d+)$'});
      final got = await bump(root.path, list, '0.4.3');
      expect(got.changed, ['VERSION']);
      expect(bytes('VERSION'), utf8.encode('0.4.3\r\nsecond\r\n'));
    });

    test('a byte order mark and non-ASCII text are kept', () async {
      final original = [
        0xef,
        0xbb,
        0xbf,
        ...utf8.encode('é€ 0.4.2 \u{1F600}\n'),
      ];
      write('NOTE', original);
      await bump(root.path, entries({'NOTE': r'(\d+\.\d+\.\d+)'}), '0.4.3');
      expect(bytes('NOTE'), [
        0xef,
        0xbb,
        0xbf,
        ...utf8.encode('é€ 0.4.3 \u{1F600}\n'),
      ]);
    });

    test(
      'the plan holds the new bytes and nothing is written by planning',
      () async {
        write('VERSION', '0.4.2\n');
        write('README.md', 'badge/version-0.4.2-blue');
        final list = entries({'VERSION': _plain, 'README.md': _badge});
        final read = await readVersions(WorkTree(root.path), list);
        final plan = planBump(read, '0.4.3');
        expect(plan.keys, ['README.md', 'VERSION']);
        expect(plan['VERSION'], utf8.encode('0.4.3\n'));
        expect(text('VERSION'), '0.4.2\n');
      },
    );

    test('a rerun to the same target completes an interrupted bump', () async {
      write('VERSION', '0.4.3\n');
      write('README.md', 'badge/version-0.4.2-blue');
      final list = entries({'VERSION': _plain, 'README.md': _badge});
      await expectLater(
        agree(WorkTree(root.path), list),
        stops('version_files_disagree'),
      );
      final done = await bump(root.path, list, '0.4.3');
      expect(done.from, '0.4.2');
      expect(done.changed, ['README.md']);
      expect(text('README.md'), 'badge/version-0.4.3-blue');
      expect(text('VERSION'), '0.4.3\n');
    });

    test('a rerun to another target than the interrupted one stops', () async {
      write('VERSION', '0.4.3\n');
      write('README.md', 'badge/version-0.4.2-blue');
      final list = entries({'VERSION': _plain, 'README.md': _badge});
      await expectLater(
        bump(root.path, list, '0.4.4'),
        stops('version_files_disagree'),
      );
      expect(text('VERSION'), '0.4.3\n');
    });

    test(
      'a target that is not greater or not MAJOR.MINOR.PATCH stops',
      () async {
        write('VERSION', '0.4.2\n');
        final list = entries({'VERSION': _plain});
        await expectLater(
          bump(root.path, list, '0.4.2'),
          stops('target_not_greater', ['0.4.2']),
        );
        await expectLater(
          bump(root.path, list, '0.3.9'),
          stops('target_not_greater'),
        );
        await expectLater(
          bump(root.path, list, '1.0'),
          stops('bad_target', ['1.0']),
        );
        expect(text('VERSION'), '0.4.2\n');
      },
    );

    test('a non-UTF-8 file is refused before any write, and every file keeps its bytes', () async {
      final readme = [...utf8.encode('badge/version-0.4.2-blue '), 0xff, 0x0a];
      write('VERSION', '0.4.2\n');
      write('README.md', readme);
      final list = entries({'VERSION': _plain, 'README.md': _badge});
      await expectLater(
        bump(root.path, list, '0.4.3'),
        throwsA(
          isA<ReleaseStop>()
              .having((e) => e.error, 'error', 'bad_version_files')
              .having((e) => e.code, 'code', 1)
              .having((e) => e.message, 'message', contains('README.md')),
        ),
      );
      expect(bytes('README.md'), readme);
      expect(text('VERSION'), '0.4.2\n');
    });

    test('a failed write reports what was written and what is pending', () {
      write('a/VERSION', '0.4.2\n');
      final plan = {
        'a/VERSION': Uint8List.fromList(utf8.encode('0.4.3\n')),
        'gone/VERSION': Uint8List.fromList(utf8.encode('0.4.3\n')),
      };
      expect(
        () => writePlan(root.path, plan, '0.4.3'),
        throwsA(
          isA<ReleaseStop>()
              .having((e) => e.error, 'error', 'write_failed')
              .having(
                (e) => e.message,
                'message',
                allOf(
                  contains('gone/VERSION'),
                  contains('written: a/VERSION'),
                  contains('Rerun bump --to 0.4.3'),
                ),
              )
              .having((e) => e.extra['written'], 'written', ['a/VERSION'])
              .having((e) => e.extra['pending'], 'pending', ['gone/VERSION']),
        ),
      );
      expect(text('a/VERSION'), '0.4.3\n');
    });
  });
}
