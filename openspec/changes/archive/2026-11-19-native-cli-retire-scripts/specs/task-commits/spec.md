# Spec Delta

## MODIFIED Requirements

### Requirement: Commit tooling runs in the project's sw
The skills SHALL run `sw commit task-cover` and `sw commit fit-subject` directly, and these SHALL keep the arguments and output contracts of `task-cover.sh` and `fit-subject.sh`. No other implementation of the commit tooling SHALL remain. An argument that is not well-formed Unicode SHALL be refused before any file is read, as native-cli "Arguments sw cannot represent are refused" states.

#### Scenario: Coverage through a matching sw
- **WHEN** the project's `VERSION` reads `0.26.0`, `sw` 0.26.0 runs `commit task-cover --repo <r> --range main..feat/a --tasks <t> --change a` on a branch whose one commit has the subject `feat(a): task 1.1 Add it`
- **THEN** stdout is one JSON document, task `1.1` has one commit with form `subject`, and the exit status is 0

#### Scenario: Fitting through a matching sw
- **WHEN** the project's `VERSION` matches the running `sw` and `sw commit fit-subject <msg>` runs on a message whose line 1 is a 90-character task subject
- **THEN** line 1 of `<msg>` is cut at the last whole word within 72 characters, every other byte of the file is unchanged, the cut subject is printed, and the exit status is 0

#### Scenario: Arguments reach sw unchanged
- **WHEN** `sw commit fit-subject "<dir with space>/msg $1.txt"` runs
- **THEN** `sw` reads the path as one whole value, and that file is the one rewritten

#### Scenario: A non-UTF-8 message path
- **WHEN** on Linux `sw commit fit-subject <path holding 0xFF>` runs
- **THEN** the exit status is non-zero, stdout is empty, and no file changes

#### Scenario: Git Bash paths on Windows
- **WHEN** on Windows Git Bash runs `<sw> commit fit-subject /c/Users/<u>/m.txt`, and that file holds a 90-character task subject
- **THEN** `sw` receives `C:/Users/<u>/m.txt`, converted by Git Bash, fits that file, exits 0, and no `cygpath` ran

#### Scenario: Git Bash path to tasks.md on Windows
- **WHEN** on Windows Git Bash runs `<sw> commit task-cover --repo /c/<r> --tasks /c/<r>/openspec/changes/a/tasks.md ...`
- **THEN** the document equals the one for the same call with the drive-form paths, and `no_tasks` is not reported

#### Scenario: UNC path on Windows
- **WHEN** on Windows `sw commit fit-subject //server/share/m.txt` runs, and that file holds a 90-character task subject
- **THEN** `sw` fits that file and exits 0, and no `could not convert path` stop occurs

#### Scenario: Path conversion fails on Windows
- **WHEN** on Windows a caller that is not Git Bash runs `sw commit fit-subject /etc/m.txt`, and the current drive holds a file `\etc\m.txt` with a 90-character task subject
- **THEN** `sw` takes the value as given, a root-relative Windows path, fits `\etc\m.txt` on the current drive, and prints no `could not convert path` or `bad_path` stop

#### Scenario: Another version
- **WHEN** `sw` 0.26.0 runs `commit fit-subject <msg>` in a project whose `VERSION` reads `0.27.0`, and line 1 of `<msg>` is a 90-character subject
- **THEN** stdout is the `sw_mismatch` document, the exit status is 1, and `<msg>` is byte for byte as it was

#### Scenario: A stop keeps its exit status
- **WHEN** `sw commit task-cover` runs with a range of more than `TASK_COVER_MAX_COMMITS` commits
- **THEN** the exit status is 1 and stdout is one JSON document with `"error": "range_too_large"`, as before this change

### Requirement: task-cover.sh finds the project from --code
`sw commit task-cover` SHALL accept an optional `--code <code toplevel>`. Without a leading `--project`, the project whose `VERSION` is checked SHALL be the first directory holding a `.git` entry at or above `--code` when it names a directory, else at or above the current directory, found with no Git command. `--code` SHALL NOT change the document. Store-backed callers SHALL pass it.

#### Scenario: Store-backed coverage finds the code checkout's sw
- **WHEN** `sw commit task-cover --code <code> --repo <store> --range main..feat/a --tasks <store tasks.md> --change a` runs from inside the store, whose checkout has no `openspec/.specwright/VERSION`, and `<code>` holds one matching the running `sw`
- **THEN** the check reads `<code>/openspec/.specwright/VERSION`, the coverage of the store's branch is printed, and `--code` changes nothing in the document

#### Scenario: Store-backed call without --code
- **WHEN** `sw commit task-cover --repo <store> ...` runs from inside the store with no `--code` and no `--project`, and the store has no `openspec/.specwright/VERSION`
- **THEN** it exits 1 with the `sw_mismatch` document saying no installed version was found, and no Git command ran

### Requirement: Apply stops on a missing sw
When `sw commit fit-subject` or `sw commit task-cover` prints `sw_mismatch`, or the project's `sw` is missing and cannot start, `specwright-commit` SHALL stop apply: it SHALL make no commit, tick nothing further, and report the message with the instruction to rerun the install prompt. It SHALL NOT treat a `sw_mismatch` exit 1 from `fit-subject` as the subject that does not fit.

#### Scenario: Mismatched sw during a task commit
- **WHEN** `sw commit fit-subject` exits 1 and its stdout is a `sw_mismatch` document
- **THEN** apply stops before `[vcs] commit`, and the report names the version mismatch and says to rerun the install prompt, rather than the 72-character limit

#### Scenario: Missing sw during a task commit
- **WHEN** `<home>/.specwright/bin/<project VERSION>/` holds no `sw` when apply runs `fit-subject`
- **THEN** apply makes no commit, ticks nothing further, and tells the user to rerun the install prompt

#### Scenario: Subject that does not fit is still reported as before
- **WHEN** `sw commit fit-subject` exits 1 with nothing on stdout and its message on stderr
- **THEN** apply makes no commit for that task, leaves its files uncommitted, reports the task, the subject and the 72-character limit, and goes on as before this change

## REMOVED Requirements

### Requirement: A missing or mismatched sw stops the commit tooling
**Reason**: The `task-cover.sh` and `fit-subject.sh` shims are removed, so no `sw_missing` or `no_python` document is printed. The commands check the project's version themselves.
**Migration**: See native-cli "Project commands check the project's version" and "Skills run sw directly", and "Apply stops on a missing sw" above.
