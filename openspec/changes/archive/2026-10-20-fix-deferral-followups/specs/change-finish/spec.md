# Spec Delta

## ADDED Requirements

### Requirement: Resume takes the newest add of the archive as its archive commit
When finish finds a change's archive commit on its branch from the commits that added the archive directory's `review.md`, it SHALL take the newest such commit. An older add was reverted when a newer one exists, and SHALL NOT be taken as the archive commit. Finish SHALL NOT take the newest commit that merely touches the archive directory, since that can be a later review fix.

#### Scenario: Archive added once
- **WHEN** one commit on the branch added `changes/archive/2026-10-19-add-x/review.md`, and a later commit edited that file
- **THEN** finish takes the adding commit as A, not the later edit

#### Scenario: Archive reverted and archived again
- **WHEN** the branch holds an archive commit A1 of `add-x`, a revert of A1, and a second archive commit A2 that added the same archive directory again
- **THEN** finish takes A2 as the archive commit, and the undo plan targets A2 only, leaving A1 and its revert as they are

### Requirement: A deferred archive's undo is planned by a script that runs nothing
When the deferred check stops on `VERDICT: DEFERRED`, finish SHALL run `finish.sh undo-archive-plan` and show the user the undo script it prints. Finish SHALL NOT run it, and SHALL make no commit, merge or push. The plan SHALL read the repo and write nothing. Its output SHALL be one JSON document: the facts found, the undo script, an optional after-rerun script, and warnings. Each script SHALL stop at its first failing command.

#### Scenario: Deferred archive found
- **WHEN** finish starts after a deferred change was archived
- **THEN** finish prints the plan's undo script, and `git status --porcelain`, `git rev-parse HEAD` and every ref are the same after finish as before it

#### Scenario: Plan run on a dirty unrelated path in a resume on main
- **WHEN** the archive is committed on `bugfix/add-x`, finish resumes on `main`, and `main` has an uncommitted change to `README.md`
- **THEN** the plan exits non-zero with `dirty_tree`, names `README.md`, prints no script, and the repo is unchanged

#### Scenario: No archive of the change
- **WHEN** the plan runs for a change with no archive directory in the working tree and no add commit on the branch
- **THEN** it exits non-zero with `no_archive` and prints no script

#### Scenario: Branch moved after the plan
- **WHEN** a commit is added to the branch after the plan was printed, and the user then runs its undo script
- **THEN** the script exits non-zero at its guard, no commit is made, the index and working tree are unchanged, and no main spec is restored

### Requirement: The undo restores the pre-archive state without losing any edit
Applying the printed plan SHALL leave every change of the archive back in `changes/<name>/`, together with every later amendment and every uncommitted edit made to its archive copy. Each main spec the archive modified SHALL get back its pre-archive content, and each one it created SHALL be removed. Every path the archive did not touch SHALL be left as it is. A committed archive SHALL be undone by one new commit, never by a reset, a force-push or a revert of a later commit.

#### Scenario: Uncommitted single archive
- **WHEN** a deferred change's archive is uncommitted, it modified `specs/a/spec.md` and created `specs/b/spec.md`, and the plan is applied
- **THEN** `changes/add-x/` holds the archive copy's files, `specs/a/spec.md` equals `HEAD`'s copy, `specs/b/spec.md` is gone, and no commit was made

#### Scenario: Uncommitted edit in a synced main spec
- **WHEN** the archive is uncommitted, and the user also edited `specs/a/spec.md`, which the archive modified
- **THEN** the undo script copies `specs/a/spec.md` to a backup path under the git directory before restoring it, the plan names that path in a warning, and after the script has run the backup holds the user's edit

#### Scenario: Committed archive with a later amendment
- **WHEN** archive commit A moved `add-x` and synced `specs/a/spec.md`, and a later commit on the branch amended both `changes/archive/2026-10-19-add-x/design.md` and `specs/a/spec.md`
- **THEN** after the undo script's commit, `changes/add-x/design.md` holds the amendment, `specs/a/spec.md` equals its content at `A^`, and the amended copy saved under the git directory holds the amendment to `specs/a/spec.md`

#### Scenario: Amendment survives the rerun
- **WHEN** a bulk archive of the deferred `add-x` and `add-y` was undone this way, a later commit had amended `specs/a/spec.md`, and the after-rerun script then archives `add-y` again and merges the saved amendment back
- **THEN** `specs/a/spec.md` in the working tree holds both `add-y`'s synced requirement and the amendment, with no conflict marker, before finish makes the new archive commit

#### Scenario: Later commit that also changes unrelated paths
- **WHEN** a later commit on the branch amended the archive copy and also changed `src/app.py`
- **THEN** after the undo commit `src/app.py` keeps that commit's content, and the undo commit changes no path outside the archive's paths

#### Scenario: Uncommitted edit in a committed archive copy
- **WHEN** the archive is committed and `changes/archive/2026-10-19-add-x/tasks.md` has an uncommitted edit
- **THEN** after the plan is applied `changes/add-x/tasks.md` holds that edit

#### Scenario: Bulk archive with a deferred member
- **WHEN** one commit A archived `add-x` (deferred) and `add-y` (not deferred), both syncing `specs/a/spec.md`
- **THEN** the undo script moves both archive copies back, restores `specs/a/spec.md` to its content at `A^`, the plan lists both as members with only `add-x` deferred, and it says to rerun the archive without `add-x`

#### Scenario: Uncommitted bulk archive with a deferred member
- **WHEN** an uncommitted bulk archive moved `add-x` (deferred) and `add-y` to `changes/archive/`, and the plan is run for `add-x`
- **THEN** the plan lists both as members, warns that the whole archive is undone, and after its script has run both `changes/add-x/` and `changes/add-y/` are back and neither archive directory exists

#### Scenario: Resume on main with the archive on the branch
- **WHEN** finish resumes on a clean `main` and the archive commit is on `bugfix/add-x`
- **THEN** the undo script checks out `bugfix/add-x` before its guard, and the undo commit is made on that branch, never on `main`

#### Scenario: Saved amendment conflicts after the rerun
- **WHEN** the rerun archive leaves `specs/a/spec.md` so that the saved amendment overlaps the re-synced lines
- **THEN** the after-rerun script exits non-zero at that file, `specs/a/spec.md` holds conflict markers, and both saved copies are still in the backup directory
