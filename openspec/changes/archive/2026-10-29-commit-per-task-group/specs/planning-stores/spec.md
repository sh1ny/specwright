## MODIFIED Requirements

### Requirement: Planning commits go to the store
For a store-backed change, `specwright-commit` SHALL commit planning artifacts and drift amendments in the store, on the store's change branch, staging only the change's directory. Task code SHALL be committed in the code repo. It SHALL NOT stop because the planning root is in another repository.

#### Scenario: Planning artifacts committed before the first task
- **WHEN** apply starts on a store-backed change with uncommitted artifacts under `<store>/openspec/changes/<change-name>/`
- **THEN** the store has a commit `<type>(<change-name>): add planning artifacts` on its change branch containing only those paths, and the code repo has no planning commit

#### Scenario: Task commit for a store-backed change
- **WHEN** a task is ticked `[x]` in `<store>/openspec/changes/<change-name>/tasks.md` after code files changed
- **THEN** the code files are committed in the code repo as `<type>(<change-name>): task X.Y ...`, and the `tasks.md` update is committed in the store with the same subject

#### Scenario: Group commit for a store-backed change
- **WHEN** `commit_granularity` is `group` and every task of group 1 is ticked in the store's `tasks.md` after code files changed
- **THEN** the code files are committed in the code repo first, then `tasks.md` in the store, both with the identical message: subject `<type>(<change-name>): group 1 ...` and one `Specwright-Task:` trailer per covered task

#### Scenario: Group with no code
- **WHEN** `commit_granularity` is `group` and group 3 is complete but changed no code file
- **THEN** the store gets the group 3 commit with a `Code-Changes: none` line before the trailers, and the code repo gets no commit for group 3

#### Scenario: Store on the wrong branch
- **WHEN** a planning or task commit is due and the store's current branch is not `<prefix>/<change-name>`
- **THEN** Specwright makes no commit in either repo and stops, naming the store's current branch

### Requirement: Task commit pairs are reconciled before new work
Before ticking or committing a task or group, and before any planning commit, `specwright-commit` SHALL find every ticked task with no store evidence (a store commit with a subject starting `<type>(<change-name>): task X.Y ` or a `Specwright-Task: X.Y` trailer), except ticks this session made and is committing now. If they have a code commit, it SHALL commit their `tasks.md` change in the store with that commit's message. A store commit SHALL never include a tick its message does not name.

#### Scenario: Normal code task
- **WHEN** this session ticks task 1.2 after changing code files and commits it
- **THEN** the code commit and the store commit for 1.2 are made without asking whether 1.2 was a no-op

#### Scenario: Store commit failed, apply resumes
- **WHEN** task 1.1's code commit succeeded, its tick is uncommitted in the store after the store commit failed, and apply restarts
- **THEN** before task 1.2 is ticked, the store gets a commit whose subject starts with `<type>(<change-name>): task 1.1 ` and whose `tasks.md` diff ticks only 1.1

#### Scenario: Group store half failed, apply resumes
- **WHEN** in group mode the code commit for group 1 (trailers 1.1, 1.2, 1.3) succeeded, the store commit failed with those ticks uncommitted, and apply restarts
- **THEN** before any group 2 task is ticked, the store gets one commit with the code commit's subject and trailers whose `tasks.md` diff ticks exactly 1.1, 1.2 and 1.3, and the code repo gets no second group 1 commit

#### Scenario: Group code half interrupted, apply resumes
- **WHEN** in group mode tasks 1.1 to 1.3 are ticked in the store, group 1's code files are uncommitted in the code repo, neither repo has a group 1 commit, and apply restarts
- **THEN** 1.1 to 1.3 are verified again, the code repo gets one group 1 commit, then the store one with the same message, and no tick is lost

#### Scenario: Reconciliation cannot isolate the tick
- **WHEN** the uncommitted `tasks.md` ticks more than one task that lacks a store commit, and no single code commit's message names exactly those tasks
- **THEN** Specwright makes no commit, lists the tasks involved and asks the user how to record them

### Requirement: A tick without a code commit is confirmed
When reconciliation finds ticked tasks with no store evidence and no code commit, not ticked by the current session, Specwright SHALL NOT infer that they changed no code. In task mode it SHALL stop and ask whether the task was a code no-op before any commit or tick. In group mode it SHALL ask the same about the group when the code repo has no uncommitted change the group's tasks account for.

#### Scenario: Restart before a task's code commit
- **WHEN** task 1.3 was ticked, the session stopped before its code commit, and apply restarts in a fresh session
- **THEN** Specwright makes no commit until the user says whether 1.3 changed code; if it did, the code files are committed first and then the tick in the store

#### Scenario: No-op task's store commit failed
- **WHEN** a verification-only task 2.3 was ticked with no code commit, its store commit failed, and apply restarts in a fresh session
- **THEN** Specwright makes no commit and ticks nothing until the user confirms whether task 2.3 changed no code, then commits the tick in the store with the original subject and `Code-Changes: none`

#### Scenario: Group ticked, code tree clean
- **WHEN** in group mode every task of group 3 is ticked in the store, neither repo has a group 3 commit, the code tree is clean, and apply restarts
- **THEN** Specwright makes no commit until the user says whether group 3 changed code; on no, the store gets the group 3 commit with `Code-Changes: none`

### Requirement: Completion check covers both repos
For a store-backed change, the "every task is `[x]`" check SHALL require, for every ticked task, exactly one code-repo commit naming it or a store commit for it with `Code-Changes: none`, and exactly one store commit naming it, by a subject starting with `<type>(<change-name>): task X.Y ` or a `Specwright-Task: X.Y` trailer. It SHALL also require clean trees in both repos, apart from files that were already there before apply.

#### Scenario: All tasks committed in both repos
- **WHEN** every task is ticked and each has a matching commit in both repos and both trees are clean
- **THEN** Specwright reports `<N> tasks, <M> task-work commits, tree clean` separately for the code repo and the store

#### Scenario: Store has uncommitted tasks.md
- **WHEN** every task is ticked but the store still has an uncommitted `tasks.md` change
- **THEN** Specwright reconciles it as above, or reports the gap, and does not hand off to archive or PR until it is closed

#### Scenario: Group pair complete
- **WHEN** in group mode five ticked tasks are named by two code commits and two store commits with matching trailers, and both trees are clean
- **THEN** Specwright reports `code: 5 tasks, 2 task-work commits, tree clean` and `store: 5 tasks, 2 task-work commits, tree clean`
