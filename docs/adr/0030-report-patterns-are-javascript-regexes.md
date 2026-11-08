# 0030. Report patterns are JavaScript regular expressions in Unicode mode

- Status: accepted
- Date: 2026-11-08
- Adds to: 0022 (reviewer detection is generic), which names no regex dialect

## Context

ADR 0022 puts bot-specific reviewer rules in the user's settings: `pr.reviewers.<login>.report.sha_pattern` and `ignore` are regular expressions that the evaluator runs over PR text. Until now the evaluator was `reviewers.py`, so the patterns were Python `re` expressions, though nothing recorded that. `native-cli-pr-pair` ports the evaluator to `sw pr reviewers`, in Dart. Dart's `RegExp` implements the JavaScript (ECMAScript) dialect, not Python's. The port either translates Python syntax, keeps a Python evaluator, or changes the dialect the settings are written in.

## Decision

- **`sha_pattern` and `ignore` are JavaScript regular expressions in Unicode mode, as Dart's `RegExp(pattern, unicode: true)` reads them.** They are searched (a match anywhere counts), case-sensitive and not multiline, as before.
- **Unicode mode, not the default mode.** In the default mode `\A` and `\Z` compile and match the letters `A` and `Z`, and `{,3}` is read as literal text, so a Python pattern would silently change its meaning. Unicode mode refuses those, and `(?P<name>...)`, `(?i)` and an escape of a character that needs none (`\:`). A pattern written for Python therefore either keeps its meaning or fails `--check-config`, naming the reviewer and the key. It never decides under another meaning.
- **A change to what a pattern matches raises the reviewer-config `format`.** The config file's bytes and their SHA-256 digest are what every snapshot and the merge policy compare (ADR 0022). If the dialect changed and the bytes did not, a snapshot decided under the old rules would carry a matching digest. This change moves the config to `"format": 2`, and the evaluator accepts only that format. Any later change to the dialect or its flags raises `format` again.

**Rejected: a translator from Python syntax to `RegExp`.** It keeps the old dialect, but its correctness needs its own proof, for patterns that in practice are simple. **Rejected: keeping `reviewers.py` as a Python child of `sw`.** It keeps Python as a prerequisite, which M8 removes, and only moves the question to `native-cli-retire-scripts`. **Rejected: the default (non-Unicode) mode,** for the silent meaning changes above.

## Consequences

- This is a breaking settings change. Projects whose patterns use Python-only syntax must rewrite them; the snapshot refuses such a pattern loudly. The documented patterns, the settings template and this repository's own settings mean the same in both dialects.
- Some constructs both engines accept match differently: `\w`, `\W` and `\b` treat non-ASCII letters such as `é` differently. Format 2 makes every snapshot decided by the old evaluator a `rules_mismatch`, so no merge is authorized from evidence the new rules did not decide.
- The docs, the settings template and the `pr-evidence` spec name the dialect.
- Reversal cost: medium. Changing the dialect again breaks users' patterns again and needs another format bump.
