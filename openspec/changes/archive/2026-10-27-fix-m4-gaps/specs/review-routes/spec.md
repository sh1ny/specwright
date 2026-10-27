# Spec Delta

## MODIFIED Requirements

### Requirement: The size bound applies to the answer
The 2 MiB output bound SHALL apply to the review's answer, not to a route's event stream: claude's printed output; for codex the text of the last completed `agent_message` item in its `--json` event stream; and for OMP the final message of the last `agent_end` event. A codex stream with no completed `agent_message` item, or an OMP stream with no `agent_end` event, SHALL fail validation.

#### Scenario: Large OMP event stream with a small answer
- **WHEN** an OMP design review's event stream on stdout is 3 MiB and its final `agent_end` message is a 19 KB valid review
- **THEN** the run exits 0 and writes that 19 KB review

#### Scenario: OMP answer over the bound
- **WHEN** an OMP review's final `agent_end` message is larger than 2 MiB
- **THEN** the run exits non-zero with `status: invalid` and `output too large`, and no review file is written

#### Scenario: OMP stream without a final message
- **WHEN** an OMP review exits 0 but its event stream has no `agent_end` event
- **THEN** the run exits non-zero with `status: invalid`, and no review file is written

#### Scenario: Codex answer taken from the event stream
- **WHEN** a codex design review exits 0 after printing two completed `agent_message` items, the second a valid 19 KB review
- **THEN** the run exits 0 and writes that 19 KB review, and no file other than its own work files and the review file was written

#### Scenario: Codex answer over the bound
- **WHEN** a codex review's last completed `agent_message` item holds more than 2 MiB of text
- **THEN** the run exits non-zero with `status: invalid` and `output too large`, and no review file is written

#### Scenario: Codex stream without an answer
- **WHEN** a codex review exits 0 but its event stream has no completed `agent_message` item
- **THEN** the run exits non-zero with `status: invalid` naming the missing answer, and no review file is written

### Requirement: Reviewer output is bounded while the CLI runs
While a reviewer CLI or probe runs, `review-run.sh` SHALL bound its output: stderr 8 MiB; stdout 2 MiB on the claude route (the answer) and 64 MiB on codex and OMP (the event stream holding the answer). No route's answer is read from a file the CLI writes itself. Once one passes its bound, the process tree SHALL be stopped as at the deadline. The run fails with `status: invalid` and `output too large`, naming the stream, and writes no result file and no review record.

#### Scenario: Output within the bounds
- **WHEN** an OMP design review streams 3 MiB of events on stdout and 100 KB on stderr, and ends with a valid 19 KB answer
- **THEN** the run exits 0 and writes that review

#### Scenario: Runaway stdout
- **WHEN** a claude pre-ship review keeps printing to stdout and passes 2 MiB well before `review.timeout`
- **THEN** the reviewer process tree is stopped within 5 seconds of passing the bound, the run exits 3 with `status: invalid` and `output too large` naming stdout, no findings file or pre-ship record is written, and no other route runs

#### Scenario: Runaway stderr
- **WHEN** a codex review prints more than 8 MiB to stderr and nothing on stdout
- **THEN** the reviewer is stopped, the run exits 3 with `status: invalid` naming stderr, and the review file is byte-identical to before

#### Scenario: Codex event stream over the bound
- **WHEN** a codex review keeps printing events and its stdout passes 64 MiB while codex is still running
- **THEN** the reviewer is stopped within 5 seconds of passing the bound, and the run exits 3 with `status: invalid` and `output too large` naming stdout, writing no review

#### Scenario: Codex answer file over the bound
- **WHEN** `review-run.sh` builds the codex command line for a design or pre-ship review
- **THEN** it has `--json` and no `-o` or `--output-last-message` argument, so codex writes no answer file and its answer is bounded as part of stdout

## ADDED Requirements

### Requirement: A reviewer that exits before the deadline is judged by its exit
A reviewer that exits before `review.timeout` SHALL NOT be reported with `status: timeout`, also when a process it started still holds its output open; such a run fails as a reviewer that left its output open. Its exit SHALL be observed when it happens, not at a later poll. A reviewer whose exit is first observed at or after the deadline SHALL be reported with `status: timeout`.

#### Scenario: Exit in the last poll interval with a held pipe
- **WHEN** a codex review with `review.timeout` of 5 seconds, run with the capture loop's wait interval raised to 10 seconds by the test hook, starts a child that keeps its stdout open, and codex exits 0 at an absolute time the test set to 1 second before the run's deadline (measured from before the run starts), its recorded exit time being before that deadline
- **THEN** the run exits 3 with `status: failed` and the message that a process it started kept its output open, not `status: timeout`

#### Scenario: Reviewer held past the deadline
- **WHEN** on POSIX a reviewer is still running at `review.timeout` and the capture loop is held until after the reviewer has exited
- **THEN** the run exits 3 with `status: timeout`, and no review file or record is written

### Requirement: A process a reviewer started is stopped on every platform
When a review run stops a reviewer, or the reviewer exits while a process it started still holds its output, every process the reviewer started SHALL be stopped, on Windows as on POSIX, also when the reviewer itself has already exited. When Windows cannot hold the reviewer's processes together, the run's receipt SHALL say so and the tree SHALL be stopped from the reviewer's process as before.

#### Scenario: No job object on Windows
- **WHEN** on Windows the test hook makes job creation fail, and a reviewer runs past `review.timeout`
- **THEN** the run exits 3 with `status: timeout`, the reviewer's process is no longer running, and the receipt has `process_group: none` with the reason

#### Scenario: Orphan holding the pipe on Windows
- **WHEN** on Windows a reviewer starts a child that keeps its stdout open and sleeps for an hour, and the reviewer exits 0
- **THEN** the run fails within 10 seconds of the reviewer's exit, and the child's process is no longer running

#### Scenario: Reviewer stopped at the deadline with a grandchild
- **WHEN** a reviewer starts a child that starts a grandchild, all three sleep, and `review.timeout` passes
- **THEN** the run exits 3 with `status: timeout`, and neither the child nor the grandchild is still running
