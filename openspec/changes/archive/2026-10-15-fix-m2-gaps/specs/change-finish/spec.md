# Spec Delta

## MODIFIED Requirements

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

## ADDED Requirements

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
