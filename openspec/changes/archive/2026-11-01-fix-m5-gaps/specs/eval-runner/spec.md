# Spec Delta

## ADDED Requirements

### Requirement: A stopped test file's nested sessions are stopped too
When the runner stops a test file (timeout, interrupt, or the leftover sweep after the file exits), it SHALL also stop every process group that the file or its descendants started through `bounded.py`, on Linux, macOS and Windows. Outside the runner, `bounded.py` SHALL start and stop processes as before.

#### Scenario: Timed-out file with a nested bounded session
- **WHEN** a test file starts a sleeper through `bounded.spawn` (its own session on POSIX) and is still running at `--timeout 4`
- **THEN** the runner reports `timeout after 4 s`, and once it exits neither the file's process nor the sleeper is alive

#### Scenario: Interrupted run
- **WHEN** the run is interrupted while a file holds a nested bounded session
- **THEN** the sleeper is no longer alive when the runner exits

#### Scenario: Outside the runner
- **WHEN** `pr-pair.sh` runs a `gh` call through `bounded.py` with no runner around it
- **THEN** no spawn record is written, and the call's process is its own session as before
