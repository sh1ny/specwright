# Spec Delta

## MODIFIED Requirements

### Requirement: The store gate is exclusive
`specwright-branch` SHALL run the store checks and the branch creation while holding an exclusive gate lock on the store, taken with `sw gate lock`, so two sessions cannot both pass against the same store checkout. A lock left by an interrupted session SHALL be removed only with the user's confirmation, through `sw gate unlock --stale`.

#### Scenario: Two sessions start changes against one store at once
- **WHEN** two sessions in separate code checkouts run the branch gate for different changes against the same store at the same time, with the store clean on main
- **THEN** exactly one session creates its branches, and the other stops before creating any branch in either repo, reporting the store as busy or locked

#### Scenario: Gate lock left by an interrupted session
- **WHEN** the branch gate finds the store's gate lock held and no Specwright session is running its gate
- **THEN** Specwright creates no branch, shows when the lock was taken, and removes it with `sw gate unlock --stale` only after the user confirms

#### Scenario: The user does not confirm
- **WHEN** the branch gate finds the store's gate lock held and the user does not confirm that it is stale
- **THEN** Specwright runs no `sw gate unlock`, creates no branch in either repo, and the lock and its owner file are unchanged

### Requirement: Roadmap branches in a store go through the gate lock
When roadmap **init** or **close** creates its project-file branch in a store, it SHALL take the store's exclusive gate lock (the one `specwright-branch` uses) with `sw gate lock --branch <branch>` before checking the store, and SHALL release only the lock it took, right after the branch exists, with `sw gate unlock` with the token its `sw gate lock` printed. A lock held by another session SHALL stop it before any branch or write.

#### Scenario: Store is free
- **WHEN** close runs against a store that is clean on main with no gate lock
- **THEN** it creates `docs/close-m1` in the store while holding the lock, and the lock no longer exists after the branch is created

#### Scenario: Another session holds the lock
- **WHEN** close runs while the store's gate lock exists, owned by another session's change
- **THEN** `sw gate lock` reports `gate_locked`, close creates no branch in either repo, writes no project file, leaves the lock and its owner file unchanged, and shows the owner

### Requirement: A failed store gate branch leaves no new branch
When a store gate's `git checkout -b <branch>` errors in either repo (`specwright-branch`, or roadmap **init** or **close**), the gate SHALL, in each repo where it ran `git checkout -b` and `<branch>` exists, switch back to that repo's main and delete `<branch>`. It SHALL judge the switch by the repo's current branch, not by the command's exit status. It SHALL then release the gate lock it took with `sw gate unlock --token <its token>` and stop with the error.

#### Scenario: Store hook fails after the branch is created
- **WHEN** close runs store-backed with project files in both repos, and the store's `post-checkout` hook exits non-zero, so `git checkout -b docs/close-m1` errors after creating and switching to the branch
- **THEN** both repos are on their main, `docs/close-m1` exists in neither, the gate lock no longer exists, nothing is committed, and the report shows the hook's error

#### Scenario: Store hook fails after the code branch exists
- **WHEN** `specwright-branch` has created `feat/add-csv-export` in the code repo, and the store's `post-checkout` hook exits non-zero on the store's `git checkout -b`
- **THEN** both repos are on their main, `feat/add-csv-export` exists in neither, the gate lock no longer exists, no change directory exists, and the report shows the hook's error

#### Scenario: Code hook fails after the store branch exists
- **WHEN** close runs store-backed with project files in both repos, has created `docs/close-m1` in the store, and the code repo's `post-checkout` hook exits non-zero on its `git checkout -b docs/close-m1`
- **THEN** both repos are on their main, `docs/close-m1` exists in neither, the gate lock no longer exists, nothing is committed, and the report shows the hook's error

#### Scenario: Branch creation refused outright
- **WHEN** the store's `git checkout -b docs/close-m1` errors without creating the branch
- **THEN** no repo holds `docs/close-m1`, both repos are on their main, and the gate lock no longer exists

#### Scenario: One repo cannot switch back
- **WHEN** after a hook failure the code repo is still on `docs/close-m1` after `git checkout main`, and the store is on `docs/close-m1` too
- **THEN** the store is switched to its main and its `docs/close-m1` deleted, the code repo's `docs/close-m1` is kept, the gate lock no longer exists, and the report names the code repo, `docs/close-m1` and its main

#### Scenario: Gate passes without errors
- **WHEN** both repos' `git checkout -b docs/close-m1` succeed
- **THEN** both repos are on `docs/close-m1` and no rollback runs

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
- **THEN** the gate takes no lock, creates no branch in either repo, and says to run the install/update in this project

## ADDED Requirements

### Requirement: sw gate lock takes the store gate lock
`sw gate lock --store <store toplevel> --branch <name> --code <code toplevel>` SHALL create `<store's git common dir>/specwright-gate.lock` with an exclusive `mkdir`, then place its `owner` file whole by renaming a finished temporary file into it, with lines `time:`, `change:`, `code:` and `token:` (fresh and random). It SHALL print `"ok": true` with the lock path and owner. A held lock SHALL print `"error": "gate_locked"` with the owner, exit 1 and change nothing.

#### Scenario: Free store
- **WHEN** `sw gate lock --store <s> --branch add-x --code <c>` runs and the store has no gate lock
- **THEN** the lock directory exists with an `owner` file naming the time, `add-x`, `<c>` and a token, stdout is one JSON document with `"ok": true` and that token, and the exit status is 0

#### Scenario: Lock already held
- **WHEN** the store's gate lock exists with owner `change: add-y` from checkout `<d>`, and `sw gate lock --store <s> --branch add-x --code <c>` runs
- **THEN** stdout is one JSON document with `"ok": false`, `"error": "gate_locked"` and `owner` holding `add-y`, `<d>` and its time, the exit status is 1, and the lock and its owner file are unchanged

#### Scenario: Two locks at once
- **WHEN** two `sw gate lock` calls for different changes run against the same store at the same time
- **THEN** exactly one prints `"ok": true`, the other prints `gate_locked`, and the owner file names the winner only

#### Scenario: Owner file is never half-written
- **WHEN** `sw gate lock` is killed after its `mkdir` and before the rename of its owner file
- **THEN** the lock directory holds no `owner` file, never a partial one, and `sw gate show` reports it held with an empty owner

#### Scenario: Store is not a repository
- **WHEN** `--store` names a directory inside no Git repository
- **THEN** stdout is one JSON document with `"ok": false` and `"error": "not_a_repo"`, the exit status is 1, and no lock directory is created

### Requirement: sw gate show reports the lock and changes nothing
`sw gate show --store <store toplevel>` SHALL print one JSON document with `"ok": true` and `held` set to whether the store's gate lock exists, and, when held, `owner` with its `time`, `change`, `code` and `token` fields (empty for a missing line or owner file). It SHALL write nothing and exit 0.

#### Scenario: Lock held
- **WHEN** the store's gate lock exists with owner `change: add-x`
- **THEN** stdout has `"held": true` and `owner` naming `add-x`, its `code`, `time` and `token`, the exit status is 0, and the lock is unchanged

#### Scenario: Lock directory without an owner file
- **WHEN** the lock directory exists but holds no `owner` file
- **THEN** stdout has `"held": true` and an `owner` whose fields are empty, and nothing is written

#### Scenario: No lock
- **WHEN** the store has no gate lock
- **THEN** stdout has `"held": false`, the exit status is 0, and no lock is created

### Requirement: sw gate unlock releases only the lock it is given
`sw gate unlock --store <store toplevel> --token <token>`, run with `--project <code>` from a store, SHALL read the lock's owner and remove the lock only when its `token` equals `<token>`; on a mismatch it SHALL print `"error": "gate_not_owner"` with the owner fields, exit 1, and remove nothing. The check and the removal are not atomic, as the inline `rm -r` they replace was not. A match SHALL print `"ok": true`, `"removed": true`; no lock SHALL print `"removed": false`, exit 0.

#### Scenario: Own lock released
- **WHEN** the lock's owner holds token `t1` and `<sw> --project <c> gate unlock --store <s> --token t1` runs
- **THEN** the lock directory no longer exists, stdout has `"removed": true`, and the exit status is 0

#### Scenario: A newer acquisition of the same branch
- **WHEN** a session took the lock for `add-x` with token `t1`, it was removed, the same branch's gate took it again with token `t2`, and `<sw> --project <c> gate unlock --store <s> --token t1` runs
- **THEN** stdout has `"error": "gate_not_owner"` with the owner holding `t2`, the exit status is 1, and the lock with token `t2` still exists at its path

#### Scenario: No lock to release
- **WHEN** the store has no gate lock and `<sw> --project <c> gate unlock --store <s> --token t1` runs from the store
- **THEN** stdout has `"ok": true` and `"removed": false`, and the exit status is 0

### Requirement: A stale gate lock is removed only on the user's word
`sw gate unlock --stale --store <store toplevel>` SHALL remove a lock another session left only with `--token <token>` equal to the owner token `sw gate show` printed for the user, or with `--ownerless` when the lock has no owner token. It SHALL refuse an owner whose `change` starts with `specwright-update` with `"error": "gate_update_held"` naming its `code`, exit 1. Skills SHALL run it only after the user confirms the lock `show` printed is stale.

#### Scenario: Confirmed stale lock
- **WHEN** `<sw> --project <c> gate show --store <s>` printed owner `add-y` with token `t9`, the user confirmed it is stale, and `<sw> --project <c> gate unlock --stale --store <s> --token t9` runs
- **THEN** the lock directory no longer exists, stdout has `"removed": true`, and the exit status is 0

#### Scenario: The lock was replaced after the confirmation
- **WHEN** the user confirmed the lock with token `t9`, another session removed it and a new gate took it with token `t10`, and `<sw> --project <c> gate unlock --stale --store <s> --token t9` runs
- **THEN** stdout has `"error": "gate_not_owner"` naming the owner with `t10`, the exit status is 1, and the lock with `t10` still exists

#### Scenario: Lock held by a store update
- **WHEN** the lock's owner has `change: specwright-update 0.5.0 -> 0.6.0` and `code: <a>`, and `<sw> --project <c> gate unlock --stale --store <s> --token <its token>` runs
- **THEN** stdout has `"error": "gate_update_held"` naming `<a>`, the exit status is 1, and the lock and its owner file are unchanged

#### Scenario: An ownerless lock
- **WHEN** the lock directory holds no owner token (an older version's lock, or a gate killed before its owner rename), the user confirmed it is stale, and `<sw> --project <c> gate unlock --stale --ownerless --store <s>` runs from the store
- **THEN** the lock is removed and stdout has `"removed": true`; the same call on a lock that has a token prints `"error": "gate_not_owner"` and leaves it

### Requirement: The gate lock keeps its on-disk form
`sw gate` SHALL use the same lock directory (`<store's git common dir>/specwright-gate.lock`) and the same `owner` lines (`time:`, `change:`, `code:`, plus a `token:` line as `sw update` writes it), byte-compatible with the inline shell lock of earlier versions and with `sw update`'s lock, so a session on an older version and a `sw update` in progress see and respect a lock taken through `sw gate`, and `sw gate` sees theirs. `sw update`'s own use of the lock SHALL be unchanged.

#### Scenario: Lock taken by an older version
- **WHEN** a session on an earlier version took the lock with `mkdir` and wrote its `owner` file, and `sw gate lock` runs for another change
- **THEN** it prints `gate_locked` with that owner's time, change and code, and changes nothing

#### Scenario: Older version meets an sw gate lock
- **WHEN** `sw gate lock` holds the lock and a session on an earlier version runs its inline `mkdir` of the lock directory
- **THEN** the `mkdir` fails because the directory exists, and its `cat` of `owner` shows the `time`, `change` and `code` lines `sw gate lock` wrote

#### Scenario: Update meets an sw gate lock
- **WHEN** `sw gate lock` holds the lock for `add-x` and an owner's `sw update swap` runs against the store
- **THEN** the swap stops with `store_locked` before any write, naming `add-x` as the holder, and the lock is unchanged

### Requirement: Store-started sw calls name the code checkout
Each `sw` project command a skill runs with a store as its working directory or target SHALL name the code checkout, with a leading `--project <code toplevel>` or the command's own `--code`, so the version check reads the code checkout's `VERSION` and never the store's.

#### Scenario: Fenced store push
- **WHEN** a skill pushes the store branch with `<sw> --project <code> as <store login> git push ...` from the store toplevel, and `<code>`'s `VERSION` matches the running `sw`
- **THEN** the push runs in the store as the store login, and no `sw_mismatch` is printed

#### Scenario: Gate commands from a store with no VERSION
- **WHEN** from the store toplevel, which has no `VERSION`, a skill runs `<sw> --project <code> gate lock --store <s> --branch add-x --code <code>`, then `<sw> --project <code> gate show --store <s>`, then `<sw> --project <code> gate unlock --store <s> --token <its token>`
- **THEN** each passes the version check through `--project`, the lock is taken, shown with its token and released, and no `sw_mismatch` is printed

#### Scenario: Code checkout not named
- **WHEN** an `sw` project command runs from the store toplevel with neither `--project` nor `--code`, and the store has no `openspec/.specwright/VERSION`
- **THEN** it prints the `sw_mismatch` document, exits 1, and does nothing in the store
