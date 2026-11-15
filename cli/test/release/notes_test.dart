// Tests of the release notes (cli/lib/src/release/notes.dart): the
// `## Release Notes` section parser, the first Why sentence, the summary
// choice, the section reads at a commit and `buildNotes`. Expected texts come
// from the TestNotes, TestSectionedNotes and TestReleaseNotesParse evals.
import 'dart:convert';
import 'dart:io';

import 'package:path/path.dart' as p;
import 'package:specwright_cli/src/release/git.dart';
import 'package:specwright_cli/src/release/notes.dart';
import 'package:test/test.dart';

ParsedNotes? parse(String text) => parseReleaseNotes(text);

List<String> items(ParsedNotes notes, String heading) => [
  for (final i in notes.items[heading] ?? const <NoteItem>[]) i.text,
];

ParsedNotes valid(String text) {
  final notes = parse(text)!;
  expect(notes.errors, isEmpty);
  return notes;
}

List<NoteError> invalid(String text) {
  final errors = parse(text)!.errors;
  expect(errors, isNotEmpty);
  return errors;
}

String section(
  String summary, {
  List<String> added = const [],
  List<String> changed = const [],
  List<String> fixed = const [],
  List<String> removed = const [],
}) {
  final out = StringBuffer('## Release Notes\n\n$summary\n');
  for (final (heading, list) in [
    ('Added', added),
    ('Changed', changed),
    ('Fixed', fixed),
    ('Removed', removed),
  ]) {
    if (list.isEmpty) continue;
    out.write('\n### $heading\n\n');
    for (final item in list) {
      out.write('- $item\n');
    }
  }
  return out.toString();
}

ParsedNotes sectionOf(
  String summary, {
  List<String> added = const [],
  List<String> changed = const [],
  List<String> fixed = const [],
  List<String> removed = const [],
}) => valid(
  section(
    summary,
    added: added,
    changed: changed,
    fixed: fixed,
    removed: removed,
  ),
);

ReleaseChange change(String name, int? pr, [String? why]) =>
    ReleaseChange(name, why ?? 'Why of $name.', pr);

void main() {
  group('parseReleaseNotes', () {
    test('a section with groups out of order', () {
      final n = valid(
        '## Why\n\nx\n\n## Release Notes\n\nOne sentence.\n\n### Fixed\n\n- F1\n- F2\n\n### Added\n\n- A1\n',
      );
      expect(n.summary, 'One sentence.');
      expect(items(n, 'fixed'), ['F1', 'F2']);
      expect(items(n, 'added'), ['A1']);
      expect(n.items.containsKey('changed'), isFalse);
    });

    test('no section is null', () {
      expect(parse('## Why\n\nx\n'), isNull);
    });

    test('an unknown heading is one error on its line', () {
      final errors = invalid('## Release Notes\n\nS.\n\n### Security\n\n- x\n');
      expect(errors, hasLength(1));
      expect(errors.single.message, contains('Security'));
      expect(errors.single.line, 5);
    });

    test('a heading twice is an error', () {
      final errors = invalid(
        '## Release Notes\n\nS.\n\n### Added\n\n- a\n\n### added\n\n- b\n',
      );
      expect(errors.single.message, contains('appears twice'));
    });

    test('prose under a heading is an error on its line', () {
      final errors = invalid(
        '## Release Notes\n\nS.\n\n### Changed\n\nSome prose here.\n- ok\n',
      );
      expect([for (final e in errors) e.line], [7]);
    });

    test('a missing summary or no items is an error', () {
      expect(
        invalid('## Release Notes\n\n### Added\n\n- a\n').first.message,
        contains('summary'),
      );
      expect(
        invalid('## Release Notes\n\nA summary.\n').first.message,
        contains('item'),
      );
    });

    test('an item is at most 500 characters', () {
      valid('## Release Notes\n\nS.\n\n### Added\n\n- ${'x' * 500}\n');
      final errors = invalid(
        '## Release Notes\n\nS.\n\n### Added\n\n- ok\n- ${'x' * 501}\n',
      );
      expect([for (final e in errors) e.line], [8]);
    });

    test('a summary is at most 600 characters', () {
      final errors = invalid(
        '## Release Notes\n\n${'x' * 601}\n\n### Added\n\n- a\n',
      );
      expect(errors.single.message, contains('600'));
    });

    test('comments are ignored but keep their lines', () {
      final n = valid(
        '## Release Notes\n\n<!-- guidance\nover two lines -->\nS.\n\n### Added\n\n<!-- items go here -->\n- A\n',
      );
      expect(n.summary, 'S.');
      expect(n.items['added'], [(text: 'A', line: 10)]);
    });

    test('a comment-only section has no summary', () {
      final errors = invalid(
        '## Release Notes\n\n<!-- only the template comment -->\n',
      );
      expect(errors.first.message, contains('summary'));
    });

    test('indented continuation lines join, with any list marker', () {
      final n = valid(
        '## Release Notes\n\nS.\n\n### Added\n\n- first part\n  second part\n+ plus item\n* star item\n',
      );
      expect(items(n, 'added'), [
        'first part second part',
        'plus item',
        'star item',
      ]);
    });

    test('an unindented line after an item is an error', () {
      final errors = invalid(
        '## Release Notes\n\nS.\n\n### Fixed\n\n- item\nstray line\n',
      );
      expect([for (final e in errors) e.line], [8]);
    });

    test('a two-paragraph summary joins', () {
      final n = valid(
        '## Release Notes\n\nFirst sentence.\n\nSecond   sentence.\n\n### Added\n\n- A\n',
      );
      expect(n.summary, 'First sentence. Second sentence.');
    });

    test('every error is collected and sorted by line', () {
      final errors = invalid(
        '## Release Notes\n\nS.\n\n### Security\n\n- a\n\n### Added\n\n- ${'x' * 501}\n',
      );
      expect([for (final e in errors) e.line], [5, 11]);
    });

    test('CRLF text parses as LF', () {
      final n = valid(
        '## Release Notes\r\n\r\nS.\r\n\r\n### Added\r\n\r\n- A\r\n',
      );
      expect(n.summary, 'S.');
      expect(items(n, 'added'), ['A']);
    });

    test('the section ends at the next ## heading', () {
      final n = valid(
        '## Release Notes\n\nS.\n\n### Added\n\n- A\n\n## Appendix\n\nprose\n',
      );
      expect(items(n, 'added'), ['A']);
    });
  });

  group('itemLine', () {
    test('an unreferenced item gets the pr', () {
      expect(
        itemLine('New --dry-run flag', 140),
        '- New --dry-run flag (#140)',
      );
    });

    test('a referenced item stays', () {
      expect(
        itemLine('Bounded tag push (#111)', 140),
        '- Bounded tag push (#111)',
      );
      expect(
        itemLine('Thanks to acme/tool#12', 140),
        '- Thanks to acme/tool#12',
      );
    });

    test('a reference inside a code span does not count', () {
      expect(
        itemLine('Parse `#123` comments', 140),
        '- Parse `#123` comments (#140)',
      );
    });

    test('with no pr the item is as written', () {
      expect(itemLine('New --dry-run flag', null), '- New --dry-run flag');
    });

    test('the notes command passes the literal placeholder', () {
      expect(itemLine('New flag', '<pr>'), '- New flag (#<pr>)');
    });
  });

  group('firstSentence', () {
    final cases = {
      'code span': (
        '`release.sh` is missing. It matters.',
        '`release.sh` is missing.',
      ),
      'list marker': (
        '- First item. Second sentence.\n- other item',
        'First item.',
      ),
      'abbreviations': (
        'Cost is high (e.g. v1.2 vs. 1.3) today. Next.',
        'Cost is high (e.g. v1.2 vs. 1.3) today.',
      ),
      'wrapped': (
        'Operators cannot\ntell   which build\nthey run. Next one.',
        'Operators cannot tell which build they run.',
      ),
      'span with a dot': ('Run `a. b` now. Done.', 'Run `a. b` now.'),
      'bang': ('Stop it! Then go.', 'Stop it!'),
      'no end': ('no full stop here', 'no full stop here'),
    };
    cases.forEach((name, c) {
      test(name, () {
        expect(
          firstSentence('## Why\n\n${c.$1}\n\n## What Changes\n\n- x\n'),
          c.$2,
        );
      });
    });

    test('over 300 characters it is cut to 299 and an ellipsis', () {
      final s = firstSentence('## Why\n\n${'word ' * 80}\n')!;
      expect(s.runes.length, 300);
      expect(s.endsWith('…'), isTrue);
    });

    test('no Why heading or an empty one is null', () {
      expect(firstSentence('## What Changes\n\n- x\n'), isNull);
      expect(firstSentence('## Why\n\n## What Changes\n'), isNull);
    });
  });

  group('summaryChoice', () {
    ArchiveSection row(String dir, {bool section = true, bool bump = false}) =>
        ArchiveSection(
          dir,
          section ? sectionOf('Summary $dir.', added: ['A']) : null,
          null,
          bump,
        );

    test('the only change with a bump task and a valid section', () {
      final rows = [row('a'), row('b', bump: true), row('c')];
      expect(summaryChoice(rows)!.dir, 'b');
    });

    test('with none or several it is the last valid section', () {
      expect(summaryChoice([row('a'), row('b')])!.dir, 'b');
      expect(
        summaryChoice([row('a', bump: true), row('b', bump: true), row('c')])!
            .dir,
        'c',
      );
    });

    test('a bumper with no valid section does not count', () {
      expect(
        summaryChoice([row('a'), row('b', section: false, bump: true)])!.dir,
        'a',
      );
    });

    test('no valid section is null', () {
      expect(summaryChoice([row('a', section: false)]), isNull);
      expect(summaryChoice(const []), isNull);
    });
  });

  group('buildNotes', () {
    test('no change says so', () {
      expect(
        buildNotes('v0.4.2', const []),
        'No change was archived in this release (v0.4.2).',
      );
    });

    test('no section gives one line per change', () {
      expect(
        buildNotes('v0.4.2', [
          change('zeta', 1, 'Zeta first.'),
          change('alpha', 2, 'Alpha second.'),
        ]),
        'Changes in v0.4.2:\n\n- zeta (#1): Zeta first.\n- alpha (#2): Alpha second.',
      );
    });

    test('a change with no pr or no why drops that part', () {
      expect(
        buildNotes('v1', [
          ReleaseChange('a', 'W.', null),
          ReleaseChange('b', null, 3),
        ]),
        'Changes in v1:\n\n- a: W.\n- b (#3)',
      );
    });

    test('over 100 changes list names only, then the count', () {
      final changes = [
        for (var i = 0; i < 106; i++) change('c${'$i'.padLeft(3, '0')}', 9),
      ];
      final notes = buildNotes('v1', changes);
      expect(notes, contains('- c000\n'));
      expect(notes, isNot(contains('Why of')));
      expect(notes.endsWith('\n- c099\n…and 6 more'), isTrue);
    });

    test('one change with a section', () {
      final fixes = [for (var i = 1; i <= 8; i++) 'Fix $i'];
      expect(
        buildNotes(
          'v0.4.1',
          [change('fix-m4-gaps', 129)],
          sections: [sectionOf('Closes the M4 gaps.', fixed: fixes)],
          summary: 'Closes the M4 gaps.',
        ),
        'Closes the M4 gaps.\n\nFixed:\n${[for (final f in fixes) '- $f (#129)'].join('\n')}',
      );
    });

    test('the groups, then the changes without a section', () {
      expect(
        buildNotes(
          'v0.4.2',
          [change('old-x', 7), change('new-y', 8)],
          sections: [
            null,
            sectionOf('S.', fixed: ['F (#5)'], added: ['A']),
          ],
          summary: 'S.',
        ),
        'S.\n\nAdded:\n- A (#8)\n\nFixed:\n- F (#5)\n\nChanges:\n- old-x (#7): Why of old-x.',
      );
    });

    test('items follow the change order within a group', () {
      expect(
        buildNotes(
          'v0.4.2',
          [change('add-a', 1), change('add-b', 2)],
          sections: [
            sectionOf('Summary a.', added: ['A1', 'A2']),
            sectionOf('Summary b.', added: ['B1'], removed: ['R1']),
          ],
          summary: 'Summary b.',
        ),
        'Summary b.\n\nAdded:\n- A1 (#1)\n- A2 (#1)\n- B1 (#2)\n\nRemoved:\n- R1 (#2)',
      );
    });

    test('past 150 items a count line closes the last group', () {
      final big = sectionOf(
        'S.',
        added: [for (var i = 0; i < 100; i++) 'a$i (#1)'],
        fixed: [for (var i = 0; i < 50; i++) 'f$i (#1)'],
        removed: [for (var i = 0; i < 20; i++) 'r$i (#1)'],
      );
      final notes = buildNotes(
        'v0.4.2',
        [change('old-x', 7), change('big', 8)],
        sections: [null, big],
        summary: 'S.',
      );
      expect(
        notes,
        'S.\n\nAdded:\n${[for (var i = 0; i < 100; i++) '- a$i (#1)'].join('\n')}'
        '\n\nFixed:\n${[for (var i = 0; i < 50; i++) '- f$i (#1)'].join('\n')}'
        '\n…and 20 more items\n\nChanges:\n- old-x (#7): Why of old-x.',
      );
      expect(notes, isNot(contains('Removed:')));
    });
  });

  group('reading the archive at a commit', () {
    late Directory root;
    late ReleaseGit rg;
    String git(List<String> args) {
      final r = Process.runSync('git', [
        '-c',
        'user.name=t',
        '-c',
        'user.email=t@t.invalid',
        '-c',
        'commit.gpgsign=false',
        '-c',
        'core.autocrlf=false',
        ...args,
      ], workingDirectory: root.path);
      expect(r.exitCode, 0, reason: '${r.stderr}');
      return (r.stdout as String).trim();
    }

    void commit(Map<String, String> files) {
      files.forEach((rel, text) {
        final file = File(p.join(root.path, rel))
          ..parent.createSync(recursive: true);
        file.writeAsBytesSync(utf8.encode(text));
      });
      git(['add', '-A']);
      git(['commit', '-q', '-m', 'archive']);
    }

    const base = 'openspec/changes/archive/2026-10-10';
    String proposal(String why, [String extra = '']) =>
        '## Why\n\n$why\n\n## What Changes\n\n- x\n\n$extra';

    setUp(() {
      root = Directory.systemTemp.createTempSync('sw-notes-');
      git(['init', '-q', '-b', 'main']);
      rg = ReleaseGit(root.path);
    });
    tearDown(() => root.deleteSync(recursive: true));

    test('sections, warnings and bump tasks per directory', () async {
      commit({
        '$base-add-ok/proposal.md': proposal(
          'Ok.',
          section('Ok summary.', added: ['A']),
        ),
        '$base-add-ok/tasks.md': '## 3. Release\n\n- [x] 3.1 Run `release.sh bump --to 0.4.2` and commit\n',
        '$base-add-bad/proposal.md': proposal(
          'Bad.',
          '## Release Notes\n\nS.\n\n### Security\n\n- x\n',
        ),
        '$base-add-big/proposal.md': proposal('Big.', 'x' * (70 * 1024)),
        '$base-add-none/proposal.md': proposal('None.'),
        '$base-add-unticked/proposal.md': proposal(
          'U.',
          section('U.', added: ['A']),
        ),
        '$base-add-unticked/tasks.md':
            '- [ ] 3.1 `release.sh bump --to 0.4.2`\n',
      });
      final dirs = [
        '2026-10-10-add-ok',
        '2026-10-10-add-bad',
        '2026-10-10-add-big',
        '2026-10-10-add-none',
        '2026-10-10-add-unticked',
      ];
      final got = await readSections(rg, 'HEAD', 'openspec', [
        for (final d in dirs) (dir: d, pr: null),
      ], '0.4.2');
      final ok = got['2026-10-10-add-ok']!;
      expect(
        (ok.section!.summary, ok.warning, ok.bump),
        ('Ok summary.', null, true),
      );
      expect(
        got['2026-10-10-add-bad']!.warning,
        matches(RegExp(r"^line \d+: unknown heading 'Security'")),
      );
      expect(got['2026-10-10-add-bad']!.section, isNull);
      expect(got['2026-10-10-add-big']!.warning, contains('64 KB'));
      final none = got['2026-10-10-add-none']!;
      expect((none.section, none.warning, none.bump), (null, null, false));
      expect(got['2026-10-10-add-unticked']!.bump, isFalse);
    });

    test('a bump task for another version does not count', () async {
      commit({
        '$base-add-a/proposal.md': proposal('A.'),
        '$base-add-a/tasks.md': '- [x] 3.1 `release.sh bump --to 0.4.20`\n',
      });
      final got = await readSections(rg, 'HEAD', 'openspec', [
        (dir: '2026-10-10-add-a', pr: null),
      ], '0.4.2');
      expect(got['2026-10-10-add-a']!.bump, isFalse);
    });

    test('whyLines reads the first Why sentence of each proposal', () async {
      commit({
        '$base-add-a/proposal.md': proposal('Operators cannot tell. More.'),
        '$base-add-b/proposal.md': '## What Changes\n\n- x\n',
      });
      final why = await whyLines(rg, 'HEAD', 'openspec', [
        '2026-10-10-add-a',
        '2026-10-10-add-b',
        '2026-10-10-gone',
      ]);
      expect(why, {
        '2026-10-10-add-a': 'Operators cannot tell.',
        '2026-10-10-add-b': null,
        '2026-10-10-gone': null,
      });
    });

    test(
      'whyLines cuts the proposal to 64 KB after reading it whole',
      () async {
        commit({
          '$base-add-a/proposal.md':
              '${'x' * 70 * 1024}\n\n## Why\n\nToo late.\n',
          '$base-add-b/proposal.md': '## Why\n\nEarly.\n\n${'x' * 70 * 1024}\n',
        });
        final why = await whyLines(rg, 'HEAD', 'openspec', [
          '2026-10-10-add-a',
          '2026-10-10-add-b',
        ]);
        expect(why['2026-10-10-add-a'], isNull);
        expect(why['2026-10-10-add-b'], 'Early.');
      },
    );

    test('changeName drops the date prefix', () {
      expect(changeName('2026-10-10-add-x'), 'add-x');
      expect(changeName('add-x'), 'add-x');
    });
  });
}
