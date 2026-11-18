# Spec Delta

## MODIFIED Requirements

### Requirement: sw starts itself only for its helper and the reviewer evaluator
For its own work `sw` SHALL start its own binary only as the bounded process helper and as the reviewer evaluator under a poll deadline. It SHALL never start a shipped script or a Python interpreter. Running another installed or downloaded `sw` to read its version and interface SHALL stay allowed. Printing a command for an agent or user to run is not a launch.

#### Scenario: Retrofitted paths with sentinels and no Python
- **WHEN** `sw vcs` fetch, pull and push against github.com, `sw pr snapshot` with a reviewer config, and the PR workflow commands run with recording `as.sh`, `vcs.sh`, `pr-pair.sh` and `sw-path.sh` sentinels in the handoff scripts directory and failing `python` and `python3` first on `PATH`, on Linux, Windows and macOS
- **THEN** each returns its expected document or output, no sentinel recorded a run, and neither interpreter ran

#### Scenario: Reviewer evaluator stays a separate process
- **WHEN** a reviewer report pattern backtracks past the poll deadline
- **THEN** the evaluator child is killed at the deadline and the poll fails, while the snapshot process itself keeps running

#### Scenario: Printed commands are not launches
- **WHEN** `sw vcs plan` or a PR cleanup plan prints a command that names `vcs.sh` or `pr-pair.sh`
- **THEN** the document holds that command and no such script ran

#### Scenario: sw update checks a downloaded sw and starts no script
- **WHEN** `sw update sw-install` places a downloaded `sw` and an owner's `sw update swap` checks a jj store, with recording `update.sh`, `vcs.sh`, `as.sh` and `sw-path.sh` sentinels in the download's scripts directories and failing `python` and `python3` first on `PATH`
- **THEN** the downloaded binary ran only as `version --json`, no sentinel recorded a run, and neither interpreter ran

### Requirement: A launch-site allowlist guards process starts
A test over `cli/lib/src`, run on Linux, Windows and macOS, SHALL list every call that starts a process and every caller of the process runners, and SHALL fail on a launch site missing from its allowlist, on a self-launch other than the helper and the evaluator, on a shipped script name in a launch's arguments, and on a shipped script name written anywhere under `cli/lib/src` outside a listed printed-command, message or label site.

#### Scenario: Current tree passes
- **WHEN** the allowlist test runs on the tree this change produces
- **THEN** it passes, and its allowlist names each launch site with its permitted kind: external tool, process helper, reviewer evaluator or binary check

#### Scenario: A new unlisted launch fails
- **WHEN** a source file under `cli/lib/src` adds a call to a process runner that the allowlist does not name
- **THEN** the test fails, naming the file and the call

#### Scenario: A script in launch arguments fails
- **WHEN** a listed launch site passes `as.sh`, `vcs.sh`, `pr-pair.sh`, `pr-snapshot.sh`, `pr-reply.sh`, `review-run.sh`, `release.sh`, `update.sh`, `install-sw.sh` or a `.py` file as a launch argument
- **THEN** the test fails, naming the script and the site

#### Scenario: A self-launch outside the allowed two fails
- **WHEN** a call starts `sw`'s own executable with arguments other than the `__exec` helper or `pr reviewers` under a deadline, including a listed site whose subcommand is changed, whose argument list is not a literal, or whose evaluator runs without its bound, while every call count stays the same
- **THEN** the test fails, naming the site

#### Scenario: A script name built away from the launch fails
- **WHEN** a source file under `cli/lib/src` writes `as.sh` or another shipped script name into a value outside a listed printed-command, message or label site, and passes that value to a listed launch
- **THEN** the test fails, naming the file and the script

#### Scenario: The binary checks of sw update are listed
- **WHEN** the allowlist test runs on the `sw update` sources
- **THEN** the run of a downloaded or placed `sw` with `version --json` is listed as a binary check, and any other argument list at that site fails the test
