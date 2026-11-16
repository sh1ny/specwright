# Proposal

## Why

`sw` carries an 830-line port of Python's settings reader, `cli/lib/src/settings/yaml.dart`, and a second check, `yaml_problem`, that exists only because that reader is lenient for local reads and has to be strict for remote ones. One real parser for local and remote reads removes the reason for both. This change serves M8, Complete the native CLI migration (#148). It runs after `native-cli-release`, when the Python readers in `skills/specwright-review/scripts/review-run.sh` and `skills/specwright-release/scripts/release.sh` are gone, and before `native-cli-update`. It has no user-verified exit criterion.

The design is written when this change starts, because the review and release ports will change the callers it would cite.

## What Changes

- **Experiment first.** The change starts with an experiment that runs the `yaml` package against this repository's settings, every settings fixture in the evals, the dogfood projects' settings as the user provides them, and the failure cases below. The package is adopted only if the experiment passes. If it fails, the change stops, the strict reader stays, and no dependency is added.
- **One parser.** Local and remote reads of `openspec/specwright.yaml` use the same parser and the same refusals. `yaml_problem` goes away, in `sw` and in the shim scripts that still carry it.
- **BREAKING:** a boolean setting written `yes` or `no` is an error telling the user to write `true` or `false`. The `yaml` package treats those words as strings, so a silent reading would turn a setting off.
- **Upgrade note.** The release that ships this carries a specific note telling the agent to find `yes` and `no` boolean settings in existing `openspec/specwright.yaml` files and rewrite them as `true` and `false`.
- **Fail-closed remote policy.** A remote settings file that the parser refuses, holds duplicate keys, or has the wrong shape stops `policy` with `lookup_failed`, and nothing merges.
- **Deep nesting.** The strict reader's depth limit goes away, so a deeply nested settings file must stop with the settings problem error and never crash.

### What the experiment must show

- One acceptance matrix decides it, recorded in `experiment.md`. Each settings file above gives the same values and outcomes as the old reader, except the differences this change approves, each listed with its expected outcome: a plain `yes` or `no` is refused (S6); a file the old reader read leniently but YAML refuses is refused (S5); anchors, aliases and tags are refused (S7); hex, octal, floats and integers written with non-ASCII digits read as YAML 1.2 defines them (design D3); an empty or comment-only file is still an empty mapping; valid YAML the old reader skipped or misread, or its strict check refused only for that reason, reads as YAML 1.2 defines it (block sequences as lists, non-ASCII spaces, `...`, explicit block-scalar indentation, trailing flow commas, `<<` as a plain unmerged key, flow nesting up to 64), approved by the user at the experiment gate (2026-11-16). Any other difference that reaches a consumer stops adoption.
- Duplicate keys are refused, `yes` and `no` reach the boolean check as strings, and a parse error reports a line.
- A file nested far beyond the old limit neither crashes nor passes as valid.
- `cli/test/no_build_hooks_test.dart` passes after `dart pub get`, and the notice covers `yaml` and its closure (`collection`, `source_span`, `string_scanner`).

### Tests that retire

- `cli/test/settings/yaml_test.dart`: the cases whose expected values come from CPython running the frozen reader, including `yaml_problem` and Python-specific scalar forms.
- `evals/pr-pair/test_pr_pair.py` around line 623: the check that loads `yaml_problem` from the script.

### Tests that change to parsed values or outcomes

- `cli/test/settings/yaml_test.dart`: the surviving cases assert the value read and the stop reported for each input.
- `evals/pr-pair/test_parity.py`: `test_context_tab_in_indentation_names_line_7` and the settings cases compare the parsed fields and the `settings_problem` line number, with the `yes`/`no` difference listed.
- `evals/pr-pair/test_parity.py` `test_policy_stops` and the `lookup_failed` cases gain the remote cases above: duplicate key, refused syntax, wrong shape, deep nesting.
- Eval fixtures that write `yes` or `no` for a boolean change to `true` or `false`, except the new tests of the error.

### Skills and scripts that change

- `skills/specwright-pr/scripts/pr-pair.sh`: any remaining `yaml_problem` text.
- The skills that read or describe settings booleans (`specwright-review`, `specwright-release`, `specwright-pr`) state `true` and `false`.
- README settings examples and the install prompt's generated settings use `true` and `false`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pr-script-runtime`: the settings reader's contract, the strict remote read and the boolean error.
- `native-cli`: the shipped dependency set gains `yaml` if the experiment passes.
- `pr-merge`: policy reads fail closed under the new parser.
- `pr-evidence`: `context` stops on a settings file the reader refuses instead of reporting it as `settings_problem` and going on (S5).
- `cost-tiers`: `yes` no longer reads as true; a refused file leaves the cheap tier off with a note.
- `releases`: a release stops on any file the reader refuses, not only on a line the old reader would misread.

## Impact

Touches `cli/lib/src/settings/yaml.dart` and its callers, `cli/lib/src/pr/policy.dart`, `cli/pubspec.yaml` and `pubspec.lock`, the third-party notice, the evals above and the settings text in skills and the README. Any project with a boolean written `yes` or `no` stops at its first settings read until it is corrected, which the upgrade note covers.

## Decision Making

DECISION_MAKING: important
- **Source:** setting

### S1: Adopt yaml only if the experiment passes

- **Choice:** Run the experiment first, and stop with the strict reader in place if it fails.
- **Rejected:** Adopt the package unconditionally.
- **Reversal cost:** medium
- **Important:** yes, weak evidence.
- **Chosen by:** user, "It starts with an experiment, and the yaml package is adopted only if the experiment passes."

### S2: yes and no become an error

- **Choice:** A boolean setting written `yes` or `no` stops with an error naming `true` and `false`, with an upgrade note for the agent.
- **Rejected:** Keep accepting them through a local conversion, which keeps the Python rule.
- **Reversal cost:** low
- **Important:** yes, changes what users see.
- **Chosen by:** user, "Boolean settings written yes or no become an error telling the user to write true or false".

### S3: One parser for local and remote reads

- **Choice:** A single parser, removing `yaml_problem`.
- **Rejected:** Keep a separate strict check for remote reads.
- **Reversal cost:** medium
- **Important:** yes, binds future changes.
- **Chosen by:** user, "One real parser for local and remote reads removes the reason yaml_problem exists."

### S4: Write the design at this change's turn

- **Choice:** This proposal only.
- **Rejected:** Full artifacts now, which the intervening ports would make stale.
- **Reversal cost:** low
- **Important:** yes, binds future changes.
- **Chosen by:** user, "Their designs are written at their turn, because the intervening ports would make them stale."

### S5: A refused file stops every local read

- **Choice:** Every command that reads the settings stops with its settings error naming the line, `context` included, so ship, finish and cleanup stop until the file is fixed. `tier` alone exits 0 with the cheap tier off and a note. `context` keeps `settings_problem` for problems with a value that was read, such as `pr.settle`.
- **Rejected:** `context` reports the problem and returns defaults so ship, finish and cleanup go on; defaults can pick the wrong backend, main branch or account.
- **Reversal cost:** medium
- **Important:** yes, changes what users see.
- **Chosen by:** user, "Every reader stops" (2026-11-15).

### S6: Any plain yes or no is refused

- **Choice:** The reader refuses any unquoted `yes` or `no` value, in any case, naming the line and `true`/`false`. A quoted `'yes'` stays a string.
- **Rejected:** Each reader checks its own boolean keys, where a missed key turns a setting off silently.
- **Reversal cost:** low
- **Important:** yes, changes what users see.
- **Chosen by:** user, "Any plain yes/no" (2026-11-15).

### S7: Anchors, aliases and tags stay refused

- **Choice:** The reader refuses them, locally and remotely, as the strict check did.
- **Rejected:** Accept them as YAML does, with a separate bound on expanded size for remote reads.
- **Reversal cost:** low
- **Important:** yes, security.
- **Chosen by:** user, "Keep refusing" (2026-11-15).

## Release Notes

Settings are now read by one real YAML parser, locally and remotely. This release breaks settings that write a boolean as `yes` or `no`: after updating to 0.36.0, find those values in `openspec/specwright.yaml` and rewrite them as `true` and `false`. Until then a settings read stops and names the line.

### Changed

- `openspec/specwright.yaml` is read by one parser, locally and remotely, with the same refusals (#148).
- **Breaking:** a boolean setting written `yes` or `no` (any case) stops with an error naming the line, `true` and `false`. After upgrading, find such settings and rewrite them (#148).
- Anchors, aliases and tags, duplicate keys and NaN or infinite numbers are refused, naming the line (#148).
- A section of the wrong shape (a list or a plain value where a mapping goes) stops the read instead of being read as empty (#148).
- Each command stops with its own code on a refused file; `context` stops with `bad_setting`, and `settings_problem` reports only value problems (#148).
- `sw` now depends on the `yaml` Dart package (#148).
