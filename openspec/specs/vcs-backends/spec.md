# vcs-backends Specification

## Purpose

Lets a project choose the version-control tool that owns every Specwright write in each repo (Git or Jujutsu). Each workflow step behaves the same on either tool, and stops before writing when the tool or repo does not fit.

## Requirements

### Requirement: The backend is chosen per repo
`vcs` in `openspec/specwright.yaml` SHALL select the backend of the code repo, and `planning_store.vcs` the backend of a planning store. `vcs` SHALL accept `git`, `jj` or `gitbutler`; `planning_store.vcs` SHALL accept `git` or `jj`. Each SHALL default to `git` when absent. `planning_store.vcs` SHALL NOT fall back to `vcs`.

#### Scenario: Unset means Git
- **WHEN** `specwright.yaml` has no `vcs` key and the repo has no `.jj/`
- **THEN** every Specwright write in that repo runs through Git

#### Scenario: Store keeps its own backend
- **WHEN** `vcs` is `jj` and `planning_store.vcs` is absent
- **THEN** the code repo's writes run through jj and the store's writes run through Git

#### Scenario: GitButler code repo with a Git store
- **WHEN** `vcs` is `gitbutler`, `finish` is `pr` and `planning_store.vcs` is absent
- **THEN** the code repo's writes run through the GitButler backend and the store's writes run through Git

#### Scenario: Unknown value
- **WHEN** `vcs` is `hg`
- **THEN** the first step that reads the branch or writes stops before any write with `unknown_vcs`, naming the value and the accepted values `git`, `jj` and `gitbutler`

### Requirement: The jj backend is probed before the branch is read
Every branch read and every write in a jj repo SHALL first check that `jj` 0.46 or newer is on PATH, that `.jj/` is at the repo's toplevel, and that a Git work tree shares that toplevel (colocated). A failed check SHALL stop the step before any write, with an error naming the missing piece. Specwright SHALL never run `jj git init` or convert a repo.

#### Scenario: Colocated jj repo
- **WHEN** `vcs` is `jj`, `jj --version` reports 0.46.0, and the toplevel holds both `.jj/` and `.git`
- **THEN** the probe passes and the step continues

#### Scenario: jj not installed
- **WHEN** `vcs` is `jj` and no `jj` is on PATH
- **THEN** the step stops with `tool_missing: jj`, and no branch, commit or bookmark is created

#### Scenario: jj too old
- **WHEN** `vcs` is `jj` and `jj --version` reports 0.45.1
- **THEN** the step stops with `tool_too_old`, naming 0.45.1 and the minimum 0.46

#### Scenario: Not a jj repo
- **WHEN** `vcs` is `jj` and the toplevel has no `.jj/`
- **THEN** the step stops with `not_managed`, and Specwright runs neither `jj git init` nor any Git write

#### Scenario: Secondary jj workspace
- **WHEN** `vcs` is `jj` and the step runs in a jj workspace whose directory has no Git work tree
- **THEN** the step stops with `not_colocated`

### Requirement: A jj repo on the Git backend is reported, not blocked
When the backend is `git` and the toplevel holds `.jj/`, the branch gate SHALL report once that the repo has jj metadata, and that `vcs: jj` (or `planning_store.vcs: jj`) routes writes through jj. It SHALL then continue on Git as before. The Git backend SHALL never run `jj`.

#### Scenario: Leftover jj metadata
- **WHEN** `vcs` is unset, the toplevel holds `.jj/`, and Git's HEAD is on main
- **THEN** the gate prints the jj note, creates the branch with `git checkout -b`, and runs no `jj` command

#### Scenario: Git repo on Git
- **WHEN** `vcs` is unset and the repo has no `.jj/`
- **THEN** the gate prints no jj note and runs no `jj` command

### Requirement: The Git backend keeps today's commands
With the `git` backend, every write SHALL run the same Git command that the skills ran before this change, with the same timeout behaviour: branch creation, switch, commit by named paths, `--no-ff` merge, branch deletion, fetch, pull and push. Commit subjects, trailers and merge subjects SHALL be unchanged.

#### Scenario: Git commit by name
- **WHEN** the backend is `git` and a task group commits `a.sh` and `b.sh` with a message file
- **THEN** the commands run are `git add -- a.sh b.sh` and `git commit -F <file> -- a.sh b.sh`, and no `jj` command runs

#### Scenario: Git push
- **WHEN** the backend is `git` and ship pushes with run login `code-bot`
- **THEN** the command run is the fenced `git push -u origin HEAD`, with no deadline added

#### Scenario: Git commit with nothing to commit
- **WHEN** the backend is `git` and the named paths have no changes
- **THEN** the commit fails as `git commit` fails today, and no other path is committed

### Requirement: On jj a change branch is a bookmark at the parent of the working copy
With `jj`, the branch of every Specwright requirement SHALL be the local bookmark of that name. After every Specwright write, the change bookmark SHALL point at `@-`, Git's HEAD, and Specwright's commits SHALL be ancestors of it. Git SHALL be able to read the bookmark's commits as `refs/heads/<branch>`.

#### Scenario: Git reads after a jj commit
- **WHEN** a task group was committed on jj on `feat/x`
- **THEN** `git rev-parse HEAD` and `git rev-parse refs/heads/feat/x` print the same commit, and `task-cover.sh --range main..HEAD` counts the group's tasks

#### Scenario: Working copy left with other edits
- **WHEN** `@` holds an unrelated edit to `notes.txt` when a group is committed
- **THEN** after the commit `notes.txt` is still changed in `@` and is not in any commit under `feat/x`

### Requirement: On jj the current change branch is resolved from bookmarks
On jj, the current change branch SHALL be the one local bookmark, other than main, that points at `@-`. A conflicted bookmark, several such bookmarks, or an `@` with more than one parent SHALL stop the step, naming them. With no such bookmark, the repo SHALL count as on main only when main points at `@-`.

#### Scenario: One bookmark
- **WHEN** `feat/x` and main point at `@-`
- **THEN** the current branch is `feat/x`

#### Scenario: Two bookmarks at the parent
- **WHEN** both `feat/x` and `docs/y` point at `@-`
- **THEN** the step stops with `ambiguous_branch`, naming both, and writes nothing

#### Scenario: Neither main nor a bookmark
- **WHEN** no bookmark points at `@-` and main points elsewhere
- **THEN** the repo is neither on main nor on a change branch, and the branch gate stops as it does for "not on main"

### Requirement: Fetches for reading move no jj bookmark
On jj, a fetch made only to read the remote's main (the gate's refresh, roadmap status, ship's base check, PR-pair ancestry checks, release publish) SHALL write only `FETCH_HEAD` and objects, never a remote-tracking ref. The step SHALL read the fetched commit instead of `origin/<main>`, because jj turns a remote-tracking move into a move of its tracked local bookmark.

#### Scenario: Remote main ahead, main tracked
- **WHEN** local main tracks `main@origin`, origin's main has a new commit, and the gate refreshes main on jj
- **THEN** local main still points at `@-`, `refs/remotes/origin/main` is unchanged, the gate counts the repo on main, and the archive check reads the fetched commit

#### Scenario: Local main diverged before a read
- **WHEN** local main holds a local merge commit, origin's main moved, and roadmap status refreshes main on jj
- **THEN** no bookmark becomes conflicted, and status reads the fetched commit

#### Scenario: Release publish on jj with main tracked
- **WHEN** local main tracks `main@origin` and release publish runs on jj
- **THEN** no bookmark moves, the history reads use the fetched commit, and the notes list the merged PRs of the base branch by its name

### Requirement: The jj gate creates the bookmark from a clean main
On jj, the gate SHALL count the repo clean when `@` has no changes apart from added files under this change's own `<P>/changes/<change-name>/`, with paths compared using `/` separators. It SHALL count the repo on main when main points at `@-`, and SHALL create the branch with `jj bookmark create <branch> -r @-`. jj offers no stash.

#### Scenario: Gate on jj
- **WHEN** main points at `@-`, `@` is empty, and the gate runs for `add-x`
- **THEN** bookmark `feat/add-x` points at `@-`, the current branch is `feat/add-x`, and no Git write ran

#### Scenario: Carry-over on Windows
- **WHEN** `@` holds only added files under `openspec/changes/add-x/`, and jj prints them with `\` separators
- **THEN** the gate counts them as carry-over and creates the bookmark

#### Scenario: Dirty working copy
- **WHEN** `@` holds a change to `src/a.py`
- **THEN** the gate stops, shows the changed paths, and offers to commit first or abort, never a stash

### Requirement: Moving the working copy on jj carries uncommitted edits
On jj, a switch to main or to a branch, and the working-copy move after a merge or pull, SHALL move `@` onto the target with its edits. If the move leaves `@` conflicted, the step SHALL put `@` back on its old parent with its edits unchanged, then stop with `carry_conflict` and the paths. An empty `@` SHALL simply be started anew on the target.

#### Scenario: Switch with carry-over
- **WHEN** `feat/old` points at `@-`, `@` holds only added files under `openspec/changes/add-x/`, and the gate switches to main
- **THEN** main points at `@-`, the files are still on disk and in `@`, and no bookmark moved

#### Scenario: Carry conflicts
- **WHEN** `@` edits `a.txt`, and the target changed the same lines
- **THEN** `@` is back on its old parent with the same edits, the target bookmark did not move, and the step stops with `carry_conflict` naming `a.txt`

### Requirement: On jj a commit takes only its named paths
A jj commit SHALL commit exactly the named paths from `@` with the given message, then point the change bookmark at the new commit. It SHALL stop before any write when the named paths have no changes in `@`, or when a named path on disk is not tracked in `@` (ignored, or over jj's snapshot size limit).

#### Scenario: Group commit on jj
- **WHEN** a group names `a.sh` and `b.sh`, and `@` also holds `scratch.log`
- **THEN** one commit holds exactly `a.sh` and `b.sh` with the message file's text, the bookmark points at it, and `scratch.log` stays in `@`

#### Scenario: Nothing to commit
- **WHEN** the named paths have no changes in `@`
- **THEN** the commit stops with `nothing_to_commit`, no empty commit is made, and the bookmark does not move

#### Scenario: Named file jj did not snapshot
- **WHEN** a group names a new 2 MB file, over jj's snapshot size limit, and another changed path
- **THEN** the commit stops with `path_not_tracked` naming the file and the reason, no commit is made, and the bookmark does not move

#### Scenario: Message trailers kept
- **WHEN** the message file ends with `Specwright-Task: 1.1` and a `Co-authored-by:` trailer
- **THEN** `git log -1 --format=%B refs/heads/<branch>` shows both trailers exactly

### Requirement: An interrupted jj commit is resumed without loss
When the current branch's bookmark is behind `@-` on a linear path, the next run SHALL move it to `@-` only when every commit between them has a subject with the branch's scope. That scope is `<type>(<change-name>): ` for a change branch, and `<type>(<branch-name>): ` for a roadmap branch. Otherwise the run SHALL stop and list those commits.

#### Scenario: Bookmark left behind by an interruption
- **WHEN** the run died after `jj commit` and before the bookmark moved, so `@-` is `feat(add-x): group 2 Parser` and the bookmark is its parent
- **THEN** the next run moves the bookmark to `@-`, the group is not committed again, and its ticks stay

#### Scenario: Someone else's commit
- **WHEN** the commit between the bookmark and `@-` has the subject `wip`
- **THEN** the run stops with `bookmark_behind`, lists that commit, and moves nothing

#### Scenario: More than 50 commits
- **WHEN** 51 commits lie between the bookmark and `@-`
- **THEN** the run stops with `bookmark_behind` listing the first 50, and moves nothing

### Requirement: A jj local merge keeps the merge proof
A local finish on jj SHALL make a merge commit without moving `@`. Its first parent SHALL be main, its second the branch, and its text the merge message file's (subject `merge: <name>`). It SHALL then carry `@` onto it and point main at it. A conflicted merge SHALL be abandoned, leaving main, `@` and the branch unmoved, and the step SHALL stop.

#### Scenario: Local merge on jj with leftover edits
- **WHEN** `feat/add-x` is merged locally on jj and `@` still holds `scratch.log`
- **THEN** `git log --first-parent --format=%s main` shows `merge: add-x` first, main points at `@-`, and `scratch.log` is still in `@`

#### Scenario: Conflicted merge
- **WHEN** the merge commit would be conflicted
- **THEN** the merge commit is abandoned, main and `@` are where they were, and finish stops naming the conflicted paths

#### Scenario: Interrupted after the merge commit
- **WHEN** a run died after making the `merge: add-x` commit with parents main and `feat/add-x`, but before main moved
- **THEN** the next run reuses that commit, points main at it, and makes no second merge commit

### Requirement: A jj branch is deleted only locally and only once merged
On jj, deleting a change branch SHALL forget the local bookmark without marking a remote deletion. A delete that requires the branch to be merged SHALL first check that the bookmark is an ancestor of main.

#### Scenario: Cleanup after local merge
- **WHEN** `feat/add-x` is an ancestor of main and finish deletes it
- **THEN** the bookmark is gone locally, `refs/heads/feat/add-x` is gone, and no later `jj git push` deletes the remote branch

#### Scenario: Not merged
- **WHEN** a merged-only delete runs while `feat/add-x` is not an ancestor of main
- **THEN** it stops with `not_merged`, and the bookmark stays

### Requirement: A jj push publishes only the change bookmark
A push on jj SHALL push only the change bookmark to the remote, and only when the bookmark points at `@-`. It SHALL stop before any network call when a commit between main and the bookmark is conflicted or has an empty description.

#### Scenario: Ship on jj
- **WHEN** ship pushes `feat/add-x` on jj
- **THEN** origin's `feat/add-x` equals `git rev-parse HEAD`, no other branch or bookmark is pushed, and `gh pr create` is given `--head feat/add-x`

#### Scenario: Conflicted commit
- **WHEN** a commit in `main..feat/add-x` is conflicted
- **THEN** the push stops with `conflicted`, naming the commit, and nothing is pushed

#### Scenario: Bookmark not at the parent
- **WHEN** the bookmark does not point at `@-`
- **THEN** the push stops with the current-branch error, and nothing is pushed

### Requirement: The jj pull fetches only main and only fast-forwards
On jj, a pull SHALL first read the remote's main with a read-only fetch. Equal or behind local main: done, with no jj fetch. Ahead of local main: fetch only main through jj and move local main to it. Diverged: stop with `not_fast_forward` before any jj fetch. A main left conflicted SHALL be set back to its pre-pull commit, then the pull stops. When the repo was on main, `@` SHALL be carried onto the new main.

#### Scenario: Cleanup pull on jj
- **WHEN** the PR merged on GitHub and cleanup pulls main on jj, with `@` empty
- **THEN** local main equals `main@origin`, `@-` is main, and `@` is empty

#### Scenario: Remote head branch deleted at merge
- **WHEN** GitHub deleted `feat/add-x` when the PR merged, and cleanup pulls main on jj
- **THEN** the local bookmark `feat/add-x` and its commits are still there, and `branch-check` decides its deletion

#### Scenario: Local main diverged
- **WHEN** local main has a commit the remote's main lacks, and the remote's main has one local main lacks
- **THEN** the pull stops with `not_fast_forward` naming both commits, main is not conflicted and still points at its local commit, and no branch is deleted

#### Scenario: Local main ahead
- **WHEN** in pr mode the change was merged locally, so local main is ahead of the remote's main, and cleanup pulls
- **THEN** the pull succeeds without a jj fetch and without moving main, and `branch-check` runs

#### Scenario: Remote moved again during the pull
- **WHEN** the read-only fetch found local main behind, but the jj fetch left main conflicted because origin moved in between
- **THEN** main is set back to its pre-pull commit, is not conflicted, and the pull stops with `not_fast_forward`

### Requirement: Release tags are the one Git write on jj
On jj, `release.sh publish` SHALL keep creating the annotated tag with Git, fetching the tag and pushing `refs/tags/<tag>` with Git, because a jj tag carries no message. It SHALL write no other Git ref and SHALL not touch HEAD, the index, a branch or the working copy.

#### Scenario: Publish on jj
- **WHEN** a release is published on a jj repo
- **THEN** origin has an annotated `v0.11.0` at the release commit, and every Git write in the run targets `refs/tags/v0.11.0`

#### Scenario: Tag at another commit
- **WHEN** `v0.11.0` already exists at another commit on jj
- **THEN** publish stops as it does on Git (exit 1), and nothing is written

### Requirement: No other Git write runs under jj
With `jj`, no Specwright step SHALL run a Git command that writes a ref, the index, HEAD, a stash or the working tree in that repo, apart from the release-tag exception. A Git fetch that writes only `FETCH_HEAD` and objects counts as a read. A remote-tracking update does not count as a read.

#### Scenario: Full local flow on jj
- **WHEN** branch, apply of two groups, archive and local finish run on a colocated jj repo with every `git` call Specwright makes logged
- **THEN** the log has no `checkout`, `switch`, `add`, `rm`, `restore`, `read-tree`, `commit`, `merge`, `branch -d/-D`, `pull`, `push`, `stash`, `reset`, `rebase`, and no `fetch` without an empty refmap

#### Scenario: Full PR flow on jj
- **WHEN** branch, apply, ship, archive and cleanup after merge run in `pr` mode on jj with every `git` call Specwright makes logged
- **THEN** the log holds no Git write, every push and pull ran through `jj git`, and `refs/remotes/origin/main` moved only through jj's fetch

### Requirement: Debug never stashes on jj
On jj, `specwright-debug` SHALL never stash. When it would stash the working copy to test on a clean tree, it SHALL stop and ask the user to set their edits aside, or to abort.

#### Scenario: Dirty working copy during a reproduction
- **WHEN** `@` holds edits that may cause the bug and the backend is `jj`
- **THEN** debug shows the changed paths, asks the user, and runs no `git stash`

#### Scenario: Clean working copy
- **WHEN** `@` is empty
- **THEN** debug continues without asking

### Requirement: The archive undo plan uses jj on a jj repo
On a jj repo, `finish.sh`'s undo plan SHALL emit a script that:
- guards like the Git script, but checks for no change in `@` under the touched paths instead of an empty index;
- moves the archived directories back, restores the main specs from the pre-archive commit with `jj restore --from`, and removes the specs it added;
- in committed mode, commits only those paths with `jj commit` and points the branch's bookmark at the result.

#### Scenario: Undo plan on jj
- **WHEN** the undo plan is asked for on a jj repo on `feat/add-x` with the archive committed
- **THEN** the emitted script contains no `git checkout`, `git rm`, `git read-tree`, `git restore` or `git commit`, and after it runs `@-` is `feat(add-x): undo archive of add-x` holding only the touched paths

#### Scenario: Archive committed on another branch
- **WHEN** the archive commit is the tip of `feat/add-x` but the current branch is another, and `@` is empty
- **THEN** the emitted script first moves `@` onto `feat/add-x` with `jj new`, then guards and undoes as above

#### Scenario: Touched path already changed
- **WHEN** `@` already holds a change under `openspec/changes/archive/2026-10-29-add-x/`
- **THEN** the emitted script's guard fails before any move or restore, and nothing is changed

#### Scenario: Wrong branch
- **WHEN** the current branch on jj is not the one passed with `--branch`, and `@` is not empty
- **THEN** finish.sh exits with its wrong-branch error and emits no script

### Requirement: A jj store passes the update's branch check
The install and update SHALL accept a store whose backend is `jj` and whose Git HEAD is detached. They SHALL read its current branch with the jj rule, using the script shipped in the downloaded copy. They SHALL still refuse a store on no branch by that rule, and SHALL refuse with `vcs_script_missing` when the downloaded copy lacks that script.

#### Scenario: jj store on main
- **WHEN** `planning_store.vcs` is `jj`, main points at the store's `@-`, and the update runs
- **THEN** the update does not refuse the store for a detached HEAD

#### Scenario: Git store with a detached HEAD
- **WHEN** `planning_store.vcs` is `git` and the store's HEAD is detached
- **THEN** the update refuses the store as it does today

#### Scenario: Script missing from the download
- **WHEN** `planning_store.vcs` is `jj` and the downloaded copy has no backend script
- **THEN** the update refuses the store with `vcs_script_missing`, and swaps nothing

### Requirement: Paired repos each use their own backend
In a store-backed change, every write in the code repo SHALL use the code repo's backend and every write in the store the store's backend. Branch mirroring, paired commits, the gate lock and rollback SHALL keep their current order and checks on each backend.

#### Scenario: jj code repo with a Git store
- **WHEN** `vcs` is `jj`, `planning_store.vcs` is `git`, and the gate creates `feat/add-x`
- **THEN** the code repo has bookmark `feat/add-x` made by jj, the store has branch `feat/add-x` made by `git checkout -b`, and the gate lock is taken and released as before

#### Scenario: Store probe fails
- **WHEN** `planning_store.vcs` is `jj` and the store has no `.jj/`
- **THEN** the gate stops before creating either branch and releases the lock

### Requirement: GitButler runs only for the code repo with `finish: pr`
`planning_store.vcs: gitbutler` SHALL stop with `unsupported_vcs`, and `vcs: gitbutler` with `finish` other than `pr` (absent included, since it defaults to `local`) SHALL stop with `unsupported_combination`. Both stops SHALL come from the first step that reads the branch or writes, before any write in either repo.

#### Scenario: GitButler store
- **WHEN** `planning_store.vcs` is `gitbutler`
- **THEN** the first step that reads a branch or writes stops before any write in either repo with `unsupported_vcs`, saying a store accepts `git` or `jj`

#### Scenario: GitButler with a local finish
- **WHEN** `vcs` is `gitbutler` and `finish` is `local`
- **THEN** the branch gate stops before any branch exists with `unsupported_combination`, saying GitButler runs only with `finish: pr`

#### Scenario: GitButler with no finish setting
- **WHEN** `vcs` is `gitbutler` and `specwright.yaml` has no `finish` key
- **THEN** the branch gate stops before any branch exists with `unsupported_combination`

### Requirement: The GitButler backend is probed before any `but` command
Every branch read and write on `gitbutler` SHALL first check with Git reads that GitButler manages the repo (`.git/gitbutler/` and `gitbutler.project.targetRef`) with `<main>` as target, then run `but --version` outside the repo to require 0.23+. A failure SHALL stop before any write with `not_managed`, `target_mismatch`, `tool_missing`, `tool_version_unknown` or `tool_too_old`. Specwright SHALL never run `but` setup, teardown or target commands.

#### Scenario: `but` missing
- **WHEN** `vcs` is `gitbutler` and `but` is not on PATH
- **THEN** the branch gate stops with `tool_missing`, no branch exists, and `.git/` is unchanged

#### Scenario: Repo not managed by GitButler
- **WHEN** `vcs` is `gitbutler` and the repo has no `.git/gitbutler/` directory
- **THEN** the step stops with `not_managed`, saying to open the repo with GitButler first, no `but` command ran inside the repo, `.git/gitbutler/` is still absent and `.git/config` is unchanged

#### Scenario: Target is another branch
- **WHEN** the repo's GitButler target is `refs/remotes/origin/develop` and `<main>` is `main`
- **THEN** the step stops with `target_mismatch`, naming both

### Requirement: The GitButler gate applies the change branch beside the others
On GitButler, the branch gate SHALL create `<prefix>/<change-name>` with `but branch new` on the target and leave every other applied branch applied. Uncommitted changes outside `<P>/changes/<change-name>/`, assigned or not, SHALL NOT stop the gate; it SHALL list them once as changes this change will not commit. An existing branch of that name, applied or not, SHALL stop the gate as on Git.

#### Scenario: Other branches applied
- **WHEN** branches `feat/a` and `feat/b` are applied, `feat/b` has uncommitted edits in `src/b.py`, and the gate runs for `add-c`
- **THEN** `feat/add-c` is created and applied, `feat/a` and `feat/b` stay applied with the same commits, `src/b.py` is unchanged on disk and uncommitted, and the gate names `src/b.py` as not part of this change

#### Scenario: Name already taken
- **WHEN** `feat/add-c` exists but is not applied
- **THEN** the gate stops before any `but` write and offers resume, another name or abort

### Requirement: On GitButler the change branch is resolved by name
On GitButler, the change branch SHALL be the one the caller names, never HEAD. `state` SHALL report if it is applied, its tip, and dirty paths split into the change's, unassigned and other branches'. `branch` SHALL be the name when applied, else empty; `on_main` SHALL be false exactly when applied; `clean` SHALL ignore other branches' paths. Switching to main SHALL be a no-op; to an unapplied branch, a `branch_not_applied` stop. Nothing SHALL be applied implicitly.

#### Scenario: Workspace HEAD
- **WHEN** three branches are applied and the commit step asks for `feat/add-c`
- **THEN** `state` reports `feat/add-c` applied with its own tip, not the `gitbutler/workspace` commit

#### Scenario: Another agent's edits during the completion check
- **WHEN** every task of `add-c` is committed and `src/b.py` has uncommitted edits assigned to `feat/b`
- **THEN** `state --branch feat/add-c` reports `clean` true and lists `src/b.py` under the other branch's paths

#### Scenario: Own unnamed edit at the completion check
- **WHEN** the implementer edited `src/y.py` during apply, no task commit named it, and the completion check runs with another agent's edits assigned to `feat/b`
- **THEN** the check lists `src/y.py` as uncommitted and asks whether it belongs to the change, and does not list `feat/b`'s paths

#### Scenario: Finish commits the archive on the change branch
- **WHEN** the archive ran on `feat/add-c`, which is applied beside `feat/b`, and finish starts
- **THEN** `state --branch feat/add-c` reports `on_main` false and `branch` `feat/add-c`, the archive is committed on `feat/add-c`, and no `chore/archive-*` branch is offered

#### Scenario: Cleanup switches to main
- **WHEN** finish or cleanup asks to switch to `<main>` on GitButler
- **THEN** the switch succeeds with `switched: false`, and HEAD, the applied branches and the work tree are unchanged

#### Scenario: Branch unapplied mid-change
- **WHEN** the user unapplied `feat/add-c` and a task commit runs
- **THEN** the commit stops with `branch_not_applied`, and no `but` write runs

### Requirement: On GitButler a commit takes only its named paths into the change branch
A GitButler commit SHALL run `but commit -b <branch>` with the message file and named paths, never without paths. It SHALL stop first with `nothing_to_commit` (named paths unchanged) or `path_owned_elsewhere` (a named path assigned to another branch). The new tip SHALL touch exactly the named paths that changed, hold the message and have the old tip as parent, with no other branch changed; otherwise it SHALL stop with `commit_mismatch`.

#### Scenario: Unrelated edits stay uncommitted
- **WHEN** `src/x.py` (this task) and `notes.txt` (unassigned, not named) are modified and the task commit names `src/x.py`
- **THEN** the new commit on the change branch touches only `src/x.py`, and `notes.txt` is still modified and uncommitted

#### Scenario: Path belongs to another branch
- **WHEN** a named path's changes are assigned to the applied branch `feat/b`
- **THEN** the commit stops with `path_owned_elsewhere`, naming the path and `feat/b`, and no commit is made

#### Scenario: Short path that looks like an ID
- **WHEN** the task commit names a file `ab` while another uncommitted file has the GitButler short ID `ab`
- **THEN** either the commit holds exactly `ab`, or it stops with `commit_mismatch` naming the files it took; it never reports success for a commit of another file

#### Scenario: Trailers kept
- **WHEN** the message file holds a subject, a body and `Specwright-Task:` and `Co-authored-by:` trailers
- **THEN** `git log -1 --format=%B <branch>` shows the same subject, body and trailers

### Requirement: Change ranges read the change branch tip
Every range or record standing for a change's commits (pre-ship range, record key and after-archive lookup, task evidence, the reviewer's diff, finish's head checks, `release.sh check`) SHALL take the branch name and resolve its tip itself on every call, never a SHA from the caller and never HEAD. On GitButler a reader without the branch name SHALL stop. On Git and jj the tip SHALL equal HEAD, so their ranges and keys are unchanged.

#### Scenario: Other applied branches
- **WHEN** `feat/add-c` and `feat/b` are applied on GitButler and the pre-ship review of `add-c` runs
- **THEN** its range is `<main>...<tip of feat/add-c>`, and no commit of `feat/b` or the workspace commit is in the reviewed diff

#### Scenario: Gate after the archive commit
- **WHEN** the archive commit lands on `feat/add-c` while `feat/b` is applied and ship runs the pre-ship gate
- **THEN** the gate finds the pass recorded for the tip before the archive commit, the parent of the archive commit on `feat/add-c`

#### Scenario: Version check ignores other branches
- **WHEN** `feat/b` committed a version bump and `release.sh check` runs for `feat/add-c`, which did not bump
- **THEN** the check reads the version files at the tip of `feat/add-c` and judges only `<main>..<tip of feat/add-c>`

#### Scenario: Branch not given
- **WHEN** `review-run.sh` runs a pre-ship step in a `vcs: gitbutler` project without `--branch`
- **THEN** it stops with a usage error naming `--branch`, and no review runs

#### Scenario: Branch moved after the review
- **WHEN** a pass was recorded for the tip of `feat/add-c`, a fix commit then lands on it, and ship runs the gate with `--branch feat/add-c`
- **THEN** the gate resolves the new tip, finds no record for it, and ship does not push

#### Scenario: Git unchanged
- **WHEN** the pre-ship review runs on the Git backend on `feat/x`
- **THEN** its range and record key name the same commit as `<main>...HEAD` did before this change

### Requirement: A GitButler push publishes only the change branch
A GitButler push SHALL push `refs/heads/<branch>` to the same-named remote branch, without force and without setting an upstream, through the identity fence. It SHALL never run `but push` or `but pr`. A push the remote rejects as non-fast-forward SHALL stop with `push_rejected` and SHALL NOT retry with force. The PR SHALL be opened for that branch alone with `gh pr create --head <branch>`.

#### Scenario: Ship with another branch applied
- **WHEN** `feat/b` has unpushed commits and ship runs for `feat/add-c`
- **THEN** only `refs/heads/feat/add-c` is updated on the remote, `feat/b` is not pushed, and one PR is opened, for `feat/add-c`

#### Scenario: Rewritten branch
- **WHEN** the change branch was rebased outside Specwright after its last push
- **THEN** the push stops with `push_rejected`, and the remote branch is unchanged

### Requirement: The GitButler pull never rebases another branch
A GitButler pull SHALL run `but pull` through the identity fence only when no branch other than the one being cleaned up is applied and no linked worktree exists. Otherwise it SHALL run no `but` write and report `pulled: false`, `pull_skipped`, and the applied branches and worktrees. A skipped pull SHALL NOT stop its caller. Steps that read main after a pull SHALL read the fetched remote main on GitButler.

#### Scenario: Cleanup alone in the workspace
- **WHEN** the merged change branch is the only applied branch and cleanup pulls
- **THEN** `but pull` runs fenced, the local target moves to the remote's main, and the merged branch is no longer applied

#### Scenario: Another branch applied
- **WHEN** cleanup pulls while `feat/b` is applied
- **THEN** no `but pull` runs, `feat/b`'s commits are unchanged, and the result names `feat/b` with `pull_skipped`

#### Scenario: Linked worktree
- **WHEN** cleanup pulls while the merged branch is the only applied branch and a linked worktree exists
- **THEN** no `but pull` runs, and the result names the worktree with `pull_skipped`

#### Scenario: Finish after a skipped pull
- **WHEN** the change's PR merged on GitHub, `feat/b` is applied, and finish checks that main holds the archive
- **THEN** finish reads the archive on the fetched remote main, finds it, and does not report the repo as not done

### Requirement: A GitButler branch is deleted only once merged
On GitButler, deleting a change branch SHALL run `but branch delete` only when the commit the GitButler workspace is based on already contains the merged change (the tip, or the PR's merge commit for a squash merge, is its ancestor). Otherwise it SHALL delete nothing and report `left_applied` for the user's next `but pull`. It SHALL never delete a remote branch or use a Git write.

#### Scenario: Squash-merged PR
- **WHEN** the PR for `feat/add-c` was squash-merged and cleanup runs with no other branch applied
- **THEN** `feat/add-c` is removed from the workspace, other applied branches are unchanged, and the remote branch is touched only by the existing remote-delete step

#### Scenario: Pull skipped
- **WHEN** the PR for `feat/add-c` merged, cleanup's pull was skipped because `feat/b` is applied, a fetch then moved `origin/main` to the merge, and `feat/b` is unapplied before the delete runs
- **THEN** the workspace base still lacks the merge, so `feat/add-c` stays applied with its commits in the work tree, and the result is `left_applied`

#### Scenario: Not merged
- **WHEN** cleanup is asked to delete `feat/add-c` and neither proof holds
- **THEN** the delete stops before any `but` write, naming the branch

### Requirement: No other Git write runs under GitButler
With `gitbutler`, no Specwright step SHALL run a Git command that writes a ref, the index, HEAD, a stash, config or the working tree in that repo, apart from the change branch's push and the release-tag exception. A Git fetch that writes only `FETCH_HEAD` and objects counts as a read.

#### Scenario: Full PR flow on GitButler
- **WHEN** branch, apply of two groups, pre-ship review, ship, archive and cleanup after merge run with `vcs: gitbutler` and every `git` call Specwright makes logged, with another branch applied throughout
- **THEN** the log holds no Git write other than the change branch's `push`, the other branch's commits and uncommitted edits are unchanged, and exactly one PR was opened

#### Scenario: GitButler code repo with a Git store
- **WHEN** the same flow runs store-backed, with a Git store, through the PR pair's ship, feedback and cleanup plan
- **THEN** the code repo's log holds no `checkout`, `switch`, `branch -d/-D`, `pull` or `fetch` without an empty refmap, and the store's cleanup runs its Git commands as before

#### Scenario: Feedback pass with another agent's edits
- **WHEN** a feedback pass runs for `feat/add-c` while `src/b.py` has edits assigned to `feat/b` and `notes.txt` was unassigned and modified before the pass started
- **THEN** the pass plan reports neither path as `unrecorded_change`, and the pass commits only its recorded files

### Requirement: The Git backend refuses to write in a GitButler workspace
With the `git` backend, a repo that GitButler manages (`.git/gitbutler/` and `gitbutler.project.targetRef`) SHALL stop before any write with `gitbutler_workspace`, whatever HEAD is, saying to set `vcs: gitbutler`.

#### Scenario: `vcs` unset in a GitButler workspace
- **WHEN** `vcs` is absent and HEAD is `gitbutler/workspace`
- **THEN** the branch gate stops with `gitbutler_workspace` before any branch or commit, and HEAD is unchanged

#### Scenario: `vcs` unset with one applied branch
- **WHEN** `vcs` is absent, GitButler manages the repo and HEAD is the single applied branch `feat/b`
- **THEN** the gate stops with `gitbutler_workspace`, offers no switch to main, and HEAD stays on `feat/b`

#### Scenario: GitButler metadata with HEAD on main
- **WHEN** `vcs` is absent, GitButler manages the repo and HEAD is `main`
- **THEN** the branch gate stops with `gitbutler_workspace` before any branch exists, and HEAD stays on `main`

### Requirement: Debug never stashes on GitButler
On GitButler, `specwright-debug` SHALL never stash. When it would stash the working tree to test on a clean tree, it SHALL stop and ask the user to set their edits aside, or to abort.

#### Scenario: Dirty workspace during a reproduction
- **WHEN** the workspace holds uncommitted edits that may cause the bug and the backend is `gitbutler`
- **THEN** debug shows the changed paths, asks the user, and runs no `git stash`

### Requirement: The archive undo plan uses GitButler on a GitButler repo
On a GitButler repo, `finish.sh`'s undo plan SHALL emit a script that stops unless the touched paths have no uncommitted change, moves the archived directories back, restores the main specs from the pre-archive commit by writing each file from `git cat-file --filters`, and commits exactly those paths to the change branch with `but commit -b <branch>`. The script SHALL run no Git write.

#### Scenario: Undo a deferred archive
- **WHEN** the undo plan is printed for an archive commit on `feat/add-c` in a GitButler repo
- **THEN** its script names `feat/add-c` in its `but commit -b`, lists every touched path, and contains no `git restore`, `git checkout`, `git add` or `git commit`

### Requirement: GitButler's agent skills are offered, never installed silently
With `vcs: gitbutler`, Specwright SHALL use GitButler's own agent skill as the tool guidance and ship none of its own. The install prompt SHALL offer `but skill install --path <agent skills dir>` for each selected agent and run it only on the user's yes. The branch gate SHALL note, without stopping, when `but skill check` reports the skill missing or out of date in the project.

#### Scenario: Skill not installed
- **WHEN** `vcs` is `gitbutler` and `but skill check` finds no installed GitButler skill in the project
- **THEN** the gate notes the missing skill with the install command once and continues

#### Scenario: Install without consent
- **WHEN** the install runs with `vcs: gitbutler` and the user declines the skill offer
- **THEN** no `but skill install` runs and no global skill directory changes

### Requirement: On GitButler Specwright runs from wherever it was installed
With `vcs: gitbutler`, `vcs.sh` SHALL run the same way whether its scripts directory and the Specwright skill and agent copies are inside the code work tree or outside it. Neither location SHALL be refused or reported as an error.

#### Scenario: Skills installed in the repo
- **WHEN** `vcs` is `gitbutler`, GitButler manages the repo with main as its target, and `vcs.sh probe` runs from `<repo>/.claude/skills/specwright-pr/scripts/`
- **THEN** it exits 0 with `ok: true` and `backend: gitbutler`

#### Scenario: Skills installed at user level beside an in-repo copy
- **WHEN** `vcs` is `gitbutler`, GitButler manages the repo with main as its target, `vcs.sh probe` runs from a directory outside the repo, and the work tree also holds `.claude/skills/specwright-pr/`
- **THEN** it exits 0 with `ok: true` and `backend: gitbutler`

### Requirement: On GitButler the settings are those the change branch committed
With `vcs: gitbutler`, the settings SHALL be read only from `pr-pair.sh context --branch <b>` right before each use (each `pr.validate` run, the merge settings), and `vcs.sh push` SHALL check again. Each SHALL stop with `settings_not_pinned` when the work-tree `openspec/specwright.yaml` differs from the file at the tip of `<b>` (after the merge, with `--after-merge`: that tip while `<b>` exists, else GitButler's target ref), or exists on one side only. Branch reads and commits are not pinned.

#### Scenario: Unassigned edit before ship
- **WHEN** the change branch `feat/add-c` has the settings committed, an unassigned work-tree edit changes `pr.validate`, and ship runs `pr-pair.sh context --branch feat/add-c`
- **THEN** it exits 1 with `settings_not_pinned` naming the file, no validate command runs, and ship does not push

#### Scenario: Watch reads merge settings
- **WHEN** an unassigned edit changes `pr.merge` and watch runs `pr-pair.sh context --branch feat/add-c`
- **THEN** it exits 1 with `settings_not_pinned`, and no merge setting is reported

#### Scenario: Push with an unpinned edit
- **WHEN** an unassigned edit of the settings exists and `vcs.sh push --branch feat/add-c` runs
- **THEN** it exits 1 with `settings_not_pinned`, and nothing is pushed

#### Scenario: Context without the branch
- **WHEN** `vcs` is `gitbutler` and `pr-pair.sh context` runs for the merge settings without `--branch`
- **THEN** it exits 2 with a usage error naming `--branch`, and no merge setting is reported

#### Scenario: Feedback or CI fix push in a repo-local project
- **WHEN** a repo-local GitButler project's feedback pass (or watch's CI fix) is about to run `pr.validate` before its push, and an unassigned edit changed `pr.validate`
- **THEN** the skill reads `validate` from `pr-pair.sh context --branch feat/add-c`, which exits 1 with `settings_not_pinned`, and the edited validate command never runs

#### Scenario: Cleanup after the merge
- **WHEN** the PR of `feat/add-c` merged, cleanup has pulled, the local branch is gone, and the work-tree settings equal the file at GitButler's target ref
- **THEN** `pr-pair.sh context --after-merge --branch feat/add-c` reports `merge` and `delete_branch`, and the remote-branch deletion follows them

#### Scenario: Cleanup with an unpinned edit
- **WHEN** after the merge an unassigned edit sets `delete_branch: true` that the target ref does not have
- **THEN** `pr-pair.sh context --after-merge --branch feat/add-c` exits 1 with `settings_not_pinned`, and no remote branch is deleted

#### Scenario: Cleanup after a skipped pull
- **WHEN** `feat/add-c` committed an edit of `openspec/specwright.yaml` and its PR merged, another branch is applied, `vcs.sh pull --branch feat/add-c` returned `pull_skipped`, and `delete-branch` returned `left_applied`
- **THEN** `pr-pair.sh context --after-merge --branch feat/add-c` reports `merge` and `delete_branch` with no `settings_not_pinned` stop, and the remote-branch deletion follows them

#### Scenario: Settings never committed on the branch
- **WHEN** `openspec/specwright.yaml` exists in the work tree but not at the tip of `feat/add-c`, and ship runs `pr-pair.sh context --branch feat/add-c`
- **THEN** it exits 1 with `settings_not_pinned`

#### Scenario: The change commits its own settings edit
- **WHEN** a task of `feat/add-c` edits `openspec/specwright.yaml` and `specwright-commit` runs `vcs.sh state --branch feat/add-c` and `vcs.sh commit --branch feat/add-c -- openspec/specwright.yaml`
- **THEN** neither stops with `settings_not_pinned`, the edit is committed on `feat/add-c`, and a following `context --branch feat/add-c` passes

#### Scenario: Branch already deleted
- **WHEN** finish cleanup or a gate rollback runs `vcs.sh state --branch feat/add-c` after the branch was deleted
- **THEN** it reports the branch as gone, as before, with no `settings_not_pinned` stop

#### Scenario: Pinned settings
- **WHEN** the work-tree settings equal the file at the tip of `feat/add-c`
- **THEN** `push` and `context --branch` run as before

#### Scenario: Git backend
- **WHEN** `vcs` is `git` and the settings file has an uncommitted edit
- **THEN** no `settings_not_pinned` stop is raised
