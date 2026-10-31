## ADDED Requirements

### Requirement: Suites that need GitButler run with a pinned `but` in CI
Only jobs of suites with tests that need a real `but` SHALL install `but`: the build in `BUT_VERSION` from its versioned release URL, failing setup unless its SHA-256 equals the pinned hash and `but --version` names that version. A test needing `but` SHALL skip with `but not installed` when `but` is missing and `SPECWRIGHT_REQUIRE_BUT` is unset, and fail when it is `1`, as every CI job sets. GitButler tests SHALL run only in scratch repos they create.

#### Scenario: CI run
- **WHEN** a pull request runs the `vcs` suite in CI
- **THEN** the job downloads the pinned build, its SHA-256 matches, `but --version` names the version in `BUT_VERSION`, and no test in the suite is skipped for a missing `but`

#### Scenario: Upstream released a new version
- **WHEN** GitButler publishes a newer build than `BUT_VERSION`
- **THEN** the `vcs` job still installs the pinned build and passes setup

#### Scenario: Downloaded bytes differ
- **WHEN** the file at the pinned URL no longer matches the pinned SHA-256
- **THEN** the setup step of the `vcs` job fails before the file is run, and the jobs of the other suites are unaffected

#### Scenario: Local run without `but`
- **WHEN** a developer runs `python evals/run.py vcs` with no `but` on PATH and `SPECWRIGHT_REQUIRE_BUT` unset
- **THEN** each GitButler test is reported skipped with `but not installed`, and the run does not count as a failure

#### Scenario: Required but missing
- **WHEN** `SPECWRIGHT_REQUIRE_BUT=1` and no `but` is on PATH
- **THEN** each GitButler test fails, naming the missing `but`
