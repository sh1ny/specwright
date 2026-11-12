# pr-script-runtime Specification

## Purpose
Keeps the PR scripts working on every Python version they accept, keeps their failures machine-readable, and makes their prerequisites visible before the PR flow starts.

## Requirements

### Requirement: Pass records can be written on Python 3.8
The `pr-pair.sh` shim SHALL still accept Python 3.8 at its existing prerequisite check. `pass write` SHALL write its record through `sw`, as UTF-8 JSON with LF line endings and atomic replacement, without executing embedded Python. The script's prerequisite probe stays until runtime retirement.

#### Scenario: Pass write on Python 3.8
- **WHEN** the only Python on `PATH` is 3.8, a matching `sw` is installed and a valid store-backed `pass write` runs
- **THEN** the script exits 0 with `"ok": true`, and the record file exists, parses as JSON and contains no CR bytes

#### Scenario: No Python 3.8 available to the test
- **WHEN** the minimum-runtime test finds no Python 3.8 interpreter
- **THEN** it reports that interpreter check as skipped, and an always-run test verifies native pass-write dispatch and UTF-8/LF records without relying on embedded Python source

### Requirement: Unexpected failures keep the JSON error contract
`pr-pair.sh`, and each `sw pr` subcommand it hands a call to, SHALL report any unexpected exception as one JSON line on stdout with `"ok": false`, `"error": "internal_error"` and a `message` naming the exception type, and SHALL exit 1. Existing structured stops SHALL keep their own error codes and exit statuses.

#### Scenario: Filesystem error during pass write
- **WHEN** `pass write` runs and the record's parent directory path is an existing regular file
- **THEN** stdout is a single JSON line with `"error": "internal_error"`, the exit status is 1, and stderr contains no `Traceback`

#### Scenario: Existing structured stop
- **WHEN** `pass write` runs for a round whose record already exists
- **THEN** it reports the same error code and exit status as before this change

#### Scenario: Unexpected failure in a ported subcommand
- **WHEN** `sw pr context` meets an unexpected exception while it writes the reviewer config
- **THEN** stdout is a single JSON line with `"error": "internal_error"` and a message naming the exception type, the exit status is 1, and stderr holds no Dart stack trace

### Requirement: Prerequisites are stated and checked at install
The README prerequisites and install Step 1 SHALL list `bash` with a POSIX userland, `git` and Python 3.8+ as core requirements (the review scripts run every design and pre-ship review), and `gh` 2.48+ as a requirement of the PR skills. Install SHALL check each one. A missing core requirement SHALL stop the install. A missing PR requirement SHALL be reported as `PR workflow not ready: <missing>` without blocking the install. `specwright-pr` SHALL state the same script dependencies.

#### Scenario: All prerequisites present
- **WHEN** install runs where bash, git, gh 2.48 and Python 3.11 are available
- **THEN** Step 1 passes and the final report shows no `PR workflow not ready` line

#### Scenario: Python missing
- **WHEN** install runs where neither `python3` nor `python` reports version 3.8 or later
- **THEN** the install stops at Step 1 and tells the user to install Python 3.8 or later

#### Scenario: gh missing
- **WHEN** install runs where `gh` is missing or older than 2.48, and every core requirement is present
- **THEN** the install completes and its report includes `PR workflow not ready: gh 2.48+`

### Requirement: PR scripts remove their temp files on every exit
Every temp file a PR script creates SHALL be removed when the script exits, whether it succeeds, fails or stops on a structured error. A skill step that tells the agent to write a body or message to a temp file SHALL also tell it to remove that file once the command that reads it has run, whatever that command's outcome.

#### Scenario: Reply posted
- **WHEN** `pr-reply.sh` posts a reply and exits 0
- **THEN** no temp file it created remains

#### Scenario: Post fails
- **WHEN** `pr-reply.sh` has written its reply temp file and the GitHub call that posts it fails
- **THEN** the script exits non-zero and no temp file it created remains

#### Scenario: Pending review stop after the reply
- **WHEN** a thread reply was posted and the following pending-review check exits 2
- **THEN** no temp file it created remains

#### Scenario: Skill steps that write body files
- **WHEN** the `specwright-pr` text tells the agent to write a PR description, review request, reply or issue body to a temp file
- **THEN** the same step tells the agent to remove that file after the command that reads it

### Requirement: Network commands have a deadline
Every `gh` or `git` network command run by `pr-pair.sh`, `pr-snapshot.sh` or `pr-reply.sh`, and every credential or identity lookup `as.sh` makes before it runs the command it fences, SHALL run under a deadline: 120 seconds, or 300 seconds for a paginated read. When the deadline passes, the command and every process it started SHALL be stopped, and the script SHALL report `deadline_exceeded`, naming the command. It SHALL NOT wait for the command.

#### Scenario: GitHub answers in time
- **WHEN** `pr-pair.sh closing-check` runs and every `gh` call answers within its deadline
- **THEN** the check reports its result as before this change, and no `deadline_exceeded` appears

#### Scenario: Hung gh call in pr-pair.sh
- **WHEN** `pr-pair.sh discover` runs and its `gh api` call never answers
- **THEN** the script exits 3 within the deadline plus 10 seconds, with one JSON line holding `"error": "deadline_exceeded"` and a message naming `gh api`, and no `gh` process it started is still running

#### Scenario: Hung gh call in a bash PR script
- **WHEN** `pr-reply.sh` posts a reply and its `gh api` call never answers
- **THEN** the script exits non-zero within the deadline plus 10 seconds, stderr names `deadline_exceeded` and the command, and no temp file it created remains

#### Scenario: Hung credential lookup in as.sh
- **WHEN** `as.sh <login> gh ...` runs and its `gh auth token` lookup never answers
- **THEN** as.sh exits 3 within the deadline plus 10 seconds, names `deadline_exceeded` on stderr, and does not run the fenced command

### Requirement: GitHub responses are bounded
`pr-pair.sh`, `pr-snapshot.sh` and `pr-reply.sh` SHALL read at most 32 MiB from any one `gh` or `git` network command they run, paginated reads included, and `as.sh` at most 32 MiB from any credential or identity lookup it makes; the PR scripts SHALL read at most 50 pages in any cursor loop they drive themselves. Passing either bound SHALL stop the command and be reported as `response_too_large`, naming the command. It SHALL NOT yield a partial result.

#### Scenario: Large but bounded list
- **WHEN** `pr-pair.sh discover` reads a paginated list whose pages total 2 MiB
- **THEN** the script reads all of it and answers as before this change

#### Scenario: Oversized paginated read
- **WHEN** a paginated `gh api` read in `pr-pair.sh` prints more than 32 MiB
- **THEN** the script exits 3 with `"error": "response_too_large"` naming the command, and reports no partial list as the answer

#### Scenario: Reaction loop past its page cap
- **WHEN** `pass plan` looks for a reaction, and the reactions it pages through never contain it and have more than 50 pages
- **THEN** the script exits 3 with `"error": "response_too_large"`, and does not report the reaction as absent

### Requirement: A command that exits before its deadline keeps its result
A bounded network command that exits before its deadline SHALL return its own exit status and output, never `deadline_exceeded`, also when a process it started still holds its output open. Its exit SHALL be observed when it happens, not at a later poll. An exit first observed at or after the deadline SHALL be `deadline_exceeded`.

#### Scenario: Exit just before the deadline with a held pipe
- **WHEN** a bounded command with a 3-second deadline, run with the loop's wait interval raised to 5 seconds by the test hook, starts a child that keeps its stdout open and sleeps, and the command itself exits 0 at an absolute time the test set to 1 second before the run's deadline (measured from before the run starts)
- **THEN** the command's recorded exit time is before the run's deadline, the call returns exit status 0 and the command's output with no limit named, and the child is no longer running

#### Scenario: Exit after the deadline
- **WHEN** a bounded command with a 1-second deadline sleeps for 3 seconds and then exits 0
- **THEN** the call reports `deadline_exceeded` within the deadline plus 10 seconds, and no process it started is still running

### Requirement: A process a network command started is stopped on every platform
When a bounded network command is stopped, or exits while a process it started still holds its output, every process it started SHALL be stopped, on Windows as on POSIX, also when the command itself has already exited. When Windows cannot hold the command's processes together, the run SHALL say so on stderr and stop the tree from the command's process as before.

#### Scenario: No job object on Windows
- **WHEN** on Windows the test hook makes job creation fail, and a bounded command with a 1-second deadline sleeps
- **THEN** the call reports `deadline_exceeded`, the command's process is no longer running, and stderr holds one line saying the run has no job object and naming the reason

#### Scenario: Orphan holding the pipe on Windows
- **WHEN** on Windows a bounded command starts a child that keeps its stdout open and sleeps for an hour, and the command exits 0
- **THEN** the call returns within its grace period plus 5 seconds, and the child's process is no longer running

#### Scenario: Hung command with a grandchild
- **WHEN** a bounded command with a 1-second deadline starts a child that starts a grandchild, and all three sleep
- **THEN** the call reports `deadline_exceeded`, and neither the child nor the grandchild is still running

### Requirement: The deadline override is read one way
`SPECWRIGHT_NET_DEADLINE` SHALL be read by one rule for each command's deadline and for a watch poll's deadline: a non-negative decimal number of seconds, fractions included, that can lower the 120-second deadline and never raise it. A value that is not a non-negative number SHALL leave 120 seconds.

#### Scenario: Fractional override lowers the poll
- **WHEN** a watch poll runs with `SPECWRIGHT_NET_DEADLINE=1.5` and its first `gh` call never answers
- **THEN** the poll reports `deadline_exceeded` within 1.5 seconds plus 10 seconds, and the deadline every command of that poll received was at most 1.5 seconds from the start of the poll

#### Scenario: Invalid override
- **WHEN** a watch poll runs with `SPECWRIGHT_NET_DEADLINE=soon`
- **THEN** the poll's deadline is 120 seconds, as for each command in it

#### Scenario: Override above the default
- **WHEN** a watch poll runs with `SPECWRIGHT_NET_DEADLINE=500`
- **THEN** the poll's deadline is 120 seconds

### Requirement: PR snapshots and replies run in the project's sw
`pr-snapshot.sh` and `pr-reply.sh` SHALL keep their paths, arguments and output contracts, and SHALL run every call as `sw pr snapshot` or `sw pr reply` in the project's `sw`, found by the shared resolver. An optional leading `--project <code-checkout>` SHALL select only the project to resolve; without it, the project is the nearest directory holding a `.git` entry, cwd included, found with no Git command. Stdout, stderr and exit status SHALL be `sw`'s; no other implementation SHALL remain.

#### Scenario: Snapshot with a matching sw
- **WHEN** a matching `sw` is installed and `as.sh sh1ny bash pr-snapshot.sh 12 --repo o/r` runs against a PR with one unresolved thread
- **THEN** stdout is one JSON line listing that thread with its `id`, `rev` and body, and the exit status is 0

#### Scenario: Reply with a matching sw
- **WHEN** a matching `sw` is installed and `pr-reply.sh 12 thread <thread-id> <root-id> body.md --resolve --repo o/r` runs
- **THEN** one reply is posted whose body is the file's bytes followed by `<!-- specwright:handled <thread-id> resolve -->`, the thread is resolved, and the exit status is 0

#### Scenario: A refusal keeps its exit status
- **WHEN** `pr-reply.sh 12 comment <id> missing.md --repo o/r` runs and `missing.md` does not exist
- **THEN** the exit status is 4, stderr names the body file, and no `gh` call was made, as before this change

#### Scenario: Store-started snapshot selects the code project
- **WHEN** a planning store has no `openspec/.specwright/VERSION`, a matching `sw` is installed for the code project `<code>`, and `as.sh store-bot bash pr-snapshot.sh --project <code> 7 --repo o/store` runs inside the store
- **THEN** the snapshot of `o/store` PR 7 is printed, its gh calls run in the store with store-bot's token, and `--project` reaches `sw` neither as an argument nor as the repository

#### Scenario: Store-started reply selects the code project
- **WHEN** a planning store has no `openspec/.specwright/VERSION`, and `pr-reply.sh --project <code> 7 comment <id> body.md --repo o/store` runs inside the store with a matching `sw` for `<code>`
- **THEN** one reply is posted on `o/store` PR 7 and the exit status is 0

#### Scenario: Missing selected binary refuses without fallback
- **WHEN** `pr-snapshot.sh --project <code> 7` names a project with no matching `sw`, and the current directory's project has one
- **THEN** stdout is one `sw_missing` document, the exit status is 1, no `gh` call was made, and the other binary was not used

#### Scenario: Malformed project prefix
- **WHEN** `pr-reply.sh --project` is given without a value, with an empty value, or with a second leading `--project`
- **THEN** after the existing Python prerequisite check, the script prints a usage line on stderr, exits with its usage status (2 for `pr-snapshot.sh`, 4 for `pr-reply.sh`) and makes no `gh` call

### Requirement: A missing or mismatched sw stops PR snapshots and replies
When the resolver stops, `pr-snapshot.sh` and `pr-reply.sh` SHALL print one JSON document on stdout with `"ok": false`, `"error": "sw_missing"` and a `message` that starts with `sw missing or mismatched: rerun the install prompt` and holds the resolver's detail, and exit 1. They SHALL make no `gh` call and never fall back to another implementation, another version's binary or an `sw` on `PATH`.

#### Scenario: Reply with no sw posts nothing
- **WHEN** no matching `sw` is installed and `pr-reply.sh 12 comment <id> body.md --repo o/r` runs
- **THEN** the exit status is 1, stdout is one JSON document with `"error": "sw_missing"`, and nothing was posted

#### Scenario: Watch with no sw
- **WHEN** no matching `sw` is installed and `pr-snapshot.sh 12 --wait` runs
- **THEN** it exits 1 at once with the `sw_missing` document, and no watch claim file was created

#### Scenario: No Python
- **WHEN** no `python3` or `python` 3.8+ is on `PATH`
- **THEN** each script exits 2 with its `no_python` line on stderr, as before this change, and `sw` did not run

### Requirement: sw pr snapshot and sw pr reply keep the scripts' contracts
`sw pr snapshot` and `sw pr reply`, run through the scripts' shims, SHALL take the scripts' arguments and print the same stdout bytes, stderr messages and exit statuses for the same GitHub answers: the snapshot line, `--full`, `--wait` wake documents, markers, revision checks, reactions and resolutions included. `sw pr snapshot` has two exceptions: its `reviewer_config` digest is that of the format 2 config, and an evaluator line it relays keeps its `reviewers.py:` prefix, its wording free.

#### Scenario: Unchanged black-box evals pass on sw
- **WHEN** `evals/pr-pair/test_pr_snapshot.py`, `test_pr_reply.py` and every other eval that runs the two scripts run in CI on Linux, Windows and macOS against the `sw` built from the tree
- **THEN** every test passes with its assertions unchanged from before this change, apart from the format 2 digest and the wording of relayed `reviewers.py:` lines; every other byte of stdout, stderr and the exit status is compared as before

#### Scenario: Stale revision posts nothing
- **WHEN** `pr-reply.sh 12 thread <t> <r> body.md --rev 900@2026-11-01T10:00:00Z` runs and the thread's revision is now `901@2026-11-02T09:00:00Z`
- **THEN** the exit status is 5, stderr says `judged 900@2026-11-01T10:00:00Z, now 901@2026-11-02T09:00:00Z`, and nothing was posted, resolved or reacted to

#### Scenario: Removed reviewer flag
- **WHEN** `pr-snapshot.sh 12 --reviewer bot:review:600` runs
- **THEN** it exits 2 naming `--reviewer-config`, before any `gh` call

### Requirement: Watch claims and head records stay shared across implementations
`sw pr snapshot` SHALL read and write watch claims under `<state>/watch/v2/<owner>/<name>/<pr>/` (lower case) and head records under `<state>/heads/`, where `<state>` is `SPECWRIGHT_STATE_DIR`, else `$HOME/.cache/specwright`, with the file names and contents `pr-snapshot.sh` used before this change, so `pr-pair.sh` and a watcher of either implementation see each other's claims and records.

#### Scenario: A newer sw watcher takes over an older script watcher
- **WHEN** a watcher run by the `pr-snapshot.sh` from before this change waits on PR 12, and the new `pr-snapshot.sh 12 --wait` shim starts a `sw pr snapshot` watcher for the same PR
- **THEN** the older watcher exits 4 before its next poll, and the new watcher owns the PR

#### Scenario: Equal claim numbers across implementations (accepted gap)
- **WHEN** an old-script watcher and an `sw` watcher create claims with the same number on PR 12 within one directory listing
- **THEN** `sw` picks the owner by comparing the nonces as bytes, the old script compares them by the locale's collation, and the two may each see themselves as owner. This is accepted and is not a parity failure. If a duplicate owner is ever seen in a run, the gap is reconsidered

#### Scenario: State directory cannot be created
- **WHEN** `SPECWRIGHT_STATE_DIR` names a path under a regular file and `pr-snapshot.sh 12 --wait` runs
- **THEN** stderr says `pr-snapshot: cannot create the watch state directory; ownership is off for PR 12 (this watcher polls unowned)` and the watch goes on unowned

### Requirement: The ported pr-pair subcommands keep the script's contracts
`sw pr identity`, `vcs`, `tier`, `context` and `policy`, run through the shim, SHALL accept the argument forms shipped callers use, print a JSON line with the same parsed fields and values, and exit with the same status for the same settings files, repositories and GitHub answers, apart from the native-cli JSON, input and option differences. That covers the settings problems, the reviewer-config bytes (apart from `"format": 2`), path and digest, the GitButler pin, and the policy checks.

#### Scenario: Policy's remote settings read is strict
- **WHEN** `policy` reads a settings file from the remote and it holds a construct the strict reader cannot read whole
- **THEN** `policy` stops with `lookup_failed` and merges nothing, and never decides from a best-effort parse

#### Scenario: Git Bash path forms
- **WHEN** on Windows a subcommand is given a directory or snapshot file as a Git Bash path such as `/c/work/repo`
- **THEN** it reads the same repository or file as with `C:/work/repo`, and a path it reports is in the `C:/` form

#### Scenario: Unchanged black-box evals pass on sw
- **WHEN** the `evals/pr-pair` and `evals/vcs` tests that run these five subcommands run in CI on Linux, Windows and macOS against the `sw` built from the tree
- **THEN** every test passes with its assertions unchanged from before this change, apart from the format migration (D10): the expected `"format"` value, the reviewer-config digests and content-addressed paths derived from it, and the format refused by the config check; the regex dialect cases (pr-evidence); assertions on free text, which check its prefix instead (see the message-text requirement); and assertions on stdout bytes, which compare the parsed value instead. The native-cli JSON/input and option differences have explicit outcome tests; every other field, error code and exit status is compared exactly

#### Scenario: Differential run against the frozen script
- **WHEN** the parity eval runs a case of each subcommand through the frozen copy of `pr-pair.sh` and through the shim, against the same repositories and fake-gh state
- **THEN** both exit with the same status and make the same `gh` calls for inputs retained by the native-cli contract; documented JSON/input and option refusals have explicit difference tests. For retained inputs they print stderr with the same lines up to each line's prefix. Their stdout parses to the same JSON value, apart from free text compared by its prefix and except that each `reviewer_config` digest and config path names that side's own file. Each side writes a reviewer config whose bytes are checked exactly on their own: the frozen script's with `"format": 1`, the shim's the same with `"format": 2`. Each file is named by the digest of its own bytes, and each digest field in stdout equals that digest

#### Scenario: A malformed settings file names its line
- **WHEN** `openspec/specwright.yaml` holds a tab in its indentation on line 7 and `pr-pair.sh context --code <code>` runs
- **THEN** `settings_problem` starts with `line 7:` as before this change, and the exit status is the same

#### Scenario: Settings not pinned on GitButler
- **WHEN** `vcs` is `gitbutler`, the work-tree `openspec/specwright.yaml` differs from the one committed on `feat/a`, and `pr-pair.sh context --code <code> --branch feat/a` runs
- **THEN** it exits 1 with `"error": "settings_not_pinned"`, naming the file and the ref, as before this change

### Requirement: Message text of the ported subcommands may be reworded
Free text in dispatched `sw pr` commands and `reviewers` MAY be reworded after stable prefixes. Other representations MAY change with their consuming skills when explicit contract tests prove the same workflow outcomes. Identity, mutation guards, ownership and recovery SHALL remain intact. Retained interfaces keep their existing values/statuses; persisted records remain interoperable. Incidental Python formatting and parser quirks SHALL NOT require byte-for-byte replicas.

#### Scenario: A reworded stop keeps its code
- **WHEN** `pr-pair.sh policy` reads a default-branch settings file whose content is not valid base64
- **THEN** stdout has `"error": "lookup_failed"` and the exit status is 3, as before this change, and `message` starts with `merge policy unknown: unreadable openspec/specwright.yaml at <ref>:`

#### Scenario: Workflow error keeps structured values
- **WHEN** native `ensure-pr` finds an open PR targeting another base
- **THEN** it returns `wrong_base` with the same PR and base values and exit status as the frozen script, without creating a PR

### Requirement: sw pr reviewers keeps the evaluator's contract
`sw pr reviewers --check-config FILE` and `sw pr reviewers --config FILE --material FILE --head OID` SHALL print the same parsed output fields, one stderr line prefixed `reviewers.py:` where `reviewers.py` printed one, naming the same reviewer and key, and exit with the same status as `reviewers.py` did, except where a report pattern compiles differently, the config's format is not 2 (see pr-evidence), or the native-cli JSON/input or option contract explicitly changes an accepted form.

#### Scenario: Unchanged evaluator tests
- **WHEN** `evals/pr-pair/test_reviewers.py` runs against `sw pr reviewers` in CI on Linux, Windows and macOS
- **THEN** every test passes with its assertions unchanged from before this change, apart from the format migration (D10): the expected `"format"` value, the reviewer-config digests and content-addressed paths derived from it, and the format refused by the config check; the regex dialect cases (pr-evidence); assertions on free text, which check its prefix instead (see the message-text requirement); and assertions on stdout bytes, which compare the parsed value instead. The native-cli JSON/input and option differences have explicit outcome tests; every other field, error code and exit status is compared exactly

#### Scenario: Material that is not its head
- **WHEN** `sw pr reviewers --config cfg.json --material m.json --head <oid>` runs and `m.json` is for another head
- **THEN** it exits 1 with nothing on stdout, as `reviewers.py` did

### Requirement: Snapshots evaluate reviewers through sw
`sw pr snapshot` SHALL check the `--reviewer-config` file in its own process before any `gh` call. It SHALL decide reviewer states by running its own binary as `sw pr reviewers` under the deadline, byte bound and temp-file rules `reviewers.py` ran under, and SHALL read that child's document by parsing it. It SHALL start no Python evaluator and run no interpreter probe; the `pr-snapshot.sh` shim keeps its own prerequisite check until `native-cli-retire-scripts`.

#### Scenario: Reviewer states decided in sw
- **WHEN** `pr-snapshot.sh 12 --reviewer-config cfg.json` runs and `cfg.json` lists `chatgpt-codex-connector[bot]` as a reviewer that has posted its report
- **THEN** that login's `reviewers` entry has the state `reviewers.py` decided before this change, `reviewer_config` holds the file's digest, and no `reviewers.py` process was started

#### Scenario: A pattern that backtracks past the deadline
- **WHEN** a reviewer's `report.ignore` backtracks on a comment body for longer than the evaluator's deadline
- **THEN** the evaluation is stopped at the deadline, stderr holds the line `bounded: deadline_exceeded: reviewers.py python3`, the poll fails, and no evaluator process or material file is left

#### Scenario: Bad reviewer config
- **WHEN** `cfg.json` is not valid JSON and `pr-snapshot.sh 12 --reviewer-config cfg.json` runs
- **THEN** the exit status is 2, stderr holds one line prefixed `reviewers.py:` that says the file is not valid JSON, no `gh` call was made, and no child `sw` was started for the check

#### Scenario: No Python on PATH
- **WHEN** `sw pr snapshot` runs through its handoff with failing `python` and `python3` first on `PATH` and a reviewer config
- **THEN** the snapshot and its reviewer states are printed with exit 0, neither interpreter ran, and stderr holds no `no_python` line

#### Scenario: Evaluator output that is not a document
- **WHEN** the `sw pr reviewers` child exits 0 but its stdout does not parse as one JSON document
- **THEN** the poll fails with exit 1 and prints no snapshot built from that output

### Requirement: All pr-pair subcommands run in the project's sw
`pr-pair.sh` SHALL keep its path and arguments and dispatch all nineteen subcommands to the project's matching `sw`. Its stdout, stderr and exit status SHALL be those of `sw`; no embedded Python implementation SHALL remain. The five existing native entry points SHALL stay supported. With a matching binary, missing and unknown commands SHALL retain the script's usage JSON and exit 2.

#### Scenario: Context with a matching sw
- **WHEN** a matching `sw` is installed and `pr-pair.sh context --code <code>` runs in a repo-local project
- **THEN** stdout is one JSON line with `"ok": true`, the code repo's `login`, `main` and `reviewer_config`, and the exit status is 0, as before this change

#### Scenario: Discovery runs natively
- **WHEN** a matching `sw` is installed and `pr-pair.sh discover --repo o/r --branch feat/a` runs
- **THEN** the shim runs the native discovery command and returns the same normalized PR list and exit status as the frozen script

#### Scenario: Identity of a store from the code checkout
- **WHEN** a matching `sw` is installed for the code project, the store checkout has no `openspec/.specwright/VERSION`, and `pr-pair.sh identity <store toplevel>` runs from the code checkout
- **THEN** stdout is one JSON line with the store's `<owner>/<name>` from its `origin`, and the exit status is 0, as before this change

#### Scenario: Missing subcommand
- **WHEN** a matching `sw` is installed and `pr-pair.sh` runs with no arguments
- **THEN** it returns the usage JSON listing all nineteen subcommands and exits 2

#### Scenario: Unknown subcommand
- **WHEN** a matching `sw` is installed and `pr-pair.sh not-a-command` runs
- **THEN** it returns the same usage JSON and exit 2, without making a GitHub call or writing state

### Requirement: A missing or mismatched sw stops every pr-pair invocation
When resolution fails, every `pr-pair.sh` invocation SHALL return one JSON line with `"ok": false`, `"error": "sw_missing"` and a message beginning `sw missing or mismatched: rerun the install prompt`, and exit 1. It SHALL make no GitHub call, write no workflow state and never fall back to embedded Python or another binary. The existing Python prerequisite check SHALL still precede resolution.

#### Scenario: Policy with no sw
- **WHEN** no matching `sw` is installed and `pr-pair.sh policy --repo o/r --head <sha> --snapshot code=s.json` runs
- **THEN** the exit status is 1, stdout is one JSON line with `"error": "sw_missing"`, and no `gh` call was made

#### Scenario: Workflow command needs matching sw
- **WHEN** no matching `sw` is installed and `pr-pair.sh branch-check --dir <d> --branch feat/a --main main` runs
- **THEN** it exits 1 with `sw_missing`, without reading or deleting the branch

#### Scenario: Matching binary permits dispatch
- **WHEN** a matching `sw` is installed and a valid branch-check invocation runs
- **THEN** it returns the native branch-check result rather than `sw_missing`

#### Scenario: No Python
- **WHEN** no `python3` or `python` 3.8+ is on `PATH` and `pr-pair.sh context --code <code>` runs
- **THEN** it exits 2 with its `no_python` JSON line, as before this change, and `sw` did not run

### Requirement: Native PR workflow commands preserve their effects
The fourteen newly native commands SHALL preserve product workflow outcomes, effects, mutation sequencing, identity and recovery. Producer/consumer representations MAY change together with explicit contract tests and documented differences. The frozen script is comparison evidence, not a byte-format mandate. Printed commands SHALL execute in the intended cwd with correct arguments/login. Failed or limited reads SHALL retain unknown/unreadable/refusal decisions without speculative mutation.

#### Scenario: Every workflow command has differential coverage
- **WHEN** differential cases run discovery, expected-set, creation, closing checks, linking, pair-state, rounds, all four pass operations, cleanup, branch-check, merge, delete-remote and item-issues through both implementations
- **THEN** workflow decisions, effects, identity, mutation guards and recovery agree, including success and failure cases for each command; any representation difference has explicit producer/consumer contract coverage

#### Scenario: Unknown read permits no follow-on mutation
- **WHEN** discovery or an issue-state read fails or exceeds its deadline or byte bound
- **THEN** the native command retains the frozen script's error, unknown fields and exit status, and makes no follow-on create, merge or delete call

#### Scenario: Merge is attempted once then read back
- **WHEN** the merge request is cut off after GitHub accepted it
- **THEN** the command makes one merge request and a read-back, returning the merged result when confirmed, or unknown when the read-back fails, without a second merge request

#### Scenario: Moved remote branch is retained
- **WHEN** delete-remote finds that the branch no longer points to the supplied merged head
- **THEN** it reports the moved state and performs no delete request

#### Scenario: Rendered closing lines preserve code boundaries
- **WHEN** closing-check reads a rendered description containing code spans, code blocks, entities and closing-list prose
- **THEN** `intended`, `missing`, `extra` and `status` describe the issues and state from standard HTML5 interpretation, text rendered as code is not an intended issue, and a code span between references ends the closing list

#### Scenario: Malformed table text follows HTML5 interpretation
- **WHEN** closing prose is extracted from malformed HTML `Fixes <table>#1</table>`
- **THEN** issue 1 in the description's own repository is an intended closing reference under HTML5 tree construction

#### Scenario: Feedback round counters remain encodable
- **WHEN** rounds reads no feedback trailers or ordinary in-range Feedback-Round trailers
- **THEN** rounds and per-repository max_trailer are exact JSON integers, including zero, and the workflow decision is preserved

#### Scenario: Oversized feedback-round trailer is refused
- **WHEN** rounds reads a Feedback-Round trailer exceeding signed 64-bit range
- **THEN** it stops with its unknown-read error, without ignoring, rounding or wrapping the trailer, and makes no mutation

### Requirement: Feedback record locks and fallback publication stay exclusive
Write SHALL publish exclusively; adopt and done SHALL hold their own record lock and never remove another call's lock. Native locks SHALL be exclusively created files at the existing `.lock` path; legacy lock directories SHALL still block and SHALL never be removed automatically. A failed hard link MAY fall back to exclusive creation that refuses an occupied destination. An ordinary failure after that creation SHALL remove only the file the request created.

#### Scenario: Concurrent mutations acquire one lock
- **WHEN** two adopt or done calls race for the same record while the winning call holds its lock
- **THEN** exactly one call holds the lock, the other reports record_busy without changing the record, and only the holder releases the lock

#### Scenario: Native and legacy locks exclude each other
- **WHEN** a native call finds a legacy lock directory, or a legacy script call finds a native lock file at the same `.lock` path
- **THEN** the second call refuses the held lock and leaves it untouched; native cleanup removes only its own created file

#### Scenario: Interrupted SDK publication stays recoverable
- **WHEN** the SDK fallback is interrupted after exclusive creation but before opening or finishing the record
- **THEN** the empty or partial record remains in place, `pass write` refuses with record_exists, and `pass plan`, `pass adopt` and `pass done` return record_unreadable

#### Scenario: Fallback permission failure leaves no record
- **WHEN** the publication fallback exclusively creates a POSIX record and setting its private permissions fails
- **THEN** the error is reported, no record content was written, only the created file is removed, and a later `pass write` can create the record

### Requirement: Workflow shims select a binary project explicitly
`pr-pair.sh` SHALL accept one leading `--project <code-checkout>` prefix for exact-version binary selection, consume it before native dispatch and preserve cwd and remaining arguments. Without it, current project discovery SHALL remain. Store callers and emitted cleanup commands SHALL name the code project where discovery cannot resolve it; every other printed argument and cwd SHALL remain unchanged.

#### Scenario: Workflow command starts in a store
- **WHEN** a store without VERSION runs pr-pair.sh --project <code> discover with a matching binary for the selected code project
- **THEN** discovery runs natively with cwd still the store, and the prefix is not passed as a workflow command argument

#### Scenario: Cleanup commands carry the explicit project
- **WHEN** cleanup-plan emits store branch-check and fenced pull commands
- **THEN** each shim needing binary resolution carries --project <code>, preserves the store cwd, and retains every other command argument

#### Scenario: Selected project cannot resolve a binary
- **WHEN** the explicit project has no usable matching binary even though another sw is available from cwd or PATH
- **THEN** the shim returns sw_missing with exit 1, performs no GitHub call and never falls back to the other binary

#### Scenario: Malformed project prefix is refused
- **WHEN** the leading --project prefix lacks a nonempty value or is repeated as a leading selector
- **THEN** after the existing Python prerequisite check, the shim returns one JSON line with `"error": "usage"` and exit 2 before resolution, authentication or state changes

### Requirement: Paginated GitHub lists read every page or decide nothing
A list read that decodes whole pages SHALL use `gh api --paginate --slurp`, flatten the returned array of pages into one list in page order, and on any response other than an array of arrays SHALL report the read as unknown. An unknown read SHALL NOT lead to a GitHub mutation. `item-issues` retains `--paginate --jq` per-page output and its existing `unreadable response` refusal.

#### Scenario: Several pages
- **WHEN** `gh` returns three pages holding 100, 100 and 7 items for a list read
- **THEN** the caller receives 207 items in page order

#### Scenario: No items
- **WHEN** `gh` returns one empty page
- **THEN** the caller receives an empty list and reports no error

#### Scenario: A page that is not an array
- **WHEN** one page in the response is a JSON object
- **THEN** the read is unknown, the command stops with its unknown-read error, and no GitHub write is made

#### Scenario: gh older than 2.48
- **WHEN** `gh` exits non-zero reporting that `--slurp` is an unknown flag
- **THEN** the read is unknown, the message names `gh` 2.48 as the minimum version, and no GitHub write is made

### Requirement: Native workflow integration calls every ported operation in process
Native PR workflow code SHALL call ported settings, fence and VCS operations directly, the non-Git branch-check's VCS fetch-main included. It SHALL retain target-repo checks, per-call credentials, environment restoration and existing bounds. Reads previously bounded as a whole SHALL share that budget. Unbounded VCS reads and planning SHALL stay unbounded.

#### Scenario: Internal scripts are not launched
- **WHEN** workflow calls need VCS state or plans and fenced reads, and the handoff scripts directory contains recording as.sh and vcs.sh sentinels
- **THEN** neither sentinel runs, no second sw is launched for those operations, and the workflow returns the expected result

#### Scenario: Nested VCS fetch runs the fence in process
- **WHEN** non-Git branch-check with --code invokes native VCS fetch-main for a store that has no `openspec/.specwright/VERSION`, and the handoff scripts directory contains a recording as.sh sentinel
- **THEN** login resolution (when no --login was given) and the fetch run in process in the store's directory as the store's login, the sentinel does not run, and the result is not sw_missing

#### Scenario: Fenced read uses one deadline
- **WHEN** pass-plan performs a fenced Git read, credential checks consume part of its existing outer budget, and the Git command then hangs with a descendant
- **THEN** the remaining budget limits execution, the descendant is terminated, and pass-plan reports deadline_exceeded with exit 3 and its existing unknown fields

#### Scenario: Rounds reports an outer read deadline as unreadable
- **WHEN** a rounds remote_contains read exceeds its enclosing deadline
- **THEN** rounds returns ok true with remote_unreadable and the same unpushed and round results as the frozen script

#### Scenario: Nested fence lookup limit retains refusal mapping
- **WHEN** a rounds fenced read has a nested credential or identity lookup reach its own smaller deadline before the outer budget expires
- **THEN** it retains the fence_refused result and exit 3 rather than converting the nested limit to remote_unreadable

#### Scenario: Direct VCS failures retain wrapper mapping
- **WHEN** a direct VCS state or plan call returns an exit-2 stop with additional fields
- **THEN** its workflow caller preserves the frozen script's exit-1 mapping and error/message fields without adding the native stop's extra fields

#### Scenario: Another repository is checked under its own identity
- **WHEN** a command started in repo A needs a GitHub read in repo B under another login
- **THEN** it checks B's remotes, uses B's verified per-call credential, leaves the parent environment and later login unchanged, and refuses before networking if B's URL contains credentials

#### Scenario: Non-GitHub transport restores the original environment
- **WHEN** a workflow started under a GitHub fence reads a non-GitHub remote
- **THEN** the child receives the restored pre-fence transport environment without the GitHub token, as in the frozen script

#### Scenario: Command arguments remain exact
- **WHEN** a direct fenced read receives empty arguments, shell metacharacters or long Windows values
- **THEN** the invoked tool receives the same argument values as through the old script, with no shell started, without expansion, truncation or credential values in diagnostics

#### Scenario: A non-UTF-8 path argument is refused
- **WHEN** a direct fenced read is handed a POSIX path argument holding non-UTF-8 bytes
- **THEN** the workflow stops with `"error": "not_utf8"` and exit 1 before any credential lookup, and the tool does not run

#### Scenario: Unbounded VCS calls remain unbounded
- **WHEN** a workflow's VCS state or plan call takes longer than the configured network deadline but completes
- **THEN** the workflow receives its result without a newly introduced deadline_exceeded stop

### Requirement: Feedback records interoperate across the port on UTF-8 paths
Native pass operations SHALL preserve record keys, version-2 JSON, LF encoding, ownership, legacy migration and exclusive publication. Interrupted or foreign-owned state SHALL retain the existing recovery result; the port SHALL NOT start a new pass beside an unreadable record or silently adopt another owner. A state-directory or home value that is not valid UTF-8 SHALL stop the call with `"error": "not_utf8"`, exit 1, before any record is read or written.

#### Scenario: Native plan resumes an existing record
- **WHEN** the frozen script writes a record and native pass-plan reads it with equivalent snapshots, local history and owner
- **THEN** the native plan returns the same resume rows, owner state and completion decision, without starting a new pass

#### Scenario: Script plan reads a native record
- **WHEN** native pass-write writes a record and the frozen script reads it
- **THEN** the script reads the same intent, owner and state, with UTF-8/LF contents and the same record key

#### Scenario: Non-UTF-8 POSIX state directory stops by name
- **WHEN** a POSIX feedback call uses a process state-directory environment value containing non-UTF-8 path bytes
- **THEN** it returns `"error": "not_utf8"` with exit 1 and a `message` that names `SPECWRIGHT_STATE_DIR` and asks for a UTF-8 path, and no record is read or created in any directory

#### Scenario: Injected environment does not inherit an ambient directory
- **WHEN** a call supplies an explicit environment while the process has a different state-directory value
- **THEN** feedback path selection uses only the supplied environment, including its missing or empty values

#### Scenario: Non-UTF-8 POSIX home stops by name
- **WHEN** a POSIX feedback call has no nonempty process state-directory value and a process `HOME` containing non-UTF-8 bytes
- **THEN** it returns `"error": "not_utf8"` with exit 1 and a `message` that names `HOME`, and no record is read or created

#### Scenario: Process state override does not need a home
- **WHEN** a POSIX feedback call has a nonempty process state-directory value and `HOME` is unset
- **THEN** the record is located under the state directory and the call does not stop for a missing home

#### Scenario: Missing home refuses without choosing a directory
- **WHEN** a POSIX process feedback call has a missing or empty state-directory value and `HOME` is unset or empty
- **THEN** it returns internal_error with exit 1, creates no record and uses no substitute directory

#### Scenario: A non-UTF-8 state directory never falls back to a default
- **WHEN** a POSIX pass plan has a non-UTF-8 process state-directory value and a head record exists in the default state directory
- **THEN** the plan returns `"error": "not_utf8"` with exit 1 and does not read the default directory's record

#### Scenario: Concurrent writers publish one record
- **WHEN** two valid pass-write calls race for the same record
- **THEN** exactly one complete record is published, and the losing call reports the frozen script's refusal rather than overwriting it

#### Scenario: Legacy migration and held lock remain safe
- **WHEN** a matching legacy record is migrated and a later adopt call finds the record lock already held
- **THEN** migration retains the record identity and contents, and adopt reports record_busy without changing the owner or removing the lock

#### Scenario: Unreadable record blocks a new pass
- **WHEN** a new-key record or a sole matching legacy record contains truncated JSON
- **THEN** `pass plan`, `pass adopt` and `pass done` return record_unreadable; `pass write` returns record_unreadable for a sole legacy record and record_exists for a new-key record; and the file is left in place
