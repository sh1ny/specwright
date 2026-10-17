# Spec Delta

## MODIFIED Requirements

### Requirement: Reviewers run isolated and read-only
Each route SHALL run with one fixed command line that turns off the user's skills, extensions, rules and slash commands where the CLI supports it, and allows only an explicit list of read-only tools. An OMP review SHALL run with a new, empty session directory, so it never continues an earlier session. On Windows, the codex route SHALL keep the user's config file ignored and pass only that file's `windows.sandbox` value, when it is set to a plain name, as an explicit setting.

#### Scenario: OMP review starts a fresh session
- **WHEN** two OMP reviews run one after the other in the same checkout
- **THEN** each command line names its own new `--session-dir`, and the second session file holds no message from the first

#### Scenario: Reviewer tries to write
- **WHEN** a review on each of `codex`, `claude` and `omp` is asked to edit a file in the checkout
- **THEN** after each review the tracked files and `git status --porcelain` are unchanged

#### Scenario: Codex on Windows with a sandbox setting
- **WHEN** a codex review runs on Windows and `$CODEX_HOME/config.toml` (default `~/.codex/config.toml`) has `[windows] sandbox = "elevated"` and a project trust entry
- **THEN** the command line still has `--ignore-user-config` and `-s read-only`, adds `-c windows.sandbox="elevated"`, and carries no trust entry or other setting from that file

#### Scenario: Codex on Windows without a usable setting
- **WHEN** a codex review runs on Windows and the config file is missing, unreadable, has no `windows.sandbox`, or holds a value that is not a plain name (such as `"x\" -c y"`)
- **THEN** the command line adds no `windows.sandbox` setting, and the review runs as before

#### Scenario: Codex off Windows
- **WHEN** a codex review runs on Linux or macOS and the config file has `[windows] sandbox = "elevated"`
- **THEN** the command line adds no `windows.sandbox` setting

### Requirement: Review output is validated and fails closed
A review from any route, the subagent included, SHALL count as done only when its output validates: a pre-ship review against the findings schema, a design review as a review file with exactly one `VERDICT:` line and exactly one `CHANGES_APPLIED:` line. A route that ran but whose output fails validation, or that passes the deadline, SHALL be a failed review that stops the caller. It SHALL NOT fall through to another route.

#### Scenario: Valid findings
- **WHEN** a pre-ship review prints JSON that matches the findings schema
- **THEN** the run exits 0 and writes the findings to the result file

#### Scenario: Output that is not JSON
- **WHEN** a pre-ship review on `codex` prints prose instead of JSON
- **THEN** the run exits non-zero with `status: invalid` and the validation error, no findings are recorded, and no other route runs

#### Scenario: Subagent design review without a verdict
- **WHEN** the `specwright-reviewer` subagent writes a scratch result file with no `VERDICT:` line
- **THEN** validation exits non-zero with `status: invalid`, and the tasks step does not start

#### Scenario: Design review with two verdicts
- **WHEN** a design review prints two `VERDICT:` lines
- **THEN** the run exits non-zero with `status: invalid`, and no review file is written

#### Scenario: Reviewer exceeds the deadline
- **WHEN** a review is still running when `review.timeout` (default 20m) passes
- **THEN** the reviewer process is stopped, the run exits non-zero with `status: timeout`, and no other route runs

## ADDED Requirements

### Requirement: Design review verdict values are checked
A design review's `VERDICT:` value SHALL be `APPROVE`, `APPROVE_WITH_CHANGES` or `REVISE`, and its `CHANGES_APPLIED:` value SHALL be `no` or `yes` after `APPROVE_WITH_CHANGES` and `n/a` after any other verdict. Any other value SHALL fail validation, naming the value.

#### Scenario: Design review that could not review
- **WHEN** a codex design review prints `VERDICT: BLOCKED` and `CHANGES_APPLIED: n/a`, and the change's `review.md` holds an earlier valid review
- **THEN** the run exits 3 with `status: invalid` and an error naming `BLOCKED`, `review.md` is byte-identical to before, and no other route runs

#### Scenario: Verdict a reviewer may not set
- **WHEN** a reviewer CLI or the subagent returns `VERDICT: USER_OVERRIDE` or `VERDICT: SKIPPED_LIGHT`
- **THEN** validation exits non-zero with `status: invalid` naming the value, and no review file is written by the run

#### Scenario: CHANGES_APPLIED does not match the verdict
- **WHEN** a design review returns `VERDICT: APPROVE` with `CHANGES_APPLIED: yes`, or `VERDICT: REVISE` with `CHANGES_APPLIED: none`
- **THEN** validation exits non-zero with `status: invalid` naming the value

#### Scenario: Valid re-check
- **WHEN** a reviewer's re-check run returns `VERDICT: APPROVE_WITH_CHANGES` with `CHANGES_APPLIED: yes`
- **THEN** the run exits 0 and writes `review.md`

### Requirement: A refused design review leaves the earlier review file unchanged
A design review that fails validation or passes the deadline SHALL leave any earlier review file unchanged. The subagent SHALL write its design review to a scratch result file, which validation copies to the review file only when it passes, removing the scratch file; a refused scratch file SHALL be kept and named in the report.

#### Scenario: Subagent design review that could not review
- **WHEN** the `specwright-reviewer` subagent writes `VERDICT: BLOCKED` to its scratch result file, and the change's `review.md` holds an earlier valid review
- **THEN** validation exits 3 with `status: invalid`, `review.md` is byte-identical to before, and the report names the scratch file

#### Scenario: Valid subagent design review
- **WHEN** the subagent writes a valid `VERDICT: REVISE` review with `CHANGES_APPLIED: n/a` to its scratch result file
- **THEN** validation exits 0, writes that content to `review.md`, and removes the scratch file

### Requirement: The size bound applies to the answer
The 2 MiB output bound SHALL apply to the review's answer, not to a route's event stream: codex's last-message file, claude's printed output, and for OMP the final message of the last `agent_end` event. An OMP stream with no `agent_end` event SHALL fail validation.

#### Scenario: Large OMP event stream with a small answer
- **WHEN** an OMP design review's event stream on stdout is 3 MiB and its final `agent_end` message is a 19 KB valid review
- **THEN** the run exits 0 and writes that 19 KB review

#### Scenario: OMP answer over the bound
- **WHEN** an OMP review's final `agent_end` message is larger than 2 MiB
- **THEN** the run exits non-zero with `status: invalid` and `output too large`, and no review file is written

#### Scenario: OMP stream without a final message
- **WHEN** an OMP review exits 0 but its event stream has no `agent_end` event
- **THEN** the run exits non-zero with `status: invalid`, and no review file is written
