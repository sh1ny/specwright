# Spec Delta

## ADDED Requirements

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
