## ADDED Requirements

### Requirement: A CRLF message file commits on every backend
`sw vcs commit --message-file <file>` SHALL accept a message file whose lines end in CRLF on Git, jj and GitButler. jj SHALL replace each CRLF with LF before the commit, so the stored message holds LF. GitButler SHALL pass the file to `but commit -F` unchanged, and its read-back check SHALL read CRLF and a lone CR as LF in both the stored message and the file. On Git the file SHALL be passed to `git commit -F` as given, as now; Git's `commit.cleanup` mode decides what is stored.

#### Scenario: GitButler commit with a CRLF message file
- **WHEN** on GitButler `sw vcs commit --branch <change branch> --message-file msg.txt -- a.md` runs and `msg.txt` holds `docs(x): subject\r\n\r\nBody line\r\n`
- **THEN** it exits 0 with the usual commit document, no `commit_mismatch` is reported, and the new tip's message, with its line endings read as LF, is `docs(x): subject`, a blank line and `Body line`

#### Scenario: jj commit with a CRLF message file
- **WHEN** on jj the same commit runs with the same CRLF message file
- **THEN** it exits 0 and the stored message holds no `\r`

#### Scenario: Git commit with a CRLF message file under default cleanup
- **WHEN** on Git, with no `commit.cleanup` setting, the same commit runs with the same CRLF message file
- **THEN** it exits 0 and the stored message holds no `\r`

#### Scenario: A message that still differs is a mismatch
- **WHEN** on GitButler `but commit` stores a message whose text still differs from the message file after line endings are read as LF and trailing LFs are trimmed from both, as the check trims them now
- **THEN** the commit stops with `commit_mismatch` as before, and the new tip is left in place

### Requirement: GitButler reads the message file where sw runs
On GitButler, `sw vcs commit` SHALL resolve the message file's path against the directory `sw` runs in, read it from there, and pass that absolute path to `but commit -F`. No copy of the message SHALL be written. When the `but commit` command line, absolute message path included, is too long for the OS or the batch launcher, the commit SHALL stop with `too_many_paths` before `but commit` runs.

#### Scenario: A relative message file named from outside the repo
- **WHEN** on GitButler `sw vcs commit` runs from a directory outside the repo with `--message-file msg.txt`, and that directory and the repo each hold a different `msg.txt`
- **THEN** the commit's message is the one from the directory `sw` runs in, whether that file ends its lines in LF or CRLF

#### Scenario: The file exists only in the repo
- **WHEN** on GitButler `sw vcs commit` runs from a directory outside the repo with `--message-file msg.txt`, and only the repo holds a `msg.txt`
- **THEN** the commit fails with a non-zero exit before `but commit` runs, and no commit is made

#### Scenario: A commit whose real command line just exceeds the limit
- **WHEN** on Windows a GitButler commit names paths that fit with the message file's relative spelling but not once the `but` path, `-b <branch>`, `-F <absolute path>` and `--json` are counted
- **THEN** it stops with `too_many_paths` before `but commit` starts, and no commit is made

#### Scenario: A batch-file `but` whose line is over the batch limit
- **WHEN** on Windows `but` resolves to `but.cmd` and a commit's batch line is over the batch limit but under the native limit
- **THEN** it stops with `too_many_paths` before `but commit` starts, not `internal_error`

### Requirement: A committed GitButler undo refuses paths its commit would rename
On GitButler, the undo plan for a committed archive SHALL stop with `bad_path` and print no steps when a path its commit would name is refused by the GitButler path check or would be rewritten by it, such as a glob character or, on Linux and macOS, a backslash. An uncommitted archive's undo SHALL keep its path validation as before. Where this differs from "The archive undo plan uses GitButler on a GitButler repo", it SHALL take precedence.

#### Scenario: A bracket in a committed undo's path
- **WHEN** on GitButler the undo of a committed archive would commit `openspec/specs/a[1]/spec.md`
- **THEN** the plan stops with `bad_path` naming that path and prints no steps

#### Scenario: The same path in an uncommitted undo
- **WHEN** on GitButler the archive holding `openspec/specs/a[1]/spec.md` is uncommitted
- **THEN** the plan prints its steps as before, with no backend commit

### Requirement: A GitButler-selected undo reports a failed target read
When `vcs` is `gitbutler`, the archive-undo planner's read of `gitbutler.project.targetRef` SHALL stop with `vcs_error` when the read fails other than by Git reporting the setting unset, and with `not_managed` when it is unset or read as blank. This is the one exception to the GitButler probe's closed error list; every other VCS command's probe SHALL keep its errors unchanged.

#### Scenario: A failed target read during a GitButler undo
- **WHEN** with `vcs: gitbutler` the undo planner's read of the GitButler target fails with an error other than an unset setting
- **THEN** the plan stops with `vcs_error` and prints no steps

#### Scenario: An unset target during a GitButler undo
- **WHEN** with `vcs: gitbutler` Git reports the GitButler target unset, or reads it successfully with a blank value
- **THEN** the plan stops with `not_managed`, as today

### Requirement: Fixed commit defects are exceptions to the backends' unchanged outputs
The requirements above change results: GitButler CR read as LF and relative message paths read where `sw` runs, LF on jj, the real `but` line counted, a Windows VCS line of exactly 32,767 units refused before start, and a fixed `git_commit_failed` message for a Windows `git.cmd` line over the limit. Where they differ from the three `sw vcs` parity requirements (settings and fencing, vcs.sh's output and exit codes, document values), they SHALL take precedence.

#### Scenario: A CRLF commit that stopped before
- **WHEN** on GitButler a commit from a CRLF message file runs, which before this change stopped with `commit_mismatch`
- **THEN** it succeeds with the usual commit document, as the CRLF requirement states

#### Scenario: A message file with an interior carriage return
- **WHEN** on GitButler a commit runs from a message file named by an absolute path whose text holds a lone CR inside a line, and `but` stores it so that it matches only with that CR read as LF
- **THEN** it succeeds with the usual commit document, where before this change it stopped with `commit_mismatch`

#### Scenario: jj stores LF for a CRLF message
- **WHEN** on jj a commit runs from a CRLF message file
- **THEN** the stored message holds LF where the file held CRLF, so the message and commit ID differ from those the same commit made before this change

#### Scenario: A commit the old size check refused
- **WHEN** on GitButler a commit's paths exceed the old check's 32,000-byte quoted estimate but the real `but commit` command line fits
- **THEN** it commits where before this change it stopped with `too_many_paths`

#### Scenario: A Git commit line at the Windows boundary
- **WHEN** on Windows a Git commit's `git add` fits but its `git commit -F` line is exactly 32,767 units with its resolved path
- **THEN** the commit stops with `not_utf8` naming the command line, where it stopped with `git_commit_failed` before, and the paths `git add` staged stay staged

#### Scenario: A non-commit VCS command at the Windows boundary
- **WHEN** on Windows `sw vcs merge` would start a Git line of exactly 32,767 units with its resolved path
- **THEN** it stops with `not_utf8` naming the command line, where it reported `merge_failed` before

#### Scenario: A fenced network call at the Windows boundary
- **WHEN** on Windows a fenced Git `fetch-main` would start a line of exactly 32,767 units
- **THEN** it reports `git_network_error` with exit 3, as it does for any line it cannot represent

#### Scenario: A GitButler message path a batch shim cannot carry
- **WHEN** on Windows `but` resolves to a `.cmd` shim, a commit names its message file by a relative path without `%` or `!`, and that path resolved against the directory `sw` runs in holds `%` or `!`
- **THEN** the earlier `but` reads run, `but commit` is never started, and the commit stops with `internal_error`, exit 1, naming the unsafe batch argument, where before this change the relative path was passed and the commit could run

#### Scenario: A Git commit through a batch shim over the limit
- **WHEN** on Windows `git` resolves to `git.cmd` and the commit's raw `cmd.exe` or helper line is over the limit while its batch payload fits
- **THEN** `git commit` never starts and the commit stops with `git_commit_failed` and its exit as before, its message `cannot start git: cannot start the helper: its command line is too long` where the OS text followed `cannot start git: `

#### Scenario: Any other commit
- **WHEN** a commit runs on any backend from a message file named by an absolute path whose text holds no CR, whatever the message's length, on GitButler the old and the new size checks both admit it, no started line is exactly 32,767 units, no batch-shim line is over the limit, and the tool resolves to the same executable as before this change
- **THEN** its output, stop and exit status are as before this change
