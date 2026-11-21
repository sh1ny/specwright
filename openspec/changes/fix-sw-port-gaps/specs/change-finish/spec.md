## MODIFIED Requirements

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

### Requirement: A deferred archive's undo is planned by a script that runs nothing
When the deferred check stops on `VERDICT: DEFERRED`, finish SHALL run `finish.sh undo-archive-plan` and show the undo script it prints, without running it or making a commit, merge or push. The plan SHALL write no repo state but jj's snapshot and Git import; the GitButler probe's temp directory is outside it and removed. On jj, a resume SHALL read the one requested bookmark by its exact name, without recovering a scope or matching a suffix, and stop with `ambiguous_branch` when it is conflicted, before reading the archive branch's tip; a conflict on any other bookmark SHALL NOT stop the plan, and a failed lookup SHALL stop it with `vcs_error`. Its output SHALL be one JSON document: the facts found, the undo script, an optional after-rerun script, and warnings. Each script SHALL stop at its first failing command.

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

#### Scenario: A conflicted bookmark that is not the resume target
- **WHEN** the undo is planned on jj for resume bookmark `feat/add-x` while a different bookmark, such as `team/feat/add-x`, is conflicted
- **THEN** the plan prints its steps, and no `ambiguous_branch` stop is raised

#### Scenario: The jj bookmark lookup fails
- **WHEN** the jj lookup of the requested resume bookmark by exact name fails
- **THEN** the plan stops with `vcs_error` and prints no steps

## ADDED Requirements

### Requirement: The undo planner reports paths whole
On Git and GitButler, `sw finish undo-archive-plan` SHALL report each path its own `git status` reads give, in a `dirty_tree` stop's `files` and in `carried_edits`, exactly as named: never cut, C-quoted or with a backslash rewritten. A staged rename or copy SHALL give both its paths in `files`. `carried_edits` SHALL stay in UTF-8 byte order. A non-UTF-8 path SHALL stop with `not_utf8`; carried edits drop non-member records first. jj and an uncommitted archive keep their present path sources.

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
