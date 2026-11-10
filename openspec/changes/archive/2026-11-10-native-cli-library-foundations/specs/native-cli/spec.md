## ADDED Requirements

### Requirement: sw documents are compact JSON ending in one line feed
Every JSON document `sw` prints SHALL be one compact JSON value followed by a single LF on every operating system. Consumers SHALL read a document by parsing it, never by matching its text, except the temporary snapshot regex readers and the printed undo-archive branch guards, retained until `native-cli-internal-calls`; those readers retain the compact keys they require.

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
- **WHEN** reviewers prints a document consumed by the snapshot regex readers
- **THEN** its compact keys remain readable by loginsOf, recheck, fail_names, fail_run_ids, merge_state, ci_pending and complete until native-cli-internal-calls replaces that boundary

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

#### Scenario: A hook package enters the lock file
- **WHEN** a package with build hooks enters `cli/pubspec.lock`
- **THEN** the dependency check fails naming that package

#### Scenario: A dependency without a notice
- **WHEN** the resolved closure holds a package the notice does not name
- **THEN** the notice check fails naming that package
