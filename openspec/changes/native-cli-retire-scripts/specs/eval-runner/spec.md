# Spec Delta

## ADDED Requirements

### Requirement: Suites call sw through one eval helper
Evals SHALL run every Specwright command through a shared helper under `evals/` that starts the binary named by `SPECWRIGHT_SW` with its arguments as a list. They SHALL start no shipped script and load no file from `skills/*/scripts/`. A fixture project that runs a project command SHALL carry an `openspec/.specwright/VERSION` that equals the version the binary under test reports.

#### Scenario: A test runs a project command
- **WHEN** a suite's test runs `vcs state` in a fixture project through the helper
- **THEN** the helper starts `SPECWRIGHT_SW` with `vcs state` and the test's arguments, the fixture's `VERSION` equals that binary's version, and the command prints its state document

#### Scenario: No scripts in the tree
- **WHEN** CI runs every suite on a tree with no `skills/*/scripts/` directory
- **THEN** no test fails or skips for a missing script, and no test starts a `.sh` or `.py` file under `skills/`

### Requirement: Recording shells are not shells an eval starts
A recording `bash` or `sh` that an absence eval puts first on `PATH` (on Windows a `.cmd` wrapper beside its script) SHALL be exempt from the rule that every bash an eval starts is Git Bash: the eval never starts it, and it records any start by `sw` and exits 1. Everything else such an eval starts by name SHALL still follow that rule.

#### Scenario: The fenced shell control on Windows
- **WHEN** on Windows the absence eval runs `sw as <login> bash -c 'exit 7'` with the recording `bash.cmd` first on `PATH`
- **THEN** the recorder logs one start and exits 1, the test passes, and the bash-resolution check reports no violation for it

### Requirement: Frozen-oracle evals are migrated before the cutover
Every eval that runs a frozen script, a shim or the shipped scripts directory SHALL be moved, in the commits before the cutover, to one of: recorded CLI runs of the frozen side; recorded state in both directions; or outcome checks that run what `sw` prints. A CI check SHALL then fail on any eval naming a removed script.

#### Scenario: Feedback records both ways after the cutover
- **WHEN** the feedback-record interoperability cases run on the script-free tree
- **THEN** the native reader resumes from the recorded bytes the frozen writer produced; a native-written record is UTF-8 with LF line ends, its generated owner id, write time, checkout and host are checked for form and for their relation to the run, and its other parsed fields equal the frozen-reader-accepted fixture once those are normalized; and no case starts a frozen script

#### Scenario: Finish parity becomes outcome checks
- **WHEN** the finish and GitButler undo parity cases run on the script-free tree
- **THEN** each runs the printed `steps` and checks the resulting refs, index and files, each refusal case checks its error and exit status, and none compares a document with the frozen planner's

#### Scenario: An eval left on a removed script
- **WHEN** after the cutover an eval still copies or runs `vcs.sh`, `as.sh`, `sw-path.sh`, `bounded.py` or a frozen script that needs them
- **THEN** the CI check fails, naming the eval file and the script

## MODIFIED Requirements

### Requirement: A stopped test file's nested sessions are stopped too
The runner SHALL start and stop test files through its own process helper under `evals/`, loading no file from `skills/`. When it stops a test file (timeout, interrupt, or the leftover sweep after the file exits), it SHALL also stop every process group that the file or its descendants started through that helper or `sw run --bounded`, on Linux, macOS and Windows. Outside the runner, `sw run --bounded` SHALL start and stop processes as before.

#### Scenario: Timed-out file with a nested bounded session
- **WHEN** a test file starts a sleeper through `sw run --bounded` (its own session on POSIX) and is still running at `--timeout 4`
- **THEN** the runner reports `timeout after 4 s`, and once it exits neither the file's process nor the sleeper is alive

#### Scenario: Interrupted run
- **WHEN** the run is interrupted while a file holds a nested bounded session
- **THEN** the sleeper is no longer alive when the runner exits

#### Scenario: Outside the runner
- **WHEN** `sw pr` runs a `gh` call through its bounded helper with no runner around it
- **THEN** no spawn record is written, and the call's process is its own session as before

#### Scenario: No shipped bounded.py
- **WHEN** the runner runs a suite in a tree with no `skills/specwright-pr/scripts/bounded.py`
- **THEN** it starts, times out and stops test files as above, and its own process helper is the one it loads
