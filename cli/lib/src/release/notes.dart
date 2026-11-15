import 'dart:convert';
import 'dart:math';

import 'git.dart';
import 'stop.dart';
import 'versions.dart' show catBlobs;

/// A proposal is read for its section only up to this many bytes.
const int maxProposal = 64 * 1024;
const int _maxWhy = 300;
const int _maxListed = 100;
const int _maxSummary = 600;
const int _maxItem = 500;
const int _maxItems = 150;
const int _maxParsed = 1000;

/// The groups of a `## Release Notes` section, in the order the notes list
/// them.
const List<String> noteHeadings = ['added', 'changed', 'fixed', 'removed'];

/// One list item of a section and the line it starts on.
typedef NoteItem = ({String text, int line});

/// One problem in a section and the line it is on.
typedef NoteError = ({int line, String message});

/// The `## Release Notes` section of one proposal. It is valid when [errors]
/// is empty.
class ParsedNotes {
  ParsedNotes(this.summary, this.items, this.errors);

  final String summary;

  /// The non-empty groups by heading (lower case), items in order.
  final Map<String, List<NoteItem>> items;
  final List<NoteError> errors;
}

int _length(String text) => text.runes.length;

String _collapse(String text) => text.replaceAll(RegExp(r'\s+'), ' ').trim();

String _cut(String text, int max) => String.fromCharCodes(text.runes.take(max));

final RegExp _notesHead = RegExp(
  r'^##[ \t]+Release Notes[ \t]*$',
  caseSensitive: false,
);
final RegExp _subHead = RegExp(r'^###(?!#)[ \t]*(.*?)[ \t]*$', dotAll: true);
final RegExp _itemStart = RegExp(r'^[-*+][ \t]+(.*)$', dotAll: true);
final RegExp _codeSpan = RegExp(
  r'(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)',
  dotAll: true,
);
final RegExp _reference = RegExp(r'#\d+(?!\w)');

/// The `## Release Notes` section of a proposal: null when there is no such
/// heading, else its summary, items and every error with its line. HTML
/// comments go first (their newlines stay, so lines still count the file's).
/// The section runs to the next `##` heading or the end. The summary is the
/// text before the first `###`, whitespace collapsed, at most 600 characters.
/// The headings are Added, Changed, Fixed and Removed (any case), each at most
/// once, followed only by items: a line starting `-`, `*` or `+` and a space,
/// joined with the indented lines after it, at most 500 characters collapsed.
ParsedNotes? parseReleaseNotes(String source) {
  final text = source.replaceAllMapped(
    RegExp(r'<!--.*?-->', dotAll: true),
    (m) => '\n' * '\n'.allMatches(m[0]!).length,
  );
  final lines = [
    for (final l in text.split('\n')) l.replaceFirst(RegExp(r'\r+$'), ''),
  ];
  final start = lines.indexWhere(_notesHead.hasMatch);
  if (start < 0) return null;
  var end = lines.length;
  for (var i = start + 1; i < lines.length; i++) {
    if (RegExp(r'^##(?!#)').hasMatch(lines[i])) {
      end = i;
      break;
    }
  }
  final errors = <NoteError>[];
  final items = <String, List<NoteItem>>{};
  final summary = <String>[];
  final seen = <String>{};
  String? cur; // the heading being read, null under an invalid one
  List<String>? parts; // the open item's text and its line
  var itemLine = 0;

  void close() {
    final open = parts;
    if (open != null && cur != null) {
      final t = _collapse(open.join(' '));
      if (t.isEmpty) {
        errors.add((line: itemLine, message: 'empty list item'));
      } else if (_length(t) > _maxItem) {
        errors.add((
          line: itemLine,
          message: 'item is ${_length(t)} characters, over the $_maxItem limit',
        ));
      } else {
        items[cur]!.add((text: t, line: itemLine));
      }
    }
    parts = null;
  }

  for (var i = start + 1; i < end; i++) {
    final line = lines[i];
    final n = i + 1;
    final head = _subHead.firstMatch(line);
    if (head != null) {
      close();
      final name = head[1]!;
      final key = name.toLowerCase();
      if (!noteHeadings.contains(key)) {
        errors.add((
          line: n,
          message:
              "unknown heading '$name' (use Added, Changed, Fixed or Removed)",
        ));
        cur = null;
      } else if (seen.contains(key)) {
        errors.add((line: n, message: "heading '$name' appears twice"));
        cur = null;
      } else {
        cur = key;
        items[key] = [];
      }
      seen.add(key);
      continue;
    }
    if (line.trim().isEmpty) continue;
    if (seen.isEmpty) {
      summary.add(line.trim());
      continue;
    }
    // under an invalid heading: that heading's error covers the line
    if (cur == null) continue;
    final m = _itemStart.firstMatch(line);
    if (m != null) {
      close();
      parts = [m[1]!];
      itemLine = n;
    } else if ((line.startsWith(' ') || line.startsWith('\t')) &&
        parts != null) {
      parts!.add(line.trim());
    } else {
      close();
      errors.add((
        line: n,
        message:
            'line is neither a list item nor an indented continuation: ${_cut(line.trim(), 60)}',
      ));
    }
  }
  close();
  final bodyErrors = errors.length;
  final joined = _collapse(summary.join(' '));
  if (joined.isEmpty) {
    errors.add((
      line: start + 1,
      message: 'the summary is missing (text before the first ### heading)',
    ));
  } else if (_length(joined) > _maxSummary) {
    errors.add((
      line: start + 1,
      message:
          'summary is ${_length(joined)} characters, over the $_maxSummary limit',
    ));
  }
  if (items.values.every((l) => l.isEmpty) && bodyErrors == 0) {
    errors.add((
      line: start + 1,
      message: 'no list item under Added, Changed, Fixed or Removed',
    ));
  }
  // by line, in the order found within one line
  final ordered = [for (var i = 0; i < errors.length; i++) (i, errors[i])]
    ..sort((a, b) {
      final c = a.$2.line.compareTo(b.$2.line);
      return c != 0 ? c : a.$1.compareTo(b.$1);
    });
  return ParsedNotes(
    joined,
    {
      for (final e in items.entries)
        if (e.value.isNotEmpty) e.key: e.value,
    },
    [for (final (_, e) in ordered) e],
  );
}

/// The notes line of one item: ` (#<pr>)` appended when the item names no
/// issue or pull request outside a code span and [pr] is known.
String itemLine(String text, Object? pr) {
  if (pr != null && !_reference.hasMatch(text.replaceAll(_codeSpan, ' '))) {
    return '- $text (#$pr)';
  }
  return '- $text';
}

final RegExp _whyHead = RegExp(
  r'^#{2}[ \t]+Why[ \t]*$',
  caseSensitive: false,
  multiLine: true,
);
final RegExp _abbrev = RegExp(
  r'(?:^|[\s(])(?:e\.g|i\.e|vs|cf)$',
  caseSensitive: false,
);
final RegExp _marker = RegExp(r'^\s*(?:[-*+]|\d+[.)])\s+');

/// The first sentence of the first paragraph under `## Why`, or null. The
/// paragraph runs from the first non-blank line after the heading to a blank
/// line, a heading, or (after a list item's first line) the next list marker;
/// a leading list marker (`-`, `*`, `+`, `1.`) is dropped; whitespace collapses
/// to single spaces; the sentence ends at the first `.`, `!` or `?` that is
/// followed by whitespace or the end, is outside a backtick code span, and does
/// not close `e.g`, `i.e`, `vs` or `cf`; with no end the whole paragraph is the
/// sentence. Over 300 characters it is cut to 299 plus an ellipsis.
String? firstSentence(String proposal) {
  final head = _whyHead.firstMatch(proposal);
  if (head == null) return null;
  final para = <String>[];
  for (var line in proposal.substring(head.end).split(RegExp(r'\r\n|\r|\n'))) {
    if (line.trim().isEmpty) {
      if (para.isNotEmpty) break;
      continue;
    }
    if (line.trimLeft().startsWith('#')) break;
    if (para.isEmpty) {
      line = line.replaceFirst(_marker, '');
    } else if (_marker.hasMatch(line)) {
      break;
    }
    para.add(line.trim());
  }
  final text = _collapse(para.join(' '));
  if (text.isEmpty) return null;
  final n = text.length;
  var end = n, i = 0;
  while (i < n) {
    final ch = text[i];
    if (ch == '`') {
      var j = i;
      while (j < n && text[j] == '`') {
        j++;
      }
      final close = text.indexOf(text.substring(i, j), j);
      i = close >= 0 ? close + (j - i) : j;
      continue;
    }
    if ('.!?'.contains(ch) &&
        (i + 1 == n || RegExp(r'\s').hasMatch(text[i + 1])) &&
        !(ch == '.' && _abbrev.hasMatch(text.substring(0, i)))) {
      end = i + 1;
      break;
    }
    i++;
  }
  final s = text.substring(0, end);
  return _length(s) <= _maxWhy ? s : '${_cut(s, _maxWhy - 1)}…';
}

final RegExp _datePrefix = RegExp(r'^\d{4}-\d{2}-\d{2}-');

/// The change's name: an archive directory without its date prefix.
String changeName(String dirname) => dirname.replaceFirst(_datePrefix, '');

/// One archived change of a release: its [name], the first sentence of its
/// Why (null when it has none or its section is used), and the pull request
/// that carried it, when known.
class ReleaseChange {
  ReleaseChange(this.name, this.why, this.pr);

  final String name;
  final String? why;
  final int? pr;

  Map<String, Object?> toJson() => {'name': name, 'why': why, 'pr': pr};
}

/// One archive directory as read at a commit: its valid [section] (null when
/// it has none or an invalid one), the [warning] for an invalid or oversize
/// proposal, and whether its `tasks.md` has a ticked bump task for the
/// version.
class ArchiveSection {
  ArchiveSection(this.dir, this.section, this.warning, this.bump);

  final String dir;
  final ParsedNotes? section;
  final String? warning;
  final bool bump;
}

/// The change that supplies the summary: the only one with a bump task and a
/// valid section, else the last one with a valid section; null when no section
/// is valid.
ArchiveSection? summaryChoice(List<ArchiveSection> rows) {
  final valid = [
    for (final r in rows)
      if (r.section != null) r,
  ];
  final bumpers = [
    for (final r in valid)
      if (r.bump) r,
  ];
  if (bumpers.length == 1) return bumpers.first;
  return valid.isEmpty ? null : valid.last;
}

/// The byte size of each `<commit>:<path>` spec through one `git cat-file
/// --batch-check`, null for a missing object.
Future<List<int?>> _blobSizes(ReleaseGit git, List<String> specs) async {
  if (specs.isEmpty) return [];
  final r = await git.run([
    'cat-file',
    '--batch-check',
  ], input: utf8.encode('${specs.join('\n')}\n'));
  if (r.exitCode != 0) {
    throw ReleaseStop(
      'git_failed',
      'git cat-file failed: ${trimmed(r.stderr)}',
      code: 3,
    );
  }
  final out = <int?>[];
  for (final line in lossy(r.stdout).split('\n').take(specs.length)) {
    final head = line.split(' ');
    out.add(
      head.last == 'missing' || head.length < 3 ? null : int.parse(head[2]),
    );
  }
  return out;
}

/// The sections of the last 1000 archive directories of [rows] at [commit].
/// One size pass over every `proposal.md` and `tasks.md`, then one read of the
/// blobs within 64 KB. A proposal over the bound is never read for its section
/// (a warning); a `tasks.md` over it counts as having no bump task. The bump
/// task is a ticked `release.sh bump --to <version>` item.
Future<Map<String, ArchiveSection>> readSections(
  ReleaseGit git,
  String commit,
  String prefix,
  List<({String dir, int? pr})> rows,
  String version,
) async {
  final dirs = [
    for (final r in rows.skip(max(0, rows.length - _maxParsed))) r.dir,
  ];
  final base = '$commit:$prefix/changes/archive/';
  final specs = [
    for (final d in dirs)
      for (final f in ['proposal.md', 'tasks.md']) '$base$d/$f',
  ];
  final sizes = await _blobSizes(git, specs);
  final want = [
    for (var i = 0; i < specs.length; i++)
      if (sizes[i] != null && sizes[i]! <= maxProposal) specs[i],
  ];
  final got = await catBlobs(git.root, want);
  final blobs = {for (var i = 0; i < want.length; i++) want[i]: got[i]};
  final bump = RegExp(
    r'^[ \t]*[-*+][ \t]+\[[ \t]*x[ \t]*\][ \t]+.*release\.sh[ \t]+bump[ \t]+--to[ \t]+'
    '${RegExp.escape(version)}(?!\\.?\\d)',
    caseSensitive: false,
    multiLine: true,
  );
  final out = <String, ArchiveSection>{};
  for (var i = 0; i < dirs.length; i++) {
    final proposal = specs[2 * i], tasks = specs[2 * i + 1];
    final psz = sizes[2 * i], tsz = sizes[2 * i + 1];
    ParsedNotes? section;
    String? warning;
    if (psz != null && psz > maxProposal) {
      warning =
          'the proposal is $psz bytes, over the ${maxProposal ~/ 1024} KB limit';
    } else if (psz != null && blobs[proposal] != null) {
      final parsed = parseReleaseNotes(lossy(blobs[proposal]!));
      if (parsed != null && parsed.errors.isNotEmpty) {
        final first = parsed.errors.first;
        warning = 'line ${first.line}: ${first.message}';
      } else {
        section = parsed;
      }
    }
    final tasksBlob = blobs[tasks];
    final ticked =
        tsz != null &&
        tsz <= maxProposal &&
        tasksBlob != null &&
        bump.hasMatch(lossy(tasksBlob));
    out[dirs[i]] = ArchiveSection(dirs[i], section, warning, ticked);
  }
  return out;
}

/// The first Why sentence of each archive directory in [dirs], read at
/// [commit]; null for a proposal with none or a missing one.
///
/// The fallback Why read takes each listed proposal's whole blob and cuts it to
/// 64 KB afterwards; only the section read is size-checked first.
Future<Map<String, String?>> whyLines(
  ReleaseGit git,
  String commit,
  String prefix,
  List<String> dirs,
) async {
  final got = await catBlobs(git.root, [
    for (final d in dirs) '$commit:$prefix/changes/archive/$d/proposal.md',
  ]);
  return {
    for (var i = 0; i < dirs.length; i++)
      dirs[i]: got[i] == null
          ? null
          : firstSentence(lossy(got[i]!.take(maxProposal).toList())),
  };
}

/// `- <name> (#<pr>): <why>` per change; names only, then `…and <n> more`,
/// past 100 changes.
List<String> changeLines(List<ReleaseChange> changes) {
  final lines = <String>[];
  for (final c in changes.take(_maxListed)) {
    if (changes.length > _maxListed) {
      lines.add('- ${c.name}');
    } else {
      final why = c.why;
      lines.add(
        '- ${c.name}${c.pr != null ? ' (#${c.pr})' : ''}${why != null && why.isNotEmpty ? ': $why' : ''}',
      );
    }
  }
  if (changes.length > _maxListed) {
    lines.add('…and ${changes.length - _maxListed} more');
  }
  return lines;
}

/// The text for the tag annotation and the release body. [sections] is
/// parallel to [changes]: a change's valid section or null. With no valid
/// section the text is `Changes in <tag>:` and one line per change; else the
/// [summary], the Added/Changed/Fixed/Removed groups (at most 150 items, then
/// `…and <n> more items`) and `Changes:` for the changes without a section,
/// one blank line between blocks.
String buildNotes(
  String tag,
  List<ReleaseChange> changes, {
  List<ParsedNotes?>? sections,
  String? summary,
}) {
  if (changes.isEmpty) return 'No change was archived in this release ($tag).';
  final secs = sections ?? List<ParsedNotes?>.filled(changes.length, null);
  if (secs.every((s) => s == null)) {
    return ['Changes in $tag:', '', ...changeLines(changes)].join('\n');
  }
  final flat = [
    for (final h in noteHeadings)
      for (var i = 0; i < changes.length; i++)
        for (final item in secs[i]?.items[h] ?? const <NoteItem>[])
          (h, itemLine(item.text, changes[i].pr)),
  ];
  final listed = flat.take(_maxItems).toList();
  final blocks = <String>[?summary];
  for (final h in noteHeadings) {
    final group = [
      for (final (g, line) in listed)
        if (g == h) line,
    ];
    if (group.isNotEmpty) {
      blocks.add(
        ['${h[0].toUpperCase()}${h.substring(1)}:', ...group].join('\n'),
      );
    }
  }
  if (flat.length > _maxItems) {
    blocks[blocks.length - 1] += '\n…and ${flat.length - _maxItems} more items';
  }
  final plain = [
    for (var i = 0; i < changes.length; i++)
      if (secs[i] == null) changes[i],
  ];
  if (plain.isNotEmpty) {
    blocks.add(['Changes:', ...changeLines(plain)].join('\n'));
  }
  return blocks.join('\n\n');
}
