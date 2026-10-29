## MODIFIED Requirements

### Requirement: Task subjects fit 72 characters
`specwright-commit` SHALL build each task subject as `<type>(<change-name>): task X.Y <task text>`, and each group subject as `<type>(<change-name>): group N <group heading text>`, and measure it mechanically before committing, counting every character of the task or heading text, backticks included. When the subject is longer than 72 characters, it SHALL cut the text at the last word boundary that keeps the whole subject within 72. A subject that already fits SHALL be used unchanged.

#### Scenario: Long task text with backticks
- **WHEN** task 1.1 of `add-greeting` reads ``Add `greet(name)` with tests test_greet_named and test_greet_empty; ...``
- **THEN** the commit subject is at most 72 characters, starts with `feat(add-greeting): task 1.1 Add`, and ends at a whole word of the task text

#### Scenario: Subject exactly at the limit
- **WHEN** the full subject is exactly 72 characters
- **THEN** the subject is committed unchanged

#### Scenario: Store-backed task pair
- **WHEN** a store-backed task gets a code commit and a store commit
- **THEN** both commits carry the identical fitted subject

#### Scenario: Long group heading
- **WHEN** group 2 of `add-greeting` is headed `## 2. Documentation of greet and farewell for the README and the user guide pages`
- **THEN** the group commit subject is at most 72 characters, starts with `feat(add-greeting): group 2 Documentation`, and ends at a whole word of the heading

### Requirement: Unfittable subject stops the commit
When not even the first word of the task text fits after the `<type>(<change-name>): task X.Y ` prefix, or of the group heading after the `<type>(<change-name>): group N ` prefix, within 72 characters, `specwright-commit` SHALL make no commit for that task or group and SHALL report the task or group, the subject and the limit.

#### Scenario: Prefix plus first word too long
- **WHEN** the change name is so long that the prefix and the task text's first word exceed 72 characters
- **THEN** no commit is made for the task, the task's files stay uncommitted, and the report names the task and the 72-character limit

#### Scenario: Group prefix plus first word too long
- **WHEN** the change name is so long that the `group 1 ` prefix and the heading's first word exceed 72 characters
- **THEN** no commit is made for group 1, its files and ticks stay uncommitted, and the report names group 1 and the 72-character limit

## ADDED Requirements

### Requirement: Commit granularity is a project setting
`specwright-commit` SHALL read `commit_granularity` from `openspec/specwright.yaml` once at the start of each apply run. `task`, or no setting, SHALL keep one commit per task, unchanged. `group` SHALL commit once per task group. Any other value SHALL stop apply before any commit and name the value and the two allowed ones.

#### Scenario: Setting unset
- **WHEN** `openspec/specwright.yaml` has no `commit_granularity` and apply finishes tasks 1.1, 1.2 and 2.1
- **THEN** the branch has one commit per task with subjects `<type>(<change-name>): task 1.1 ...`, `task 1.2 ...` and `task 2.1 ...`, and no commit carries a `Specwright-Task:` trailer

#### Scenario: Unknown value
- **WHEN** `commit_granularity` is `groups`
- **THEN** apply makes no commit and reports `groups` together with `task` and `group`

### Requirement: A group is committed once at its boundary
With `commit_granularity: group`, `specwright-commit` SHALL leave a task group's work uncommitted until every task of the group is ticked and freshly verified, then SHALL commit it once, staging the group's files and `tasks.md` by name. The message SHALL carry one `Specwright-Task: X.Y` trailer for each task of the group that the commit covers, in task order.

#### Scenario: Two groups
- **WHEN** apply in group mode finishes groups `1.1`-`1.3` and `2.1`-`2.2`
- **THEN** the branch has exactly two task-work commits, `group 1 ...` with trailers `Specwright-Task: 1.1`, `1.2` and `1.3`, then `group 2 ...` with trailers `2.1` and `2.2`, and every task is ticked

#### Scenario: Shared file within a group
- **WHEN** tasks 1.1 and 1.3 both change `greet.py`
- **THEN** `greet.py` appears in the group 1 commit only, and no commit holds part of group 1's work

#### Scenario: Unowned edits present
- **WHEN** `scratch-notes.txt` was untracked before apply started
- **THEN** no group commit contains it and it is still untracked after apply

#### Scenario: Interrupted before the group is complete
- **WHEN** task 2.1 is ticked and 2.2 is not, and the run stops
- **THEN** no commit holds 2.1's work or tick

### Requirement: One group is pending at a time
In group mode, a complete group SHALL be committed, both halves when store-backed, before any task of another group is ticked, parallel dispatch included.

#### Scenario: Groups run in parallel
- **WHEN** groups 1 and 2 touch disjoint files and are dispatched in parallel
- **THEN** no task of group 2 is ticked until the group 1 commit exists, and each group still gets exactly one commit

#### Scenario: Group 1 commit fails
- **WHEN** group 1 is complete, its commit fails, and group 2's work has finished in parallel
- **THEN** no task of group 2 is ticked and the report names the failed group 1 commit

### Requirement: Group membership is exact
A task SHALL belong to group N when its ID has exactly N before the dot. A group commit SHALL carry trailers only for tasks of its own group. Its subject text SHALL be the heading `## N. <text>` of `tasks.md`. A group with no such heading SHALL stop the commit and be reported.

#### Scenario: Group 1 and group 10
- **WHEN** `tasks.md` has groups 1 (`1.1`, `1.2`) and 10 (`10.1`), and group 1 is complete
- **THEN** the group 1 commit carries trailers `1.1` and `1.2` only and holds none of task 10.1's tick or files

#### Scenario: Missing heading
- **WHEN** tasks `3.1` and `3.2` follow a heading `## Cleanup` with no number
- **THEN** no commit is made for group 3 and the report names group 3 and the missing `## 3.` heading

### Requirement: Task evidence is a subject or a trailer
A task SHALL count as committed in a repository when a commit on the change branch since main has a subject starting with `<type>(<change-name>): task X.Y ` or a `Specwright-Task` trailer whose value is exactly `X.Y`. A read-only check SHALL report, for each task in `tasks.md`, its group, its tick, and the commits covering it. It SHALL also report every task covered by more than one commit in that repository, and every trailer naming a task outside its commit's group.

#### Scenario: Exact match
- **WHEN** a commit carries `Specwright-Task: 1.10` and `tasks.md` has tasks 1.1 and 1.10
- **THEN** the check reports 1.10 covered and 1.1 not covered by that commit

#### Scenario: Task ID inside other text
- **WHEN** a group 2 commit's subject is `fix(add-greeting): group 2 Fix task 1.1 regressions`, or a task 2.1 subject reads `fix(add-greeting): task 2.1 Revert task 1.1 output`
- **THEN** neither commit counts as coverage of task 1.1

#### Scenario: Task covered twice
- **WHEN** task 1.2 has a per-task commit and is also named by a group 1 trailer
- **THEN** the check reports 1.2 as covered twice, naming both commits

#### Scenario: Trailer outside its group
- **WHEN** a commit with subject `... group 1 ...` carries `Specwright-Task: 10.1`
- **THEN** the check reports 10.1 as a cross-group trailer on that commit

### Requirement: An interrupted group resumes without loss
When apply in group mode starts and exactly one group has ticked tasks with no evidence, `specwright-commit` SHALL treat them as that group's pending work: it SHALL re-run their verification, finish the group's remaining tasks and make one group commit covering all its uncovered tasks. Ticked tasks with no evidence in more than one group SHALL make no commit, and SHALL be listed for the user. A tick SHALL never be removed.

#### Scenario: Resume in a fresh session
- **WHEN** tasks 1.1 and 1.2 are ticked with their work uncommitted, 1.3 is not ticked, and apply restarts
- **THEN** 1.1 and 1.2 are verified again, 1.3 is done, and one `group 1` commit carries trailers 1.1, 1.2 and 1.3

#### Scenario: Group already partly committed
- **WHEN** group 1 has an earlier commit covering 1.1 and apply in group mode finishes 1.2 and 1.3
- **THEN** the new group 1 commit carries trailers 1.2 and 1.3 only, and no task is covered twice

#### Scenario: Two groups pending
- **WHEN** ticks in groups 1 and 2 have no evidence when apply restarts
- **THEN** no commit is made, both groups and their tasks are listed, and no tick is removed

### Requirement: A resumed red step is re-verified by its test
On resume, a ticked task whose verification is a test seen failing before the implementation (a red step) SHALL count as re-verified when the named test exists and now passes with the group's implementation. The group commit body SHALL say that the original red output is unavailable for that task. The task SHALL stay ticked.

#### Scenario: Red step ticked before the interruption
- **WHEN** group 1 is pending with 1.1 (write `test_greet_named`, confirm it fails) and 1.2 (implement `greet`) ticked, and apply restarts
- **THEN** `test_greet_named` is run and passes, 1.1 stays ticked, and the group 1 commit body says 1.1's red output is unavailable

#### Scenario: Named test missing
- **WHEN** the pending group's ticked red step names `test_greet_named` and no such test exists
- **THEN** no group commit is made and the report names 1.1 and the missing test

### Requirement: Pending ticks wait for their group commit
In group mode, a tick of a task with no evidence SHALL reach Git only in that task's group commit (store-backed: the store half). The planning and amendment commits SHALL NOT stage a `tasks.md` whose diff ticks such a task; that `tasks.md` waits for the group commit, and an untracked `tasks.md` that already ticks a task SHALL stop apply before any commit.

#### Scenario: Resume with a pending group and a planning edit
- **WHEN** group 1 is pending (1.1 and 1.2 ticked, uncommitted), `design.md` has an uncommitted edit, and apply restarts
- **THEN** the planning commit holds `design.md` and no tick, and the group 1 commit's `tasks.md` diff ticks exactly 1.1, 1.2 and 1.3

#### Scenario: First planning commit with ticks
- **WHEN** `tasks.md` is untracked and already ticks 1.1 when apply starts in group mode
- **THEN** no commit is made and the report names the ticked tasks

### Requirement: Grouping never rewrites history
`specwright-commit` SHALL NOT amend, squash, rebase or regroup an existing commit to form a group commit, published or not. A group commit SHALL cover only the group's tasks that have no evidence yet, so tasks already committed keep their commits. When a group mixes per-task and group commits, the report SHALL say so once, naming the group.

#### Scenario: Switching to group mode mid-change
- **WHEN** task 1.1 was committed as `task 1.1 ...`, `commit_granularity` is then set to `group`, and apply finishes 1.2, 1.3, 2.1 and 2.2
- **THEN** the `task 1.1` commit keeps its SHA, a `group 1` commit carries trailers 1.2 and 1.3 only, a `group 2` commit carries 2.1 and 2.2, and the report says group 1 mixes both forms

#### Scenario: PR feedback after group commits
- **WHEN** a PR fix round follows two pushed group commits
- **THEN** the fix is a new commit and both group commits keep their SHAs

### Requirement: End-of-apply check uses task evidence
When every task is ticked, `specwright-commit` SHALL require each ticked task to have exactly one covering commit, no cross-group trailer, and a clean tree apart from pre-existing files. It SHALL then report `<N> tasks, <M> task-work commits, tree clean`. Any task with no evidence, or covered twice, SHALL stop the hand-off and be listed.

#### Scenario: Group mode complete
- **WHEN** five ticked tasks are covered by two group commits and the tree is clean
- **THEN** the report reads `5 tasks, 2 task-work commits, tree clean` and the hand-off continues

#### Scenario: Lost coverage
- **WHEN** task 2.2 is ticked but no commit names it in its subject or a trailer
- **THEN** there is no hand-off to archive or PR, and the report lists 2.2 as uncovered
