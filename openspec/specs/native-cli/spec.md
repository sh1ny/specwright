# native-cli Specification

## Purpose

Defines `sw`, the compiled Dart executable that will replace Specwright's shipped bash and Python scripts: how it reports its version and interface, how it runs a command under bounds, and how it is built and checked on each platform.

## Requirements

### Requirement: sw reports its version and interface version
`sw version --json` SHALL print exactly one JSON object on stdout with `version`, the Specwright version the binary was built from (the `VERSION` file at build time), and `interface`, a positive integer that changes whenever a command's arguments, JSON output or exit codes change incompatibly. It SHALL exit 0. This change sets `interface` to 3.

#### Scenario: Version report of a CI build
- **WHEN** `sw version --json` runs on a binary CI built from a tree whose `VERSION` reads `0.23.0`
- **THEN** stdout is one JSON object with `"version": "0.23.0"` and `"interface": 3`, stderr is empty and the exit status is 0

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
`sw run --bounded` SHALL find the command on `PATH` itself. On Windows it SHALL also try each `PATHEXT` extension in order, so `.exe`, `.cmd` and `.bat` shims (the eval fakes of `gh` and the reviewer CLIs included) resolve. A name containing a path separator SHALL be used as given. On POSIX an empty `PATH` entry (leading, trailing, or between two colons) SHALL mean the current directory, searched in its position, as the shell and `execvp` search it. On Windows empty entries SHALL be dropped.

#### Scenario: A .cmd shim on Windows
- **WHEN** on Windows `PATH` holds a directory with `gh.cmd` and no `gh.exe`, and `sw run --bounded -- gh api user` runs
- **THEN** `gh.cmd` runs with the arguments `api user` and its output and status come through

#### Scenario: A name that resolves nowhere
- **WHEN** neither the bare name nor any `PATHEXT` variant exists on `PATH`
- **THEN** `sw` exits 127 and names the command on stderr

#### Scenario: An empty POSIX PATH entry is the current directory
- **WHEN** on Linux or macOS `PATH` is `:/usr/bin`, the current directory holds an executable `./tool`, `/usr/bin` holds another `tool`, and `sw run --bounded -- tool` runs
- **THEN** `./tool` runs, as `bash -c tool` would run it, and not `/usr/bin/tool`

#### Scenario: The empty entry keeps its position
- **WHEN** on Linux or macOS `PATH` is `/usr/bin:`, both `/usr/bin/tool` and `./tool` exist, and `sw run --bounded -- tool` runs
- **THEN** `/usr/bin/tool` runs

#### Scenario: No empty entry, no current directory
- **WHEN** on Linux or macOS `PATH` is `/usr/bin` with no empty entry, only `./tool` exists, and `sw run --bounded -- tool` runs
- **THEN** `sw` exits 127 and names `tool` on stderr

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
Binary assets SHALL keep the five `sw-<target>` names and Windows `.exe` suffix. From 0.30.0, releases SHALL also carry `THIRD_PARTY_NOTICES.txt`. `SHA256SUMS` SHALL hold one `<64 lowercase hex digits>  <asset name>` line per required asset, with no unknown or duplicate names. Older releases retain their five-binary manifest. Renaming an asset, or changing this format, is a workflow change (minor version).

#### Scenario: Checksum file content
- **WHEN** the release workflow attaches the assets of `v0.24.0`
- **THEN** `SHA256SUMS` has exactly five lines, one per binary asset name, and each hash equals the SHA-256 of that asset's bytes

#### Scenario: A malformed checksum line
- **WHEN** a consumer reads a `SHA256SUMS` line with an uppercase or short hash, a single space, an unknown name or a duplicate name
- **THEN** the consumer treats the file as invalid and uses no hash from it

### Requirement: SHA256SUMS is uploaded last and seals the release
The workflow SHALL upload `SHA256SUMS` only after every asset required for that release (the five binaries and, from 0.30.0, the notice) is attached and each, read back from the release, has the hash it lists. Once a release has `SHA256SUMS`, no run SHALL replace or add any of its assets. Runs for one tag, from either trigger, SHALL never overlap. The workflow SHALL also run by hand for a named tag, and SHALL fail when the tag has no release.

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
- **WHEN** the workflow runs by hand for a release that already has `SHA256SUMS` and every asset required for its version
- **THEN** the run changes no asset and reports the release as already complete

#### Scenario: Sealed release missing a binary
- **WHEN** a release has `SHA256SUMS` but `sw-macos-x64` was deleted from it
- **THEN** the run fails, naming the missing asset and saying the sealed release needs the owner, and uploads nothing

#### Scenario: No release for the tag
- **WHEN** the workflow is run by hand for a tag that has no GitHub release
- **THEN** the run fails, saying that the tag has no release, and attaches nothing

### Requirement: Third-party notices accompany new sw distributions
From 0.30.0, builds, releases and installs SHALL include `THIRD_PARTY_NOTICES.txt` alongside the binary. Release upload SHALL verify the notice by read-back before sealing; sealed assets SHALL never change. Downloaded binary and notice hashes SHALL be verified before the binary runs. Failed notice verification or placement SHALL report failure without replacing an existing binary. Reruns SHALL repair missing or incorrect notices even when keeping the binary.

#### Scenario: New release carries a verified notice before sealing
- **WHEN** the 0.30.0 release is attached
- **THEN** it contains five binaries, the notice and `SHA256SUMS`, the notice hash matches its bytes, and the seal is uploaded only after all six assets pass read-back

#### Scenario: Sealed new release lacks its notice
- **WHEN** a release from 0.30.0 has its checksum seal but lacks its notice
- **THEN** attachment fails naming the missing notice and changes no release asset

#### Scenario: Download installs the notice beside the binary
- **WHEN** the tagged installer installs a release from 0.30.0
- **THEN** it verifies the notice and binary before running the downloaded binary and installs the notice in the binary's version directory

#### Scenario: Notice failure preserves the existing binary
- **WHEN** the new release notice is missing, corrupt or cannot be placed
- **THEN** `sw-install` returns `ok: false` with `sums_invalid`, `asset_missing`, `checksum_mismatch` or `notice_write_failed`, its message names the notice and the release, the install stops before staging, the downloaded binary did not run before notice verification, and any existing binary is byte-identical

#### Scenario: Kept binary gets its notice repaired
- **WHEN** a new-release install rerun keeps a matching binary but its installed notice is missing or incorrect
- **THEN** installation repairs the notice before reporting success

#### Scenario: Source-build install includes notices
- **WHEN** the local source-build installer places a checked binary
- **THEN** it places the source notice beside that binary and does not report success if required notice placement fails

#### Scenario: Older release needs no retrospective notice
- **WHEN** the tagged installer or attachment tool handles a release before 0.30.0 with its original five-binary manifest
- **THEN** the old release remains usable without adding a notice or modifying a sealed release

#### Scenario: Build artifacts carry identical notices
- **WHEN** a ref at 0.30.0 or later is built for the five targets
- **THEN** each artifact holds the same notice bytes and a matching checksum file, and a missing source notice fails the build

#### Scenario: Older tag builds without a notice
- **WHEN** the current build workflow runs for a tag below 0.30.0
- **THEN** it requires no notice and a sealed release reports complete without any asset change

#### Scenario: Notice read-back differs before the seal
- **WHEN** the notice read back from an unsealed 0.30.0 release differs from the built notice
- **THEN** attachment fails naming the notice and both hashes, and uploads no `SHA256SUMS`

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

### Requirement: sw options follow one parsing rule
`sw vcs`, `sw finish` and `sw pr` SHALL accept `--name value` and `--name=value`, SHALL take the next word as an option's value whatever it looks like, SHALL keep every value of a repeated list option without splitting on commas, and SHALL stop with their usage error on an unknown or incomplete option, exiting 2 (`sw pr reply`: its usage code 4). Option names SHALL NOT be abbreviated. Removing an accidental form that no shipped caller uses SHALL NOT change `interface`.

#### Scenario: Equals form
- **WHEN** `sw vcs state --repo=/r --role=code` runs against a repository
- **THEN** it reports the same state as `--repo /r --role code`

#### Scenario: A value that looks like an option
- **WHEN** `sw vcs commit --repo /r --role code --branch --force` runs
- **THEN** `--branch` receives the value `--force`

#### Scenario: A repeated option holding a comma
- **WHEN** a list option is given twice, with the values `a,b` and `c`
- **THEN** the command receives the two values `a,b` and `c`

#### Scenario: Abbreviated option
- **WHEN** `sw pr reviewers --mat m.json --head <oid>` runs
- **THEN** it exits 2 with its usage error and reads no file

#### Scenario: Missing value
- **WHEN** `sw vcs state --repo` runs
- **THEN** stdout is one JSON document with `"error": "usage"` and the exit status is 2

#### Scenario: Words that are not paths
- **WHEN** `sw vcs commit --repo /r --role code stray -- a.txt` runs
- **THEN** it exits 2 with the `usage` error and commits nothing

#### Scenario: Shipped callers use whole option names
- **WHEN** the shipped skills, scripts and `sw`'s own launches are scanned for `sw` option words
- **THEN** every option word is a whole option name the command defines

### Requirement: The shipped dependencies stay hook-free and carry their notices
`sw` SHALL stay one single-file executable with no dependency that declares build hooks, and SHALL ship a third-party notice covering every package in its resolved runtime closure.

#### Scenario: Current dependency set
- **WHEN** the dependency check runs after `dart pub get`
- **THEN** no package in the closure declares build hooks, and the notice names each package in the closure with its licence text

#### Scenario: The settings parser joins the closure
- **WHEN** `yaml` is a runtime dependency of `cli/` and the dependency check runs after `dart pub get`
- **THEN** the check passes, and the notice names `yaml` and each package it brings into the runtime closure, `collection`, `source_span` and `string_scanner` among them, with its licence text

#### Scenario: A hook package enters the lock file
- **WHEN** a package with build hooks enters `cli/pubspec.lock`
- **THEN** the dependency check fails naming that package

#### Scenario: A dependency without a notice
- **WHEN** the resolved closure holds a package the notice does not name
- **THEN** the notice check fails naming that package

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

### Requirement: Skills run sw directly
Shipped skills, the schema, the agent definitions and the README SHALL tell the agent to run `<sw> <command> [arguments]`, where `<sw>` is `<home>/.specwright/bin/<project VERSION>/sw` (`sw.exe` on Windows) and `<home>` is `SPECWRIGHT_HOME` when set, else the user's home. They SHALL name no shipped script, give no bash-only command, and never use an `sw` on `PATH`.

#### Scenario: A skill step names sw
- **WHEN** the shipped skill text is searched for the commands it gives the agent
- **THEN** each Specwright command starts with `<sw>`, and no command names `vcs.sh`, `as.sh`, `pr-pair.sh`, `pr-snapshot.sh`, `pr-reply.sh`, `sw-path.sh`, `task-cover.sh`, `fit-subject.sh`, `finish.sh`, `review-run.sh`, `release.sh`, `update.sh` or a `.py` file

#### Scenario: The binary is not there
- **WHEN** the agent runs `<sw>` for a project whose `VERSION` reads `0.38.0` and `<home>/.specwright/bin/0.38.0/` holds no `sw`
- **THEN** the skill tells the agent to stop the step and tell the user to rerun the install prompt, and never to try another version's binary or one on `PATH`

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
