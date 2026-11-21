## MODIFIED Requirements

### Requirement: Long Windows arguments reach native tools whole
On Windows a native tool SHALL receive every argument whole up to the OS command-line limit of 32,767 UTF-16 units, the terminating NUL included, so the longest accepted line has 32,766 units before its NUL. A command line over that limit SHALL be refused before the tool or the helper that would carry it starts.

#### Scenario: A 20,000-character argument on Windows
- **WHEN** on Windows a 20,000-character argument with spaces, quotes and trailing backslashes is passed to a native tool
- **THEN** the tool receives the whole value unchanged

#### Scenario: Over the Windows command-line limit
- **WHEN** on Windows the quoted command line for a native tool exceeds 32,766 UTF-16 units before its terminating NUL
- **THEN** the caller reports the refusal with its usual error and exit status, and neither the tool nor the helper starts

#### Scenario: The last accepted and first refused lengths
- **WHEN** on Windows a direct launch's quoted command line is exactly 32,766 units, and then exactly 32,767 units, before its NUL
- **THEN** the first is started and the second is refused before the tool starts

#### Scenario: Under the limit alone, over it behind the helper
- **WHEN** on Windows a bounded launch has a tool command line within the limit but a helper command line, serialized as it would be started, over it
- **THEN** neither the tool nor the helper starts, and the caller reports the failed helper start it reports before this change (for `sw run --bounded`, `bounded: cannot start <cmd>: cannot start the helper: ...`; for `sw pr reply`'s pending check, that diagnostic and exit 127)

#### Scenario: A batch launch behind the helper
- **WHEN** on Windows a captured `.cmd` launch's raw `cmd.exe` line fits alone but the helper's command line is over the limit
- **THEN** neither the tool nor the helper starts, and the caller reports the failed helper start it reports before this change

#### Scenario: An inherited batch launch through the identity fence
- **WHEN** on Windows `sw as <login> tool.cmd <args>` passes the fence's checks and the raw `cmd.exe` line for `tool.cmd`, its NUL included, is over the limit
- **THEN** it exits 2 with `as.sh: unrepresentable` naming the command, and neither `cmd.exe` nor `tool.cmd` starts

#### Scenario: A reviewer run behind the helper
- **WHEN** on Windows a review run's reviewer command line fits on its own but is over the limit behind the helper
- **THEN** the review reports `reviewer_failed`, exit 3, with `exit_code: 127` beside its receipt, as before this change, and neither the helper nor the reviewer starts; the reviewer's `--version` probe may run first

#### Scenario: A reviewer line of exactly 32,767 units
- **WHEN** on Windows a review run's resolved reviewer command line is exactly 32,767 units before its NUL
- **THEN** the review reports `reviewer_failed`, exit 3, with `exit_code: 127` beside its receipt, as before this change, and neither that invocation nor its helper starts; the reviewer's `--version` probe may run first

#### Scenario: A base-branch read behind the helper
- **WHEN** on Windows the local `git show-ref` probe for the base fits through the helper and finds nothing, and the remote probe fits on its own but not through the helper
- **THEN** the review reports `no_base`, as before this change, and the remote probe never starts

#### Scenario: A reviewer argument that cannot be represented
- **WHEN** a review run's reviewer command holds an argument with a NUL character
- **THEN** the run reports `not_utf8`, as before this change, with a message naming the argument

#### Scenario: An explicit omp run whose version probe is over the limit
- **WHEN** on Windows `sw review run --route omp` runs and the `omp --version` probe's command line is more than 32,767 visible units as given, or once `omp` resolves to a native executable
- **THEN** the review reports `not_utf8`, exit 1, with a message naming the command line, not `omp_too_old`, and the review invocation never starts

#### Scenario: An explicit omp run whose resolved version probe is exactly at the limit
- **WHEN** on Windows `sw review run --route omp` runs and the resolved native `omp --version` probe line is exactly 32,767 visible units
- **THEN** the probe is refused before start as a failed start, the review reports `omp_too_old` as a failed version probe did before this change, and the review invocation never starts

#### Scenario: An explicit omp run whose batch version probe is over the limit
- **WHEN** on Windows `omp` resolves to a short `omp.cmd` whose raw `cmd.exe` line for `--version` is over the limit
- **THEN** the probe does not start and the review reports `omp_too_old`, as before this change

#### Scenario: A line of exactly 32,767 units before lookup
- **WHEN** on Windows a command given as a line of exactly 32,767 units resolves to a `.cmd` or `.bat` shim, and its resolved batch payload is over the batch line limit
- **THEN** the caller reports the batch-line refusal it gives before this change, not an unrepresentable command line

#### Scenario: A line of exactly 32,767 units that resolves shorter
- **WHEN** on Windows a native command given as a line of exactly 32,767 units resolves to a path that makes the started line 32,766 units or fewer, launched directly rather than behind the bounded-run helper
- **THEN** the command starts and receives its arguments unchanged; a bounded launch also needs its helper line to fit

#### Scenario: A review's Git read over the limit
- **WHEN** on Windows a Git read the review run makes, such as its `git show-ref` base lookup, has a command line of more than 32,767 units as given, or once `git` resolves to a native executable
- **THEN** the review reports that refusal as `not_utf8`, as before this change, not as a missing base

#### Scenario: A review's Git read the old checks admitted
- **WHEN** on Windows a review's Git read resolves to a native executable and its line is exactly 32,767 visible units, so it is over the limit only with its terminating NUL
- **THEN** the read is refused before start and the review reports what a failed start gave before this change (`no_base` when no other base ref is found, `not-a-repo` for the first repository read)

#### Scenario: A review's Git read through a batch shim over the limit
- **WHEN** on Windows `git` resolves to a `.cmd` shim, the read's batch payload fits, and its raw `cmd.exe` line or its helper line is over the limit
- **THEN** the read is refused before start and the review reports what a failed start gave before this change (`no_base` when no other base ref is found, `not-a-repo` for the first repository read)

#### Scenario: A route probe through a batch shim over its limit
- **WHEN** on Windows `omp` resolves to `omp.cmd` and the configured model puts the `omp models find` probe's batch line over 8,191 units
- **THEN** `omp models find` never starts, `omp` is skipped with a reason naming the unrepresentable command line, and selection continues in `review.order` to the first eligible route, or `subagent` when none is, not `internal_error`

#### Scenario: A route probe behind the helper
- **WHEN** on Windows the `omp` route's configured model makes the `omp models find` probe's line too long, either for a check that existed before this change (the line as given more than 32,767 visible units) or only for a check this change adds (a resolved native line of exactly 32,767 visible units, or a helper line over the limit)
- **THEN** `omp models find` never starts, `omp` is skipped with the reason `unrepresentable command line: <resolved path>` for the older check and with the failed-probe reason it gives before this change (`probe failed: omp models find exited 127`) for a newly refused line, the exact 32,767 boundary included, and selection continues in `review.order` to the first eligible route, or `subagent` when none is

### Requirement: Arguments reach native executables unchanged
A native executable (anything but a `.cmd` or `.bat` file) SHALL start with no shell before it and receive every argument value unchanged, as UTF-8 on Linux and macOS, up to the OS command-line limit (32,767 UTF-16 units on Windows). Input the launcher cannot represent SHALL be refused by name before any start. On Windows, for `bash -c <script> <name> <args...>`, the arguments after `<name>` SHALL travel on stdin as in `bounded.py`, so Git Bash's 8,186-character cut cannot shorten them.

#### Scenario: A long argument to a native executable
- **WHEN** an argument of 20,000 characters with spaces, quotes, backslashes, newlines, Unicode and an empty argument beside it is passed to a native executable after `--`
- **THEN** the executable receives every argument value unchanged, with its boundaries

#### Scenario: Arguments that fit only once they move to stdin
- **WHEN** on Windows a `sw run --bounded -- bash -c <script> <name> <args...>` call's line with its arguments would pass the limit, but the line left after they move to stdin fits, and so does the helper's own command line carrying it
- **THEN** the call runs and receives every argument unchanged

#### Scenario: A long argument through bash -c on Windows
- **WHEN** on Windows `sw run --bounded -- bash -c 'printf %s "$1"' name <20,000-character argument>` runs
- **THEN** stdout is the whole argument, unchanged

#### Scenario: A missing transport end marker
- **WHEN** the bash prelude reads its stdin and finds no end marker
- **THEN** the script does not run and the exit status is 126

#### Scenario: An argument the launcher cannot represent
- **WHEN** an argument after `--` holds a NUL
- **THEN** `sw` exits 2 with `bounded: unrepresentable argument: <cmd>` on stderr and starts no process

### Requirement: sw reports its version and interface version
`sw version --json` SHALL print exactly one JSON object on stdout with `version`, the Specwright version the binary was built from (the `VERSION` file at build time), and `interface`, a positive integer that changes whenever a command's arguments, JSON output or exit codes change incompatibly. It SHALL exit 0. This change sets `interface` to 3.

#### Scenario: Version report of a CI build
- **WHEN** `sw version --json` runs on a binary CI built from a tree whose `VERSION` reads `0.23.0`
- **THEN** stdout is one JSON object with `"version": "0.23.0"` and `"interface": 3`, stderr is empty and the exit status is 0

#### Scenario: Unknown command or flag
- **WHEN** `sw` runs with no arguments, an unknown command such as `sw frobnicate`, or `sw version --bogus`
- **THEN** it prints a usage line naming the valid commands on stderr, prints nothing on stdout and exits 2


### Requirement: Skills check the project version before running sw
Before building the `<sw>` path, a skill SHALL check that the project's `VERSION` is `x.y.z` with an optional pre-release or build suffix and stop otherwise. Before the first other command of a run it SHALL run `<sw> version --json` with a 10-second tool timeout, and stop unless it exits 0 in time with one JSON object naming the project's version and interface 3.

#### Scenario: VERSION is not a version
- **WHEN** a skill reads `VERSION` holding `../../planted/.specwright/bin/0.38.0`
- **THEN** the skill tells the agent to stop before building any path and to tell the user to rerun the install prompt, and no process is started from that value

#### Scenario: The version probe hangs or floods
- **WHEN** the binary at `<sw>` does not answer `version --json` within 10 seconds, prints something other than one JSON object, or exits non-zero even with a matching JSON object
- **THEN** the skill tells the agent to stop the probe, run no other `sw` command, and tell the user to rerun the install prompt

#### Scenario: An older project with newer skills
- **WHEN** user-level skills of this version serve a project whose `VERSION` reads `0.38.0`, and `<sw> version --json` reports interface 2, or a project at `0.37.0` whose binary reports interface 1
- **THEN** the skill tells the agent to stop before any other `sw` command and to tell the user to update that project, and no command but `version --json` reaches the older binary

### Requirement: Project commands check the project's version
`sw vcs`, `sw pr`, `sw as`, `sw commit`, `sw finish`, `sw review`, `sw release` and `sw gate` SHALL read the project's `openspec/.specwright/VERSION` before any other work (`finish undo-archive-plan`: after option checks). When it is missing, is not a version or differs from the running `sw`'s version, they SHALL print one JSON document with `"ok": false`, `"error": "sw_mismatch"` and a `message` naming the running version, the project's value and the expected binary path, and SHALL exit 1.

#### Scenario: Matching version
- **WHEN** `sw` 0.38.0 runs `vcs state` in a project whose `VERSION` reads `0.38.0`
- **THEN** it prints the state document as usual

#### Scenario: Another version
- **WHEN** `sw` 0.38.0 runs `vcs commit` in a project whose `VERSION` reads `0.39.0`
- **THEN** it prints the `sw_mismatch` document naming `0.38.0`, `0.39.0` and `<home>/.specwright/bin/0.39.0/sw`, exits 1, and runs no `git` and writes nothing

#### Scenario: No VERSION
- **WHEN** a project command runs in a checkout with no `openspec/.specwright/VERSION`
- **THEN** it prints the `sw_mismatch` document saying no installed version was found and to rerun the install prompt, exits 1, and does no other work

#### Scenario: A fenced call with another version
- **WHEN** `sw as sh1ny gh pr comment 5 --body-file b` runs in a project of another version
- **THEN** stdout holds only the `sw_mismatch` document, the exit status is 1, and no `gh` command and no credential lookup ran

#### Scenario: The undo planner validates options first
- **WHEN** `sw finish undo-archive-plan` runs without `--change` in a project of another version
- **THEN** it reports `usage`, exit 2, not `sw_mismatch`, and runs no `git`

### Requirement: The project is chosen by --project, then the command's own argument
A project command SHALL take an optional leading `--project <code checkout>`, used only to choose the `VERSION` to check; it SHALL change neither the working directory, the target repositories nor the login. Without it the project SHALL be the command's code-checkout argument (`--code`, else `--repo` for `vcs`, `--dir` for `release` and `finish`), else the current directory, each walked up to the first directory holding `.git`. An undo plan's relative `--code` starts at the `--dir` root.

#### Scenario: A store-started call
- **WHEN** the current directory is a planning store with no `VERSION` and `sw --project <code checkout> pr pair-state ...` runs
- **THEN** `sw` checks the code checkout's `VERSION`, and the subcommand runs with the store as its working directory and its own arguments unchanged

#### Scenario: Store-started call without --project
- **WHEN** the same call runs without `--project` and without `--code`
- **THEN** it prints the `sw_mismatch` document saying no installed version was found in the store, exits 1, and does no other work

#### Scenario: Two leading --project options
- **WHEN** a call starts with `--project a --project b`
- **THEN** `sw` stops with a usage error, exit 2, and does no other work

#### Scenario: A relative --code in the undo planner
- **WHEN** `sw finish --dir <store> undo-archive-plan ... --code ../code` runs from outside the store
- **THEN** the version checked is that of `../code` taken from the store's root, not from the current directory

## ADDED Requirements

### Requirement: A bounded launch checks the helper's own command line
For every launch through the bounded helper (`gh` calls, other bounded commands, `.cmd` and `.bat` launches, `sw run --bounded` and review runs), the Windows line checked SHALL be the helper's own command line as it is started, so a tool line that fits alone but not behind the helper is refused before start. A refusal the old checks did not make SHALL be reported as a failed helper start. Checks the caller runs first, such as the identity fence's, may already have run.

#### Scenario: A line that fits only without the helper
- **WHEN** on Windows a bounded call's tool line fits the limit alone but not behind the helper
- **THEN** neither the helper nor the tool starts, and the call reports a failed helper start

### Requirement: A caller's check of the command as given keeps its limit
A caller's check of a command as given, before lookup, SHALL keep its limit of 32,767 UTF-16 units without the NUL; the started line's limit, with its NUL, applies after lookup.

#### Scenario: A command exactly at the caller's limit
- **WHEN** on Windows a command as given is exactly 32,767 visible units
- **THEN** the caller's check passes it, and the started line is then checked with its NUL

### Requirement: The failed-job log call caps its two streams together
The `gh run view --log-failed` call of `sw pr snapshot --logs` SHALL count stdout and stderr against one shared cap, and SHALL report `response_too_large` with no partial log when their sum passes it. This is the one exception to "Launch bounds are unchanged by the launcher", whose capped calls bound stdout only; every other call keeps its bound.

#### Scenario: Two streams under their old separate caps
- **WHEN** the failed-job log call writes 20 MiB to stdout and 20 MiB to stderr, each under the old per-stream cap but together over the shared one
- **THEN** the snapshot reports `response_too_large` for the log, prints no partial log and exits 1


### Requirement: Command lookup takes only files the user can execute
On Linux and macOS, `PATH` lookup SHALL take a file only when the current process, by its effective user and group IDs, can execute it. A same-named file the user cannot execute SHALL be skipped and the search SHALL go on down `PATH`, as the shell does. A name given with a path separator SHALL keep its current handling.

#### Scenario: A file only another user can run comes first
- **WHEN** on Linux or macOS, run as a user other than root, `PATH` is `/a:/b`, `/a/tool` is owned by that user with mode 0070 (execute for its group only), `/b/tool` has mode 0755, and `sw run --bounded -- tool` runs
- **THEN** `/b/tool` runs, because the owner's own bits deny execution although a group bit is set

#### Scenario: No file the user can execute
- **WHEN** the only `tool` on `PATH` is one the current user cannot execute
- **THEN** `sw` exits 127 and names `tool` on stderr

#### Scenario: An explicit path the user cannot execute
- **WHEN** on Linux or macOS, run as a user other than root, `sw run --bounded -- ./tool` names a file owned by that user with mode 0070
- **THEN** the start fails with the same permission diagnostic and exit status as before this change, not `command not found`

### Requirement: The undo plan's Git steps carry their safety options
The Git steps of `sw finish undo-archive-plan` SHALL carry `--literal-pathspecs` and `--no-replace-objects` on every Git command, name the archive parent by its resolved OID, and the resume checkout SHALL carry `--no-overwrite-ignore` and `--no-recurse-submodules`. Where this differs from "Printed commands name sw", which keeps directly printed `git` commands as the old scripts printed them, it SHALL take precedence for those steps only; every other printed command keeps that requirement.

#### Scenario: An undo plan's Git step
- **WHEN** `sw finish undo-archive-plan` prints a Git step
- **THEN** its argv is `git --literal-pathspecs --no-replace-objects` followed by the subcommand and arguments it had before, with a commit OID where it named `<archive>^`, and the resume checkout also has `--no-overwrite-ignore` and `--no-recurse-submodules`

#### Scenario: A resume with submodule recursion enabled
- **WHEN** `submodule.recurse` is true, an initialized submodule is clean on a local branch, and the archive branch records another gitlink for it
- **THEN** the resume checkout leaves the submodule's HEAD, branch and files unchanged

#### Scenario: Another printed command
- **WHEN** `sw` prints a `git`, `jj` or `openspec` command outside the undo plan
- **THEN** it is as the old scripts printed it

### Requirement: The project root is found from the physical path
For every project command, `sw` SHALL resolve an existing version-check start (`--project`, `--code` or `--dir`, else the current directory) to its physical path, symbolic links resolved, before it looks upward for the checkout whose `VERSION` it checks. A start that does not exist SHALL keep its given form. `--project` still selects only the `VERSION` checked, not the repository a command acts on.

#### Scenario: A project path through a link and `..`
- **WHEN** on POSIX `sw --project /A/link/.. vcs state --repo /C --role code` runs, `link` points to `/B/subdir`, and only `/B`'s `VERSION` matches the running `sw`
- **THEN** the version check reads `/B`, the command proceeds, and the state document's `head` is `/C`'s
