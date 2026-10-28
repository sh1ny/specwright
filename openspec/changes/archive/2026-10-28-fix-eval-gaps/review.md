# Review

## Metadata

- **Round:** 3 (re-check run)
- **Prior round:** Round 2 returned APPROVE_WITH_CHANGES with Required Changes 1-7 (C1, M1-M6) verified, CHANGES_APPLIED: yes, and two non-blocking stale-text notes (S1 Context example, S5 kept-log wording). Later author edits to D8, Risks, the eval-runner timing requirement and the proposal voided that verdict. The first run of round 3 returned APPROVE_WITH_CHANGES with one Moderate (M1: tasks.md still made a new before run) and two Suggestions.
- **Reviewer:** fresh-context subagent (Claude Code specwright-reviewer)
- **Reviewed:** The first run of round 3 read openspec/changes/fix-eval-gaps/proposal.md, design.md, specs/eval-grading/spec.md, specs/eval-runner/spec.md, review.md (round 2), tasks.md and openspec/roadmap.md. It checked them against git history (tags v0.8.0 = 6b4b8ee, v0.8.1 = 0b07689, v0.9.0 = 1ad19af), `git diff 6b4b8ee HEAD -- evals/`, the current per-suite `def test_` counts and the `evals/` directory list. This re-check run re-read tasks.md and the proposal's `## Release Notes` section from disk, and covers only M1, S1 and S2. Installed project skills named: none.

<!-- This verdict covers only the contents reviewed. Editing proposal, specs or design afterward (other than applying Required Changes, or an edit confined to the proposal's `## Release Notes` section) voids it. -->

## Findings

### Critical (blocking)

None.

### Moderate

**M1. tasks.md still made a new before measurement and treated #127 only as a reference, contradicting the edited D8 and the spec.** Status: **resolved.**
- Task group 1 is now "Baseline test IDs", with only 1.1. That task lists the test IDs with the `unittest` loader only and runs no tests. It states that "The before timing column is the #127 figures (design D8); no before run is made". Its verify step checks each suite's count against the #127 counts (pr-pair 559, update 95, review-routes 157, git-workflow 323, release 118, finish 41). Those match the figures in the request.
- The old 1.2 (the base timing run into `timings-before.md`) is gone, and no task refers to `timings-before.md` any more.
- 7.2 now writes `evals/timings.md` with the #127 figures as the before column, cited with the issue, 2026-10-26 and its test counts. The after column has its counts and the machine, OS, git and Python versions. 7.2 also keeps the ID comparison, where a missing ID blocks the change.
- 7.1's `TimingsRecord` now checks both test counts. This matches the spec's "Before and after recorded" scenario and D8.

### Suggestions

- **S1. The new `evals/runner/` suite has no before figure.** Status: **applied.** 7.2 adds a note in `evals/timings.md` that `runner` is new in this change and is left out of both totals. A small leftover with no effect: 7.3's label says "Run all six suites" but lists seven names, `runner` included. The command is right; only the word "six" is off.
- **S2. The Release Notes fetch item left out `--multiple`.** Status: **applied.** The #121 item now reads "no refspec, `--all`/`--multiple`, or a `src:dst` refspec". The edit is confined to `## Release Notes`, so it does not void the verdict.

### Checks of the round-3 edits (no finding; carried from the first run)

- **D8 and Risks: before = #127.** The history supports the claim. Since the M4 close, tests have been added and none have been sped up. Every current suite count is equal to or above its #127 count, so the comparison is stricter, not easier.
- **The "Suite wall times are recorded" spec requirement and its scenarios** match D8, and every outcome can be checked.
- **The roadmap exit criterion** is met. #127 is a Windows measurement of every suite under `evals/` today, taken before this change began.
- **The proposal's #121 and #127 bullets** match D2, D8 and the specs. The round-2 stale lines are fixed, and no earlier fix is broken.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. (M1) In `openspec/changes/fix-eval-gaps/tasks.md`, rewrite task 1.2 so that it records no new before run, and rewrite task 7.2 to write `evals/timings.md` with the #127 figures as the before column, keeping task 1.1's base test-ID listing and the 7.2 ID comparison. **Verified:** group 1 holds only the discovery-only 1.1, checked against the #127 counts. 7.2 uses #127 as the before column, with its date and counts, and keeps the ID comparison. 7.1 checks both counts.

CHANGES_APPLIED: yes

## Rebuttals
