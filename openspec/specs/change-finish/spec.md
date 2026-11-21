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
When the deferred check stops on `VERDICT: DEFERRED`, finish SHALL run `finish.sh undo-archive-plan` and show the undo script it prints, without running it or making a commit, merge or push. The plan SHALL write no repo state but jj's snapshot and Git import; the GitButler probe's temp directory is outside it and removed. Its output SHALL be one JSON document: the facts found, the undo script, an optional after-rerun script, and warnings. Each script SHALL stop at its first failing command.

#### Scenario: Deferred archive found
- **WHEN** finish starts after a deferred change was archived
- **THEN** finish prints the plan's undo script, and `git status --porcelain`, `git rev-parse HEAD` and every ref are the same after finish as before it on Git; on jj every working-tree file is the same, and refs and the operation log change only by jj's own snapshot and import

#### Scenario: Plan run on a dirty unrelated path in a resume on main
- **WHEN** the archive is committed on `bugfix/add-x`, finish resumes on `main`, and `main` has an uncommitted change to `README.md`
- **THEN** the plan exits non-zero with `dirty_tree`, names `README.md`, prints no script, and every working-tree file is unchanged; on Git the index, HEAD and refs are unchanged too, and on jj only jj's own snapshot and import are recorded

#### Scenario: No archive of the change
- **WHEN** the plan runs for a change with no archive directory in the working tree and no add commit on the branch
- **THEN** it exits non-zero with `no_archive` and prints no script

#### Scenario: Branch moved after the plan
- **WHEN** a commit is added to the branch after the plan was printed, and the user then runs its undo script
- **THEN** the script exits non-zero at its guard, no commit is made, the index and working tree are unchanged, and no main spec is restored

#### Scenario: A jj plan with an unsnapshotted edit
- **WHEN** the undo is planned on a jj store whose working copy has an edit jj has not yet snapshotted
- **THEN** every file's bytes are unchanged after planning, and the only new operations in the operation log, read with `--ignore-working-copy`, are working-copy snapshots

#### Scenario: A jj plan with a pending Git ref import
- **WHEN** the undo is planned for resume bookmark `feat/add-x` on a colocated jj store after a plain `git fetch` moved the remote branch it tracks
- **THEN** every working-tree file's bytes are unchanged; separately, the operation log gains only jj's own import and snapshot operations, and `feat/add-x` and its `refs/heads/` mirror move, or `feat/add-x` becomes conflicted and the plan stops with `ambiguous_branch`

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
`finish.sh` and `sw finish undo-archive-plan` SHALL run only local `git` reads and SHALL NOT run a `git` network command (`fetch`, `pull`, `push`, `ls-remote`) or `gh`. Every network step of finish SHALL be one the agent runs through `as.sh`, under that script's bounds.

#### Scenario: Plan with an unreachable origin
- **WHEN** `finish.sh undo-archive-plan` runs for a committed bulk archive in a repo whose `origin` URL points nowhere, with a `gh` on `PATH` that never answers
- **THEN** it exits 0 within 30 seconds with its usual plan, and the fake `gh` logged no call

#### Scenario: A network command added to finish.sh
- **WHEN** `finish.sh` holds a call to `git fetch`, `git pull`, `git push`, `git ls-remote` or `gh`
- **THEN** the eval that scans the script fails, naming the line

#### Scenario: A network command added to the sw finish source
- **WHEN** a non-comment line of a Dart file under `cli/lib/src/finish/` names `fetch`, `pull`, `push`, `ls-remote` or `gh` as a command word
- **THEN** the eval that scans those files fails, naming the file and the line

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

### Requirement: An archive-only push skips the code validate
Watch SHALL hand finish, and finish ship, the ready head of each repo (`ready head: <repo>=<sha>`). Before the push, ship SHALL run `review-run.sh archive-only` in the planning repo against its ready head. When it reports `archive_only: true`, ship SHALL skip `pr.validate` for the planning repo, and for a code repo still at its ready head; `planning_store.validate` SHALL still run. Any other result, an error, or no ready head SHALL run `pr.validate`.

#### Scenario: Archive of a reviewed head
- **WHEN** watch reported head `h1` ready and handed `ready head: h1`, the change is archived as commit `h2` whose only change is the archive move and the synced main specs, and `pr.validate` is `make test`
- **THEN** ship pushes `h2` without running `make test`, and reports that validate was skipped for an archive-only push

#### Scenario: Store-backed archive
- **WHEN** the change is store-backed, the archive commit is on the store branch, `archive-only` in the store reports `true`, and `planning_store.validate` is `openspec validate --all --strict`
- **THEN** that command runs in the store before the push, a failure stops the push, and the code repo's `pr.validate` is skipped because its head is still the code ready head it was handed

#### Scenario: Archive commit with other files
- **WHEN** the archive commit also changes `src/app.dart`
- **THEN** `archive-only` reports `archive_only: false`, and `pr.validate` runs before the push

#### Scenario: No ready head
- **WHEN** the archive was started by hand, outside watch, so no ready head was handed over
- **THEN** `pr.validate` runs before the push

#### Scenario: Check fails to run
- **WHEN** `archive-only` exits 3 because git cannot read the commits
- **THEN** `pr.validate` runs before the push, and the report names the `archive-only` error

### Requirement: The undo plan runs in the project's sw
The skills SHALL run `sw finish undo-archive-plan` directly; it SHALL keep `finish.sh`'s arguments, refusals and exit codes and print its undo as `steps` and `after_rerun_steps`, and no other implementation SHALL remain. A malformed argument SHALL be refused as native-cli "Arguments sw cannot represent are refused" states; an archived name that is not valid UTF-8 SHALL stop the plan with `"error": "not_utf8"` and exit 1. Neither prints a plan.

#### Scenario: Plan through a matching sw
- **WHEN** the project's `VERSION` reads `0.27.0`, and `sw` 0.27.0 runs `finish undo-archive-plan --change add-x --archived-name 2026-11-07-add-x --prefix openspec --main main` on a branch whose last commit archived `add-x`
- **THEN** stdout is one JSON document with `"ok": true`, `"mode": "committed"` and `steps`, a list of `{cwd, argv}` objects, and the exit status is 0

#### Scenario: Arguments reach sw unchanged
- **WHEN** `sw finish undo-archive-plan` runs with `--prefix "my plans/openspec"` and a `--change` name holding a non-ASCII letter, both archived on the branch
- **THEN** `sw` reads both values whole and unchanged, and the document's member `name` and the printed undo subject name the change as given

#### Scenario: A non-UTF-8 argument
- **WHEN** on Linux `sw finish undo-archive-plan` runs with a `--change` value holding the byte 0xFF
- **THEN** the exit status is non-zero, stdout is empty, no Git command ran, and no plan is printed

#### Scenario: A non-UTF-8 file under the archive
- **WHEN** on Linux the archived change directory, committed on the branch, holds a file outside its `specs` directory whose name holds the byte 0xFF
- **THEN** the exit status is 1, stdout is one JSON document with `"error": "not_utf8"` naming that file with the byte shown as `\xFF`, and no `script` is printed

#### Scenario: A refusal keeps its exit status
- **WHEN** the plan runs for a change with no archive directory in the working tree and no add commit on the branch
- **THEN** the exit status is 1 and stdout is one JSON document with `"error": "no_archive"`, as before this change

#### Scenario: Git Bash path on Windows
- **WHEN** on Windows Git Bash runs `<sw> finish --dir /c/<repo> undo-archive-plan ...`
- **THEN** `sw` receives `C:/<repo>`, converted by Git Bash, the document equals the one for the same call with `--dir C:/<repo>`, and no `cygpath` ran

#### Scenario: Path conversion fails on Windows
- **WHEN** on Windows a caller that is not Git Bash runs `sw finish --dir /etc/x undo-archive-plan ...` and the current drive holds no repository at `\etc\x`
- **THEN** `sw` takes the value as given, a root-relative Windows path, stops with the plan's existing error for a directory that is not a repository, prints no `bad_path` and no script, and runs no Git write

### Requirement: finish.sh finds the project from --code, then --dir
A relative `--code` SHALL start at the planning repo (the root walking up from `--dir`, else from the cwd). Without leading `--project`, the checked project SHALL be the first directory with a `.git` entry at or above `--code`, else `--dir`, else the current directory (each if a directory), found without Git. `--code` SHALL keep its meaning for the plan; a given `--code` that is empty or no directory SHALL give `not_repository` after `usage` and missing `--dir`, before version checks.

#### Scenario: Store-backed plan finds the code checkout's sw
- **WHEN** `sw finish --dir <store> undo-archive-plan ... --code <code>` runs from inside the store, whose checkout has no `openspec/.specwright/VERSION`, and `<code>` holds one matching the running `sw`
- **THEN** the check reads `<code>/openspec/.specwright/VERSION`, and the plan probes the store's own backend as before this change

#### Scenario: Store-backed call without --code
- **WHEN** `sw finish --dir <store> undo-archive-plan ...` runs from inside the store with no `--code` and no `--project`, and the store has no `openspec/.specwright/VERSION`
- **THEN** it exits 1 with the `sw_mismatch` document saying no installed version was found, no Git command ran, and no script is printed

#### Scenario: Relative --code is read from the planning repo
- **WHEN** `sw finish --dir <store> undo-archive-plan ... --code ../code` runs from a directory other than the store, where `<store>/../code` is the code checkout and `../code` from the caller is another checkout with other settings
- **THEN** the plan probes with `<store>/../code`'s settings, and the version checked is the one in that checkout's `VERSION`

#### Scenario: A missing code directory in a checkout of another version
- **WHEN** `sw finish --dir <store> undo-archive-plan ... --code missing` runs and the `--dir` checkout's `VERSION` does not match the running `sw`
- **THEN** the plan reports `not_repository` for that path, not `sw_mismatch`, exits non-zero and emits no script

### Requirement: Finish stops on a missing sw
When `sw finish undo-archive-plan` prints `sw_mismatch`, or the project's `sw` is missing and cannot start, `specwright-finish` SHALL stop with the message and the instruction to rerun the install prompt. It SHALL make no commit, merge or push, run no restore, and SHALL NOT present the answer as an undo plan.

#### Scenario: Mismatched sw at the deferred check
- **WHEN** the deferred check stops on `VERDICT: DEFERRED` and `sw finish undo-archive-plan` exits 1 with a `sw_mismatch` document
- **THEN** finish reports the version mismatch and says to rerun the install prompt, shows no undo script, and every ref, the index and the working tree are as they were

#### Scenario: Missing sw at the deferred check
- **WHEN** the deferred check stops on `VERDICT: DEFERRED` and `<home>/.specwright/bin/<project VERSION>/` holds no `sw`
- **THEN** finish tells the user to rerun the install prompt, shows no undo steps, and makes no commit, merge or push

#### Scenario: A plan that runs is still shown
- **WHEN** the deferred check stops on `VERDICT: DEFERRED` and `sw finish undo-archive-plan` exits 0
- **THEN** finish shows the plan's `steps` in order, each with its working directory, and runs none of them

### Requirement: The undo plan prints steps, not a script
`sw finish undo-archive-plan` SHALL print `steps` and `after_rerun_steps`: ordered lists of objects with `cwd`, an absolute checkout path, and `argv`, starting with the running `sw`'s absolute path, `git`, `jj` or `openspec`; never a shell script. Guards, backups and file checks SHALL be `sw finish` steps. A runner SHALL run each step in its `cwd` in order and stop at the first non-zero exit.

#### Scenario: A committed archive's plan
- **WHEN** the plan runs for a committed deferred archive
- **THEN** stdout holds `steps`, a list of objects each with an absolute `cwd` and an `argv` array, no `script` key, and no element names `bash`, `set -euo pipefail` or a shell operator

#### Scenario: A guard step stops the undo
- **WHEN** a commit is added to the branch after the plan was printed and the user runs the steps in order
- **THEN** the guard step exits non-zero, the later steps do not run, no commit is made, and the index and working tree are unchanged

#### Scenario: Steps run from PowerShell
- **WHEN** on Windows the steps run one by one from PowerShell with no bash installed, from a directory outside the planning checkout
- **THEN** each step starts in its `cwd` and the undo ends with the same refs and files as the old script gave

#### Scenario: A jj planning checkout's plan
- **WHEN** the plan runs for a deferred archive in a `vcs: jj` planning checkout
- **THEN** the jj operations the old script ran (`jj new`, `jj restore`, `jj commit`, `jj bookmark set`) appear as `jj` steps with that checkout as `cwd`, and running them gives the same bookmark and files as the old script

### Requirement: Undo steps do what the old script did
`steps` SHALL run the old script's operations in its order, with its backups and warnings; each `sw` step carries `--project <code toplevel>`. File operations, `git cat-file --filters` writes and the message write SHALL be `sw finish undo-step` steps (`move`, `remove`, `copy`, `mkdir`, `rmdir-if-empty`, `write-blob`, `write-text`); `vcs.sh` calls become `sw vcs` steps. A failing step stops the runner as `set -e` did; recovery is the plan's `warnings`.

#### Scenario: A store-backed plan run from outside both checkouts
- **WHEN** the plan for a deferred archive in a planning store is run step by step from a directory outside the store and the code checkout
- **THEN** every `sw` step passes the version check through its `--project`, and the store ends with the same refs, index and files as the old script gave

#### Scenario: A filtered base written by a step
- **WHEN** the old script would write `git cat-file --filters <rev>:<path> > <file>`
- **THEN** the plan has a `write-blob` step with that revision, path and target, and the file ends with the same bytes

#### Scenario: A GitButler plan commits its paths to the branch
- **WHEN** the plan for a committed deferred archive on a GitButler code repo, with another branch applied that has its own edits, is run step by step
- **THEN** a `write-text` step writes the undo subject to the message file, an `sw vcs commit --repo <code toplevel> --role code --branch <change branch> --message-file <file> -- <paths>` step, run with its argv unchanged, commits only the touched paths to that branch, and the other branch's edits stay uncommitted

#### Scenario: The branch guard reads the structured branch
- **WHEN** on jj (code or store role) or GitButler (the named change branch) the checkout is on another branch when the plan's branch `check` step runs
- **THEN** the step reads the backend's branch value in process, not text of a `vcs state` document, exits non-zero naming both branches, and no later step runs, so none of the writes the old guard prevented happen

#### Scenario: An emptied spec directory that still holds a file
- **WHEN** the plan removes a new main spec whose directory also holds another file, as the old script's best-effort `rmdir` met it
- **THEN** the `rmdir-if-empty` step leaves that directory and its file, exits 0, and the later steps, the jj or GitButler commit included, run

#### Scenario: A step fails partway
- **WHEN** on Git, on jj and on GitButler a step after the first changing step is made to fail
- **THEN** the runner stops at that step and later steps do not run, and the plan's `warnings` hold the same recovery text the old script's plan printed for that backend

### Requirement: The undo planner keeps its decisions
Only the rendering of the undo changes. `sw finish undo-archive-plan` SHALL keep reading user-task ids and archive date prefixes as ASCII digits only, list `carried_edits` in whole-path UTF-8 byte order on every OS, treat a linked `spec.md` or carried file as its regular-file counterpart without descending into a linked directory, and print `internal_error`, exit 1, on an unexpected failure.

#### Scenario: Non-ASCII digits are not a user-task id
- **WHEN** an archived `tasks.md` holds `- [ ] ١.١ [user] Check it` and no other user task
- **THEN** that member's `waiting_on_user` is `[]`

#### Scenario: Non-ASCII digits are not a date prefix
- **WHEN** the plan runs for an archived name `２０２６-１１-０７-add-x` (full-width digits)
- **THEN** no date prefix is stripped, and the active change path the plan restores is `changes/２０２６-１１-０７-add-x`

#### Scenario: Carried edits keep their byte order
- **WHEN** an uncommitted archive's copies of `b.md`, `a.md`, `a/z.md` and `sub/c.md` differ from the change at HEAD, on Linux, Windows and macOS
- **THEN** `carried_edits` lists `a.md`, `a/z.md`, `b.md`, `sub/c.md` under the archive directory in that order on each OS

#### Scenario: Linked files are planned as regular files
- **WHEN** on Linux and macOS an archived `specs/foo/spec.md` is a symlink to a readable file, and in an uncommitted archive a changed `notes.md` is a symlink to a file
- **THEN** capability `foo` is restored or removed as for a regular `spec.md`, `notes.md` is in `carried_edits`, and a linked directory is listed but not descended into

#### Scenario: An unexpected planner failure
- **WHEN** the planner hits an error it has no named stop for
- **THEN** stdout is one JSON document with `"error": "internal_error"`, the exit status is 1, and no steps are printed

### Requirement: Undo requirements that say script mean the steps
Where a change-finish requirement says the undo script or the after-rerun script, it SHALL mean `steps` or `after_rerun_steps`, with the same outcomes: the same guards, backups, restored files, warnings and refusals.

#### Scenario: A requirement on the undo script's backup
- **WHEN** a requirement says the undo script copies a spec to a backup path before restoring it
- **THEN** a step of `steps` makes that copy before the step that restores the spec

#### Scenario: A requirement on an after-rerun refusal
- **WHEN** a requirement says the after-rerun script exits non-zero at a file
- **THEN** a step of `after_rerun_steps` exits non-zero at that file and no later step runs

### Requirement: A jj resume reads its bookmark by exact name
On jj, an undo plan that resumes SHALL read the one requested bookmark by its exact name, without recovering a scope or matching a suffix, and stop with `ambiguous_branch` when it is conflicted, before reading the archive branch's tip. A conflict on any other bookmark SHALL NOT stop the plan, and a failed lookup SHALL stop it with `vcs_error`.

#### Scenario: A conflicted bookmark that is not the resume target
- **WHEN** the undo is planned on jj for resume bookmark `feat/add-x` while a different bookmark, such as `team/feat/add-x`, is conflicted
- **THEN** the plan prints its steps, and no `ambiguous_branch` stop is raised

#### Scenario: The jj bookmark lookup fails
- **WHEN** the jj lookup of the requested resume bookmark by exact name fails
- **THEN** the plan stops with `vcs_error` and prints no steps

### Requirement: The undo planner reports paths whole
On Git and GitButler, `sw finish undo-archive-plan` SHALL read a `dirty_tree` stop's `files` and `carried_edits` with one NUL-framed porcelain reader, and report each exactly as named: never cut, C-quoted or with a backslash rewritten. A staged rename or copy SHALL give both its paths in `files`. `carried_edits` SHALL stay in UTF-8 byte order. A non-UTF-8 path SHALL stop with `not_utf8`; carried edits drop non-member records first. jj and an uncommitted archive keep their path sources.

#### Scenario: The first dirty path keeps its first character
- **WHEN** the archive is committed on `bugfix/add-x`, finish resumes on `main`, and `main` has an uncommitted change to `README.md`, the first entry of `git status`
- **THEN** the `dirty_tree` document's `files` holds `README.md`, not `EADME.md`

#### Scenario: A name that porcelain quotes
- **WHEN** on Linux, Windows and macOS the same resume finds a dirty file named `café.md`, which `git status --porcelain` prints C-quoted by default
- **THEN** `files` holds `café.md`, without quotes or octal escapes

#### Scenario: A staged rename on resume
- **WHEN** on Linux, Windows and macOS the archive is committed on `bugfix/add-x`, finish resumes on `main`, and `main`'s index holds a staged rename of `notes.md` to `old-notes.md`
- **THEN** the `dirty_tree` document's `files` holds both `notes.md` and `old-notes.md`, whole

#### Scenario: The planner leaves the index alone
- **WHEN** on Git the index holds a stale stat entry and the plan runs
- **THEN** the index file's bytes are the same after the plan as before it

#### Scenario: A name with a backslash
- **WHEN** on Linux or macOS the same resume finds a dirty file named `a\b.md`
- **THEN** `files` holds `a\b.md` with its backslash, not `a/b.md`

#### Scenario: A non-UTF-8 name in an unrelated archive
- **WHEN** on Linux finish plans a committed archive's undo on the change branch, and an older archive not being undone holds, beside its tracked `review.md`, an untracked file whose name is not valid UTF-8, which the first `git status` lists by name
- **THEN** the plan succeeds and neither `carried_edits` nor any stop names that file

#### Scenario: An unreadable directory in an unrelated archive
- **WHEN** on Linux, as a non-root user, finish plans a committed archive's undo on the change branch, and an older archive holds an unreadable, unignored `scratch/` that makes `git status` warn and exit 0
- **THEN** the plan stops with `vcs_error` naming Git's warning and prints no steps

#### Scenario: A dirty path that is not UTF-8 on resume
- **WHEN** on Linux finish resumes on `main` and `main` has an untracked file whose name is not valid UTF-8
- **THEN** the plan exits 1 with one `not_utf8` stop document and lists no undo steps

### Requirement: The undo planner's status reads list every untracked file
On Git and GitButler, the planner's own `git status` reads SHALL list every untracked file within the paths each read names, whatever `status.showUntrackedFiles` says, and no `git` the planner runs, its state read included, SHALL rewrite the index.

#### Scenario: Untracked files hidden by configuration
- **WHEN** on Git finish resumes on `main`, `status.showUntrackedFiles` is `no`, and `main` has an untracked file `new/notes.md`
- **THEN** the plan stops with `dirty_tree` and `files` holds `new/notes.md`

### Requirement: A failed status read stops the undo plan
When the planner's own resume or carried-edits `git status` read fails, `sw finish undo-archive-plan` SHALL stop with `vcs_error`, exit 1 and no undo steps. Its message SHALL name `git status` and hold Git's stderr, cut to 4 KiB, or the exit status when stderr is empty. It SHALL never be taken for a clean tree or no carried edits. On Git, on the change branch, a non-empty index SHALL still stop with `staged_changes` before the carried-edits read; GitButler has no index guard, as now.

#### Scenario: The resume status read fails
- **WHEN** finish resumes on `main` and the planner's `git status` read exits non-zero with empty stdout and empty stderr
- **THEN** the plan exits 1 with one `vcs_error` stop naming `git status` and its exit status, and lists no undo steps

#### Scenario: The carried-edits status read fails
- **WHEN** the plan runs on the change branch with a committed archive and the carried-edits `git status` read exits non-zero
- **THEN** the plan exits 1 with one `vcs_error` stop and lists no undo steps, not a plan without carried edits

#### Scenario: A carried-edits read fails on GitButler
- **WHEN** on GitButler the plan runs on the applied change branch with a committed archive and the carried-edits `git status` read exits non-zero
- **THEN** the plan exits 1 with one `vcs_error` stop and lists no undo steps

#### Scenario: A staged change on the change branch
- **WHEN** on Git the plan runs on the change branch with a committed archive and the index differs from HEAD
- **THEN** it stops with `staged_changes`, as before

### Requirement: A failed staged-index read stops the undo plan
On Git, when the planner's staged-index read (`git diff-index --cached`) fails, on the change branch or for an uncommitted archive, `sw finish undo-archive-plan` SHALL stop with `vcs_error`, exit 1 and no undo steps, naming the command and Git's stderr or exit status. A failed read SHALL never be taken for an empty index.

#### Scenario: The staged-index read fails
- **WHEN** on Git the plan runs on the change branch with a committed archive, the staged-index read exits non-zero with empty stdout, and the carried-edits read succeeds
- **THEN** the plan exits 1 with one `vcs_error` stop naming `git diff-index --cached`, and lists no undo steps

#### Scenario: The staged-index read fails for an uncommitted archive
- **WHEN** on Git the archive is uncommitted and the staged-index read exits non-zero with empty stdout
- **THEN** the plan exits 1 with one `vcs_error` stop naming `git diff-index --cached`, and lists no undo steps

### Requirement: The staged-index checks see every staged path
On Git, the planner's staged-index read and the emitted `check index` step SHALL compare the index with HEAD whatever submodule-ignore or diff-helper configuration says, so a staged gitlink update counts as staged and stops the plan with `staged_changes` or the step before its commit. Each check holds only when it runs; the plan's warnings SHALL say the index must not be changed by other commands or hooks while the steps run.

#### Scenario: A staged gitlink hidden by configuration before planning
- **WHEN** on Git `diff.ignoreSubmodules` is `all`, the plan runs on the change branch with a committed archive, and the index holds a staged gitlink update
- **THEN** the plan stops with `staged_changes`

#### Scenario: A staged path that a diff helper would hide
- **WHEN** on Git a path is staged after the plan was printed and before its steps run, and a configured external diff helper exits 0
- **THEN** the `check index` step refuses, and the undo commit is not made

#### Scenario: The plan warns about the index
- **WHEN** a plan with undo steps is printed on Git
- **THEN** its warnings include one saying the index must not be changed by other commands or hooks while the steps run

#### Scenario: A gitlink staged after planning
- **WHEN** on Git `diff.ignoreSubmodules` is `all` and a gitlink update is staged after the plan was printed and before its steps run
- **THEN** the `check index` step refuses, and the undo commit is not made

### Requirement: The resume cleanliness checks see submodule changes
On Git, the resume `git status` read, and on Git and GitButler the emitted `check clean` step, SHALL report a submodule's changes whatever submodule-ignore configuration says, so a dirty submodule stops the plan with `dirty_tree`, or the step refuses, before any checkout, move or restore.

#### Scenario: A submodule dirty at planning
- **WHEN** on Git a submodule has `ignore = all`, its work tree has an unstaged change, and finish resumes on `main` with a committed archive
- **THEN** the plan stops with `dirty_tree` naming the submodule, and lists no undo steps

#### Scenario: A submodule made dirty before the steps run
- **WHEN** on Git finish resumes on `main` with a committed archive, so the plan switches branches, and a submodule with `ignore = all` has its work tree changed after the plan was printed and before its steps run
- **THEN** the `check clean` step refuses, and no checkout runs

#### Scenario: A dirty submodule under a GitButler undo
- **WHEN** on GitButler the archive is committed and, after the plan is printed, a submodule with `ignore = all` and an unstaged change is added under an archived member the undo moves (a submodule there at planning is a nested repository, which the plan refuses)
- **THEN** the `check clean` step refuses, and no move or restore runs

### Requirement: The resume checkout never overwrites an ignored file
On Git, the emitted checkout of the archive branch SHALL refuse rather than overwrite an ignored file in the work tree that the branch tracks, so the step stops before any later step runs.

#### Scenario: An ignored local file the branch tracks
- **WHEN** finish resumes on `main`, `main` ignores `scratch.log`, the user has a local `scratch.log`, and the archive branch tracks that path
- **THEN** the checkout step refuses, `scratch.log`'s bytes and the current branch are unchanged, and no later undo step runs

### Requirement: The GitButler undo guard compares trees itself
On GitButler, the emitted `check unchanged` step SHALL compare the planned tip with workspace HEAD under the touched paths whatever diff-helper configuration says, so another applied branch's committed edit to a touched path stops the steps before any backup, move or restore.

#### Scenario: Another applied branch's edit with a diff helper that exits 0
- **WHEN** on GitButler another applied branch has a committed edit under a path the undo touches, and a configured external diff helper exits 0
- **THEN** the `check unchanged` step refuses, and no backup, move or restore runs

#### Scenario: Another applied branch edits only a sibling path
- **WHEN** on GitButler another applied branch has a committed edit only to an untouched path beside a touched path under the same directory
- **THEN** the `check unchanged` step passes and the undo runs

### Requirement: The Git undo treats each path literally and reads one object view
On Git, every command the undo planner runs or emits SHALL treat each path as a literal name and read history without replacement objects, and the restore steps SHALL use the archive parent the planner resolved.

#### Scenario: A Git undo leaves a pattern-matching sibling alone
- **WHEN** on Git the archive added `openspec/specs/a[1]/spec.md`, `openspec/specs/a1/spec.md` was already tracked, and the undo steps run
- **THEN** `openspec/specs/a1/spec.md` is unchanged in the undo commit and in the work tree

#### Scenario: A replaced archive parent
- **WHEN** on Git the archive parent has a replacement commit with different spec bytes, and `GIT_NO_REPLACE_OBJECTS` differs between planning and the steps
- **THEN** the restored spec equals the true parent's bytes

### Requirement: The Git undo refuses a Git environment that changes what it reads or writes
On Git, the planner SHALL stop with `git_env` when Git's effective top level, Git directory, common directory, index or object path differs from the checkout's own `.git` defaults, and the first step SHALL stop with `git_env` before any checkout or write when they differ at step time. The planner and every guard SHALL also stop with `git_env` on a true glob, noglob or icase pathspec setting, an alternate object, namespace or attribute-source variable, an `attr.tree` setting, or a grafts file.

#### Scenario: An inherited attribute source
- **WHEN** on Git a resume undo is planned, or its steps run, with `GIT_ATTR_SOURCE` set, or `attr.tree` configured, naming a tree that gives a smudge filter to a `tasks.md` only the archive branch has
- **THEN** the plan, or the first step before any checkout, stops with `git_env` naming the setting, and the filter does not run

#### Scenario: Inherited pathspec settings
- **WHEN** on Git `GIT_GLOB_PATHSPECS`, `GIT_NOGLOB_PATHSPECS` or `GIT_ICASE_PATHSPECS` is set to a true value when the undo is planned, or when its steps run
- **THEN** the plan stops with `git_env` naming the variable and prints no steps, or the steps' preflight step stops before any checkout, backup or write

#### Scenario: An index override present from planning
- **WHEN** on Git `GIT_INDEX_FILE` names a copy of the real index inside the Git directory both when the undo is planned and when its steps run
- **THEN** the plan stops with `git_env` naming the index and prints no steps

#### Scenario: Another checkout named by the environment
- **WHEN** on Git the undo is planned for one checkout while `GIT_DIR` and `GIT_WORK_TREE` name another
- **THEN** the plan stops with `git_env` and prints no steps, and neither checkout changes

#### Scenario: A work tree rerouted by configuration
- **WHEN** on Git a plan made without overrides runs with `core.worktree` supplied through `GIT_CONFIG_COUNT` entries
- **THEN** the preflight step stops with `git_env` naming the work tree, before any checkout, backup or write

#### Scenario: An index routed elsewhere
- **WHEN** on Git `GIT_INDEX_FILE`, `GIT_DIR`, `GIT_WORK_TREE` or another variable that reroutes the repository, index or object store is set when the undo is planned, or when its steps run
- **THEN** the plan stops with `git_env` naming the rerouted value, or the steps' preflight step stops before any checkout, backup, index change or commit

### Requirement: The Git undo refuses while a Git operation is in progress
On Git, the planner SHALL stop with `operation_in_progress`, and the steps' preflight step SHALL stop before any checkout or write, while a merge, cherry-pick, revert, rebase or sequence is in progress.

#### Scenario: A Git operation in progress
- **WHEN** on Git a merge, cherry-pick, revert, rebase or multi-commit sequence is in progress when the undo is planned, or starts before its steps run
- **THEN** the plan stops with `operation_in_progress`, or the steps' preflight step fails, before any checkout, backup or write, and nothing is committed

### Requirement: The undo plan stops when a read it relies on fails
The undo planner SHALL treat a path or setting as absent only on positive evidence: a successful tree listing with no entry, a work-tree file or directory that does not exist, or Git reporting a setting unset. Any other failed Git or work-tree read the plan uses SHALL stop the plan with `vcs_error` and no steps, except the first state read's failed branch lookup or `git status`, which keep `git_error`, and default main detection and a dangling archive-branch ref, read as absent.

#### Scenario: A planner read fails
- **WHEN** on Git a planner read whose output the plan uses fails, such as the archive-presence read, the archive's own diff on a bulk archive, or the content read of a member's `review.md` or `tasks.md` that exists in the tree
- **THEN** the plan stops with `vcs_error` and prints no steps

#### Scenario: A member replaced by a file
- **WHEN** on Git a later commit replaced an archived member directory with a tracked file at the same path
- **THEN** the plan stops with `vcs_error` naming that path and prints no steps

#### Scenario: An unlistable delta directory
- **WHEN** an uncommitted archive's delta directory cannot be listed while the archive itself can be moved
- **THEN** the plan stops with `vcs_error` and prints no steps

#### Scenario: A GitButler target that cannot be read
- **WHEN** on a Git-selected undo a GitButler workspace has its target configured and only the read of that setting fails, or `GIT_CONFIG` names a file without it
- **THEN** the plan stops with `gitbutler_workspace` and prints no steps, and emits no Git write

#### Scenario: A failed target read with GitButler selected
- **WHEN** with `vcs: gitbutler` the read of the GitButler target fails, rather than reporting the setting unset
- **THEN** the plan stops with `vcs_error` and prints no steps, while an unset target still stops with `not_managed`

#### Scenario: A partial clone
- **WHEN** a Git undo is planned in a partial clone
- **THEN** the plan stops with `git_env` naming the partial clone before any blob read, makes no remote call and writes no object

#### Scenario: Configuration that reroutes Git only on the archive branch
- **WHEN** a Git undo resumes an archive branch on which conditional configuration (an `includeIf "onbranch:..."` include) sets a setting the preflight refuses, such as `attr.tree`
- **THEN** the preflight run after the checkout stops with `git_env` before any backup or undo index mutation, and nothing is committed

#### Scenario: A resume from main passes both branch guards
- **WHEN** a Git undo resumes from a clean `main` with the archive commit on `bugfix/add-x` and nothing changes after planning
- **THEN** the guard before the checkout expects `main`, the guard after it expects `bugfix/add-x`, both pass, and the steps check out `bugfix/add-x` exactly once

#### Scenario: A code directory reached through a symlink and `..`
- **WHEN** on POSIX the undo is planned with `--code` naming `<A>/link/..`, where `link` points into checkout B, and A and B select different backends for the store
- **THEN** the plan uses B's settings, as the VCS session does, and emits no Git write for a store B routes through jj

#### Scenario: A relative code directory resolved from the store
- **WHEN** `sw finish --dir <store> undo-archive-plan ... --code ../code` runs from a directory outside the store, and `../code` from there and from the store's root name checkouts with different `VERSION` values
- **THEN** only the store-relative checkout's version decides: when it matches the plan proceeds with its settings, and when it does not the command stops with `sw_mismatch` naming it before any Git command runs

#### Scenario: Options are validated before the version check
- **WHEN** `sw finish --dir <store> undo-archive-plan` runs without `--change`, or with an unknown option, in a project of another version
- **THEN** it reports `usage`, exit 2, and runs no Git command

#### Scenario: A code directory that does not exist
- **WHEN** `--code` names a directory that does not exist inside a checkout whose `VERSION` matches
- **THEN** the plan reports `not_repository` for that path, as before this change, and emits no script

#### Scenario: A missing planning directory
- **WHEN** `--dir` names a directory that does not exist
- **THEN** the plan reports `not_a_repo` naming it, as before this change, and runs no version check and no Git command

#### Scenario: The emitted steps check the version the planner checked
- **WHEN** the undo is planned with `--project A`, whose `VERSION` matches, and `--code B`, whose `VERSION` does not
- **THEN** every `sw` step in the plan carries `--project A`, and running the steps as printed passes each step's version check

#### Scenario: The archive branch carries another committed version
- **WHEN** a repo-local resume is planned from `main`, whose committed `VERSION` matches the running `sw`, and the archive branch commits another `VERSION`
- **THEN** the plan stops with `sw_mismatch` naming the archive branch's value, prints no script, and HEAD, index and work tree are unchanged

#### Scenario: A version stamp the checkout changes
- **WHEN** on POSIX a repo-local resume is planned the source tree is otherwise clean, and the live `VERSION` is an ignored, untracked symlink to a tracked file that holds the running version on `main` and another version on the archive branch
- **THEN** the first `sw` step after the checkout stops with `sw_mismatch`, no backup directory is created and no undo write runs, and the plan's warning names `main` and tells the user to check Git's effective work tree and index before switching back

#### Scenario: A decision file that is not a regular file on the current branch
- **WHEN** on POSIX the undo is planned on the archive branch and its committed `tasks.md` is a symlink to an ignored FIFO with no writer
- **THEN** the plan exits 1 with `vcs_error` naming `tasks.md`, without blocking, and prints no steps

#### Scenario: An explicit filter unset
- **WHEN** a resume is planned and an archived `tasks.md` has `-filter` or `-working-tree-encoding`
- **THEN** the plan stops with `unsupported_filter` and prints no steps, although no conversion would apply

#### Scenario: Two members whose names differ only by case
- **WHEN** a bulk undo is planned for `2026-10-18-add-x` and `2026-10-19-Add-X`
- **THEN** the plan stops with `duplicate_member` naming both, prints no steps, and both archives stay as they are

#### Scenario: A filter whose name is unspecified
- **WHEN** a resume is planned and an archived `tasks.md` has `filter=unspecified`, with a configured smudge driver of that name
- **THEN** the plan stops with `unsupported_filter`, prints no steps, and the driver never runs

#### Scenario: A change marker that is not a regular file
- **WHEN** on POSIX a commit after the archive makes `specwright-change.yaml` a symlink to a FIFO with no writer, and the printed steps run
- **THEN** the marker backup step stops with `vcs_error` naming the marker, without blocking, no undo index change is made and the marker is left in place

#### Scenario: A settings file that is not a regular file
- **WHEN** on POSIX the archive branch adds `openspec/specwright.yaml` as a symlink to a FIFO with no writer and the printed steps run
- **THEN** the branch guard after the checkout stops with `vcs_error` naming the path, without blocking, and no backup or undo write runs

#### Scenario: A detached HEAD moved after planning
- **WHEN** a resume is planned on detached commit A and HEAD moves to another detached commit B before the steps run
- **THEN** the steps stop before the checkout, and B stays checked out

#### Scenario: A version stamp that is not a regular file
- **WHEN** on POSIX the archive branch makes `VERSION` a symlink to a FIFO with no writer and the printed steps run
- **THEN** the first `sw` step after the checkout returns `sw_mismatch` saying the stamp is not a regular file, without blocking, and no backup or undo write runs

#### Scenario: A jj store resume whose backend changed after planning
- **WHEN** a jj store resume is planned and the code checkout's `--code` settings then select `git` for the store before the steps run
- **THEN** the steps stop with `git_env` naming both backends before any `jj` command runs, the cleanliness check included, and the store is unchanged even with an unsnapshotted edit

#### Scenario: A sparse checkout on resume
- **WHEN** a resume, or a plan on the checked-out archive branch, is planned in a checkout with sparse checkout enabled
- **THEN** the plan stops with `git_env` naming sparse checkout, prints no script, and nothing is changed

#### Scenario: The version check names the same checkout
- **WHEN** on POSIX `--code` names `<A>/link/..` with `link` pointing into checkout B, and only A's `VERSION` matches the running `sw`
- **THEN** the command stops with `sw_mismatch` naming B's version before any Git command runs

#### Scenario: A backend selection changed before the resume checkout
- **WHEN** after a Git undo is planned the settings that select the repo's backend come to select jj or GitButler
- **THEN** the steps stop with `git_env` before the checkout, and HEAD, the index and the work tree are unchanged

#### Scenario: A resumed branch that selects another backend
- **WHEN** a Git undo resumes an archive branch whose committed settings select jj or GitButler
- **THEN** the steps stop with `git_env` after the checkout, naming both backends, before any backup or undo index mutation

#### Scenario: GitButler set up after planning
- **WHEN** a Git undo was planned and the GitButler metadata directory appears before its steps run
- **THEN** the preflight step stops with `gitbutler_workspace` before any checkout, backup or write

#### Scenario: Settings that cannot be read
- **WHEN** the settings file that chooses the backend exists but cannot be read, or is a symlink whose target cannot be reached
- **THEN** the plan stops with `vcs_error` and prints no steps, while a missing settings file still means Git

#### Scenario: An unreadable work-tree tasks file
- **WHEN** on the change branch a member's work-tree `tasks.md` exists but cannot be read, and its committed copy has no pending task
- **THEN** the plan stops with `vcs_error` and prints no steps

#### Scenario: A tag named like the archive branch
- **WHEN** a tag `feat/add-x` points at another archive of the same member than branch `feat/add-x`
- **THEN** the plan finds the archive in the branch's history, and running its steps restores the bytes of the branch archive's parent

#### Scenario: A tag that spells the full branch ref
- **WHEN** no local branch `feat/add-x` exists and a tag is literally named `refs/heads/feat/add-x`
- **THEN** the plan stops with `no_archive` and prints no steps

#### Scenario: The archive branch deleted after planning
- **WHEN** a resume plan is printed, branch `feat/add-x` is then deleted, and tags named `refs/heads/feat/add-x` and `feat/add-x` point at the planned tip
- **THEN** the steps stop at the tip guard before `git checkout`, with HEAD, index and work tree unchanged

#### Scenario: A branch name that is not UTF-8 at the guard
- **WHEN** a Git resume is planned on a branch whose name holds a literal U+FFFD, and before the steps run the checkout switches to a branch at the same commit whose name has byte `0xFF` in that place
- **THEN** the branch guard stops with `not_utf8`, and both branches, the index and the work tree are unchanged

#### Scenario: A task file hidden by an index flag
- **WHEN** an undo is planned on the checked-out archive branch and a bulk member's `tasks.md`, holding an unticked `[user]` task, is flagged skip-worktree and absent from the work tree
- **THEN** the plan stops with `git_env` naming that file, prints no steps and emits no `openspec archive`

#### Scenario: A main spec with a hidden local edit
- **WHEN** a resume touches a main spec that has the same blob on both branches and is flagged assume-unchanged with a local edit
- **THEN** the plan stops with `git_env` naming that spec before any checkout, and the branch and file bytes are unchanged

#### Scenario: An unrelated file with a hidden edit on resume
- **WHEN** a resume is planned while an unrelated tracked `README.md`, with the same blob on both branches, is flagged assume-unchanged and edited
- **THEN** the plan stops with `git_env` naming `README.md`, and if the flag is set only after planning, the steps stop before `git checkout`; the branch and file bytes are unchanged

#### Scenario: Ignored content under the archive root
- **WHEN** `add-x` is archived without a commit and the archive root holds an ignored directory, such as an archived `add-y` hidden by a local exclude rule or an older, never-committed copy of `add-y`
- **THEN** the plan stops with `git_env` naming that directory, prints no steps, and nothing is changed

#### Scenario: An edit a filesystem monitor missed on resume
- **WHEN** a resume is planned, or its steps run, while a tracked `README.md` has an edit that a stale filesystem-monitor cache does not report
- **THEN** the plan or the clean check stops before `git checkout`, and the branch and file bytes are unchanged

#### Scenario: A GitButler undo over a hidden edit
- **WHEN** a committed GitButler undo is planned while a touched main spec is flagged assume-unchanged and edited
- **THEN** the steps stop before any backup, move or restore, and the main spec's bytes are unchanged

#### Scenario: An archive sibling Git cannot list
- **WHEN** on POSIX, as a non-root user, `add-x` is archived without a commit beside an archived `add-y` whose directory cannot be read
- **THEN** the plan stops with `vcs_error`, prints no steps, and every spec and archive is unchanged

#### Scenario: A status read that warns and exits 0
- **WHEN** a resume is planned, or its steps run, and `git status` exits 0 with no records but writes a warning that it could not open a directory
- **THEN** the plan stops with `vcs_error` and prints no steps, or the clean check stops before `git checkout`

#### Scenario: A main spec whose type the archive changed
- **WHEN** the archive commit replaced a tracked symlink main spec with a regular `spec.md`
- **THEN** the plan stops with `unsupported_entry` naming that spec and prints no steps

#### Scenario: An empty code directory
- **WHEN** `sw finish --dir <store> undo-archive-plan ... --code ''` runs, whatever the `--dir` checkout's `VERSION`
- **THEN** the plan reports `not_repository` for the empty value, before any version check, and emits no script

#### Scenario: A clean resume reads an empty status
- **WHEN** a resume is planned from a clean tree, so `git status` prints no records and exits 0
- **THEN** the empty listing counts as complete and the plan prints its steps

#### Scenario: A rerun under a nested planning root
- **WHEN** the selected OpenSpec root is `planning/`, an active change of the same name exists in the checkout's top-level OpenSpec root, and the printed rerun steps run
- **THEN** only the `planning/` root's change and specs change; the top-level root is unchanged

#### Scenario: A new spec that is a case alias of a tracked one
- **WHEN** on a case-insensitive volume an uncommitted undo's delta names `specs/Foo/spec.md` and `specs/foo/spec.md` is tracked
- **THEN** the plan stops with `unsupported_entry` naming both spellings before any backup or move, and the tracked spec is unchanged

#### Scenario: An untracked case alias owned by another GitButler branch
- **WHEN** on a case-insensitive volume a GitButler uncommitted undo's delta names `specs/Foo/spec.md` and an untracked `specs/foo/spec.md` assigned to `feat/b` is on disk
- **THEN** the plan stops naming both spellings before any backup or move, and the file's bytes and assignment are unchanged

#### Scenario: The archive branch lookup fails
- **WHEN** the archive branch exists but Git fails the lookup of its tip with an error
- **THEN** the plan stops with `vcs_error`, not `no_archive`, and prints no steps

#### Scenario: The state read's branch lookup fails
- **WHEN** the planner's first state read runs `git branch --show-current` and it fails
- **THEN** the plan stops with `git_error`, as before this change, exits 1 and prints no steps; a successful empty result on detached HEAD still plans

#### Scenario: The state read's status fails
- **WHEN** the planner's first state read runs `git status` and it fails
- **THEN** the plan stops with `git_error`, as before this change, exits 1 and prints no steps

### Requirement: Rerun eligibility is read from the copy the undo restores
The planner SHALL decide whether to archive a bulk member again, and which deltas that rerun consumes, from the copy the undo restores: on the current branch the work-tree copy at planning, with no committed fallback; on resume the tip's stored bytes. On a Git resume, a member's `review.md` or `tasks.md` that is not a regular file or has an explicit `filter` or `working-tree-encoding` assignment (unsets included) on the tip or `HEAD` SHALL stop the plan with `unsupported_filter`.

#### Scenario: A checkout filter on a rerun input
- **WHEN** on Git a resume undo restores a member, eligible or not by its stored bytes, whose `tasks.md` the archive branch's attributes give a smudge filter
- **THEN** the plan stops with `unsupported_filter` naming the path, prints no steps, and that file's smudge command does not run

#### Scenario: An untracked attributes file in the work tree
- **WHEN** on Git a resume undo is planned and an ignored `openspec/.gitattributes`, tracked by neither `HEAD` nor the archive branch, gives a smudge filter to a `tasks.md` only the archive branch has
- **THEN** the plan stops with `unsupported_filter` naming that `.gitattributes`, prints no steps, nothing is checked out and the filter does not run

#### Scenario: A checkout filter configured only when the steps run
- **WHEN** on Git a resume is planned from a clean `main`, and its steps run with `core.attributesFile` supplied through `GIT_CONFIG_COUNT`, naming a file that gives a smudge filter to a `tasks.md` only the archive branch has
- **THEN** the last guard before the checkout stops with `unsupported_filter` naming the path, nothing is checked out and the filter does not run

#### Scenario: A current-branch filter on an unchanged decision file
- **WHEN** on Git the current branch and the archive branch hold the same `tasks.md` blob for a member, and only the current branch's attributes give it a filter
- **THEN** the plan stops with `unsupported_filter` naming the path and `HEAD`, and prints no steps

#### Scenario: Restored decision bytes differ from the tip
- **WHEN** on Git a resume undo checks out the archive branch and a member's restored `review.md` or `tasks.md` differs from the tip's blob other than in line endings, or an entry under a member is flagged assume-unchanged or skip-worktree
- **THEN** the steps stop after the checkout naming the path, before any backup or undo index mutation, and nothing is archived again

#### Scenario: A submodule inside an archived member
- **WHEN** on Git the branch tip a committed undo restores from holds a gitlink anywhere under an archived member, on the current branch or on resume, even when the archive commit held none
- **THEN** the plan stops with `unsupported_entry` naming the path and prints no steps

#### Scenario: A committed symlink as a decision file
- **WHEN** on Git a resume undo restores a member whose `tasks.md` is committed as a symlink
- **THEN** the plan stops with `unsupported_filter` naming the path and prints no steps

#### Scenario: A Git too old to read the tip's attributes
- **WHEN** on Git a resume undo runs under a Git older than 2.40
- **THEN** the plan stops with `tool_too_old` naming the attribute read it needs, the minimum 2.40 and the version found, and prints no steps

#### Scenario: A tasks file deleted from the work tree
- **WHEN** on the change branch a member's work-tree `tasks.md` is absent while its committed copy holds a pending user task
- **THEN** the planner decides as for a member with no tasks file, not from the committed copy

#### Scenario: A member deferred after its archive commit
- **WHEN** on the change branch a bulk member's committed `review.md` approves it and its work-tree `review.md` defers it
- **THEN** that member is restored and not archived again, while an eligible sibling is archived again

### Requirement: A Git undo that fails between index steps names what to clean up
On Git, when a step fails after the undo began changing the index and before its commit, the warning SHALL name the undo's index paths and backup directory and SHALL print no command.

#### Scenario: A Git undo that fails between index steps
- **WHEN** on Git the undo's `git read-tree` step fails after `git rm --cached` succeeded
- **THEN** the warning names the undo's index paths and the backup directory, says a resume plan's checkout may have happened, and holds no command; no undo commit is made and no step after the checkout changed the work tree, and planning again stops with `staged_changes` until the user has unstaged those paths and moved the backup

### Requirement: The Git undo checks each restore destination after the checkout
On Git, the steps SHALL check that each restore destination is absent, and on resume that the archive directory holds no untracked or ignored file, after any checkout and before any backup or index write.

#### Scenario: An ignored directory at a restore destination
- **WHEN** on Git a resume undo would restore `openspec/changes/add-x/` and an ignored, untracked, non-empty directory is at that path
- **THEN** the steps stop at the destination check after the checkout and before any backup or index write; the ignored file survives, the archive stays where it is, and no undo commit is made

#### Scenario: An untracked file in a resumed archive
- **WHEN** on Git a resume undo checks out the archive branch and the archive directory holds an untracked or ignored file the tip does not track
- **THEN** the steps stop naming that file after the checkout and before any backup or index write

### Requirement: A committed GitButler undo stops on a path it cannot commit as named
On GitButler, a committed-archive undo SHALL stop with `bad_path` and no steps when a path its commit names would be refused or respelled by the commit.

#### Scenario: A GitButler undo of a path with glob characters
- **WHEN** on GitButler the undo of a committed archive would commit `openspec/specs/a[1]/spec.md`, or on Linux or macOS `openspec/specs/a\b/spec.md`
- **THEN** the plan stops with `bad_path` naming that path, and prints no steps, so nothing is backed up, moved or committed

### Requirement: The undo keeps a copy of every change marker it removes
On every backend and in every mode, after any checkout and guards and before the undo's first index change or removal, the undo SHALL copy each `specwright-change.yaml` it will remove into its backup directory as the file is when the steps run, skip a marker that is absent then, and stop on any other copy failure. A guard that refuses first SHALL leave the marker untouched.

#### Scenario: An edited change marker in the archive
- **WHEN** the marker the undo removes was edited before planning or after the plan was printed, and the steps' guards pass
- **THEN** its bytes as they were when the backup step ran are in the named backup directory, copied before the undo's first index change or removal

#### Scenario: A guard refuses before the backup
- **WHEN** a guard such as a committed GitButler or jj undo's `check clean` over the archive refuses
- **THEN** the steps stop and the marker is untouched

#### Scenario: A resumed undo's marker
- **WHEN** on Git a resume undo checks out the archive branch, its post-checkout guards pass, and the marker exists
- **THEN** the marker is copied after the checkout and those guards, and before `git rm --cached`

#### Scenario: A marker deleted after planning
- **WHEN** on Git the marker of a committed archive is deleted after the plan is printed and before the steps run
- **THEN** its backup step does nothing and the undo completes

#### Scenario: A marker copy that fails
- **WHEN** the marker exists but copying it into the backup directory fails
- **THEN** the steps stop at that copy, before the undo's first index change or removal; on a resume the archive branch stays checked out

### Requirement: The dirty_tree message names each record plainly
For a `dirty_tree` stop from the planner's own resume `git status` read, the message SHALL list each dirty record as its two-character status with its spaces trimmed, a space and its path, joined by `; `, as now. A rename or copy SHALL read `<status> <source> -> <path>`. Paths SHALL appear unquoted and untrimmed, as in `files`; a newline, carriage return or tab in a name SHALL show as `\n`, `\r` or `\t`, so the message stays one line.

#### Scenario: Other dirty stops keep their messages
- **WHEN** the plan stops because a committed archive's file is missing from the working tree, or on a jj resume
- **THEN** the stop's message is the one it gave before this change

#### Scenario: Ordinary names read as before
- **WHEN** the dirty records are a modified `README.md` and an untracked `new.txt`
- **THEN** the message ends with `M README.md; ?? new.txt`, the same text as before this change

#### Scenario: A rename and a name with a tab
- **WHEN** on Linux or macOS the dirty records are a staged rename of `a.md` to `b.md` and an untracked file named with a tab, `x<TAB>y.md`
- **THEN** the message holds `R a.md -> b.md` and `?? x\ty.md`, and `files` holds `a.md`, `b.md` and the name with its real tab

#### Scenario: A carriage return and a trailing space in a name
- **WHEN** on Linux the only dirty record is an untracked file named `x`, a carriage return, `y.md` and a trailing space
- **THEN** the message ends with `?? x\ry.md ` with the escape and the trailing space, and `files` holds the name with its real carriage return and its trailing space

### Requirement: A usage error from the planner's state read exits 2
When the planner's read of the repo state fails with a usage error, `sw finish undo-archive-plan` SHALL exit 2, as other usage errors do. Any other failed state read SHALL stay a finish stop with exit 1.

#### Scenario: State read refuses its arguments
- **WHEN** the state read the planner runs fails with a usage error
- **THEN** the planner prints one JSON stop document naming that error and exits 2

#### Scenario: State read fails for another reason
- **WHEN** the state read fails with `not_repository`, or with `bad_setting` because the settings YAML is malformed
- **THEN** the planner prints its stop document and exits 1, as before

### Requirement: Fixed undo-plan defects are exceptions to the script's refusals
The undo-plan requirements above change `finish.sh`'s refusals, exit codes, guards and warnings: usage errors exit 2, failed reads stop with `vcs_error`, paths are whole, guards see what configuration hid, and the plan warns about the index. Where these differ from "The undo plan runs in the project's sw", "Undo steps do what the old script did" or "Undo requirements that say script mean the steps", they SHALL take precedence; all else follows those.

#### Scenario: A usage error from the state read
- **WHEN** the planner's state read fails with a usage error, which `finish.sh` reported with exit 1
- **THEN** the plan exits 2, as the usage-error requirement states

#### Scenario: A guard that now refuses
- **WHEN** the index holds a staged gitlink hidden by `diff.ignoreSubmodules=all`, which `finish.sh` let through
- **THEN** the plan stops with `staged_changes` and prints no steps

#### Scenario: A plan carries the new index warning
- **WHEN** on Git a plan with undo steps is printed with a clean index
- **THEN** its warnings hold the new index warning beside the warnings `finish.sh` gave

#### Scenario: Any other refusal
- **WHEN** the plan is refused for a reason none of these requirements changes, such as `staged_changes`
- **THEN** its error and exit status are as `finish.sh` gave them

### Requirement: An undo destination is absent only by evidence
Each `check absent` guard an undo plan emits SHALL prove its path absent from the nearest existing ancestor: that ancestor SHALL be a directory, not a link, whose listing succeeds and has no entry named as the next component down. An ancestor that is not a directory, cannot be listed, or lists that name SHALL stop the step with `vcs_error` naming the path, before any undo write. A restore destination SHALL get this guard on Git only.

#### Scenario: The first undo in a fresh checkout
- **WHEN** the undo runs in a checkout with no `specwright-undo` directory yet
- **THEN** the absence check passes from the Git directory's listing and the backup is created

#### Scenario: An ancestor that cannot be listed
- **WHEN** on POSIX the nearest existing ancestor of a destination cannot be listed
- **THEN** the step stops with `vcs_error` naming the destination, before any backup or undo write

### Requirement: A rerun plan warns that it writes specs in place
A plan with `after_rerun_steps` SHALL include a warning that the rerun's `openspec archive` updates existing main specs in place, so a hard link to one of them, elsewhere, also changes; the restore's replacement does not cover the rerun.

#### Scenario: A bulk undo that reruns the archive
- **WHEN** a bulk undo plan has `after_rerun_steps`
- **THEN** its warnings include the in-place rerun warning, and a plan without `after_rerun_steps` has none

### Requirement: Every printed undo step fits the command line
The planner's own Git calls and every step it emits, with each command a step starts, SHALL fit the launcher's limit for the resolved executable: 32,766 UTF-16 units, 8,191 for a batch file; on POSIX 32,766 UTF-8 bytes plus one per argument, environment not counted. Steps repeating one operation per path SHALL be split into runs that fit, and the commit subject shortened past 1,000 characters. A one-run step that does not fit SHALL stop the plan with `plan_too_large`, printing no steps.

#### Scenario: A POSIX commit sized in bytes
- **WHEN** on POSIX a jj bulk undo's commit fileset of multi-byte names fits 32,766 UTF-16 units but its UTF-8 bytes plus one per argument exceed 32,766
- **THEN** the plan stops with `plan_too_large` and prints no steps

#### Scenario: A jj bulk undo whose commit fileset is too long
- **WHEN** on Windows a jj bulk undo has a short subject but its commit's fileset of archived and restored directories would exceed the limit
- **THEN** the plan stops with `plan_too_large` and prints no steps; working-tree bytes are unchanged, the undo makes no commit or bookmark move, and the operation log gains only jj's own snapshot and import

#### Scenario: A GitButler bulk undo whose commit runs through `but.cmd`
- **WHEN** on Windows `but` resolves to `but.cmd` and a GitButler bulk undo's commit paths fit 32,766 units but not the batch file's 8,191
- **THEN** the plan stops with `plan_too_large`, prints no steps, and the branch tip and archive files are unchanged

#### Scenario: A Git bulk undo whose synced spec paths force batching
- **WHEN** on Windows a committed Git bulk undo's `mkdir`, `git restore`, `git rm --cached` and post-commit `remove` steps each name more synced spec paths than one line holds
- **THEN** each is emitted as several runs under the limit and the steps run to one undo commit with every spec restored or removed

#### Scenario: A bulk undo with a very long member list
- **WHEN** on Windows, with the archive branch checked out, `sw finish undo-archive-plan` plans a committed docs-only bulk archive whose member names joined into the undo subject would exceed the command-line limit
- **THEN** the plan's commit step fits the limit, the steps run to one undo commit whose subject names the deferred change and the member count, and no step fails to start

### Requirement: The planner does not count the environment a step runs with
On POSIX the planner SHALL size each command line without the environment the steps will run with, which the kernel also counts against its limit. A jj or GitButler commit that fits the planner's budget can therefore be rejected at launch after the members moved, and the user then reruns the commit step with a smaller environment.

#### Scenario: A large environment is not counted
- **WHEN** on POSIX a jj bulk undo is planned under an inherited environment whose size, added to its commit line, passes the 32,766-byte budget
- **THEN** the plan prints the commit as one step and does not stop with `plan_too_large`

### Requirement: An undo never writes inside a nested repository
Unless the earlier ignored-archive refusal applies, an undo SHALL stop with `unsupported_entry` naming it if a path its steps, other than the resume branch switch, may write, remove or move has a work-tree component that the index, or on resume the archive tip, records as a gitlink, or that holds a `.git` entry, or if a moved member's directory holds below it an entry of any type whose name folds to `.git`; checked at planning, before any backup or move, and before the rerun.

#### Scenario: A rerun spec inside a submodule
- **WHEN** a later commit adds a clean, initialized submodule at `openspec/specs/foo`, and an eligible archived member of a committed bulk undo gains a `foo` delta
- **THEN** the plan stops with `unsupported_entry` naming `openspec/specs/foo`, prints no steps, and both repositories are unchanged

#### Scenario: A linked worktree inside an archived member
- **WHEN** a committed archive's member to be moved holds an ignored linked worktree at `scratch/`, whose `.git` file names another repository
- **THEN** the plan stops with `unsupported_entry` naming `scratch/.git`, prints no steps, and there is no undo commit or move and the worktree registration is unchanged

#### Scenario: A linked `.git` marker inside an archived member
- **WHEN** on POSIX a committed archive's member to be moved holds an ignored `scratch/` whose `.git` is a relative symbolic link to metadata outside the member
- **THEN** the plan stops with `unsupported_entry` naming `scratch/.git`, prints no steps, and there is no undo commit or move and the nested checkout is unchanged

#### Scenario: A worktree marker spelled in another case
- **WHEN** on a case-insensitive volume a committed archive's member to be moved holds an ignored linked worktree whose marker is stored as `.GIT` and Git recognizes it
- **THEN** the plan stops with `unsupported_entry` naming that marker, prints no steps, and there is no undo commit or move and the worktree registration is unchanged

#### Scenario: A gitlink only on the archive branch
- **WHEN** a resume is planned from a clean `main`, only the archive branch records `openspec/specs/foo` as a gitlink, and an eligible member has a `foo` delta
- **THEN** the plan stops with `unsupported_entry` naming `openspec/specs/foo`, prints no steps, and nothing is checked out

### Requirement: An undo writes only the paths it names
In every undo, on any main-spec path the steps or after-rerun steps may write or remove, and each moved member's source and target, existing components below the checkout root SHALL be real directories, an existing spec file a regular file, and no path SHALL equal or lie under another after case folding, else `unsupported_entry`; steps SHALL recheck before any backup or move and before the rerun. A restore SHALL replace the file, with its restored revision's mode.

#### Scenario: A restore destination that is a link
- **WHEN** on POSIX a GitButler undo is planned after a touched main spec was replaced by a symlink to an unrelated file
- **THEN** the plan stops with `unsupported_entry` naming that spec, the unrelated file's bytes are unchanged and the archive stays in place

#### Scenario: A removed spec under a linked directory
- **WHEN** on POSIX a newly synced spec's capability directory is replaced by a symlink to an unrelated directory with its own `spec.md`, before planning or only after the plan was printed
- **THEN** the plan, or the first destination check before any backup or move, stops naming that path; the unrelated `spec.md` is unchanged and the archive is not moved

#### Scenario: A hard-linked restore destination
- **WHEN** on POSIX a modified main spec, executable on disk but not in the restore revision, restored by a GitButler undo has a second hard link elsewhere
- **THEN** the restore gives the spec its old bytes and the revision's non-executable mode, the other link keeps its bytes, and the archive is moved

#### Scenario: A rerun spec under a linked directory
- **WHEN** on POSIX a GitButler bulk undo's rerun would write `specs/foo/bar/spec.md` and `specs/foo` is a link to an outside directory holding `bar/` but no `bar/spec.md`
- **THEN** the plan stops with `unsupported_entry` naming that path, and no file is created outside the checkout

#### Scenario: A rerun destination linked after the undo
- **WHEN** a bulk undo's steps ran and a rerun spec's capability directory is then replaced by a link to an outside directory
- **THEN** an after-rerun destination check stops naming that path before any `openspec archive` starts, and the outside directory is unchanged

#### Scenario: A plain-Git removal under a linked directory
- **WHEN** on POSIX a Git uncommitted undo would remove a new spec whose capability directory links to an outside directory holding a regular `spec.md`
- **THEN** the plan stops naming that path, with no backup, no archive move, and the outside `spec.md` unchanged

#### Scenario: Two absent rerun specs that differ only by case
- **WHEN** a bulk undo's rerun would write `specs/Foo/spec.md` for one member and `specs/foo/spec.md` for another, both absent, on a case-sensitive or a case-insensitive volume
- **THEN** the plan stops with `unsupported_entry` naming both spellings and prints no steps; neither member is moved or archived again

#### Scenario: Two absent rerun specs where one lies under the other
- **WHEN** a bulk undo's rerun would write `specs/a/spec.md` for one member and `specs/a/spec.md/b/spec.md` for another, both absent
- **THEN** the plan stops with `unsupported_entry` naming both paths and prints no steps; neither member is moved or archived again

#### Scenario: A rerun spec blocked by an existing directory
- **WHEN** a committed bulk undo's rerun would write `specs/a/spec.md`, and the checkout already tracks `specs/a/spec.md/b/spec.md`, which the undo does not touch
- **THEN** the plan stops with `unsupported_entry` naming `specs/a/spec.md` and prints no steps; HEAD, the index and every file are unchanged

#### Scenario: A linked archive directory
- **WHEN** on POSIX the unignored `changes/archive` is a symbolic link to an outside directory holding the archived member, which has no spec deltas, before planning or only after the plan was printed
- **THEN** the plan, or the first destination check before any backup or move, stops with `unsupported_entry` naming the member path; nothing is backed up or moved and the outside directory is unchanged

#### Scenario: Another GitButler branch's edit at a rerun-only spec
- **WHEN** a GitButler undo's rerun would write `foo/spec.md`, which the archive did not touch, and another applied branch has an edit there
- **THEN** the plan stops before any write and the other branch's edit is unchanged

#### Scenario: Another GitButler branch's assigned edit on an uncommitted undo
- **WHEN** an uncommitted GitButler undo would restore `foo/spec.md`, or move an archived member holding `design.md`, and another applied branch has an assigned, uncommitted edit at that file
- **THEN** the plan stops before any backup or write, and the file, its assignment and the archive are unchanged

#### Scenario: Another GitButler branch's assigned edit at a backslash path
- **WHEN** on POSIX another applied branch has an assigned, uncommitted edit at `openspec/specs/a\b/spec.md`, before planning or only after the plan was printed, and the GitButler undo would restore that spec
- **THEN** the plan, or the destination check before any backup, stops naming that path, and nothing is written

#### Scenario: An archived member edited after a GitButler plan
- **WHEN** a committed GitButler undo is planned and an archived member's `design.md` is then edited before the steps run
- **THEN** the steps stop before any backup, move or commit

#### Scenario: A foreign assignment made after a GitButler plan
- **WHEN** an uncommitted GitButler undo is planned and, before its steps run, an archived member's `design.md` edit is reassigned to another applied branch
- **THEN** the destination check stops before any backup or move, and the edit and its assignment are unchanged

#### Scenario: An unassigned member edit on a GitButler undo
- **WHEN** an uncommitted GitButler undo moves an archived member whose `design.md` has an edit assigned to no other branch
- **THEN** the undo runs and the edit is carried with the member
