# 0037. Release version patterns are JavaScript regular expressions in Unicode and multiline mode

- Status: accepted
- Date: 2026-11-15
- Supersedes: —
- Adds to: 0030 (report patterns are JavaScript regexes), which covers reviewer patterns only

## Context

`release.version_files` maps each version file glob to a regular expression with one capture group, the version. `release.sh` compiled these patterns with Python's `re` in multiline mode, though nothing recorded the dialect. `native-cli-release` ports the release operations to `sw release`, in Dart, whose `RegExp` implements the JavaScript (ECMAScript) dialect. ADR 0030 made the same choice for reviewer patterns and rejected a translator and a kept Python evaluator; the reasons hold here too.

## Decision

- **`release.version_files` patterns are JavaScript regular expressions in Unicode and multiline mode,** as Dart's `RegExp(pattern, multiLine: true, unicode: true)` reads them. `^` and `$` match at each line. A multiline `$` matches before a `\r`, so a CRLF file needs no translation, and match offsets index the original text, so a bump keeps the CRLF.
- **Unicode mode refuses Python-only syntax.** `(?P<name>...)`, `\A`, `\Z`, `(?i)`, `{,n}` and an escape of a character that needs none (`\:`) do not compile. Such a pattern stops every release subcommand that reads settings (`check`, `bump`, `status`, `untagged`, `publish`) with `bad_version_files`, exit 1, naming the entry, before any file, tag or release is read or written. A pattern never matches under another meaning than the one it was written for.
- **Exactly one capture group is still required.** A pattern with none or several is `bad_version_files` too.

**Rejected: a translator from Python syntax to `RegExp`,** because its correctness needs its own proof for patterns that are simple in practice (as ADR 0030). **Rejected: keeping a Python evaluator,** because M8 removes Python as a prerequisite.

## Consequences

- A breaking settings change: a project whose pattern uses Python-only syntax must rewrite it. The stop names the entry. The settings template, the docs and this repository's own patterns mean the same in both dialects.
- Some constructs both engines accept match differently, as ADR 0030 lists: `\w`, `\W` and `\b` treat non-ASCII letters such as `é` differently. Version captures are ASCII digits, so the shipped patterns are unaffected.
- The `specwright-release` skill, the settings template and the `releases` spec name the dialect.
- Reversal cost: medium. Changing the dialect again breaks users' patterns again.
