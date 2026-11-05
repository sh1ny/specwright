# Spec Delta

## ADDED Requirements

### Requirement: Suites that need sw run against a binary built from the tree in CI
Each CI job of a suite with `sw` tests SHALL build `sw` from the checked-out `cli/` with the Dart SDK `mise.toml` pins, and point `SPECWRIGHT_SW` at that binary. A test that needs `sw` SHALL skip with `sw not built` when `SPECWRIGHT_SW` is unset and `SPECWRIGHT_REQUIRE_SW` is unset, and fail when it is `1`, as CI sets.

#### Scenario: CI run
- **WHEN** a pull request runs the `cli` suite in CI on any of the three OSes
- **THEN** the job builds `sw` from the tree, `SPECWRIGHT_SW` names it, and no test in the suite is skipped for a missing `sw`

#### Scenario: Build fails
- **WHEN** `sw` does not compile in a job
- **THEN** that job's setup step fails and the job does not report success

#### Scenario: Local run without sw
- **WHEN** a developer runs a `cli` test module with `SPECWRIGHT_SW` and `SPECWRIGHT_REQUIRE_SW` unset
- **THEN** each `sw` test is reported skipped with `sw not built`, and the run does not count as a failure

#### Scenario: Required but missing
- **WHEN** `SPECWRIGHT_REQUIRE_SW=1` and `SPECWRIGHT_SW` is unset or names no file
- **THEN** each `sw` test fails, naming the missing binary

### Requirement: A stopped test file's sw process groups are stopped too
On POSIX, when `SPECWRIGHT_TEST_SPAWN_DIR` names a directory, `sw run --bounded` SHALL create an empty file named after each process group it starts in that directory before the command runs, so the runner's existing sweep stops `sw` sessions when it times out, interrupts or finishes a test file. Without the variable it SHALL write nothing.

#### Scenario: Runner timeout during a hung sw test
- **WHEN** the runner stops a `cli` test file on Linux or macOS while `sw` runs a command that hangs with a child
- **THEN** after the sweep no process from that `sw` session is alive

#### Scenario: Variable unset
- **WHEN** `sw run --bounded` runs without `SPECWRIGHT_TEST_SPAWN_DIR`
- **THEN** no file is created anywhere

#### Scenario: Unwritable spawn directory
- **WHEN** `SPECWRIGHT_TEST_SPAWN_DIR` names a directory `sw` cannot write
- **THEN** the command still runs and its result is unchanged

### Requirement: Dart tests run locally only for the module being written
`AGENTS.md` and `CONTRIBUTING.md` SHALL tell contributors to run Dart tests locally only for the test file being written, through the SDK `mise.toml` pins (`mise exec -- dart test <file>`), and to rely on CI for the full Dart test run on the three OSes. Neither SHALL tell the reader to run the whole Dart test set locally. A test in `evals/runner` SHALL check this.

#### Scenario: Both files carry the rule
- **WHEN** the runner tests run
- **THEN** `AGENTS.md` and `CONTRIBUTING.md` each name `mise exec -- dart test` with a single test file and say CI runs the rest

#### Scenario: A file tells the reader to run every Dart test
- **WHEN** `AGENTS.md` or `CONTRIBUTING.md` tells the reader to run `dart test` with no file, or `mise run test`, locally during a change
- **THEN** the runner test fails, naming the file and the line
