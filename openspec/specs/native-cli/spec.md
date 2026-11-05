# native-cli Specification

## Purpose

Defines `sw`, the compiled Dart executable that will replace Specwright's shipped bash and Python scripts: how it reports its version and interface, how it runs a command under bounds, and how it is built and checked on each platform.

## Requirements

### Requirement: sw reports its version and interface version
`sw version --json` SHALL print exactly one JSON object on stdout with `version`, the Specwright version the binary was built from (the `VERSION` file at build time), and `interface`, a positive integer that changes whenever a command's arguments, JSON output or exit codes change incompatibly. It SHALL exit 0. This change sets `interface` to 1.

#### Scenario: Version report of a CI build
- **WHEN** `sw version --json` runs on a binary CI built from a tree whose `VERSION` reads `0.23.0`
- **THEN** stdout is one JSON object with `"version": "0.23.0"` and `"interface": 1`, stderr is empty and the exit status is 0

#### Scenario: Unknown command or flag
- **WHEN** `sw` runs with no arguments, an unknown command such as `sw frobnicate`, or `sw version --bogus`
- **THEN** it prints a usage line naming the valid commands on stderr, prints nothing on stdout and exits 2

### Requirement: sw run --bounded keeps bounded.py's command-line contract
`sw run --bounded [--paged] [--secret] -- <cmd> [args...]` SHALL run the command and, when no limit hits, copy its stdout and stderr through after it ends and exit with its status. When a limit hits it SHALL print only `bounded: <limit>: <cmd> <first arg>` on stderr (for a `sh`/`bash -c` wrapper: the wrapped command and its first argument), nothing on stdout, and exit 124 for `deadline_exceeded` or 125 for `response_too_large`.

#### Scenario: Command finishes within its limits
- **WHEN** `sw run --bounded -- <cmd>` runs a command that prints `out` on stdout and `err` on stderr and exits 3
- **THEN** `sw` prints `out` on stdout and `err` on stderr and exits 3

#### Scenario: Deadline reached
- **WHEN** the command is still running when its deadline passes
- **THEN** `sw` prints `bounded: deadline_exceeded: <cmd> <first arg>` on stderr, nothing on stdout, and exits 124

#### Scenario: Output over the bound
- **WHEN** the command writes more bytes than the bound to stdout, or to stderr
- **THEN** `sw` prints `bounded: response_too_large: <cmd> <first arg>` on stderr, nothing on stdout, and exits 125 before the deadline

#### Scenario: Invalid invocation
- **WHEN** `sw run --bounded` gets no `--`, no command after `--`, or a flag other than `--paged` and `--secret`
- **THEN** it prints a usage line on stderr, starts no process and exits 2

#### Scenario: Command cannot be started
- **WHEN** the command named after `--` does not exist on `PATH`
- **THEN** `sw` exits 127 and prints the reason on stderr

#### Scenario: A limited command is never run again
- **WHEN** a command ends in a limit
- **THEN** `sw` started it at most once (never when the limit hit during startup): it never retries, and the caller decides any state by a read-back

#### Scenario: Limit line names the command a shell wraps
- **WHEN** `sw run --bounded -- bash -c 'exec gh "$@"' gh api user` (or `sh -c ...`) hits its deadline, on any OS
- **THEN** stderr is `bounded: deadline_exceeded: gh api`: for `sh` or `bash` with `-c` and more than three arguments, the line names the two arguments after the script, as `bounded.py` does

### Requirement: Bounded limits can only be lowered
`sw run --bounded` SHALL use a 120-second deadline (300 seconds with `--paged`) and a 32 MiB bound on each of stdout and stderr. `SPECWRIGHT_NET_DEADLINE`, `SPECWRIGHT_NET_PAGED_DEADLINE` and `SPECWRIGHT_NET_MAX_BYTES` SHALL only lower these, never raise them; a value that is not a non-negative number SHALL leave the default. `SPECWRIGHT_NET_DEADLINE_AT` (epoch seconds) SHALL cap the deadline to the time left until then.

#### Scenario: Environment lowers the deadline
- **WHEN** `SPECWRIGHT_NET_DEADLINE=1` is set and the command sleeps 30 seconds
- **THEN** `sw` exits 124 within 1 second plus the grace periods, not after 120 seconds

#### Scenario: Environment tries to raise a limit
- **WHEN** `SPECWRIGHT_NET_MAX_BYTES` is set above 32 MiB, or `SPECWRIGHT_NET_DEADLINE` above 120
- **THEN** the 32 MiB bound and the 120-second deadline still apply

#### Scenario: Deadline-at already in the past
- **WHEN** `SPECWRIGHT_NET_DEADLINE_AT` names a time already passed
- **THEN** `sw` exits 124 at once without starting the command

#### Scenario: Malformed override
- **WHEN** `SPECWRIGHT_NET_DEADLINE=abc` is set
- **THEN** the 120-second deadline applies

### Requirement: A command's exit is judged when it happens
`sw run --bounded` SHALL record a command's exit when it happens, not at a later poll. An exit before the deadline SHALL keep the command's own status and output, also when a process it started still holds its output open: those readers get 2 seconds, then that tree is stopped. An exit first recorded at or after the deadline SHALL be `deadline_exceeded`.

#### Scenario: Exit just before the deadline while a child holds the pipe
- **WHEN** a command starts a child that inherits its stdout and sleeps, then exits 0 shortly before the deadline
- **THEN** `sw` exits 0 with the command's own output, never 124, and the child is stopped

#### Scenario: Exit after the deadline
- **WHEN** a command is still running at its deadline and would exit after it
- **THEN** `sw` exits 124

### Requirement: The whole process tree is stopped
When `sw run --bounded` stops a command (a limit, or a held pipe after the command exited), it SHALL stop every process the command started, at any depth, also one whose parent already exited, by process group or job, never by name. On Windows the command SHALL be inside a job object before it runs. A survivor still holding a pipe after the stop SHALL be let go after 5 seconds.

#### Scenario: Orphaned grandchild on a deadline
- **WHEN** a command starts a child, which starts a grandchild and exits, and the command then hangs past its deadline
- **THEN** after `sw` exits 124 the command, the child and the grandchild are all gone, on Windows, Linux and macOS

#### Scenario: A limit before the command has started
- **WHEN** the deadline passes while `sw` is still setting up the command's job or process group (for example `SPECWRIGHT_NET_DEADLINE_AT` already passed), on any OS
- **THEN** `sw` exits 124, the command never starts, and no process `sw` started survives, except a helper that has not announced itself within 5 s (next scenario)

#### Scenario: A limit before the helper has announced itself
- **WHEN** a limit hits before the helper has announced itself, and it neither announces itself nor exits within 5 s
- **THEN** `sw` writes `bounded: helper not stopped: <cmd>` on stderr and exits 124, the command never starts, and the helper exits 125 without starting anything once it runs on

#### Scenario: The helper dies during startup
- **WHEN** the helper `sw` starts to hold the command exits after announcing itself and before the command is started
- **THEN** `sw` exits 127 with `bounded: helper exited during startup: <cmd>` on stderr, the command never starts, and on Windows `sw` assigns no other process to its job and terminates none

#### Scenario: sw itself already runs in a job
- **WHEN** on Windows `sw` is started inside a job object that its caller created
- **THEN** a bounded command's tree is still held by `sw`'s own job and stopped on a limit

#### Scenario: No job object on Windows
- **WHEN** on Windows `SPECWRIGHT_TEST_NO_JOB=1` is set, or the job object cannot be created or assigned
- **THEN** `sw` writes `bounded: no job object: <reason>` on stderr, runs the command anyway and stops its tree by PID on a limit

### Requirement: Secret mode keeps output off disk
With `--secret`, `sw run --bounded` SHALL hold the command's output only in memory and write no file at any point, under the same limits. On a limit it SHALL print only the limit line, never any of the command's output.

#### Scenario: Token lookup
- **WHEN** `sw run --bounded --secret -- <cmd>` runs a command that prints a token, with `TMPDIR`, `TMP` and `TEMP` pointing at a fresh empty directory
- **THEN** stdout is the token, the exit status is the command's, and the directory is still empty

#### Scenario: Secret command floods its output
- **WHEN** a secret-mode command writes past the byte bound
- **THEN** `sw` exits 125 with only the limit line on stderr, and no part of the output appears on stdout, on stderr or on disk

### Requirement: Commands resolve as the shell would find them
`sw run --bounded` SHALL find the command on `PATH` itself. On Windows it SHALL also try each `PATHEXT` extension in order, so `.exe`, `.cmd` and `.bat` shims (the eval fakes of `gh` and the reviewer CLIs included) resolve. A name containing a path separator SHALL be used as given.

#### Scenario: A .cmd shim on Windows
- **WHEN** on Windows `PATH` holds a directory with `gh.cmd` and no `gh.exe`, and `sw run --bounded -- gh api user` runs
- **THEN** `gh.cmd` runs with the arguments `api user` and its output and status come through

#### Scenario: A name that resolves nowhere
- **WHEN** neither the bare name nor any `PATHEXT` variant exists on `PATH`
- **THEN** `sw` exits 127 and names the command on stderr

### Requirement: Arguments reach native executables unchanged
A native executable (anything but a `.cmd` or `.bat` file) SHALL be started with no shell between `sw` and it, and SHALL receive every argument byte for byte, up to the OS command-line limit (32,767 UTF-16 units on Windows). On Windows, for `bash -c <script> <name> <args...>`, the arguments after `<name>` SHALL travel on the command's stdin as in `bounded.py`, so Git Bash's 8,186-character cut cannot shorten them.

#### Scenario: A long argument to a native executable
- **WHEN** an argument of 20,000 characters with spaces, quotes, backslashes, newlines, Unicode and an empty argument beside it is passed to a native executable after `--`
- **THEN** the executable receives every argument byte for byte

#### Scenario: A long argument through bash -c on Windows
- **WHEN** on Windows `sw run --bounded -- bash -c 'printf %s "$1"' name <20,000-character argument>` runs
- **THEN** stdout is the whole argument, byte for byte

#### Scenario: A missing transport end marker
- **WHEN** the bash prelude reads its stdin and finds no end marker
- **THEN** the script does not run and the exit status is 126

### Requirement: Batch shims get escaped arguments or none
On Windows a `.cmd` or `.bat` command SHALL run through `cmd.exe` with the path and every argument in double quotes, never caret-escaped, and trailing backslashes doubled, so a program the shim forwards `%*` to reads each value unchanged. What quoting cannot protect SHALL be refused with `bounded: unsafe batch argument: <cmd>`, exit 2, before any process starts.

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
- **WHEN** an argument to a `.cmd` command contains `%`, `!`, a double quote, CR, LF or NUL (for example `%PATH%` or `!x!`)
- **THEN** `sw` exits 2 with `bounded: unsafe batch argument: <cmd>` on stderr and starts no process

#### Scenario: A batch command line over the cmd.exe limit
- **WHEN** the escaped command line for a `.bat` command exceeds 8,191 characters
- **THEN** `sw` exits 2 with the same message and starts no process

### Requirement: Every platform's binary is built and checked in CI
For each pull request that touches `cli/` or the build, CI SHALL build `sw` on Linux x64, Windows x64 and macOS arm64, run its tests there, and upload each binary with a SHA-256 checksum. A separate job per OS SHALL download that artifact, verify the checksum, and run `sw version --json`, checking that `version` equals `VERSION`. Any mismatch SHALL fail the job.

#### Scenario: All three builds pass
- **WHEN** a pull request changes `cli/`
- **THEN** each OS's build, test and download-and-run jobs pass and three binaries with checksums are attached to the run

#### Scenario: Checksum does not match
- **WHEN** a downloaded binary's SHA-256 differs from its recorded checksum
- **THEN** the download-and-run job fails, naming the file, and does not run the binary

#### Scenario: Version drifts from VERSION
- **WHEN** `sw version --json` reports a version other than the `VERSION` file's
- **THEN** the download-and-run job fails, naming both versions

### Requirement: The macOS binary runs after a documented quarantine step
The macOS download-and-run job SHALL set the `com.apple.quarantine` attribute on the downloaded binary, as a browser or `curl` download would, record whether it runs as-is, then apply the step the ADR documents for the install and require `sw version --json` to succeed after it.

#### Scenario: Quarantined binary after the documented step
- **WHEN** the downloaded macOS binary carries `com.apple.quarantine` and the documented step is applied
- **THEN** `sw version --json` exits 0 and the job log records whether the quarantined binary ran before the step

#### Scenario: The documented step does not unblock it
- **WHEN** the binary still cannot run after the documented step
- **THEN** the job fails, showing the error, so signing becomes the next decision
