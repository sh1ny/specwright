# Proposal

## Why

Specwright writes to version control through Git or colocated jj (ADR 0017), so a project that works in a GitButler workspace cannot run the workflow. In GitButler several branches are applied in one working tree at once, Git's HEAD is the synthetic `gitbutler/workspace` commit, and a plain `git commit` or `git checkout` there corrupts the workspace. Today's branch gate, commits and pre-ship ranges all assume HEAD is the change branch. Issue #19 asks for a GitButler backend next to jj; this change delivers it on the seam `add-jj-backend` built.

This change is M5 (Commits and VCS backends), change 7, version 0.12.0. It serves these exit criteria:
- With `vcs: gitbutler`, commits go to the change's own branch, other workspace changes stay untouched and only the change's PR is opened.
- A missing tool, or a repo the backend does not manage, stops before any write.
- With `vcs` unset, the Git flow is unchanged.
- Every code fix has a regression test in `evals/`, and the named suites pass.
- The change ships as its own release, 0.12.0.

## What Changes

- **New setting value.** `vcs: gitbutler` selects GitButler for the code repo. `planning_store.vcs` stays `git | jj`: a `gitbutler` value there stops with `unsupported_vcs`. A GitButler code repo works with a Git or jj store.
- **PR mode only.** With `vcs: gitbutler`, a `finish` other than `pr` stops before any write with `unsupported_combination`. That includes an absent `finish`, which defaults to `local`. GitButler's `but merge` cannot write the `merge: <name>` subject that roadmap and release proofs read, and a local Git merge would leave the workspace.
- **`vcs.sh` gains a `gitbutler` backend** on the same subcommands:
  - **probe** needs `but` 0.23 or newer on PATH and a repo GitButler already manages, with `<main>` as its target. It decides this from Git config and `.git/gitbutler/` before running any `but` command, because any `but` call sets a repo up as a side effect. Specwright never runs `but setup` or `but agent setup` and never sets up or converts a repo.
  - **branch-create** applies a new branch on the target with `but branch new`, next to the branches already applied. The workspace need not be on a bare main: other applied branches and their changes are allowed.
  - **state** reports the change branch by name (applied or not), its tip, the target, and the uncommitted paths split into this change's, unassigned and other branches'. HEAD is never read as the change branch.
  - **commit** runs `but commit -b <branch> -F <msgfile> <paths>`. It names every path and never runs a bare `but commit`, which would take every change in the workspace. It stops when a named path's changes belong to another applied branch.
  - **push** pushes only the change branch, without force, through the fenced Git push, never `but push` (which always force-pushes and pushes the whole stack). **PRs** are opened with `gh pr create --head <branch>` as today, never `but pr`.
  - **pull** runs `but pull` through the identity fence only when no other branch is applied and no linked worktree exists. Otherwise it changes nothing and reports `pull_skipped`, so Specwright never rebases another branch. After a pull, steps read main from the fetched remote main, so a skipped pull never hides a merge.
  - **fetch-main** is the read-only fetch already used on jj (`FETCH_HEAD` only).
  - **delete-branch** removes the merged change branch with `but branch delete`, but only once the commit the GitButler workspace is based on already holds the merge. **merge** stops (PR mode only). **switch** to main is a no-op.
  - **PR-pair cleanup plans** and their fetches go through `vcs.sh` for every backend other than Git, so a GitButler code repo paired with a store gets no Git checkout, pull or branch deletion. The feedback pass ignores other branches' paths, and the unassigned paths that were already present when the pass started.
- **A Git backend in a GitButler workspace stops.** With `vcs` unset in a repo GitButler manages, the probe stops with `gitbutler_workspace` before any write.
- **Reads name the change branch, not HEAD.** The pre-ship review range, its record key and after-archive lookup, task evidence, the reviewer's diff and `release.sh check` read `<main>...<branch tip>`. Each reader takes the branch name and resolves the tip itself. On GitButler, a reader without the branch name stops. On Git and jj that is HEAD, so nothing changes there. On GitButler, HEAD would also pull in the other applied branches.
- **No other Git writes.** On GitButler, Specwright makes no Git write apart from the change branch's push, the read-only fetch and the release tag (ADR 0010's exception). It never stashes: `specwright-debug` asks instead, as on jj.
- **GitButler's own skills.** Specwright does not ship GitButler guidance. The README and install prompt offer `but skill install --path <agent skills dir>` per selected agent, run only on the user's yes. The branch gate notes when `but skill check` reports the skill missing or out of date.
- **Identity fencing.** `as.sh` fences `but pull`, refuses every other `but` subcommand, and refuses options that select another repository.
- **Evals and CI.** The `evals/vcs` suite gains real-`but` tests in scratch repos with a local bare remote and the fake `gh`:
  - other applied branches and unassigned edits stay untouched;
  - only the change's PR opens;
  - the probe and combination stops fire before any write;
  - no Git write happens beyond the named exceptions.

  CI downloads the `but` build pinned in `BUT_VERSION` from GitButler's versioned release URL, and fails unless its SHA-256 matches the pinned hash and `but --version` names that version. Locally the tests are skipped with a named reason when `but` is missing.

## Capabilities

### New Capabilities
- none

### Modified Capabilities
- `vcs-backends`: `gitbutler` as a code-repo backend: the probe and combination stops, workspace state, branch creation, named-path commits, push, guarded pull, deletion, the Git-write boundary, no stash, the undo plan, and change-branch reads instead of HEAD.
- `preship-review`: the pre-ship range is `<main>...` the change branch's tip, which is HEAD on Git and jj.
- `github-identity`: `as.sh` fences `but pull` and refuses every other `but` subcommand and repository-selecting options.
- `eval-runner`: suites that need `but` skip locally with a named reason and fail in CI, where a pinned `but` build is downloaded and checked against its SHA-256.

## Impact

- **Skills:** `specwright-branch` (workspace gate, skill note), `-commit`, `-finish` (PR-only stop, cleanup), `-pr` (push, cleanup), `-roadmap` (pull skip), `-review` (range by branch), `-release` (bump commit), `-debug` (no stash). The reviewer agents (`agents/*/specwright-reviewer.md`) read the diff against the branch, not HEAD.
- **Scripts:**
  - `vcs.sh` gets the gitbutler backend;
  - `pr-pair.sh vcs` accepts `gitbutler` for the code repo, refuses it for the store and refuses it without `finish: pr`;
  - `pr-pair.sh cleanup-plan`, `remote_contains`, `branch-check` and the feedback pass route non-Git backends through `vcs.sh`;
  - `as.sh` fences `but pull`;
  - `review-run.sh`, `release.sh check` and `finish.sh` read the branch tip instead of HEAD;
  - `finish.sh`'s undo plan emits GitButler commands.
- **Config, docs and decisions:** `templates/openspec/specwright.yaml`, README (setup, skill install, hooks that `but commit` does not run), install prompt, architecture index, and a new ADR recording the GitButler backend's boundary.
- **Evals and CI:** `evals/vcs` (GitButler tests), `evals/suites.json`, `.github/workflows/evals.yml` (pinned download, SHA-256 and version check), new `BUT_VERSION`.
- **Unchanged:** the Git and jj flows, which the existing suites guard. OpenSpec itself is not touched (ADR 0001).
- **Out of scope:**
  - `finish: local` on GitButler;
  - a planning store on GitButler;
  - stacked branches, `but pr`, `but push`, `but worktree`;
  - setting up, converting or tearing down a GitButler repo.

## Release Notes

Specwright 0.12.0 adds GitButler as a backend next to Git and jj. With `vcs: gitbutler`, a change gets its own applied branch in a GitButler workspace. Commits name their paths and go only to that branch, only that branch is pushed and gets a PR, and cleanup never rebases another branch. Change ranges (pre-ship review, task evidence, version check) read the branch tip, which is HEAD on Git and jj. Specwright stops before any write when `but` is missing or older than 0.23, or the repo is not GitButler-managed. GitButler needs `finish: pr`. Git stays the default.

### Added
- `vcs: gitbutler` for the code repo: branch, commit, push, PR and cleanup through GitButler 0.23+. Commits name their paths and target the change's branch with `but commit -b`, and other applied branches and unassigned edits are never committed, pushed or rebased (#19).
- Stops before any write: `but` missing or older than 0.23, a repo GitButler does not manage or whose target is not main, GitButler without `finish: pr`, `planning_store.vcs: gitbutler`, and the Git backend in a GitButler workspace (#19).
- `as.sh` fences `but pull` to the run login and refuses other `but` subcommands. The README and install prompt offer GitButler's own agent skills with `but skill install --path`, and the branch gate notes a missing or outdated skill (#19).
- Real-`but` eval tests cover branch targeting, untouched workspace changes, publication scope and the Git-write boundary. CI installs a pinned `but` build and checks its SHA-256 (#19).

### Changed
- The pre-ship review range, its record key, the reviewer's diff and `release.sh check` use the change branch's tip instead of HEAD. This is the same commit on Git and jj (#19).
