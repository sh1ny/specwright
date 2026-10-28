# eval-runner Specification

## Purpose

Runs the eval suites as a whole, in parallel, with one pass or fail result and each suite's wall time, and keeps a record of those times so a slowdown is noticed.

## Requirements

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

### Requirement: Changed paths select the suites
`python evals/run.py --changed <base>` SHALL run only the suites and test files that `evals/suites.json` maps the changed paths to; a rule's target is a whole suite or one `suite/test_*.py` file. Changed paths are those differing between the merge base of `<base>` and `HEAD` and the working tree, untracked files included. It SHALL first print each selected target with the paths that selected it.

#### Scenario: Renamed, deleted and untracked paths count
- **WHEN** since the merge base a file was renamed, another deleted, and a new file created but not added (and not ignored)
- **THEN** both sides of the rename, the deleted path and the untracked file each select the targets the map gives them

#### Scenario: A change to one skill script
- **WHEN** the only changed path is `skills/specwright-release/scripts/release.sh`
- **THEN** the runner prints each suite the map sends that path to, with that path as the reason (with the map in this change: `release`, `git-workflow`, `pr-pair` and `update`), runs exactly those suites and no other, and exits as that run does

#### Scenario: A rule that targets one test file
- **WHEN** the only changed path is `openspec/changes/<name>/tasks.md` and the map sends `openspec/**` to `git-workflow/test_specs_strict.py`
- **THEN** the runner runs only that test file, not the rest of `git-workflow`

#### Scenario: An uncommitted file counts
- **WHEN** the branch has no commit since `<base>` and `skills/specwright-finish/scripts/finish.sh` is modified but not staged
- **THEN** the runner selects the suites the map gives for that path

#### Scenario: A path the map does not cover
- **WHEN** a changed path matches no pattern in the map and is not in its no-eval list
- **THEN** the runner prints that path as uncovered, runs every suite, and exits as that run does

#### Scenario: Only paths that need no eval
- **WHEN** every changed path is in the map's no-eval list (for example `docs/adr/0015-release-notes-come-from-each-proposal.md`)
- **THEN** the runner prints `no eval suite covers these changes`, runs no test, and exits 0

#### Scenario: A base that does not resolve
- **WHEN** `--changed no-such-ref` runs, or `<base>` has no merge base with `HEAD`
- **THEN** the runner exits 2 with an error naming the base, and runs no test

#### Scenario: Suites named together with --changed
- **WHEN** `python evals/run.py --changed main release` runs
- **THEN** the runner exits 2 with an error saying `--changed` and suite names cannot be combined, and runs no test

### Requirement: The suite map covers every tracked file
Every tracked file SHALL match a rule of `evals/suites.json` or its no-eval list, never both: no-eval covers only paths no rule matches. Every suite and test file the map names SHALL exist under `evals/`. A test in `evals/runner` SHALL check all three.

#### Scenario: A complete map
- **WHEN** every tracked file matches a pattern or the no-eval list and every named suite exists
- **THEN** the map test passes

#### Scenario: A new file no pattern covers
- **WHEN** a tracked file is added that matches no pattern and is not in the no-eval list
- **THEN** the map test fails and names that file

#### Scenario: A pattern names a missing suite or file
- **WHEN** the map sends a pattern to a suite that has no directory with `test_*.py` files under `evals/`, or to a test file that does not exist
- **THEN** the map test fails naming that target, and `--changed` exits 2 naming it before running any test

#### Scenario: A no-eval pattern overlaps a rule
- **WHEN** a no-eval pattern matches a tracked file that a rule also matches
- **THEN** the map test fails naming that file and the no-eval pattern, and `--changed` still selects the rule's targets for that file

#### Scenario: A path under a removed suite
- **WHEN** a changed path is under `evals/<name>/` and `<name>` is no longer a suite (it was renamed or removed)
- **THEN** the path counts as uncovered and the runner runs every suite

### Requirement: CI runs every suite on Linux for each pull request
`.github/workflows/evals.yml` SHALL run on every pull request, opened or updated, and on a manual dispatch. It SHALL take the suite list from `python evals/run.py --list-suites` (a JSON array of every suite under `evals/`) and run each with `python evals/run.py <suite>` on Linux, one job per suite, with the OpenSpec CLI at the version in `OPENSPEC_VERSION`. A job SHALL fail when its setup fails or its suite's run exits non-zero, and pass only when both succeed.

#### Scenario: All suites pass
- **WHEN** a pull request is opened or a new commit is pushed to it and every suite passes
- **THEN** one check per suite reports success on that head

#### Scenario: A suite fails
- **WHEN** one suite has a failing test file on Linux
- **THEN** that suite's check fails with the runner's failure output in its log, and the other suites' checks still report their own results

#### Scenario: A new suite appears
- **WHEN** a directory with `test_*.py` files is added under `evals/` and the workflow file is not edited
- **THEN** `--list-suites` includes it and the next pull request gets a check for that suite

#### Scenario: The suite list cannot be read
- **WHEN** `python evals/run.py --list-suites` exits non-zero in the workflow
- **THEN** the job that lists the suites fails, no suite job starts, and the pull request shows a failed check rather than a passing one

### Requirement: The instructions say which suites to run when
The tracked agent instructions (`AGENTS.md`, which `CLAUDE.md` imports) and `CONTRIBUTING.md` SHALL tell whoever works on this repository to run `python evals/run.py --changed main` during a change, to rely on the CI workflow for every suite on each pull request, and to run every suite locally only at a milestone close. A test in `evals/runner` SHALL check that both files say so and that `CLAUDE.md` imports `AGENTS.md`.

#### Scenario: Both files carry the rule
- **WHEN** the runner tests run
- **THEN** both `AGENTS.md` and `CONTRIBUTING.md` name `python evals/run.py --changed main`, the CI workflow and the milestone close, `CLAUDE.md` holds the line `@AGENTS.md`, and the test passes

#### Scenario: One file drops the rule
- **WHEN** `CONTRIBUTING.md` no longer names `--changed`, or `CLAUDE.md` no longer imports `AGENTS.md`
- **THEN** the instructions test fails naming that file
