# Proposal

## Why

`pr-pair.sh` is a bash wrapper around about 2,900 lines of embedded Python with 19 subcommands. It reads every Specwright setting the PR flow uses, writes the reviewer config, decides the merge policy, and runs the PR flow's GitHub and git steps. `reviewers.py` decides which reviewers reported on a head. Both need Python 3.8+. `sw` itself still runs `pr-pair.sh` as a subprocess: `sw vcs` and the GitButler backend read the backend and logins through `pr-pair.sh vcs` and `context`, and `sw pr snapshot` runs `reviewers.py`. ADR 0027 moves shipped tooling into the Dart `sw` binary, and ADR 0028 ports each script behind a shim.

This change serves **M8 - Complete the native CLI migration** (#148). It is change 2 of 7: this proposal splits the roadmap's `native-cli-pr-pair` in two. This change ports the settings and policy side: `identity`, `vcs`, `tier`, `context` and `policy`, the strict settings reader they share, and `reviewers.py`. A new change after it, `native-cli-pr-pair-flow`, ports the other 14 subcommands. This change advances the agent-verified exit criterion "The PR, review, release and update operations use `sw`; their existing JSON, exit-code and workflow contracts are covered by the corresponding black-box evals on the three CI platforms" for the settings and policy reads. It also moves toward "No shipped skill calls a bash or Python script". The `evals/pr-pair` and `evals/vcs` tests of these subcommands, and a differential run against a frozen copy of the two scripts, check this change's part in CI on Linux, Windows and macOS.

## What Changes

- `sw` gains `sw pr identity`, `sw pr vcs`, `sw pr tier`, `sw pr context` and `sw pr policy`. They keep `pr-pair.sh`'s arguments, JSON fields, error names and exit codes; message text says the same in its own words (S5). That covers the strict settings reader and its `line N: why` problems, the reviewer-config file and its digest name, the GitButler settings pin, and the merge policy read from GitHub with its drift and `reported` checks.
- `sw` gains `sw pr reviewers`, the port of `reviewers.py`, with its `--check-config` and evaluation forms, output and exit codes. `sw pr snapshot` runs its own binary as `sw pr reviewers` instead of starting `reviewers.py`, under the same deadline and with the same results and limit messages.
- `pr-pair.sh` keeps its path and command line and becomes an ADR 0028 shim for the five ported subcommands: it resolves `sw` through `sw-path.sh` and hands them over. The other 14 subcommands, and a missing or unknown subcommand, still run the embedded Python until `native-cli-pr-pair-flow`. A missing or mismatched `sw` stops the five with `sw_missing`, and nothing falls back to the old code.
- **BREAKING** (settings): `pr.reviewers.<login>.report.sha_pattern` and `ignore` are read as JavaScript regular expressions in Unicode mode, as Dart's `RegExp` reads them, instead of Python's. The patterns in the docs, the settings template and this repo's own settings mean the same in both dialects. Unicode mode refuses the Python-only syntax (`(?P<name>...)`, `\A`, `\Z`, `(?i)`, `{,n}`) rather than reading it as something else. It also refuses an escape of a character that needs none, such as `\:` or `` \` ``. Such a pattern fails `--check-config`, naming the reviewer and the key, with Dart's compile error text.
- The reviewer-config file moves to `"format": 2`, so its digest changes. A snapshot decided by the old Python evaluator no longer matches `policy`'s digest and reports `rules_mismatch`, and watch takes a fresh one. The evaluator refuses a format 1 config (design D10).
- **BREAKING** (shipped files): `reviewers.py` is removed. No shipped caller is left, and its tests run `sw pr reviewers` with the same assertions.
- `sw vcs` and its GitButler backend read settings in-process instead of running `pr-pair.sh vcs` and `context`, with the same results and stops.
- The `evals/pr-pair` and `evals/vcs` tests of these subcommands run against the `sw` built from the tree on all three platforms, with their assertions unchanged apart from the regex dialect cases, the config format migration (`"format": 2`, its digests and paths) and assertions on message text, which check its prefix instead (S5). Every other field, code and status is compared exactly. A frozen oracle copy of `pr-pair.sh` and `reviewers.py` is run differentially against the shims.
- The roadmap's M8 lists `native-cli-pr-pair-flow` as change 3, before `native-cli-review`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pr-script-runtime`: `pr-pair.sh identity`, `vcs`, `tier`, `context` and `policy` run `sw pr <sub>` through the shim with the same contract, and stop with `sw_missing` when no matching `sw` is found. `sw pr snapshot` decides reviewer states through `sw pr reviewers`, and `reviewers.py` is gone.
- `pr-evidence`: `report.sha_pattern` and `ignore` are JavaScript regular expressions in Unicode mode, as Dart's `RegExp` reads them, instead of Python ones. The reviewer config they are written into moves to `"format": 2`.
- `vcs-backends`: `sw vcs` and the GitButler backend read the backend settings and logins in-process instead of through `pr-pair.sh`, with the same stops.

## Impact

- New Dart code under `cli/lib/src/settings/` (the strict reader and the setting rules) and `cli/lib/src/pr/` (`identity`, `vcs`, `tier`, `context`, `policy`, `reviewers`). The `pr` command group in `cli/lib/src/commands/pr.dart` grows, with Dart unit tests under `cli/test/`. `cli/lib/src/vcs/scripts.dart`, `vcs/gitbutler_backend.dart` and `pr/snapshot.dart` stop starting the scripts.
- `skills/specwright-pr/scripts/pr-pair.sh` gains a dispatch on its first argument. `reviewers.py` is deleted. `bounded.py` stays: the 14 unported subcommands and the review, release and update scripts still use it.
- Callers (the skills, `release.sh`, `review-run.sh`, `update.sh`) keep their command lines. `skills/specwright-pr/SKILL.md` gains the rule that every `pr-pair.sh` call runs from the code checkout, `identity <store toplevel>` included, because a store has no `openspec/.specwright/VERSION` to resolve `sw` from (design D2).
- `evals/pr-pair/test_reviewers.py` runs `sw pr reviewers`. `evals/pr-pair/oracle/` gains frozen `pr-pair.sh` and `reviewers.py`, used by the parity test. `evals/suites.json` gains rules for the new paths.
- `openspec/roadmap.md`: M8 grows from six changes to seven.
- The regex wording in `skills/specwright-pr/SKILL.md` and `templates/openspec/specwright.yaml` changes to name the JavaScript dialect. This repo's `openspec/specwright.yaml` pattern is checked under the new dialect and kept, since it means the same in both. Projects whose patterns use Python-only syntax must rewrite them.
- Users' prerequisites do not change until `native-cli-retire-scripts`: bash and Python stay for the scripts not yet ported.

## Decision Making

DECISION_MAKING: important
- **Source:** setting

### S1: Split the pr-pair port in two

- **Choice:** this change ports `identity`, `vcs`, `tier`, `context`, `policy`, their shared settings reader and `reviewers.py`, which together make up the settings and policy side that `sw` itself already calls. `native-cli-pr-pair-flow` ports `discover`, `expected`, `ensure-pr`, `closing-check`, `closed-check`, `link`, `pair-state`, `rounds`, `pass`, `cleanup-plan`, `branch-check`, `merge`, `delete-remote` and `item-issues`. Until then the shim sends each subcommand to `sw` or to the old Python.
- **Rejected:** one change for all 19 subcommands, as the roadmap listed it. That would be a PR of about 5,000 Dart lines, and earlier large PRs ran up to 15 review rounds.
- **Reversal cost:** low
- **Important:** yes: it changes the M8 plan the roadmap records
- **Chosen by:** user

### S2: Command names `sw pr <sub>`

- **Choice:** each ported subcommand goes under the existing `sw pr` group with its current name (`sw pr context`, `sw pr policy`, `sw pr vcs`, `sw pr reviewers` ...), beside `sw pr snapshot` and `sw pr reply`. `native-cli-retire-scripts` then swaps names one for one.
- **Rejected:** `sw pr pair <sub>`, an extra level named for store pairs, though most subcommands also serve repo-local changes. A separate `sw settings` group, a second rename for callers to learn.
- **Reversal cost:** medium
- **Important:** yes: binds future changes (the names the skills will call)
- **Chosen by:** user

### S3: Remove `reviewers.py` now

- **Choice:** `reviewers.py` is ported as `sw pr reviewers`, with the same arguments, output fields and exit codes, and deleted in this change. `test_reviewers.py` and the parity oracle run `sw pr reviewers` with every assertion unchanged, apart from the config format migration (design D10), the regex dialect cases (S6) and assertions on message text, which check its prefix (S5).
- **Rejected:** a Python shim kept until `native-cli-retire-scripts`. It would need Python only to start `sw`, and no shipped code would call it.
- **Reversal cost:** low
- **Important:** yes: changes the shipped files users see
- **Chosen by:** user

### S4: The five subcommands become ADR 0028 shims

- **Choice:** `pr-pair.sh` keeps its path and command line. For the five ported subcommands it resolves `sw` through `sw-path.sh` and runs it, with no fallback, as the earlier shims do.
- **Rejected:** switching the callers to `sw` now. ADR 0028 settles this for every M8 port.
- **Reversal cost:** low
- **Important:** no: ADR 0028 already decided it
- **Chosen by:** agent

### S5: Port for parity of what programs read

- **Choice:** every JSON field name and value, error code, exit code and file format stays, and the parity eval compares them exactly. Message text (`message`, the text after a `line N:` or `reviewers.py:` prefix, stderr lines) may say the same thing in other words, and is compared by its prefix. The exceptions are the regex dialect (S6) and the reviewer-config format 2 that follows from it (design D10): the expected format, the digests and paths derived from it, and the format the config check refuses. A defect found while porting is kept for parity and filed as an issue, unless it blocks parity on a CI platform.
- **Rejected:** byte-exact output, which would need Python's error texts reproduced in Dart although no skill parses them. Fixing behaviour or changing JSON shapes during the port, which would stop the old evals from proving parity while 14 subcommands still run in Python.
- **Reversal cost:** low
- **Important:** yes: it sets what the remaining M8 ports must keep
- **Chosen by:** user ("Fields exact, messages free")

### S6: Report patterns switch to the JavaScript regex dialect

- **Choice:** `sha_pattern` and `ignore` are compiled by Dart's `RegExp` in Unicode mode, case-sensitive and not multiline. Unicode mode is the agent's refinement of the user's choice. In the default mode, `\A` and `\Z` compile and match the letters `A` and `Z`, which silently changes a Python pattern's meaning. Unicode mode refuses them, and refuses `{,n}`, so a pattern either keeps its meaning or fails `--check-config` (checked against Dart 3.13 while planning). This is a documented breaking change: the docs, the settings template and the `pr-evidence` spec name the new dialect.
- **Rejected:** a translator from Python syntax to Dart `RegExp`. It would keep the old dialect, but its correctness would need its own proof, for patterns that in practice are simple. Keeping `reviewers.py` as a Python subprocess, which only moves the question to `native-cli-retire-scripts`.
- **Reversal cost:** medium
- **Important:** yes: changes settings users see
- **Chosen by:** user ("why do we care if we break stuff? We will update the specwright config with the new regex and document it as breaking change")

## Release Notes

The settings, reviewer-config and merge-policy reads of `pr-pair.sh` (`identity`, `vcs`, `tier`, `context` and `policy`) and the reviewer evaluator now run in the native `sw` binary, with unchanged JSON fields and exit codes. Some error messages are worded differently. `reviewers.py` is removed. Breaking: reviewer `report` patterns are now JavaScript regular expressions.

### Changed

- **Breaking:** `pr.reviewers.<login>.report.sha_pattern` and `ignore` are read as JavaScript regular expressions in Unicode mode (Dart's `RegExp`), no longer Python ones. Simple patterns, the documented ones included, are unaffected. Rewrite any pattern that uses `(?P<name>...)`, `\A`, `\Z`, `(?i)`, `{,n}`, or an escape of a character that needs none (`\:`). The snapshot now refuses such a pattern, naming the reviewer and the key. The reviewer config moves to format 2, so a snapshot taken before the update reports `rules_mismatch` and watch takes a fresh one; restart any watch that was running during the update (#148).

- `pr-pair.sh identity`, `vcs`, `tier`, `context` and `policy` now run `sw pr <sub>`, the Dart port, with the same JSON fields, error codes and exit codes. Error messages keep their prefixes and may be worded differently. A missing or mismatched `sw` stops them with `sw missing or mismatched: rerun the install prompt` (#148).
- `sw vcs` reads settings in-process, and `sw pr snapshot` decides reviewer states through `sw pr reviewers`, so neither starts `pr-pair.sh` or `reviewers.py` for them (#148). Run `pr-pair.sh` from the code checkout: from inside a store checkout, the ported subcommands stop with `sw_missing`.

### Removed

- `skills/specwright-pr/scripts/reviewers.py`. Its evaluator is `sw pr reviewers` (#148).
