# Proposal

## Why

Five known gaps were filed while M2 shipped (Codex and Kody findings on PRs #73, #79 and #82). Each one leaves a path where Specwright either reports the wrong state or authenticates as the wrong account. This change closes them before M3 builds distribution on top of the same scripts. It is change 1 of **M3 - Distribution** (release 0.4.1) and advances these exit criteria: every issue in the milestone's changes is closed by a merged PR, and each code fix has a regression test in `evals/`; `evals/pr-pair`, `evals/git-workflow` and `evals/review-routes` pass; each change ships as its own release.

## What Changes

- **#75 - finish resume trusts a stale main.** When the newest PR of a change branch has merged and the local branch is gone, finish no longer accepts an archive directory it finds on a stale local `main`. It refreshes `main` first (`git status --porcelain` guard, then a fenced `git pull --ff-only`), then reads the archive fact again before it runs the backstop and counts the repo done. For a store-backed change the re-read applies to the store only; the code repo needs no archive. The `eval-finish-resume-merged-branch-gone` and `eval-finish-resume-squash-merged` evals change with it: the pull is now expected, and a branch deletion still is not.
- **#77 - reused-branch-name wording.** The reused-branch-name check moves ahead of the "none of A, M, B" report. It reads the same `discover` result that rule fetches, so a reused name never ends in "no archive found". The table's "code PR closed unmerged" row defers to that rule, so both name the same PRs.
- **#81 - pre-ship recovery review after the archive commit.** When the change directory has been moved to `<P>/changes/archive/<date>-<change>/`, `review-run.sh` points the reviewer at the archived artifacts instead of the moved active paths. That covers the prompt `run` builds and a new `artifacts` list that `preflight` prints for the subagent dispatch. A recovery review on another machine then reads the governing proposal, design, tasks and specs.
- **#83 - trailing-dot host.** `as.sh` treats `github.com.` (the absolute DNS form) as github.com in the userinfo check and in its credential helper. A URL such as `https://user:tok@github.com./o/r.git` is refused, and a credential-free `github.com.` URL gets the fenced token. `pr-pair.sh` classifies a `github.com.` remote as GitHub in the same way, so that remote is never read unfenced.
- **#84 - enterprise tokens for unfenced store reads.** `as.sh` keeps the caller's `GH_HOST`, `GH_ENTERPRISE_TOKEN` and `GITHUB_ENTERPRISE_TOKEN` before it unsets them. `pr-pair.sh`'s unfenced environment restores them, so a GitHub Enterprise Server store whose credential helper is `gh auth git-credential` can be read by `rounds` and the remote checks. They stay out of every fenced command.
- Release 0.4.1 (patch): `VERSION`, the README badge and the skill `metadata.version` fields.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `change-finish`: a merged PR whose branch is gone is counted done only after `main` is refreshed and still holds the archive (#75); the reused-branch-name check runs before the no-archive report and governs the closed-PR row (#77).
- `github-identity`: the trailing-dot host `github.com.` is github.com for the URL refusal, the credential helper and the GitHub/non-GitHub split (#83); unfenced non-GitHub git calls get back the caller's enterprise host and token variables, while fenced calls still never see them (#84).
- `preship-review`: a recovery pre-ship review after the archive commit reviews against the archived change artifacts (#81).

## Impact

- `skills/specwright-finish/SKILL.md` (Resume section and table).
- `skills/specwright-review/scripts/review-run.sh` (`artifact_paths`, `preflight` output), `skills/specwright-review/SKILL.md` (subagent dispatch passes the artifact paths), `agents/claude/specwright-reviewer.md` and `agents/omp/specwright-reviewer.md` (pre-ship mode reads the paths it is given).
- `skills/specwright-pr/scripts/as.sh` (host match, credential helper, saved originals), `skills/specwright-pr/scripts/pr-pair.sh` (`GH_URL`, `unfenced_env`).
- Tests: `evals/pr-pair/test_as_sh.py`, `evals/pr-pair/test_pr_pair.py`, `evals/review-routes/test_review_run.py`, skill-text tests in `evals/git-workflow` and `evals/pr-pair`, and graded evals in `evals/git-workflow/evals.json` (`eval-finish-resume-merged-branch-gone` and `eval-finish-resume-squash-merged`, whose shared fixture gets a pullable origin and whose grader allows the refresh, and a new stale-main case).
- No new configuration key, no dependency change, no workflow change for an in-flight change.
