# change-finish Specification

## Purpose
Lets `specwright-finish` complete a change that an earlier finish run left partly done, by reading which finish steps git already shows as done instead of repeating or skipping them.

## Requirements

### Requirement: Finish resumes from git evidence
When finish runs again for a change it already archived, it SHALL derive what is done from git in each repo of the change: an archive commit on the change branch, a `merge: <change-name>` commit on main's first-parent history (which counts for an existing change branch only when that branch's tip is on main), and whether the change branch still exists. It SHALL continue from the first step not done and SHALL NOT repeat a done step.

#### Scenario: Interrupted after the archive commit, local mode
- **WHEN** a repo-local change in `finish: local` has its archive commit on the change branch, the branch is not merged, and finish runs again
- **THEN** no second archive commit is made, main gets one `merge: <change-name>` commit, and the change branch is deleted

#### Scenario: Interrupted after the merge, before the branch deletion
- **WHEN** main already has `merge: <change-name>` and the change branch still exists, fully merged
- **THEN** finish makes no new merge commit and deletes the branch with `git branch -d`

#### Scenario: Resumed on the branch it deletes
- **WHEN** finish resumes with the change branch checked out, and that branch is fully merged into main
- **THEN** finish checks out main before running `git branch -d`, and the branch is deleted

#### Scenario: Archive-recovery branch after the change merged
- **WHEN** main has `merge: <change-name>` from the change's earlier merge, and `chore/archive-<change-name>` holds an archive commit that is not on main
- **THEN** finish does not treat that repo as merged and does not delete the branch: it continues with that branch's next step (ship in `finish: pr`, merge in `finish: local`)

#### Scenario: Store merged by hand, code PR still open
- **WHEN** a store-backed change in `finish: pr` has its store branch merged by hand (a store with no GitHub origin), and the code branch's PR is still open
- **THEN** finish does not merge the code branch or delete it, and ships it: the open code PR is reported

#### Scenario: Interrupted after the archive commit, pr mode
- **WHEN** a change in `finish: pr` has its archive commit on the change branch, not yet pushed, and finish runs again
- **THEN** no second archive commit is made, and ship pushes the branch and reports the PR

#### Scenario: Every repo already done
- **WHEN** every repo of the change has `merge: <change-name>` on main and no change branch left
- **THEN** finish reports `Nothing to finish - archive is on <main>` and makes no commit, merge or branch deletion

#### Scenario: Archive commit not found
- **WHEN** finish runs for a change that has no change directory, no archive commit on its branch and no archive on main
- **THEN** finish makes no commit or merge and reports that it found no archive of the change

#### Scenario: Archive committed on the branch but archive paths dirty
- **WHEN** the archive commit is on the change branch and a file under the archive directory has uncommitted changes
- **THEN** finish merges nothing, lists that file, and asks the user

### Requirement: Finish resume keeps the planning-only test and each repo's scope
A resumed finish SHALL run the planning-only test before an archive commit it still has to make. It SHALL NOT merge, ship or delete the code repo's branch after a store-only archive recovery, and SHALL count a code repo with no archive commit, merge or branch beside a finished store as done only when the store's archive marks the change as having no code changes.

#### Scenario: Interrupted before the archive commit, planning-only change
- **WHEN** a store-backed planning-only change was archived but finish stopped before step 2, so the archive paths are uncommitted and no archive commit exists, and finish runs again
- **THEN** the planning-only test runs and writes `specwright-change.yaml` with `code_changes: none` before the archive commit

#### Scenario: Planning-only change already finished
- **WHEN** a store-backed planning-only change finished locally (store merged, empty code branch deleted), and finish runs again
- **THEN** both repos are done, and finish reports `Nothing to finish - archive is on <main>`

#### Scenario: Interrupted store-only archive recovery
- **WHEN** a store-only archive recovery (`chore/archive-<change-name>` in the store) finished its store merge and was interrupted, and the code repo has a change branch with commits not on main
- **THEN** finish does not merge, ship or delete the code branch, and reports it

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
In `finish: pr`, when a repo's change PR is MERGED and its change branch is gone locally, finish SHALL refresh that repo's `main` (only with a clean tree) and SHALL delete no branch there. The planning repo SHALL count only an archive on the refreshed `main`; with none, finish SHALL run no backstop and SHALL NOT count it done. Otherwise, and for a store-backed code repo, finish SHALL run only the issues-left-open backstop for that PR; the repo is done when it succeeds.

#### Scenario: Cleanup already ran
- **WHEN** a repo-local `finish: pr` change's PR merged with a merge commit, cleanup already deleted the local branch, and finish runs again
- **THEN** no `git branch` deletion runs, `main` is pulled fast-forward, the backstop runs once for the merged PR, and finish reports `Nothing to finish - archive is on <main>`

#### Scenario: Stale main holds an older change's archive
- **WHEN** the change name was used before, local `main` already holds that older change's archive directory, the newest PR from the branch has merged on GitHub, and the local branch is gone
- **THEN** finish runs the fenced `git pull --ff-only` on `main` before it reads the archive fact; the refreshed `main` holds this change's archive directory, so the backstop runs once and finish reports `Nothing to finish - archive is on <main>`

#### Scenario: Refreshed main has no archive
- **WHEN** the newest PR from the branch merged, the branch is gone, and after the pull `main` holds no archive of the change
- **THEN** finish runs no backstop, deletes no branch, does not report `Nothing to finish`, and reports that the merged PR did not bring the change's archive to `main`

#### Scenario: Store-backed code repo after merge
- **WHEN** a store-backed `finish: pr` change has its store done, its code PR merged, and the code branch gone
- **THEN** `closed-check` runs for the code PR, finish gives no report that the merged PR did not bring the archive, and finish reports `Nothing to finish - archive is on <main>`

#### Scenario: Dirty tree before the refresh
- **WHEN** the newest PR merged, the branch is gone, and `git status --porcelain` shows changes
- **THEN** finish checks out, pulls and merges nothing, lists the files, and asks the user

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

### Requirement: A reused branch name stops finish before any report
In `finish: pr`, when the branch's PRs include an older merged PR and a newer PR that is closed unmerged, or open with the branch gone, finish SHALL report every such PR and ask the user. This check SHALL use the same PR lookup the no-archive rule makes, and SHALL run before the no-archive report, any done or merged-PR outcome, and the closed-PR row.

#### Scenario: Newest PR closed unmerged, older PR merged, nothing local
- **WHEN** no repo shows an archive commit, a merge or the branch, the newest PR from the branch is closed unmerged, and an older PR from it merged
- **THEN** finish names both PRs and asks, does not report that no archive was found, runs no `closed-check`, and changes no branch

#### Scenario: Closed-PR row with an older merged PR
- **WHEN** the store is done, the code branch has commits, its newest PR is closed unmerged, and an older PR from the same branch merged
- **THEN** finish names both PRs and asks, the same report as the reused-name rule, and merges or deletes nothing

#### Scenario: Only a closed PR
- **WHEN** the store is done, the code branch has commits, and its only PR is closed unmerged
- **THEN** finish reports that closed PR and asks, and merges or deletes nothing

### Requirement: Finish offers a release once the change is on main
With `release.enabled` true, once the change is on main (after the local merge, or after the PR is merged and cleanup finished), `specwright-finish` SHALL read `release.sh untagged`. It SHALL offer `specwright-release` publish for each listed version oldest first, or with `release.auto` publish them oldest first, stopping at the first failure, before the roadmap offer. With none listed, or releases disabled, it SHALL NOT mention a release.

#### Scenario: Untagged version after a PR merge
- **WHEN** releases are enabled, `release.auto` is false, the merged PR moved `VERSION` to 0.5.0 and no `v0.5.0` tag exists
- **THEN** finish offers publish for 0.5.0, then the roadmap mode

#### Scenario: Auto release
- **WHEN** releases are enabled with `release.auto` true and the version on main has no tag
- **THEN** finish runs publish without asking, reports its result, then offers the roadmap mode

#### Scenario: An earlier version was left untagged
- **WHEN** 0.5.0 was merged and never published, and the PR that moved `VERSION` to 0.5.1 is merged
- **THEN** finish offers publish for 0.5.0, then 0.5.1

#### Scenario: Version already tagged
- **WHEN** the merged change did not bump the version and the current version already has its tag
- **THEN** finish offers no release

#### Scenario: Releases disabled
- **WHEN** `release.enabled` is false or missing
- **THEN** finish's report and offers contain no release step

#### Scenario: Auto publish fails
- **WHEN** `release.auto` is true and publish exits non-zero
- **THEN** finish reports the publish error, keeps the merge and cleanup it already did, and still offers the roadmap mode

### Requirement: Local finish publishes no tag without a push decision
In `finish: local` the merge is never pushed, so the release commit is not on origin. Finish SHALL NOT run publish on its own in local mode, even with `release.auto` true. It SHALL report that the version is untagged and that publish runs once main is pushed.

#### Scenario: Local merge with auto release
- **WHEN** `finish` is `local`, `release.auto` is true and the local merge moved the version to 0.5.0
- **THEN** no tag is created or pushed, and the report says `v0.5.0` can be published after `main` is pushed

#### Scenario: Local merge after main was pushed
- **WHEN** the user later pushes main and asks for the release
- **THEN** publish finds the release commit on `origin/main` and tags it

### Requirement: Local finish lists untagged versions from local tags
With `release.enabled` true and `finish: local`, `specwright-finish` SHALL read `release.sh untagged --local` once the change is on main, resolve no login and make no network call, and say that the list comes from local tags, to publish after `main` is pushed.

#### Scenario: Local finish with a github.com origin and no login
- **WHEN** `finish` is `local`, origin's fetch URL is on github.com, the run login is `none`, and the local merge moved `VERSION` to 0.5.0
- **THEN** finish runs `release.sh untagged --local`, resolves no login, runs no `git ls-remote` or other network call, and reports 0.5.0 as untagged from local tags, to publish after `main` is pushed

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
