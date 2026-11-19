# Spec Delta

## ADDED Requirements

### Requirement: Skills run sw directly
Shipped skills, the schema, the agent definitions and the README SHALL tell the agent to run `<sw> <command> [arguments]`, where `<sw>` is `<home>/.specwright/bin/<project VERSION>/sw` (`sw.exe` on Windows) and `<home>` is `SPECWRIGHT_HOME` when set, else the user's home. They SHALL name no shipped script, give no bash-only command, and never use an `sw` on `PATH`.

#### Scenario: A skill step names sw
- **WHEN** the shipped skill text is searched for the commands it gives the agent
- **THEN** each Specwright command starts with `<sw>`, and no command names `vcs.sh`, `as.sh`, `pr-pair.sh`, `pr-snapshot.sh`, `pr-reply.sh`, `sw-path.sh`, `task-cover.sh`, `fit-subject.sh`, `finish.sh`, `review-run.sh`, `release.sh`, `update.sh` or a `.py` file

#### Scenario: The binary is not there
- **WHEN** the agent runs `<sw>` for a project whose `VERSION` reads `0.38.0` and `<home>/.specwright/bin/0.38.0/` holds no `sw`
- **THEN** the skill tells the agent to stop the step and tell the user to rerun the install prompt, and never to try another version's binary or one on `PATH`

### Requirement: Skills check the project version before running sw
Before building the `<sw>` path, a skill SHALL check that the project's `VERSION` is `x.y.z` with an optional pre-release or build suffix and stop otherwise. Before the first other command of a run it SHALL run `<sw> version --json` with a 10-second tool timeout, and stop unless it exits 0 in time with one JSON object naming the project's version and interface 2.

#### Scenario: VERSION is not a version
- **WHEN** a skill reads `VERSION` holding `../../planted/.specwright/bin/0.38.0`
- **THEN** the skill tells the agent to stop before building any path and to tell the user to rerun the install prompt, and no process is started from that value

#### Scenario: The version probe hangs or floods
- **WHEN** the binary at `<sw>` does not answer `version --json` within 10 seconds, prints something other than one JSON object, or exits non-zero even with a matching JSON object
- **THEN** the skill tells the agent to stop the probe, run no other `sw` command, and tell the user to rerun the install prompt

#### Scenario: An older project with newer skills
- **WHEN** user-level skills of this version serve a project whose `VERSION` reads `0.37.0`, and `<sw> version --json` reports interface 1
- **THEN** the skill tells the agent to stop before any other `sw` command and to tell the user to update that project, and no direct-argument command reaches the interface-1 binary

### Requirement: sw takes its arguments directly
Every `sw` command SHALL take its arguments as the process's own argument list, with no stdin or file handoff and no script directory or bash record, and SHALL treat each argument as one whole value. `sw` SHALL convert no MSYS-form path itself: a path reaches a command as the caller's shell passed it.

#### Scenario: Arguments with spaces and non-ASCII text
- **WHEN** `sw vcs commit --repo "<dir with a space>" --role code --branch feat/x --message-file "m é.txt" -- "a b.md"` runs on Linux, Windows and macOS
- **THEN** `sw` reads the repository, message file and path each as one whole value, with the same bytes the caller passed

#### Scenario: The old handoff flag
- **WHEN** a caller runs `sw vcs --args-stdin state` or `sw as --args-file <path>`
- **THEN** `sw` stops with a usage error naming the unknown option, exit 2, reads no stdin and no file, and does no other work

#### Scenario: An MSYS path given from PowerShell
- **WHEN** on Windows a caller that is not Git Bash passes `--repo /c/Users/u/p`
- **THEN** `sw` uses the value as given, a root-relative Windows path, and stops with the command's existing error for a directory that does not exist

### Requirement: Arguments sw cannot represent are refused
An argument that is not well-formed Unicode as it reaches the process SHALL be refused before any work. `sw` SHALL check the raw argument list the OS holds and, on a malformed argument, print one JSON document with `"ok": false`, `"error": "bad_argument"` and a `message` naming its position, and exit 2. On Linux and macOS the Dart runtime refuses non-UTF-8 bytes before `sw`'s code runs; that refusal (non-zero exit, empty stdout, nothing run) stands in for the document there (ADR 0040, C6).

#### Scenario: A well-formed argument
- **WHEN** an argument holds `日本語` or an emoji
- **THEN** `sw` takes it unchanged and does its work

#### Scenario: A valid U+FFFD is just a character
- **WHEN** an argument holds the character U+FFFD, well-formed, on Linux, Windows and macOS
- **THEN** `sw` takes it unchanged and does its work; no `bad_argument` document is printed

#### Scenario: A lone surrogate on Windows
- **WHEN** on Windows an argument holds an unpaired UTF-16 surrogate
- **THEN** `sw` prints the `bad_argument` document naming that argument's position, exits 2, starts no process and writes no file

#### Scenario: Bytes that are not UTF-8 on Linux and macOS
- **WHEN** on Linux or macOS an argument holds the byte `0xFF`
- **THEN** the process exits non-zero with an empty stdout before `sw`'s own code runs, starts no process and writes no file

### Requirement: Project commands check the project's version
`sw vcs`, `sw pr`, `sw as`, `sw commit`, `sw finish`, `sw review`, `sw release` and `sw gate` SHALL read the project's `openspec/.specwright/VERSION` before any other work. When it is missing, is not a version or differs from the running `sw`'s version, they SHALL print one JSON document with `"ok": false`, `"error": "sw_mismatch"` and a `message` naming the running version, the project's value and the expected binary path, and SHALL exit 1.

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

### Requirement: The version check reads only a version
The check SHALL accept the project's `VERSION` only when it is `x.y.z` with an optional pre-release or build suffix, after trimming surrounding whitespace and line endings. Any other value SHALL give the `sw_mismatch` document saying the value is not a version.

#### Scenario: VERSION with CRLF
- **WHEN** `VERSION` reads `0.38.0\r\n` and `sw` is 0.38.0
- **THEN** the check passes

#### Scenario: VERSION names a path
- **WHEN** `VERSION` reads `../../../planted/.specwright/bin/0.38.0`
- **THEN** the command prints the `sw_mismatch` document saying the value is not a version, exits 1, and does no other work

### Requirement: Commands that check no project version
`sw version`, `sw run --bounded`, `sw update`, `sw pr reviewers` (the evaluator, which reads only the files it is given and runs no tool) and the internal process helper SHALL do no project version check, so a probe, a bounded run, an evaluator child and an install or update of another version work in any directory.

#### Scenario: Update across versions
- **WHEN** a downloaded `sw` 0.39.0 runs `update plan` in a project whose `VERSION` reads `0.38.0`
- **THEN** no `sw_mismatch` stop happens, and the update plan is printed

#### Scenario: Evaluator child of a store-started snapshot
- **WHEN** `<sw> --project <code> pr snapshot 12 --reviewer-config <file>` runs with the store as its working directory, which has no `VERSION`
- **THEN** the snapshot starts its `pr reviewers` child, the child evaluates without a version check, the snapshot prints its document, and a pattern that backtracks past the poll deadline still kills the child

#### Scenario: Version outside a project
- **WHEN** `sw version --json` runs in a directory with no repository
- **THEN** it prints its version document and exits 0

### Requirement: The project is chosen by --project, then the command's own argument
A project command SHALL take an optional leading `--project <code checkout>`, used only to choose the `VERSION` to check; it SHALL change neither the working directory, the target repositories nor the login. Without it the project SHALL be the command's code-checkout argument (`--code`, else `--repo` for `vcs`, `--dir` for `release` and `finish`), else the current directory, each walked up to the first directory holding `.git`.

#### Scenario: A store-started call
- **WHEN** the current directory is a planning store with no `VERSION` and `sw --project <code checkout> pr pair-state ...` runs
- **THEN** `sw` checks the code checkout's `VERSION`, and the subcommand runs with the store as its working directory and its own arguments unchanged

#### Scenario: Store-started call without --project
- **WHEN** the same call runs without `--project` and without `--code`
- **THEN** it prints the `sw_mismatch` document saying no installed version was found in the store, exits 1, and does no other work

#### Scenario: Two leading --project options
- **WHEN** a call starts with `--project a --project b`
- **THEN** `sw` stops with a usage error, exit 2, and does no other work

### Requirement: Retired script names map to sw commands
Where a requirement names a retired script, it SHALL mean the matching `sw` command with the same arguments and contract: `vcs.sh` is `sw vcs`, `as.sh` is `sw as`, `pr-pair.sh` is `sw pr`, `pr-snapshot.sh` and `pr-reply.sh` are `sw pr snapshot` and `sw pr reply`, `task-cover.sh` and `fit-subject.sh` are `sw commit task-cover` and `fit-subject`, `finish.sh` is `sw finish`, and `review-run.sh`, `release.sh` and `update.sh` are `sw review`, `sw release` and `sw update`.

#### Scenario: A requirement naming a script
- **WHEN** a requirement says `vcs.sh fetch-main` prints a `ref`
- **THEN** `sw vcs fetch-main` prints that `ref`, under the same rules

#### Scenario: The Python helpers
- **WHEN** a requirement names `bounded.py` or `reviewers.py`
- **THEN** it means `sw run --bounded` or `sw pr reviewers` respectively

#### Scenario: A requirement about a removed shim behaviour
- **WHEN** a requirement describes a shim's own resolution, handoff, `sw_missing` or `no_python` behaviour
- **THEN** it does not apply: the version check and the direct argument entry above replace it

### Requirement: Review reference files are built into sw
`sw review` SHALL take the review brief and the findings schema from copies built into the binary at build time from `skills/specwright-review/references/`, never from a file at run time. Where a reviewer needs the schema as a file, `sw` SHALL write its copy into the run's own directory and name that path.

#### Scenario: A review run without the skill folder
- **WHEN** `sw review run --kind preship ...` runs with no `skills/specwright-review/references/` anywhere on disk
- **THEN** the prompt holds the brief, the findings are validated against the built-in schema, and the run succeeds as before

#### Scenario: A build whose copies differ from the sources
- **WHEN** CI checks a build whose built-in brief or schema differs from `skills/specwright-review/references/`
- **THEN** the check fails, naming the file

### Requirement: Printed commands name sw
Every command `sw` prints for an agent or a user to run (undo-archive plans, `vcs` plans, cleanup and recovery steps) SHALL name no shipped script and no `bash`. Each one that runs Specwright's own work SHALL start with the absolute path of the running `sw`; `git`, `jj` and `openspec` commands the old scripts printed directly stay as they were.

#### Scenario: An undo-archive plan
- **WHEN** `sw finish undo-archive-plan` prints its plan
- **THEN** each step the old script ran through `vcs.sh` has an argv of the running binary's absolute path, `--project <code>`, `vcs` and the old subcommand with its arguments, a state check the old script made by text becomes an `undo-step check` step, the `git` and `jj` steps the old script ran directly stay `git` and `jj` steps, and no step names `vcs.sh` or `bash`

#### Scenario: A cleanup plan that pulls under the fence
- **WHEN** a PR cleanup plan prints a fenced `git pull --ff-only`
- **THEN** that step starts with the running binary's absolute path followed by `--project <code> as <login> git pull --ff-only`, and no step names `as.sh`

### Requirement: Commands run with no scripts and no interpreters
On Linux, Windows and macOS, black-box evals SHALL run the `vcs`, `pr`, `as`, `commit`, `finish`, `review`, `release`, `update` and `gate` commands with no shipped script on disk and with `python`, `python3`, `bash` and `sh` that record their start and exit 1 first on `PATH`.

#### Scenario: All commands without scripts or interpreters
- **WHEN** those evals run
- **THEN** each command returns the document or output it returns in a normal environment, and no recorder ran

#### Scenario: A fenced shell the caller asked for
- **WHEN** `sw as sh1ny bash -c 'exit 7'` runs in that environment
- **THEN** the recording `bash` (on Windows its `.cmd` wrapper) starts as the fenced command and exits 1, and `sw as` exits 1 with it

### Requirement: sw runs no POSIX utilities for its own work
`sw` SHALL create temporary files and directories, links, pauses, timestamps, system limits and physical working directories with its own operations, starting no `mktemp`, `ln`, `sleep`, `date`, `getconf`, `pwd` or `cygpath`.

#### Scenario: Failing utilities first on PATH
- **WHEN** on Linux, Windows and macOS the ported commands run with recording `mktemp`, `ln`, `sleep`, `date`, `getconf`, `pwd` and `cygpath` that exit 1 placed first on `PATH`
- **THEN** each returns the result it returns without them, and no recorder ran

#### Scenario: A path from Git Bash on Windows
- **WHEN** on Windows Git Bash runs `<sw> vcs state --repo /c/Users/u/p --role code`
- **THEN** `sw` receives the path as `C:/Users/u/p`, converted by Git Bash itself, works on it, and no `cygpath` ran

### Requirement: sw run --bounded keeps its Windows bash -c transport
Removing the shim handoff SHALL NOT remove the Windows transport `sw run --bounded` uses for a caller-requested `bash -c <script> <name> <args...>`: the arguments after `<name>` SHALL still travel on stdin, so Git Bash's 8,186-character cut cannot shorten them. It is used only when the caller asks for bash, never for `sw`'s own work.

#### Scenario: A long argument through caller-requested bash on Windows
- **WHEN** after the scripts are removed, on Windows `sw run --bounded -- bash -c 'printf %s "$1"' name <20,000-character argument>` runs
- **THEN** the script prints the whole argument unchanged, and the launch-site test lists this transport as a caller-requested shell site

## MODIFIED Requirements

### Requirement: JSON input that is not plain JSON is refused
`sw` SHALL read files and gh responses as standard JSON, preserving command-specific unreadable-input refusals. No BigInt SHALL reach a document: integer settings follow the caller-specific problem/default rules below; oversized raw policy values use settingText. Task-cover SHALL ignore oversized task, subject, trailer and heading group numbers.

#### Scenario: Well-formed input
- **WHEN** `sw pr reviewers --material m.json --head <oid>` reads a valid JSON material file
- **THEN** it evaluates the material and exits 0

#### Scenario: Non-finite number
- **WHEN** a reviewer material file holds `NaN` or `Infinity` as a number
- **THEN** the command exits 1, prints one stderr line prefixed `reviewers.py:` naming the file, and prints nothing on stdout

#### Scenario: Very deep nesting
- **WHEN** a JSON input is nested 100,000 levels deep
- **THEN** the command stops with its unreadable-input error or reads the input whole; it never crashes with a stack trace

#### Scenario: An integer that cannot be held exactly
- **WHEN** a reviewer-config timeout holds an integer beyond signed 64-bit range
- **THEN** reviewers reports its config error with exit 2 and nothing on stdout, without comparing a rounded value

#### Scenario: A JSON file over the size limit
- **WHEN** a reviewer material file, reviewer config, policy snapshot, workflow snapshot, feedback intent or feedback record file is larger than 32 MiB
- **THEN** the command stops with its unreadable-input error naming the file, without decoding it

#### Scenario: An integer setting beyond 64 bits
- **WHEN** context reads openspec/specwright.yaml with a reviewer timeout beyond signed 64-bit range
- **THEN** it stops with bad_setting, exit 2, naming the key before writing any reviewer config; the rules layer supplies timeout default 1200 and no BigInt escapes

#### Scenario: Reviewer config for ordinary values
- **WHEN** a reviewer config is built from values within 64 bits
- **THEN** its bytes and digest equal those written before this change

#### Scenario: An oversized feedback record stays unreadable
- **WHEN** a new-key or matching legacy feedback record exceeds 32 MiB
- **THEN** the command retains its existing occupied/unreadable-record refusal, leaves the record untouched, and starts no replacement pass

#### Scenario: Oversized workflow and intent files
- **WHEN** a workflow snapshot or feedback intent exceeds 32 MiB, including at a raw POSIX path
- **THEN** its existing unreadable-input error and exit status are retained, and the intended file is neither truncated nor treated as absent

#### Scenario: Feedback integers are exact
- **WHEN** a feedback intent round exceeds the signed 64-bit range
- **THEN** pass-write reports invalid_intent and publishes no record instead of comparing a rounded value

#### Scenario: rounds with max_fix_rounds beyond 64 bits stops with bad_setting
- **WHEN** rounds reads max_fix_rounds beyond signed 64-bit range
- **THEN** the rules layer reports bad_setting and substitutes 2, and workflowContexts collects the problem so rounds stops with bad_setting and exit 2 instead of encoding or comparing a BigInt; pass callers use the same rule

#### Scenario: policy lists an oversized head integer in invalid and exits 0
- **WHEN** main has valid settings and the head sets a reviewer timeout beyond signed 64-bit range
- **THEN** policy exits 0, names the key in invalid, and its values, drift comparison, pr.reviewers and reviewer config use default 1200 without a BigInt; the same problem on main stops through its bads path

#### Scenario: Lone surrogate keeps its pre-change digest
- **WHEN** a reviewer report string holds a lone surrogate
- **THEN** reviewer-config bytes and digest equal the fixed baseline captured before the change, replacing the surrogate with ? even if JsonEncoder needs the D1 string fallback

#### Scenario: Printed undo guard reads the compact branch
- **WHEN** `sw finish undo-archive-plan` plans an undo on a jj or GitButler repository
- **THEN** the plan's branch guard is an `undo-step check` step that reads the backend's branch value in process, not the text of a `vcs state` document, so the undo runs on the planned branch and refuses on another

#### Scenario: Watcher compact keys remain readable
- **WHEN** `sw pr reviewers` or a `gh --jq` read used by `sw pr snapshot` prints its document with a space after a `:` or `,`
- **THEN** the snapshot parses it and reads the same logins, recheck ids, failing check names and run ids, merge state, pending check count and completeness as from the compact form


### Requirement: sw starts itself only for its helper and the reviewer evaluator
For its own work `sw` SHALL start its own binary only as the bounded process helper and as the reviewer evaluator under a poll deadline. It SHALL never start a shipped script or a Python interpreter. Running another installed or downloaded `sw` to read its version and interface SHALL stay allowed. Printing a command for an agent or user to run is not a launch.

#### Scenario: Retrofitted paths with sentinels and no Python
- **WHEN** `sw vcs` fetch, pull and push against github.com, `sw pr snapshot` with a reviewer config, and the PR workflow commands run with no shipped script on disk and failing `python` and `python3` first on `PATH`, on Linux, Windows and macOS
- **THEN** each returns its expected document or output, and neither interpreter ran

#### Scenario: Reviewer evaluator stays a separate process
- **WHEN** a reviewer report pattern backtracks past the poll deadline
- **THEN** the evaluator child is killed at the deadline and the poll fails, while the snapshot process itself keeps running

#### Scenario: Printed commands are not launches
- **WHEN** `sw vcs plan` or a PR cleanup plan prints a command that names the running `sw`
- **THEN** the document holds that command and no process ran for it

#### Scenario: sw update checks a downloaded sw and starts no script
- **WHEN** `sw update sw-install` places a downloaded `sw` and an owner's `sw update swap` checks a jj store, with no scripts in the download and failing `python` and `python3` first on `PATH`
- **THEN** the downloaded binary ran only as `version --json`, and neither interpreter ran

### Requirement: A launch-site allowlist guards process starts
A test over `cli/lib/src`, run on Linux, Windows and macOS, SHALL list every call that starts a process and every caller of the process runners, and SHALL fail on a launch site missing from its allowlist, on a self-launch other than the helper and the evaluator, on a shipped script name in a launch's arguments, and on a retired script name written anywhere under `cli/lib/src` outside a listed message or label site.

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
- **WHEN** a source file under `cli/lib/src` writes `vcs.sh`, `as.sh` or another retired script name into a printed command
- **THEN** the test fails, naming the file and the script

#### Scenario: An absolute-path shell at a listed site fails
- **WHEN** a listed external-tool launch site is changed to start `/bin/bash`, `/bin/sh`, `sh` or Git Bash's `bash.exe` by absolute path for Specwright's own work, while every call count stays the same
- **THEN** the test fails, naming the site and the shell, while the fenced command site that runs a shell the caller asked for still passes

#### Scenario: The binary checks of sw update are listed
- **WHEN** the allowlist test runs on the `sw update` sources
- **THEN** the run of a downloaded or placed `sw` with `version --json` is listed as a binary check, and any other argument list at that site fails the test

### Requirement: sw reports its version and interface version
`sw version --json` SHALL print exactly one JSON object on stdout with `version`, the Specwright version the binary was built from (the `VERSION` file at build time), and `interface`, a positive integer that changes whenever a command's arguments, JSON output or exit codes change incompatibly. It SHALL exit 0. This change sets `interface` to 2.

#### Scenario: Version report of a CI build
- **WHEN** `sw version --json` runs on a binary CI built from a tree whose `VERSION` reads `0.23.0`
- **THEN** stdout is one JSON object with `"version": "0.23.0"` and `"interface": 2`, stderr is empty and the exit status is 0

#### Scenario: Unknown command or flag
- **WHEN** `sw` runs with no arguments, an unknown command such as `sw frobnicate`, or `sw version --bogus`
- **THEN** it prints a usage line naming the valid commands on stderr, prints nothing on stdout and exits 2

## REMOVED Requirements

### Requirement: A project's sw is found and checked before use
**Reason**: `sw-path.sh` is removed. Skills name the version-pinned path directly, and each project command checks the project's version itself.
**Migration**: See "Skills run sw directly" and "Project commands check the project's version".

### Requirement: A missing or mismatched sw stops with one message
**Reason**: There is no resolver to stop. A mismatched binary stops with `sw_mismatch`, and a missing binary fails to start, which the skills turn into "rerun the install prompt".
**Migration**: See "Project commands check the project's version" and "Skills run sw directly".

### Requirement: The resolver reads only a version from VERSION
**Reason**: The resolver is removed; the same rule now guards the version check.
**Migration**: See "The version check reads only a version".

### Requirement: sw needs no POSIX utilities for its own work
**Reason**: Its MSYS path conversion scenarios no longer apply: `sw` converts no MSYS path, because arguments arrive directly and Git Bash converts them itself.
**Migration**: See "sw runs no POSIX utilities for its own work" and "sw takes its arguments directly".
