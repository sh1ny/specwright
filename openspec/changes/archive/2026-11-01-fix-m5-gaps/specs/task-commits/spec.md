# Spec Delta

## ADDED Requirements

### Requirement: A repeated task id stops the coverage check
`task-cover.sh` SHALL exit 2 with error `duplicate_task_ids` when two or more tracked lines of `tasks.md` (a checkbox line with any box content) carry the same task id. The message SHALL name every repeated id. It SHALL print no coverage data, so `specwright-commit` makes no commit and stops, showing the error.

#### Scenario: Ticked line followed by a draft line with the same id
- **WHEN** `tasks.md` holds `- [x] 1.1 add greet` and later `- [~] 1.1 draft`, and a commit `task 1.1: add greet` exists
- **THEN** `task-cover.sh` exits 2, its JSON has `ok: false`, `error: duplicate_task_ids` and a message naming `1.1`, and it reports no `uncovered` list

#### Scenario: Unique ids
- **WHEN** every tracked line of `tasks.md` has its own id
- **THEN** `task-cover.sh` reports coverage as before and exits 0

#### Scenario: Repeated id in an untracked line
- **WHEN** `1.1` appears on a tracked line and again in a plain bullet with no checkbox
- **THEN** the plain bullet is not a task, and `task-cover.sh` exits 0
