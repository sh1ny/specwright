# Spec Delta

## ADDED Requirements

### Requirement: Resume finds an archive that reached main without its own subject
When finish resumes, a repo SHALL count as having its archive on main (fact A on main) when the planning repo's main holds the change's archive directory `<P>/changes/archive/<archived-name>/`, even when no commit on main has the subject `<type>(<change-name>): archive change`. A directory whose name only contains the change name as part of a longer name SHALL NOT count.

#### Scenario: Archive squash-merged in pr mode
- **WHEN** a repo-local `finish: pr` change's PR was squash-merged, so main has the archive directory under the subject `<PR title> (#N)`, the local change branch is deleted, and finish runs again
- **THEN** finish does not report that it found no archive: it runs the issues-left-open backstop for the merged PR and reports `Nothing to finish - archive is on <main>`

#### Scenario: Bulk archive commit
- **WHEN** one archive commit on main archived `add-a` and `add-b` together, both branches are merged and deleted, and finish runs again for `add-b`
- **THEN** finish finds the archive of `add-b` on main and reports `Nothing to finish - archive is on <main>`

#### Scenario: Only a longer change name is archived
- **WHEN** main holds `<P>/changes/archive/2026-10-01-add-a-2/` and finish resumes for `add-a`, which has no archive commit, merge or branch
- **THEN** finish reports that it found no archive of `add-a` and makes no commit, merge or branch deletion

### Requirement: A merged PR whose branch is gone is done after the backstop
In `finish: pr`, when a repo's change PR is MERGED and its change branch no longer exists locally, finish SHALL run only the issues-left-open backstop for that PR and SHALL count the repo as done. It SHALL NOT run `git branch -d` or any other branch deletion for that repo.

#### Scenario: Cleanup already ran
- **WHEN** a repo-local `finish: pr` change's PR merged with a merge commit, cleanup already deleted the local branch, and finish runs again
- **THEN** no `git branch` deletion runs, the backstop runs once for the merged PR, and finish reports `Nothing to finish - archive is on <main>`

#### Scenario: Branch still present
- **WHEN** the change PR is MERGED and the local change branch still exists
- **THEN** finish runs **After the PR is merged** cleanup for that branch, under the branch deletion rule

#### Scenario: Backstop cannot read GitHub
- **WHEN** the change PR is MERGED, the branch is gone, and `closed-check` exits 3
- **THEN** finish deletes no branch, reports the backstop as not done, and does not report `Nothing to finish`

### Requirement: A branch is deleted after a merge only when main has its work
Cleanup after a PR merges, repo-local or store-backed, SHALL delete a change branch only when, after main is updated, its tip is on main, or is the merged PR's head commit or an ancestor of it. Otherwise it SHALL keep the branch and report the commits neither holds. Git's own merged check SHALL NOT be the only safeguard, because it tests the upstream branch, not main.

#### Scenario: Branch merged with a merge commit
- **WHEN** the PR merged with a merge commit and the local branch tip is on main after `git pull --ff-only`
- **THEN** the branch is deleted

#### Scenario: Branch squash-merged
- **WHEN** the PR was squash-merged and the local branch tip equals the PR's head commit
- **THEN** the branch is deleted, although its tip is not on main

#### Scenario: Commit pushed after the merge
- **WHEN** the PR merged at commit A, commit B was then pushed to the same branch, and the local branch tip is B
- **THEN** the branch is kept, B is reported as a commit main lacks, and no `git branch -d` or `-D` runs for it

#### Scenario: Local branch behind the merged head
- **WHEN** the PR was squash-merged with head C, the local branch tip is C's parent because C was pushed from another checkout, and the pull fetched C into `origin/<branch>`, so C is in the local repository
- **THEN** the branch is deleted

#### Scenario: Store-backed cleanup after a late push
- **WHEN** a store-backed change's code PR merged with head A, the local code branch tip is B, and cleanup has checked out and pulled the code main
- **THEN** the code branch is kept and reported with B, while the store branch, whose tip is its merged PR's head, is deleted

#### Scenario: Merged head not available locally
- **WHEN** the local tip is not on main and the merged PR's head commit is not in the local repository, for example because GitHub deleted the remote branch before C was fetched
- **THEN** the branch is kept and reported, and nothing is deleted
