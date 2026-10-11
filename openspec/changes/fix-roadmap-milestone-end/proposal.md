# Proposal

## Why

Milestone **M2 - Ship flow**, change 1 of 5 (release 0.1.12). Three gaps in roadmap planning and the store branch gates each force a manual rescue or a confused stop:

- **#51** At a milestone end `specwright-roadmap` has no path from **next** to **close**. `next` covers only "a planned change is left" and "none is left but a criterion fails"; when every Now change is done it either does nothing useful or invents a gap-closing change. `close` then re-splits a Next milestone the author already agreed and split, and `init` gives a project no way to record such an agreement. A downstream project hit this at its M1 end and had to ask what each offered choice would do.
- **#60** A failing `post-checkout` hook makes `git checkout -b` exit non-zero after it has created and switched to the branch. The store-backed roadmap gate and the `specwright-branch` store gate treat that as "nothing was branched", so a repo is left on an empty branch and a retry is refused.
- **#66** Four `planning-stores` requirements are longer than 500 characters, so `openspec validate --specs --strict` fails on the main specs.

This change advances the M2 exit criteria "every issue in the changes below is closed by a merged PR, and each code fix has a regression test in `evals/pr-pair` or `evals/git-workflow`", "`evals/pr-pair` and `evals/git-workflow` pass", and "each change ships as its own release" (0.1.12).

## What Changes

- **#51 next**: when every change of the Now milestone is done, `next` reports a milestone end, offers **close** and starts nothing. It never starts a change of a milestone that is not Now; **close** promotes it first. The gap-closing path stays, but only for an exit criterion that **close** found failing or that the user reports failing.
- **#51 close**: when Next already holds a split the author agreed, promoting it keeps that split. Close re-checks it against what the milestone taught and proposes amendments to the user; it never re-plans silently. A Next without an agreed split is split as before.
- **#51 init, close and the roadmap template**: only the current milestone is split, unless the author explicitly agrees a Next split; the milestone then carries a `Split agreed: <date>` line, so close can tell an agreed split from a draft. Close drops the line when it promotes the milestone.
- **#51 status**: when every Now change is done, status says `milestone end: run close` as what `next` would do.
- **#51 finish**: `specwright-finish` offers **close** (not next) once the merged change was the Now milestone's last one, otherwise **next**.
- **#60**: both store gates (`specwright-roadmap` Committing project files step 3, `specwright-branch` Store-backed changes step 3) replace their per-case rollbacks with one rule: after any `git checkout -b` error, check each repo; wherever the new branch exists, switch back to main, judged by the current branch rather than the exit status, and delete it; then release the lock and stop with the error.
- **#66**: the four over-long `planning-stores` requirements are split. Each keeps its header, its first behaviour's wording and all its scenarios, and each split-off sentence becomes its own requirement with new happy and failure scenarios. No behaviour changes.
- Regression coverage in `evals/git-workflow`: agent evals for the milestone end, the kept split and the hook rollback in both gates; text checks for each rule; a check that the main specs pass strict validation once every active change is applied.
- Everything moves to 0.1.12.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `project-planning`: **Gap-closing roadmap edit is committed on the new change's branch** (triggered only by a criterion close found failing or the user reports failing); new requirements for the milestone end (next, status and finish offer close), the kept agreed Next split, and recording that agreement at init.
- `planning-stores`: new requirement that a store gate whose `git checkout -b` errors leaves no new branch in either repo; **Commands run where they resolve correctly**, **Watch covers the expected PR set**, **Feedback rounds span the PR pair** and **An interrupted feedback pass is completed first** are shortened, and their split-off parts become four new requirements with the same behaviour.

## Impact

- Skills: `specwright-roadmap` SKILL.md (next, close, init roadmap rules, status, Committing project files step 3) and `references/roadmap.md`; `specwright-branch` SKILL.md (Store-backed changes step 3); `specwright-finish` SKILL.md (the roadmap offer). `metadata.version` moves to 0.1.12 in all six skills.
- Specs: `openspec/specs/project-planning/spec.md` and `openspec/specs/planning-stores/spec.md` through this change's deltas. The archived deltas of `fix-workflow-recovery` and `fix-pr-evidence-freshness` stay as they were merged (design D4).
- Tests: `evals/git-workflow` (`evals.json`, `fixtures.py`, `grade.py` where a case needs a new check, `test_instructions.py`, and a new strict-validation test). The existing `eval-roadmap-next-gap` case now reaches the gap path through **close**, as the new next rule requires.
- Docs: README badge, `VERSION`, and the README roadmap line if its wording of next and close changes.
- Version: 0.1.12, a fix release, as the roadmap plans. The milestone-end and kept-split rules define cases the wording left undefined. The `Split agreed:` line is an optional roadmap line: roadmaps without it keep working, and close asks about an unmarked list. No setting changes.
- Out of scope: rolling back a failed `git checkout -b` in the single-repo `specwright-branch` gate (a retry there stops on the existing branch and offers to resume it, which is the right recovery); #50's separate `next` step 3 problem is already closed by the gap-closing requirement.
