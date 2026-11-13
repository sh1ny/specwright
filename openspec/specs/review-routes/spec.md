# review-routes Specification

## Purpose

Chooses, isolates, runs and checks the reviewer that Specwright hands a review to, so design reviews and pre-ship reviews use one configurable list of reviewer CLIs, fail closed on unusable output and record what actually ran.

## Requirements

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
Each route SHALL retain fixed isolation flags alongside its effective tools, disabled features and extra flags. It SHALL disable user skills, extensions, rules and slash commands where supported. OMP SHALL use only its fixed trusted local-target extension, no user extensions, and a new empty session directory, never continuing a prior session. Windows Codex SHALL ignore user config, explicitly forwarding only that file's configured plain-name `windows.sandbox` value.

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

### Requirement: The review input is built by Specwright, within a bound
For a pre-ship review, Specwright SHALL put the diff of the code range, and of the store range when store-backed, into the reviewer's prompt itself, so every route reviews the same change whatever its tools. When the combined diff exceeds `review.max_diff_kb` (default 1024), the review SHALL stop before any reviewer starts, and SHALL never run on a truncated diff.

#### Scenario: Route without a shell
- **WHEN** a store-backed pre-ship review runs on `claude`, whose tools include no shell
- **THEN** the prompt it receives contains the changed lines of both the code range and the store range

#### Scenario: Diff over the bound
- **WHEN** the combined diff of a change is 1.5 MB and `review.max_diff_kb` is unset
- **THEN** the run exits with `diff_too_large` and the size, no reviewer process starts, and no record is written

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

### Requirement: Every review records a receipt
Every review run SHALL write a receipt naming the route it used, each skipped route with its reason, the requested model and reasoning level, the model and level that actually ran (or `unknown` when the CLI does not report them), and the route's effective tool list, disabled features and extra flags. An OMP receipt SHALL additionally name the fixed policy identity and the SHA-256 of the module used.

#### Scenario: OMP review receipt
- **WHEN** an OMP review runs with `@default`, and its session file records the resolved model `gpt-6.1-sol` at level `high`
- **THEN** the receipt has `route: omp`, `requested_model: "@default"`, `actual_model: "gpt-6.1-sol"` and `actual_thinking: "high"`

#### Scenario: Model not reported
- **WHEN** a Claude review runs with `review.models.claude: default` and its output names no model
- **THEN** the receipt has `requested_model: "default"` and `actual_model: "unknown"`

#### Scenario: Effective tools in the receipt
- **WHEN** an OMP review runs with `review.routes.omp.tools: [read, grep, glob, lsp]` and no `args`
- **THEN** the receipt has `tools: ["read", "grep", "glob", "lsp"]` and `extra_args: []`

#### Scenario: OMP policy identity in the receipt
- **WHEN** an OMP review uses the fixed trusted local-target policy
- **THEN** the receipt records policy identity `local-only-v1` and the SHA-256 of the actual module passed to OMP, with the effective overlay keys; the fixed module is not reported as a user extra argument

#### Scenario: Receipt of a refused setting
- **WHEN** a run stops with `route_setting_unsafe`
- **THEN** no receipt, findings file, review file or pre-ship record is written

### Requirement: Design review verdict values are checked
A design review's `VERDICT:` value SHALL be `APPROVE`, `APPROVE_WITH_CHANGES` or `REVISE`, and its `CHANGES_APPLIED:` value SHALL be `no` or `yes` after `APPROVE_WITH_CHANGES` and `n/a` after any other verdict. Any other value SHALL fail validation, naming the value. The verdicts the author or the user records (`USER_OVERRIDE`, `SKIPPED_LIGHT`, `DEFERRED`, `WAIVED`) are among the refused values.

#### Scenario: Design review that could not review
- **WHEN** a codex design review prints `VERDICT: BLOCKED` and `CHANGES_APPLIED: n/a`, and the change's `review.md` holds an earlier valid review
- **THEN** the run exits 3 with `status: invalid` and an error naming `BLOCKED`, `review.md` is byte-identical to before, and no other route runs

#### Scenario: Verdict a reviewer may not set
- **WHEN** a reviewer CLI or the subagent returns `VERDICT: USER_OVERRIDE`, `VERDICT: SKIPPED_LIGHT`, `VERDICT: DEFERRED` or `VERDICT: WAIVED`
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
The 2 MiB output bound SHALL apply to the review's answer, not to a route's event stream: claude's printed output; for codex the text of the last completed `agent_message` item in its `--json` event stream; and for OMP the final message of the last `agent_end` event. A codex stream with no completed `agent_message` item, or an OMP stream with no `agent_end` event, SHALL fail validation.

#### Scenario: Large OMP event stream with a small answer
- **WHEN** an OMP design review's event stream on stdout is 3 MiB and its final `agent_end` message is a 19 KB valid review
- **THEN** the run exits 0 and writes that 19 KB review

#### Scenario: OMP answer over the bound
- **WHEN** an OMP review's final `agent_end` message is larger than 2 MiB
- **THEN** the run exits non-zero with `status: invalid` and `output too large`, and no review file is written

#### Scenario: OMP stream without a final message
- **WHEN** an OMP review exits 0 but its event stream has no `agent_end` event
- **THEN** the run exits non-zero with `status: invalid`, and no review file is written

#### Scenario: Codex answer taken from the event stream
- **WHEN** a codex design review exits 0 after printing two completed `agent_message` items, the second a valid 19 KB review
- **THEN** the run exits 0 and writes that 19 KB review, and no file other than its own work files and the review file was written

#### Scenario: Codex answer over the bound
- **WHEN** a codex review's last completed `agent_message` item holds more than 2 MiB of text
- **THEN** the run exits non-zero with `status: invalid` and `output too large`, and no review file is written

#### Scenario: Codex stream without an answer
- **WHEN** a codex review exits 0 but its event stream has no completed `agent_message` item
- **THEN** the run exits non-zero with `status: invalid` naming the missing answer, and no review file is written

### Requirement: Reviewer output is bounded while the CLI runs
While a reviewer CLI or probe runs, the review run SHALL bound its output: stderr 8 MiB; stdout 2 MiB on the claude route (the answer) and 64 MiB on codex and OMP (the event stream holding the answer). No route's answer is read from a file the CLI writes itself. Once one passes its bound, the process tree SHALL be stopped as at the deadline. The run fails with `status: invalid` and `output too large`, naming the stream, and writes no result file and no review record.

#### Scenario: Output within the bounds
- **WHEN** an OMP design review streams 3 MiB of events on stdout and 100 KB on stderr, and ends with a valid 19 KB answer
- **THEN** the run exits 0 and writes that review

#### Scenario: Runaway stdout
- **WHEN** a claude pre-ship review keeps printing to stdout and passes 2 MiB well before `review.timeout`
- **THEN** the reviewer process tree is stopped within 5 seconds of passing the bound, the run exits 3 with `status: invalid` and `output too large` naming stdout, no findings file or pre-ship record is written, and no other route runs

#### Scenario: Runaway stderr
- **WHEN** a codex review prints more than 8 MiB to stderr and nothing on stdout
- **THEN** the reviewer is stopped, the run exits 3 with `status: invalid` naming stderr, and the review file is byte-identical to before

#### Scenario: Codex event stream over the bound
- **WHEN** a codex review keeps printing events and its stdout passes 64 MiB while codex is still running
- **THEN** the reviewer is stopped within 5 seconds of passing the bound, and the run exits 3 with `status: invalid` and `output too large` naming stdout, writing no review

#### Scenario: Codex answer file over the bound
- **WHEN** the review run builds the codex command line for a design or pre-ship review
- **THEN** it has `--json` and no `-o` or `--output-last-message` argument, so codex writes no answer file and its answer is bounded as part of stdout

### Requirement: A reviewer that exits before the deadline is judged by its exit
A reviewer that exits before `review.timeout` SHALL NOT be reported with `status: timeout`, also when a process it started still holds its output open; such a run fails as a reviewer that left its output open. Its exit SHALL be observed when it happens, not at a later poll. A reviewer whose exit is first observed at or after the deadline SHALL be reported with `status: timeout`.

#### Scenario: Exit in the last poll interval with a held pipe
- **WHEN** a codex review with `review.timeout` of 5 seconds, run with the capture loop's wait interval raised to 10 seconds by the test hook, starts a child that keeps its stdout open, and codex exits 0 at an absolute time the test set to 1 second before the run's deadline (measured from before the run starts), its recorded exit time being before that deadline
- **THEN** the run exits 3 with `status: failed` and the message that a process it started kept its output open, not `status: timeout`

#### Scenario: Reviewer held past the deadline
- **WHEN** on POSIX a reviewer is still running at `review.timeout` and the capture loop is held until after the reviewer has exited
- **THEN** the run exits 3 with `status: timeout`, and no review file or record is written

### Requirement: A process a reviewer started is stopped on every platform
When a review run stops a reviewer, or the reviewer exits while a process it started still holds its output, every process the reviewer started SHALL be stopped, on Windows as on POSIX, also when the reviewer itself has already exited. When Windows cannot hold the reviewer's processes together, the run's receipt SHALL say so and the tree SHALL be stopped from the reviewer's process as before.

#### Scenario: No job object on Windows
- **WHEN** on Windows the test hook makes job creation fail, and a reviewer runs past `review.timeout`
- **THEN** the run exits 3 with `status: timeout`, the reviewer's process is no longer running, and the receipt has `process_group: none` with the reason

#### Scenario: Orphan holding the pipe on Windows
- **WHEN** on Windows a reviewer starts a child that keeps its stdout open and sleeps for an hour, and the reviewer exits 0
- **THEN** the run fails within 10 seconds of the reviewer's exit, and the child's process is no longer running

#### Scenario: Reviewer stopped at the deadline with a grandchild
- **WHEN** a reviewer starts a child that starts a grandchild, all three sleep, and `review.timeout` passes
- **THEN** the run exits 3 with `status: timeout`, and neither the child nor the grandchild is still running

### Requirement: Review operations run in the project's sw
Each `review-run.sh` subcommand SHALL run in the project's matching `sw`, resolved as other ported scripts, preserving options, JSON, exits 0/1/2/3, records and state directory. Operations SHALL NOT start Python, bash or shipped scripts for their own work. No matching `sw` SHALL yield one `sw_missing` JSON and exit 1, without probing or fallback. The fixed OMP policy SHALL run inside OMP, not in a separate interpreter process.

#### Scenario: Pre-ship run without Python or bash
- **WHEN** `review-run.sh run --kind preship` runs on Linux, Windows and macOS with failing `python`, `python3`, `bash` and `sh` first on `PATH` for `sw`, and a fake codex reviewer that prints valid findings
- **THEN** the run exits 0, writes the findings and the pre-ship record at the same path as before the port, and none of the failing interpreters was started by `sw`

#### Scenario: Gate reads a record written before the port
- **WHEN** a pre-ship record written by the Python `review-run.sh` exists for the change's current heads, and `review-run.sh gate` runs through `sw`
- **THEN** it prints `status: pass` with the same `heads` and `reviewed_heads`

#### Scenario: VCS backend read in process
- **WHEN** a pre-ship step without `--branch` runs in a code repo whose settings select `vcs: gitbutler`, and `pr-pair.sh` is absent from the install
- **THEN** it stops with the existing usage error asking for `--branch`, and no `pr-pair.sh` or `vcs.sh` process starts

#### Scenario: No matching sw
- **WHEN** `review-run.sh select --runtime claude` runs in a project whose `sw` is missing or reports another version
- **THEN** it prints one `sw_missing` JSON document, exits 1, and starts no reviewer probe

### Requirement: Each route's tools, features and extra flags are settings
A `review.routes.<route>` block for `codex`, `claude` or `omp` SHALL set that route's reviewer: `tools` (claude and OMP) replaces the default tool list, `disable` (codex) adds Codex features to turn off, and `args` adds flags after the fixed ones. An unset key SHALL keep the shipped default. Values SHALL be checked when settings are read, before any probe or reviewer starts.

#### Scenario: OMP tool list from settings
- **WHEN** `review.routes.omp.tools` is `[read, grep, glob, lsp]` and a review runs on `omp`
- **THEN** the OMP command line has `--tools read,grep,glob,lsp` and keeps `--no-skills`, `--no-extensions`, `--no-rules` and a new `--session-dir`

#### Scenario: Extra Codex feature disabled
- **WHEN** `review.routes.codex.disable` is `[apps]` and a review runs on `codex`
- **THEN** the command line has `--disable apps` in addition to every default `--disable` and keeps `-s read-only` and `--ignore-user-config`

#### Scenario: Extra flag passed
- **WHEN** `review.routes.claude.args` is `["--no-session-persistence"]` and a review runs on `claude`
- **THEN** the command line has `--no-session-persistence` after the fixed flags and before any prompt argument

#### Scenario: Key on the wrong route
- **WHEN** `review.routes.codex.tools` is set, or `review.routes` names a route other than `codex`, `claude` or `omp`
- **THEN** `select` and `run` exit 1 with `error: bad_route_setting` naming the key and the keys that route accepts, and no probe or reviewer starts

#### Scenario: Wrong value type
- **WHEN** `review.routes.omp.tools` is the string `"read,grep"` instead of a list
- **THEN** `select` and `run` exit 1 with `error: bad_route_setting` naming `review.routes.omp.tools` and the expected list of names

### Requirement: A route setting that weakens isolation is refused
A route setting SHALL be refused when it names a tool on that route's refused list (tools that run code, edit or write files, reach the network, start agents or keep memory), names a Codex feature in `args` through `--enable`, or adds a flag that Specwright sets itself or that changes the sandbox, permissions, session, skills, rules, extensions, hooks or settings sources. The refusal SHALL be a stop before any probe or reviewer starts.

#### Scenario: Shell tool for claude
- **WHEN** `review.routes.claude.tools` is `[Read, Grep, Glob, Bash]`
- **THEN** `select` and `run` exit 1 with `error: route_setting_unsafe` naming `Bash` and `review.routes.claude.tools`, and no reviewer starts

#### Scenario: OMP write and memory tools
- **WHEN** `review.routes.omp.tools` names a refused write, execution, agent or memory tool, including `edit`, `write`, `bash`, `learn`, `manage_skill`, `find`, `eval`, `ast_edit`, `debug`, `github`, `checkpoint`, `rewind` or `retain`
- **THEN** the run exits 1 with `error: route_setting_unsafe` naming that tool

#### Scenario: Sandbox override in Codex args
- **WHEN** `review.routes.codex.args` contains `-s`, `--sandbox`, `--dangerously-bypass-approvals-and-sandbox`, its `--yolo` alias, `--approve-for-me`, its `--not-so-yolo` alias, `--enable`, `--profile` or `-c` with a `sandbox` key
- **THEN** the run exits 1 with `error: route_setting_unsafe` naming the flag, and no reviewer starts

#### Scenario: Protected Codex key set through its parent table or quoting
- **WHEN** `review.routes.codex.args` contains `-c` with `features={apps=true}`, `"features"."apps"=true`, `windows={sandbox="none"}` or ` sandbox_mode = "danger-full-access"`
- **THEN** the run exits 1 with `error: route_setting_unsafe` naming the protected key, and no reviewer starts

#### Scenario: Flag Specwright sets itself
- **WHEN** `review.routes.omp.args` contains `--session-dir`, `--continue`, `--resume` or `--tools`
- **THEN** the run exits 1 with `error: route_setting_unsafe` naming the flag and the setting to use instead where there is one

#### Scenario: User-supplied OMP trusted module
- **WHEN** `review.routes.omp.args` contains `--trusted-extension`, including its `--trusted-extension=<path>` form
- **THEN** `select` and `run` exit 1 with `error: route_setting_unsafe` naming that flag before any probe or reviewer starts, and write no receipt, result or record

### Requirement: Shipped defaults disable unsafe reviewer features
With no `review.routes` settings, the OMP route SHALL offer only `read`, `grep` and `glob` with memory, auto-learn and web fetching off and its fixed local-target policy active, and SHALL treat an OMP older than the version that was verified as unavailable. The Codex route SHALL turn off its dedicated network, image, plugin, memory, hook and goal features; its other tools stay under the read-only sandbox. The claude route SHALL keep `Read`, `Grep` and `Glob` under `--restricted`.

#### Scenario: Default OMP command line
- **WHEN** a review runs on `omp` with no `review.routes.omp`
- **THEN** the command line has `--tools read,grep,glob`, has no `find`, turns off OMP's memory, auto-learn and web fetching without changing the user's config files, retains `--no-extensions`, and loads exactly one fixed Specwright-owned trusted policy from the private run directory

#### Scenario: Default Codex command line
- **WHEN** a review runs on `codex` with no `review.routes.codex`
- **THEN** the command line keeps `-s read-only`, `--ephemeral`, `--ignore-rules` and `--ignore-user-config`, has a `--disable` for each default feature listed in the `specwright-review` skill, and sets Codex's web search to disabled

#### Scenario: OMP older than the verified version
- **WHEN** `omp --version` reports a version below 18.19.0, the first version on which the run's overlay was verified to turn off memory and auto-learn, and `claude` is next in `review.order` and available
- **THEN** `select` skips `omp` with a reason naming its version and the required 18.19.0 and selects `claude`, and `run --route omp` exits 1 with `error: omp_too_old` without starting OMP

#### Scenario: Codex version without a listed feature
- **WHEN** the installed Codex rejects `--disable` for a default feature it does not know
- **THEN** the run exits 3 with `status: failed` and Codex's message, and the review does not run without that feature disabled

### Requirement: OMP tool operations enforce local targets
OMP's fixed policy SHALL deny remote URI/resource/network-root targets before `read`, `grep`, `glob` and optional LSP file operations, including compound/encoded/mixed/aliased forms. Local paths, selectors and multiple roots SHALL work; LSP actions SHALL be read-only. The policy SHALL NOT register/invoke tools. This is not an OS network/filesystem sandbox: provider transport, underlying mounts and trusted host implementations remain outside its tool-target/operation boundary.

#### Scenario: Remote targets fail without a request
- **WHEN** retained OMP tools receive HTTP(S), SSH, opaque MCP/resource URI or UNC targets, including a remote entry hidden in compound roots, exclusions, a JSON-encoded list or a mixed local/remote input
- **THEN** each attempted operation ends in a native policy-denial error before remote dispatch and the controlled fixture receives no TCP connection or request

#### Scenario: Local review inputs keep working
- **WHEN** OMP reads, greps and globs local fixtures using normal absolute/relative paths, spaces, Unicode, supported read selectors, delimiter-bearing literal paths and multiple local search roots
- **THEN** the operations return the expected local contents or matches without a policy-denial error

#### Scenario: Bare open-ended read selectors remain local
- **WHEN** OMP receives a single bare extensionless read path with an open-ended selector, such as `README:50-` or `README:17-:raw`
- **THEN** the fixed hook schema-replaces it with its explicit `./` local form and validates that effective input before dispatch
- **AND** the operation returns the expected local contents without invoking opaque URI/resource routing
- **AND** compound, encoded and aliased inputs still require every native interpretation to remain local

#### Scenario: LSP is optional and read-only
- **WHEN** an OMP review configured with `[read, grep, glob, lsp]` requests a local definition/diagnostic query and then a rename, raw request, reload or remote file target
- **THEN** the local read-only query remains usable and each unsafe operation is blocked before its native implementation runs

#### Scenario: Invalid trusted policy cannot start a review
- **WHEN** OMP cannot load the run's fixed trusted policy
- **THEN** the reviewer fails before agent/tool execution, the controller reports the failed run without writing a successful review or record, and never retries without the module

#### Scenario: Policy callback failure cannot bypass the gate
- **WHEN** a policy callback throws while handling a remote-target read or grep
- **THEN** that native tool call fails, the fixture receives no TCP connection, and neither the tool nor controller retries through an unguarded invocation
