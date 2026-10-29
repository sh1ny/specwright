# Proposal

## Why

Specwright writes to version control only through Git, so a project that uses Jujutsu (jj) cannot run the workflow. On a colocated jj repo, Git's HEAD is detached and `git branch --show-current` is empty, so the branch gate, the commit guard and finish all stop or misfire. Git writes there also go behind jj's back. Issue #19 asks for a selectable backend. This change delivers its jj part and leaves a seam that `add-gitbutler-backend` reuses.

This change is M5 (Commits and VCS backends), change 6, version 0.11.0. It serves these exit criteria:
- With `vcs: jj`, branch, apply, archive and finish run on a colocated repo in `local` and `pr` modes, with every write made through jj.
- A missing tool, or a repo the backend does not manage, stops before any write.
- With `vcs` unset, the Git flow is unchanged.
- Every code fix has a regression test in `evals/`, and the named suites pass.
- The change ships as its own release, 0.11.0.

## What Changes

- **New setting.** `vcs: git | jj` in `openspec/specwright.yaml` selects the tool that owns every version-control write in the code repo. It defaults to `git`. `planning_store.vcs` sets the store's backend on its own; it defaults to `git` and is never inherited from the code repo.
- **One backend script.** A new `vcs.sh` in `specwright-pr` owns the write operations and the "current change branch" read for both backends:
  - writes: create a branch, switch to main or a branch, commit named paths, local `--no-ff` merge, delete a merged branch, refresh main, push;
  - every skill that writes through Git calls it instead of `git checkout -b`, `git add`/`commit`, `git merge`, `git branch -d/-D`, `git pull` and `git push`;
  - for Git it runs the commands the skills run today.
- **Probe before any write.** Each repo is probed before its branch is read or anything is written. These stop with a named error before anything is written:
  - `vcs: jj` where `jj` is missing or older than 0.46;
  - `vcs: jj` where the repo has no `.jj/`, or is not colocated (no Git work tree at the same toplevel, which includes a secondary jj workspace);
  - an unknown `vcs` value.

  A repo with `.jj/` left on the Git backend gets a one-line note from the branch gate and keeps working on Git. Specwright never runs `jj git init`, never converts a repo, and never falls back to Git writes.
- **Branches on jj.**
  - A change branch is a jj bookmark. Specwright keeps one rule: the bookmark points at `@-`, Git's HEAD, and the working-copy commit `@` holds only uncommitted edits.
  - Commits use `jj commit <paths> -m`, so other edits in `@` are never swept in, then move the bookmark to `@-`.
  - A local finish makes the merge off to the side with `jj new --no-edit <main> <branch>`, so the first parent is main and the `merge: <name>` proof is unchanged. A conflicted merge is abandoned.
  - Switches, merges and pulls carry the working copy's uncommitted edits onto the target, as Git's checkout does, and put them back when they would conflict.
  - A merged branch is dropped with `jj bookmark forget`, which never marks a remote deletion.
  - Pushes run `jj git push --bookmark <branch>` after a check for conflicted or undescribed commits.
  - Fetches made only to read the remote's main write `FETCH_HEAD` alone, so jj never moves or conflicts a tracked bookmark. Pulls fetch only main through jj, which keeps a change bookmark whose remote branch GitHub deleted at merge.
- **Reads stay Git.** Git reads (logs, trailers, `ls-tree`, ranges ending at `HEAD`) still work on a colocated repo, because jj exports bookmarks to `refs/heads` and HEAD to `@-`. Read-only scripts keep using them; only the branch read (`branch --show-current`) moves to `vcs.sh`.
- **Identity fencing.** `as.sh` fences `jj git push` and `jj git fetch` like `git`. It refuses jj options that select another repository or replace config (`-R`, `--repository`, `--config`, `--config-file`).
- **Release tags stay Git.** jj tags carry no message, and ADR 0010 requires annotated tags, so `release.sh` keeps `git tag -a` and the tag push under `vcs: jj`. This is the one named Git write, and it touches only `refs/tags/<tag>`.
- **Debug never stashes on jj.** jj has no stash. Where `specwright-debug` would stash, it asks the user to set their edits aside or abort.
- **Recovery.** These are recovered from what is on disk, with no new state file:
  - an interrupted commit (bookmark one or more Specwright commits behind `@-`);
  - an interrupted merge (a `merge: <name>` commit not yet on main);
  - a failed push.
- **Evals and CI.**
  - A new `evals/vcs` suite runs real jj against scratch colocated repos, a local bare remote and the fake `gh`, and fails on any Git write other than the tag exception. It covers the backend script, both finish modes, recovery and the probe stops.
  - The CI workflow installs a pinned jj release and runs the suite. Locally the suite is skipped with a named reason when jj is missing.

## Capabilities

### New Capabilities
- `vcs-backends`: selecting the version-control tool per repo, stopping before any write when the tool or repo does not fit, and how branch, commit, merge, push, cleanup and recovery behave on each backend.

### Modified Capabilities
- `github-identity`: `jj git push` and `jj git fetch` are fenced to the run login like `git`, and jj options that select another repository or config are refused.
- `eval-runner`: suites that need jj are skipped with a named reason locally when jj is missing, and fail in CI.

## Impact

- **Skills:** `specwright-branch`, `-commit`, `-finish`, `-pr`, `-roadmap`, `-review` (pre-ship round commits), `-release` (bump commit, tag exception) and `-debug`. Each changes its write steps and its current-branch read.
- **Scripts:**
  - `skills/specwright-pr/scripts/vcs.sh` is new, with `pr-pair.sh vcs` to read the settings;
  - `as.sh` fences jj;
  - `finish.sh` takes its branch from `vcs.sh` and emits jj commands in its undo plan;
  - `pr-pair.sh` emits backend commands in `cleanup-plan` and fetches without moving a remote-tracking ref on jj;
  - `update.sh` accepts a jj store whose Git HEAD is detached;
  - `release.sh` takes `--base <branch>` for its merged-PR lookup when `--main` and `--store-main` are fetched commits.
- **Config, docs and decisions:** `templates/openspec/specwright.yaml` (`vcs`, `planning_store.vcs`), README, architecture index, and new ADR 0017.
- **Evals and CI:** `evals/vcs` (new), `evals/suites.json`, `.github/workflows/evals.yml` (pinned jj install).
- **Unchanged:** the Git flow, which the existing suites and new Git-case tests of `vcs.sh` guard. This includes the push, which keeps today's command and gets no new deadline. OpenSpec itself is not touched (ADR 0001).
- **Out of scope:**
  - GitButler (`add-gitbutler-backend`);
  - jj repos that are not colocated, including secondary jj workspaces;
  - converting or initializing a repo.

## Release Notes

Projects can run the whole Specwright workflow on Jujutsu. Set `vcs: jj` in `specwright.yaml`, and `planning_store.vcs` for a store. Every change write then goes through jj; Git stays the default.

### Added
- `vcs: git | jj` and `planning_store.vcs` settings. On jj, branch, commit, local merge, push and cleanup work through bookmarks, and other edits in the working copy are never committed (#19).
- With `vcs: jj`, a probe stops before any write when jj is missing or older than 0.46, or the repo is not a colocated jj repo (#19).
- `jj git push` and `jj git fetch` run under the fenced GitHub login (#19).
