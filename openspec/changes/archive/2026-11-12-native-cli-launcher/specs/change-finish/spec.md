# Spec Delta

## MODIFIED Requirements

### Requirement: The undo plan runs in the project's sw
`finish.sh` SHALL keep its path, arguments and output contract, and SHALL build the undo plan by resolving the project's `sw` with the shared resolver and running `sw finish undo-archive-plan` with the same arguments. Its stdout, stderr and exit status SHALL be those of `sw`, and no other implementation of the plan SHALL remain in the script. An argument or archived name that is not valid UTF-8 SHALL stop the plan with `"error": "not_utf8"` and exit 1, printing no script.

#### Scenario: Plan through a matching sw
- **WHEN** the project's `VERSION` reads `0.27.0`, the resolver finds a matching `sw` 0.27.0, and `finish.sh undo-archive-plan --change add-x --archived-name 2026-11-07-add-x --prefix openspec --main main` runs on a branch whose last commit archived `add-x`
- **THEN** stdout is the one JSON document `sw finish undo-archive-plan` printed, with `"ok": true`, `"mode": "committed"` and a `script` that begins with `set -euo pipefail`, and the exit status is 0

#### Scenario: Arguments reach sw unchanged
- **WHEN** `finish.sh undo-archive-plan` runs with `--prefix "my plans/openspec"` and a `--change` name holding a non-ASCII letter, both archived on the branch
- **THEN** `sw finish undo-archive-plan` receives both values unchanged, and the document's member `name` and the printed undo subject name the change as given

#### Scenario: A non-UTF-8 file under the archive
- **WHEN** on Linux the archived change directory, committed on the branch, holds a file outside its `specs` directory whose name holds the byte 0xFF
- **THEN** the exit status is 1, stdout is one JSON document with `"error": "not_utf8"` naming that file with the byte shown as `\xFF`, and no `script` is printed

#### Scenario: A refusal keeps its exit status
- **WHEN** the plan runs for a change with no archive directory in the working tree and no add commit on the branch
- **THEN** the exit status is 1 and stdout is one JSON document with `"error": "no_archive"`, as before this change

#### Scenario: Git Bash path on Windows
- **WHEN** on Windows `finish.sh --dir /c/<repo> undo-archive-plan ...` runs
- **THEN** the document equals the one for the same call with `--dir C:/<repo>`, no `not_a_repo` is reported, and no `cygpath` ran

#### Scenario: Path conversion fails on Windows
- **WHEN** on Windows `finish.sh --dir /etc/x undo-archive-plan ...` runs and the Git Bash install root cannot be found from the bash the shim handed over
- **THEN** it exits 2 with `"error": "bad_path"` naming `/etc/x`, no Git command ran, and no script is printed

### Requirement: sw finish undo-archive-plan keeps finish.sh's contract
`sw finish undo-archive-plan` SHALL accept the options shipped callers pass and print a JSON document that parses to the same keys and values for the same repo state and arguments, `script` and `after_rerun` texts on Git, jj and GitButler included, with exit codes 0 to 2. Differences: ASCII-digit task ids and date prefixes, `bad_path` for an unconvertible `/` path on Windows, and `carried_edits` in whole-path UTF-8 byte order. An unexpected failure SHALL print `internal_error` and exit 1.

#### Scenario: Unchanged finish evals pass on sw
- **WHEN** the `evals/finish` tests run in CI on Linux, Windows and macOS, and the `evals/vcs` GitButler undo tests run on Linux, against the `sw` built from the tree
- **THEN** every test passes with its assertions unchanged from before this change, apart from assertions on stdout bytes, which compare the parsed value instead

#### Scenario: Output bytes equal the old script's
- **WHEN** the frozen copy of the old `finish.sh` and the shim plan the same committed, uncommitted and bulk archives, on Git and jj, on GitButler where `but` is installed, and for a refusal such as `target_exists`
- **THEN** both print stdout that parses to the same JSON value once `carried_edits` is compared as a sorted list, and exit with the same code

#### Scenario: Printed scripts still call vcs.sh by path
- **WHEN** the plan runs on a GitButler repo for a committed archive
- **THEN** `script` calls `bash <specwright-pr>/scripts/vcs.sh state` and `commit` by the same absolute path `finish.sh` printed before this change, and names no `sw` binary

#### Scenario: Usage error
- **WHEN** `sw finish undo-archive-plan` is run without `--main`
- **THEN** it exits 2 and stdout is one JSON document with `"error": "usage"` and the message `undo-archive-plan needs --main`

#### Scenario: User-task ids are ASCII digits
- **WHEN** an archived `tasks.md` holds `- [ ] ١.١ [user] Check it` (Arabic-Indic digits) and no other user task
- **THEN** that member's `waiting_on_user` is `[]`

#### Scenario: Carried edits in sorted order
- **WHEN** the plan finds an uncommitted archive's carried edits by walking the archive directory, and its copies of `b.md`, `a.md`, `a/z.md` and `sub/c.md` differ from the change at HEAD, on Linux, Windows and macOS
- **THEN** `carried_edits` lists `a.md`, `a/z.md`, `b.md`, `sub/c.md` under the archive directory in that order on each OS

#### Scenario: Linked files in the archive keep their place
- **WHEN** on Linux and macOS an archived `specs/foo/spec.md` is a symlink to a readable file, and in an uncommitted archive a changed `notes.md` is a symlink to a file
- **THEN** capability `foo` is restored or removed as for a regular `spec.md`, `notes.md` is listed in `carried_edits`, and a linked directory is listed but not descended into, as before this change

#### Scenario: A non-UTF-8 name in the archive walk
- **WHEN** on Linux the archive directory holds a file whose name holds the byte 0xFF
- **THEN** it exits 1 with `"error": "not_utf8"` naming the file with the byte shown as U+FFFD, and no script is printed

