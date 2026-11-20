## ADDED Requirements

### Requirement: Windows lock creation retries a transient denial
On Windows, taking a feedback record lock whose exclusive create is refused with access denied or a sharing violation while nothing exists at the path SHALL be retried, at most 5 times 20 ms apart; publication's exclusive create SHALL NOT be retried.

#### Scenario: A denial that clears within the retry window
- **WHEN** on Windows a lock create is refused with access denied while nothing exists at the path, and a later create within the 5 retries succeeds
- **THEN** the call holds the lock

#### Scenario: A lock taken by another call during the retries
- **WHEN** on Windows a lock create is refused with access denied while nothing exists at the path, and a later create within the 5 retries fails because the lock file now exists
- **THEN** the call reports record_busy without changing the record

#### Scenario: A denial that persists
- **WHEN** on Windows every lock create, the first and all 5 retries, is refused with access denied and nothing exists at the path after any of them
- **THEN** the call reports that file error, not record_busy, and leaves the record unchanged

#### Scenario: Publication is not retried
- **WHEN** on Windows the publication fallback's exclusive create is refused with access denied and nothing exists at the path
- **THEN** the error is reported at once, as before, with no retry

### Requirement: A PR call's new helper refusal keeps its exit with a fixed diagnostic
On Windows, when a `sw pr reply` or `sw pr snapshot` `gh` call is refused by a launch check this change adds (such as a helper line over the limit), the command SHALL report `cannot start the helper: its command line is too long` where the OS text of the failed start was, with the same exit. An older check SHALL keep its diagnostic (`unrepresentable command line` or `unsafe batch argument`). Where this differs from the two PR parity requirements, it SHALL take precedence.

#### Scenario: A reaction whose gh line fits only without the helper
- **WHEN** on Windows `sw pr reply ... react` reaches its pending check with a `gh` line that fits alone but not behind the helper
- **THEN** neither the helper nor `gh` starts, the fixed diagnostic is relayed on stderr, and the reply exits 127 as before this change

#### Scenario: A snapshot query that fits only without the helper
- **WHEN** on Windows a `sw pr snapshot` GraphQL `gh` line fits alone but not behind the helper
- **THEN** neither the helper nor `gh` starts, and the snapshot relays the fixed diagnostic where it relayed the OS text, with the same exit

#### Scenario: A PR call refused by an older check
- **WHEN** on Windows a reply or snapshot `gh` line is over 32,767 visible units as given or once `gh` resolves to a native executable
- **THEN** the command reports `unrepresentable command line` as before this change; a resolved line of exactly 32,767 units is a new refusal and reports the fixed diagnostic

#### Scenario: A PR call whose batch payload is too long
- **WHEN** on Windows `gh` resolves to a `.cmd` shim and the call's batch payload is over 8,191 units
- **THEN** the command reports `unsafe batch argument` as before this change

### Requirement: Fixed snapshot defects are exceptions to the scripts' contract
The three requirements below fix defects `sw pr snapshot` kept from `pr-snapshot.sh`. Where they differ from "sw pr snapshot and sw pr reply keep the scripts' contracts" or from "PR snapshots and replies run in the project's sw", they SHALL take precedence for `sw pr snapshot` only. Every other output, except the new helper refusal above, still follows both requirements and the frozen oracle records.

#### Scenario: A fixed case differs from its record
- **WHEN** the parity eval runs a case whose output one of these fixes changes
- **THEN** that case is listed as a difference and its new outcome is asserted by its own test, while the frozen record is left unchanged

#### Scenario: An unaffected case still matches its record
- **WHEN** the parity eval runs any other snapshot case
- **THEN** its exit status, stdout and stderr match the frozen record as before

### Requirement: sw pr snapshot reads --timeout as decimal seconds
`sw pr snapshot --timeout` SHALL take a whole number of seconds written in ASCII decimal digits, from 0 to 9223372036854775807, so every digit string accepted now still is; leading zeros SHALL be read as decimal. The value SHALL be checked when the options are read. Any other value SHALL be a usage error: exit 2, a stderr line naming `--timeout` and the value, and no `gh` call.

#### Scenario: A leading zero
- **WHEN** `sw pr snapshot 12 --wait --until attention --timeout 08 --interval 2` runs under a controlled clock, with polls that take no time and nothing changing
- **THEN** the wake is `timeout` once the clock reaches 8 seconds, after the polls at 2, 4, 6 and 8 seconds, with no error on stderr

#### Scenario: A value that is not a number
- **WHEN** `sw pr snapshot 12 --wait --until attention --timeout abc` runs, or the value is `+5`, `-3` or `0x10`
- **THEN** it exits 2, stderr names `--timeout` and the value, no wake document is printed and no `gh` call is made

#### Scenario: A value out of range
- **WHEN** `sw pr snapshot 12 --wait --until attention --timeout 9223372036854775808` runs, or the value is `99999999999999999999`
- **THEN** it exits 2 naming `--timeout` and the value, before any `gh` call

#### Scenario: Large values stay accepted
- **WHEN** `sw pr snapshot 12 --wait --until attention --timeout 2147483648 --interval 2` runs under a controlled clock, with nothing changing, and again with `--timeout 9223372036854775807`
- **THEN** neither reports a usage error, and each runs its first poll

### Requirement: sw pr snapshot names a material file it cannot write
When `sw pr snapshot` cannot write the reviewer evaluator's material file, the poll SHALL fail with exit 1 and a stderr line naming the file and the operating system's reason, where it now fails with nothing on stderr.

#### Scenario: The material file cannot be written
- **WHEN** the write of the snapshot's material temp file fails
- **THEN** the poll fails with exit 1 and stderr names that path and the reason

#### Scenario: Material file written
- **WHEN** the material file can be written
- **THEN** nothing about it is printed on stderr

### Requirement: Snapshot logs keep the order their output arrived in
`sw pr snapshot --logs` SHALL read the failed job's log call with its stdout and stderr merged in the order their output reached `sw`, then keep the last 80 lines of that merged output. Output written on one stream after a pause in which the other stream's earlier output was delivered SHALL follow that output; writes close together MAY interleave in either order, even inside a line. The merged call SHALL accept at most 32 MiB from both streams together.

#### Scenario: stderr that arrives partway through the log
- **WHEN** the failed-log call's output reaches `sw` as 50 stdout lines, then one stderr line, then 50 more stdout lines, each delivered after the one before it
- **THEN** the merged output has 101 lines, the tail is its last 80, the stderr line is line 30 of the tail, and stdout line 100 is its last line

#### Scenario: A line split across chunks
- **WHEN** a stdout line reaches `sw` in two chunks and a stderr chunk arrives between them
- **THEN** the merged output holds the stderr bytes between the two parts of that line, which may split a UTF-8 sequence, and the snapshot still exits as it would without the split

#### Scenario: The snapshot keeps the merged order
- **WHEN** the failed-log call's merged output holds a stderr line between two runs of stdout lines, so that separate stdout and stderr buffers would put it last
- **THEN** the snapshot's log tail shows the stderr line between those runs, not at the end

#### Scenario: A long log through the helper
- **WHEN** the failed-log call runs through the bounded helper and writes 101 numbered lines, `line 1` to `line 101`, to stdout
- **THEN** the snapshot's log tail is `line 22` to `line 101`, in order

#### Scenario: Helper protocol bytes never reach the log
- **WHEN** the failed-log call runs through the bounded helper
- **THEN** the merged output holds what the target wrote and never the helper's startup frames

#### Scenario: The log call fails to start
- **WHEN** the failed-log call's target cannot start, or the call is refused before any start
- **THEN** the snapshot shows that call's start-failure text in place of the log, as it does now

#### Scenario: Two streams that fit alone but not together
- **WHEN** the failed-log call writes 20 MiB on stdout and 20 MiB on stderr
- **THEN** the first chunk past 32 MiB is rejected, the call is stopped, no partial log is kept, and the snapshot shows the `response_too_large` limit line in place of the log

#### Scenario: The log call passes a bound
- **WHEN** the failed-log call passes its deadline or output bound
- **THEN** the snapshot shows the limit line in place of the log, as before
