# Spec Delta

## MODIFIED Requirements

### Requirement: The archive head gets no new review round
With `pr.review_after_archive` `false` (the default), after a change's archive commit is pushed, watch SHALL post no review request and SHALL count each required reviewer's report on the previous head as valid for the archive head, provided the archive commit is the only commit after that head and touches only the change's archive paths and the main specs it synced.

#### Scenario: Archive pushed after a clean review
- **WHEN** a required reviewer with a `request` reported on head `h1` with no findings, and watch pushes the archive commit `h2` whose parent is `h1`
- **THEN** no review request is posted on `h2`, and readiness of `h2` does not wait for that reviewer, only for CI, mergeability and new feedback

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

### Requirement: A wait can skip wakes that are only check progress
With `--until attention`, `pr-snapshot.sh --wait` SHALL keep waiting while the snapshot differs from its first good snapshot only in checks or merge state, a CI check (`checks.ci_pending` above 0) is still pending, no check newly fails, and the merge state is not `DIRTY`. Any other difference SHALL wake `changed`. The output SHALL add `filtered`, the number of skipped polls. `incomplete`, `timeout` and ownership SHALL work as without the flag.

#### Scenario: A check passes while others run
- **WHEN** a wait with `--until attention` sees one of three pending CI checks pass, and two are still pending
- **THEN** it keeps waiting, and when it later wakes, `filtered` is at least 1

#### Scenario: The last check finishes
- **WHEN** a wait with `--until attention` sees the last pending CI check pass
- **THEN** it wakes `changed`

#### Scenario: CI finishes before the reviewer's check
- **WHEN** a wait with `--until attention` sees the last CI check pass while a reviewer's named check is still pending
- **THEN** it wakes `changed`

#### Scenario: Only a reviewer's check is pending
- **WHEN** no CI check is pending, a reviewer's named check is pending, and that check's state is the only difference from the baseline
- **THEN** the wait wakes `changed`

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
Watch SHALL run each of its waits with `--until attention`. A wait SHALL use `--timeout 1800`, except when the PR's latest snapshot meets every ready condition but the quiet window: then it SHALL use `pr.settle` in seconds (default `5m`). An archive head under "An archive-only head needs no further quiet window" SHALL first wait for the rest of `pr.settle` since its push. Any `timeout` wake SHALL count as the quiet window for the ready rule, even when it skipped check progress. Ready SHALL accept `merge_state` CLEAN, or UNSTABLE when no check fails and `checks.ci_pending` is 0.

#### Scenario: Watch's wait command
- **WHEN** the watch text gives the command for step 1
- **THEN** that command contains `--wait` and `--until attention`, names `--timeout 1800`, `--timeout <pr.settle in seconds>` and the archive head's `--timeout <rest of pr.settle since the push>` with the condition for each, and the skill-text test fails if any is missing

#### Scenario: Ready after a quiet wait with a check re-run
- **WHEN** every check passed in the baseline, one is re-run (pass to pending, a filtered poll) and passes again before the `pr.settle` timeout, and the snapshot meets every other ready condition
- **THEN** the wait wakes `timeout`, and watch treats it as the quiet window and reports the PR ready

#### Scenario: Default settle window
- **WHEN** `pr.settle` is not set and a PR's snapshot meets every ready condition but the quiet window
- **THEN** watch waits with `--timeout 300`, and reports the PR ready on a `timeout` wake with nothing new, without a 30-minute wait

#### Scenario: Long wait ends quiet
- **WHEN** a wait with `--timeout 1800` wakes `timeout` and its snapshot meets every other ready condition
- **THEN** watch reports the PR ready without a further `pr.settle` wait

#### Scenario: Pending check makes the merge state unstable
- **WHEN** CI passed, the only pending check is an advisory reviewer's named check that timed out, and `merge_state` is UNSTABLE
- **THEN** that does not keep the PR from ready

#### Scenario: Not yet ready
- **WHEN** CI is still running and a required reviewer is `waiting`
- **THEN** watch waits with `--timeout 1800`, not `pr.settle`

#### Scenario: Bad settle value
- **WHEN** `pr.settle` is `soon`, or a duration under `1m` or over `1h`
- **THEN** `pr-pair.sh context` prints `settings_problem` naming `pr.settle`, and watch starts no wait

## ADDED Requirements

### Requirement: An advisory reviewer's named check stops blocking once it reported
A check SHALL belong to a configured reviewer only when its name is that reviewer's `report.check`. A pending check of an advisory reviewer that reported or timed out SHALL count in `checks.advisory_pending`, not `checks.pending`. The snapshot SHALL also give `checks.ci_pending`: the pending checks that belong to no configured reviewer.

#### Scenario: Advisory reviewer timed out with its check pending
- **WHEN** advisory reviewer `check-bot` (timeout 15m, `report.check: Bot Code Review`) has that check still pending 16 minutes after the head was pushed
- **THEN** `checks.pending` leaves that check out, `checks.advisory_pending` is 1, and `checks.ci_pending` leaves it out

#### Scenario: Required reviewer's check pending
- **WHEN** required reviewer `check-bot` with `report.check: Bot Code Review` has that check pending
- **THEN** it counts in `checks.pending` and not in `checks.ci_pending`

#### Scenario: Shared app
- **WHEN** reviewer `github-actions` has no `report.check`, and CI checks from app `github-actions` are pending
- **THEN** they count in `checks.pending` and `checks.ci_pending`, as any CI check

#### Scenario: Bot that is not configured
- **WHEN** a pending check comes from app `other-bot`, which is not in `pr.reviewers`
- **THEN** it counts in `checks.pending` and `checks.ci_pending`

### Requirement: An archive-only head needs no further quiet window
When reports carry over to an archive head, watch SHALL judge it ready, with no further quiet window, once the snapshot's `now` is at least `pr.settle` after the head's cutoff and it is mergeable, `merge_state` is CLEAN or UNSTABLE, `checks.ci_pending` is 0, no check fails and no feedback is new. Before that time, or while not ready, watch SHALL wait with `--until attention` (timeout: the rest of `pr.settle`, then 1800) and judge each wake, `timeout` included, by the same rule.

#### Scenario: CI already green
- **WHEN** a snapshot taken `pr.settle` after the archive head's push shows every CI check passed, the PR mergeable with `merge_state` UNSTABLE, and no new feedback, while advisory reviewer `check-bot`'s named check is still pending
- **THEN** watch reports the archive head ready from that snapshot and starts no further wait

#### Scenario: Snapshot before CI exists
- **WHEN** the archive head's first snapshot, taken 20 seconds after the push, shows no checks at all
- **THEN** watch does not report it ready, and waits until `pr.settle` after the push before judging it again

#### Scenario: CI still running
- **WHEN** a snapshot taken after `pr.settle` since the push shows a pending CI check
- **THEN** watch waits, and reports ready on the wake where `checks.ci_pending` reached 0 with no failure and no new feedback, without a further quiet window

#### Scenario: Feedback on the archive head
- **WHEN** a new review comment appears on the archive head
- **THEN** the archive head is not ready, and watch runs feedback as for any head

#### Scenario: Failing CI on the archive head
- **WHEN** a CI check fails on the archive head
- **THEN** the archive head is not ready, and watch handles the failure as for any head

### Requirement: An announced review can extend the wait
When a reviewer counts as `reported` only `by: output` and watch judges from its `evidence` that the output only announces a review, watch SHALL treat that reviewer as waiting until its `timeout` has passed by the snapshot's `now`, and after it as `timed_out`. Watch SHALL NOT treat as reported a reviewer the snapshot reports `waiting` or `timed_out`.

#### Scenario: Announcement only
- **WHEN** a required reviewer's only evidence on the head is a comment `Review in progress`, and its timeout has not passed
- **THEN** watch does not report the PR ready and waits again

#### Scenario: Timeout passed after an announcement
- **WHEN** the same reviewer posts nothing more and its timeout passes by the snapshot's `now`
- **THEN** watch treats it as a required reviewer that timed out: the PR is not ready, watch reports `<login> announced a review on <head> but posted no result` and asks, and sends no merge request
