# Spec Delta

## Purpose

Runs the eval suites as a whole, in parallel, with one pass or fail result and each suite's wall time, and keeps a record of those times so a slowdown is noticed.

## ADDED Requirements

### Requirement: The runner runs each test file as its own process
`python evals/run.py [suite ...]` SHALL discover the `test_*.py` files of each named suite under `evals/` (every suite when none is named) and run each file as its own `python -m unittest` process, up to `--jobs N` at a time (default: the CPU count). It SHALL use only the Python standard library. It SHALL exit 0 only when every file's process exits 0, and 1 otherwise.

#### Scenario: All files pass
- **WHEN** `python evals/run.py git-workflow finish` runs and every test file of both suites passes
- **THEN** it exits 0 and prints one line per suite with its number of files, tests run and wall time in seconds

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

### Requirement: Faster suites keep every test
Each suite SHALL run the same tests after the speed-up as before, with the same assertions: no test is removed, skipped or weakened to save time. Every suite's test count SHALL stay the same, or grow by the regression tests a change adds.

#### Scenario: Counts after the change
- **WHEN** a suite's tests are counted before and after a change that cuts process launches
- **THEN** the count after is at least the count before, and every test name present before is still present

#### Scenario: A shared fixture is not shared state
- **WHEN** two tests copy the same cached fixture repo and one of them commits, tags or deletes a branch in its copy
- **THEN** the other test's copy and the cached original are unchanged

### Requirement: Suite wall times are recorded
`evals/timings.md` SHALL record, for each suite of a change that aims to cut eval time, a before and an after wall time on the same Windows machine with each test count, the source and date of each, the after run's machine, git and Python versions, and whether every test ID from before is still present. The before time MAY be an earlier recorded measurement. The after run SHALL be made with no other load from that work. The after total SHALL be lower than the before total.

#### Scenario: Before and after recorded
- **WHEN** `fix-eval-gaps` is ready to ship
- **THEN** `evals/timings.md` lists `pr-pair`, `update`, `review-routes`, `git-workflow`, `release` and `finish` with the #127 before time and an after time each, both test counts, states that every base test ID is still present, and the after total is lower than the before total

#### Scenario: A test ID went missing
- **WHEN** the test IDs listed after the change lack an ID listed at the base commit
- **THEN** the record names the missing ID and the change is not ready to ship

#### Scenario: A suite that did not get faster
- **WHEN** one suite's after time is not lower than its before time
- **THEN** the record shows both times as measured and names that suite in a note, and the after total is still compared with the before total
