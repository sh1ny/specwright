# Spec Delta

## MODIFIED Requirements

### Requirement: A group is committed once at its boundary
With `commit_granularity: group`, `specwright-commit` SHALL leave a task group's work uncommitted until every agent and evidence task of the group is ticked and freshly verified, then SHALL commit it once, staging the group's files and `tasks.md` by name. The group's user tasks SHALL NOT hold the group commit back, and the group commit SHALL NOT tick or cover them. The message SHALL carry one `Specwright-Task: X.Y` trailer for each agent or evidence task of the group that the commit covers, in task order. User ticks follow **User ticks ride the next tasks.md commit**.

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

#### Scenario: Group with a user task
- **WHEN** group 3 has 3.1, 3.2 `[user]` and 3.3, and 3.1 and 3.3 are ticked and verified while 3.2 is not ticked
- **THEN** the group 3 commit is made with trailers `Specwright-Task: 3.1` and `3.3` only, and 3.2 stays unticked

### Requirement: End-of-apply check uses task evidence
When every agent and evidence task is ticked, `specwright-commit` SHALL require each ticked task to have exactly one covering commit, no cross-group trailer, no entry in `evidence_missing`, and a clean tree apart from pre-existing files. It SHALL then report `<N> tasks, <M> task-work commits, tree clean`, and, when user tasks are unticked, `waiting on the user: <ids>`. Unticked user tasks SHALL NOT stop the hand-off to the pre-ship review and the PR. Any task with no evidence, or covered twice, or listed in `evidence_missing`, SHALL stop the hand-off and be listed.

#### Scenario: Group mode complete
- **WHEN** five ticked tasks are covered by two group commits and the tree is clean
- **THEN** the report reads `5 tasks, 2 task-work commits, tree clean` and the hand-off continues

#### Scenario: Lost coverage
- **WHEN** task 2.2 is ticked but no commit names it in its subject or a trailer
- **THEN** there is no hand-off to archive or PR, and the report lists 2.2 as uncovered

#### Scenario: User task still open
- **WHEN** every agent task is ticked and covered, the tree is clean, and user task 4.3 is unticked
- **THEN** the report adds `waiting on the user: 4.3` and the hand-off to the pre-ship review and the PR continues

### Requirement: An interrupted group resumes without loss
When apply in group mode starts and exactly one group has ticked agent or evidence tasks with no evidence, `specwright-commit` SHALL treat them as that group's pending work: it SHALL re-run their verification, finish the group's remaining tasks and make one group commit covering all its uncovered tasks. Ticked agent or evidence tasks with no evidence in more than one group SHALL make no commit, and SHALL be listed for the user. A ticked, uncovered user task SHALL NOT make its group pending: it SHALL be listed apart, as an uncommitted user tick, and committed by the rule **User ticks ride the next tasks.md commit**. A tick SHALL never be removed.

#### Scenario: Resume in a fresh session
- **WHEN** tasks 1.1 and 1.2 are ticked with their work uncommitted, 1.3 is not ticked, and apply restarts
- **THEN** 1.1 and 1.2 are verified again, 1.3 is done, and one `group 1` commit carries trailers 1.1, 1.2 and 1.3

#### Scenario: Group already partly committed
- **WHEN** group 1 has an earlier commit covering 1.1 and apply in group mode finishes 1.2 and 1.3
- **THEN** the new group 1 commit carries trailers 1.2 and 1.3 only, and no task is covered twice

#### Scenario: Two groups pending
- **WHEN** ticks in groups 1 and 2 have no evidence when apply restarts
- **THEN** no commit is made, both groups and their tasks are listed, and no tick is removed

#### Scenario: Interrupted group plus a user tick
- **WHEN** agent task 1.1 is ticked and uncommitted, the user has ticked 2.1 `[user]`, and apply restarts
- **THEN** only group 1 is pending, 2.1 is listed as an uncommitted user tick, and the group 1 commit carries `Specwright-Task: 1.1` and `Specwright-User-Task: 2.1`

#### Scenario: All-user group
- **WHEN** group 5 holds only `[user]` tasks and the user ticks 5.1 with no agent work pending
- **THEN** group 5 is never listed as pending and 5.1 is committed as `... record user checks 5.1`

## ADDED Requirements

### Requirement: User ticks ride the next tasks.md commit
A ticked user task SHALL count as committed when a commit on the change branch carries a `Specwright-User-Task` trailer exactly naming it. Every commit that stages `tasks.md` SHALL carry one for each user task it ticks that no earlier commit covers; it is never a cross-group trailer. With no agent work pending, the agent SHALL commit `tasks.md` alone as `<type>(<change-name>): record user checks <ids>`. Otherwise the tick SHALL wait for the commit that covers the pending agent ticks.

#### Scenario: User tick with nothing pending
- **WHEN** every agent task is committed and the user ticks 3.2 `[user]`
- **THEN** one commit `<type>(<change-name>): record user checks 3.2` stages only `tasks.md`, its diff ticks only 3.2, and it carries `Specwright-User-Task: 3.2`

#### Scenario: Two user ticks at once
- **WHEN** the user ticks 3.2 and 4.3, both `[user]`, with nothing else pending
- **THEN** one commit `... record user checks 3.2, 4.3` carries `Specwright-User-Task: 3.2` and `Specwright-User-Task: 4.3`, and its `tasks.md` diff ticks exactly those two

#### Scenario: User tick while a group is pending
- **WHEN** agent tasks 1.1 and 1.2 are ticked and uncommitted and the user ticks 2.1 `[user]`
- **THEN** no commit is made for 2.1 alone; the group 1 commit stages `tasks.md` with all three ticks and carries `Specwright-Task: 1.1`, `Specwright-Task: 1.2` and `Specwright-User-Task: 2.1`, and none of them is reported cross-group

#### Scenario: Trailer for an agent task
- **WHEN** a commit carries `Specwright-User-Task: 1.1` and 1.1 is an agent task
- **THEN** the check does not count it as coverage of 1.1
