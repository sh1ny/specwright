# Spec Delta

## ADDED Requirements

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
