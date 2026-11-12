# Spec Delta

## ADDED Requirements

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

#### Scenario: LSP is optional and read-only
- **WHEN** an OMP review configured with `[read, grep, glob, lsp]` requests a local definition/diagnostic query and then a rename, raw request, reload or remote file target
- **THEN** the local read-only query remains usable and each unsafe operation is blocked before its native implementation runs

#### Scenario: Invalid trusted policy cannot start a review
- **WHEN** OMP cannot load the run's fixed trusted policy
- **THEN** the reviewer fails before agent/tool execution, the controller reports the failed run without writing a successful review or record, and never retries without the module

#### Scenario: Policy callback failure cannot bypass the gate
- **WHEN** a policy callback throws while handling a remote-target read or grep
- **THEN** that native tool call fails, the fixture receives no TCP connection, and neither the tool nor controller retries through an unguarded invocation

## MODIFIED Requirements

### Requirement: Reviewers run isolated and read-only
Each route SHALL run with a command line built from fixed isolating flags plus the route's effective tool list, disabled features and extra flags (shipped defaults or `review.routes`). The fixed flags SHALL turn off the user's skills, extensions, rules and slash commands where the CLI supports it. OMP's sole trusted-extension exception SHALL be its fixed Specwright-owned local-target policy; ambient/user extensions remain disabled. An OMP review SHALL run with a new, empty session directory, so it never continues an earlier session. On Windows, the codex route SHALL keep the user's config file ignored and pass only that file's `windows.sandbox` value, when it is set to a plain name, as an explicit setting.

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
