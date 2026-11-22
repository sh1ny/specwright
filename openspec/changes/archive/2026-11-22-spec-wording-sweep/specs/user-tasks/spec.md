# Spec Delta

## MODIFIED Requirements

### Requirement: A task can be marked as the user's
A tracked task whose text starts with `[user]` right after its id (`- [ ] X.Y [user] <text>`) SHALL be a user task. A tracked task whose text starts with `[evidence]` SHALL be an evidence task. Every other tracked task SHALL be an agent task. `sw commit task-cover` SHALL report each task's kind as `user`, `evidence` or `agent`, and SHALL list the ids of unticked user tasks, in file order, as `waiting_on_user`. A marker anywhere else in the text, or in another case, SHALL NOT change the kind.

#### Scenario: Kinds are reported
- **WHEN** `tasks.md` holds `- [ ] 2.1 Add the parser`, `- [ ] 2.2 [evidence] Save the run log → evidence/run.log` and `- [ ] 2.3 [user] Play the first level`
- **THEN** `sw commit task-cover` reports 2.1 as `agent`, 2.2 as `evidence` and 2.3 as `user`, and `waiting_on_user` is `["2.3"]`

#### Scenario: Marker not at the start of the text
- **WHEN** a task reads `- [ ] 2.4 Document the [user] marker`, or `- [ ] 2.5 [User] Check the menu`
- **THEN** both are reported as `agent` tasks and neither is in `waiting_on_user`

#### Scenario: Ticked user task
- **WHEN** the user has ticked `- [x] 2.3 [user] Play the first level`
- **THEN** `waiting_on_user` is empty

### Requirement: An evidence task is ticked only with its evidence
An evidence task SHALL name one file as a path starting `evidence/` under the change, and SHALL be ticked only once that file is not empty and committed with the task. `sw commit task-cover` SHALL list a ticked evidence task as `evidence_missing` when it names no such path or the file is not a regular, non-empty blob in the index of the repository holding `tasks.md`, whatever `--repo` names (with `--rev`, that revision's tree); it SHALL NOT read the file through the working tree.

#### Scenario: Evidence present
- **WHEN** task 2.2 names `evidence/run.log`, the file holds the run's output and is committed with the task
- **THEN** 2.2 is ticked and `evidence_missing` is empty

#### Scenario: Evidence file missing
- **WHEN** task 2.2 is ticked and `evidence/run.log` does not exist
- **THEN** `sw commit task-cover` lists 2.2 in `evidence_missing` and there is no hand-off to the pre-ship review or the PR

#### Scenario: Evidence only in the working tree
- **WHEN** task 2.2 is ticked and `evidence/run.log` exists in the working tree but is neither staged nor committed
- **THEN** `sw commit task-cover` lists 2.2 in `evidence_missing`

#### Scenario: Store-backed evidence
- **WHEN** `tasks.md` and `evidence/run.log` are committed in the store only, a group commit in each repo covers 2.2, and `sw commit task-cover` runs with the store's `tasks.md` against the store and against the code repo
- **THEN** both calls report no `uncovered`, `duplicates`, `cross_group` or `evidence_missing` entry, so the end-of-apply check passes; once `evidence/run.log` is committed empty, or removed, in the store, both calls list 2.2 in `evidence_missing` and the check stops

#### Scenario: No evidence path named
- **WHEN** a ticked task reads `- [x] 2.6 [evidence] Capture the frame times`
- **THEN** `sw commit task-cover` lists 2.6 in `evidence_missing`
