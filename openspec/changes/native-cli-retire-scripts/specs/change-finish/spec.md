# Spec Delta

## ADDED Requirements

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

## MODIFIED Requirements

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
A relative `--code` SHALL be read from the planning repo (the first directory with a `.git` entry at or above `--dir`, else the current directory), as before. Without a leading `--project`, the checked project SHALL be the first directory with a `.git` entry at or above `--code`, else `--dir`, else the current directory (each only when it names a directory), found with no Git command. `--code` SHALL keep its meaning for the plan.

#### Scenario: Store-backed plan finds the code checkout's sw
- **WHEN** `sw finish --dir <store> undo-archive-plan ... --code <code>` runs from inside the store, whose checkout has no `openspec/.specwright/VERSION`, and `<code>` holds one matching the running `sw`
- **THEN** the check reads `<code>/openspec/.specwright/VERSION`, and the plan probes the store's own backend as before this change

#### Scenario: Store-backed call without --code
- **WHEN** `sw finish --dir <store> undo-archive-plan ...` runs from inside the store with no `--code` and no `--project`, and the store has no `openspec/.specwright/VERSION`
- **THEN** it exits 1 with the `sw_mismatch` document saying no installed version was found, no Git command ran, and no script is printed

#### Scenario: Relative --code is read from the planning repo
- **WHEN** `sw finish --dir <store> undo-archive-plan ... --code ../code` runs from a directory other than the store, where `<store>/../code` is the code checkout and `../code` from the caller is another checkout with other settings
- **THEN** the plan probes with `<store>/../code`'s settings, and the version checked is the one in that checkout's `VERSION`

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

## REMOVED Requirements

### Requirement: sw finish undo-archive-plan keeps finish.sh's contract
**Reason**: The plan no longer prints a bash `script` and `after_rerun` text; it prints `steps` and `after_rerun_steps`, so its output no longer parses to the old script's value.
**Migration**: See "The undo plan prints steps, not a script" and "Undo requirements that say script mean the steps". The finish evals run the printed steps and assert the same refs, files and refusals.

### Requirement: A missing or mismatched sw stops the undo plan
**Reason**: The `finish.sh` shim is removed, so no `sw_missing` or `no_python` document is printed, and `sw finish` reads the branch in process, so a missing `vcs.sh` no longer stops the plan with `vcs_script_missing`.
**Migration**: See native-cli "Project commands check the project's version" and "Skills run sw directly", and "Finish stops on a missing sw" above.
