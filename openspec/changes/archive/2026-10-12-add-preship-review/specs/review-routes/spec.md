# Spec Delta

## Purpose

Chooses, isolates, runs and checks the reviewer that Specwright hands a review to, so design reviews and pre-ship reviews use one configurable list of reviewer CLIs, fail closed on unusable output and record what actually ran.

## ADDED Requirements

### Requirement: Reviewer routes are tried in the configured order
Selection SHALL walk `review.order` (default `[codex, claude, omp]`), skip the route of the harness the agent runs in, and take the first route whose CLI is installed and whose probe passes. When no route is left, or `review.cross_model` is `false`, the `specwright-reviewer` subagent SHALL review. Design reviews (FULL tier and the roadmap baseline) and the pre-ship review SHALL use this selection.

#### Scenario: Claude Code with Codex installed
- **WHEN** the agent runs in Claude Code, `review.order` is unset, and `codex` is installed and its probe passes
- **THEN** the selected route is `codex`, and the result lists `claude` as skipped with reason `current runtime`

#### Scenario: First route missing
- **WHEN** the agent runs in Claude Code, `review.order` is `[codex, claude, omp]`, `codex` is not installed and `omp` is installed and its probe passes
- **THEN** the selected route is `omp`, and the result lists `codex` with reason `not installed` and `claude` with reason `current runtime`

#### Scenario: No route available
- **WHEN** no route in `review.order` other than the current runtime is installed
- **THEN** the selected route is `subagent`, and every listed route appears in the skipped list with its reason

#### Scenario: Cross-model reviews turned off
- **WHEN** `review.cross_model` is `false` and `codex` is installed
- **THEN** the selected route is `subagent` and no CLI probe runs

#### Scenario: Unknown route name
- **WHEN** `review.order` contains `gemini`
- **THEN** selection exits non-zero with a message naming `gemini` and the accepted names, and selects no route

### Requirement: An OMP model that cannot be resolved makes OMP unavailable
The OMP route SHALL pass `review.models.omp` (default `@default`, an OMP role or a `<provider>/<id>` selector) as its model. When OMP reports that the model is not found, OMP SHALL count as unavailable and selection SHALL move to the next route.

#### Scenario: Configured role exists
- **WHEN** the selected route is `omp` with `review.models.omp: "@slow"`, and OMP resolves `@slow`
- **THEN** the review runs on OMP with `--model @slow`

#### Scenario: Unknown role
- **WHEN** `review.models.omp` is `@nosuchrole`, OMP's probe exits 1 with `Model "@nosuchrole" not found`, and `claude` is next in the order and available
- **THEN** the selected route is `claude`, and `omp` is listed as skipped with the OMP error as its reason

### Requirement: Reviewers run isolated and read-only
Each route SHALL run with one fixed command line that turns off the user's skills, extensions, rules and slash commands where the CLI supports it, and allows only an explicit list of read-only tools. An OMP review SHALL run with a new, empty session directory, so it never continues an earlier session.

#### Scenario: OMP review starts a fresh session
- **WHEN** two OMP reviews run one after the other in the same checkout
- **THEN** each command line names its own new `--session-dir`, and the second session file holds no message from the first

#### Scenario: Reviewer tries to write
- **WHEN** a review on each of `codex`, `claude` and `omp` is asked to edit a file in the checkout
- **THEN** after each review the tracked files and `git status --porcelain` are unchanged

### Requirement: The review input is built by Specwright, within a bound
For a pre-ship review, Specwright SHALL put the diff of the code range, and of the store range when store-backed, into the reviewer's prompt itself, so every route reviews the same change whatever its tools. When the combined diff exceeds `review.max_diff_kb` (default 1024), the review SHALL stop before any reviewer starts, and SHALL never run on a truncated diff.

#### Scenario: Route without a shell
- **WHEN** a store-backed pre-ship review runs on `claude`, whose tools include no shell
- **THEN** the prompt it receives contains the changed lines of both the code range and the store range

#### Scenario: Diff over the bound
- **WHEN** the combined diff of a change is 1.5 MB and `review.max_diff_kb` is unset
- **THEN** the run exits with `diff_too_large` and the size, no reviewer process starts, and no record is written

### Requirement: Review output is validated and fails closed
A review from any route, the subagent included, SHALL count as done only when its output validates: a pre-ship review against the findings schema, a design review as a review file with exactly one `VERDICT:` line and a `CHANGES_APPLIED:` line. A route that ran but whose output fails validation, or that passes the deadline, SHALL be a failed review that stops the caller. It SHALL NOT fall through to another route.

#### Scenario: Valid findings
- **WHEN** a pre-ship review prints JSON that matches the findings schema
- **THEN** the run exits 0 and writes the findings to the result file

#### Scenario: Output that is not JSON
- **WHEN** a pre-ship review on `codex` prints prose instead of JSON
- **THEN** the run exits non-zero with `status: invalid` and the validation error, no findings are recorded, and no other route runs

#### Scenario: Subagent design review without a verdict
- **WHEN** the `specwright-reviewer` subagent writes a `review.md` with no `VERDICT:` line
- **THEN** validation exits non-zero with `status: invalid`, and the tasks step does not start

#### Scenario: Design review with two verdicts
- **WHEN** a design review prints two `VERDICT:` lines
- **THEN** the run exits non-zero with `status: invalid`, and no review file is written

#### Scenario: Reviewer exceeds the deadline
- **WHEN** a review is still running when `review.timeout` (default 20m) passes
- **THEN** the reviewer process is stopped, the run exits non-zero with `status: timeout`, and no other route runs

### Requirement: Every review records a receipt
Every review run SHALL write a receipt naming the route it used, each skipped route with its reason, the requested model and reasoning level, and the model and level that actually ran, or `unknown` when the CLI does not report them.

#### Scenario: OMP review receipt
- **WHEN** an OMP review runs with `@default`, and its session file records the resolved model `gpt-6.1-sol` at level `high`
- **THEN** the receipt has `route: omp`, `requested_model: "@default"`, `actual_model: "gpt-6.1-sol"` and `actual_thinking: "high"`

#### Scenario: Model not reported
- **WHEN** a Claude review runs with `review.models.claude: default` and its output names no model
- **THEN** the receipt has `requested_model: "default"` and `actual_model: "unknown"`
