# Spec Delta

## ADDED Requirements

### Requirement: Suites that need jj run with a pinned jj in CI
The CI workflow SHALL install the jj release pinned in `JJ_VERSION`, check its archive against a pinned SHA-256, and run every suite with it on PATH. A test that needs jj SHALL be skipped with the reason `jj not installed` when jj is missing and `SPECWRIGHT_REQUIRE_JJ` is unset. With `SPECWRIGHT_REQUIRE_JJ=1`, which CI sets, a missing jj SHALL fail that test.

#### Scenario: CI run
- **WHEN** a pull request runs the `vcs` suite in CI
- **THEN** the job installs the pinned jj, `jj --version` prints the version in `JJ_VERSION`, and no test in the suite is skipped for a missing jj

#### Scenario: Checksum mismatch
- **WHEN** the downloaded jj archive does not match the pinned SHA-256
- **THEN** the setup step fails, and no suite job reports success

#### Scenario: Local run without jj
- **WHEN** a developer runs `python evals/run.py vcs` with no jj on PATH and `SPECWRIGHT_REQUIRE_JJ` unset
- **THEN** each jj test is reported skipped with `jj not installed`, and the run does not count as a failure

#### Scenario: Required but missing
- **WHEN** `SPECWRIGHT_REQUIRE_JJ=1` and no jj is on PATH
- **THEN** each jj test fails, naming the missing jj
