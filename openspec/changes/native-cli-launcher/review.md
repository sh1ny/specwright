# Review

## Metadata

- **Round:** 2
- **Prior round:** Round 1, Codex: REVISE; Critical C1–C2 and Moderate M1–M5. The revised design addresses the original collision, working-directory, stdio and bound failures; consistency issues remain below.
- **Reviewer:** Codex CLI
- **Reviewed:** Proposal, design, all six capability deltas; corresponding main-spec requirements; architecture and ADRs 0014, 0022, 0027–0029, 0031 and 0033; tracked source cited by the design, including process launch, resolution, transport, bounds and helper code, kernel32/libc, fence code, VCS backends and walks, finish planning, commit tooling, PR context/state code, codec, shim and launch-site tests. Source paths were checked with `git ls-files`; no outside SDK source was opened.
- **Test map:** No tasks artifact exists yet; no scenario-to-user-task mapping was available to assess.

This verdict covers only the reviewed contents. Subsequent proposal, spec or design edits void it except for the Required Changes below or edits confined to the proposal’s Release Notes.

## Findings

### Critical (blocking)

None.

### Moderate

**R2-M1 — The carried batch constraint would undo the stdio fix.**

`design.md` D3 deliberately starts fenced batch commands in process through `runWithCommandLine`. C1 nevertheless requires every batch command to run through the helper, and D11 repeats the helper-only contract for ADR 0034. Following those instructions would restore the intermediary whose framed pipes caused M1. The existing helper protocol is documented in `cli/lib/src/process/bounded_run.dart:47-70`.

**R2-M2 — Walk diagnostics still have contradictory requirements.**

The `vcs-backends` requirement “sw vcs documents keep their values and refuse non-UTF-8 names” includes directory listings and requires each invalid byte as `\xHH`. Its directory-walk requirement instead requires U+FFFD, matching D6. The native-cli general non-UTF-8 document scenario also lacks that exception. A walk-found `a\xFF.txt` therefore has incompatible diagnostic assertions, despite the user’s explicit choice.

**R2-M3 — NUL refusal conflicts with the retained batch contract.**

D5 and the native-cli delta require every NUL argument to produce `bounded: unrepresentable argument: <cmd>`. The unchanged main requirement “Batch shims get escaped arguments or none” explicitly includes NUL and requires `bounded: unsafe batch argument: <cmd>` (`openspec/specs/native-cli/spec.md:173`). A NUL argument to `fake.cmd` cannot satisfy both. Validation precedence must be specified.

**R2-M4 — Regrouping the sorted walk loses global carried-edit order.**

D6 returns finish results regrouped as `(rel, dirs, files)`. The existing consumer emits each directory’s files together (`cli/lib/src/finish/undo_plan.dart:558-570`); the walker’s existing grouping is top-down (`cli/lib/src/finish/walk.dart:58-105`). Sorting before that regrouping does not ensure globally sorted `carried_edits`: root `b.md` can precede `a/z.md`, although UTF-8 order requires the reverse. The new scenario uses root files followed by `sub/c.md`, so it misses this case.

### Suggestions

None.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. Amend C1 and D11 to distinguish captured/bounded batch execution through the helper from standalone inherited-stdio fenced batch execution through in-process `runWithCommandLine`. Preserve the no-new-deadline rule and ADR destination.
2. Add an explicit directory-walk exception to the general VCS diagnostic requirement and native-cli document scenario: byte-bearing boundaries use `\xHH`; walk-found names use U+FFFD under D6.
3. Modify the main batch requirement through the native-cli delta to give NUL the D5 unrepresentable-input result. Retain the unsafe-batch result for the remaining batch-specific refusals, and add a batch-NUL scenario asserting the precedence.
4. Specify a final UTF-8-byte sort of `carried_edits` after regrouped traversal. Extend the finish sorting scenario with changed root `b.md` and nested `a/z.md`, asserting `a/z.md` before `b.md`.

CHANGES_APPLIED: yes

## Rebuttals

The original collision, cwd, batch-stdio and output-bound fixes are accepted at design level, subject to the planned CI proofs of A1/A3. The findings above are retained as the round-2 record. This re-check covered only Required Changes 1–4 in the current artifacts; all four are applied.

1. **Applied.** C1 and D11 now route captured or bounded batch calls through the helper and inherited-stdio fenced batch calls through in-process `runWithCommandLine`. Both preserve the no-new-deadline rule and ADR 0034 destination.
2. **Applied.** The general VCS requirement explicitly excepts walk-found names from `\xHH` diagnostics. The native-cli document scenario now covers byte-bearing argument/tool boundaries, with a separate directory-walk scenario requiring U+FFFD, consistent with D6.
3. **Applied.** The native-cli MODIFIED batch requirement gives NUL the `bounded: unrepresentable argument: <cmd>` result before batch validation, matching D5. Compared with the main requirement, the retained unsafe-batch scenario removes NUL while preserving the other refusals. The new batch-NUL scenario combines NUL with `%PATH%` and asserts unrepresentable-input precedence, exit 2 and no process start.
4. **Applied.** D6 explicitly requires sorting the finished `carried_edits` list by whole-path UTF-8 bytes after regrouped traversal. The finish requirement specifies whole-path ordering, and its scenario now includes changed root `b.md` and nested `a/z.md`, expecting `a.md`, `a/z.md`, `b.md`, `sub/c.md`. The cited walker and consumer are tracked source; their grouping behavior supports the need for this final sort.