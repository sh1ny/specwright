# Review

## Metadata

- **Round:** 4
- **Prior round:** 3. APPROVE_WITH_CHANGES with RC1: a symlinked version file was bumped but could not be read at the release commit. RC1 was applied with option (b), refusing symlinks in the working tree and at a commit. S1 (`tag_mismatch` wording) was applied, and S2 became moot. All of it was re-checked (`CHANGES_APPLIED: yes`). This round reviews the uncommitted amendments since commit 1515329, which answer two Codex findings on PR #92: the notes boundary in a clone without tags (P1), and two entries capturing in one file (P2).
- **Reviewer:** fresh-context subagent (specwright-reviewer, Claude Code harness)
- **Re-check run (S1-S2):** fresh-context subagent (specwright-reviewer, Claude Code harness), after the author's edits. I read the Rebuttals, design.md D4 (:55) and the `status` line (:108), and the release.sh `status` header comment. S1 is applied: D4 now states that publish fetches only main. S2 is applied: the header names the second `ls-remote --tags --refs` read and its exit 3, and the design `status` line names both `ls-remote` reads. These edits are wording only and change no reviewed decision, so the APPROVE verdict stands.
- **Reviewed:** the amendment diff (`git diff -- openspec skills evals`):
  - design.md: D4 and D7
  - specs/releases/spec.md: "Notes list the changes merged since the previous release" and its new scenario "Backfill in a clone without the tags"
  - release.sh: `Hit.span`, `cmd_bump`, `published_tags`, `status_doc`
  - evals/release/test_release.py: the two new tests

  Read alongside it:
  - release.sh: `previous_release` callers, `cmd_untagged`, `cmd_publish`, `refuse_older_untagged`, and the `status` header comment
  - skills/specwright-release/SKILL.md: publish step 1 (fetch main only, never `--tags`)
  - design.md: D6 step 1, the D8 `status` line, the Failure table
  - ADR 0010; ADR 0008, unchanged in substance by this diff, because the added read is the existing `ls-remote --tags --refs` and `status_doc` runs inside publish, which is fenced

  Run: the full `python -m unittest evals.release.test_release` passed, 69 tests, on git 2.55.0.windows.4.

<!-- This verdict covers only the contents reviewed. Editing proposal, specs or design afterward (other than applying Required Changes) voids it. -->

What holds:
- **P1 (notes boundary).** `status_doc` now passes `local_tags(st) | published_tags(st)` to `previous_release`. A clone that fetched only main therefore anchors a backfill on the highest lower tag on origin, as D4 and the spec now say.
  - The union keeps the earlier rule: a local-only tag whose push failed is still a boundary. `refuse_older_untagged` still blocks a higher publish until that tag is pushed, so the union opens no gap.
  - The per-run cache (`st._published`) means publish makes one `ls-remote --tags --refs`, plus the existing per-tag `ls-remote` in `remote_tag`. No tag is written between the two reads, so caching cannot go stale within a run.
  - `test_backfill_boundary_counts_origin_only_tags` pins the case: the previous version is 0.1.0 with basis `tag`, and the changes are add-b and add-c.
- **P2 (two captures in one file).** `cmd_bump` now gathers each entry's capture span per file and drops identical spans in a set. It applies the spans right to left, so earlier offsets stay valid, and writes once. It stops on overlap: with spans sorted descending, a span whose end passes the start of the next span stops the run. That also catches nested spans with the same start.
  - The stop is raised while the plan is built, before the first temp file, so "a failure before the first rename changes nothing" still holds.
  - Spans already at the target are skipped, which keeps D7's completion of an interrupted bump.
  - A partial overlap with a different captured value is stopped earlier by the agreement check (`version_files_disagree`). The eval asserts this with a snapshot.

## Findings

### Critical (blocking)

None.

### Moderate

None.

### Suggestions

- **S1. D4 wording.** D4's parenthetical "(publish no longer fetches tags, ...)" describes how the change evolved, not the design. After archive, "no longer" has nothing to refer to. State the fact instead: "publish fetches only main (specwright-release publish step 1), so a fresh clone may have no tags locally".
- **S2. `status` header comment.** The comment still names only one read-only `git ls-remote --tags origin` (for `tag_remote`). `status` now also runs `git ls-remote --tags --refs origin` through `published_tags`, and can exit 3 `remote_tags_unreadable` from it even when origin has the tag itself. Mention the second read there, and in D8's "`status` ... read-only apart from `ls-remote`" if the call count matters to a reader.

## Verdict

VERDICT: APPROVE

## Required Changes

None.

<!-- yes (applied, and re-checked by the reviewer - only the reviewer sets it) | no (outstanding) | n/a (any other verdict) -->
CHANGES_APPLIED: n/a

## Rebuttals

<!-- Author: fixed (cite) or rebutted (reason) per finding. A Critical/Moderate rebuttal counts only once marked "accepted by reviewer". -->

- **S1:** applied. D4 now says "publish fetches only main, so a fresh clone may hold none of the tags locally".
- **S2:** applied. The `status` header comment in release.sh names the second `ls-remote --tags --refs` and its exit 3; D9's `status` line says "two `ls-remote` reads of origin ... an unreadable origin is exit 3".
