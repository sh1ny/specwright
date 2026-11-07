# Spec Delta

## ADDED Requirements

### Requirement: Commit tooling runs in the project's sw
`task-cover.sh` and `fit-subject.sh` SHALL keep their paths, arguments and output contracts, and SHALL carry out their work by resolving the project's `sw` with the shared resolver and running `sw commit task-cover` and `sw commit fit-subject` with the same arguments. Their stdout, stderr and exit status SHALL be those of `sw`, and no other implementation SHALL remain in either script.

#### Scenario: Coverage through a matching sw
- **WHEN** the project's `VERSION` reads `0.26.0`, the resolver finds a matching `sw` 0.26.0, and `task-cover.sh --repo <r> --range main..feat/a --tasks <t> --change a` runs on a branch whose one commit has the subject `feat(a): task 1.1 Add it`
- **THEN** stdout is the one JSON document `sw commit task-cover` printed, task `1.1` has one commit with form `subject`, and the exit status is 0

#### Scenario: Fitting through a matching sw
- **WHEN** a matching `sw` is installed and `fit-subject.sh <msg>` runs on a message whose line 1 is a 90-character task subject
- **THEN** line 1 of `<msg>` is cut at the last whole word within 72 characters, every other byte of the file is unchanged, the cut subject is printed, and the exit status is 0

#### Scenario: Arguments reach sw unchanged
- **WHEN** `fit-subject.sh "<dir with space>/msg $1.txt"` runs
- **THEN** `sw commit fit-subject` receives the path byte for byte, and that file is the one rewritten

#### Scenario: Git Bash paths on Windows
- **WHEN** on Windows `fit-subject.sh /c/Users/<u>/m.txt` runs, and again with `/tmp/m.txt`, each file holding a 90-character task subject
- **THEN** each file is fitted as the drive-form path `C:/Users/<u>/m.txt` or Git Bash's Windows directory for `/tmp` would be, and the exit status is 0

#### Scenario: Git Bash path to tasks.md on Windows
- **WHEN** on Windows `task-cover.sh --repo /c/<r> --tasks /c/<r>/openspec/changes/a/tasks.md ...` runs
- **THEN** the document equals the one for the same call with the drive-form paths, and `no_tasks` is not reported

#### Scenario: UNC path on Windows
- **WHEN** on Windows `cygpath -m` converts the message path to the UNC form `//server/share/m.txt`, and that file holds a 90-character task subject
- **THEN** `fit-subject.sh` fits that file and exits 0, and no `could not convert path` stop occurs

#### Scenario: Path conversion fails on Windows
- **WHEN** on Windows `cygpath -m` fails for `fit-subject.sh /tmp/m.txt`, and the current drive holds a file `\tmp\m.txt` with a 90-character task subject
- **THEN** it exits 2 with `fit-subject.sh: could not convert path: /tmp/m.txt` on stderr, neither file changes, and for `task-cover.sh --tasks /tmp/t.md ...` under the same failure the document is `"error": "bad_path"` with exit 2 and no coverage

#### Scenario: A stop keeps its exit status
- **WHEN** `task-cover.sh` runs with a range of more than `TASK_COVER_MAX_COMMITS` commits
- **THEN** the exit status is 1 and stdout is one JSON document with `"error": "range_too_large"`, as before this change

### Requirement: task-cover.sh finds the project from --code
`task-cover.sh` SHALL accept an optional `--code <code toplevel>`. The project whose `sw` runs SHALL be the first directory holding a `.git` entry at or above `--code` when it names a directory, else at or above the current directory, found with no Git command. `sw commit task-cover` SHALL accept `--code` and SHALL NOT let it change the document. Store-backed callers SHALL pass it.

#### Scenario: Store-backed coverage finds the code checkout's sw
- **WHEN** `task-cover.sh --code <code> --repo <store> --range main..feat/a --tasks <store tasks.md> --change a` runs from inside the store, whose checkout has no `openspec/.specwright/VERSION`, and `<code>` holds a matching one
- **THEN** the resolver reads `<code>/openspec/.specwright/VERSION`, the coverage of the store's branch is printed, and `--code` changes nothing in the document

#### Scenario: Store-backed call without --code
- **WHEN** `task-cover.sh --repo <store> ...` runs from inside the store with no `--code`, and the store has no `openspec/.specwright/VERSION`
- **THEN** it exits 1 with `"error": "sw_missing"` and a message saying no installed version was found, and no Git command ran

### Requirement: A missing or mismatched sw stops the commit tooling
When the resolver stops, `task-cover.sh` and `fit-subject.sh` SHALL print one JSON document on stdout with `"ok": false`, `"error": "sw_missing"` and a `message` that starts with `sw missing or mismatched: rerun the install prompt`, copy the resolver's detail to stderr, and exit 1. They SHALL run no `git` command, leave the message file untouched, and never fall back to another implementation, another version's binary or an `sw` on `PATH`.

#### Scenario: Binary missing for task-cover
- **WHEN** the project's `VERSION` reads `0.26.0` and `<home>/.specwright/bin/0.26.0/` holds no `sw`
- **THEN** `task-cover.sh` exits 1, stdout is one JSON document with `"error": "sw_missing"`, and no Git command ran

#### Scenario: Interface mismatch for fit-subject
- **WHEN** the installed binary reports another `interface` than the skills expect and `fit-subject.sh <msg>` runs on a 90-character subject
- **THEN** it exits 1, stdout is one JSON document with `"error": "sw_missing"`, and `<msg>` is byte for byte as it was

#### Scenario: No Python for task-cover
- **WHEN** no `python3` or `python` 3.8+ is on `PATH`
- **THEN** `task-cover.sh` exits 2 and stdout is `{"ok":false,"error":"no_python","message":"task-cover.sh needs python 3.8+"}` as before this change, and `sw` did not run

#### Scenario: No Python for fit-subject
- **WHEN** no `python3` or `python` 3.8+ is on `PATH`, so the resolver cannot check a binary
- **THEN** `fit-subject.sh` exits 1 with a `sw_missing` document whose message says the resolver needs Python 3.8+, and the message file is untouched

### Requirement: sw commit task-cover keeps task-cover.sh's contract
`sw commit task-cover` SHALL accept `task-cover.sh`'s options, honour `TASK_COVER_MAX_COMMITS`, and print the same JSON document byte for byte for the same inputs: keys in the same order, `", "` and `": "` separators, non-ASCII text as raw UTF-8, the same error codes and exit codes 0 to 3. The one difference: task and group ids are ASCII digits only. An unexpected failure SHALL print the document `"error": "internal_error"` and exit 1, never a stack trace.

#### Scenario: Unchanged task-cover evals pass on sw
- **WHEN** the `evals/git-workflow` tests of `task-cover.sh` and the `evals/vcs` coverage test run in CI on Linux, Windows and macOS against the `sw` built from the tree
- **THEN** every test passes with its assertions unchanged from before this change

#### Scenario: Usage error
- **WHEN** `sw commit task-cover` is run without `--change`
- **THEN** it exits 2 and stdout is one JSON document with `"error": "usage"` and the usage line `task-cover.sh` printed before this change, with ` [--code <dir>]` added at its end

#### Scenario: Task ids are ASCII digits
- **WHEN** a `tasks.md` line reads `- [x] ١.١ Do it` (Arabic-Indic digits)
- **THEN** the line is not a task: it is not in `tasks`, and no group `1` comes from it

### Requirement: sw commit fit-subject keeps fit-subject.sh's contract
`sw commit fit-subject` SHALL accept the one message-file argument and produce the same file bytes, stdout, stderr and exit codes 0 to 2 as `fit-subject.sh` for the same file. An unexpected failure SHALL print one line on stderr, leave the file untouched and exit 2, never a stack trace on stdout.

#### Scenario: Unchanged fit-subject evals pass on sw
- **WHEN** the `evals/git-workflow` tests of `fit-subject.sh` run in CI on Linux, Windows and macOS against the `sw` built from the tree
- **THEN** every test passes with its assertions unchanged from before this change

#### Scenario: Characters, not bytes, are counted
- **WHEN** line 1 is a task subject of 72 characters, some of them multi-byte UTF-8, and longer than 72 bytes
- **THEN** `sw commit fit-subject` leaves the file untouched, prints the subject and exits 0

#### Scenario: Line endings kept
- **WHEN** the message file uses CRLF line endings and line 1 is cut
- **THEN** the new line 1 ends in CRLF and every later byte, its CRs included, is unchanged

#### Scenario: Rewrite fails
- **WHEN** line 1 must be cut and the temporary file beside `<msg>` cannot be written
- **THEN** it exits 2 with `fit-subject.sh: could not rewrite <msg>` on stderr, `<msg>` is byte for byte as it was, and no temporary file is left

### Requirement: Apply stops on a missing sw
When `fit-subject.sh` or `task-cover.sh` reports `sw_missing`, `specwright-commit` SHALL stop apply: it SHALL make no commit, tick nothing further, and report the message with the instruction to rerun the install prompt. It SHALL NOT treat a `sw_missing` exit 1 from `fit-subject.sh` as the subject that does not fit.

#### Scenario: Missing sw during a task commit
- **WHEN** `fit-subject.sh` exits 1 and its stdout is a `sw_missing` document
- **THEN** apply stops before `[vcs] commit`, and the report names `sw missing or mismatched: rerun the install prompt` rather than the 72-character limit

#### Scenario: Subject that does not fit is still reported as before
- **WHEN** `fit-subject.sh` exits 1 with nothing on stdout and its message on stderr
- **THEN** apply makes no commit for that task, leaves its files uncommitted, reports the task, the subject and the 72-character limit, and goes on as before this change
