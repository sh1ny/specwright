# task-commits Specification

## Purpose
Keeps task commit subjects within the project's 72-character limit, measured mechanically rather than estimated, without changing the subject format.

## Requirements

### Requirement: Task subjects fit 72 characters
`specwright-commit` SHALL build each task subject as `<type>(<change-name>): task X.Y <task text>`, and each group subject as `<type>(<change-name>): group N <group heading text>`, and measure it mechanically before committing, counting every character of the task or heading text, backticks included. When the subject is longer than 72 characters, it SHALL cut the text at the last word boundary that keeps the whole subject within 72. A subject that already fits SHALL be used unchanged.

#### Scenario: Long task text with backticks
- **WHEN** task 1.1 of `add-greeting` reads ``Add `greet(name)` with tests test_greet_named and test_greet_empty; ...``
- **THEN** the commit subject is at most 72 characters, starts with `feat(add-greeting): task 1.1 Add`, and ends at a whole word of the task text

#### Scenario: Subject exactly at the limit
- **WHEN** the full subject is exactly 72 characters
- **THEN** the subject is committed unchanged

#### Scenario: Store-backed task pair
- **WHEN** a store-backed task gets a code commit and a store commit
- **THEN** both commits carry the identical fitted subject

#### Scenario: Long group heading
- **WHEN** group 2 of `add-greeting` is headed `## 2. Documentation of greet and farewell for the README and the user guide pages`
- **THEN** the group commit subject is at most 72 characters, starts with `feat(add-greeting): group 2 Documentation`, and ends at a whole word of the heading

### Requirement: Task text is never run as shell input
The subject and message SHALL reach `git commit` through a file, and fitting SHALL read the message from that file, so backticks, `$` and quotes in task text are kept as literal characters and never executed.

#### Scenario: Shell-like task text
- **WHEN** a task's text contains `` `touch pwned` `` and `$(echo hi)`
- **THEN** the committed subject contains those characters literally (cut only at a word boundary), and no file named `pwned` is created

### Requirement: Unfittable subject stops the commit
When not even the first word of the task text fits after the `<type>(<change-name>): task X.Y ` prefix, or of the group heading after the `<type>(<change-name>): group N ` prefix, within 72 characters, `specwright-commit` SHALL make no commit for that task or group and SHALL report the task or group, the subject and the limit.

#### Scenario: Prefix plus first word too long
- **WHEN** the change name is so long that the prefix and the task text's first word exceed 72 characters
- **THEN** no commit is made for the task, the task's files stay uncommitted, and the report names the task and the 72-character limit

#### Scenario: Group prefix plus first word too long
- **WHEN** the change name is so long that the `group 1 ` prefix and the heading's first word exceed 72 characters
- **THEN** no commit is made for group 1, its files and ticks stay uncommitted, and the report names group 1 and the 72-character limit

### Requirement: Commit granularity is a project setting
`specwright-commit` SHALL read `commit_granularity` from `openspec/specwright.yaml` once at the start of each apply run. `task`, or no setting, SHALL keep one commit per task, unchanged. `group` SHALL commit once per task group. Any other value SHALL stop apply before any commit and name the value and the two allowed ones.

#### Scenario: Setting unset
- **WHEN** `openspec/specwright.yaml` has no `commit_granularity` and apply finishes tasks 1.1, 1.2 and 2.1
- **THEN** the branch has one commit per task with subjects `<type>(<change-name>): task 1.1 ...`, `task 1.2 ...` and `task 2.1 ...`, and no commit carries a `Specwright-Task:` trailer

#### Scenario: Unknown value
- **WHEN** `commit_granularity` is `groups`
- **THEN** apply makes no commit and reports `groups` together with `task` and `group`

### Requirement: A group is committed once at its boundary
With `commit_granularity: group`, `specwright-commit` SHALL leave a task group's work uncommitted until every agent and evidence task of the group is ticked and freshly verified, then SHALL commit it once, staging the group's files and `tasks.md` by name. The message SHALL carry one `Specwright-Task: X.Y` trailer per agent or evidence task of the group it covers, in task order. The group's user tasks SHALL NOT hold the commit back, and it SHALL NOT tick or cover them.

#### Scenario: Two groups
- **WHEN** apply in group mode finishes groups `1.1`-`1.3` and `2.1`-`2.2`
- **THEN** the branch has exactly two task-work commits, `group 1 ...` with trailers `Specwright-Task: 1.1`, `1.2` and `1.3`, then `group 2 ...` with trailers `2.1` and `2.2`, and every task is ticked

#### Scenario: Shared file within a group
- **WHEN** tasks 1.1 and 1.3 both change `greet.py`
- **THEN** `greet.py` appears in the group 1 commit only, and no commit holds part of group 1's work

#### Scenario: Unowned edits present
- **WHEN** `scratch-notes.txt` was untracked before apply started
- **THEN** no group commit contains it and it is still untracked after apply

#### Scenario: Interrupted before the group is complete
- **WHEN** task 2.1 is ticked and 2.2 is not, and the run stops
- **THEN** no commit holds 2.1's work or tick

#### Scenario: Group with a user task
- **WHEN** group 3 has 3.1, 3.2 `[user]` and 3.3, and 3.1 and 3.3 are ticked and verified while 3.2 is not ticked
- **THEN** the group 3 commit is made with trailers `Specwright-Task: 3.1` and `3.3` only, and 3.2 stays unticked

### Requirement: One group is pending at a time
In group mode, a complete group SHALL be committed, both halves when store-backed, before any task of another group is ticked, parallel dispatch included.

#### Scenario: Groups run in parallel
- **WHEN** groups 1 and 2 touch disjoint files and are dispatched in parallel
- **THEN** no task of group 2 is ticked until the group 1 commit exists, and each group still gets exactly one commit

#### Scenario: Group 1 commit fails
- **WHEN** group 1 is complete, its commit fails, and group 2's work has finished in parallel
- **THEN** no task of group 2 is ticked and the report names the failed group 1 commit

### Requirement: Group membership is exact
A task SHALL belong to group N when its ID has exactly N before the dot. A group commit SHALL carry trailers only for tasks of its own group. Its subject text SHALL be the heading `## N. <text>` of `tasks.md`. A group with no such heading SHALL stop the commit and be reported.

#### Scenario: Group 1 and group 10
- **WHEN** `tasks.md` has groups 1 (`1.1`, `1.2`) and 10 (`10.1`), and group 1 is complete
- **THEN** the group 1 commit carries trailers `1.1` and `1.2` only and holds none of task 10.1's tick or files

#### Scenario: Missing heading
- **WHEN** tasks `3.1` and `3.2` follow a heading `## Cleanup` with no number
- **THEN** no commit is made for group 3 and the report names group 3 and the missing `## 3.` heading

### Requirement: Task evidence is a subject or a trailer
A task SHALL count as committed in a repository when a commit on the change branch since main has a subject starting with `<type>(<change-name>): task X.Y ` or a `Specwright-Task` trailer whose value is exactly `X.Y`. A read-only check SHALL report, for each task in `tasks.md`, its group, its tick, and the commits covering it. It SHALL also report every task covered by more than one commit in that repository, and every trailer naming a task outside its commit's group.

#### Scenario: Exact match
- **WHEN** a commit carries `Specwright-Task: 1.10` and `tasks.md` has tasks 1.1 and 1.10
- **THEN** the check reports 1.10 covered and 1.1 not covered by that commit

#### Scenario: Task ID inside other text
- **WHEN** a group 2 commit's subject is `fix(add-greeting): group 2 Fix task 1.1 regressions`, or a task 2.1 subject reads `fix(add-greeting): task 2.1 Revert task 1.1 output`
- **THEN** neither commit counts as coverage of task 1.1

#### Scenario: Task covered twice
- **WHEN** task 1.2 has a per-task commit and is also named by a group 1 trailer
- **THEN** the check reports 1.2 as covered twice, naming both commits

#### Scenario: Trailer outside its group
- **WHEN** a commit with subject `... group 1 ...` carries `Specwright-Task: 10.1`
- **THEN** the check reports 10.1 as a cross-group trailer on that commit

### Requirement: An interrupted group resumes without loss
When apply in group mode starts and exactly one group has ticked agent or evidence tasks with no evidence, `specwright-commit` SHALL treat them as that group's pending work: re-run their verification, finish the group's remaining tasks and make one group commit covering them all. Such ticks in more than one group SHALL make no commit and be listed. A ticked, uncovered user task SHALL NOT make its group pending; it is listed as an uncommitted user tick. A tick SHALL never be removed.

#### Scenario: Resume in a fresh session
- **WHEN** tasks 1.1 and 1.2 are ticked with their work uncommitted, 1.3 is not ticked, and apply restarts
- **THEN** 1.1 and 1.2 are verified again, 1.3 is done, and one `group 1` commit carries trailers 1.1, 1.2 and 1.3

#### Scenario: Group already partly committed
- **WHEN** group 1 has an earlier commit covering 1.1 and apply in group mode finishes 1.2 and 1.3
- **THEN** the new group 1 commit carries trailers 1.2 and 1.3 only, and no task is covered twice

#### Scenario: Two groups pending
- **WHEN** ticks in groups 1 and 2 have no evidence when apply restarts
- **THEN** no commit is made, both groups and their tasks are listed, and no tick is removed

#### Scenario: Interrupted group plus a user tick
- **WHEN** agent task 1.1 is ticked and uncommitted, the user has ticked 2.1 `[user]`, and apply restarts
- **THEN** only group 1 is pending, 2.1 is listed as an uncommitted user tick, and the group 1 commit carries `Specwright-Task: 1.1` and `Specwright-User-Task: 2.1`

#### Scenario: All-user group
- **WHEN** group 5 holds only `[user]` tasks and the user ticks 5.1 with no agent work pending
- **THEN** group 5 is never listed as pending and 5.1 is committed as `... record user checks 5.1`

### Requirement: A resumed red step is re-verified by its test
On resume, a ticked task whose verification is a test seen failing before the implementation (a red step) SHALL count as re-verified when the named test exists and now passes with the group's implementation. The group commit body SHALL say that the original red output is unavailable for that task. The task SHALL stay ticked.

#### Scenario: Red step ticked before the interruption
- **WHEN** group 1 is pending with 1.1 (write `test_greet_named`, confirm it fails) and 1.2 (implement `greet`) ticked, and apply restarts
- **THEN** `test_greet_named` is run and passes, 1.1 stays ticked, and the group 1 commit body says 1.1's red output is unavailable

#### Scenario: Named test missing
- **WHEN** the pending group's ticked red step names `test_greet_named` and no such test exists
- **THEN** no group commit is made and the report names 1.1 and the missing test

### Requirement: Pending ticks wait for their group commit
In group mode, a tick of a task with no evidence SHALL reach Git only in that task's group commit (store-backed: the store half). The planning and amendment commits SHALL NOT stage a `tasks.md` whose diff ticks such a task; that `tasks.md` waits for the group commit, and an untracked `tasks.md` that already ticks a task SHALL stop apply before any commit.

#### Scenario: Resume with a pending group and a planning edit
- **WHEN** group 1 is pending (1.1 and 1.2 ticked, uncommitted), `design.md` has an uncommitted edit, and apply restarts
- **THEN** the planning commit holds `design.md` and no tick, and the group 1 commit's `tasks.md` diff ticks exactly 1.1, 1.2 and 1.3

#### Scenario: First planning commit with ticks
- **WHEN** `tasks.md` is untracked and already ticks 1.1 when apply starts in group mode
- **THEN** no commit is made and the report names the ticked tasks

### Requirement: Grouping never rewrites history
`specwright-commit` SHALL NOT amend, squash, rebase or regroup an existing commit to form a group commit, published or not. A group commit SHALL cover only the group's tasks that have no evidence yet, so tasks already committed keep their commits. When a group mixes per-task and group commits, the report SHALL say so once, naming the group.

#### Scenario: Switching to group mode mid-change
- **WHEN** task 1.1 was committed as `task 1.1 ...`, `commit_granularity` is then set to `group`, and apply finishes 1.2, 1.3, 2.1 and 2.2
- **THEN** the `task 1.1` commit keeps its SHA, a `group 1` commit carries trailers 1.2 and 1.3 only, a `group 2` commit carries 2.1 and 2.2, and the report says group 1 mixes both forms

#### Scenario: PR feedback after group commits
- **WHEN** a PR fix round follows two pushed group commits
- **THEN** the fix is a new commit and both group commits keep their SHAs

### Requirement: End-of-apply check uses task evidence
When every agent and evidence task is ticked, `specwright-commit` SHALL require each ticked task to have exactly one covering commit, no cross-group trailer, no `evidence_missing` entry, and a clean tree apart from pre-existing files, then report `<N> tasks, <M> task-work commits, tree clean`. A task with no evidence, covered twice or in `evidence_missing` SHALL stop the hand-off and be listed. Unticked user tasks SHALL NOT stop it; the report adds `waiting on the user: <ids>`.

#### Scenario: Group mode complete
- **WHEN** five ticked tasks are covered by two group commits and the tree is clean
- **THEN** the report reads `5 tasks, 2 task-work commits, tree clean` and the hand-off continues

#### Scenario: Lost coverage
- **WHEN** task 2.2 is ticked but no commit names it in its subject or a trailer
- **THEN** there is no hand-off to archive or PR, and the report lists 2.2 as uncovered

#### Scenario: User task still open
- **WHEN** every agent task is ticked and covered, the tree is clean, and user task 4.3 is unticked
- **THEN** the report adds `waiting on the user: 4.3` and the hand-off to the pre-ship review and the PR continues

### Requirement: A repeated task id stops the coverage check
`task-cover.sh` SHALL exit 2 with error `duplicate_task_ids` when two or more tracked lines of `tasks.md` (a checkbox line with any box content) carry the same task id. The message SHALL name every repeated id. It SHALL print no coverage data, so `specwright-commit` makes no commit and stops, showing the error.

#### Scenario: Ticked line followed by a draft line with the same id
- **WHEN** `tasks.md` holds `- [x] 1.1 add greet` and later `- [~] 1.1 draft`, and a commit `task 1.1: add greet` exists
- **THEN** `task-cover.sh` exits 2, its JSON has `ok: false`, `error: duplicate_task_ids` and a message naming `1.1`, and it reports no `uncovered` list

#### Scenario: Unique ids
- **WHEN** every tracked line of `tasks.md` has its own id
- **THEN** `task-cover.sh` reports coverage as before and exits 0

#### Scenario: Repeated id in an untracked line
- **WHEN** `1.1` appears on a tracked line and again in a plain bullet with no checkbox
- **THEN** the plain bullet is not a task, and `task-cover.sh` exits 0

### Requirement: User ticks ride the next tasks.md commit
A ticked user task SHALL count as committed when a commit on the change branch carries a `Specwright-User-Task` trailer exactly naming it. Every commit that stages `tasks.md` SHALL carry one for each user task it ticks that no earlier commit covers; it is never a cross-group trailer. With no agent work pending, the agent SHALL commit `tasks.md` alone as `<type>(<change-name>): record user checks <ids>`. Otherwise the tick SHALL wait for the commit that covers the pending agent ticks.

#### Scenario: User tick with nothing pending
- **WHEN** every agent task is committed and the user ticks 3.2 `[user]`
- **THEN** one commit `<type>(<change-name>): record user checks 3.2` stages only `tasks.md`, its diff ticks only 3.2, and it carries `Specwright-User-Task: 3.2`

#### Scenario: Two user ticks at once
- **WHEN** the user ticks 3.2 and 4.3, both `[user]`, with nothing else pending
- **THEN** one commit `... record user checks 3.2, 4.3` carries `Specwright-User-Task: 3.2` and `Specwright-User-Task: 4.3`, and its `tasks.md` diff ticks exactly those two

#### Scenario: User tick while a group is pending
- **WHEN** agent tasks 1.1 and 1.2 are ticked and uncommitted and the user ticks 2.1 `[user]`
- **THEN** no commit is made for 2.1 alone; the group 1 commit stages `tasks.md` with all three ticks and carries `Specwright-Task: 1.1`, `Specwright-Task: 1.2` and `Specwright-User-Task: 2.1`, and none of them is reported cross-group

#### Scenario: Trailer for an agent task
- **WHEN** a commit carries `Specwright-User-Task: 1.1` and 1.1 is an agent task
- **THEN** the check does not count it as coverage of 1.1

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
`sw commit task-cover` SHALL accept `task-cover.sh`'s options, honour `TASK_COVER_MAX_COMMITS`, and print JSON that parses to the same keys, key order and values for the same inputs, with the same error codes and exit codes 0 to 3. Differences: task and group ids are ASCII digits only, and a task, commit subject, trailer or numbered heading with a group number beyond 64 bits is ignored. An unexpected failure SHALL print the document `"error": "internal_error"` and exit 1, never a stack trace.

#### Scenario: Unchanged task-cover evals pass on sw
- **WHEN** the `evals/git-workflow` tests of `task-cover.sh` and the `evals/vcs` coverage test run in CI on Linux, Windows and macOS against the `sw` built from the tree
- **THEN** every test passes with its assertions unchanged from before this change, apart from assertions on stdout bytes, which compare the parsed value instead

#### Scenario: Usage error
- **WHEN** `sw commit task-cover` is run without `--change`
- **THEN** it exits 2 and stdout is one JSON document with `"error": "usage"` and the usage line `task-cover.sh` printed before this change, with ` [--code <dir>]` added at its end

#### Scenario: A group number beyond 64 bits is not a task
- **WHEN** a `tasks.md` line reads `- [x] 99999999999999999999.1 Do it`
- **THEN** the line is not a task: it is not in `tasks`, and the command prints a JSON document rather than `internal_error`

#### Scenario: A numbered heading beyond 64 bits is ignored
- **WHEN** a `tasks.md` holds `## 99999999999999999999. Heading` alongside an ordinary group and task
- **THEN** that group is absent from `groups`, the ordinary task keeps its coverage result, and the command prints its normal report rather than `internal_error`

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
