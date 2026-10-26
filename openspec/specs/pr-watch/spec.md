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

### Requirement: The watch timeout is elapsed time
`pr-snapshot.sh --wait` SHALL measure `--timeout` as elapsed time from its start, polling included, and SHALL NOT sleep past it. Each poll, the first snapshot included, SHALL have one 120-second deadline for all its commands, so the timeout is reported within 130 seconds of passing (10 for process start and kill). A hung poll SHALL NOT block that report or the ownership checks before each poll and before the report.

#### Scenario: Slow polls count toward the timeout
- **WHEN** a watcher runs with `--timeout 60 --interval 20`, each poll takes 15 seconds, and nothing changes
- **THEN** it reports the timeout after at most 85 seconds, having polled no more than 4 times

#### Scenario: Poll hangs during the watch
- **WHEN** a watcher runs with `--timeout 60`, and every `gh` call after its first snapshot never answers
- **THEN** each poll stops at its 120-second deadline with `deadline_exceeded` named on stderr, and the watcher exits 1 reporting that the last poll failed, no later than 190 seconds after it started

#### Scenario: Takeover after a hung poll
- **WHEN** watcher A's poll hangs on PR 5 and watcher B claims PR 5 meanwhile
- **THEN** once A's poll passes its deadline, A exits 4, before its next poll and before reporting a timeout

#### Scenario: First snapshot hangs
- **WHEN** a watcher runs with `--timeout 30` and every `gh` call of its first snapshot never answers
- **THEN** the first snapshot stops at its 120-second deadline with `deadline_exceeded` named on stderr, and the watcher exits 1 no later than 160 seconds after it started

### Requirement: A wait can skip wakes that are only check progress
With `--until attention`, `pr-snapshot.sh --wait` SHALL keep waiting while the snapshot differs from its first good snapshot only in checks or merge state, a check is still pending, no check newly fails, and the merge state is not `DIRTY`. Any other difference SHALL wake `changed`. The output SHALL add `filtered`, the number of skipped polls. `incomplete`, `timeout` and ownership SHALL work as without the flag.

#### Scenario: A check passes while others run
- **WHEN** a wait with `--until attention` sees one of three pending checks pass, and two are still pending
- **THEN** it keeps waiting, and when it later wakes, `filtered` is at least 1

#### Scenario: The last check finishes
- **WHEN** a wait with `--until attention` sees the last pending check pass
- **THEN** it wakes `changed`

#### Scenario: A check fails
- **WHEN** a wait with `--until attention` sees a check fail that was pending in the baseline, and other checks are still pending
- **THEN** it wakes `changed`

#### Scenario: Feedback arrives during check progress
- **WHEN** a reviewer posts a comment while checks are still pending
- **THEN** the wait wakes `changed`

#### Scenario: A conflict appears
- **WHEN** the merge state turns `DIRTY` while checks are still pending
- **THEN** the wait wakes `changed`

#### Scenario: Unknown mode or no wait
- **WHEN** `--until` is given `quiet`, or `--until attention` is given without `--wait`
- **THEN** `pr-snapshot.sh` exits 2 with a message naming `--until`, and makes no `gh` call

### Requirement: Watch waits for attention
Watch SHALL run each of its waits with `--until attention`. A wake SHALL be handled by the watch rules exactly as before. A `timeout` wake SHALL still count as a full wait with no new activity for the ready rule, even when it skipped check progress.

#### Scenario: Watch's wait command
- **WHEN** the watch text gives the command for step 1
- **THEN** that command contains `--wait` and `--until attention`, and the skill-text test fails if either is missing

#### Scenario: Ready after a quiet wait with a check re-run
- **WHEN** every check passed in the baseline, one is re-run (pass to pending, a filtered poll) and passes again before the timeout, and the snapshot meets every other ready condition
- **THEN** the wait wakes `timeout`, and watch treats it as a full wait with no new activity and reports the PR ready
