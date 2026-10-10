# Spec Delta

## Purpose

Keeps background PR watching owned by exactly one watcher per pull request on a machine, so a handover between watchers never leaves a PR unwatched and two PRs never share an owner.

## ADDED Requirements

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
