# Spec Delta

## MODIFIED Requirements

### Requirement: Commit tooling runs in the project's sw
`task-cover.sh` and `fit-subject.sh` SHALL keep their paths, arguments and output contracts, and do their work by resolving the project's `sw` with the shared resolver and running `sw commit task-cover` or `sw commit fit-subject` with the same arguments. Their stdout, stderr and exit status SHALL be `sw`'s; no other implementation SHALL remain in either script. A non-UTF-8 argument SHALL stop before any file is read: `not_utf8`, exit 1, or `fit-subject.sh: not valid UTF-8: <path>`, exit 2.

#### Scenario: Coverage through a matching sw
- **WHEN** the project's `VERSION` reads `0.26.0`, the resolver finds a matching `sw` 0.26.0, and `task-cover.sh --repo <r> --range main..feat/a --tasks <t> --change a` runs on a branch whose one commit has the subject `feat(a): task 1.1 Add it`
- **THEN** stdout is the one JSON document `sw commit task-cover` printed, task `1.1` has one commit with form `subject`, and the exit status is 0

#### Scenario: Fitting through a matching sw
- **WHEN** a matching `sw` is installed and `fit-subject.sh <msg>` runs on a message whose line 1 is a 90-character task subject
- **THEN** line 1 of `<msg>` is cut at the last whole word within 72 characters, every other byte of the file is unchanged, the cut subject is printed, and the exit status is 0

#### Scenario: Arguments reach sw unchanged
- **WHEN** `fit-subject.sh "<dir with space>/msg $1.txt"` runs
- **THEN** `sw commit fit-subject` receives the path unchanged, and that file is the one rewritten

#### Scenario: A non-UTF-8 message path
- **WHEN** on Linux `fit-subject.sh <path holding 0xFF>` runs
- **THEN** it exits 2 with `fit-subject.sh: not valid UTF-8: ` and the path with the byte shown as `\xFF` on stderr, and no file changes

#### Scenario: Git Bash paths on Windows
- **WHEN** on Windows `fit-subject.sh /c/Users/<u>/m.txt` runs, and again with `/tmp/m.txt`, each file holding a 90-character task subject
- **THEN** each file is fitted as the drive-form path `C:/Users/<u>/m.txt` or the same name under the `TEMP` directory respectively, the exit status is 0, and no `cygpath` ran

#### Scenario: Git Bash path to tasks.md on Windows
- **WHEN** on Windows `task-cover.sh --repo /c/<r> --tasks /c/<r>/openspec/changes/a/tasks.md ...` runs
- **THEN** the document equals the one for the same call with the drive-form paths, and `no_tasks` is not reported

#### Scenario: UNC path on Windows
- **WHEN** on Windows `fit-subject.sh //server/share/m.txt` runs, and that file holds a 90-character task subject
- **THEN** `fit-subject.sh` fits that file and exits 0, and no `could not convert path` stop occurs

#### Scenario: Path conversion fails on Windows
- **WHEN** on Windows `fit-subject.sh /etc/m.txt` runs, the Git Bash install root cannot be found from the bash the shim handed over, and the current drive holds a file `\etc\m.txt` with a 90-character task subject
- **THEN** it exits 2 with `fit-subject.sh: could not convert path: /etc/m.txt` on stderr, neither file changes, and for `task-cover.sh --tasks /etc/t.md ...` under the same failure the document is `"error": "bad_path"` with exit 2 and no coverage

#### Scenario: A stop keeps its exit status
- **WHEN** `task-cover.sh` runs with a range of more than `TASK_COVER_MAX_COMMITS` commits
- **THEN** the exit status is 1 and stdout is one JSON document with `"error": "range_too_large"`, as before this change
