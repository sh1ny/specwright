# Spec Delta

## ADDED Requirements

### Requirement: sw starts external tools without a shell
For its own work `sw` SHALL start each external tool (`git`, `gh`, `jj`, `but`, reviewer CLIs and the like) directly, with no `bash`, `sh` or `cmd.exe` between `sw` and the tool, apart from `.cmd` and `.bat` commands on Windows, which run through `cmd.exe` as the batch-shim requirement states. A fenced command the caller asked for by name SHALL run as given, even when it is a shell or an interpreter.

#### Scenario: Ported commands with failing shells first on PATH
- **WHEN** on Linux, Windows and macOS `sw vcs` state, commit, fetch-main and push, `sw finish undo-archive-plan`, `sw commit task-cover` and `fit-subject`, and the `sw pr` workflow commands run with a `bash` and an `sh` that record their start and exit 1 placed first on `PATH`
- **THEN** each returns the document or output it returns with working shells, and neither recorder ran

#### Scenario: An absolute-path shell is not used either
- **WHEN** the same commands run and `/bin/bash`, `/bin/sh` or the Git Bash binary is the only shell present
- **THEN** no shell process is started by `sw` for its own work, as the launch-site test and a process trace of the eval run show

#### Scenario: A fenced shell command the caller asked for
- **WHEN** `as.sh sh1ny bash -c 'exit 7'` runs after the identity check passes
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
- **WHEN** on Windows `as.sh sh1ny fake.cmd` runs after the identity check passes, where `fake.cmd` reads one line from stdin, prints it and whether `GH_TOKEN` is set, and exits 3
- **THEN** the line the caller wrote on stdin appears on the caller's stdout with `GH_TOKEN` set, no helper frame appears on stderr, and the exit status is 3

#### Scenario: A missing tool
- **WHEN** `PATH` holds no `jj` and `sw vcs state` runs on a repo configured with `vcs: jj`
- **THEN** the document reports the same `tool_missing` stop and exit status as before this change, and no shell was started to look for `jj`

#### Scenario: A tool ended by a signal
- **WHEN** on Linux or macOS a fenced command is killed by SIGTERM
- **THEN** the fence ends with status 143, the status a bash caller saw before this change

### Requirement: Launch bounds are unchanged by the launcher
A call that had a deadline or output bound before this change SHALL keep the same deadline and bound, and a deadline SHALL stop the tool's whole process tree. A call that had none SHALL get none from the launcher, whether the tool is a native executable or a `.cmd` or `.bat` file. A capped call SHALL bound stdout only, as before, and report overflow as its existing output-too-large result. Every call, bounded or not, SHALL run in the working directory its caller names.

#### Scenario: Bounded read with a descendant
- **WHEN** a fenced Git read under its existing deadline starts a descendant and hangs past the deadline
- **THEN** the tool and its descendant are stopped and the caller reports `deadline_exceeded`, as before this change

#### Scenario: Bounded read in another repository
- **WHEN** a `sw pr` workflow started in code repository A runs a bounded `git` read whose working directory is store B
- **THEN** the read reports B's state, not A's, and `sw`'s own working directory is unchanged afterwards

#### Scenario: An unbounded batch tool past the default byte bound
- **WHEN** on Windows an unbounded call starts a `.cmd` tool that prints 40 MiB on stdout and exits 0
- **THEN** the caller receives all 40 MiB and exit 0, with no deadline or output-too-large result

#### Scenario: A capped call with a loud stderr
- **WHEN** a capped `but` call (a `.cmd` on Windows, an executable on Linux) prints less than its stdout cap and 40 MiB on stderr
- **THEN** the call is not reported as output too large, and its exit status reaches the caller

#### Scenario: Unbounded fenced push
- **WHEN** `SPECWRIGHT_NET_DEADLINE` is 1 and a fenced `git push` takes 3 seconds before it succeeds
- **THEN** the push succeeds with no `deadline_exceeded`

### Requirement: Input the launcher cannot represent is refused by name
Before starting a tool, the launcher SHALL refuse an argument, environment value or working directory that holds a NUL or is not well-formed Unicode, naming the command and the input, and SHALL start no process. A caller with a JSON document SHALL report it as `"error": "not_utf8"` with exit 1; `sw run --bounded` SHALL print `bounded: unrepresentable argument: <cmd>` and exit 2.

#### Scenario: Ordinary Unicode arguments
- **WHEN** a launched tool is passed arguments holding spaces, quotes, backslashes, newlines, an empty value and non-ASCII letters
- **THEN** the tool receives each value unchanged, as UTF-8 on Linux and macOS and as the same characters on Windows

#### Scenario: An argument with a NUL
- **WHEN** `sw run --bounded -- tool "a<NUL>b"` runs
- **THEN** it exits 2 with `bounded: unrepresentable argument: tool` on stderr and no process starts

#### Scenario: A lone surrogate reaches the launcher
- **WHEN** an internal caller passes an argument holding a lone surrogate code unit
- **THEN** the caller's document has `"error": "not_utf8"`, the exit status is 1, and the tool did not start

### Requirement: Long Windows arguments reach native tools whole
On Windows a native tool SHALL receive every argument whole up to the OS command-line limit of 32,767 UTF-16 units, and a command line over that limit SHALL be refused before any process starts.

#### Scenario: A 20,000-character argument on Windows
- **WHEN** on Windows a 20,000-character argument with spaces, quotes and trailing backslashes is passed to a native tool
- **THEN** the tool receives the whole value unchanged

#### Scenario: Over the Windows command-line limit
- **WHEN** on Windows the quoted command line for a native tool exceeds 32,767 UTF-16 units
- **THEN** the caller reports the refusal with its usual error and exit status, and no process starts

### Requirement: sw needs no POSIX utilities for its own work
`sw` SHALL create temporary files and directories, links, pauses, timestamps, system limits, physical working directories and Windows path conversion with its own operations, starting no `mktemp`, `ln`, `sleep`, `date`, `getconf`, `pwd` or `cygpath`.

#### Scenario: Failing utilities first on PATH
- **WHEN** on Linux, Windows and macOS the ported commands run with recording `mktemp`, `ln`, `sleep`, `date`, `getconf`, `pwd` and `cygpath` that exit 1 placed first on `PATH`
- **THEN** each returns the result it returns without them, and no recorder ran

#### Scenario: An MSYS path argument on Windows
- **WHEN** on Windows a shim hands `sw` the path `/c/Users/u/m.txt`, and again `//server/share/m.txt`
- **THEN** `sw` works on `C:/Users/u/m.txt` and on the UNC path `//server/share/m.txt` respectively, and no `cygpath` ran

#### Scenario: A `/tmp` path on Windows
- **WHEN** on Windows a shim hands `sw` the path `/tmp/m.txt`, with `TEMP` set and the Git Bash install root not found from the handed-over bash
- **THEN** `sw` works on `m.txt` under the `TEMP` directory, and no `cygpath` ran

#### Scenario: A `/tmp` path with no TEMP
- **WHEN** on Windows a shim hands `sw` the path `/tmp/m.txt` and neither `TEMP` nor `TMP` is set
- **THEN** the command stops with its existing `bad_path` result naming `/tmp/m.txt`, and nothing else runs

#### Scenario: A root-relative MSYS path with no known Git Bash root
- **WHEN** on Windows a shim hands `sw` the path `/etc/m.txt` and the Git Bash install root cannot be found from the bash the shim handed over
- **THEN** the command stops with its existing `bad_path` result naming `/etc/m.txt`, and nothing else runs

## MODIFIED Requirements

### Requirement: Arguments reach native executables unchanged
A native executable (anything but a `.cmd` or `.bat` file) SHALL start with no shell before it and receive every argument value unchanged, as UTF-8 on Linux and macOS, up to the OS command-line limit (32,767 UTF-16 units on Windows). Input the launcher cannot represent SHALL be refused by name before any start. On Windows, for `bash -c <script> <name> <args...>`, the arguments after `<name>` SHALL travel on stdin as in `bounded.py`, so Git Bash's 8,186-character cut cannot shorten them.

#### Scenario: A long argument to a native executable
- **WHEN** an argument of 20,000 characters with spaces, quotes, backslashes, newlines, Unicode and an empty argument beside it is passed to a native executable after `--`
- **THEN** the executable receives every argument value unchanged, with its boundaries

#### Scenario: A long argument through bash -c on Windows
- **WHEN** on Windows `sw run --bounded -- bash -c 'printf %s "$1"' name <20,000-character argument>` runs
- **THEN** stdout is the whole argument, unchanged

#### Scenario: A missing transport end marker
- **WHEN** the bash prelude reads its stdin and finds no end marker
- **THEN** the script does not run and the exit status is 126

#### Scenario: An argument the launcher cannot represent
- **WHEN** an argument after `--` holds a NUL
- **THEN** `sw` exits 2 with `bounded: unrepresentable argument: <cmd>` on stderr and starts no process

### Requirement: sw documents are compact JSON ending in one line feed
Every JSON document `sw` prints SHALL be one compact JSON value followed by a single LF on every operating system. Consumers SHALL read a document by parsing it, never by matching its text, except the printed undo-archive branch guards, retained until `native-cli-retire-scripts`; those guards retain the compact `"branch"` key they require.

#### Scenario: Document on Windows
- **WHEN** `sw vcs probe` prints its document on Windows
- **THEN** stdout parses to the same fields as on Linux, holds no space between tokens outside strings, and ends in exactly one `\n` with no `\r`

#### Scenario: Non-UTF-8 file name in a document
- **WHEN** a `sw vcs` command meets a file whose name holds the byte 0xFF in an argument or in `git` or `jj` output, where it would report or act on that file (a name found by a directory walk is the next scenario)
- **THEN** stdout is valid UTF-8 JSON with `"error": "not_utf8"` and a `message` that shows the byte as `\xFF` and asks for a rename, and the exit status is 1

#### Scenario: Non-UTF-8 file name found by a directory walk
- **WHEN** a `sw vcs` directory walk meets a file whose name holds the byte 0xFF
- **THEN** stdout is valid UTF-8 JSON with `"error": "not_utf8"` and a `message` that names the file with the invalid byte shown as U+FFFD, because the listing does not give the raw bytes, and asks for a rename, and the exit status is 1

#### Scenario: A value a document cannot hold
- **WHEN** a command builds a document holding a value JSON cannot represent, such as a non-finite number
- **THEN** stdout is one JSON document with `"ok": false` and `"error": "internal_error"`, the exit status is 1, and no stack trace is printed

### Requirement: Batch shims get escaped arguments or none
On Windows a `.cmd` or `.bat` command SHALL run through `cmd.exe` with the path and every argument in double quotes, never caret-escaped, trailing backslashes doubled, so a program the shim forwards `%*` to reads each value unchanged. What quoting cannot protect SHALL be refused with `bounded: unsafe batch argument: <cmd>`, exit 2, before any start. A NUL argument SHALL be refused first, as unrepresentable input: `bounded: unrepresentable argument: <cmd>`, exit 2.

#### Scenario: Metacharacters reach the shim literally
- **WHEN** `sw run --bounded -- fake.cmd "a&b" "c|d" "<e>" "(f)" "g^h" "" "x & echo pwned"` runs a shim that forwards `%*` to a native program recording its arguments
- **THEN** the recorder receives exactly those seven arguments, values and boundaries unchanged, and no other command runs

#### Scenario: Trailing backslashes survive forwarding
- **WHEN** `sw run --bounded` runs the same forwarding shim with the four argument values `C:\two words\` (one trailing backslash), `D:\x\\` (two), `next` and the empty string
- **THEN** the recorder receives exactly those four values, with values and boundaries unchanged

#### Scenario: A shim found in a directory whose name cmd.exe would expand
- **WHEN** `fake.cmd` is resolved from a `PATH` directory literally named `C:\tools\%SW_SLOT%` and `SW_SLOT` names another directory holding a different `fake.cmd`
- **THEN** `sw` exits 2 with `bounded: unsafe batch argument: <cmd>` on stderr and neither shim runs

#### Scenario: An argument that cmd.exe would expand
- **WHEN** an argument to a `.cmd` command contains `%`, `!`, a double quote, CR or LF (for example `%PATH%` or `!x!`)
- **THEN** `sw` exits 2 with `bounded: unsafe batch argument: <cmd>` on stderr and starts no process

#### Scenario: A batch command line over the cmd.exe limit
- **WHEN** the escaped command line for a `.bat` command exceeds 8,191 characters
- **THEN** `sw` exits 2 with the same message and starts no process

#### Scenario: A NUL argument to a batch command
- **WHEN** on Windows `sw run --bounded -- fake.cmd "a<NUL>b"` runs, where the value also holds `%PATH%`
- **THEN** `sw` exits 2 with `bounded: unrepresentable argument: fake.cmd` on stderr, not the unsafe-batch message, and starts no process
