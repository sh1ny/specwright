# Spec Delta

## MODIFIED Requirements

### Requirement: sw starts external tools without a shell
For its own work `sw` SHALL start each external tool (`git`, `gh`, `jj`, `but`, reviewer CLIs and the like) directly, with no `bash`, `sh` or `cmd.exe` between `sw` and the tool, apart from `.cmd` and `.bat` commands on Windows, which run through `cmd.exe` as the batch-shim requirement states. A fenced command the caller asked for by name SHALL run as given, even when it is a shell or an interpreter.

#### Scenario: Ported commands with failing shells first on PATH
- **WHEN** on Linux, Windows and macOS `sw vcs` state, commit, fetch-main and push, `sw finish undo-archive-plan`, `sw commit task-cover` and `fit-subject`, and the `sw pr` workflow commands run with a `bash` and an `sh` that record their start and exit 1 placed first on `PATH`
- **THEN** each returns the document or output it returns with working shells, and neither recorder ran

#### Scenario: An absolute-path shell is not used either
- **WHEN** the same commands run and `/bin/bash`, `/bin/sh` or the Git Bash binary is the only shell present
- **THEN** no shell process is started by `sw` for its own work, as the launch-site test and a process trace of the eval run show

#### Scenario: A fenced shell command the caller asked for
- **WHEN** `sw as sh1ny bash -c 'exit 7'` runs after the identity check passes
- **THEN** `bash` starts as the fenced command and the exit status is 7

### Requirement: Tool lookup, exit status and stdin keep their contract
The native launcher SHALL find a command as `sw run --bounded` finds it, resolving a command path or `PATH` entry that is relative against the working directory the caller names, not `sw`'s own, SHALL report a command it cannot find with exit 127 and the command's name on stderr, SHALL give the tool the stdin its caller passes or inherits, and SHALL report a tool ended by a signal as 128 plus the signal number on Linux and macOS.

#### Scenario: A tool found on PATH gets its stdin
- **WHEN** a launched `git check-ignore -z --stdin` reads NUL-separated names from the stdin `sw` passes it
- **THEN** it receives exactly those names and its output and exit status come back to the caller

#### Scenario: A relative lookup resolves in the call's directory
- **WHEN** on Linux `PATH` starts with an empty entry, `sw`'s own directory holds an executable `git` that records its start, and a launch of `git status` names repository B as its working directory, where no `git` file exists
- **THEN** the recorder in `sw`'s directory did not run and the `git` found later on `PATH` ran in B

#### Scenario: A fenced batch command keeps the caller's stdio
- **WHEN** on Windows `sw as sh1ny fake.cmd` runs after the identity check passes, where `fake.cmd` reads one line from stdin, prints it and whether `GH_TOKEN` is set, and exits 3
- **THEN** the line the caller wrote on stdin appears on the caller's stdout with `GH_TOKEN` set, no helper frame appears on stderr, and the exit status is 3

#### Scenario: A missing tool
- **WHEN** `PATH` holds no `jj` and `sw vcs state` runs on a repo configured with `vcs: jj`
- **THEN** the document reports the same `tool_missing` stop and exit status as before this change, and no shell was started to look for `jj`

#### Scenario: A tool ended by a signal
- **WHEN** on Linux or macOS a fenced command is killed by SIGTERM
- **THEN** the fence ends with status 143, the status a bash caller saw before this change

## ADDED Requirements

### Requirement: A command shown without its required options means the workflow's call
Where a requirement or scenario shows an `sw` command without options it requires (`--download` for `sw update` reads of the download, `--code` for `sw pr context`, `--repo` and `--role` for `sw vcs`, the task and change options of `sw commit task-cover`, the change options of `sw review run`), it SHALL mean the call the workflow makes with them, and its asserted outcome SHALL be that call's. A usage stop for a missing option is meant only where the text says the option is missing.

#### Scenario: A shortened call
- **WHEN** a scenario says `sw pr context --branch feat/add-c` stops with `settings_not_pinned`
- **THEN** it means `sw pr context --code <code> --branch feat/add-c` run as the workflow runs it, and that call stops with `settings_not_pinned`

#### Scenario: A missing option named on purpose
- **WHEN** a scenario says `sw update plan` runs without `--download`
- **THEN** it means that call, which prints a `usage` document and exits 2
