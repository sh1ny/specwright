# Review

## Metadata

- **Round:** 2
- **Prior round:** Round 1 APPROVE_WITH_CHANGES (M1-M4 required, applied and re-checked, CHANGES_APPLIED: yes). After that verdict, the planning-stores requirement "Task commit pairs are reconciled before new work" was reworded during apply to fit OpenSpec's 500-character limit, which voided the verdict. This file is the reviewer's re-check of round 2's Required Change 1.
- **Reviewer:** fresh-context subagent (Claude Code)
- **Reviewed:** openspec/changes/commit-per-task-group/proposal.md, design.md, review.md, tasks.md, specs/task-commits/spec.md, specs/planning-stores/spec.md (and `git diff HEAD` of the change directory: the only artifact change since round 1 is the one requirement paragraph, apart from review.md itself); main specs openspec/specs/task-commits/spec.md and openspec/specs/planning-stores/spec.md; skills/specwright-commit/SKILL.md; skills/specwright-commit/scripts/fit-subject.sh; docs/adr index (0002, 0003, 0006, 0007, 0010 as cited in design.md). `openspec validate commit-per-task-group --strict` passes. Project skills named for the reviewed work: none.

<!-- This verdict covers only the contents reviewed. Editing proposal, specs or design afterward (other than applying Required Changes, or an edit confined to the proposal's `## Release Notes` section) voids it. -->

## Findings

### Critical (blocking)

None.

### Moderate

**M1. The reworded exclusion drops "this session ticked", so a resumed session can exclude an earlier session's ticks from reconciliation.**
Before (round 1, HEAD): "... other than the tasks this session ticked and is committing now." After: "... other than the ticks it is committing now." The rest of the rewording keeps its meaning. "A store commit with a subject starting ... or a `Specwright-Task: X.Y` trailer" says the same as "whose subject starts ... or whose trailer is", and "that commit's message" still refers to the code commit. The dropped qualifier is different. It is the provenance guard, and it appears in the main spec (`openspec/specs/planning-stores/spec.md:99`, "the task this session ticked and is committing now") and in `SKILL.md:38` ("The task this session just ticked and is committing now is not a gap").

What goes wrong: the next requirement, "A tick without a code commit is confirmed", fires only "When reconciliation finds ticked tasks with no store evidence and no code commit, not ticked by the current session". With the new wording, a resumed session that plans to commit an earlier session's tick can call that tick one it "is committing now". Reconciliation then never finds the tick, and the confirm-before-commit rule never fires. Two concrete cases: task 1.3 in "Restart before a task's code commit", and group 3 in "Group ticked, code tree clean". In each, an earlier session ticked the tasks, and the resumed session is about to commit them. The scenarios still assert the question, so the evals would catch it. But the requirement text now allows what the scenarios forbid. Task 4.2 rewrites SKILL.md's Reconcile section from this text, so the weaker wording could reach the skill. Group mode does not need the broader exclusion. D4's pending group is handled by the confirm requirement's own group clause (ask only when no uncommitted code change accounts for the group), which runs either way.

A wording that keeps the qualifier and still validates is given below (494 characters).

### Suggestions

None new. Round 1's S1 and S3 are carried into tasks.md (4.2 keeps the report text; 5.1 updates `completion_by_repo` and keeps the grader's matcher independent of `task-cover.sh`). S2 is left to task-mode Reconcile, as round 1 recorded.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. (M1) In `openspec/changes/commit-per-task-group/specs/planning-stores/spec.md`, replace the requirement text of "Task commit pairs are reconciled before new work" with this paragraph (494 characters, under the 500 limit):

   Before ticking or committing a task or group, and before any planning commit, `specwright-commit` SHALL find every ticked task with no store evidence (a store commit with a subject starting `<type>(<change-name>): task X.Y ` or a `Specwright-Task: X.Y` trailer), except ticks this session made and is committing now. If they have a code commit, it SHALL commit their `tasks.md` change in the store with that commit's message. A store commit SHALL never include a tick its message does not name.

   Then re-run `openspec validate commit-per-task-group --strict`.

<!-- yes (applied, and re-checked by the reviewer - only the reviewer sets it) | no (outstanding) | n/a (any other verdict) -->
CHANGES_APPLIED: yes

## Rebuttals

- **Required Change 1 (M1): fixed, accepted by reviewer.** `git diff HEAD -- openspec/changes/commit-per-task-group/specs/` shows that the requirement paragraph of "Task commit pairs are reconciled before new work" (`specs/planning-stores/spec.md:27`) now matches the required text word for word. It restores the qualifier "except ticks this session made and is committing now", so reconciliation still finds an earlier session's ticks and "A tick without a code commit is confirmed" fires as its scenarios require. The evidence forms and the "never include a tick its message does not name" rule are unchanged. `openspec validate commit-per-task-group --strict` passes. No other artifact (proposal, design, tasks, task-commits spec) changed. Applied as required.
