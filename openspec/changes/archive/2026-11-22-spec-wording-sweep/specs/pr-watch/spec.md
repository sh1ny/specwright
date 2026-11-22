# Spec Delta

## MODIFIED Requirements

### Requirement: The newest watcher owns a PR
Each `sw pr snapshot --wait` SHALL claim ownership of its PR when it starts. Only the most recent claim SHALL own the PR. A watcher that no longer owns its PR SHALL exit 4 before its next poll. A watcher that exits SHALL give up only its own claim, so its exit never ends a newer watcher's ownership, whatever the order of the two watchers' steps.

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

### Requirement: The watch timeout is elapsed time
`sw pr snapshot --wait` SHALL measure `--timeout` as elapsed time from its start, polling included, and SHALL NOT sleep past it. Each poll, the first snapshot included, SHALL have one 120-second deadline for all its commands, so the timeout is reported within 130 seconds of passing (10 for process start and kill). A hung poll SHALL NOT block that report or the ownership checks before each poll and before the report.

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
With `--until attention`, `sw pr snapshot --wait` SHALL keep waiting while the snapshot differs from its first good snapshot only in checks or merge state, a CI check (`checks.ci_pending` above 0) is still pending, no check newly fails, and the merge state is not `DIRTY`. Any other difference SHALL wake `changed`. The output SHALL add `filtered`, the number of skipped polls. `incomplete`, `timeout` and ownership SHALL work as without the flag.

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
- **THEN** `sw pr snapshot` exits 2 with a message naming `--until`, and makes no `gh` call

### Requirement: Watch waits for attention
Watch SHALL run each of its waits with `--until attention`. A wait SHALL use `--timeout 1800`, except when the PR's latest snapshot meets every ready condition but the quiet window: then it SHALL use `pr.settle` in seconds (default `5m`). An archive head under "An archive-only head needs no further quiet window" SHALL first wait for the rest of `pr.settle` since its push. Any `timeout` wake SHALL count as the quiet window for the ready rule, even when it skipped check progress.

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

#### Scenario: Not yet ready
- **WHEN** CI is still running and a required reviewer is `waiting`
- **THEN** watch waits with `--timeout 1800`, not `pr.settle`

#### Scenario: Bad settle value
- **WHEN** `pr.settle` is `soon`, or a duration under `1m` or over `1h`
- **THEN** `sw pr context` prints `settings_problem` naming `pr.settle`, and watch starts no wait

### Requirement: The quiet window is main's
Watch SHALL take `pr.settle` from `sw pr policy` (the default branch's value), never from the PR branch or the work tree. `policy` SHALL compare `pr.settle` between main and the head like the other policy keys, so a PR that changes it is a difference the user confirms before an agent merge.

#### Scenario: PR shortens the window
- **WHEN** main has `pr.settle: 30m` and the PR branch sets `pr.settle: 1m`
- **THEN** watch's settle wait uses 1800 seconds, and `policy` lists `pr.settle` in `drift` with 1800 and 60

#### Scenario: Default written out
- **WHEN** main has no `pr.settle` and the head sets `pr.settle: 5m`
- **THEN** `policy` reports no difference

### Requirement: Ready accepts an unstable merge state once CI is done
Ready SHALL accept `merge_state` CLEAN, or UNSTABLE when no check fails and `checks.ci_pending` is 0. `sw pr pair-state` SHALL apply the same rule.

#### Scenario: Pending check makes the merge state unstable
- **WHEN** CI passed, the only pending check is an advisory reviewer's named check that timed out, and `merge_state` is UNSTABLE
- **THEN** that does not keep the PR from ready

#### Scenario: Snapshot without ci_pending
- **WHEN** `merge_state` is UNSTABLE and the snapshot has no `checks.ci_pending`
- **THEN** the PR is not ready
