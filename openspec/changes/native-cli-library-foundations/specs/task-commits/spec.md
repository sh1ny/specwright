## MODIFIED Requirements

### Requirement: sw commit task-cover keeps task-cover.sh's contract
`sw commit task-cover` SHALL accept `task-cover.sh`'s options, honour `TASK_COVER_MAX_COMMITS`, and print a JSON document that parses to the same keys, key order and values for the same inputs, with the same error codes and exit codes 0 to 3. The differences: task and group ids are ASCII digits only, and a task, commit subject, trailer or numbered heading whose group number is beyond 64 bits is ignored. An unexpected failure SHALL print the document `"error": "internal_error"` and exit 1, never a stack trace.

#### Scenario: Unchanged task-cover evals pass on sw
- **WHEN** the `evals/git-workflow` tests of `task-cover.sh` and the `evals/vcs` coverage test run in CI on Linux, Windows and macOS against the `sw` built from the tree
- **THEN** every test passes with its assertions unchanged from before this change, apart from assertions on stdout bytes, which compare the parsed value instead

#### Scenario: Usage error
- **WHEN** `sw commit task-cover` is run without `--change`
- **THEN** it exits 2 and stdout is one JSON document with `"error": "usage"` and the usage line `task-cover.sh` printed before this change, with ` [--code <dir>]` added at its end

#### Scenario: A group number beyond 64 bits is not a task
- **WHEN** a `tasks.md` line reads `- [x] 99999999999999999999.1 Do it`
- **THEN** the line is not a task: it is not in `tasks`, and the command prints a JSON document rather than `internal_error`

#### Scenario: A numbered heading beyond 64 bits is ignored
- **WHEN** a `tasks.md` holds `## 99999999999999999999. Heading` alongside an ordinary group and task
- **THEN** that group is absent from `groups`, the ordinary task keeps its coverage result, and the command prints its normal report rather than `internal_error`

#### Scenario: Task ids are ASCII digits
- **WHEN** a `tasks.md` line reads `- [x] ١.١ Do it` (Arabic-Indic digits)
- **THEN** the line is not a task: it is not in `tasks`, and no group `1` comes from it
