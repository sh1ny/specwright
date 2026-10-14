# Review

## Metadata

- **Round:** 2
- **Prior round:** 1 - APPROVE_WITH_CHANGES (C1 store-backed code repo never done, M1 squash-merged eval missing, M2 persistent insteadOf, M3 unassertable stale-main THEN); all four applied and re-checked (CHANGES_APPLIED: yes). That verdict was voided by commit 539d820, which reworded the change-finish requirement "A merged PR whose branch is gone is done after the backstop" to fit the 500-character limit.
- **Reviewer:** fresh-context subagent (specwright-reviewer, Claude Code)
- **Reviewed:** proposal.md, design.md, specs/change-finish/spec.md, specs/github-identity/spec.md, specs/preship-review/spec.md, the round 1 review.md, commit 539d820 (`git show`); main spec openspec/specs/change-finish/spec.md (fact A on main, the requirement being modified); ADRs 0002, 0003, 0007, 0008 as cited in design.md; skills/specwright-finish/SKILL.md (Run login, Resume, the three facts, the reused-name rule, the resume table); `openspec validate fix-m2-gaps --strict` (valid; the requirement body is now 487 characters).

<!-- This verdict covers only the contents reviewed. Editing proposal, specs or design afterward (other than applying Required Changes) voids it. -->

## Findings

### Critical (blocking)

None.

### Moderate

**M1. The rewording dropped the only link between the archive re-read and "done", so the requirement body now contradicts its own "Refreshed main has no archive" scenario.**
The main spec's body says finish "SHALL run only the issues-left-open backstop for that PR and SHALL count the repo as done". Because this is a MODIFIED requirement, the delta body replaces it in full at archive. The round 1 delta wording still tied the outcome to the re-read: "read the archive fact again on the refreshed `main` before it counts the repo done". Commit 539d820 removed that clause. The body no longer says "done" anywhere, and its last sentence has no condition: "Finish SHALL then run only the issues-left-open backstop for that PR". Read literally, a planning repo whose refreshed `main` has no archive still runs the backstop. The only thing that says otherwise is "an archive seen only on a stale `main` SHALL NOT count", and it does not say what happens next. This conflicts with:
- the scenario "Refreshed main has no archive" (THEN "finish runs no backstop ... does not report `Nothing to finish`"),
- D1 ("A absent → report ..., run no backstop, and leave the repo not done"),
- the implemented row in `skills/specwright-finish/SKILL.md` ("A absent → ... no backstop; repo not done").

After archive, the main spec's normative text would require a backstop on a merged PR that never brought the archive to `main`. "Count the repo done" would then survive only in the requirement's title. A later verify, or a change that edits this skill against the main spec, could follow the body and break the scenario. The commit message calls the edit "wording only". The other meaning claims hold: the refresh, the stale-main rule, the store-backed code repo exemption and the no-branch-deletion rule ("SHALL delete no branch in that repo" is equivalent to the old `git branch -d` clause). Dropping "the one repo when repo-local" from the parenthetical is harmless, because the main spec already uses "the planning repo" for both layouts (fact A requirement) and the "Cleanup already ran" scenario pins the repo-local case. The lost conditional is the one change in meaning. Required Change 1 gives a 473-character wording that restores it.

### Suggestions

None new. Round 1 suggestions S1-S3 were moved into tasks.md and are outside this run.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. **(M1)** In specs/change-finish/spec.md, replace the body of "A merged PR whose branch is gone is done after the backstop" with wording that makes the backstop and "done" depend on the re-read, stays under 500 characters, and keeps every scenario unchanged. For example (473 characters):
   "In `finish: pr`, when a repo's change PR is MERGED and its change branch is gone locally, finish SHALL refresh that repo's `main` (only with a clean tree) and SHALL delete no branch there. The planning repo SHALL count only an archive on the refreshed `main`; with none, finish SHALL run no backstop and SHALL NOT count it done. Otherwise, and for a store-backed code repo, finish SHALL run only the issues-left-open backstop for that PR; the repo is done when it succeeds."
   Re-run `openspec validate fix-m2-gaps --strict` afterwards.

<!-- yes (applied, and re-checked by the reviewer - only the reviewer sets it) | no (outstanding) | n/a (any other verdict) -->
CHANGES_APPLIED: yes

## Rebuttals

<!-- Author: fixed (cite) or rebutted (reason) per finding. A Critical/Moderate rebuttal counts only once marked "accepted by reviewer". -->
- **M1 - fixed (accepted by reviewer, re-check run).** specs/change-finish/spec.md: the requirement body is now the Required Change's wording verbatim (473 characters); `openspec validate fix-m2-gaps --strict` passes.
