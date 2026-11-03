# user-tasks Specification

## Purpose

Lets a change carry checks that only the user can make, and the evidence those checks need, so an agent never passes them on the user's behalf and the change cannot be archived or merged by an agent until the user has made them.

## Requirements

### Requirement: A task can be marked as the user's
A tracked task whose text starts with `[user]` right after its id (`- [ ] X.Y [user] <text>`) SHALL be a user task. A tracked task whose text starts with `[evidence]` SHALL be an evidence task. Every other tracked task SHALL be an agent task. `task-cover.sh` SHALL report each task's kind as `user`, `evidence` or `agent`, and SHALL list the ids of unticked user tasks, in file order, as `waiting_on_user`. A marker anywhere else in the text, or in another case, SHALL NOT change the kind.

#### Scenario: Kinds are reported
- **WHEN** `tasks.md` holds `- [ ] 2.1 Add the parser`, `- [ ] 2.2 [evidence] Save the run log → evidence/run.log` and `- [ ] 2.3 [user] Play the first level`
- **THEN** `task-cover.sh` reports 2.1 as `agent`, 2.2 as `evidence` and 2.3 as `user`, and `waiting_on_user` is `["2.3"]`

#### Scenario: Marker not at the start of the text
- **WHEN** a task reads `- [ ] 2.4 Document the [user] marker`, or `- [ ] 2.5 [User] Check the menu`
- **THEN** both are reported as `agent` tasks and neither is in `waiting_on_user`

#### Scenario: Ticked user task
- **WHEN** the user has ticked `- [x] 2.3 [user] Play the first level`
- **THEN** `waiting_on_user` is empty

### Requirement: An agent never ticks or delegates a user task
An agent SHALL NOT tick, implement or dispatch a user task, to an implementer or any other worker. Apply SHALL skip each user task, go on with the next agent task, and report the user tasks waiting on the user. An implementer handed a user task SHALL refuse it as BLOCKED. A user saying in chat that a check passed SHALL NOT make the agent tick it: the agent SHALL ask the user to tick it in `tasks.md`.

#### Scenario: Apply skips a user task
- **WHEN** group 3 has tasks 3.1, 3.2 `[user]` and 3.3, and apply runs
- **THEN** 3.1 and 3.3 are implemented and ticked, 3.2 stays unticked, no packet names 3.2, and the apply report lists 3.2 as waiting on the user

#### Scenario: Packet with a user task
- **WHEN** an implementer receives a packet that includes `3.2 [user] Play the first level`
- **THEN** it does no work for 3.2 and reports it BLOCKED as a user task

#### Scenario: User says it passed in chat
- **WHEN** the user writes "the playtest was fine" and 3.2 is unticked
- **THEN** the agent leaves 3.2 unticked and asks the user to tick 3.2 in `tasks.md`

### Requirement: An evidence task is ticked only with its evidence
An evidence task SHALL name one file as a path starting `evidence/` under the change, and SHALL be ticked only once that file is not empty and committed with the task. `task-cover.sh` SHALL list a ticked evidence task as `evidence_missing` when it names no such path or the file is not a regular, non-empty blob in the index of the repository holding `tasks.md`, whatever `--repo` names (with `--rev`, that revision's tree); it SHALL NOT read the file through the working tree.

#### Scenario: Evidence present
- **WHEN** task 2.2 names `evidence/run.log`, the file holds the run's output and is committed with the task
- **THEN** 2.2 is ticked and `evidence_missing` is empty

#### Scenario: Evidence file missing
- **WHEN** task 2.2 is ticked and `evidence/run.log` does not exist
- **THEN** `task-cover.sh` lists 2.2 in `evidence_missing` and there is no hand-off to the pre-ship review or the PR

#### Scenario: Evidence only in the working tree
- **WHEN** task 2.2 is ticked and `evidence/run.log` exists in the working tree but is neither staged nor committed
- **THEN** `task-cover.sh` lists 2.2 in `evidence_missing`

#### Scenario: Store-backed evidence
- **WHEN** `tasks.md` and `evidence/run.log` are committed in the store only, a group commit in each repo covers 2.2, and `task-cover.sh` runs with the store's `tasks.md` against the store and against the code repo
- **THEN** both calls report no `uncovered`, `duplicates`, `cross_group` or `evidence_missing` entry, so the end-of-apply check passes; once `evidence/run.log` is committed empty, or removed, in the store, both calls list 2.2 in `evidence_missing` and the check stops

#### Scenario: No evidence path named
- **WHEN** a ticked task reads `- [x] 2.6 [evidence] Capture the frame times`
- **THEN** `task-cover.sh` lists 2.6 in `evidence_missing`

### Requirement: The test map can point a scenario at a user task
A scenario that only a person can judge SHALL map in the test map to its user task id with state `user`. The row SHALL turn `green` only when that user task is ticked. A scenario that can be tested in code or by a mechanical check SHALL NOT be mapped to a user task.

#### Scenario: Person-judged scenario
- **WHEN** a scenario reads "the jump feels responsive" and task 4.3 is `[user] Play the jump section and judge the response`
- **THEN** its test map row names task 4.3 with state `user`, and the row reads `green` only after the user ticks 4.3

#### Scenario: Testable scenario mapped to a user task
- **WHEN** a scenario that a unit test can check maps to a user task
- **THEN** the design review reports the row as a finding

### Requirement: A user-verified exit criterion reaches the tasks
When the proposal names a user-verified exit criterion of its milestone, `tasks.md` SHALL hold a user task that checks it for this change, or the proposal SHALL say that the criterion can only be judged at the milestone close and why.

#### Scenario: Criterion carried to a task
- **WHEN** the proposal serves the user-verified criterion "the owner sees alerts in the console"
- **THEN** `tasks.md` holds a `[user]` task for the owner to see the alerts this change produces

#### Scenario: Criterion judged only at close
- **WHEN** the criterion spans three changes of the milestone
- **THEN** the proposal says it is judged at the milestone close and why, and no user task is required

### Requirement: Archive and verify wait for the user
A change with an unticked user task SHALL NOT be archived: the archive SHALL move nothing, sync no spec, and name the waiting tasks. Verify SHALL report each unticked user task as waiting on the user and SHALL NOT report the change verified. Finish SHALL check the archived `tasks.md` the same way before any commit, merge or push.

#### Scenario: Archive with a user task open
- **WHEN** the user runs archive and task 4.3 `[user]` is unticked
- **THEN** nothing moves, no spec is synced, and the agent names 4.3 as waiting on the user

#### Scenario: User ticks, then archive
- **WHEN** the user ticks 4.3 and the agent commits that tick
- **THEN** archive proceeds as for any change with every task done

#### Scenario: Archived with a user task open
- **WHEN** finish finds an archived `tasks.md` with an unticked user task
- **THEN** it makes no commit, merge or push and names the task

### Requirement: The agent merge waits for the user
Before it archives and again before every merge request, watch SHALL read the change's `tasks.md` as committed at the ready head of the planning repo, from the active change folder or else the archived one, never from the working tree. When it holds an unticked user task, watch SHALL report the PR ready and waiting on the user, naming the tasks, and SHALL NOT archive or merge. When that file cannot be read at the ready head, watch SHALL report the user-task check as unknown and SHALL NOT merge.

#### Scenario: Agent merge waits
- **WHEN** `pr.merge` is `agent`, the PR is ready, and task 4.3 `[user]` is unticked at the ready head
- **THEN** watch reports `ready, waiting on the user: 4.3`, makes no archive commit and sends no merge request

#### Scenario: Tick arrives while waiting
- **WHEN** the user ticks 4.3 after that report and the agent pushes the tick commit
- **THEN** watch judges the new head as for any pushed commit, and archives and merges only once it is ready again

#### Scenario: Archived task unticked by a later commit
- **WHEN** the change is archived on the branch and a later commit unticks archived task 4.3 `[user]`
- **THEN** watch reads the archived `tasks.md` at the ready head, reports 4.3 waiting on the user and sends no merge request

#### Scenario: Local copy differs from the ready head
- **WHEN** 4.3 is ticked in the local working tree but unticked at the ready head
- **THEN** watch reports 4.3 waiting on the user and sends no merge request

#### Scenario: tasks.md unreadable at the ready head
- **WHEN** neither the active nor the archived `tasks.md` exists at the ready head
- **THEN** watch reports the user-task check as unknown and sends no merge request
