# Spec Delta

## ADDED Requirements

### Requirement: A command that exits before its deadline keeps its result
A bounded network command that exits before its deadline SHALL return its own exit status and output, never `deadline_exceeded`, also when a process it started still holds its output open. Its exit SHALL be observed when it happens, not at a later poll. An exit first observed at or after the deadline SHALL be `deadline_exceeded`.

#### Scenario: Exit just before the deadline with a held pipe
- **WHEN** a bounded command with a 3-second deadline, run with the loop's wait interval raised to 5 seconds by the test hook, starts a child that keeps its stdout open and sleeps, and the command itself exits 0 at an absolute time the test set to 1 second before the run's deadline (measured from before the run starts)
- **THEN** the command's recorded exit time is before the run's deadline, the call returns exit status 0 and the command's output with no limit named, and the child is no longer running

#### Scenario: Exit after the deadline
- **WHEN** a bounded command with a 1-second deadline sleeps for 3 seconds and then exits 0
- **THEN** the call reports `deadline_exceeded` within the deadline plus 10 seconds, and no process it started is still running

### Requirement: A process a network command started is stopped on every platform
When a bounded network command is stopped, or exits while a process it started still holds its output, every process it started SHALL be stopped, on Windows as on POSIX, also when the command itself has already exited. When Windows cannot hold the command's processes together, the run SHALL say so on stderr and stop the tree from the command's process as before.

#### Scenario: No job object on Windows
- **WHEN** on Windows the test hook makes job creation fail, and a bounded command with a 1-second deadline sleeps
- **THEN** the call reports `deadline_exceeded`, the command's process is no longer running, and stderr holds one line saying the run has no job object and naming the reason

#### Scenario: Orphan holding the pipe on Windows
- **WHEN** on Windows a bounded command starts a child that keeps its stdout open and sleeps for an hour, and the command exits 0
- **THEN** the call returns within its grace period plus 5 seconds, and the child's process is no longer running

#### Scenario: Hung command with a grandchild
- **WHEN** a bounded command with a 1-second deadline starts a child that starts a grandchild, and all three sleep
- **THEN** the call reports `deadline_exceeded`, and neither the child nor the grandchild is still running

### Requirement: The deadline override is read one way
`SPECWRIGHT_NET_DEADLINE` SHALL be read by one rule for each command's deadline and for a watch poll's deadline: a non-negative decimal number of seconds, fractions included, that can lower the 120-second deadline and never raise it. A value that is not a non-negative number SHALL leave 120 seconds.

#### Scenario: Fractional override lowers the poll
- **WHEN** a watch poll runs with `SPECWRIGHT_NET_DEADLINE=1.5` and its first `gh` call never answers
- **THEN** the poll reports `deadline_exceeded` within 1.5 seconds plus 10 seconds, and the deadline every command of that poll received was at most 1.5 seconds from the start of the poll

#### Scenario: Invalid override
- **WHEN** a watch poll runs with `SPECWRIGHT_NET_DEADLINE=soon`
- **THEN** the poll's deadline is 120 seconds, as for each command in it

#### Scenario: Override above the default
- **WHEN** a watch poll runs with `SPECWRIGHT_NET_DEADLINE=500`
- **THEN** the poll's deadline is 120 seconds
