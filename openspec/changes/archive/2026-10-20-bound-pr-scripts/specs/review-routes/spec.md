# Spec Delta

## ADDED Requirements

### Requirement: Reviewer output is bounded while the CLI runs
While a reviewer CLI or probe runs, `review-run.sh` SHALL watch its output. The bounds are: stderr 8 MiB; stdout 2 MiB on the claude route, where stdout is the answer, and 64 MiB on codex and OMP; codex's answer file 2 MiB. Once one passes its bound, the process tree SHALL be stopped as at the deadline. The run fails with `status: invalid` and `output too large`, naming the stream, and writes no result file and no review record.

#### Scenario: Output within the bounds
- **WHEN** an OMP design review streams 3 MiB of events on stdout and 100 KB on stderr, and ends with a valid 19 KB answer
- **THEN** the run exits 0 and writes that review

#### Scenario: Runaway stdout
- **WHEN** a claude pre-ship review keeps printing to stdout and passes 2 MiB well before `review.timeout`
- **THEN** the reviewer process tree is stopped within 5 seconds of passing the bound, the run exits 3 with `status: invalid` and `output too large` naming stdout, no findings file or pre-ship record is written, and no other route runs

#### Scenario: Runaway stderr
- **WHEN** a codex review prints more than 8 MiB to stderr and nothing on stdout
- **THEN** the reviewer is stopped, the run exits 3 with `status: invalid` naming stderr, and the review file is byte-identical to before

#### Scenario: Codex answer file over the bound
- **WHEN** codex's last-message file passes 2 MiB while codex is still running
- **THEN** the reviewer is stopped, and the run exits 3 with `status: invalid` and `output too large`, writing no review
