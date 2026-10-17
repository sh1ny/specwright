# Spec Delta

## ADDED Requirements

### Requirement: A store records its schema version and owner
When the install/update swaps the schema into a store, it SHALL write `<root>/openspec/.specwright/STORE` in the same locked step: the new version and the owner, the code repo whose update wrote it (its `origin` repository, else its checkout path). A rollback SHALL restore the previous record. A store without a record SHALL be claimed by the first project that updates it, and the report SHALL say so. The install SHALL NOT commit the record.

#### Scenario: First update claims the store
- **WHEN** project A updates to 0.6.0 and the store has no `STORE` record
- **THEN** the store's `STORE` names version `0.6.0` and owner A, the file is left uncommitted in the store and listed in the report, and the report says A now owns the store's schema

#### Scenario: Two projects claim at once
- **WHEN** projects A and B both run an update of a store with no `STORE` record, and A's swap takes the store gate lock first
- **THEN** the store's `STORE` names owner A, and B's swap, finding that record under the lock, stops before any write and names owner A

#### Scenario: Unreadable record
- **WHEN** the store's `STORE` exists but has no version or no owner
- **THEN** the update stops before staging, names the file and the missing field, and writes no file in either repo

### Requirement: Only the owner replaces a store's schema
In a store, only the owner's update SHALL replace the schema and the store's `config.yaml` context. Another project's update SHALL install only its code-side files and leave the store unchanged. It SHALL be refused before any write when its target's major or minor version differs from the store's recorded version, naming the store's version, its owner, and the highest release tag with the store's major and minor version.

#### Scenario: Owner updates
- **WHEN** owner A updates from 0.5.0 to 0.6.0, the store is clean on its main, and no change is in flight in the store
- **THEN** the store's schema and `STORE` read 0.6.0, and project B's files are unchanged

#### Scenario: Another project updates within the store's version
- **WHEN** the store records 0.6.0 owned by A, and project B updates from 0.6.0 to 0.6.1
- **THEN** B's skills, agents and `VERSION` move to 0.6.1, `VERSION` is stamped, and the store's schema, `config.yaml` and `STORE` are byte-identical to before

#### Scenario: Another project would leave the store's version
- **WHEN** the store records 0.5.0 owned by A, tag `v0.5.3` exists, and project B asks to update to 0.6.0
- **THEN** the update stops before any write, names the store's version 0.5.0, owner A and `v0.5.3`, and says A updates the store first

### Requirement: The store schema is swapped only on a free store
The owner's swap of the store schema SHALL hold the store gate lock and require the store on its main with no change other than this update's own staging. When the store is busy (on a change branch, or dirty), a patch update whose staged schema is byte-identical to the installed one SHALL swap only the code-side files; any other update SHALL be refused before any write, naming the store's branch.

#### Scenario: Store busy, schema unchanged
- **WHEN** owner A updates from 0.6.0 to 0.6.1, the 0.6.1 schema is byte-identical to 0.6.0's, and the store is checked out on `feat/add-x`
- **THEN** A's skills, agents and `VERSION` move to 0.6.1, `VERSION` is stamped, the store's files, `config.yaml` and `STORE` are unchanged, and the report says the store schema was already current

#### Scenario: Store busy, schema changed
- **WHEN** owner A updates from 0.6.0 to 0.7.0 while the store is checked out on `feat/add-x`
- **THEN** the update stops before any write in either repo, names `feat/add-x`, says to finish that change first, and releases the gate lock it took

#### Scenario: Only this update's staging is untracked
- **WHEN** the store is on its main and its only untracked paths are this update's staging directories
- **THEN** the store counts as free and the swap continues

### Requirement: A store workflow update waits for other projects' changes
The owner's workflow update of a store SHALL be refused before any write while another project's change is in flight in the store (as the install-update rule finds them), naming each. A change is the owner's when the owner's code repo has its local branch `<prefix>/<change-name>`; the owner's own changes are validated as for any workflow update.

#### Scenario: Another project's change in flight
- **WHEN** owner A runs an update from 0.5.0 to 0.6.0 while the store, on its main, has B's local branch `feat/add-y` with an unarchived change and A has no `<prefix>/add-y` branch
- **THEN** the update stops before any write and names `add-y`, the store schema stays 0.5.0, and `add-y` still validates and can ship with B's 0.5.0 skills

#### Scenario: Only the owner's change in flight
- **WHEN** owner A runs an update from 0.5.0 to 0.6.0, the store is on its main, the store's local branch `feat/add-x` holds A's change `add-x` (A has `feat/add-x`), and `add-x` validates against 0.6.0
- **THEN** the update completes and lists `add-x` as validated against 0.6.0

### Requirement: An interrupted store swap is recovered from its own checkout
The update's store gate lock SHALL name the update (`specwright-update <from> -> <to>`) and its code checkout. Only a rerun of the update from that checkout SHALL take over that lock, to discard, resume or roll back, and it SHALL release it. A gate or roadmap lock step that finds it SHALL stop, say to rerun the update from that checkout, and SHALL NOT offer to remove the lock. A rollback SHALL repeat the store checks and stop when they fail.

#### Scenario: Rerun from the same checkout
- **WHEN** owner A's update was killed during the store schema swap, leaving the gate lock with `change: specwright-update 0.5.0 -> 0.6.0` and A's checkout, and the user reruns the update in A
- **THEN** the rerun takes over the lock, resumes or rolls back the swap, reports which, and the lock no longer exists afterwards

#### Scenario: Interrupted after taking the lock, before the first rename
- **WHEN** owner A's swap was killed after it took the gate lock and before its first rename
- **THEN** the rerun in A discards the staging, removes the lock, reports `discarded unfinished update to 0.6.0`, and no lock is left

#### Scenario: Rollback after Step 7 failed, store untouched since
- **WHEN** A's swap completed and released the lock, Step 7 failed, and the store is on main with only A's swapped schema, `STORE` and merged `config.yaml` uncommitted
- **THEN** the rollback takes the lock, restores the previous schema, `config.yaml` and `STORE` record (or removes `STORE` after a claim), releases the lock and reports `rolled back to 0.5.0`

#### Scenario: Another project's gate meets the update lock
- **WHEN** project B starts a change while that lock is held
- **THEN** B's gate creates no branch, names A's checkout and the update, says to rerun the update there, and does not offer to remove the lock

#### Scenario: Rollback after another project moved on
- **WHEN** A's swap finished and released the lock, Step 7 failed, and before A asks to roll back the store is checked out on B's new branch `feat/add-u`
- **THEN** the rollback stops before any rename, names `feat/add-u`, and keeps the swapped state and the journal

### Requirement: Change gate checks the store's version
For a store-backed change, with the gate lock held, `specwright-branch` SHALL compare the project's installed version (`openspec/.specwright/VERSION` in the code repo) with the store's recorded version before it creates any branch. When their major or minor version differs, it SHALL stop, naming both versions and the store's owner, and say which side to update. A store with no `STORE` record SHALL pass the check.

#### Scenario: Versions match
- **WHEN** the project runs 0.6.1 and the store records 0.6.0
- **THEN** the gate continues and creates the branches

#### Scenario: Project behind the store
- **WHEN** the project runs 0.5.0 and the store records 0.6.0 owned by A
- **THEN** the gate creates no branch in either repo, names 0.5.0, 0.6.0 and owner A, and says to update this project to 0.6

#### Scenario: Store behind the project
- **WHEN** the project runs 0.6.0 and the store records 0.5.0 owned by A
- **THEN** the gate creates no branch in either repo and says the owner A updates the store first

#### Scenario: Project has no completed install
- **WHEN** the store records 0.6.0 and the code repo has no `openspec/.specwright/VERSION`
- **THEN** the gate creates no branch in either repo, names the store's version 0.6.0, and says to run the install/update in this project
