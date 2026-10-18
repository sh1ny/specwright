# Spec Delta

## ADDED Requirements

### Requirement: Store staging belongs to one checkout
An update SHALL stage the store schema in a directory of the store whose name is unique to its code checkout. Stage, discard, finish and rollback SHALL create, read and remove only that checkout's directory. Another checkout's staging directory SHALL count as an untracked path that makes the store busy, never as this update's own staging. A swap refused before its first rename SHALL remove its own staging and journal, so a refused checkout never keeps the store busy.

#### Scenario: Two checkouts stage against one store
- **WHEN** checkouts A and B of projects using one store both run `stage` for 0.6.0
- **THEN** the store holds two separate staging directories, one per checkout, and each journal names only its own

#### Scenario: Discard after a refused swap keeps the other checkout's rollback copy
- **WHEN** A swapped the store schema and kept its old schema in its own staging directory, and B's swap is refused
- **THEN** B's refused swap removes only B's own staging directory and journal, A's staging directory and its old schema are unchanged, and a later `recover --rollback` in A restores the old schema

#### Scenario: Another checkout's staging makes the store busy
- **WHEN** B's swap finds the store on its main with A's staging directory untracked
- **THEN** B's swap is refused before any rename, the message names A's staging directory as the reason the store is busy and says to rerun the update in that checkout, and B's own staging and journal are removed

#### Scenario: Both checkouts staged before either swapped
- **WHEN** checkouts A and B both ran `stage` against one store, and A's swap runs first
- **THEN** A's swap is refused naming B's staging directory and removes A's own staging and journal, B's swap then runs, and a rerun of A's update after B finished is not refused because of staging

#### Scenario: Interrupted update from an earlier version
- **WHEN** a journal written before this change names the shared staging directory `openspec/.specwright-update-schemas`
- **THEN** `recover` discards, resumes or rolls back using the path in that journal
