# Spec Delta

## MODIFIED Requirements

### Requirement: An unreadable commit changes the version only when its parent is not among its versions
In the history walk of `release.sh check --main <ref>`, a commit whose parent is unreadable and on the branch SHALL be a change when it matched a version that parent did not match. Otherwise a commit whose own version is unreadable SHALL be no change when the version it is judged against is among the versions it matched, or is unreadable too. A change SHALL be a bump only when it matched at least one version and each is greater than the version it is judged against, or, when that one is unreadable, than each version it matched.

#### Scenario: Bump reverted through an unreadable version
- **WHEN** the branch bumps 0.4.2 to 0.5.0, a later commit sets `VERSION` back to `0.4.2` twice, a still later one removes the duplicate, and `origin/main` is at 0.5.0
- **THEN** `check --main origin/main` exits 0 and reports version 0.4.2

#### Scenario: Bump reverted between two unreadable versions
- **WHEN** `origin/main` and the merge base are at 0.5.0, one branch commit sets `VERSION` to `0.6.0` twice, a later one sets it to `0.5.0` twice, and a still later one removes the duplicate
- **THEN** `check --main origin/main` exits 0 and reports version 0.5.0

#### Scenario: Unreadable bump reverted by a readable commit
- **WHEN** `origin/main` and the merge base are at 0.5.0, one branch commit sets `VERSION` to `0.6.0` twice, and a later one sets it to `0.5.0` once
- **THEN** `check --main origin/main` exits 0 and reports version 0.5.0

#### Scenario: Unreadable edit that keeps the matched versions
- **WHEN** the merge base is at 0.5.0, one branch commit sets `VERSION` to `0.6.0` twice, a later one adds a third `0.6.0` line, a still later one keeps one line, and the branch then merges `origin/main` at 0.6.0
- **THEN** `check --main origin/main` exits non-zero with `version_not_ahead_of_main`, naming 0.6.0 on the branch and on `origin/main`

## ADDED Requirements

### Requirement: Publish's network commands are bounded
Every `git` or `gh` network command `release.sh` runs SHALL run under ADR 0012's bounds: 120 seconds, or 300 seconds for the paginated closed-PR read, and at most 32 MiB from each command. When one passes a bound, its process tree SHALL be stopped, and `release.sh` SHALL exit 3 with `deadline_exceeded` or `response_too_large` as its `error`, naming the command. It SHALL NOT use a partial answer.

#### Scenario: Remote tags answer in time
- **WHEN** `release.sh untagged` runs and `git ls-remote --tags origin` answers within its deadline
- **THEN** the command lists the untagged versions as before this change, and no limit is named

#### Scenario: Hung tag lookup
- **WHEN** publish runs and `git ls-remote --tags origin` never answers
- **THEN** `release.sh` exits 3 within the deadline plus 10 seconds with `"error": "deadline_exceeded"` naming `git ls-remote`, no tag is created, and no process it started is still running

#### Scenario: Oversized closed-PR read
- **WHEN** store-backed publish reads merged PRs and the paginated `gh api` read prints more than 32 MiB
- **THEN** `release.sh` exits 3 with `"error": "response_too_large"` naming `gh api`, and creates no tag

### Requirement: A cut-off tag push or release creation is decided by a read-back
When the tag push or `gh release create` is stopped by a bound, publish SHALL read back whether it landed (`git ls-remote`, `gh release view`) before it reports. A pushed tag SHALL count as done only when origin's tag is the local tag object at the release commit, else the tag conflict or mismatch stop applies. A release found SHALL count as done. A write not found SHALL be reported as not done with the limit named, and a failed read-back as state unknown.

#### Scenario: Push cut off after it landed
- **WHEN** the tag push passes its deadline after origin received the local `v0.5.0` tag object
- **THEN** publish reports the tag as published, and goes on to create the GitHub release

#### Scenario: Push cut off while another clone's tag won
- **WHEN** the tag push passes its deadline, and the read-back finds `refs/tags/v0.5.0` on origin at the release commit as a different tag object
- **THEN** publish exits 1 with `tag_mismatch` naming both tag objects, and creates no GitHub release

#### Scenario: Push cut off with origin's tag on another commit
- **WHEN** the tag push passes its deadline, and the read-back finds `refs/tags/v0.5.0` on origin at another commit
- **THEN** publish exits 1 with `tag_conflict` naming both commits, and creates no GitHub release

#### Scenario: Release creation cut off before it landed
- **WHEN** `gh release create v0.5.0` passes its deadline and `gh release view v0.5.0` then finds no release
- **THEN** publish exits 3 with `"error": "deadline_exceeded"` naming `gh release create`, and says the tag is on origin and a re-run creates the release

#### Scenario: Read-back fails too
- **WHEN** the tag push passes its deadline and the `git ls-remote` read-back fails
- **THEN** publish exits 3 saying the tag's state on origin is unknown, and creates no GitHub release
