# Spec Delta

## MODIFIED Requirements

### Requirement: On jj a change branch is a bookmark at the parent of the working copy
With `jj`, the branch of every Specwright requirement SHALL be the local bookmark of that name. After every Specwright write, the change bookmark SHALL point at `@-`, Git's HEAD, and Specwright's commits SHALL be ancestors of it. Git SHALL be able to read the bookmark's commits as `refs/heads/<branch>`.

#### Scenario: Git reads after a jj commit
- **WHEN** a task group was committed on jj on `feat/x`
- **THEN** `git rev-parse HEAD` and `git rev-parse refs/heads/feat/x` print the same commit, and `sw commit task-cover --range main..HEAD` counts the group's tasks

#### Scenario: Working copy left with other edits
- **WHEN** `@` holds an unrelated edit to `notes.txt` when a group is committed
- **THEN** after the commit `notes.txt` is still changed in `@` and is not in any commit under `feat/x`

### Requirement: Release tags are the one Git write on jj
On jj, `sw release publish` SHALL keep creating the annotated tag with Git, fetching the tag and pushing `refs/tags/<tag>` with Git, because a jj tag carries no message. It SHALL write no other Git ref and SHALL not touch HEAD, the index, a branch or the working copy.

#### Scenario: Publish on jj
- **WHEN** a release is published on a jj repo
- **THEN** origin has an annotated `v0.11.0` at the release commit, and every Git write in the run targets `refs/tags/v0.11.0`

#### Scenario: Tag at another commit
- **WHEN** `v0.11.0` already exists at another commit on jj
- **THEN** publish stops as it does on Git (exit 1), and nothing is written

### Requirement: Change ranges read the change branch tip
Every range or record standing for a change's commits (pre-ship range, record key and after-archive lookup, task evidence, the reviewer's diff, finish's head checks, `sw release check`) SHALL take the branch name and resolve its tip itself on every call, never a SHA from the caller and never HEAD. On GitButler a reader without the branch name SHALL stop. On Git and jj the tip SHALL equal HEAD, so their ranges and keys are unchanged.

#### Scenario: Other applied branches
- **WHEN** `feat/add-c` and `feat/b` are applied on GitButler and the pre-ship review of `add-c` runs
- **THEN** its range is `<main>...<tip of feat/add-c>`, and no commit of `feat/b` or the workspace commit is in the reviewed diff

#### Scenario: Gate after the archive commit
- **WHEN** the archive commit lands on `feat/add-c` while `feat/b` is applied and ship runs the pre-ship gate
- **THEN** the gate finds the pass recorded for the tip before the archive commit, the parent of the archive commit on `feat/add-c`

#### Scenario: Version check ignores other branches
- **WHEN** `feat/b` committed a version bump and `sw release check` runs for `feat/add-c`, which did not bump
- **THEN** the check reads the version files at the tip of `feat/add-c` and judges only `<main>..<tip of feat/add-c>`

#### Scenario: Branch not given
- **WHEN** `sw review` runs a pre-ship step in a `vcs: gitbutler` project without `--branch`
- **THEN** it stops with a usage error naming `--branch`, and no review runs

#### Scenario: Branch moved after the review
- **WHEN** a pass was recorded for the tip of `feat/add-c`, a fix commit then lands on it, and ship runs the gate with `--branch feat/add-c`
- **THEN** the gate resolves the new tip, finds no record for it, and ship does not push

#### Scenario: Git unchanged
- **WHEN** the pre-ship review runs on the Git backend on `feat/x`
- **THEN** its range and record key name the same commit as `<main>...HEAD` did before this change

### Requirement: On GitButler the settings are those the change branch committed
With `vcs: gitbutler`, the settings SHALL be read only from `sw pr context --branch <b>` right before each use (each `pr.validate` run, the merge settings), and `sw vcs push` SHALL check again. Each SHALL stop with `settings_not_pinned` when the work-tree `openspec/specwright.yaml` differs from the file at the tip of `<b>` (after the merge, with `--after-merge`: that tip while `<b>` exists, else GitButler's target ref), or exists on one side only. Branch reads and commits are not pinned.

#### Scenario: Unassigned edit before ship
- **WHEN** the change branch `feat/add-c` has the settings committed, an unassigned work-tree edit changes `pr.validate`, and ship runs `sw pr context --branch feat/add-c`
- **THEN** it exits 1 with `settings_not_pinned` naming the file, no validate command runs, and ship does not push

#### Scenario: Watch reads merge settings
- **WHEN** an unassigned edit changes `pr.merge` and watch runs `sw pr context --branch feat/add-c`
- **THEN** it exits 1 with `settings_not_pinned`, and no merge setting is reported

#### Scenario: Push with an unpinned edit
- **WHEN** an unassigned edit of the settings exists and `sw vcs push --branch feat/add-c` runs
- **THEN** it exits 1 with `settings_not_pinned`, and nothing is pushed

#### Scenario: Context without the branch
- **WHEN** `vcs` is `gitbutler` and `sw pr context` runs for the merge settings without `--branch`
- **THEN** it exits 2 with a usage error naming `--branch`, and no merge setting is reported

#### Scenario: Feedback or CI fix push in a repo-local project
- **WHEN** a repo-local GitButler project's feedback pass (or watch's CI fix) is about to run `pr.validate` before its push, and an unassigned edit changed `pr.validate`
- **THEN** the skill reads `validate` from `sw pr context --branch feat/add-c`, which exits 1 with `settings_not_pinned`, and the edited validate command never runs

#### Scenario: Cleanup after the merge
- **WHEN** the PR of `feat/add-c` merged, cleanup has pulled, the local branch is gone, and the work-tree settings equal the file at GitButler's target ref
- **THEN** `sw pr context --after-merge --branch feat/add-c` reports `merge` and `delete_branch`, and the remote-branch deletion follows them

#### Scenario: Cleanup with an unpinned edit
- **WHEN** after the merge an unassigned edit sets `delete_branch: true` that the target ref does not have
- **THEN** `sw pr context --after-merge --branch feat/add-c` exits 1 with `settings_not_pinned`, and no remote branch is deleted

#### Scenario: Cleanup after a skipped pull
- **WHEN** `feat/add-c` committed an edit of `openspec/specwright.yaml` and its PR merged, another branch is applied, `sw vcs pull --branch feat/add-c` returned `pull_skipped`, and `delete-branch` returned `left_applied`
- **THEN** `sw pr context --after-merge --branch feat/add-c` reports `merge` and `delete_branch` with no `settings_not_pinned` stop, and the remote-branch deletion follows them

#### Scenario: Settings never committed on the branch
- **WHEN** `openspec/specwright.yaml` exists in the work tree but not at the tip of `feat/add-c`, and ship runs `sw pr context --branch feat/add-c`
- **THEN** it exits 1 with `settings_not_pinned`

#### Scenario: The change commits its own settings edit
- **WHEN** a task of `feat/add-c` edits `openspec/specwright.yaml` and `specwright-commit` runs `sw vcs state --branch feat/add-c` and `sw vcs commit --branch feat/add-c -- openspec/specwright.yaml`
- **THEN** neither stops with `settings_not_pinned`, the edit is committed on `feat/add-c`, and a following `context --branch feat/add-c` passes

#### Scenario: Branch already deleted
- **WHEN** finish cleanup or a gate rollback runs `sw vcs state --branch feat/add-c` after the branch was deleted
- **THEN** it reports the branch as gone, as before, with no `settings_not_pinned` stop

#### Scenario: Pinned settings
- **WHEN** the work-tree settings equal the file at the tip of `feat/add-c`
- **THEN** `push` and `context --branch` run as before

#### Scenario: Git backend
- **WHEN** `vcs` is `git` and the settings file has an uncommitted edit
- **THEN** no `settings_not_pinned` stop is raised

### Requirement: sw vcs keeps vcs.sh's output and exit-code contract
`sw vcs <sub>` SHALL accept the subcommands and options shipped callers pass and SHALL print exactly one JSON document on stdout for each run, with the same parsed fields, error codes and messages as `vcs.sh` for the same inputs, except that the wording of a usage error is free. It SHALL exit 0 on success, 1 on a stop, 2 on a usage error and 3 on a network or fence refusal. An unexpected failure SHALL be the document `"error": "internal_error"` with exit 1, never a stack trace on stdout.

#### Scenario: Unchanged black-box evals pass on sw
- **WHEN** the `evals/vcs` suite and every other suite that runs `sw vcs` run in CI on Linux, Windows and macOS against the `sw` built from the tree
- **THEN** every test passes with its assertions unchanged from before this change, apart from assertions on stdout bytes, which compare the parsed value instead, and on usage wording, which check the `usage` error and exit 2

#### Scenario: Unknown subcommand
- **WHEN** `sw vcs frobnicate --repo <r> --role code` runs
- **THEN** it exits 2 and stdout is one JSON document with `"ok": false` and `"error": "usage"`

### Requirement: sw vcs reads settings and fences identity in process
`sw vcs` SHALL read the backend settings, the main branch and logins, and the GitButler pinned settings in-process, with the rules of `sw pr vcs` and `sw pr context`, starting no `sw pr` process. It SHALL resolve a missing login and run every network command against a github.com remote through the identity fence in its own process, starting no `sw as` and no second `sw`. It SHALL keep the outputs, stops and exit codes it gave before this change.

#### Scenario: Settings read through pr-pair.sh
- **WHEN** `openspec/specwright.yaml` sets `vcs: jj` and `sw vcs state` runs
- **THEN** the backend is `jj`, as `sw pr vcs --code <code>` reports it, and no other `sw` process was started: the same rules run in `sw vcs`

#### Scenario: Unknown backend in the settings
- **WHEN** `openspec/specwright.yaml` sets `vcs: svn`
- **THEN** `sw vcs state` stops with the same `error` as before this change and a `message` naming `svn`, and runs no `git`, `jj` or `but` write

#### Scenario: Scripts installed under a non-UTF-8 directory
- **WHEN** on Linux the skills are installed under a directory whose name holds the byte 0xFF, `openspec/specwright.yaml` sets `vcs: jj`, and `sw vcs state --repo <r> --role code` runs with a UTF-8 `<r>`
- **THEN** stdout is the usual state document with `"backend": "jj"`, no `not_utf8` stop occurs because `sw` reads no scripts directory, and the exit status is 0

#### Scenario: Unpinned settings stop a GitButler push
- **WHEN** `vcs` is `gitbutler`, an unassigned work-tree edit changes `openspec/specwright.yaml`, and `sw vcs push --branch feat/a --login KintsugiBot` runs
- **THEN** it stops with `settings_not_pinned`, naming the file and the ref, with the same exit code as before this change, and nothing is pushed

#### Scenario: Fenced push
- **WHEN** origin's fetch URL is on github.com and `sw vcs push --branch feat/a --login KintsugiBot` runs on Git
- **THEN** `git push` runs in the repo with KintsugiBot's verified token and the fence's transport settings, receives the same argument values as before this change, and no second `sw` and no `bash` process started

#### Scenario: Refused fence
- **WHEN** origin's push URL is `https://tok@github.com/o/r.git` and `sw vcs push --branch feat/a --login KintsugiBot` runs on Git, jj or GitButler
- **THEN** the document has `"error": "fence_failed"`, a `message` that starts with `as.sh:` and masks the userinfo as `***`, the exit status is 3, and no push ran

#### Scenario: Login resolved in process
- **WHEN** origin is on github.com, the active gh account is KintsugiBot, and `sw vcs fetch-main --repo <r> --role code` runs without `--login`
- **THEN** the fetch runs as KintsugiBot, the document reports the fetched `ref`, and no second `sw` process started

#### Scenario: No gh account to resolve
- **WHEN** origin is on github.com, no gh account is logged in, and `sw vcs fetch-main --repo <r> --role code` runs without `--login`
- **THEN** the document has `"error": "fence_failed"` with the fence's message, the exit status is 3, and no fetch ran

#### Scenario: Store without a Specwright version
- **WHEN** a planning store whose origin is on github.com has no `openspec/.specwright/VERSION`, and `sw vcs pull --repo <store> --role store --code <code> --branch main --login store-bot` runs, with `<code>`'s `VERSION` matching the running `sw`
- **THEN** the version check reads `<code>`'s `VERSION`, the pull runs in the store as store-bot, and the document is not `sw_mismatch`

#### Scenario: Fenced commands stay unbounded
- **WHEN** `SPECWRIGHT_NET_DEADLINE` is 1 and a fenced `git fetch` against github.com takes 3 seconds before it succeeds
- **THEN** the document reports success, with no `deadline_exceeded`, while the fence's gh credential and identity lookups keep their own deadline

#### Scenario: Non-GitHub remote runs unfenced
- **WHEN** origin's fetch URL is not on github.com and `sw vcs push --branch feat/a` runs
- **THEN** `git push` runs with the caller's environment and no fence lookup, and a failure is `git_network_error` with exit 3

