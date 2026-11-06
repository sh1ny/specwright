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
For each pull request that touches `cli/` or the build, CI SHALL build `sw` for linux-x64, linux-arm64, windows-x64, macos-arm64 and macos-x64, each on its own platform's runner, run its tests there, and upload each binary with a SHA-256 checksum. A separate job per target SHALL download that artifact on the same platform, verify the checksum, and run `sw version --json`, checking `version` against `VERSION` and `interface` against the skills' interface. Any mismatch SHALL fail the job.

#### Scenario: All three builds pass
- **WHEN** a pull request changes `cli/`
- **THEN** the linux-x64, windows-x64 and macos-arm64 build, test and download-and-run jobs pass as they did before linux-arm64 and macos-x64 were added

#### Scenario: All five builds pass
- **WHEN** a pull request changes `cli/`
- **THEN** each target's build, test and download-and-run jobs pass and five binaries with checksums are attached to the run

#### Scenario: Checksum does not match
- **WHEN** a downloaded binary's SHA-256 differs from its recorded checksum
- **THEN** the download-and-run job fails, naming the file, and does not run the binary

#### Scenario: Version drifts from VERSION
- **WHEN** `sw version --json` reports a version other than the `VERSION` file's
- **THEN** the download-and-run job fails, naming both versions

#### Scenario: Interface differs from the skills'
- **WHEN** `sw version --json` reports an interface other than the one the skills expect
- **THEN** the download-and-run job fails, naming both interfaces

#### Scenario: One target's runner fails
- **WHEN** the linux-arm64 build or its download-and-run job fails
- **THEN** that job fails, and the other targets' jobs still run and report their own results

### Requirement: The macOS binary runs after a documented quarantine step
The macOS download-and-run job SHALL set the `com.apple.quarantine` attribute on the downloaded binary, as a browser or `curl` download would, record whether it runs as-is, then apply the step the ADR documents for the install and require `sw version --json` to succeed after it.

#### Scenario: Quarantined binary after the documented step
- **WHEN** the downloaded macOS binary carries `com.apple.quarantine` and the documented step is applied
- **THEN** `sw version --json` exits 0 and the job log records whether the quarantined binary ran before the step

#### Scenario: The documented step does not unblock it
- **WHEN** the binary still cannot run after the documented step
- **THEN** the job fails, showing the error, so signing becomes the next decision

### Requirement: Each published release carries checked binaries
When a GitHub release of this repository is published, a release workflow SHALL build `sw` for all five targets from the tagged commit, check each one as the pull-request jobs do (checksum, `version` equal to the tag's `VERSION`, `interface` equal to the skills' interface at the tag, the macOS quarantine step on both macOS targets), and only after every check passes attach the five binaries and one `SHA256SUMS` file to that release.

#### Scenario: Release published
- **WHEN** `v0.24.0` is published as a GitHub release
- **THEN** the release lists `sw-linux-x64`, `sw-linux-arm64`, `sw-windows-x64.exe`, `sw-macos-arm64`, `sw-macos-x64` and `SHA256SUMS`, and each binary reports `"version": "0.24.0"`

#### Scenario: One target fails its check
- **WHEN** the macos-x64 binary fails its download-and-run check
- **THEN** the workflow fails naming that target, and attaches no asset to the release

#### Scenario: Tag's VERSION differs from the tag
- **WHEN** the release's tag is `v0.24.0` but `VERSION` at the tagged commit reads `0.23.0`
- **THEN** the workflow fails naming both versions and attaches no asset

#### Scenario: Interface mismatch at the tag
- **WHEN** a binary built at the tag reports an interface other than the skills' interface at the tag
- **THEN** the workflow fails naming both interfaces and attaches no asset

### Requirement: Release assets have fixed names and one checksum file
The release assets SHALL be named `sw-<target>` (`sw-<target>.exe` on Windows), for the targets `linux-x64`, `linux-arm64`, `windows-x64`, `macos-arm64` and `macos-x64`. `SHA256SUMS` SHALL hold one line per binary, `<64 lowercase hex digits>  <asset name>`, and nothing else. Renaming an asset, or changing this format, is a workflow change (minor version).

#### Scenario: Checksum file content
- **WHEN** the release workflow attaches the assets of `v0.24.0`
- **THEN** `SHA256SUMS` has exactly five lines, one per binary asset name, and each hash equals the SHA-256 of that asset's bytes

#### Scenario: A malformed checksum line
- **WHEN** a consumer reads a `SHA256SUMS` line with an uppercase or short hash, a single space, or an asset name outside the five
- **THEN** the consumer treats the file as invalid and uses no hash from it

### Requirement: SHA256SUMS is uploaded last and seals the release
The workflow SHALL upload `SHA256SUMS` only after all five binaries are attached and each attached binary, read back from the release, has the hash it lists. Once a release has `SHA256SUMS`, no run SHALL replace or add any of its assets. Runs for one tag, from either trigger, SHALL never overlap. The workflow SHALL also run by hand for a named tag, and SHALL fail when the tag has no release.

#### Scenario: Re-run after a failed upload
- **WHEN** a release has `sw-linux-x64` and `sw-linux-arm64` but no `SHA256SUMS`, and the workflow is run by hand for that tag
- **THEN** all five binaries are attached from this run's build (the two existing ones replaced), then `SHA256SUMS` is attached, matching every binary

#### Scenario: Overlapping runs for one tag
- **WHEN** a manual run for `v0.24.0` starts while the release-event run for `v0.24.0` is still attaching, and the two builds differ in their bytes
- **THEN** the manual run waits until the first ends, then finds the release sealed and changes nothing, and each binary on the release has the hash `SHA256SUMS` lists for it

#### Scenario: A binary changed before the seal
- **WHEN** an attached binary read back before the seal has a hash other than the one this run built
- **THEN** the run fails naming that asset and both hashes, and uploads no `SHA256SUMS`

#### Scenario: Sealed release run again
- **WHEN** the workflow runs by hand for a release that already has `SHA256SUMS` and all five binaries
- **THEN** the run changes no asset and reports the release as already complete

#### Scenario: Sealed release missing a binary
- **WHEN** a release has `SHA256SUMS` but `sw-macos-x64` was deleted from it
- **THEN** the run fails, naming the missing asset and saying the sealed release needs the owner, and uploads nothing

#### Scenario: No release for the tag
- **WHEN** the workflow is run by hand for a tag that has no GitHub release
- **THEN** the run fails, saying that the tag has no release, and attaches nothing

### Requirement: A project's sw is found and checked before use
A shared resolver SHALL take the project's code checkout, read its `openspec/.specwright/VERSION`, and look for `sw` at `<home>/.specwright/bin/<version>/sw[.exe]` (`<home>` is `SPECWRIGHT_HOME` when set, else the user's home). It SHALL run that file's `sw version --json`. When `version` equals `VERSION` and `interface` equals the interface the installed skills were written for, it SHALL print the absolute path and exit 0.

#### Scenario: Matching binary
- **WHEN** `VERSION` reads `0.24.0` and `<home>/.specwright/bin/0.24.0/sw` reports `0.24.0` and the expected interface
- **THEN** the resolver prints that path and exits 0

#### Scenario: SPECWRIGHT_HOME override
- **WHEN** `SPECWRIGHT_HOME` names a directory holding `.specwright/bin/0.24.0/sw`
- **THEN** the resolver prints the path under `SPECWRIGHT_HOME`, not under the user's home

#### Scenario: Override set but its binary missing
- **WHEN** `SPECWRIGHT_HOME` is set, holds no `.specwright/bin/0.24.0/sw`, and the user's home does hold one
- **THEN** the resolver exits 1 with the stop message naming the path under `SPECWRIGHT_HOME`, prints nothing on stdout, and does not use the file under the user's home

#### Scenario: Project has no VERSION
- **WHEN** the code checkout has no `openspec/.specwright/VERSION`
- **THEN** the resolver exits 1 with the stop message, saying no installed version was found, and runs no binary

### Requirement: A missing or mismatched sw stops with one message
When the project has no `VERSION`, or the binary is missing, cannot run, prints anything other than one JSON object with both fields, or reports another `version` or `interface`, the resolver SHALL print `sw missing or mismatched: rerun the install prompt` and the detail (the path and what was found) on stderr, print nothing on stdout, and exit 1. It SHALL never fall back to another version's binary, or to an `sw` on `PATH`.

#### Scenario: Binary missing
- **WHEN** `VERSION` reads `0.24.0` and `<home>/.specwright/bin/0.24.0/` holds no `sw`
- **THEN** the resolver exits 1 with the stop message and the expected path, even when `<home>/.specwright/bin/0.23.0/sw` exists

#### Scenario: Interface mismatch
- **WHEN** the binary reports `"version": "0.24.0"` and an interface other than the skills' interface
- **THEN** the resolver exits 1 with the stop message, naming both interfaces

#### Scenario: Version report is not JSON
- **WHEN** the file at the path prints text that is not one JSON object, or exits non-zero
- **THEN** the resolver exits 1 with the stop message, and prints nothing on stdout

### Requirement: The resolver reads only a version from VERSION
The resolver SHALL accept the project's `VERSION` only when it is `x.y.z`, with an optional pre-release or build suffix. Any other value SHALL stop it with `sw missing or mismatched: rerun the install prompt` and a detail saying the value is not a version, before it builds a path or runs a binary, so it never looks outside `<home>/.specwright/bin/`.

#### Scenario: VERSION names a path
- **WHEN** `VERSION` reads `../../../planted/.specwright/bin/0.25.0` and a matching `sw` exists at that path
- **THEN** the resolver exits 1 with the stop message saying the value is not a version, prints nothing on stdout, and runs no binary
