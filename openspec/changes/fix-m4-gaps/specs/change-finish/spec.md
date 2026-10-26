# Spec Delta

## ADDED Requirements

### Requirement: finish.sh runs no network command
`finish.sh` SHALL run only local `git` reads and SHALL NOT run a `git` network command (`fetch`, `pull`, `push`, `ls-remote`) or `gh`. Every network step of finish SHALL be one the agent runs through `as.sh`, under that script's bounds.

#### Scenario: Plan with an unreachable origin
- **WHEN** `finish.sh undo-archive-plan` runs for a committed bulk archive in a repo whose `origin` URL points nowhere, with a `gh` on `PATH` that never answers
- **THEN** it exits 0 within 30 seconds with its usual plan, and the fake `gh` logged no call

#### Scenario: A network command added to finish.sh
- **WHEN** `finish.sh` holds a call to `git fetch`, `git pull`, `git push`, `git ls-remote` or `gh`
- **THEN** the eval that scans the script fails, naming the line

### Requirement: A spec deleted after a bulk archive stays deleted after the rerun
When a later commit on the branch deleted a main spec that a bulk archive had synced, and a member the after-rerun script archives again has a delta for that spec, the after-rerun script SHALL delete that spec again after the rerun archives, and the plan's warning SHALL say that it does. The script SHALL first check that the spec does not exist, and stop before any archive if it does. A spec in no rerun member's delta SHALL keep the warning that the undo leaves it deleted.

#### Scenario: Spec synced by both members, deleted later
- **WHEN** commit A archived `add-x` (deferred) and `add-y`, both syncing `specs/a/spec.md`, a later commit deleted `specs/a/spec.md`, and the plan's script and then its after-rerun script are run
- **THEN** `specs/a/spec.md` does not exist in the working tree, `changes/archive/` holds `add-y`'s new archive, and the plan's warning names `specs/a/spec.md` as deleted again by the after-rerun script

#### Scenario: Spec recreated before the after-rerun script
- **WHEN** the plan's after-rerun script will delete `specs/a/spec.md` again, and the user created a new `specs/a/spec.md` after running the undo script
- **THEN** the after-rerun script exits non-zero before any `openspec archive`, naming `specs/a/spec.md`, and the user's file is unchanged

#### Scenario: Spec synced only by the deferred member, deleted later
- **WHEN** commit A archived `add-x` (deferred, syncing `specs/b/spec.md`) and `add-y` (syncing only `specs/a/spec.md`), and a later commit deleted `specs/b/spec.md`
- **THEN** the after-rerun script has no step for `specs/b/spec.md`, the warning says the undo leaves it deleted, and after both scripts `specs/b/spec.md` does not exist
