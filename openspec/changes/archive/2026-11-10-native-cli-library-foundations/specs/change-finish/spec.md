## MODIFIED Requirements

### Requirement: sw finish undo-archive-plan keeps finish.sh's contract
`sw finish undo-archive-plan` SHALL accept the options shipped callers pass and print a JSON document that parses to the same keys and values for the same repo state and arguments, including the `script` and `after_rerun` texts on Git, jj and GitButler, with the same exit codes 0 to 2. Differences: task ids and archive date prefixes match ASCII digits only, and on Windows an unconvertible `/` path stops with `bad_path`. An unexpected failure SHALL print `internal_error` and exit 1.

#### Scenario: Unchanged finish evals pass on sw
- **WHEN** the `evals/finish` tests run in CI on Linux, Windows and macOS, and the `evals/vcs` GitButler undo tests run on Linux, against the `sw` built from the tree
- **THEN** every test passes with its assertions unchanged from before this change, apart from assertions on stdout bytes, which compare the parsed value instead

#### Scenario: Output bytes equal the old script's
- **WHEN** the frozen copy of the old `finish.sh` and the shim plan the same committed, uncommitted and bulk archives, on Git and jj, on GitButler where `but` is installed, and for a refusal such as `target_exists`
- **THEN** both print stdout that parses to the same JSON value, and exit with the same code

#### Scenario: Printed scripts still call vcs.sh by path
- **WHEN** the plan runs on a GitButler repo for a committed archive
- **THEN** `script` calls `bash <specwright-pr>/scripts/vcs.sh state` and `commit` by the same absolute path `finish.sh` printed before this change, and names no `sw` binary

#### Scenario: Usage error
- **WHEN** `sw finish undo-archive-plan` is run without `--main`
- **THEN** it exits 2 and stdout is one JSON document with `"error": "usage"` and the message `undo-archive-plan needs --main`

#### Scenario: User-task ids are ASCII digits
- **WHEN** an archived `tasks.md` holds `- [ ] ١.١ [user] Check it` (Arabic-Indic digits) and no other user task
- **THEN** that member's `waiting_on_user` is `[]`
