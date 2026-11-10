## MODIFIED Requirements

### Requirement: sw documents are compact JSON ending in one line feed
Every JSON document `sw` prints SHALL be one compact JSON value followed by a single LF on every operating system. Consumers SHALL read a document by parsing it, never by matching its text, except the printed undo-archive branch guards, retained until `native-cli-retire-scripts`; those guards retain the compact `"branch"` key they require.

#### Scenario: Document on Windows
- **WHEN** `sw vcs probe` prints its document on Windows
- **THEN** stdout parses to the same fields as on Linux, holds no space between tokens outside strings, and ends in exactly one `\n` with no `\r`

#### Scenario: Non-UTF-8 file name in a document
- **WHEN** a `sw vcs` document reports a file whose name holds the byte 0xFF
- **THEN** stdout holds that byte unchanged inside the JSON string

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
- **THEN** the printed guard matches the compact `"branch":"<name>"` that `sw vcs state` prints, so the undo runs on the planned branch and refuses on another

#### Scenario: Watcher compact keys remain readable
- **WHEN** `sw pr reviewers` or a `gh --jq` read used by `sw pr snapshot` prints its document with a space after a `:` or `,`
- **THEN** the snapshot parses it and reads the same logins, recheck ids, failing check names and run ids, merge state, pending check count and completeness as from the compact form

## ADDED Requirements

### Requirement: sw starts itself only for its helper and the reviewer evaluator
For its own work `sw` SHALL start its own binary only as the bounded process helper and as the reviewer evaluator under a poll deadline. It SHALL never start a shipped script or a Python interpreter. Running another installed or downloaded `sw` to read its version and interface SHALL stay allowed. Printing a command for an agent or user to run is not a launch.

#### Scenario: Retrofitted paths with sentinels and no Python
- **WHEN** `sw vcs` fetch, pull and push against github.com, `sw pr snapshot` with a reviewer config, and the PR workflow commands run with recording `as.sh`, `vcs.sh`, `pr-pair.sh` and `sw-path.sh` sentinels in the handoff scripts directory and failing `python` and `python3` first on `PATH`, on Linux, Windows and macOS
- **THEN** each returns its expected document or output, no sentinel recorded a run, and neither interpreter ran

#### Scenario: Reviewer evaluator stays a separate process
- **WHEN** a reviewer report pattern backtracks past the poll deadline
- **THEN** the evaluator child is killed at the deadline and the poll fails, while the snapshot process itself keeps running

#### Scenario: Printed commands are not launches
- **WHEN** `sw vcs plan` or a PR cleanup plan prints a command that names `vcs.sh` or `pr-pair.sh`
- **THEN** the document holds that command and no such script ran

### Requirement: A launch-site allowlist guards process starts
A test over `cli/lib/src`, run on Linux, Windows and macOS, SHALL list every call that starts a process and every caller of the process runners, and SHALL fail on a launch site missing from its allowlist, on a self-launch other than the helper and the evaluator, on a shipped script name in a launch's arguments, and on a shipped script name written anywhere under `cli/lib/src` outside a listed printed-command, message or label site.

#### Scenario: Current tree passes
- **WHEN** the allowlist test runs on the tree this change produces
- **THEN** it passes, and its allowlist names each launch site with its permitted kind: external tool, process helper, reviewer evaluator or binary check

#### Scenario: A new unlisted launch fails
- **WHEN** a source file under `cli/lib/src` adds a call to a process runner that the allowlist does not name
- **THEN** the test fails, naming the file and the call

#### Scenario: A script in launch arguments fails
- **WHEN** a listed launch site passes `as.sh`, `vcs.sh`, `pr-pair.sh`, `pr-snapshot.sh`, `pr-reply.sh`, `review-run.sh`, `release.sh` or a `.py` file as a launch argument
- **THEN** the test fails, naming the script and the site

#### Scenario: A self-launch outside the allowed two fails
- **WHEN** a call starts `sw`'s own executable with arguments other than the `__exec` helper or `pr reviewers` under a deadline, including a listed site whose subcommand is changed, whose argument list is not a literal, or whose evaluator runs without its bound, while every call count stays the same
- **THEN** the test fails, naming the site

#### Scenario: A script name built away from the launch fails
- **WHEN** a source file under `cli/lib/src` writes `as.sh` or another shipped script name into a value outside a listed printed-command, message or label site, and passes that value to a listed launch
- **THEN** the test fails, naming the file and the script
