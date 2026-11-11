# Review

## Metadata

- **Round:** 3
- **Prior round:** Round 2, Codex: APPROVE_WITH_CHANGES; R2-M1–M4 applied. Subsequent amendments replaced D10’s disproved environment-decoding assumption with strict POSIX `getenv` reads and shortened five requirements, voiding that verdict.
- **Reviewer:** Codex CLI
- **Reviewed:** Proposal, design, tasks and scenario mappings, all six delta specs, corresponding main-spec requirements, architecture, ADRs 0014, 0022, 0027, 0028, 0029, 0031 and 0033, and supporting source. Also reviewed `listing_assumption_test.dart`. ADR 0034 is untracked and was excluded under the requested access restriction. No tests were run.
- **Re-check:** Round 3 Required Change 1 only: checked the uncommitted planning amendments against `cli/lib/src/finish/walk.dart` and `cli/lib/src/finish/undo_plan.dart`. Fully applied; no new contradiction identified within this scope. No tests were run.

This verdict covers only the contents reviewed. Editing proposal, specs or design afterward (other than applying Required Changes, or an edit confined to the proposal's `## Release Notes` section) voids it.

## Findings

### Critical (blocking)

None.

### Moderate

**R3-M1 — The shared walker drops finish entries that the existing contract preserves.**

D6 and task 3.6 replace the finish walk with a shared walker that skips all links. The existing finish walker includes symlinks to files: it classifies entries using a directory check that follows links, then places non-directory entries in `files` ([walk.dart](/F:/Dev/specwright/cli/lib/src/finish/walk.dart:139), [grouping](/F:/Dev/specwright/cli/lib/src/finish/walk.dart:75)).

This affects the undo plan, beyond its permitted ordering change. An archived `specs/foo/spec.md` symlink to a readable file currently identifies capability `foo`; capability discovery explicitly checks `w.files.contains('spec.md')` ([undo_plan.dart](/F:/Dev/specwright/cli/lib/src/finish/undo_plan.dart:532)). Skipping that link omits the corresponding synced main spec from restoration or removal. Linked files also disappear from uncommitted `carried_edits`.

The finish requirement preserves existing values and scripts apart from its stated differences; neither the design nor test map accounts for this additional behavior change.

### Suggestions

None.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. Amend D6 and task 3.6 to preserve finish’s existing link classification: list linked files, list linked directories without descending into them, and retain VCS’s separate link-skipping policy. Add mapped regression tests for a linked capability `spec.md` participating in main-spec restoration and a linked file participating in uncommitted `carried_edits`. Carry the distinction into the walker’s documented contract.

CHANGES_APPLIED: yes

## Rebuttals

1. **Applied.** [D6]( /F:/Dev/specwright/openspec/changes/native-cli-launcher/design.md:79) now specifies “listing a link to a directory under `dirs` without descending and any other link under `files`,” while VCS “skips links and `.git` and `.jj`.” [C3](/F:/Dev/specwright/openspec/changes/native-cli-launcher/design.md:168) carries this caller-specific policy into the planned `walkTree` doc comment. [Task 3.1](/F:/Dev/specwright/openspec/changes/native-cli-launcher/tasks.md:133) tests both policies, and [task 3.6](/F:/Dev/specwright/openspec/changes/native-cli-launcher/tasks.md:138) explicitly selects the finish policy. The new [scenario](/F:/Dev/specwright/openspec/changes/native-cli-launcher/specs/change-finish/spec.md:59) requires capability `foo` to be “restored or removed as for a regular `spec.md`,” linked `notes.md` to appear in `carried_edits`, and directory links to remain listed without descent. [Task 3.5](/F:/Dev/specwright/openspec/changes/native-cli-launcher/tasks.md:137) specifies the corresponding POSIX regressions, with a concrete [test-map row](/F:/Dev/specwright/openspec/changes/native-cli-launcher/tasks.md:19). These amendments preserve the source walker’s classification and both consumer paths without introducing a new contradiction.