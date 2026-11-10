# Proposal

## Why

The Dart CLI reproduces Python by hand: a SHA-256, a JSON reader and writer that follow CPython, four argument parsers, `os.path`, and a scanner for `gh` page output. That code exists to match a language `sw` is replacing, and `sw` and its skills ship together at one exact version, so nothing outside this repository depends on those forms.

This change serves M8, Complete the native CLI migration (#148). It advances the exit criterion that PR, review, release and update operations keep their JSON, exit-code and workflow contracts on the three CI platforms, by replacing custom code under outcome tests. It has no user-verified exit criterion. It lands directly after `native-cli-pr-pair-flow` and before `native-cli-internal-calls`, so later ports build on the libraries.

## What Changes

- `crypto` replaces the hand-written SHA-256 in `settings/reviewer_config.dart`. Reviewer-config bytes and digests stay as they are.
- `dart:convert` behind a small wrapper replaces `settings/pyjson.dart` and most of `vcs/document.dart`. Documents become compact JSON ending in one LF on every OS, with U+2028 and U+2029 left raw. **BREAKING** for anyone comparing `sw` stdout as text; parsed fields do not change.
- JSON input that Python accepted but JSON does not allow (`NaN`, `Infinity`, `-Infinity`) is refused with the existing unreadable-input stops. A JSON file over 32 MiB gets the same stop; direct file reads had no size limit before, and this replaces the 2,000-level nesting limit as their protection.
- **BREAKING:** an integer setting beyond 64 bits yields a `bad_setting` problem and a default in the rules layer: context and workflow callers stop with exit 2; policy main stops and policy head lists the invalid key while using the default, because `JsonEncoder` cannot write one. A `task-cover` group number beyond 64 bits is not a task.
- The existing `args` dependency replaces `parsePairArgs` (`pr/pair.dart`), `_parseArgs` (`pr/reviewers.dart`), `parseVcsArguments`'s loop (`vcs/args.dart`) and `_parseOptions` (`commands/finish.dart`). `--opt=value` becomes accepted everywhere. Python-style option prefixes (`--mat`) are refused. `interface` stays 1.
- `gh api --paginate --slurp` replaces the page scanner in `pr/workflow.dart` `list`. **BREAKING:** the `gh` floor rises from 2.40 to 2.48, in the install check, the prerequisite text and the fence message.
- `path` replaces `PyPath` in `commit/task_cover.dart` and the relpath helpers in `vcs/walk.dart`.
- Extend the shipped third-party notice for every runtime dependency, transitive ones included; preserve its existing install/update delivery.
- The merged feedback and workflow readers join the bounded JSON wrapper. Feedback records retain ownership, locks, recovery and legacy interoperability. Workflow round counters become ordinary integers within 64 bits; oversized feedback-round trailers stop with an unknown-read error rather than rounding or disappearing.
- ADR 0033 is the architecture record. `shellQuote`, `quoteBatchLine` and the process-tree, job-object and FFI code stay custom, with no replacement planned.

### Tests that retire

- `cli/test/settings/pyjson_test.dart` goes with `settings/pyjson.dart`. CPython's refusal positions, BigInt digits and the 2,000-level limit are not product guarantees.
- In `cli/test/vcs/document_test.dart`: the separator, compact-flag, U+2028/U+2029, Python float-repr, non-finite-number, BigInt and platform-line-ending cases.
- The private `PyPath` behaviour goes with the class; the `relpathText` group in `cli/test/vcs/raw_path_test.dart` narrows to the outcomes in the next list.

### Tests that move from exact stdout to parsed values or outcomes

- `evals/pr-pair/test_parity.py`: `assertParity` (line 101), the comparisons at lines 536 and 1084, and `ReviewersParity.pair` (line 969) compare the parsed JSON value instead of stdout bytes. The digest mask moves from bytes to the parsed field. Cases where the oracle accepted `NaN` or an abbreviated option become listed, asserted differences.
- `evals/finish`, `evals/vcs` and the `task-cover` tests in `evals/git-workflow`: any comparison of stdout bytes with a frozen script or fixed text compares the parsed value.
- `cli/test/vcs/document_test.dart`: the surviving cases assert the decoded value and the non-UTF-8 name bytes.
- `cli/test/vcs/args_test.dart`, `cli/test/pr/*` and `cli/test/commit/task_cover_test.dart`: usage cases assert the stop code and exit status, not parser wording.
- `cli/test/vcs/raw_path_test.dart`: `relpathText` cases assert the relative path produced for each OS style.
- `evals/git-workflow/test_instructions.py` lines 614, 625, 628 and 640 assert `gh` 2.48.
- `evals/fakes/gh.py` emits one array of pages for `--slurp`, and `evals/pr-pair/test_fake_gh.py` covers it. `--slurp` is already an accepted flag there (line 898) but does not nest pages.
- `cli/test/settings/yaml_test.dart` is untouched: the strict reader stays until `native-cli-yaml-settings`.

### Skills and scripts that change

- `skills/specwright-pr/SKILL.md` line 10 and the `pr-pair.sh` prerequisite comment state `gh` 2.48.
- `README.md` (prerequisites, install Step 1, the `PR workflow not ready` line) and `CONTRIBUTING.md` state `gh` 2.48.
- No skill or script reads `sw` documents as text. The in-binary snapshot regex readers (C12) and the branch guards `sw finish undo-archive-plan` prints for jj and GitButler (C13) are explicit temporary gaps until `native-cli-internal-calls`; tests pin the compact form they read.
- `openspec/strategy.md:13` and `openspec/architecture.md:150` raise the current gh prerequisite to 2.48; accepted historical ADRs remain unchanged.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `native-cli`: document form, option parsing, JSON input refusals, and the shipped dependency contract.
- `pr-script-runtime`: `gh` 2.48 prerequisite, paginated list reads, and the ported subcommands' parity moving to parsed values.
- `vcs-backends`: `sw vcs` documents keep their parsed values and name bytes instead of matching `vcs.sh` byte for byte.
- `task-commits`: `sw commit task-cover` documents are compared by parsed value.
- `change-finish`: `sw finish undo-archive-plan` documents are compared by parsed value.

## Impact

Touches `cli/lib/src/settings/`, `cli/lib/src/vcs/{document,args,walk}.dart`, `cli/lib/src/pr/{pair,reviewers,policy,workflow}.dart`, `cli/lib/src/commands/finish.dart`, `cli/lib/src/commit/task_cover.dart`, `cli/lib/src/fence/fence.dart`, `cli/pubspec.yaml` and `pubspec.lock`, the existing third-party notice, the merged feedback record/pass and workflow JSON readers, the evals listed above, the prerequisite docs and `evals/suites.json` for any new tracked file. ADR 0033 is already accepted and indexed; its file stays unchanged. Direct dependencies gain `crypto` and `path`. Existing feedback records, reviewer-config files and their digests stay readable.

Refreshed on 2026-11-10 against merged main `3fc5454` (pair-flow, PR #218, version 0.30.0); see design.md for the merged reader inventory and remaining experiments.

## Decision Making

DECISION_MAKING: important
- **Source:** setting

### S1: Adopt crypto, path, args and dart:convert now

- **Choice:** Replace the listed custom code with these libraries.
- **Rejected:** Keep the two-package limit of ADR 0027, or adopt `yaml` here; `yaml` waits for its own experiment.
- **Reversal cost:** low
- **Important:** yes, binds future changes.
- **Chosen by:** user, "Approved: crypto and path now."

### S2: Preserve workflow guarantees, not Python bytes

- **Choice:** Preserve safety, identity, ownership, recovery, fail-closed behaviour and user outcomes; change producers with their consuming tests.
- **Rejected:** Byte-for-byte parity with Python output and error text.
- **Reversal cost:** medium
- **Important:** yes, binds future changes.
- **Chosen by:** user, "not byte-for-byte Python output, parser quirks or historical error text".

### S3: Raise the gh floor to 2.48

- **Choice:** Use `--slurp`, and raise the floor everywhere it is stated.
- **Rejected:** Keep the scanner so `gh` 2.40 keeps working.
- **Reversal cost:** low
- **Important:** yes, changes what users see.
- **Chosen by:** user, "raising the gh floor from 2.40 (fence/fence.dart) to 2.48".

### S4: Keep shell quoting and process control custom

- **Choice:** `shellQuote`, `quoteBatchLine`, process-tree, job-object and FFI code are out of scope.
- **Rejected:** Planning replacements for them.
- **Reversal cost:** low
- **Important:** no.
- **Chosen by:** user, "Keep custom, do not plan replacements".

### S5: Write plain compact JSON with LF

- **Choice:** The wrapper uses `JsonEncoder` with its default compact form, one LF on every OS, and U+2028/U+2029 raw.
- **Rejected:** Keep Python's spacing and CRLF on Windows, which keeps most of the custom writer.
- **Reversal cost:** low
- **Important:** yes, changes what users see.
- **Chosen by:** user, chose "Plain JsonEncoder + LF".

### S6: Keep interface 1

- **Choice:** Dropped accidental forms (option prefixes) do not raise `interface`, because no shipped caller uses them and `sw` is pinned to its skills by exact version. A test proves no shipped caller uses one.
- **Rejected:** Raise `interface` to 2.
- **Reversal cost:** low
- **Important:** yes, binds future changes.
- **Chosen by:** user, chose "Keep interface 1".

### S7: Plan now, refresh after pair-flow

- **Choice:** Write this plan from `main` and the committed pair-flow branch, then refresh it once `native-cli-pr-pair-flow` merges.
- **Rejected:** Wait for that merge before planning.
- **Reversal cost:** low
- **Important:** yes, binds future changes.
- **Chosen by:** user, "Note in the design that it must be refreshed once native-cli-pr-pair-flow merges".

The owner approved the round 3 refinements on 2026-11-10: caller-specific oversized-setting handling, a surrogate-string writer only if needed to preserve bytes/digests, and snapshot regex readers retained as C12 until internal-calls.

## Release Notes

0.31.0 replaces custom Python-matching code in `sw` with focused libraries. PR workflow outcomes do not change, but `gh` 2.48 is now required and `sw` documents are compact JSON ending in LF on every OS.

### Changed

- `sw` now requires `gh` 2.48 or later; install reports `PR workflow not ready: gh 2.48+` for older versions (#148).
- `sw` documents are compact JSON with one LF on every OS. Fields, error codes and exit statuses do not change (#148).
- `sw` commands accept `--option=value`. Abbreviated options such as `--mat` are refused (#148).
- An integer setting beyond 64 bits, such as a reviewer `timeout`, is now a `bad_setting` problem instead of being carried as an exact big number (#148).
- JSON files `sw` reads are limited to 32 MiB (#148).

### Removed

- The hand-written SHA-256, JSON reader and writer, argument parsers and `os.path` port. Non-standard JSON numbers (`NaN`, `Infinity`) in reviewer files are refused instead of read (#148).
