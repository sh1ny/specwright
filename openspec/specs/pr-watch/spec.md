# pr-watch Specification

## Purpose

Keeps background PR watching owned by exactly one watcher per pull request on a machine, so a handover between watchers never leaves a PR unwatched and two PRs never share an owner.

## Requirements

### Requirement: The newest watcher owns a PR
Each `pr-snapshot.sh --wait` SHALL claim ownership of its PR when it starts. Only the most recent claim SHALL own the PR. A watcher that no longer owns its PR SHALL exit 4 before its next poll. A watcher that exits SHALL give up only its own claim, so its exit never ends a newer watcher's ownership, whatever the order of the two watchers' steps.

#### Scenario: Newer watcher takes over
- **WHEN** watcher A is waiting on PR 5 and watcher B starts `--wait` on PR 5
- **THEN** A exits 4 before its next poll, and B keeps polling

#### Scenario: Cleanup interleaved with a takeover
- **WHEN** watcher A begins its exit cleanup, watcher B claims PR 5 before A's cleanup ends, and A's cleanup then finishes
- **THEN** B still owns PR 5, B's next poll runs, and B does not exit 4

#### Scenario: Two watchers claim at once
- **WHEN** watchers B and C claim PR 5 at the same moment
- **THEN** exactly one of them keeps polling after the next poll, and the other exits 4

#### Scenario: Owner crashed
- **WHEN** the owning watcher was killed without its cleanup, and a new watcher starts on the PR
- **THEN** the new watcher owns the PR and polls

### Requirement: Watch keys are unique per repository and PR
The ownership key SHALL keep the repository owner, the repository name and the PR number apart, compared without regard to case, so watchers of two different PRs never share a claim.

#### Scenario: Hyphenated owners and names
- **WHEN** one watcher waits on `acme-tools/widget#5` and another on `acme/tools-widget#5`
- **THEN** both keep polling, and neither exits 4

#### Scenario: Same PR spelled with different case
- **WHEN** one watcher waits on `Acme/Widget#5` and a newer one on `acme/widget#5`
- **THEN** the older watcher exits 4 before its next poll

#### Scenario: State directory cannot be created
- **WHEN** the watch state directory cannot be created
- **THEN** the watcher polls without ownership, as in 0.1.10, and reports on stderr that ownership is off

### Requirement: The archive head gets no new review round
With `pr.review_after_archive` `false` (the default), after a change's archive commit is pushed, watch SHALL post no review request and SHALL count each required reviewer's report on the previous head as valid for the archive head, provided the archive commit is the only commit after that head and touches only the change's archive paths and the main specs it synced.

#### Scenario: Archive pushed after a clean review
- **WHEN** Codex reported on head `h1` with no findings, and watch pushes the archive commit `h2` whose parent is `h1`
- **THEN** no `@codex review` comment is posted on `h2`, and readiness of `h2` does not wait for Codex, only for CI, mergeability and new feedback

#### Scenario: Setting turned on
- **WHEN** `pr.review_after_archive` is `true` and watch pushes the archive commit
- **THEN** review requests are posted again on the archive head and watch waits for the required reviewers, as in 0.1.13

#### Scenario: Archive commit touches other files
- **WHEN** the archive commit also changes a file outside `<P>/changes/archive/<archived-name>/` and the synced main specs
- **THEN** reports on the previous head do not carry over, and review requests are posted on the archive head

#### Scenario: Another commit after the reviewed head
- **WHEN** a fix commit sits between the last reviewed head and the archive commit
- **THEN** reports do not carry over, and the fix is reviewed as after any fix push

#### Scenario: Branch protection wants a fresh approval
- **WHEN** reports carried over to the archive head, CI passed, and the head is short of ready only because `merge_state` is BLOCKED with `review_decision` `REVIEW_REQUIRED`
- **THEN** watch reports `archive head needs a fresh approval` and asks once whether to post the review requests, and does not keep waiting without asking

#### Scenario: Store-backed archive
- **WHEN** a store-backed change's archive commit is pushed to the store PR, and the store PR's required reviewers reported on its previous head
- **THEN** the same rule applies to the store PR: no request is posted and their reports carry over
