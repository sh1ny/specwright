## MODIFIED Requirements

### Requirement: The backend is chosen per repo
`vcs` in `openspec/specwright.yaml` SHALL select the backend of the code repo, and `planning_store.vcs` the backend of a planning store. `vcs` SHALL accept `git`, `jj` or `gitbutler`; `planning_store.vcs` SHALL accept `git` or `jj`. Each SHALL default to `git` when absent. `planning_store.vcs` SHALL NOT fall back to `vcs`. `planning_store.vcs: gitbutler` SHALL stop with `unsupported_vcs`, and `vcs: gitbutler` with `finish` other than `pr` (absent included, since it defaults to `local`) SHALL stop with `unsupported_combination`; both stops SHALL come from the first step that reads the branch or writes, before any write in either repo.

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

#### Scenario: GitButler store
- **WHEN** `planning_store.vcs` is `gitbutler`
- **THEN** the first step that reads a branch or writes stops before any write in either repo with `unsupported_vcs`, saying a store accepts `git` or `jj`

#### Scenario: GitButler with a local finish
- **WHEN** `vcs` is `gitbutler` and `finish` is `local`
- **THEN** the branch gate stops before any branch exists with `unsupported_combination`, saying GitButler runs only with `finish: pr`

#### Scenario: GitButler with no finish setting
- **WHEN** `vcs` is `gitbutler` and `specwright.yaml` has no `finish` key
- **THEN** the branch gate stops before any branch exists with `unsupported_combination`

## ADDED Requirements

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
