# Spec Delta

## Purpose

Keeps the user's uncommitted work safe while `specwright-debug` tests a dirty tree: the work it sets aside can always be found and restored, even after an interrupted run.

## ADDED Requirements

### Requirement: A debug stash is named and reported
When `specwright-debug` stashes a dirty tree to test it, the stash message SHALL start with `specwright-debug: ` followed by the debug topic, and the run SHALL report the stash ref before testing. After testing, it SHALL restore that stash and confirm that the tree holds the files again before it reports.

#### Scenario: Dirty tree is tested
- **WHEN** a debug run on topic `flaky-login` finds modified and untracked files and decides to test without them
- **THEN** it runs `git stash push -u -m "specwright-debug: flaky-login"`, reports the ref (for example `stash@{0}`), and after testing restores that stash and reports the files restored

#### Scenario: Restore conflicts
- **WHEN** restoring the stash conflicts with a change the debug run made
- **THEN** the run stops, keeps the stash, reports its ref and the conflicting paths, and asks the user how to proceed

### Requirement: An interrupted debug stash is found on the next run
At the start of every run, before it inspects or changes the tree, `specwright-debug` SHALL list stashes whose message starts with `specwright-debug: `. For each one found, it SHALL report the ref and topic and offer to restore it, and it SHALL NOT drop one without the user's yes.

#### Scenario: Earlier run was interrupted
- **WHEN** a debug run starts and `git stash list` holds `stash@{1}: On main: specwright-debug: flaky-login`
- **THEN** the run reports `stash@{1}` and topic `flaky-login`, offers to restore it, and does not stash again until the user decides

#### Scenario: Stash ref moved since it was reported
- **WHEN** the run reported `stash@{0}` for `specwright-debug: flaky-login`, and the user then pushed another stash, so it is now `stash@{1}`
- **THEN** the restore looks the ref up again by its message, applies and drops `stash@{1}`, and leaves the user's new stash in place

#### Scenario: No leftover stash
- **WHEN** a debug run starts and no stash message starts with `specwright-debug: `
- **THEN** the run reports no leftover stash and continues

#### Scenario: Other stashes are left alone
- **WHEN** the stash list holds only `specwright-branch: pre-add-x` and a user stash
- **THEN** the debug run neither offers to restore them nor drops them
