# Experiment: the YAML reader against the old reader

Task group 2 of `native-cli-yaml-settings` (design D6). This records what was run and what it showed; the gate decision is the orchestrator's (task 2.7).

Machine: Windows 11, Dart 3.13.7 (the `mise.toml` pin), `yaml` 3.1.4, Python 3 for the generator, run from `cli/` (Dart) and the repository root (Python).

Group 4 removed `cli/lib/src/settings/yaml.dart`, `cli/test/settings/reader_corpus_test.dart`, `cli/test/settings/gen_py_corpus.py`, `cli/test/settings/yaml_test.dart` and the `probe (2.2)` group of `reader_test.dart`; the paths below name them as they were when the experiment ran, and the results stay here.

## How it was run

- `mise exec -- dart pub get` after adding `yaml: ^3.1.3` to `cli/pubspec.yaml`.
- `mise exec -- dart test test/no_build_hooks_test.dart` (6 tests, passed).
- `mise exec -- dart test test/settings/reader_test.dart` (56 tests, passed; the `probe (2.2)` group holds the A1-A5 probes and is throwaway).
- `mise exec -- dart test test/settings/reader_corpus_test.dart` (1 test, passed). It runs `parseYaml` (lenient) and `yamlProblem` (strict) from `cli/lib/src/settings/yaml.dart` and `readSettingsYaml` from `cli/lib/src/settings/reader.dart` over 2,716 cases and prints each difference with its tag. It fails only if the new reader throws anything but `SettingsRefused`, or a failure case's new outcome is not the declared one.
- The Python part of the corpus is generated, not committed. From the repository root, with `SCRATCH` any empty directory outside the repository (for example under `%TEMP%\specwright-corpus`):

  ```
  mkdir -p "$SCRATCH"
  PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 python -I cli/test/settings/gen_py_corpus.py . "$SCRATCH/py_corpus.json"
  cd cli
  SW_CORPUS_PY="$SCRATCH/py_corpus.json" mise exec -- dart test test/settings/reader_corpus_test.dart
  rm -r "$SCRATCH"
  ```

  `cli/test/settings/gen_py_corpus.py` sits next to the corpus test; it is throwaway tooling, deleted with the experiment, and writes only the JSON file (it is about 330 lines; it parses every `evals/**/*.py` that mentions `specwright.yaml` with `ast`, evaluates string expressions, and calls the fixture helpers, as the table below says). The test reads the JSON named by `SW_CORPUS_PY`. When the variable is unset or the file is absent the test prints `PYTHON CORPUS: skipped (SW_CORPUS_PY is not set to an existing file)` and runs the rest; that run reads 907 cases, of which 773 are identical, with the same tags except fewer cases (S5 76, S6 16, S7 4, D3 4, YAML 32, text-added 16). The numbers in this file are from the run with the generated file. The generated file is 1,824 entries; 15 are dropped as duplicates of a text already in the corpus.
- `python -m unittest evals/runner/test_suite_map.py` after adding the tracked test files (10 tests, passed).

## Corpus

| Group | Cases | How gathered |
|---|---|---|
| Repository settings (`repo`) | 2 | `openspec/specwright.yaml` and `templates/openspec/specwright.yaml`, read through `readSettingsText`. No other tracked file is a settings file: `git ls-files` finds no other `specwright.yaml`, and `evals/` and `cli/test/` hold no settings fixture files (the only YAML there is `evals/packs/fixtures/schema.yaml`, a schema, not settings). |
| Dogfood projects (`dogfood`) | 2 | `F:/Dev/Dart/mythspine/openspec/specwright.yaml` and `F:/Dev/Dart/blackgrid/openspec/specwright.yaml`, read in place, never copied or committed. Only outcomes and differing key paths are recorded here. The test skips a file that is absent. |
| Dart inline literals (`inline`) | 280 | Every `.dart` file under `cli/test/` that mentions `specwright.yaml`, `parseYaml`, `yamlProblem` or `readSettings` (found by the test itself, 9 files: `settings/rules_test`, `settings/yaml_test`, `pr/settings_commands_test`, `pr/policy_test`, `review/settings_test`, `release/history_test`, `release/versions_test`, `vcs/scripts_test`, `vcs/gitbutler_backend_test`), except the experiment's own `reader_test.dart` and `reader_corpus_test.dart`. The test lexes each file, joins adjacent string literals, decodes escapes and keeps each literal whose first non-comment line looks like `key:`; duplicates are dropped. The filter also lets a few expected-message literals through (for example `pr.merge_method: '' must be merge, squash or rebase`, rules_test.dart#27 and #35); both readers see them as invalid YAML, so they show as S5 and are not settings. |
| Dart literals with interpolation (`inline-interp`) | 21 | The same lexer, for literals that contain `$name` or `${...}`; each interpolation is written as `X`. These are placeholders: the outcome describes the text with `X`, not the real interpolated text (for example `'$pinned# edited\n'` becomes `X# edited\n`). Listed separately so they can be told apart. |
| Dart helper-built (`dart-helper`) | 575 | `cli/test/release/versions_test.dart` (`entries(files, extra:)`) and `history_test.dart` (`entriesFor(files)`) build a `version_files` settings text with a `StringBuffer`. The corpus test builds the same text for each file name that is a map key in those two files, each pattern literal in them (those holding `\`, `(`, `)` or `^`), and each `extra:` literal (there is none: no call passes `extra:` a literal that the pattern finds, so only the empty `extra` is generated), with the helper's own template (`release:\n  enabled: true\n<extra>  version_files:\n    "<file>": '<pattern>'\n`). |
| Python eval literals (`py-literal`) | 259 | `gen_py_corpus.py` walks every `evals/**/*.py` that mentions `specwright.yaml` (39 files). Each string expression (literal, `+`, `*`, `%`, f-string, `.replace`, `.join`, comprehension over `range`, `chr`) is evaluated over module constants, class constants (`self.AGENT`), local assignments and `for` loops over literal collections (up to 60 items); parameters with a constant default are bound to it, a bool default both ways. An expression that evaluates to a string whose first key is a settings key (`pr`, `finish`, `vcs`, `release`, ...) is kept. |
| Python eval f-strings with an unresolved part (`py-interp`) | 1 | The same, when a `{...}` part could not be evaluated; it is written as `X` (`github:\n  login: KintsugiBot\n...`, evals/pr-pair/test_pr_pair.py:2611). |
| Python helper-built (`py-helper`) | 1,549 | The helpers are called for real, in a process that imports the eval fixtures: `evals/release/fixtures.py` `settings_text(version_files, enabled, merge_method, extra_release, extra, finish)` over 6 `version_files` maps (the default, `None`, `{}`, a `VERSION` pattern and every `version_files=` literal in `evals/release/*.py`) x enabled x 5 merge methods x 5 `extra_release` strings (including `\tnote: x\n`) x 3 `extra` strings (including `release:\n  enabled: true\n`, a duplicate key) x 2 `finish` values = 1,800 combinations, which give 1,528 distinct texts; `evals/git-workflow/fixtures.py` `release_settings(enabled, auto)` x 4 (all four texts were already in the corpus); and the texts `build_watch_merge` (agent x release variants; 6 distinct), the line-689 fixture (1 distinct), the line-1457 fixture (4) and pr-pair's `select_backend` (3 backends x 2 roles x logins; 10 distinct) build, rebuilt from the same constants. |
| Failure cases (`failure`) | 27 | Written out in the test: tab on line 7, duplicate keys, plain and quoted yes/no, on/off/y/n, anchor and alias, tag, two documents, list root, 65 literal `[` in a block scalar and in a plain scalar, 64 and 65 nested flow collections, 100,000 nested flow collections, 21-digit integer, hex, octal, float, Arabic-Indic digits, empty value, empty, blank and comment-only files, block sequence, non-string key. |

### Sources still omitted

Everything under `evals/` that mentions `specwright.yaml` was scanned. These expressions looked as if they held settings but were not evaluated, or are not settings:

- Evaluated by the generator but not settings: none.
- Not evaluable, and not settings (assertion and log messages, shell-fake scripts, commit trailers, regexes): `evals/cli/test_no_shell.py:69,198,209`; `evals/git-workflow/fixtures.py:372`; `evals/git-workflow/grade.py:1453`; `evals/git-workflow/test_decision_making.py:29`; `evals/git-workflow/test_grade.py:595,1061,1842`; `evals/pr-pair/test_parity.py:1065`; `evals/pr-pair/test_workflow_transport.py:390`; `evals/release/test_release.py:1261`; `evals/release/test_release_sw.py:91,158,221,232`; `evals/release/test_skill_text.py:49`; `evals/vcs/test_fetch_pull.py:132`; `evals/vcs/test_gitbutler_delete.py:141`; `evals/vcs/test_gitbutler_ranges.py:66,149`; `evals/vcs/test_probe.py:72`; `evals/vcs/vcs_test_support.py:204`.
- Settings the generator could not evaluate, by name: `evals/git-workflow/fixtures.py:689`, `:1390` and `:1457` and `evals/pr-pair/test_workflow_parity.py:240` (rebuilt by hand in the helper group above, from the same constants); `evals/pr-pair/test_pr_pair.py:627` (a `report:` example taken from the shipped template and skills, wrapped with `textwrap.indent`; the template file itself is in the corpus, the skill-text examples are not); the four `evals/vcs/test_gitbutler_{commit,delete,push}.py` lines (`:85`, `:78`, `:71`, `:93`) that append a fragment (`pr:\n  validate: "echo pwned"\n`, `pr:\n  merge: agent\n  delete_branch: true\n`) to a settings file the fixture already wrote; the full text depends on that fixture's file and is not reconstructed (the fragments are simple `pr:` mappings, and the corpus holds the same shapes).
- Not Python or Dart: shell scripts and skill documents under `skills/` and `scripts/` quote settings in prose and code blocks; they are not fixtures and were not scanned. Dart sources under `cli/lib/` hold no settings fixtures. `cli/test/settings/reader_test.dart` (the new reader's own tests) is not in the corpus: its texts are written for the new reader.
- Dart test texts built by helper code other than the two release helpers: `cli/test/vcs/scripts_test.dart` and `gitbutler_backend_test.dart` pass literals to `settings(...)`/`write(_settings, ...)`, which the lexer reads as literals; no text there is assembled from parts.

## Assumptions A1-A6

| # | Claim | Result | Evidence |
|---|---|---|---|
| A1 | `loadYamlNode` throws `YamlException` with a span on a duplicate key and on a second document | holds | Duplicate `role:` on the third line gives a span on 0-based line 2 (the second key). A second document gives "Only expected one document." on 0-based line 1 (the `---` line). |
| A2 | `yes` and `no` load as plain-style strings | holds | `yes`, `No` and `YES` load as `String` with `ScalarStyle.PLAIN`; `true` loads as `bool`. |
| A3 | The loader builds nodes recursively, so deep nesting can overflow the stack | holds; the package overflows | `loadYamlNode` of a 100,000-level `[[[...]]]` throws `StackOverflowError` (caught), after about 60 seconds. Measured: 1,000 levels load; 5,000 overflow after 0.17 s; 20,000 after 2.6 s; 100,000 after about 61 s. A block sequence `- - - ...` under a key loads at 3,000 levels and overflows at 10,000, in 20 ms. So the pre-scan is needed for speed as well as for the line number, and the stack backstop is the only guard for block nesting. |
| A4 | A node's span starts at its anchor or tag; an alias returns the anchored node | holds | `a: &r x` has span text starting `&`; `!!str y` and `!tag z` start `!`; the node for `*r` is `identical` to the anchored node. Also for collections: `x: &r` followed by an indented mapping or sequence starts at `&r`, as do `a: &r {x: 1}` and `a: !!map {b: 1}`. An alias without an anchor is a parse error ("Undefined alias."). |
| A5 | An integer too large for `int.tryParse` loads as a `double`; `0x` and `0o` read as integers | holds | `123456789012345678901` loads as `double`; `0x10` is 16; `0o17` is 15. The reader reads a plain decimal integer from its text (C4), so the double is never used. |
| A6 | The runtime closure is `yaml`, `collection`, `source_span`, `string_scanner`, `path`, `term_glyph`, none with build hooks | holds, with a correction | Adding `yaml` as a direct dependency changes `pubspec.lock` by one line (`yaml`: `transitive` to `direct main`). The runtime closure grows by exactly two packages, `yaml` 3.1.4 and `string_scanner` 1.4.1; `collection`, `source_span`, `path` and `term_glyph` were already in it through `html` and `toml`. `no_build_hooks_test.dart` passes (no hook in any locked package, a notice for every closure package). |

Resolved runtime closure (`dart pub deps --json`, 15 packages): `args` 2.7.0, `collection` 1.19.1, `crypto` 3.0.8, `csslib` 1.0.2, `ffi` 2.2.0, `html` 0.15.7, `meta` 1.19.0, `path` 1.9.1, `petitparser` 7.1.0, `source_span` 1.10.2, `string_scanner` 1.4.1 (new), `term_glyph` 1.2.2, `toml` 0.18.0, `web` 1.1.2, `yaml` 3.1.4 (new). Notices added to `cli/THIRD_PARTY_NOTICES.txt` for `string_scanner` (BSD-3-Clause) and `yaml` (MIT, with Kirill Simonov's 2006 copyright), with the licence text from the pub cache.

Other facts the probes showed, which the reader relies on:

- The package accepts a leading U+FEFF and its span offsets count it, so the reader's offset checks use the original text unchanged.
- An empty, blank or comment-only document loads as a null scalar whose span text holds only whitespace and comments; an explicit `null` or `~` has that text in the span. That is how the reader tells an empty file from an explicit null root.
- The package does not merge `<<` keys: a mapping holding `<<: {b: 1}` and `d: 2` loads `<<` as an ordinary key. (With `*x` it is refused as an alias.)

## Acceptance matrix

Outcomes: "read" is a value reading, "refused at line N" is a `SettingsRefused`. The old column also shows the strict check (`yamlProblem`) when it found a problem, because the old remote read used it. "Values" says how many path-level values differ; the text differences are `settingText` text. In the tables a backtick inside a quoted cell is shown as a typographic quote.

Tag legend. S5, S6, S7 and D3 are the proposal's approved differences. `YAML` was added by the user: "valid YAML read as YAML 1.2" (block sequences read as lists; constructs the old strict check refused only because the lenient reader would misread them: non-ASCII spaces, `...`, `|2`, trailing commas, `<<` as a plain unmerged key, flow nesting 33-64; and values the old lenient reader misread: U+2028/U+0085 in a plain value, a more-indented `>` fold line, `{x:1}`, `[x: 1]`, `{:x}`). It was approved by the user at gate 2.7 (2026-11-16). `text-added` marks a `settingText` text the old reader did not record and the new one does, equal to the value as written (keys inside flow mappings): no consumer change, because `settingText` is only called on top-level `pr` keys and the like, never on keys inside a flow mapping. `empty-file` marks the empty, blank and comment-only texts. `UNTAGGED` would be a difference in none of these; there is none.

Totals over 2,716 cases: 1,743 identical (values, text and strict outcome). Tag counts, each a count of cases (refusals) or paths (value and text differences; a case can carry several): S5 812 cases, S6 20 cases, S7 5 cases, D3 4 values, YAML 75 paths in cases that differ in values plus 63 cases where the old strict check refused and the new reader reads, text-added 251 paths, UNTAGGED 0.

| Group | Cases | Identical | Tags |
|---|---|---|---|
| repo | 2 | 2 | none |
| dogfood | 2 | 0 (text-added only) | text-added 6 |
| inline | 280 | 172 | S5 63, S6 14, S7 2, YAML 27 (+25 strict-case), text-added 9 |
| inline-interp | 21 | 15 | S5 5, YAML 1 (+1 strict-case), text-added 1 |
| dart-helper | 575 | 575 | none |
| py-literal | 259 | 127 | S5 36, S6 4, S7 1, YAML 43 (+35 strict-case), text-added 227 |
| py-interp | 1 | 0 (text-added only) | text-added 2 |
| py-helper | 1,549 | 843 | S5 700, text-added 6 |
| failure | 27 | 9 | D3 4, S5 8, S6 2, S7 2, YAML 4 (+2 strict-case) |

The `text-added` count is large in `py-literal` because a few settings texts hold many reviewers as flow mappings (`bot-NN: { role: advisory }` x 21, in `evals/pr-pair/test_pr_pair.py:584,589,592` and `test_parity.py:948`): each key inside a flow mapping has one text path. The tag rule for a text path in the corpus test is: no old text path, `text-added`; otherwise `YAML` when the old and new values at that path differ, or when the new reading has no such path (the key itself was read differently) and the case has a value difference; anything else is `UNTAGGED:text`. The last clause was added in this round for one row (test_parity.py:917, `rev:` followed by U+3000, which the old reader read as a space and YAML does not); it is the same class as the U+00A0 and U+3000 rows already tagged YAML.

After the follow-up change to `_map` (text kept for quoted scalars and flow collections, as the old reader did), the four real settings files read with identical values and identical text, except `text-added` on keys inside flow mappings in the two dogfood files.

### Repository and dogfood settings files

| File | Old outcome | New outcome | Values | Tags |
|---|---|---|---|---|
| `openspec/specwright.yaml` | read | read | identical (85 values, text identical) | identical |
| `templates/openspec/specwright.yaml` | read | read | identical (65 values, text identical) | identical |
| mythspine (dogfood) | read | read | identical | text-added on 2 keys: `pr.reviewers.chatgpt-codex-connector.request`, `pr.reviewers.chatgpt-codex-connector.role` |
| blackgrid (dogfood) | read | read | identical | text-added on 4 keys: `pr.reviewers.chatgpt-codex-connector.request`, `pr.reviewers.chatgpt-codex-connector.role`, `pr.reviewers.kody-ai.role`, `pr.reviewers.kody-ai.timeout` |

### Failure cases (27 listed, each with its declared new outcome asserted)

| Case | Old outcome | New outcome | Values | Tags |
|---|---|---|---|---|
| tab in indentation (line 7) | read (strict: line 7: a tab in the indentation) | refused at line 7: Expected a space but found a tab. | - | S5 |
| duplicate key in a reviewer | read (strict: line 5: duplicate key ‘role‘) | refused at line 5: Duplicate mapping key. | - | S5 |
| duplicate top-level key | read (strict: line 3: duplicate key ‘a‘) | refused at line 3: Duplicate mapping key. | - | S5 |
| plain yes | read | refused at line 2: ‘yes‘ is a boolean in some YAML readers and text in others; write tr... | - | S6 |
| plain No | read | refused at line 2: ‘No‘ is a boolean in some YAML readers and text in others; write tru... | - | S6 |
| quoted yes and no | read | read | 4 values | identical |
| on, off, y, n | read | read | 8 values | identical |
| anchor and alias | read (strict: line 1: ‘&‘ cannot start a plain value (anchors, tags, aliases and direct... | refused at line 1: anchors, aliases and tags are not read | - | S7 |
| tag | read (strict: line 1: ‘!‘ cannot start a plain value (anchors, tags, aliases and direct... | refused at line 1: anchors, aliases and tags are not read | - | S7, | |
| two documents | read (strict: line 2: a document marker the reader does not read (only ‘---‘ alone, fir... | refused at line 2: Only expected one document. | - | S5 |
| list root | read (strict: line 1: a block sequence (‘- item‘) is not read; write it as ‘[a, b]‘) | refused at line 1: the top level must be a mapping | - | S5 |
| 65 [ in a block scalar | read | read | 1 values | identical |
| 65 [ in a plain scalar | read | read | 2 values | identical |
| 65 nested flow collections | read (strict: line 1: flow collections nested more than 32 deep) | refused at line 1: flow collections are nested more than 64 deep | - | S5 |
| 64 nested flow collections | read (strict: line 1: flow collections nested more than 32 deep) | read | 0 value, 0 text differences | YAML, YAML:strict-case) |
| 100,000 nested flow collections | CRASH StackOverflowError | refused at line 1: flow collections are nested more than 64 deep | - | S5 |
| 21-digit integer | read | read | 2 values | identical |
| hex | read | read | 1 value, 0 text differences | D3 |
| octal | read | read | 1 value, 0 text differences | D3 |
| float | read | read | 1 value, 0 text differences | D3 |
| Arabic-Indic digits | read | read | 1 value, 0 text differences | D3 |
| empty value | read | read | 3 values | identical |
| empty file | read | read | 1 values | identical |
| blank file | read | read | 1 values | identical |
| comment-only file | read | read | 1 values | identical |
| block sequence | read (strict: line 3: a block sequence (‘- item‘) is not read; write it as ‘[a, b]‘) | read | 4 value, 0 text differences | YAML, YAML:strict-case) |
| non-string key | read | refused at line 1: a mapping key must be text | - | S5 |

### Inline settings texts (literals, no interpolation): 108 of 280 are not identical (172 identical, not listed)

| Case | Old outcome | New outcome | Values | Tags |
|---|---|---|---|---|
| pr/policy_test.dart#5<br>`bounded: deadline_exceeded: gh api\n` | read (strict: line 1: a plain value holds ‘:‘ before a space or tab) | refused at line 1: Mapping values are not allowed here. Did you miss a colon earlier? | - | S5 |
| pr/policy_test.dart#6<br>`merge policy unknown: deadline_exceeded: gh api` | read (strict: line 1: a plain value holds ‘:‘ before a space or tab) | refused at line 1: Mapping values are not allowed here. Did you miss a colon earlier? | - | S5 |
| pr/policy_test.dart#11<br>`merge policy unknown: unreadable openspec/specwright.yaml at main: ` | read (strict: line 1: a plain value holds ‘:‘ before a space or tab) | refused at line 1: Mapping values are not allowed here. Did you miss a colon earlier? | - | S5 |
| pr/policy_test.dart#12<br>`pr:\n  merge: agent\n\treviewers: {}\n` | read (strict: line 3: a tab in the indentation) | refused at line 3: Expected a space but found a tab. | - | S5 |
| pr/policy_test.dart#13<br>`pr:\n  reviewers:\n    - a\n` | read (strict: line 3: a block sequence (‘- item‘) is not read; write it as ‘[a, b]‘) | read | 3 value, 0 text differences | YAML, YAML:strict-case) |
| pr/settings_commands_test.dart#20<br>`a: 1\nb:\n  c: 1\n  d: 2\ne:\n  f:\n\tg: 1\n` | read (strict: line 7: a tab in the indentation) | refused at line 7: Tab characters are not allowed as indentation. | - | S5 |
| pr/settings_commands_test.dart#23<br>`pr:\n  settle: soon\n\tx: 1\n` | read (strict: line 3: a tab in the indentation) | refused at line 3: Expected a space but found a tab. | - | S5 |
| release/versions_test.dart#4<br>`release:\n\tenabled: true\n` | read (strict: line 2: a tab in the indentation) | refused at line 2: Tab characters are not allowed as indentation. | - | S5 |
| release/versions_test.dart#5<br>`release:\n  enabled: true\nrelease:\n  enabled: false\n` | read (strict: line 3: duplicate key ‘release‘) | refused at line 3: Duplicate mapping key. | - | S5 |
| review/settings_test.dart#3<br>`review:\n  cross_model: no\n  timeout: 5m\n` | read | refused at line 2: ‘no‘ is a boolean in some YAML readers and text in others; write tru... | - | S6 |
| review/settings_test.dart#6<br>`review:\n  order:\n    - codex\n` | read (strict: line 3: a block sequence (‘- item‘) is not read; write it as ‘[a, b]‘) | read | 3 value, 0 text differences | YAML, YAML:strict-case) |
| settings/rules_test.dart#18<br>`pr: {settle: yes}\n` | read | refused at line 1: ‘yes‘ is a boolean in some YAML readers and text in others; write tr... | - | S6 |
| settings/rules_test.dart#25<br>`pr:\n  merge_method: squash\n  delete_branch: no\n` | read | refused at line 3: ‘no‘ is a boolean in some YAML readers and text in others; write tru... | - | S6 |
| settings/rules_test.dart#31<br>`pr.merge_method: '' must be merge, squash or rebase` | read (strict: line 1: text after the closing quote) | refused at line 1: Expected a key while parsing a block mapping. | - | S5 |
| settings/rules_test.dart#32<br>`merge_method: yes` | read | refused at line 1: ‘yes‘ is a boolean in some YAML readers and text in others; write tr... | - | S6 |
| settings/rules_test.dart#39<br>`pr.delete_branch: '' must be true or false` | read (strict: line 1: text after the closing quote) | refused at line 1: Expected a key while parsing a block mapping. | - | S5 |
| settings/rules_test.dart#42<br>`pr:\n  reviewers:\n    codex: { role: required }\nplanning_store:\n  login: s\n` | read | read | 0 value, 1 text differences | text-added |
| settings/rules_test.dart#48<br>`vcs: gitbutler\nfinish: yes\n` | read | refused at line 2: ‘yes‘ is a boolean in some YAML readers and text in others; write tr... | - | S6 |
| settings/rules_test.dart#49<br>`vcs: yes\n` | read | refused at line 1: ‘yes‘ is a boolean in some YAML readers and text in others; write tr... | - | S6 |
| settings/rules_test.dart#51<br>`cheap_tier:\n  enabled: yes\n` | read | refused at line 2: ‘yes‘ is a boolean in some YAML readers and text in others; write tr... | - | S6 |
| settings/rules_test.dart#52<br>`cheap_tier: {enabled: yes}\n` | read | refused at line 1: ‘yes‘ is a boolean in some YAML readers and text in others; write tr... | - | S6 |
| settings/rules_test.dart#65<br>`a: yes\n` | read | refused at line 1: ‘yes‘ is a boolean in some YAML readers and text in others; write tr... | - | S6 |
| settings/rules_test.dart#66<br>`github:\n  login: me\n  review_request:\n    body: \"@codex review\"\n    login: poste..` | read | refused at line 6: ‘yes‘ is a boolean in some YAML readers and text in others; write tr... | - | S6 |
| settings/rules_test.dart#69<br>`pr:\n  merge: Agent\n  max_fix_rounds: yes\n  settle: 30s\n` | read | refused at line 3: ‘yes‘ is a boolean in some YAML readers and text in others; write tr... | - | S6 |
| settings/rules_test.dart#72<br>`pr:\n  reviewers:\n    a: { role: advisory }\n` | read | read | 0 value, 1 text differences | text-added |
| settings/yaml_test.dart#5<br>`# top\nfinish: pr\nvcs: Git\ndup: 1\ndup: yes\npr:\n  settle: 5m\n  merge: Agent\n  fl..` | read (strict: line 5: duplicate key ‘dup‘) | refused at line 5: Duplicate mapping key. | - | S5 |
| settings/yaml_test.dart#7<br>`a: yes\na: \|\n  block\n` | read (strict: line 2: duplicate key ‘a‘) | refused at line 2: Duplicate mapping key. | - | S5 |
| settings/yaml_test.dart#8<br>`a: 1\n  b: 2\nc: 3\n` | read (strict: line 2: unexpected indentation) | refused at line 2: Mapping values are not allowed here. Did you miss a colon earlier? | - | S5 |
| settings/yaml_test.dart#9<br>`  a: 1\n  b:\n    c: 2\nd: 3\n` | read (strict: line 4: unexpected indentation) | refused at line 4: Only expected one document. | - | S5 |
| settings/yaml_test.dart#13<br>`k: \|٣\n  x\n` | read (strict: line 1: a block scalar header the reader does not read (only \|, >, with +... | refused at line 1: Expected comment or line break. | - | S5 |
| settings/yaml_test.dart#15<br>`a: yes\nb: \"q\"\nc: 7\n` | read | refused at line 1: ‘yes‘ is a boolean in some YAML readers and text in others; write tr... | - | S6 |
| settings/yaml_test.dart#16<br>`a:\n\tb: 1\n` | read (strict: line 2: a tab in the indentation) | refused at line 2: Tab characters are not allowed as indentation. | - | S5 |
| settings/yaml_test.dart#18<br>`a:\n  \tb: 1\n` | read (strict: line 2: a tab in the indentation) | refused at line 2: Tab characters are not allowed as indentation. | - | S5 |
| settings/yaml_test.dart#19<br>`a: 1\n\t\nb: 2\n` | read (strict: line 2: a tab in the indentation) | refused at line 2: Expected a space but found a tab. | - | S5 |
| settings/yaml_test.dart#20<br>`a: \|\n  x\n\t\n  y\n` | read (strict: line 3: a tab in the indentation) | refused at line 4: Expected a key while parsing a block mapping. | - | S5 |
| settings/yaml_test.dart#21<br>`a: 1\nb: x\u0001y\n` | read (strict: line 2: a control character or line separator (U+0001)) | refused at line 2: Unexpected character. | - | S5 |
| settings/yaml_test.dart#22<br>`a: 1\n\nb: \u0000\n` | read (strict: line 3: a control character or line separator (U+0000)) | refused at line 3: Unexpected character. | - | S5 |
| settings/yaml_test.dart#23<br>`a: 1\nb: x\u2028y\n` | read (strict: line 2: a control character or line separator (U+2028)) | read | 1 value, 1 text differences | YAML, YAML:strict-case) |
| settings/yaml_test.dart#24<br>`a: x\u2029y\n` | read (strict: line 1: a control character or line separator (U+2029)) | read | 1 value, 1 text differences | YAML, YAML:strict-case) |
| settings/yaml_test.dart#25<br>`a: 1\nb: x\u0085y\n` | read (strict: line 2: a control character or line separator (U+0085)) | read | 1 value, 1 text differences | YAML, YAML:strict-case) |
| settings/yaml_test.dart#26<br>`a: 1\nb: x\uFEFFy\n` | read (strict: line 2: a control character or line separator (U+FEFF)) | refused at line 2: Unexpected character. | - | S5 |
| settings/yaml_test.dart#27<br>`a: 1\nb: x\fy\n` | read (strict: line 2: a control character or line separator (U+000C)) | refused at line 2: Unexpected character. | - | S5 |
| settings/yaml_test.dart#28<br>`a: 1\nb: 2\nc: x\u000by\n` | read (strict: line 3: a control character or line separator (U+000B)) | refused at line 3: Unexpected character. | - | S5 |
| settings/yaml_test.dart#29<br>`a: 1\rb: 2\rc: \u0001\r` | read (strict: line 3: a control character or line separator (U+0001)) | refused at line 3: Unexpected character. | - | S5 |
| settings/yaml_test.dart#30<br>`a: 1\nb: x\u00A0y\n` | read (strict: line 2: a space character YAML does not separate with (U+00A0)) | read | 0 value, 0 text differences | YAML, YAML:strict-case) |
| settings/yaml_test.dart#31<br>`a: 1\nb: 2\nc: x\u3000y\n` | read (strict: line 3: a space character YAML does not separate with (U+3000)) | read | 0 value, 0 text differences | YAML, YAML:strict-case) |
| settings/yaml_test.dart#32<br>`a: 1\r\nb: x\u2002y\r\n` | read (strict: line 2: a space character YAML does not separate with (U+2002)) | read | 0 value, 0 text differences | YAML, YAML:strict-case) |
| settings/yaml_test.dart#33<br>`k: a\u202Fb\n` | read (strict: line 1: a space character YAML does not separate with (U+202F)) | read | 0 value, 0 text differences | YAML, YAML:strict-case) |
| settings/yaml_test.dart#34<br>`a: 1\n---\n` | read (strict: line 2: a document marker the reader does not read (only ‘---‘ alone, fir... | refused at line 2: Only expected one document. | - | S5 |
| settings/yaml_test.dart#35<br>`a: 1\n...\n` | read (strict: line 2: a document marker the reader does not read (only ‘---‘ alone, fir... | read | 0 value, 0 text differences | YAML, YAML:strict-case) |
| settings/yaml_test.dart#36<br>`a:\n  - x\n  - y\n` | read (strict: line 2: a block sequence (‘- item‘) is not read; write it as ‘[a, b]‘) | read | 4 value, 0 text differences | YAML, YAML:strict-case) |
| settings/yaml_test.dart#37<br>`a:\n  -\n` | read (strict: line 2: a block sequence (‘- item‘) is not read; write it as ‘[a, b]‘) | read | 3 value, 0 text differences | YAML, YAML:strict-case) |
| settings/yaml_test.dart#38<br>`base: 1\n<<: x\n` | read (strict: line 2: a ‘<<‘ merge key (YAML merges it in, the reader does not)) | read | 0 value, 0 text differences | YAML, YAML:strict-case) |
| settings/yaml_test.dart#39<br>`a:\n  <<: *x\n` | read (strict: line 2: a ‘<<‘ merge key (YAML merges it in, the reader does not)) | refused at line 2: Undefined alias. | - | S5 |
| settings/yaml_test.dart#40<br>`a: {<<: x}\n` | read (strict: line 1: a ‘<<‘ merge key (YAML merges it in, the reader does not)) | read | 0 value, 1 text differences | YAML, YAML:strict-case), text-added |
| settings/yaml_test.dart#41<br>`a: 1\nb: 2\na: 3\n` | read (strict: line 3: duplicate key ‘a‘) | refused at line 3: Duplicate mapping key. | - | S5 |
| settings/yaml_test.dart#42<br>`a: 1\n\"a\": 2\n` | read (strict: line 2: duplicate key ‘a‘) | refused at line 2: Duplicate mapping key. | - | S5 |
| settings/yaml_test.dart#43<br>`'a': 1\n'a': 2\n` | read (strict: line 2: duplicate key ‘a‘) | refused at line 2: Duplicate mapping key. | - | S5 |
| settings/yaml_test.dart#44<br>`m:\n  x: 1\n  y: 2\n  x: 3\n` | read (strict: line 4: duplicate key ‘x‘) | refused at line 4: Duplicate mapping key. | - | S5 |
| settings/yaml_test.dart#46<br>`a: {x: 1, y: 2, x: 3}\n` | read (strict: line 1: duplicate key ‘x‘) | refused at line 1: Duplicate mapping key. | - | S5 |
| settings/yaml_test.dart#47<br>`a: [{x: 1, x: 2}]\n` | read (strict: line 1: duplicate key ‘x‘) | refused at line 1: Duplicate mapping key. | - | S5 |
| settings/yaml_test.dart#49<br>`a: \|2\n  x\n` | read (strict: line 1: a block scalar header the reader does not read (only \|, >, with +... | read | 0 value, 0 text differences | YAML, YAML:strict-case) |
| settings/yaml_test.dart#50<br>`a: \|٣\n  x\n` | read (strict: line 1: a block scalar header the reader does not read (only \|, >, with +... | refused at line 1: Expected comment or line break. | - | S5 |
| settings/yaml_test.dart#51<br>`a: \|x\n  y\n` | read (strict: line 1: a block scalar header the reader does not read (only \|, >, with +... | refused at line 1: Expected comment or line break. | - | S5 |
| settings/yaml_test.dart#54<br>`a: \|\n      \n  x\n` | read (strict: line 1: a blank line before a block scalar's text with more spaces than t... | refused at line 3: Expected a key while parsing a block mapping. | - | S5 |
| settings/yaml_test.dart#55<br>`a: \|\n    x\n  y\n` | read (strict: line 1: a block scalar line indented less than its first line) | refused at line 3: Expected a key while parsing a block mapping. | - | S5 |
| settings/yaml_test.dart#56<br>`a: >\n  x\n    y\n` | read (strict: line 1: a more-indented or tab-led line in a ‘>‘ block (YAML keeps its li... | read | 1 value, 0 text differences | YAML, YAML:strict-case) |
| settings/yaml_test.dart#57<br>`a: >\n  x\n  \ty\n` | read (strict: line 1: a more-indented or tab-led line in a ‘>‘ block (YAML keeps its li... | read | 1 value, 0 text differences | YAML, YAML:strict-case) |
| settings/yaml_test.dart#59<br>`a: [1, 2\n` | read (strict: line 1: unterminated ‘[‘) | refused at line 2: While parsing a flow sequence, expected ',' or ']'. | - | S5 |
| settings/yaml_test.dart#60<br>`a: [1,, 2]\n` | read (strict: line 1: an empty entry) | refused at line 1: Expected node content. | - | S5 |
| settings/yaml_test.dart#61<br>`a: [1, 2,]\n` | read (strict: line 1: a trailing comma (the reader keeps it as an empty entry)) | read | 0 value, 0 text differences | YAML, YAML:strict-case) |
| settings/yaml_test.dart#62<br>`a: {x: 1,}\n` | read (strict: line 1: a trailing comma (the reader keeps it as an empty entry)) | read | 0 value, 1 text differences | YAML, YAML:strict-case), text-added |
| settings/yaml_test.dart#63<br>`a: {x:1}\n` | read (strict: line 1: a flow key holds ‘:‘ (the reader splits at the first one)) | read | 2 value, 0 text differences | YAML, YAML:strict-case) |
| settings/yaml_test.dart#65<br>`a: [x: 1]\n` | read (strict: line 1: a ‘key: value‘ pair inside ‘[...]‘ is read as text) | read | 2 value, 1 text differences | YAML, YAML:strict-case), text-added |
| settings/yaml_test.dart#66<br>`a: &x 1\n` | read (strict: line 1: ‘&‘ cannot start a plain value (anchors, tags, aliases and direct... | refused at line 1: anchors, aliases and tags are not read | - | S7 |
| settings/yaml_test.dart#67<br>`a: *x\n` | read (strict: line 1: ‘*‘ cannot start a plain value (anchors, tags, aliases and direct... | refused at line 1: Undefined alias. | - | S5 |
| settings/yaml_test.dart#68<br>`a: !t x\n` | read (strict: line 1: ‘!‘ cannot start a plain value (anchors, tags, aliases and direct... | refused at line 1: anchors, aliases and tags are not read | - | S7 |
| settings/yaml_test.dart#69<br>`a: 'x' y\n` | read (strict: line 1: text after the closing quote) | refused at line 1: Expected a key while parsing a block mapping. | - | S5 |
| settings/yaml_test.dart#70<br>`a: [x] y\n` | read (strict: line 1: text after the closing bracket) | refused at line 1: Expected a key while parsing a block mapping. | - | S5 |
| settings/yaml_test.dart#71<br>`a: \"\\q\"\n` | read (strict: line 1: unknown escape ‘\q‘) | refused at line 1: Unknown escape character. | - | S5 |
| settings/yaml_test.dart#72<br>`a: \"x\n` | read (strict: line 1: unterminated quote) | refused at line 2: Unexpected end of file. | - | S5 |
| settings/yaml_test.dart#73<br>`a: 'x\n` | read (strict: line 1: unterminated quote) | refused at line 2: Unexpected end of file. | - | S5 |
| settings/yaml_test.dart#74<br>`a: \"\\ud800\"\n` | read (strict: line 1: unknown escape ‘\u‘) | refused at line 1: Invalid Unicode character escape code. | - | S5 |
| settings/yaml_test.dart#75<br>`a: \"\\U00110000\"\n` | CRASH RangeError | refused at line 1: Invalid Unicode character escape code. | - | S5 |
| settings/yaml_test.dart#76<br>`a: b: c\n` | read (strict: line 1: a plain value holds ‘:‘ before a space or tab) | refused at line 1: Mapping values are not allowed here. Did you miss a colon earlier? | - | S5 |
| settings/yaml_test.dart#77<br>`a: b:\n` | read (strict: line 1: a plain value holds ‘:‘ before a space or tab) | refused at line 1: Mapping values are not allowed here. Did you miss a colon earlier? | - | S5 |
| settings/yaml_test.dart#79<br>`a: [x[y]\n` | read (strict: line 1: ‘[‘ where ‘,‘ or ‘]‘ belongs) | refused at line 1: While parsing a flow sequence, expected ',' or ']'. | - | S5 |
| settings/yaml_test.dart#80<br>`a: ]\n` | read (strict: line 1: ‘]‘ cannot start a plain value (anchors, tags, aliases and direct... | refused at line 1: Expected node content. | - | S5 |
| settings/yaml_test.dart#81<br>`a: {[x]: 1}\n` | read (strict: line 1: a flow key that is a collection) | refused at line 1: a mapping key must be text | - | S5 |
| settings/yaml_test.dart#82<br>`a: [[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]\n` | read (strict: line 1: flow collections nested more than 32 deep) | read | 0 value, 0 text differences | YAML, YAML:strict-case) |
| settings/yaml_test.dart#84<br>`a: [?x]\n` | read (strict: line 1: ‘?‘ cannot start a plain value (anchors, tags, aliases and direct... | read | 0 value, 0 text differences | YAML, YAML:strict-case) |
| settings/yaml_test.dart#85<br>`a: {:x}\n` | read (strict: line 1: ‘:‘ cannot start a plain value (anchors, tags, aliases and direct... | read | 2 value, 0 text differences | YAML, YAML:strict-case) |
| settings/yaml_test.dart#87<br>`a: 1\nplain text\n` | read (strict: line 2: not a ‘key: value‘ line) | refused at line 3: Expected ':'. | - | S5 |
| settings/yaml_test.dart#88<br>`a: 1\n  b: 2\n` | read (strict: line 2: unexpected indentation) | refused at line 2: Mapping values are not allowed here. Did you miss a colon earlier? | - | S5 |
| settings/yaml_test.dart#89<br>`  a: 1\nb: 2\n` | read (strict: line 2: unexpected indentation) | refused at line 2: Only expected one document. | - | S5 |
| settings/yaml_test.dart#90<br>`a: %x\n` | read (strict: line 1: ‘%‘ cannot start a plain value (anchors, tags, aliases and direct... | refused at line 1: Unexpected character. | - | S5 |
| settings/yaml_test.dart#91<br>`a: [\|x]\n` | read (strict: line 1: ‘\|‘ cannot start a plain value (anchors, tags, aliases and direct... | refused at line 1: Unexpected character. | - | S5 |
| settings/yaml_test.dart#92<br>`a: ‘x\n` | read (strict: line 1: ‘‘‘ cannot start a plain value (anchors, tags, aliases and direct... | refused at line 1: Unexpected character. | - | S5 |
| settings/yaml_test.dart#93<br>`a: @x\n` | read (strict: line 1: ‘@‘ cannot start a plain value (anchors, tags, aliases and direct... | refused at line 1: Unexpected character. | - | S5 |
| settings/yaml_test.dart#94<br>`a: - x\n` | read (strict: line 1: ‘-‘ cannot start a plain value (anchors, tags, aliases and direct... | refused at line 1: Block sequence entries are not allowed here. | - | S5 |
| settings/yaml_test.dart#95<br>`a: ? x\n` | read (strict: line 1: ‘?‘ cannot start a plain value (anchors, tags, aliases and direct... | refused at line 1: Mapping keys are not allowed here. | - | S5 |
| settings/yaml_test.dart#96<br>`a: [1, 2] # c\nb: {x: 'y', z: \"w\"}\n` | read | read | 0 value, 2 text differences | text-added |
| settings/yaml_test.dart#97<br>`# c\nfinish: pr\nvcs: git\npr:\n  settle: 5m\n  reviewers:\n    kody-ai: { role: advis..` | read | read | 0 value, 2 text differences | text-added |
| settings/yaml_test.dart#98<br>`k:\n k:\n  k:\n   k:\n    k:\n     k:\n      k:\n       k:\n        k:\n         k:\n ..` | read (strict: line 33: mappings nested more than 32 deep) | read | 0 value, 0 text differences | YAML, YAML:strict-case) |
| settings/yaml_test.dart#101<br>`# c\n\n\na: 1\n# d\nb: [1,\n` | read (strict: line 6: unterminated ‘[‘) | refused at line 7: Expected node content. | - | S5 |
| settings/yaml_test.dart#103<br>`a: 1\r\n\r\nb: [\r\n` | read (strict: line 3: unterminated ‘[‘) | refused at line 4: Expected node content. | - | S5 |
| vcs/gitbutler_backend_test.dart#8<br>`as.sh: no\n` | read | refused at line 1: ‘no‘ is a boolean in some YAML readers and text in others; write tru... | - | S6 |
| vcs/gitbutler_backend_test.dart#9<br>`as.sh: no` | read | refused at line 1: ‘no‘ is a boolean in some YAML readers and text in others; write tru... | - | S6 |

### Inline settings texts with an interpolation (each interpolation written as `X`): 6 of 21 are not identical (15 identical, not listed)

| Case | Old outcome | New outcome | Values | Tags |
|---|---|---|---|---|
| pr/policy_test.dart#14<br>`merge policy unknown: unreadable openspec/specwright.yaml at X: ` | read (strict: line 1: a plain value holds ‘:‘ before a space or tab) | refused at line 1: Mapping values are not allowed here. Did you miss a colon earlier? | - | S5 |
| pr/policy_test.dart#21<br>`pr:\n  reviewers:\nX` | read (strict: line 3: not a ‘key: value‘ line) | refused at line 3: Could not find expected ':' for simple key. | - | S5 |
| settings/rules_test.dart#40<br>`pr:\n  X\n` | read (strict: line 2: not a ‘key: value‘ line) | read | 1 value, 1 text differences | YAML, YAML:strict-case), text-added |
| settings/rules_test.dart#44<br>`AttributeError: 'X' object has no attribute 'get'` | read (strict: line 1: text after the closing quote) | refused at line 1: Expected a key while parsing a block mapping. | - | S5 |
| vcs/gitbutler_backend_test.dart#6<br>`X has no GitButler meaning: vcs: gitbutler runs only with finish: pr, where the PR mer..` | read (strict: line 1: a plain value holds ‘:‘ before a space or tab) | refused at line 1: Mapping values are not allowed here. Did you miss a colon earlier? | - | S5 |
| vcs/gitbutler_backend_test.dart#7<br>`the GitButler commit on feat is not what was asked: it holds files outside the named p..` | read (strict: line 1: a plain value holds ‘:‘ before a space or tab) | refused at line 1: Mapping values are not allowed here. Did you miss a colon earlier? | - | S5 |

### Python eval settings literals: 132 of 259 are not identical (127 identical, not listed)

| Case | Old outcome | New outcome | Values | Tags |
|---|---|---|---|---|
| git-workflow/grade.py:973<br>`finish: pr resume where the change's PR #7 is merged and the local branch is gone (squ..` | read (strict: line 1: a comment the reader would keep as text) | refused at line 2: Expected a key while parsing a block mapping. | - | S5 |
| git-workflow/grade.py:1182<br>`finish: pr, the change's PR #7 merged on GitHub and squashed onto origin's main (Add g..` | read (strict: line 1: a comment the reader would keep as text) | refused at line 2: Expected a key while parsing a block mapping. | - | S5 |
| git-workflow/grade.py:1228<br>`finish: local with release.auto, the change's branch bumped VERSION to 0.5.0: the loca..` | read (strict: line 1: a plain value holds ‘:‘ before a space or tab) | refused at line 1: Mapping values are not allowed here. Did you miss a colon earlier? | - | S5 |
| pr-pair/test_parity.py:599<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    rev: { role: required }\n` | read | read | 0 value, 1 text differences | text-added |
| pr-pair/test_parity.py:600<br>`pr:\n  merge: user\n  reviewers:\n    rev: { role: required }\n` | read | read | 0 value, 1 text differences | text-added |
| pr-pair/test_parity.py:781<br>`github:\n  login: me\nvalidate: make check\npr:\n  settle: 2m\n  merge: agent\n  merge..` | read | read | 0 value, 5 text differences | text-added |
| pr-pair/test_parity.py:803<br>`pr:\n\treviewers: x\n` | read (strict: line 2: a tab in the indentation) | refused at line 2: Tab characters are not allowed as indentation. | - | S5 |
| pr-pair/test_parity.py:804<br>`pr:\n  reviewers:\n    r: { report: 3 }\n` | read | read | 0 value, 1 text differences | text-added |
| pr-pair/test_parity.py:804<br>`pr:\n  merge: yes\n` | read | refused at line 2: ‘yes‘ is a boolean in some YAML readers and text in others; write tr... | - | S6 |
| pr-pair/test_parity.py:841<br>`pr:\n  merge: agent\n  items:\n    - a\n` | read (strict: line 4: a block sequence (‘- item‘) is not read; write it as ‘[a, b]‘) | read | 3 value, 0 text differences | YAML, YAML:strict-case) |
| pr-pair/test_parity.py:858<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    rev: { role: required }..` | read | read | 0 value, 1 text differences | text-added |
| pr-pair/test_parity.py:885<br>`github:\n  login: me\nvalidate: make check\npr:\n  merge: user\n  reviewers:\n\trev: {..` | read (strict: line 7: a tab in the indentation) | refused at line 7: Tab characters are not allowed as indentation. | - | S5 |
| pr-pair/test_parity.py:910<br>`pr:\n  reviewers:\n    rev: { timeout: ٣٠m }\n` | read | read | 0 value, 1 text differences | text-added |
| pr-pair/test_parity.py:911<br>`pr:\n  reviewers:\n    rev: { timeout: ２０m }\n` | read | read | 0 value, 1 text differences | text-added |
| pr-pair/test_parity.py:912<br>`pr:\n\u00A0\u00A0merge: agent\n` | read (strict: line 2: a space character YAML does not separate with (U+00A0)) | read | 2 value, 2 text differences | YAML, YAML:strict-case), text-added |
| pr-pair/test_parity.py:913<br>`pr:\n\u3000merge: agent\n` | read (strict: line 2: a space character YAML does not separate with (U+3000)) | read | 2 value, 2 text differences | YAML, YAML:strict-case), text-added |
| pr-pair/test_parity.py:914<br>`pr:\n  merge:\u00A0agent\n` | read (strict: line 2: a space character YAML does not separate with (U+00A0)) | read | 2 value, 2 text differences | YAML, YAML:strict-case), text-added |
| pr-pair/test_parity.py:915<br>`pr:\n  merge: agent\u3000\n` | read (strict: line 2: a space character YAML does not separate with (U+3000)) | read | 1 value, 0 text differences | YAML, YAML:strict-case) |
| pr-pair/test_parity.py:916<br>`pr:\n  settle:\u30002m\u00A0\n` | read (strict: line 2: a space character YAML does not separate with (U+3000)) | read | 2 value, 2 text differences | YAML, YAML:strict-case), text-added |
| pr-pair/test_parity.py:917<br>`pr:\n  reviewers:\n    rev:\u3000{ role: advisory }\n` | read (strict: line 3: a space character YAML does not separate with (U+3000)) | read | 2 value, 2 text differences | YAML, YAML:strict-case), text-added |
| pr-pair/test_parity.py:918<br>`github:\n  login:\u00A0me\n` | read (strict: line 2: a space character YAML does not separate with (U+00A0)) | read | 2 value, 2 text differences | YAML, YAML:strict-case), text-added |
| pr-pair/test_parity.py:937<br>`pr:\n  merge: agent\n  reviewers:\n    rev[bot]: { role: required }\n` | read | read | 0 value, 1 text differences | text-added |
| pr-pair/test_parity.py:948<br>`pr:\n  merge: agent\n  reviewers:\n    bot-0: { role: advisory }\n    bot-1: { role: a..` | read | read | 0 value, 21 text differences | text-added |
| pr-pair/test_pr_pair.py:335<br>`finish: pr\ngithub:\n  login: sh1ny\nplanning_store:\n  login: KintsugiBot\n  main_bra..` | read | read | 0 value, 4 text differences | text-added |
| pr-pair/test_pr_pair.py:355<br>`github:\n  login: sh1ny\npr:\n  validate: \"python -m unittest\"\n  reviewers:\n    ko..` | read | read | 0 value, 1 text differences | text-added |
| pr-pair/test_pr_pair.py:367<br>`github:\n  login: sh1ny\nplanning_store:\n  validate: >-\n    openspec validate\n    -..` | read | read | 0 value, 1 text differences | text-added |
| pr-pair/test_pr_pair.py:380<br>`github:\n  login: 'sh1ny'\nplanning_store:\n  validate: 'echo ''ok'' # still the value..` | read | read | 0 value, 2 text differences | text-added |
| pr-pair/test_pr_pair.py:390<br>`github:\n  login: sh1ny\npr:\n  reviewers:\n    kody-ai: { role: advisory }\n` | read | read | 0 value, 1 text differences | text-added |
| pr-pair/test_pr_pair.py:402<br>`pr:\n  merge: auto\n  reviewers:\n    chatgpt-codex-connector: { role: required }\n` | read | read | 0 value, 1 text differences | text-added |
| pr-pair/test_pr_pair.py:410<br>`pr:\n  merge: Yes\n` | read | refused at line 2: ‘Yes‘ is a boolean in some YAML readers and text in others; write tr... | - | S6 |
| pr-pair/test_pr_pair.py:416<br>`pr:\n  merge: agent\n  reviewers:\n    chatgpt-codex-connector: { role: required }\n  ..` | read | read | 0 value, 2 text differences | text-added |
| pr-pair/test_pr_pair.py:424<br>`pr:\n  merge: agent\n  reviewers:\n    kody-ai: { role: advisory }\n` | read | read | 0 value, 1 text differences | text-added |
| pr-pair/test_pr_pair.py:433<br>`planning_store:\n  reviewers: {}\npr:\n  merge: agent\n  reviewers:\n    chatgpt-codex..` | read | read | 0 value, 1 text differences | text-added |
| pr-pair/test_pr_pair.py:467<br>`pr:\n  reviewers:\n    a-bot:\n      report:\n        check: Bot Code Review\n        ..` | read | read | 0 value, 1 text differences | text-added |
| pr-pair/test_pr_pair.py:477<br>`pr:\n  reviewers:\n    a-bot:\n      report:\n        check: Bot Code Review\n        ..` | read | read | 0 value, 4 text differences | text-added |
| pr-pair/test_pr_pair.py:499<br>`pr:\n  reviewers:\n    kody-ai: { role: advisory, timeout: 15m, request: \"@kody revie..` | read | read | 0 value, 5 text differences | text-added |
| pr-pair/test_pr_pair.py:516<br>`planning_store:\n  reviewers:\n    store-bot: { role: required }\npr:\n  reviewers:\n ..` | read | read | 0 value, 2 text differences | text-added |
| pr-pair/test_pr_pair.py:521<br>`planning_store:\n  reviewers: {}\npr:\n  reviewers:\n    chatgpt-codex-connector: { ro..` | read | read | 0 value, 1 text differences | text-added |
| pr-pair/test_pr_pair.py:584<br>`pr:\n  reviewers:\n    bot-00: { role: advisory }\n    bot-01: { role: advisory }\n   ..` | read | read | 0 value, 21 text differences | text-added |
| pr-pair/test_pr_pair.py:589<br>`pr:\n  reviewers:\n    bot-00: { role: advisory }\n    bot-01: { role: advisory }\n   ..` | read | read | 0 value, 20 text differences | text-added |
| pr-pair/test_pr_pair.py:592<br>`planning_store:\n  reviewers:\n    bot-00: { role: advisory }\n    bot-01: { role: adv..` | read | read | 0 value, 21 text differences | text-added |
| pr-pair/test_pr_pair.py:1568<br>`github:\n  login: KintsugiBot\npr:\n  max_fix_rounds: 2\n  react: true\n  reviewers:\n..` | read | read | 0 value, 2 text differences | text-added |
| pr-pair/test_pr_pair.py:2218<br>`github:\n  login: KintsugiBot\npr:\n  max_fix_rounds: 2\n  reviewers:\n    chatgpt-cod..` | read | read | 0 value, 2 text differences | text-added |
| pr-pair/test_pr_pair.py:3992<br>`cheap_tier:\n  enabled: no\n` | read | refused at line 2: ‘no‘ is a boolean in some YAML readers and text in others; write tru... | - | S6 |
| pr-pair/test_pr_pair.py:3992<br>`cheap_tier:\n  enabled: NO\n` | read | refused at line 2: ‘NO‘ is a boolean in some YAML readers and text in others; write tru... | - | S6 |
| pr-pair/test_pr_pair.py:4017<br>`cheap_tier: { enabled: on }\n` | read | read | 0 value, 1 text differences | text-added |
| pr-pair/test_pr_pair.py:4021<br>`cheap_tier: { enabled: true }\n` | read | read | 0 value, 1 text differences | text-added |
| pr-pair/test_pr_pair.py:4035<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read | read | 0 value, 1 text differences | text-added |
| pr-pair/test_pr_pair.py:4036<br>`pr:\n  merge: user\n  reviewers:\n    chatgpt-codex-connector: { role: required }\n` | read | read | 0 value, 1 text differences | text-added |
| pr-pair/test_pr_pair.py:4132<br>`main_branch: attacker-branch\npr:\n  merge: agent\n  merge_method: squash\n  reviewers..` | read | read | 0 value, 1 text differences | text-added |
| pr-pair/test_pr_pair.py:4141<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    someone-else: { role: r..` | read | read | 0 value, 1 text differences | text-added |
| pr-pair/test_pr_pair.py:4176<br>`# the policy\npr:\n  reviewers:\n    chatgpt-codex-connector: { timeout: 20m, role: 'r..` | read | read | 0 value, 2 text differences | text-added |
| pr-pair/test_pr_pair.py:4235<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read (strict: line 6: unterminated ‘[‘) | refused at line 7: While parsing a flow sequence, expected ',' or ']'. | - | S5 |
| pr-pair/test_pr_pair.py:4238<br>`pr:\n  merge agent\n` | read (strict: line 2: not a ‘key: value‘ line) | read | 1 value, 1 text differences | YAML, YAML:strict-case), text-added |
| pr-pair/test_pr_pair.py:4241<br>`pr:\n  merge: user\n merge_method: squash\n` | read (strict: line 3: unexpected indentation) | refused at line 3: Expected a key while parsing a block mapping. | - | S5 |
| pr-pair/test_pr_pair.py:4244<br>`pr:\n  merge: \"agent\n` | read (strict: line 2: unterminated quote) | refused at line 3: Unexpected end of file. | - | S5 |
| pr-pair/test_pr_pair.py:4245<br>`pr:\n  merge: agent: now\n` | read (strict: line 2: a plain value holds ‘:‘ before a space or tab) | refused at line 2: Mapping values are not allowed here. Did you miss a colon earlier? | - | S5 |
| pr-pair/test_pr_pair.py:4249<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read (strict: line 6: unknown escape ‘\q‘) | refused at line 6: Unknown escape character. | - | S5 |
| pr-pair/test_pr_pair.py:4250<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read (strict: line 6: unknown escape ‘\x‘) | refused at line 6: Expected 2-digit hexidecimal number. | - | S5 |
| pr-pair/test_pr_pair.py:4251<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read (strict: line 6: unknown escape ‘\q‘) | refused at line 6: Unknown escape character. | - | S5 |
| pr-pair/test_pr_pair.py:4257<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read (strict: line 6: unknown escape ‘\u‘) | refused at line 6: Invalid Unicode character escape code. | - | S5 |
| pr-pair/test_pr_pair.py:4257<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read (strict: line 6: unknown escape ‘\u‘) | refused at line 6: Invalid Unicode character escape code. | - | S5 |
| pr-pair/test_pr_pair.py:4257<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read (strict: line 6: unknown escape ‘\u‘) | refused at line 6: Invalid Unicode character escape code. | - | S5 |
| pr-pair/test_pr_pair.py:4257<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read (strict: line 6: unknown escape ‘\U‘) | refused at line 6: Invalid Unicode character escape code. | - | S5 |
| pr-pair/test_pr_pair.py:4257<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | CRASH RangeError | refused at line 6: Invalid Unicode character escape code. | - | S5 |
| pr-pair/test_pr_pair.py:4264<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read (strict: line 6: ‘:‘ cannot start a plain value (anchors, tags, aliases and direct... | read | 0 value, 2 text differences | YAML, YAML:strict-case), text-added |
| pr-pair/test_pr_pair.py:4264<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read (strict: line 6: ‘:‘ cannot start a plain value (anchors, tags, aliases and direct... | read | 0 value, 1 text differences | YAML, YAML:strict-case), text-added |
| pr-pair/test_pr_pair.py:4264<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read (strict: line 6: ‘?‘ cannot start a plain value (anchors, tags, aliases and direct... | read | 0 value, 1 text differences | YAML, YAML:strict-case), text-added |
| pr-pair/test_pr_pair.py:4264<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read (strict: line 6: ‘?‘ cannot start a plain value (anchors, tags, aliases and direct... | read | 0 value, 2 text differences | YAML, YAML:strict-case), text-added |
| pr-pair/test_pr_pair.py:4264<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read (strict: line 6: a ‘key: value‘ pair inside ‘[...]‘ is read as text) | read | 0 value, 1 text differences | YAML, YAML:strict-case), text-added |
| pr-pair/test_pr_pair.py:4264<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read (strict: line 6: ‘:‘ where ‘,‘ or ‘}‘ belongs) | read | 0 value, 2 text differences | YAML, YAML:strict-case), text-added |
| pr-pair/test_pr_pair.py:4264<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read (strict: line 6: a flow key's ‘:‘ not followed by a space) | read | 2 value, 2 text differences | YAML, YAML:strict-case), text-added |
| pr-pair/test_pr_pair.py:4270<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read (strict: line 6: a flow key's ‘:‘ not followed by a space) | read | 0 value, 2 text differences | YAML, YAML:strict-case), text-added |
| pr-pair/test_pr_pair.py:4270<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read (strict: line 6: a flow key's ‘:‘ not followed by a space) | read | 0 value, 2 text differences | YAML, YAML:strict-case), text-added |
| pr-pair/test_pr_pair.py:4270<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read (strict: line 6: a flow key's ‘:‘ not followed by a space) | read | 0 value, 2 text differences | YAML, YAML:strict-case), text-added |
| pr-pair/test_pr_pair.py:4270<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read (strict: line 6: a flow key's ‘:‘ not followed by a space) | read | 0 value, 1 text differences | YAML, YAML:strict-case), text-added |
| pr-pair/test_pr_pair.py:4274<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read (strict: line 5: an empty entry) | refused at line 5: Expected node content. | - | S5 |
| pr-pair/test_pr_pair.py:4276<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read (strict: line 7: a trailing comma (the reader keeps it as an empty entry)) | read | 0 value, 1 text differences | YAML, YAML:strict-case), text-added |
| pr-pair/test_pr_pair.py:4277<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read (strict: line 6: a flow key holds ‘:‘ (the reader splits at the first one)) | read | 2 value, 2 text differences | YAML, YAML:strict-case), text-added |
| pr-pair/test_pr_pair.py:4283<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read (strict: line 7: a block sequence (‘- item‘) is not read; write it as ‘[a, b]‘) | read | 3 value, 1 text differences | YAML, YAML:strict-case), text-added |
| pr-pair/test_pr_pair.py:4283<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read (strict: line 6: ‘&‘ cannot start a plain value (anchors, tags, aliases and direct... | refused at line 6: anchors, aliases and tags are not read | - | S7 |
| pr-pair/test_pr_pair.py:4283<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read (strict: line 6: duplicate key ‘pr‘) | refused at line 6: Duplicate mapping key. | - | S5 |
| pr-pair/test_pr_pair.py:4283<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read (strict: line 7: a tab in the indentation) | refused at line 7: Tab characters are not allowed as indentation. | - | S5 |
| pr-pair/test_pr_pair.py:4287<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read (strict: line 6: a plain value holds ‘:‘ before a space or tab) | refused at line 6: Mapping values are not allowed here. Did you miss a colon earlier? | - | S5 |
| pr-pair/test_pr_pair.py:4293<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read (strict: line 6: a document marker the reader does not read (only ‘---‘ alone, fir... | refused at line 6: Only expected one document. | - | S5 |
| pr-pair/test_pr_pair.py:4301<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read (strict: line 6: a control character or line separator (U+2028)) | refused at line 6: Mapping values are not allowed here. Did you miss a colon earlier? | - | S5 |
| pr-pair/test_pr_pair.py:4301<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read (strict: line 6: a control character or line separator (U+0000)) | refused at line 6: Unexpected character. | - | S5 |
| pr-pair/test_pr_pair.py:4301<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read (strict: line 6: a ‘<<‘ merge key (YAML merges it in, the reader does not)) | read | 0 value, 3 text differences | YAML, YAML:strict-case), text-added |
| pr-pair/test_pr_pair.py:4301<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read (strict: line 6: a blank line before a block scalar's text with more spaces than t... | refused at line 8: Expected a key while parsing a block mapping. | - | S5 |
| pr-pair/test_pr_pair.py:4307<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read (strict: line 6: a control character or line separator (U+0080)) | refused at line 6: Unexpected character. | - | S5 |
| pr-pair/test_pr_pair.py:4307<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read (strict: line 6: a control character or line separator (U+0084)) | refused at line 6: Unexpected character. | - | S5 |
| pr-pair/test_pr_pair.py:4307<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read (strict: line 6: a control character or line separator (U+0086)) | refused at line 6: Unexpected character. | - | S5 |
| pr-pair/test_pr_pair.py:4307<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read (strict: line 6: a control character or line separator (U+009F)) | refused at line 6: Unexpected character. | - | S5 |
| pr-pair/test_pr_pair.py:4307<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read (strict: line 6: a control character or line separator (U+FFFE)) | refused at line 6: Unexpected character. | - | S5 |
| pr-pair/test_pr_pair.py:4307<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read (strict: line 6: a control character or line separator (U+FFFF)) | refused at line 6: Unexpected character. | - | S5 |
| pr-pair/test_pr_pair.py:4313<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read (strict: line 6: a space character YAML does not separate with (U+00A0)) | refused at line 7: Expected ':'. | - | S5 |
| pr-pair/test_pr_pair.py:4313<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read (strict: line 6: a space character YAML does not separate with (U+00A0)) | read | 1 value, 1 text differences | YAML, YAML:strict-case), text-added |
| pr-pair/test_pr_pair.py:4313<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read (strict: line 6: a space character YAML does not separate with (U+00A0)) | read | 2 value, 3 text differences | YAML, YAML:strict-case), text-added |
| pr-pair/test_pr_pair.py:4313<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read (strict: line 6: a space character YAML does not separate with (U+3000)) | read | 0 value, 1 text differences | YAML, YAML:strict-case), text-added |
| pr-pair/test_pr_pair.py:4313<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read (strict: line 6: a space character YAML does not separate with (U+2003)) | read | 0 value, 1 text differences | YAML, YAML:strict-case), text-added |
| pr-pair/test_pr_pair.py:4317<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read (strict: line 6: a tab in the indentation) | refused at line 6: Tab characters are not allowed as indentation. | - | S5 |
| pr-pair/test_pr_pair.py:4318<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read (strict: line 6: a tab in the indentation) | refused at line 6: Tab characters are not allowed as indentation. | - | S5 |
| pr-pair/test_pr_pair.py:4322<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read (strict: line 6: a key of 1024 characters or more (YAML's simple-key limit)) | read | 0 value, 1 text differences | YAML, YAML:strict-case), text-added |
| pr-pair/test_pr_pair.py:4323<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read (strict: line 6: a key of 1024 characters or more (YAML's simple-key limit)) | read | 0 value, 2 text differences | YAML, YAML:strict-case), text-added |
| pr-pair/test_pr_pair.py:4327<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read (strict: line 6: a more-indented or tab-led line in a ‘>‘ block (YAML keeps its li... | read | 1 value, 1 text differences | YAML, YAML:strict-case), text-added |
| pr-pair/test_pr_pair.py:4328<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read (strict: line 6: a block scalar line indented less than its first line) | refused at line 8: Expected a key while parsing a block mapping. | - | S5 |
| pr-pair/test_pr_pair.py:4332<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read (strict: line 6: flow collections nested more than 32 deep) | refused at line 6: flow collections are nested more than 64 deep | - | S5 |
| pr-pair/test_pr_pair.py:4334<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read (strict: line 38: mappings nested more than 32 deep) | read | 0 value, 1 text differences | YAML, YAML:strict-case), text-added |
| pr-pair/test_pr_pair.py:4338<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read (strict: line 6: a more-indented or tab-led line in a ‘>‘ block (YAML keeps its li... | read | 1 value, 1 text differences | YAML, YAML:strict-case), text-added |
| pr-pair/test_pr_pair.py:4344<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read | read | 0 value, 1 text differences | text-added |
| pr-pair/test_pr_pair.py:4344<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read | read | 0 value, 1 text differences | text-added |
| pr-pair/test_pr_pair.py:4344<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read | read | 0 value, 1 text differences | text-added |
| pr-pair/test_pr_pair.py:4359<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read | read | 0 value, 1 text differences | text-added |
| pr-pair/test_pr_pair.py:4412<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    code-bot: { role: requi..` | read | read | 0 value, 3 text differences | text-added |
| pr-pair/test_pr_pair.py:4432<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read | read | 0 value, 1 text differences | text-added |
| pr-pair/test_pr_pair.py:4437<br>`pr:\n  merge: agent\n  reviewers:\n    tree-bot: { role: required }\n` | read | read | 0 value, 1 text differences | text-added |
| pr-pair/test_pr_pair.py:4456<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read | read | 0 value, 4 text differences | text-added |
| pr-pair/test_pr_pair.py:4472<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read | read | 0 value, 1 text differences | text-added |
| pr-pair/test_pr_pair.py:4499<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    rev-bot:\n      role: r..` | read | read | 0 value, 1 text differences | text-added |
| pr-pair/test_pr_pair.py:4514<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read | read | 0 value, 3 text differences | text-added |
| pr-pair/test_pr_pair.py:4546<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read | read | 0 value, 3 text differences | text-added |
| pr-pair/test_pr_pair.py:4559<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read | read | 0 value, 1 text differences | text-added |
| pr-pair/test_pr_pair.py:4559<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read | read | 0 value, 1 text differences | text-added |
| pr-pair/test_pr_pair.py:4559<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read | read | 0 value, 1 text differences | text-added |
| pr-pair/test_pr_pair.py:4563<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read | read | 0 value, 1 text differences | text-added |
| pr-pair/test_pr_pair.py:4568<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read | read | 0 value, 1 text differences | text-added |
| pr-pair/test_pr_pair.py:4568<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read | read | 0 value, 1 text differences | text-added |
| pr-pair/test_pr_pair.py:4573<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    chatgpt-codex-connector..` | read | read | 0 value, 1 text differences | text-added |
| pr-pair/test_pr_pair.py:4579<br>`pr:\n  merge: agent\n  merge_method: squash\n  reviewers:\n    bot-00: { role: advisor..` | read | read | 0 value, 21 text differences | text-added |
| review-routes/test_review_run.py:284<br>`review:\n  order:\n    - omp\n    - codex\n` | read (strict: line 3: a block sequence (‘- item‘) is not read; write it as ‘[a, b]‘) | read | 4 value, 0 text differences | YAML, YAML:strict-case) |
| review-routes/test_review_run.py:288<br>`review:\n  order:\n  - codex\n` | read (strict: line 3: a block sequence (‘- item‘) is not read; write it as ‘[a, b]‘) | read | 3 value, 0 text differences | YAML, YAML:strict-case) |
| update/test_update_jj_store.py:90<br>`planning_store: {vcs: jj}\n` | read | read | 0 value, 1 text differences | text-added |

### Python eval settings built with an f-string that could not be fully evaluated (unresolved part written as `X`): 1 of 1 are not identical (0 identical, not listed)

| Case | Old outcome | New outcome | Values | Tags |
|---|---|---|---|---|
| pr-pair/test_pr_pair.py:2611<br>`github:\n  login: KintsugiBot\npr:\n  max_fix_rounds: 2\n  reviewers:\n    chatgpt-cod..` | read | read | 0 value, 2 text differences | text-added |

### Helper-built texts, one row per distinct outcome (the identical ones are counted in the group table, not listed)

| Cases | Source | Old outcome | New outcome | Tags |
|---|---|---|---|---|
| 92 | release/fixtures.py settings_text | read (strict: line 8: duplicate key ‘release‘) | refused at line 8: Duplicate mapping key. | S5 |
| 92 | release/fixtures.py settings_text | read (strict: line 9: duplicate key ‘release‘) | refused at line 9: Duplicate mapping key. | S5 |
| 60 | release/fixtures.py settings_text | read (strict: line 8: a tab in the indentation) | refused at line 8: Tab characters are not allowed as indentation. | S5 |
| 112 | release/fixtures.py settings_text | read (strict: line 10: duplicate key ‘release‘) | refused at line 10: Duplicate mapping key. | S5 |
| 48 | release/fixtures.py settings_text | read (strict: line 11: duplicate key ‘release‘) | refused at line 11: Duplicate mapping key. | S5 |
| 48 | release/fixtures.py settings_text | read (strict: line 10: a tab in the indentation) | refused at line 10: Tab characters are not allowed as indentation. | S5 |
| 4 | release/fixtures.py settings_text | read (strict: line 5: duplicate key ‘release‘) | refused at line 5: Duplicate mapping key. | S5 |
| 16 | release/fixtures.py settings_text | read (strict: line 6: duplicate key ‘release‘) | refused at line 6: Duplicate mapping key. | S5 |
| 12 | release/fixtures.py settings_text | read (strict: line 5: a tab in the indentation) | refused at line 5: Tab characters are not allowed as indentation. | S5 |
| 36 | release/fixtures.py settings_text | read (strict: line 7: duplicate key ‘release‘) | refused at line 7: Duplicate mapping key. | S5 |
| 72 | release/fixtures.py settings_text | read (strict: line 7: a tab in the indentation) | refused at line 7: Tab characters are not allowed as indentation. | S5 |
| 12 | release/fixtures.py settings_text | read (strict: line 6: a tab in the indentation) | refused at line 6: Tab characters are not allowed as indentation. | S5 |
| 96 | release/fixtures.py settings_text | read (strict: line 9: a tab in the indentation) | refused at line 9: Tab characters are not allowed as indentation. | S5 |
| 6 | git-workflow/fixtures.py build_watch_merge | read | read | text-added |

## Differences by tag

- **S5 (old read leniently, YAML refuses)**: 812 cases refused by the new reader. 700 are `py-helper` texts: the release fixture's `release:\n  enabled: true\n` as `extra` after `release:` (duplicate key `release`) and its `\tnote: x\n` (tab indentation), over every other parameter (14 distinct outcomes, one per line number); both are the fixture's own bad-settings rows (`SettingsRows.BAD`). The other 112: 63 inline, 5 inline-interp, 36 py-literal, 8 failure cases. Their causes: tab in indentation, duplicate keys, two documents, a list root, a non-string key, unknown or invalid escapes (`"\q"`, `"\xZZ"`, surrogate and post-U+10FFFF `\u`/`\U`), unterminated quotes or brackets, control characters (including U+FEFF inside the text), `: ` inside a plain value, `:\t` in a plain value, text after a closing quote or bracket, a flow sequence missing its `]`, 65 nested flow collections (the cap), 100,000 nested flow collections, and an undefined alias. The old strict check refused every one of these except the non-string key `1: a` (its old column is a plain `read`); three rows show an old crash instead of a read: `"\U00110000"`-style escapes crash the old lenient reader with a `RangeError` (yaml_test.dart#75, test_pr_pair.py:4257), and 100,000 nested `[` crash it with a `StackOverflowError` (after about 20 s); the new reader refuses all three, naming the line. Two of the refusals are expected-message literals, not settings (rules_test.dart#27, #35).
- **S6 (plain yes/no)**: 20 cases (2 failure, 14 inline, 4 py-literal), each refused naming its line and saying to write `true` or `false`: `yes`, `No`, `YES`, `no`, `NO`, in block and flow mappings and in lists. `'yes'`, `"no"`, `on`, `off`, `y`, `n` read as strings with the same values and text as the old reader.
- **S7 (anchor, alias, tag)**: 5 cases (2 failure, 2 inline, 1 py-literal) refused naming the anchor or tag line. `a: *r` without an anchor and `<<: *x` are refused by the package as "Undefined alias." (listed under S5).
- **D3 (hex, octal, float, non-ASCII digits)**: 4 values: `0x10` string to 16, `0o17` string to 15, `1.5` string to 1.5, Arabic-Indic digits integer 12 to a string. A 21-digit integer and the 64-bit edges are identical to the old reader (exact big integers, C4). The Python corpus adds none: its Arabic-Indic and fullwidth digits sit inside flow mappings (`{ timeout: ٣٠m }`, `evals/pr-pair/test_parity.py:909-911`), where they are text in both readers (text-added only).
- **empty-file**: empty, blank and comment-only texts are identical (an empty mapping in both); an explicit `null` or `~` is refused. `key:` with no value is `null` in both readers.
- **YAML (approved by the user at gate 2.7 (2026-11-16))**: valid YAML read as YAML 1.2. In the corpus:
  - Block sequences read as lists: `review.order` as a block sequence (the spec's "A block sequence" scenario; also `evals/review-routes/test_review_run.py:284,288`), `pr.reviewers` as a list (policy_test.dart#12), `pr.items` (`test_parity.py:841`), `x:` (`test_pr_pair.py:4283`), and `a:` with two items or an empty item. The old reader skipped `- item` and read the key as `{}` (or `null`). Consumer note: a `pr.reviewers` list is now a list where the old reader gave `{}`, so group 3's `pr.reviewers` callers must treat it as a wrong shape (D5).
  - A line without a key under a key is a plain multi-line scalar in YAML 1.2: `pr:\n  merge agent\n` now reads `pr` as the string `merge agent` (old lenient: `{}`; old strict: refused as "not a `key: value` line"; `test_pr_pair.py:4238`, rules_test.dart#40 with `X`). Consumer note, same as the list: a string where a mapping belongs is a wrong shape for group 3's `pr`, `github` and `planning_store` callers.
  - Unicode spaces (U+00A0, U+3000) are not YAML separators or indentation. The old lenient reader treated them as spaces; YAML 1.2 does not, so `pr:\n  merge:\u00A0agent\n` now reads `pr` as the string `merge:\u00A0agent`, `rev:\u3000{ role: advisory }` reads a key `rev:\u3000{ role` with the text `advisory }`, a U+00A0-indented line becomes its own top-level key, and a trailing U+3000 stays in the value (`evals/pr-pair/test_parity.py:912-918`, rows 912, 913, 914, 915, 916, 917, 918 in the table below; and `test_pr_pair.py:4313`). The old strict check refused all of them, so the old policy read of a head or main settings file stopped on them (`lookup_failed`); the new reader reads them as the values just described, and group 3's policy must still stop on the wrong shape (a string `pr`) or on an unexpected key. This is the largest consumer-visible case in the Python corpus.
  - Values the old reader misread: U+2028, U+2029 or U+0085 inside a plain value (yaml_test.dart#23-25: old keeps the text before the separator, new the whole value); a `>` fold with a more-indented or tab-led line (yaml_test.dart#56, #57, `test_pr_pair.py:4327,4338`); `{x:1}`, `{a:b: 1}` and `{a: ?b: c}`-style flow keys (yaml_test.dart#63, #85, `test_pr_pair.py:4264,4277`: a key `x:1`, `a:b` or `a:?b` instead of the old split at the first `:`); `[x: 1]` (yaml_test.dart#65: a one-entry mapping instead of the string `x: 1`).
  - Constructs the old strict check refused and the new reader reads (63 cases; values equal to the old lenient read unless listed above): Unicode spaces in a plain value (U+00A0, U+3000, U+2002, U+2003, U+202F; yaml_test.dart#30-33, `test_pr_pair.py:4313`); `...` (yaml_test.dart#35); `|2` (#49); trailing commas `[1, 2,]`, `{x: 1,}` (#61, #62, `test_pr_pair.py:4276`); `[?x]` (#84); `<<` as an ordinary key, not merged (yaml_test.dart#38, #40, `test_pr_pair.py:4301`); keys of 1,024 or more characters (`test_pr_pair.py:4322,4323`); nesting from 33 to 64 levels (yaml_test.dart#82, #98, `test_pr_pair.py:4334`; the old strict cap was 32). These reach `policy`'s remote read only: `lookup_failed` before, values now. None is an anchor, alias or tag.
- **text-added (251 paths)**: the old reader recorded no text for a key inside a flow mapping (`reviewers: { codex: { role: required } }`), the new one records the value as written (and, for a key the old reader read differently, the text of the key the new reader found). Not a consumer change: `settingText` is called on top-level `pr` keys, `finish`, `cheap_tier.enabled` and `pr.reviewers`, not on keys inside a flow mapping, and the text equals the written value.

## UNTAGGED differences

None. Every difference in the 2,716 cases falls under S5, S6, S7, D3, YAML, text-added or empty-file. During this round one row first printed as `UNTAGGED:text` (`evals/pr-pair/test_parity.py:917`, `rev:` + U+3000 + `{ role: advisory }`: the old reader's `rev` text has no counterpart in the new reading, because the new key is `rev:\u3000{ role`); I changed the corpus test's text-path rule so that a missing new text path in a case that also has a value difference is `YAML`, the same class as the other U+00A0 and U+3000 rows. That is a classification decision by me, within the approved `YAML` class; say if you want it reported as separate.

The `YAML` rule in the corpus test tags a value path as YAML when the old and new readings differ and either a block sequence is read or one side lacks the path; I listed every such case above by hand against the printed rows (Dart literals and the Python literals), and each is one of the constructs above.

## Gate (task 2.7, S1)

No untagged difference reaches a consumer (none is left untagged), and every check from the proposal's "What the experiment must show" holds:
- Duplicate keys are refused, `yes` and `no` reach the boolean check as strings (A2) and are refused (S6), and a parse error reports a line.
- 100,000-level nesting neither crashes nor passes; the reader refuses it naming a line.
- `cli/test/no_build_hooks_test.dart` passes, and the notice covers `yaml` and `string_scanner`. `collection` and `source_span` were already covered.

Re-verified by the orchestrator on 2026-11-16 with the generated Python corpus: 1,743 of 2,716 cases identical, no UNTAGGED. `reader_test.dart` (56 tests) and `no_build_hooks_test.dart` pass.

Result: pass
