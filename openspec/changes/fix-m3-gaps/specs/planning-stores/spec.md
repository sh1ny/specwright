# Spec Delta

## ADDED Requirements

### Requirement: Store staging belongs to one checkout
An update SHALL stage the store schema in a directory of the store whose name is unique to its code checkout. Stage, discard, finish and rollback SHALL create, read and remove only that checkout's directory. Another checkout's staging directory SHALL count as an untracked path that makes the store busy, never as this update's own staging.

#### Scenario: Two checkouts stage against one store
- **WHEN** checkouts A and B of projects using one store both run `stage` for 0.6.0
- **THEN** the store holds two separate staging directories, one per checkout, and each journal names only its own

#### Scenario: Discard after a refused swap keeps the other checkout's rollback copy
- **WHEN** A swapped the store schema and kept its old schema in its own staging directory, B's swap is refused, and B runs `recover`
- **THEN** B removes only its own staging directory, A's staging directory and its old schema are unchanged, and a later `recover --rollback` in A restores the old schema

#### Scenario: Another checkout's staging makes the store busy
- **WHEN** B's swap finds the store on its main with A's staging directory untracked
- **THEN** B's swap is refused before any rename, the message names A's staging directory as the reason the store is busy, and B's own staging remains for `recover`

#### Scenario: Interrupted update from an earlier version
- **WHEN** a journal written before this change names the shared staging directory `openspec/.specwright-update-schemas`
- **THEN** `recover` discards, resumes or rolls back using the path in that journal
