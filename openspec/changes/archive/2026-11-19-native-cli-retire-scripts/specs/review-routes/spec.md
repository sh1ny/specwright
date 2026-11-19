# Spec Delta

## MODIFIED Requirements

### Requirement: Review operations run in the project's sw
Each `review-run.sh` subcommand SHALL run as `sw review`, called directly, preserving options, JSON, exits 0/1/2/3, records and state directory. Operations SHALL NOT start Python, bash or shipped scripts for their own work. When the project's `VERSION` is missing or differs from the running `sw`'s version, the command SHALL print one `sw_mismatch` JSON document and exit 1, before any probe and with no fallback. The fixed OMP policy SHALL run inside OMP, not in a separate interpreter process.

#### Scenario: Pre-ship run without Python or bash
- **WHEN** `review-run.sh run --kind preship` runs on Linux, Windows and macOS with failing `python`, `python3`, `bash` and `sh` first on `PATH` for `sw`, and a fake codex reviewer that prints valid findings
- **THEN** the run exits 0, writes the findings and the pre-ship record at the same path as before the port, and none of the failing interpreters was started by `sw`

#### Scenario: Gate reads a record written before the port
- **WHEN** a pre-ship record written by the Python `review-run.sh` exists for the change's current heads, and `review-run.sh gate` runs through `sw`
- **THEN** it prints `status: pass` with the same `heads` and `reviewed_heads`

#### Scenario: VCS backend read in process
- **WHEN** a pre-ship step without `--branch` runs in a code repo whose settings select `vcs: gitbutler`, with no shipped script on disk
- **THEN** it stops with the existing usage error asking for `--branch`, and no `sw vcs` or `sw pr` process starts

#### Scenario: No matching sw
- **WHEN** `sw review select --runtime claude` runs in a project whose `VERSION` names another version than the running `sw`, or has no `VERSION`
- **THEN** it prints one `sw_mismatch` JSON document, exits 1, and starts no reviewer probe
