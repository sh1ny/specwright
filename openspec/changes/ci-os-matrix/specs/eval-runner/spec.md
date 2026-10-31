# Spec Delta

## RENAMED Requirements

- FROM: `### Requirement: CI runs every suite on Linux for each pull request`
- TO: `### Requirement: CI runs every suite on Linux, Windows and macOS for each pull request`

## MODIFIED Requirements

### Requirement: The runner runs each test file as its own process
`python evals/run.py [suite ...]` SHALL discover the `test_*.py` files of each named suite under `evals/` (every suite when none is named) and run each file as its own `python -m unittest` process, up to `--jobs N` at a time (default: the CPU count). It SHALL use only the Python standard library. It SHALL exit 0 only when every file's process exits 0, and 1 otherwise.

#### Scenario: All files pass
- **WHEN** `python evals/run.py git-workflow finish` runs and every test file of both suites passes
- **THEN** it exits 0 and prints one line per suite with its number of files, tests run, tests skipped (from unittest's `skipped=N`, 0 when none) and wall time in seconds

#### Scenario: Skips are counted per suite
- **WHEN** a suite's files pass and two of its tests are skipped
- **THEN** that suite's line names `2 skipped`, and the run still exits 0

#### Scenario: A file fails
- **WHEN** one test file of a named suite has a failing test
- **THEN** the runner prints that file's name, its exit code, the last 200 lines of its output and the path of its full output, which is kept after the run; it still runs the remaining files and exits 1

#### Scenario: Unknown suite
- **WHEN** `python evals/run.py no-such-suite` runs
- **THEN** it exits 2 with an error naming `no-such-suite` and the suites that exist, and runs no test

#### Scenario: A file's process crashes
- **WHEN** a test file's process exits non-zero without unittest output (an import error, a crash)
- **THEN** the runner counts that file as failed, prints its exit code, the last 200 lines of its output (its stderr included) and the kept output's path, and exits 1

#### Scenario: A file times out
- **WHEN** a test file is still running when `--timeout S` seconds have passed
- **THEN** the runner stops that file's whole process tree, reports it as `timeout after S s` with the kept output's path, still runs the other files, and exits 1

### Requirement: CI runs every suite on Linux, Windows and macOS for each pull request
`.github/workflows/evals.yml` SHALL run on every pull request, opened or updated, and on a manual dispatch. It SHALL take the suites from `python evals/run.py --list-suites` and run each with `python evals/run.py <suite>` under `bash` on `ubuntu-24.04`, `windows-latest` and `macos-latest`, one job per suite and OS, with `fail-fast: false` and the OpenSpec CLI in `OPENSPEC_VERSION`. A job SHALL pass only when its setup and its run both succeed. On Windows, every `bash` a job or an eval starts SHALL be Git for Windows' Git Bash; an eval SHALL NOT start bash by its bare name.

#### Scenario: All suites pass
- **WHEN** a pull request is opened or a new commit is pushed to it and every suite passes on every OS
- **THEN** one check per suite and OS reports success on that head, three per suite

#### Scenario: A suite fails
- **WHEN** one suite has a failing test file on Linux
- **THEN** that suite's Linux check fails with the runner's failure output in its log, and the other suites' checks still report their own results

#### Scenario: A suite fails on one OS
- **WHEN** one suite has a failing test file on Windows only
- **THEN** that suite's Windows check fails with the runner's failure output in its log, its Linux and macOS checks and every other job still run to completion and report their own results

#### Scenario: A new suite appears
- **WHEN** a directory with `test_*.py` files is added under `evals/` and the workflow file is not edited
- **THEN** `--list-suites` includes it and the next pull request gets a check for that suite on each of the three OSes

#### Scenario: The suite list cannot be read
- **WHEN** `python evals/run.py --list-suites` exits non-zero in the workflow
- **THEN** the job that lists the suites fails, no suite job starts on any OS, and the pull request shows a failed check rather than a passing one

#### Scenario: Windows runs the POSIX userland of Git Bash
- **WHEN** a Windows job runs a step or a test that starts `bash`, `cygpath` or `sed`
- **THEN** it gets Git for Windows' `bash` and `usr/bin` tools, never another `bash` on the runner (such as the WSL launcher in `System32`), and the job's log names the `bash` it resolved

#### Scenario: A test starts bash by bare name
- **WHEN** an eval under `evals/` starts a process whose argument list begins with the bare name `"bash"`
- **THEN** a runner test fails naming that file and line, since Windows would resolve that name in `System32` before PATH

#### Scenario: A job runs past its timeout
- **WHEN** a suite's run on one OS exceeds that OS's job timeout
- **THEN** that job fails as timed out and the other jobs still report their own results

### Requirement: The instructions say which suites to run when
`AGENTS.md` (which `CLAUDE.md` imports) and `CONTRIBUTING.md` SHALL tell contributors to rely on the CI workflow for every suite during a change, to run locally only the test module being written and the `evals/runner` map test after adding files, and at a milestone close to rely on a green manual run of the workflow on `main`. Neither they nor `README.md` SHALL tell the reader to run a whole suite locally. A test in `evals/runner` SHALL check this.

#### Scenario: Both files carry the rule
- **WHEN** the runner tests run
- **THEN** both `AGENTS.md` and `CONTRIBUTING.md` name the CI workflow `.github/workflows/evals.yml`, the single-module run, the `evals/runner` map test and the milestone close, `CLAUDE.md` holds the line `@AGENTS.md`, and the test passes

#### Scenario: One file drops the rule
- **WHEN** `CONTRIBUTING.md` no longer names the CI workflow, or `AGENTS.md` no longer names the milestone close, or `CLAUDE.md` no longer imports `AGENTS.md`
- **THEN** the instructions test fails naming that file

#### Scenario: A file brings back a local suite run
- **WHEN** `AGENTS.md`, `CONTRIBUTING.md` or `README.md` holds `python evals/run.py --changed main` or `python -m unittest discover evals/` (for example `python -m unittest discover evals/pr-pair`)
- **THEN** the instructions test fails naming that file and the command

### Requirement: Suites that need jj run with a pinned jj in CI
The CI workflow SHALL install the jj release in `JJ_VERSION` on every OS from that OS's release archive (Linux x86_64 musl, macOS arm64, Windows x86_64), check the archive against the SHA-256 pinned for that OS before unpacking or running it, and run every suite with it on PATH. A test that needs jj SHALL skip with `jj not installed` when jj is missing and `SPECWRIGHT_REQUIRE_JJ` is unset, and fail when it is `1`, as CI sets.

#### Scenario: CI run
- **WHEN** a pull request runs the `vcs` suite in CI on any of the three OSes
- **THEN** the job installs that OS's pinned jj archive, `jj --version` prints the version in `JJ_VERSION`, and no test in the suite is skipped for a missing jj

#### Scenario: Checksum mismatch
- **WHEN** the downloaded jj archive on one OS does not match the SHA-256 pinned for that OS
- **THEN** that job's setup step fails before the archive is unpacked or the binary is run, and the job does not report success

#### Scenario: Runner with no pinned archive
- **WHEN** a job runs on an OS and architecture with no pinned jj archive and checksum
- **THEN** the setup step fails naming that OS and architecture, and downloads nothing

#### Scenario: Local run without jj
- **WHEN** a developer runs `python evals/run.py vcs` with no jj on PATH and `SPECWRIGHT_REQUIRE_JJ` unset
- **THEN** each jj test is reported skipped with `jj not installed`, and the run does not count as a failure

#### Scenario: Required but missing
- **WHEN** `SPECWRIGHT_REQUIRE_JJ=1` and no jj is on PATH
- **THEN** each jj test fails, naming the missing jj

### Requirement: Suites that need GitButler run with a pinned `but` in CI
Only Linux jobs of suites with tests that need a real `but` SHALL install `but`: the build in `BUT_VERSION` from its versioned release URL, failing setup unless its SHA-256 equals the pinned hash and `but --version` names that version. Only Linux jobs SHALL set `SPECWRIGHT_REQUIRE_BUT=1`. A test needing `but` SHALL skip with `but not installed` when `but` is missing and that variable is unset, and fail when it is `1`. GitButler tests SHALL run only in scratch repos they create.

#### Scenario: CI run
- **WHEN** a pull request runs the `vcs` suite in CI on Linux
- **THEN** the job downloads the pinned build, its SHA-256 matches, `but --version` names the version in `BUT_VERSION`, and no test in the suite is skipped for a missing `but`

#### Scenario: macOS and Windows jobs
- **WHEN** a pull request runs the `vcs` suite in CI on macOS or Windows
- **THEN** the job installs no `but`, `SPECWRIGHT_REQUIRE_BUT` is unset, each GitButler test is reported skipped with `but not installed`, and the job's result does not depend on them

#### Scenario: Upstream released a new version
- **WHEN** GitButler publishes a newer build than `BUT_VERSION`
- **THEN** the Linux `vcs` job still installs the pinned build and passes setup

#### Scenario: Downloaded bytes differ
- **WHEN** the file at the pinned URL no longer matches the pinned SHA-256
- **THEN** the setup step of the Linux `vcs` job fails before the file is run, and the jobs of the other suites and OSes are unaffected

#### Scenario: Local run without `but`
- **WHEN** a developer runs `python evals/run.py vcs` with no `but` on PATH and `SPECWRIGHT_REQUIRE_BUT` unset
- **THEN** each GitButler test is reported skipped with `but not installed`, and the run does not count as a failure

#### Scenario: Required but missing
- **WHEN** `SPECWRIGHT_REQUIRE_BUT=1` and no `but` is on PATH
- **THEN** each GitButler test fails, naming the missing `but`

## ADDED Requirements

### Requirement: A test skipped on one OS names its issue
An eval test skipped on some OSes only (its skip condition reads `os.name`, `sys.platform` or `platform.system()`) SHALL have a reason that names an issue (`#<number>`) for the gap, or starts with `platform:` when it tests a mechanism that exists only on the other OSes. A test in `evals/runner` SHALL check every `test_*.py` under `evals/`. Skips that depend on a tool or interpreter on PATH are outside this check; the runner's per-suite skip count shows them.

#### Scenario: A per-OS skip with its issue
- **WHEN** a test is skipped when `os.name == "nt"` with a reason that names `#<number>`
- **THEN** the runner test passes

#### Scenario: A mechanism that exists on one OS only
- **WHEN** a test of Windows job objects is skipped elsewhere with the reason `platform: job objects are Windows only`
- **THEN** the runner test passes

#### Scenario: A per-OS skip with neither
- **WHEN** a test file skips a test on one OS with a reason that names no issue and does not start with `platform:`
- **THEN** the runner test fails naming that file and line

#### Scenario: A skip inside an OS branch
- **WHEN** a test calls `self.skipTest(...)` inside an `if` whose condition reads `os.name`, with a reason that names no issue and does not start with `platform:`
- **THEN** the runner test fails naming that file and line
