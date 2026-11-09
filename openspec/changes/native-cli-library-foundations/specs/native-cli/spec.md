## ADDED Requirements

### Requirement: sw documents are compact JSON ending in one line feed
Every JSON document `sw` prints SHALL be one compact JSON value followed by a single LF on every operating system. Consumers SHALL read a document by parsing it, never by matching its text.

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
`sw` SHALL read JSON files and `gh` responses as standard JSON and SHALL stop with the command's existing unreadable-input error, deciding nothing from the input, when it is malformed or holds a form outside the standard. No integer beyond 64 bits SHALL reach a document: such a setting stops as a `bad_setting` problem, and in `sw commit task-cover` a task, subject, trailer or numbered heading with such a group number is ignored.

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
- **WHEN** a field the workflow compares as an integer holds a number beyond 64 bits
- **THEN** the command does not compare a rounded value: it stops with its unreadable-input error

#### Scenario: A JSON file over the size limit
- **WHEN** a reviewer material file, reviewer config or policy snapshot file is larger than 32 MiB
- **THEN** the command stops with its unreadable-input error naming the file, without decoding it

#### Scenario: An integer setting beyond 64 bits
- **WHEN** `openspec/specwright.yaml` sets a reviewer timeout to a number beyond 64 bits
- **THEN** the command reports a `bad_setting` problem naming that key, writes no reviewer config, and no stack trace is printed

#### Scenario: Reviewer config for ordinary values
- **WHEN** a reviewer config is built from values within 64 bits
- **THEN** its bytes and digest equal those written before this change

### Requirement: sw options follow one parsing rule
`sw vcs`, `sw finish` and `sw pr` SHALL accept `--name value` and `--name=value`, SHALL take the next word as an option's value whatever it looks like, SHALL keep every value of a repeated list option without splitting on commas, and SHALL stop with their `usage` error and exit 2 on an unknown or incomplete option. Option names SHALL NOT be abbreviated. Removing an accidental form that no shipped caller uses SHALL NOT change `interface`.

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
