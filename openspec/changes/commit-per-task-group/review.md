# Review

## Metadata

- **Round:** 1
- **Prior round:** none (this is the reviewer re-check of round 1's Required Changes 1-4)
- **Reviewer:** fresh-context subagent (Claude Code)
- **Reviewed:** openspec/changes/commit-per-task-group/proposal.md, design.md, specs/task-commits/spec.md, specs/planning-stores/spec.md; openspec/specs/task-commits/spec.md and openspec/specs/planning-stores/spec.md (main); skills/specwright-commit/SKILL.md; skills/specwright-commit/scripts/fit-subject.sh; schemas/specwright/schema.yaml (apply instruction, lines 490-530); schemas/specwright/templates/tasks.md; skills/specwright-pr/scripts/pr-pair.sh (header and Python finder); skills/specwright-release/scripts/release.sh (header); evals/git-workflow/grade.py (subject and report checks); openspec/roadmap.md (M5 Now); docs/adr/0002, 0003, 0005, 0006, 0007, 0010, 0011. Project skills named for the reviewed work: none.

<!-- This verdict covers only the contents reviewed. Editing proposal, specs or design afterward (other than applying Required Changes, or an edit confined to the proposal's `## Release Notes` section) voids it. -->

## Findings

### Critical (blocking)

None.

### Moderate

**M1. On resume, the apply-start planning commit sweeps the pending group's ticks into `add planning artifacts`.**
`SKILL.md:22` commits any uncommitted planning files before the first task with `git add -- <P>/changes/<change-name>/`, which stages the whole change directory, `tasks.md` included. In task mode that rarely matters: store-backed, Reconcile (`SKILL.md:21`) resolves or stops on every ticked, uncommitted task first, and repo-local, the tick-to-commit window is one shell call. In group mode, D4 deliberately leaves a pending group's ticks uncommitted across sessions. So every resume of a pending group finds `tasks.md` modified and commits those ticks under `add planning artifacts`. Store-backed, that breaks the delta's own rule in "Task commit pairs are reconciled before new work": "A store commit SHALL never include a tick its message does not name". It also means the later group commit's `tasks.md` diff does not tick the tasks its trailers name. Repo-local, it puts group 2's tick into a commit before the group is complete, against the spirit of "Interrupted before the group is complete". Flow & State Gaps does not cover this ordering.

**M2. Re-verifying a ticked red-confirmation task on resume is not defined, and the standard group shape triggers it.**
The tasks template (`schemas/specwright/templates/tasks.md:13-14`) makes `N.1` "Write failing test ... verify it fails" and `N.2` the implementation. D4 and the scenario "Resume in a fresh session" say the pending group's ticked tasks "are verified again". After `N.2` is ticked, `N.1`'s verification (the test fails) cannot be reproduced, because the test is now green. Today's exception (`SKILL.md:33`: accept the implementer report's exact command and failure output, and say so in the commit body) depends on a report that a fresh session no longer has. As written, a resumed group whose red step is ticked cannot meet its own re-verification rule. The agent would either stop with no defined next step, or claim a verification it cannot run.

**M3. "Subject contains `task X.Y `" combined with the new "exactly one covering commit" turns false matches into hard stops, in task mode too.**
The evidence rule matches the substring anywhere in the subject. Under the old check (`SKILL.md:44`, "needs a commit"), an extra match was harmless. The new end-of-apply requirement makes "covered twice" a stop. Concrete cases:
- A group heading `## 2. Fix task 1.1 regressions` gives the subject `feat(x): group 2 Fix task 1.1 regressions`, which covers 1.1 a second time.
- A task-mode subject `task 2.1 Revert task 1.1 helper` stops a task-mode apply that passes today, which contradicts "with it unset, nothing changes".

`fit-subject.sh:33` already defines the anchored form (`^[^ ]+: task [0-9]+\.[0-9]+ `). The evidence rule, `task-cover.sh` and the grader should use the prefix position, not a substring.

**M4. Parallel group dispatch makes "two pending groups" a routine state, and the design does not forbid it.**
The apply instruction (`schema.yaml`, "Run groups in parallel only when they touch disjoint files") lets two groups be open at once. D4 and "An interrupted group resumes without loss" stop and ask the user whenever more than one group has ticked, uncovered tasks. Nothing in D1/D4 says a group must be committed before any task of another group is ticked. Without that rule, a parallel run interrupted between verifying one group and committing it routinely ends in a user question instead of the automatic resume the exit criterion describes. Store-backed, a Reconcile pass mid-run could also see two groups' ticks and hit "cannot isolate the tick".

### Suggestions

**S1. The report wording changes in task mode with no mention.** Both deltas change the end-of-apply report from `<N> tasks, <M> task commits, tree clean` (current main spec and `SKILL.md:44`) to `task-work commits` in both modes. The proposal says that with the setting unset nothing changes. The existing grader's `completion_by_repo` (`evals/git-workflow/grade.py:156`) looks for the substring `task commit`, which `task-work commits` does not contain. Either keep `task commits` or name the rename in the proposal and design, and list the grader update.

**S2. D6's switch back to `task` mode conflicts with task-mode Reconcile.** D6 says a pending group's ticks "get per-task commits under today's split rule" when the mode goes back to `task`. Store-backed task mode treats each ticked, uncovered task with no code commit as a gap to ask about (`SKILL.md:40`), and stops when the diff ticks more than one gap (`SKILL.md:41`). The pending group is exactly that state. Either specify the switch-back path with a scenario, or state that it falls under the task-mode questions.

**S3. Keep the grader's matcher independent of `task-cover.sh`.** The ledger says the "grader reuses the same rule". If that means the grader calls `task-cover.sh`, or imports its code, a matching bug passes both the product and the eval that is meant to prove the exit criterion. An independent implementation in `grade.py`, with shared test vectors (1.1 against 1.10, group 1 against group 10, duplicates, cross-group trailers), keeps the eval a real check.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. (M1) In design.md (D4, and Flow & State Gaps) and `specs/task-commits/spec.md`, specify that in group mode the apply-start planning commit never stages the pending group's `tasks.md` ticks. For example, when `tasks.md` is already tracked, the planning commit leaves it out (or commits only non-tick edits), and the ticks reach Git only in the group commit or its store half. Add a scenario: resume with group 1 pending (1.1 and 1.2 ticked, uncommitted) and another uncommitted planning edit; THEN the planning commit's diff contains no tick, and the group 1 commit's `tasks.md` diff ticks exactly 1.1, 1.2 and 1.3 (store-backed: the store commit's diff).
2. (M2) In D4 and the requirement "An interrupted group resumes without loss", define re-verification for a ticked red-confirmation task on resume. For example: the named test exists and now passes with the group's implementation, the original red evidence is recorded as unavailable in the group commit body, and nothing is unticked. Add a scenario for a pending group whose `N.1` is a red step and `N.2` is ticked.
3. (M3) Change the subject form of task evidence, in D2, the requirement "Task evidence is a subject or a trailer", the planning-stores Reconcile and Completion requirements, and the proposal's "Task evidence" bullet, from "subject contains `task X.Y `" to "subject starts with `<type>(<scope>): task X.Y `" (the prefix `fit-subject.sh` already matches). Add a scenario where a group heading or a task text contains `task 1.1 ` and the check does not count it as coverage of 1.1.
4. (M4) In D1/D4 and the requirement "A group is committed once at its boundary", add the rule that in group mode the orchestrator commits a complete group (both halves when store-backed) before it ticks any task of another group, parallel dispatch included. Add a scenario: groups 1 and 2 run in parallel; THEN group 2's tasks are ticked only after group 1's commit exists.

<!-- yes (applied, and re-checked by the reviewer - only the reviewer sets it) | no (outstanding) | n/a (any other verdict) -->
CHANGES_APPLIED: yes

## Rebuttals

- **Required Change 1 (M1): fixed, accepted by reviewer.** A new requirement, "Pending ticks wait for their group commit" (`specs/task-commits/spec.md:132-141`), says a tick with no evidence reaches Git only in its group commit (store half when store-backed). Planning and amendment commits never stage a `tasks.md` whose diff ticks such a task. Two scenarios cover it: "Resume with a pending group and a planning edit" asserts the planning commit holds no tick and the group commit's `tasks.md` diff ticks exactly 1.1-1.3, and "First planning commit with ticks" stops on an untracked `tasks.md` that already has ticks. design.md Flow & State Gaps has the matching entry, "Pending ticks and the planning commit". Applied as required.
- **Required Change 2 (M2): fixed, accepted by reviewer.** D4 (design.md:50) and the new requirement "A resumed red step is re-verified by its test" (`specs/task-commits/spec.md:121-130`) count a ticked red step as re-verified when its named test exists and now passes. The group commit body says the original red output is unavailable, and the tick stays. Two scenarios cover it: "Red step ticked before the interruption" and "Named test missing", where a missing test means no commit and a report. Applied as required.
- **Required Change 3 (M3): fixed, accepted by reviewer.** Evidence is now "subject starts with `<type>(<change-name>): task X.Y `" in D2 (design.md:38, citing `fit-subject.sh:33`), in the task-commits requirement "Task evidence is a subject or a trailer" (`spec.md:88`), and in the planning-stores Reconcile requirement (`specs/planning-stores/spec.md:27`, scenario at `:35`) and Completion requirement (`:65`). The proposal's "Task evidence" bullet (`proposal.md:11`) says the same. The new scenario "Task ID inside other text" covers both the group-heading case and the task-text case. Applied as required. Matching the grader to this prefix is part of S3, which the coordinator says tasks.md will handle.
- **Required Change 4 (M4): fixed, accepted by reviewer.** D1 (design.md:32) commits a complete group, both halves when store-backed, before any task of another group is ticked. Parallel dispatch stays allowed, but ticks and commits go one group at a time. Flow & State Gaps "Concurrent writers" (design.md:163) points to D1. The new requirement "One group is pending at a time" (`specs/task-commits/spec.md:65-74`) has the scenarios "Groups run in parallel" and "Group 1 commit fails". Applied as required.
- **Suggestions (no rebuttal needed):** the coordinator reports that S1 (report wording) and S3 (independent grader matcher) will be handled in tasks.md. S2 (switching back to task mode in a store) is left to task-mode Reconcile, which asks. That outcome is safe: a pending group's ticks become questions, not silent commits.
