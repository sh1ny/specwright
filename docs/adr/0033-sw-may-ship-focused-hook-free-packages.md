# 0033. `sw` may ship focused, hook-free packages

- Status: accepted
- Date: 2026-11-09
- Supersedes: —
- Adds to: 0027 (its dependency clause only; `sw` stays one `dart compile exe` file with no build hooks)

## Context

ADR 0027 allowed `cli/` two packages, `package:args` and `package:ffi`. To stay inside that limit the ports reproduced Python by hand: a SHA-256, a JSON reader and writer that follow CPython, four argument parsers, `os.path`, and a page scanner for `gh` output. M7's parity method rewarded this, because each port was compared with a frozen copy of its script. The code it left costs more to keep than it protects: `sw` and the skills that consume it ship together at one exact version (ADR 0027), so nothing outside this repository depends on Python's formatting, parser quirks or historical error text.

## Decision

- **Focused packages are allowed, one approval each.** `cli/` may depend on a pure-Dart package that does one job, once the user approves that package. The approved set is `args`, `ffi`, `html` (rendered closing references, `native-cli-pr-pair-flow`), `crypto` and `path`. `yaml` is approved only if the experiment in `native-cli-yaml-settings` passes.
- **No build hooks, still.** The distribution remains one file from `dart compile exe`. `cli/test/no_build_hooks_test.dart` keeps failing when a package with build hooks enters `pubspec.lock`, and it is re-checked after every dependency change.
- **Notices ship with the dependencies.** The resolved runtime dependencies, transitive ones included, each have their licence notice in a third-party notice file delivered with `sw`.
- **What a port preserves.** A port or replacement preserves product workflow guarantees: safety, identity, ownership, recovery, fail-closed behaviour and user outcomes. It does not preserve byte-for-byte Python output, parser quirks or historical error text. A producer and its consuming skills and tests change together, and each difference that reaches a consumer has a test at that consumer.
- **What stays custom.** `shellQuote` in `finish/script_text.dart`, `quoteBatchLine` in `process/command_line.dart`, and the process-tree, job-object and FFI code stay as they are. No focused package covers these guarantees.

**Rejected: keeping the two-package limit,** because it keeps over 1,000 lines of Python-shaped code that exist only to match a language `sw` is replacing. **Rejected: any pure-Dart package without approval,** because every package adds to the shipped closure and its notices, and a dependency is cheap to add and expensive to remove once skills rely on its behaviour. **Rejected: one general-purpose framework for parsing and I/O,** because it would pull a larger closure into a single-file tool for behaviour that four small packages and `dart:convert` already cover.

## Consequences

- `pubspec.lock`'s runtime closure grows: `html` brings `csslib`, `source_span`, `collection`, `path` and `term_glyph`; `yaml` would add `string_scanner`. The notice file has to follow the lock file.
- Library behaviour replaces reproduced behaviour, so each adoption needs a test of what the consumer relies on, because a package upgrade can change it. `pubspec.lock` is enforced at build (`dart pub get --enforce-lockfile`), so an upgrade is always a reviewed change.
- Oracle comparisons become parsed-value or outcome comparisons wherever a Python-only form was all they pinned. Frozen oracles stay usable as evidence of workflow outcomes.
- Reversal cost: low for each package, since every one sits behind a small module; medium for the preservation rule, because later ports and their consumers will be written against it.
