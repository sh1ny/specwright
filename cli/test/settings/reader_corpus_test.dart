import 'dart:convert';
import 'dart:io';

import 'package:specwright_cli/src/settings/reader.dart';
import 'package:specwright_cli/src/settings/rules.dart' show readSettingsText;
import 'package:specwright_cli/src/settings/yaml.dart';
import 'package:test/test.dart';

// Evidence for task 2.6 of `native-cli-yaml-settings` (design D6): runs the old reader (`parseYaml` for the lenient
// read, `yamlProblem` for the strict check) and the new `readSettingsYaml` over a corpus and prints each difference.
// It reports; it gates only on the new reader throwing something other than `SettingsRefused` and on each failure
// case's new outcome. Deleted with the old reader once the experiment is accepted.
//
// The corpus: this repository's two settings files, the two dogfood projects' files (read in place, skipped when
// absent, only their outcome and differing key paths are printed), the settings texts the Dart tests feed to a reader
// (found by lexing the test sources for adjacent string literals that look like YAML), and the failure cases.

const _dogfood = {
  'mythspine': 'F:/Dev/Dart/mythspine',
  'blackgrid': 'F:/Dev/Dart/blackgrid',
};

class _Case {
  _Case(this.group, this.name, this.text, {this.want});
  final String group; // repo, dogfood, inline, failure
  final String name;
  final String text;

  /// For a failure case: `read` or `refused`.
  final String? want;
}

// ---- lexing Dart string literals -------------------------------------------------------------------------------------

/// The decoded value of every run of adjacent string literals in [src], with `true` when it interpolates: each
/// interpolation is then written as `X`.
List<(String, bool)> _literals(String src) {
  final out = <(String, bool)>[];
  var i = 0;
  bool startsString(int at) {
    if (at >= src.length) return false;
    final c = src[at];
    if (c == "'" || c == '"') return true;
    return c == 'r' &&
        at + 1 < src.length &&
        (src[at + 1] == "'" || src[at + 1] == '"');
  }

  int skipBlank(int at) {
    while (at < src.length) {
      if (src[at] == ' ' ||
          src[at] == '\n' ||
          src[at] == '\r' ||
          src[at] == '\t') {
        at++;
      } else if (src.startsWith('//', at)) {
        while (at < src.length && src[at] != '\n') {
          at++;
        }
      } else {
        break;
      }
    }
    return at;
  }

  while (i < src.length) {
    if (src.startsWith('//', i)) {
      while (i < src.length && src[i] != '\n') {
        i++;
      }
      continue;
    }
    if (src.startsWith('/*', i)) {
      final e = src.indexOf('*/', i + 2);
      i = e < 0 ? src.length : e + 2;
      continue;
    }
    if (!startsString(i)) {
      i++;
      continue;
    }
    // One literal, then any adjacent ones.
    final cur = StringBuffer();
    var dynamicRun = false;
    while (true) {
      final raw = src[i] == 'r';
      if (raw) i++;
      final q = src[i];
      final triple = src.startsWith('$q$q$q', i);
      i += triple ? 3 : 1;
      while (i < src.length) {
        final c = src[i];
        if (triple ? src.startsWith('$q$q$q', i) : c == q) {
          i += triple ? 3 : 1;
          break;
        }
        if (!raw && c == r'\') {
          final n = src[i + 1];
          i += 2;
          switch (n) {
            case 'n':
              cur.write('\n');
            case 'r':
              cur.write('\r');
            case 't':
              cur.write('\t');
            case '0':
              cur.write('\x00');
            case 'b':
              cur.write('\b');
            case 'f':
              cur.write('\f');
            case 'v':
              cur.write('\v');
            case 'x':
              cur.writeCharCode(int.parse(src.substring(i, i + 2), radix: 16));
              i += 2;
            case 'u':
              if (src[i] == '{') {
                final e = src.indexOf('}', i);
                cur.writeCharCode(
                  int.parse(src.substring(i + 1, e), radix: 16),
                );
                i = e + 1;
              } else {
                cur.writeCharCode(
                  int.parse(src.substring(i, i + 4), radix: 16),
                );
                i += 4;
              }
            default:
              cur.write(n);
          }
          continue;
        }
        if (!raw && c == r'$') {
          dynamicRun = true;
          cur.write('X');
          if (src[i + 1] == '{') {
            var depth = 0;
            while (i < src.length) {
              if (src[i] == '{') depth++;
              if (src[i] == '}') {
                depth--;
                if (depth == 0) break;
              }
              if (src[i] == "'" || src[i] == '"') {
                final qq = src[i];
                i++;
                while (i < src.length && src[i] != qq) {
                  i++;
                }
              }
              i++;
            }
            i++;
          } else {
            i++;
            while (i < src.length && RegExp(r'\w').hasMatch(src[i])) {
              i++;
            }
          }
          continue;
        }
        cur.write(c);
        i++;
      }
      final next = skipBlank(i);
      if (startsString(next)) {
        i = next;
        continue;
      }
      break;
    }
    out.add((cur.toString(), dynamicRun));
  }
  return out;
}

final RegExp _yamlish = RegExp(
  r'''^(?:[ \t]*(?:#[^\n]*)?\n)*[ \t]*(?:[A-Za-z_][\w. \-]*|"[^"\n]*"|'[^'\n]*'):(?:[ \t]|\n|$)''',
);

bool _looksLikeSettings(String s) =>
    s.trim().isNotEmpty && s.length > 3 && _yamlish.hasMatch(s);

// ---- comparing two readings ------------------------------------------------------------------------------------------

String _typed(Object? v) => switch (v) {
  null => 'null',
  bool() => 'bool:$v',
  int() => 'int:$v',
  BigInt() => 'bigint:$v',
  double() => 'double:$v',
  String() => 'str:${jsonEncode(v)}',
  _ => 'other:${v.runtimeType}',
};

void _flat(Object? v, String path, Map<String, String> out) {
  if (v is Map) {
    if (v.isEmpty) out[path.isEmpty ? '(root)' : path] = '{}';
    for (final k in v.keys) {
      final p = path.isEmpty ? '$k' : '$path.$k';
      _flat(v[k], p, out);
      if (v is YamlMap && v.text.containsKey(k)) {
        out['$p#text'] = jsonEncode(v.text[k]);
      }
    }
  } else if (v is List) {
    out['$path[]'] = 'list(${v.length})';
    for (var i = 0; i < v.length; i++) {
      _flat(v[i], '$path[$i]', out);
    }
  } else {
    out[path] = _typed(v);
  }
}

class _Old {
  _Old(this.value, this.strict, this.crash);
  final Map<String, Object?>? value;
  final String? strict;
  final String? crash;
}

_Old _runOld(String text) {
  String? strict;
  // The old reader is measured, not trusted: any exception it throws is recorded as its outcome.
  try {
    strict = yamlProblem(text);
  } catch (e) {
    strict = 'crash: ${e.runtimeType}';
  }
  try {
    return _Old(parseYaml(text), strict, null);
  } catch (e) {
    return _Old(null, strict, '${e.runtimeType}');
  }
}

/// The approved difference a changed [path] falls under, from the old and new typed values.
String _tagValue(String? old, String? neu) {
  if (old == null || neu == null) return 'UNTAGGED';
  bool is_(String v, String t) => v.startsWith('$t:');
  if (is_(old, 'str') && (is_(neu, 'int') || is_(neu, 'double'))) return 'D3';
  if (is_(old, 'int') && is_(neu, 'str')) return 'D3';
  if (is_(old, 'bigint') && is_(neu, 'str')) return 'D3';
  return 'UNTAGGED';
}

String _tagRefusal(SettingsRefused r) {
  if (r.why.contains('write true or false')) return 'S6';
  if (r.why.contains('anchors') || r.why.contains('aliases')) return 'S7';
  return 'S5';
}

bool _blankDoc(String t) => t.replaceAll(RegExp(r'#[^\n]*'), '').trim().isEmpty;

String _short(String s) => s.length <= 90 ? s : '${s.substring(0, 87)}...';

void main() {
  final cases = <_Case>[];

  group('corpus', () {
    // Gather.
    for (final (name, base) in [
      ('openspec/specwright.yaml', '..'),
      ('templates/openspec/specwright.yaml', '../templates'),
    ]) {
      final text = readSettingsText([base]);
      if (text != null) cases.add(_Case('repo', name, text));
    }
    for (final e in _dogfood.entries) {
      final text = readSettingsText([e.value]);
      if (text != null) cases.add(_Case('dogfood', e.key, text));
    }
    final seen = <String>{};
    // Every Dart test that mentions a settings file or a settings reader, but not this experiment's own tests.
    final sources = <String>[
      for (final e in Directory('test').listSync(recursive: true))
        if (e is File &&
            e.path.endsWith('.dart') &&
            !e.path.replaceAll(r'\', '/').contains('test/settings/reader_') &&
            RegExp(r'specwright\.yaml|parseYaml|yamlProblem|readSettings')
                .hasMatch(e.readAsStringSync()))
          e.path.replaceAll(r'\', '/'),
    ]..sort();
    for (final path in sources) {
      var n = 0;
      for (final (lit, interp) in _literals(File(path).readAsStringSync())) {
        if (!_looksLikeSettings(lit) || !seen.add(lit)) continue;
        cases.add(
          _Case(
            interp ? 'inline-interp' : 'inline',
            '${path.replaceFirst('test/', '')}#${++n}',
            lit,
          ),
        );
      }
    }
    // The release tests build version_files YAML with a helper (`entries(files, extra:)` / `entriesFor(files)`); the
    // same text is generated here for each file name and pattern literal the two tests use.
    for (final path in [
      'test/release/versions_test.dart',
      'test/release/history_test.dart',
    ]) {
      final src = File(path).readAsStringSync();
      final keys = {
        for (final m in RegExp(r'''(['"])([^'"\n]+)\1\s*:\s''').allMatches(src))
          if (RegExp(r'^[\w./*\-]+$').hasMatch(m.group(2)!)) m.group(2)!,
      };
      final values = {
        for (final (lit, interp) in _literals(src))
          if (!interp &&
              lit.length < 200 &&
              !lit.contains('\n') &&
              RegExp(r'[\\()^]').hasMatch(lit))
            lit,
      };
      final extras = {
        '',
        for (final m in RegExp(r'''extra:\s*(['"])(.*?)\1''').allMatches(src))
          m.group(2)!.replaceAll(r'\n', '\n'),
      };
      final base = path.split('/').last;
      for (final x in extras) {
        for (final k in keys) {
          for (final v in values) {
            final text =
                'release:\n  enabled: true\n$x  version_files:\n    "$k": \'$v\'\n';
            if (seen.add(text)) cases.add(_Case('dart-helper', base, text));
          }
        }
      }
    }
    // The Python evals' settings texts, dumped by an evals-side script into a JSON file named by SW_CORPUS_PY (the
    // command is in evidence/experiment.md). Skipped, and said so, when it is not set.
    final pyPath = Platform.environment['SW_CORPUS_PY'];
    if (pyPath == null || !File(pyPath).existsSync()) {
      // ignore: avoid_print
      print(
        'PYTHON CORPUS: skipped (SW_CORPUS_PY is not set to an existing file)',
      );
    } else {
      final doc =
          jsonDecode(File(pyPath).readAsStringSync()) as Map<String, Object?>;
      for (final e in (doc['entries']! as List).cast<Map<String, Object?>>()) {
        final text = e['text']! as String;
        if (!seen.add(text)) continue;
        cases.add(
          _Case(
            'py-${e['kind']}',
            (e['source']! as String).replaceFirst('evals/', ''),
            text,
          ),
        );
      }
      // ignore: avoid_print
      print(
        'PYTHON CORPUS: ${(doc['entries']! as List).length} entries from $pyPath',
      );
    }
    for (final (name, text, want) in <(String, String, String)>[
      (
        'tab in indentation (line 7)',
        'a: 1\nb:\n  c: 1\n  d:\n    e: 1\n    f: 1\n\tg: 1\n',
        'refused',
      ),
      (
        'duplicate key in a reviewer',
        'pr:\n  reviewers:\n    codex:\n      role: a\n      role: b\n',
        'refused',
      ),
      ('duplicate top-level key', 'a: 1\nb: 2\na: 3\n', 'refused'),
      ('plain yes', 'pr:\n  react: yes\n', 'refused'),
      ('plain No', 'pr:\n  react: No\n', 'refused'),
      ('quoted yes and no', "pr:\n  a: 'yes'\n  b: \"no\"\n", 'read'),
      ('on, off, y, n', 'a: on\nb: off\nc: y\nd: n\n', 'read'),
      ('anchor and alias', 'a: &r {x: 1}\nb: *r\n', 'refused'),
      ('tag', 'a: !!str x\n', 'refused'),
      ('two documents', 'a: 1\n---\nb: 2\n', 'refused'),
      ('list root', '- pr\n', 'refused'),
      ('65 [ in a block scalar', 'k: |\n  ${'[' * 65}\n', 'read'),
      ('65 [ in a plain scalar', 'k: a${'[' * 65}\n', 'read'),
      ('65 nested flow collections', 'k: ${'[' * 65}${']' * 65}\n', 'refused'),
      ('64 nested flow collections', 'k: ${'[' * 64}${']' * 64}\n', 'read'),
      (
        '100,000 nested flow collections',
        'k: ${'[' * 100000}${']' * 100000}\n',
        'refused',
      ),
      ('21-digit integer', 'n: 123456789012345678901\n', 'read'),
      ('hex', 'n: 0x10\n', 'read'),
      ('octal', 'n: 0o17\n', 'read'),
      ('float', 'n: 1.5\n', 'read'),
      ('Arabic-Indic digits', 'n: \u0661\u0662\n', 'read'),
      ('empty value', 'key:\nother: 1\n', 'read'),
      ('empty file', '', 'read'),
      ('blank file', '\n\n  \n', 'read'),
      ('comment-only file', '# c\n\n# d\n', 'read'),
      (
        'block sequence',
        'review:\n  order:\n    - codex\n    - claude\n',
        'read',
      ),
      ('non-string key', '1: a\n', 'refused'),
    ]) {
      cases.add(_Case('failure', name, text, want: want));
    }

    test('old and new readers over the corpus', () {
      var identical = 0;
      final tags = <String, int>{};
      final byGroup = <String, Map<String, int>>{};
      final groupSize = <String, int>{};
      // Generated groups hold hundreds of near-identical texts: print one example per distinct outcome, with a count.
      const condensed = {'dart-helper', 'py-helper'};
      final examples = <String, (int, String)>{};
      final report = StringBuffer();
      for (final c in cases) {
        groupSize[c.group] = (groupSize[c.group] ?? 0) + 1;
        final out = StringBuffer();
        void tag_(String t) {
          tags[t] = (tags[t] ?? 0) + 1;
          final g = byGroup.putIfAbsent(c.group, () => {});
          g[t] = (g[t] ?? 0) + 1;
        }

        void flush({bool same = false}) {
          if (condensed.contains(c.group)) {
            if (same) return;
            final sig = out
                .toString()
                .split('\n')
                .where((l) => !l.startsWith('  text:'))
                .join('\n')
                .replaceFirst(c.name, '');
            final prev = examples[c.group + sig];
            examples[c.group + sig] = (
              (prev?.$1 ?? 0) + 1,
              prev?.$2 ?? out.toString(),
            );
          } else {
            report.write(out);
          }
        }

        final old = _runOld(c.text);
        // The new reader may throw SettingsRefused only; anything else fails the test.
        Map<String, Object?>? neu;
        SettingsRefused? refused;
        try {
          neu = readSettingsYaml(c.text);
        } on SettingsRefused catch (e) {
          refused = e;
        }
        if (c.want != null) {
          expect(refused == null ? 'read' : 'refused', c.want, reason: c.name);
        }
        final oldOutcome = old.crash != null
            ? 'CRASH ${old.crash}'
            : 'read${old.strict == null ? '' : ' (strict: ${old.strict})'}';
        final newOutcome = refused == null
            ? 'read'
            : 'refused at line ${refused.line}: ${refused.why}';
        final dog = c.group == 'dogfood';
        final head =
            '${c.group} | ${c.name} | old: ${_short(oldOutcome)} | new: ${_short(newOutcome)}';
        final shown = dog ? '' : '\n  text: ${_short(jsonEncode(c.text))}';
        if (refused != null) {
          final tag = _blankDoc(c.text) ? 'empty-file' : _tagRefusal(refused);
          tag_(tag);
          out.writeln('REFUSED  $head | tag $tag$shown');
          flush();
          continue;
        }
        if (old.value == null) {
          tag_('UNTAGGED:old-crash');
          out.writeln('NEWONLY  $head | tag UNTAGGED:old-crash$shown');
          flush();
          continue;
        }
        final a = <String, String>{};
        final b = <String, String>{};
        _flat(old.value, '', a);
        _flat(neu, '', b);
        // A block sequence the old reader read as an empty mapping and the new one reads as a list.
        final seqRoots = {
          for (final p in a.keys)
            if (a[p] == '{}' && b.containsKey('$p[]')) p,
        };
        final diffs = <String>[];
        var valueDiffs = 0;
        final paths = {...a.keys, ...b.keys}.toList()..sort();
        final hasValueDiff = paths.any(
          (p) => !p.endsWith('#text') && a[p] != b[p],
        );
        for (final p in paths) {
          if (a[p] == b[p]) continue;
          String tag;
          if (p.endsWith('#text')) {
            final base = p.substring(0, p.length - 5);
            tag = a[p] == null
                ? 'text-added'
                : a[base] != b[base] || (b[p] == null && hasValueDiff)
                ? 'YAML' // the text follows a key or value the old reader misread
                : 'UNTAGGED:text';
          } else {
            valueDiffs++;
            if (seqRoots.any((r) => p == r || p.startsWith('$r['))) {
              tag = 'YAML';
            } else if (a[p] == null || b[p] == null) {
              tag = 'YAML';
            } else {
              tag = _tagValue(a[p], b[p]).replaceFirst('UNTAGGED', 'YAML');
            }
          }
          tag_(tag);
          diffs.add(
            dog
                ? '  path $p | tag $tag'
                : '  path $p | old ${a[p] ?? '(absent)'} | new ${b[p] ?? '(absent)'} | tag $tag',
          );
        }
        final strictLooser = old.strict != null;
        if (strictLooser) {
          tag_('YAML:strict-case');
        }
        if (diffs.isEmpty && !strictLooser) {
          identical++;
          out.writeln('SAME     $head | ${a.length} values');
          flush(same: true);
          continue;
        } else {
          final kind = valueDiffs == 0 && !strictLooser
              ? 'TEXTONLY'
              : valueDiffs == 0
              ? 'STRICT  '
              : 'DIFF    ';
          out.writeln(
            '$kind $head | $valueDiffs value differences, ${diffs.length - valueDiffs} text differences'
            '${strictLooser ? ' | old strict refused, new reads (tag YAML:strict-case)' : ''}$shown',
          );
          for (final d in diffs) {
            out.writeln(d);
          }
        }
        flush();
      }
      for (final e in examples.entries) {
        report.writeln('x${e.value.$1}  ${e.value.$2.trimRight()}');
      }
      report.writeln('IDENTICAL cases: $identical of ${cases.length}');
      for (final g in groupSize.keys.toList()..sort()) {
        report.writeln(
          'GROUP $g: ${groupSize[g]} cases; tags ${((byGroup[g] ?? {}).entries.toList()..sort((x, y) => x.key.compareTo(y.key))).map((e) => '${e.key}=${e.value}').join(', ')}',
        );
      }
      report.writeln(
        'TAG COUNTS: ${(tags.entries.toList()..sort((x, y) => x.key.compareTo(y.key))).map((e) => '${e.key}=${e.value}').join(', ')}',
      );
      // ignore: avoid_print
      print('\n$report');
    }, timeout: const Timeout(Duration(minutes: 5)));
  });
}
