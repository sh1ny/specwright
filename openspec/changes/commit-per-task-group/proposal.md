# Proposal

## Why

`specwright-commit` makes one commit per numbered task, so a change with six task groups and twenty tasks fills its PR with twenty commits, though each group is the coherent unit of work (#20). The 2026-10-09 decision on #20 settles the approach: commit once at the group boundary, with one `Specwright-Task:` trailer per task as evidence, and no squash, since a squash rewrites history on Git and works differently on each backend. This change serves M5 (Commits and VCS backends). It lands before `add-jj-backend` and `add-gitbutler-backend`, which reuse its evidence format. It advances the exit criterion "with `commit_granularity: group`, an apply of groups `1.1`-`1.3` and `2.1`-`2.2` makes exactly two task-work commits whose `Specwright-Task:` trailers cover all five tasks; group 1 never takes a group 10 task; a resume after an interrupted group, and after either half of a code/store pair, makes no duplicate and loses no tick. With it unset, per-task commits are unchanged." It ships as release 0.10.0, its own release per the M5 exit criteria.

## What Changes

- **New setting** `commit_granularity: task | group` in `openspec/specwright.yaml`. The default is `task`, and with the setting unset nothing changes. Any other value stops apply before its first commit. Apply reads the setting once per run.
- **Group commits:** in `group` mode, the work of task group N stays uncommitted until every task of the group is ticked and freshly verified. Then it is committed once, files by name, with the subject `<type>(<change-name>): group N <group heading>` (fitted to 72 characters like task subjects). The message carries one `Specwright-Task: N.M` trailer for each task the commit covers. A group is the set of tasks whose ID has exactly N before the dot, so group 1 never takes task 10.1. Store-backed: a code commit then a store commit with the same message, or the store commit alone with `Code-Changes: none` when the group changed no code.
- **Task evidence by trailer or subject:** a task is covered by a commit whose subject starts with `<type>(<change-name>): task X.Y ` (the per-task form, unchanged) or whose `Specwright-Task` trailer value is exactly `X.Y`. A new read-only script, `task-cover.sh`, reads the ticks in `tasks.md` and the trailers and subjects of a commit range, and prints one JSON document: each task's group, tick and covering commits, plus duplicates and cross-group trailers. Reconcile and the end-of-apply check use it in both modes, so matching never depends on the agent spotting `1.1` against `1.10`.
- **Recovery:**
  - On resume, the one group with ticked but uncovered tasks is pending group work, not a gap. Its ticked tasks are verified again, and the group is finished and committed once.
  - Store-backed: a group whose code commit landed and whose store commit failed gets its store commit with the same message. A group with no code commit is never assumed to have changed no code.
  - Ticked, uncovered tasks in more than one group, or a store diff that ticks tasks outside the pending group, make no commit and are put to the user.
- **No rewriting:** group mode never amends, squashes or regroups existing commits, published or not. A group commit covers only the tasks of its group that no commit covers yet, so a project that switches to `group` mid-change keeps its earlier per-task commits, and the report names the group that mixes both forms. Planning, amendment, pre-ship, PR-feedback and archive commits are unchanged.
- **Docs:** the template `specwright.yaml`, the README (commit table, config), `CONTRIBUTING.md` and the architecture's settings and formats entry describe both modes. A new ADR records the evidence format and the no-rewrite rule.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `task-commits`: adds commit granularity, group commits with `Specwright-Task:` trailers, task evidence in either form, group recovery and the end-of-apply evidence check. Subject fitting also covers group subjects.
- `planning-stores`: task commit pairs, reconcile, the tick-without-code-commit rule and the completion check cover group pairs and trailer evidence.

## Impact

- Skills: `skills/specwright-commit/SKILL.md` (sections 2, Reconcile and 3), `skills/specwright-commit/scripts/fit-subject.sh` (group subjects), new `skills/specwright-commit/scripts/task-cover.sh`.
- Schema: the apply instruction in `schemas/specwright/schema.yaml` ("commit task by task" becomes "commit per the configured granularity").
- Templates and docs: `templates/openspec/specwright.yaml`, `README.md`, `CONTRIBUTING.md`, `openspec/architecture.md`, a new ADR in `docs/adr/`.
- Evals: `evals/git-workflow` (fixtures with groups 1.1-1.3 and 2.1-2.2, and groups 1 and 10; new apply cases for group mode, resume and both store halves; grader checks and their tests; fit-subject and task-cover tests; instruction tests), and `evals/suites.json` rules for the new files.
- Projects that leave `commit_granularity` unset see no change. The trailer is a format that later runs parse, so this is a workflow change: version 0.10.0 (minor).

## Release Notes

0.10.0 lets a project commit once per task group instead of once per task. With `commit_granularity: group`, each task group becomes one commit whose `Specwright-Task:` trailers name every task it covers, and an interrupted group resumes without duplicate commits or lost ticks, store-backed changes included. The default stays one commit per task.

### Added
- `commit_granularity: task | group` in `openspec/specwright.yaml`: `group` makes one commit per task group, with a `Specwright-Task: X.Y` trailer for each task it covers (#20).
- `task-cover.sh` reports which commits cover each ticked task, by subject or trailer, so resume and the end-of-apply check match task IDs exactly (#20).

### Changed
- The end-of-apply check and store-backed reconcile accept either per-task subjects or `Specwright-Task:` trailers as evidence, and report a task covered twice (#20).
