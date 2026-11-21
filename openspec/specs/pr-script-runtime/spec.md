# pr-script-runtime Specification

## Purpose
Keeps the PR scripts working on every Python version they accept, keeps their failures machine-readable, and makes their prerequisites visible before the PR flow starts.

## Requirements

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
The README prerequisites and install Step 1 SHALL list `git` as the core requirement and `gh` 2.48+ as a requirement of the PR skills. They SHALL list no bash, no POSIX userland and no Python for Specwright's own work. Install SHALL check each listed tool. A missing `git` SHALL stop the install. A missing PR requirement SHALL be reported as `PR workflow not ready: <missing>` without blocking the install. `specwright-pr` SHALL state the same dependencies.

#### Scenario: All prerequisites present
- **WHEN** install runs where `git` and `gh` 2.48 are available, and no `bash`, `python3` or `python` is on `PATH`
- **THEN** Step 1 passes and the final report shows no `PR workflow not ready` line

#### Scenario: git missing
- **WHEN** install runs where `git` is not on `PATH`
- **THEN** the install stops at Step 1 and tells the user to install `git`

#### Scenario: Python missing
- **WHEN** install runs where neither `python3` nor `python` is on `PATH`, and `git` is present
- **THEN** Step 1 passes and the install asks for no Python

#### Scenario: gh missing
- **WHEN** install runs where `gh` is missing or older than 2.48, and `git` is present
- **THEN** the install completes and its report includes `PR workflow not ready: gh 2.48+`

#### Scenario: No bash or Python prerequisite in the docs
- **WHEN** the README prerequisites, install Step 1 and `specwright-pr` are searched for the tools they require
- **THEN** none names bash, a POSIX userland or Python as a requirement

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
`sw pr snapshot` and `sw pr reply` SHALL keep the scripts' arguments and output contracts and run in the project's `sw` after its version check. A leading `--project <code-checkout>` SHALL select only the project whose `VERSION` is checked. Stdout, stderr and exit status SHALL be `sw`'s; no other implementation SHALL remain.

#### Scenario: Snapshot with a matching sw
- **WHEN** the project's `VERSION` matches the running `sw` and `<sw> as sh1ny <sw> pr snapshot 12 --repo o/r` runs against a PR with one unresolved thread
- **THEN** stdout is one JSON line listing that thread with its `id`, `rev` and body, and the exit status is 0

#### Scenario: Reply with a matching sw
- **WHEN** the project's `VERSION` matches and `<sw> pr reply 12 thread <thread-id> <root-id> body.md --resolve --repo o/r` runs
- **THEN** one reply is posted whose body is the file's bytes followed by `<!-- specwright:handled <thread-id> resolve -->`, the thread is resolved, and the exit status is 0

#### Scenario: A refusal keeps its exit status
- **WHEN** `<sw> pr reply 12 comment <id> missing.md --repo o/r` runs and `missing.md` does not exist
- **THEN** the exit status is 4, stderr names the body file, and no `gh` call was made

#### Scenario: Store-started snapshot selects the code project
- **WHEN** a planning store has no `openspec/.specwright/VERSION`, the code project `<code>` matches the running `sw`, and `<sw> --project <code> as store-bot <sw> --project <code> pr snapshot 7 --repo o/store` runs inside the store
- **THEN** the snapshot of `o/store` PR 7 is printed, its gh calls run in the store with store-bot's token, and `--project` reaches the subcommand neither as an argument nor as the repository

#### Scenario: Store-started reply selects the code project
- **WHEN** a planning store has no `openspec/.specwright/VERSION`, and `<sw> --project <code> pr reply 7 comment <id> body.md --repo o/store` runs inside the store with `<code>` matching the running `sw`
- **THEN** one reply is posted on `o/store` PR 7 and the exit status is 0

#### Scenario: Missing selected binary refuses without fallback
- **WHEN** `<sw> --project <code> pr snapshot 7` names a project whose `VERSION` differs from the running `sw`, and the current directory's project matches
- **THEN** stdout is one `sw_mismatch` document, the exit status is 1, no `gh` call was made, and no other binary was used

#### Scenario: Malformed project prefix
- **WHEN** `<sw> --project` is given without a value or with an empty value before `pr reply`
- **THEN** `sw` stops with a usage error, exit 2, and makes no `gh` call

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
`sw pr identity`, `vcs`, `tier`, `context` and `policy` SHALL accept the argument forms shipped callers use, print a JSON line with the same parsed fields and values, and exit with the same status for the same settings files, repositories and GitHub answers, apart from the native-cli JSON, input and option differences. That covers the settings problems, the reviewer-config bytes (apart from `"format": 2`), path and digest, the GitButler pin, and the policy checks.

#### Scenario: Policy's remote settings read is strict
- **WHEN** `policy` reads a settings file from the remote and the settings reader refuses it, or it holds a duplicate key, or a section has the wrong shape
- **THEN** `policy` stops with `lookup_failed` and merges nothing, and never decides from a best-effort parse

#### Scenario: Git Bash path forms
- **WHEN** on Windows Git Bash runs a subcommand with a directory or snapshot file given as `/c/work/repo`
- **THEN** `sw` receives `C:/work/repo`, converted by Git Bash, reads that repository or file, and a path it reports is in the `C:/` form

#### Scenario: Unchanged black-box evals pass on sw
- **WHEN** the `evals/pr-pair` and `evals/vcs` tests that run these five subcommands run in CI on Linux, Windows and macOS against the `sw` built from the tree
- **THEN** every test passes with its assertions unchanged from before this change, apart from the format migration (D10): the expected `"format"` value, the reviewer-config digests and content-addressed paths derived from it, and the format refused by the config check; the regex dialect cases (pr-evidence); assertions on free text, which check its prefix instead (see the message-text requirement); assertions on stdout bytes, which compare the parsed value instead; and the settings cases `native-cli-yaml-settings` changed, which assert the value read or the stop reported. The native-cli JSON/input and option differences have explicit outcome tests; every other field, error code and exit status is compared exactly

#### Scenario: Differential run against the frozen script
- **WHEN** the parity eval runs each case of each subcommand through `sw pr`, against the repositories and fake-gh state the case builds, and compares it with the record the frozen `pr-pair.sh` produced for that case, captured in the commit before the scripts were removed
- **THEN** `sw pr` exits with the recorded status and makes the recorded `gh` calls for inputs retained by the native-cli contract; documented JSON/input and option refusals keep their explicit difference tests. Stderr lines match the record up to each line's prefix, and stdout parses to the recorded JSON value apart from free text compared by its prefix, `reviewer_config` digests and paths, which name `sw pr`'s own `"format": 2` file, the listed settings differences with their own outcome tests, and `cleanup-plan`'s printed commands, which this change moves from `bash .../as.sh`, `vcs.sh` and `pr-pair.sh` to `<sw> --project <code> ...`: their decisions, guards, order and `gh` calls match the record, and their argv, working directory and project selection are asserted on their own. Records hold no paths of the machine that made them. A run-generated feedback owner id in `pass write` stdout is checked to equal the owner in the record that run wrote and is then replaced by a placeholder before the comparison, and persisted write and adopt times are checked against the run, as the live matrix did. Fixture commits are made with a pinned author, committer and dates, so their ids repeat across runs and `lacking[].sha` is compared exactly; the final fake-gh state and each written comment body are recorded and compared byte for byte

#### Scenario: A malformed settings file names its line
- **WHEN** `openspec/specwright.yaml` holds a tab in its indentation on line 7 and `pr-pair.sh context --code <code>` runs
- **THEN** it exits 2 with `"error": "bad_setting"` and a `message` naming `line 7`, and prints no settings values

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
`sw pr snapshot` SHALL check the `--reviewer-config` file in its own process before any `gh` call. It SHALL decide reviewer states by running its own binary as `sw pr reviewers` under the deadline, byte bound and temp-file rules `reviewers.py` ran under, and SHALL read that child's document by parsing it. It SHALL start no Python evaluator and run no interpreter probe.

#### Scenario: Reviewer states decided in sw
- **WHEN** `<sw> pr snapshot 12 --reviewer-config cfg.json` runs and `cfg.json` lists `chatgpt-codex-connector[bot]` as a reviewer that has posted its report
- **THEN** that login's `reviewers` entry has the state `reviewers.py` decided before this change, `reviewer_config` holds the file's digest, and no `reviewers.py` process was started

#### Scenario: A pattern that backtracks past the deadline
- **WHEN** a reviewer's `report.ignore` backtracks on a comment body for longer than the evaluator's deadline
- **THEN** the evaluation is stopped at the deadline, stderr holds the line `bounded: deadline_exceeded: reviewers.py python3`, the poll fails, and no evaluator process or material file is left

#### Scenario: Bad reviewer config
- **WHEN** `cfg.json` is not valid JSON and `<sw> pr snapshot 12 --reviewer-config cfg.json` runs
- **THEN** the exit status is 2, stderr holds one line prefixed `reviewers.py:` that says the file is not valid JSON, no `gh` call was made, and no child `sw` was started for the check

#### Scenario: No Python on PATH
- **WHEN** `<sw> pr snapshot` runs directly with failing `python` and `python3` first on `PATH` and a reviewer config
- **THEN** the snapshot and its reviewer states are printed with exit 0, neither interpreter ran, and stderr holds no `no_python` line

#### Scenario: Evaluator output that is not a document
- **WHEN** the `sw pr reviewers` child exits 0 but its stdout does not parse as one JSON document
- **THEN** the poll fails with exit 1 and prints no snapshot built from that output

### Requirement: All pr-pair subcommands run in the project's sw
`sw pr` SHALL run all nineteen subcommands itself, after the project's version check. Its stdout, stderr and exit status SHALL be its own; no embedded Python implementation SHALL remain. With a matching version, a missing or unknown subcommand SHALL return the usage JSON and exit 2.

#### Scenario: Context with a matching sw
- **WHEN** the project's `VERSION` matches the running `sw` and `<sw> pr context --code <code>` runs in a repo-local project
- **THEN** stdout is one JSON line with `"ok": true`, the code repo's `login`, `main` and `reviewer_config`, and the exit status is 0

#### Scenario: Discovery runs natively
- **WHEN** the project's `VERSION` matches and `<sw> pr discover --repo o/r --branch feat/a` runs
- **THEN** it returns the same normalized PR list and exit status as the frozen script's record

#### Scenario: Identity of a store from the code checkout
- **WHEN** the code project matches the running `sw`, the store checkout has no `openspec/.specwright/VERSION`, and `<sw> pr identity <store toplevel>` runs from the code checkout
- **THEN** stdout is one JSON line with the store's `<owner>/<name>` from its `origin`, and the exit status is 0

#### Scenario: Missing subcommand
- **WHEN** the project's `VERSION` matches and `<sw> pr` runs with no subcommand
- **THEN** it returns the usage JSON listing all nineteen subcommands and exits 2

#### Scenario: Unknown subcommand
- **WHEN** the project's `VERSION` matches and `<sw> pr not-a-command` runs
- **THEN** it returns the same usage JSON and exit 2, without making a GitHub call or writing state

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
- **WHEN** workflow calls need VCS state or plans and fenced reads, with no shipped script on disk
- **THEN** no second `sw` and no script is launched for those operations, and the workflow returns the expected result

#### Scenario: Nested VCS fetch runs the fence in process
- **WHEN** non-Git branch-check with --code invokes native VCS fetch-main for a store that has no `openspec/.specwright/VERSION`
- **THEN** login resolution (when no --login was given) and the fetch run in process in the store's directory as the store's login, no second `sw` is launched, and the result is not `sw_mismatch`

#### Scenario: Fenced read uses one deadline
- **WHEN** pass-plan performs a fenced Git read, credential checks consume part of its existing outer budget, and the Git command then hangs with a descendant
- **THEN** the remaining budget limits execution, the descendant is terminated, and pass-plan reports deadline_exceeded with exit 3 and its existing unknown fields

#### Scenario: Rounds reports an outer read deadline as unreadable
- **WHEN** a rounds remote_contains read exceeds its enclosing deadline
- **THEN** rounds returns ok true with remote_unreadable and the same unpushed and round results as the frozen script's record

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
- **WHEN** on Linux `sw pr rounds` is started with a `--code` argument holding non-UTF-8 bytes in its argument list
- **THEN** the exit status is non-zero, stdout is empty, no credential lookup ran and the tool does not run (native-cli "Arguments sw cannot represent are refused")

#### Scenario: Unbounded VCS calls remain unbounded
- **WHEN** a workflow's VCS state or plan call takes longer than the configured network deadline but completes
- **THEN** the workflow receives its result without a newly introduced deadline_exceeded stop

### Requirement: Feedback records interoperate across the port on UTF-8 paths
Native pass operations SHALL preserve record keys, version-2 JSON, LF encoding, ownership, legacy migration and exclusive publication. Interrupted or foreign-owned state SHALL retain the existing recovery result; the port SHALL NOT start a new pass beside an unreadable record or silently adopt another owner. A state-directory or home value that is not valid UTF-8 SHALL stop the call with `"error": "not_utf8"`, exit 1, before any record is read or written.

#### Scenario: Native plan resumes an existing record
- **WHEN** native pass-plan reads a record the frozen script wrote, kept as recorded bytes captured before the scripts were removed, with equivalent snapshots, local history and owner
- **THEN** the native plan returns the same resume rows, owner state and completion decision, without starting a new pass

#### Scenario: Script plan reads a native record
- **WHEN** native pass-write writes a record
- **THEN** it is UTF-8 with LF line ends under the same record key, its generated owner id, write time, checkout and host are checked for form and against the run, and its intent, owner and state equal the fixture the frozen script read before the scripts were removed, once those generated fields are normalized

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

### Requirement: Settings are read by one YAML parser
Every Specwright command that reads `openspec/specwright.yaml`, from the work tree, a committed ref or GitHub, SHALL read it with one YAML parser and apply the same refusals to every read. A file the reader refuses SHALL give no values: no command decides from part of a file. A refusal SHALL name the 1-based line it found and why. An empty, whitespace-only or comment-only file SHALL read as an empty mapping; any other top level that is not a mapping SHALL be refused.

#### Scenario: The same file read locally and remotely
- **WHEN** main's `openspec/specwright.yaml` is this repository's settings file and `pr-pair.sh context` reads the work-tree copy while `policy` reads the copy on GitHub
- **THEN** both read the same values for `pr.merge`, `pr.merge_method`, `pr.delete_branch` and `pr.reviewers`, and `policy` reports no difference

#### Scenario: A file the parser refuses
- **WHEN** `openspec/specwright.yaml` holds a tab in its indentation on line 7
- **THEN** every reader refuses it naming `line 7`, and none of them reads a value from the lines before or after it

#### Scenario: A comment-only file
- **WHEN** the work-tree settings hold only comments and blank lines and `pr-pair.sh context --code <code>` runs, and main's settings on GitHub are the same file when `policy` reads them
- **THEN** `context` exits 0 with the defaults, and `policy` reads main's policy as `pr.merge: user`

#### Scenario: A top level that is not a mapping
- **WHEN** the settings file holds only `- pr`, a list, in the work tree and at the ready head
- **THEN** `pr-pair.sh context` exits 2 with `bad_setting` naming `line 1`, and `policy` exits 3 with `lookup_failed`

### Requirement: A refused settings file stops each reader
A local read of a settings file the reader refuses SHALL stop the command before any git write, network call or file write: the `pr-pair.sh` subcommands that read the settings and `sw vcs` with `bad_setting` and exit 2, the review runner and the release subcommands with `bad_settings` and exit 1, and `policy`'s remote read with `lookup_failed` and exit 3. `tier` SHALL instead exit 0 with the cheap tier off and a `note` naming the line. A missing file SHALL stay an empty settings file.

#### Scenario: Ship stops on a refused file
- **WHEN** the work-tree settings hold a duplicate `pr:` key on line 30 and ship runs `pr-pair.sh context --code <code>`
- **THEN** it exits 2 with `"error": "bad_setting"` and a `message` naming `openspec/specwright.yaml` and `line 30`, and ship pushes nothing

#### Scenario: A VCS write stops on a refused file
- **WHEN** the settings hold a tab in their indentation and `vcs.sh commit --branch feat/a --message-file m -- a.txt` runs
- **THEN** it exits 2 with `"error": "bad_setting"` naming the line, and no commit is made

#### Scenario: The cheap tier on a refused file
- **WHEN** the settings hold a tab in their indentation and `pr-pair.sh tier --code <code>` runs
- **THEN** it exits 0 with `"cheap_tier": false` and a `note` naming the line

#### Scenario: No settings file
- **WHEN** the code checkout has no `openspec/specwright.yaml` and `pr-pair.sh context --code <code>` runs
- **THEN** it exits 0 with the defaults it gave before this change

### Requirement: Commands that read no settings keep their behaviour
A command that reads no settings today, such as `pr-pair.sh identity`, SHALL keep its behaviour when the settings file is refused, and SHALL NOT start reading the settings in this change.

#### Scenario: Identity on a refused file
- **WHEN** the settings hold a tab in their indentation and `pr-pair.sh identity <code>` runs
- **THEN** it prints the repository identity it printed before this change and exits 0

#### Scenario: Identity on a missing directory
- **WHEN** `pr-pair.sh identity` is given a directory that does not exist
- **THEN** it stops with the error it gave before this change, and names no settings problem

### Requirement: A boolean written yes or no is refused
The reader SHALL refuse any unquoted value `yes` or `no`, in any letter case, anywhere in the file, naming its line and saying to write `true` or `false`. A quoted `'yes'` or `"no"` SHALL be read as a string, and `on`, `off`, `y` and `n` SHALL stay strings as before this change.

#### Scenario: true and false
- **WHEN** the settings hold `review:` with `preship: false` and `pr:` with `react: true`
- **THEN** every reader reads `preship` as false and `react` as true

#### Scenario: A yes boolean
- **WHEN** line 12 of the settings is `  react: yes` and `pr-pair.sh context --code <code>` runs
- **THEN** it exits 2 with `"error": "bad_setting"` and a `message` naming `line 12`, `yes`, `true` and `false`

#### Scenario: A capitalised no
- **WHEN** a settings line is `  enabled: No` under `release:` and `release.sh check` runs
- **THEN** it exits 1 with `error: bad_settings` naming the line, `true` and `false`, and no git call is made

#### Scenario: A quoted yes
- **WHEN** a reviewer's `request` is written `'yes'`
- **THEN** the settings are read and the request comment is the string `yes`

### Requirement: Settings constructs a settings file never needs are refused
The reader SHALL refuse a duplicate key in any mapping, an anchor, an alias, a tag, a non-finite number (`.nan`, `.inf`, `-.inf` in any case YAML reads as one) and a second document, naming the line of the first. Block sequences, flow collections, and quoted, plain and `|`/`>` block scalars SHALL read as YAML 1.2 defines them, including valid YAML the old reader skipped, misread or refused. Messages SHALL show each plain or quoted scalar (quotes kept) and each flow collection as written.

#### Scenario: A non-finite number
- **WHEN** a settings line is `  delete_branch: .inf`
- **THEN** every reader refuses the file naming that line

#### Scenario: A quoted empty value in a message
- **WHEN** the settings hold `merge: agent` and `merge_method: ''` under `pr:` and `pr-pair.sh context --code <code>` runs
- **THEN** it exits 2 with `bad_setting`, and its message names `pr.merge_method: ''`, the value as written

#### Scenario: A duplicate key in a reviewer
- **WHEN** a reviewer under `pr.reviewers` gives `role:` twice, the second time on line 41
- **THEN** every reader refuses the file naming `line 41`

#### Scenario: An alias
- **WHEN** the settings define `&r` on one reviewer and use `*r` for another
- **THEN** every reader refuses the file naming the line of the anchor or the alias

#### Scenario: A block sequence
- **WHEN** `review.order` is written as a block sequence of `codex`, `claude` and `omp`, one `- ` item per line
- **THEN** the review route order is `codex`, `claude`, `omp`, as for `order: [codex, claude, omp]`

### Requirement: A settings value of the wrong shape stops each reader
Wherever a reader expects a mapping (the top level, `pr`, `planning_store`, `github`, `github.review_request`, `cheap_tier`, `review`, `release`, `pr.reviewers`, `planning_store.reviewers`, each reviewer entry and its `report`), a present key with another value SHALL stop the read with that reader's settings error naming the key, never coerced. An absent or null key SHALL keep its default; only an absent or null `planning_store.reviewers` SHALL inherit the code reviewer set.

#### Scenario: A reviewer written as a list
- **WHEN** a reviewer under `pr.reviewers` is written as a block list (`guard:` followed by `- role: required`) and `pr-pair.sh context --code <code>` runs
- **THEN** it exits 2 with `bad_setting` naming `pr.reviewers.guard`, and no reviewer config is written

#### Scenario: A reviewer written as a list, remotely
- **WHEN** main's and the head's settings both hold a reviewer written as a block or flow list, under `pr.reviewers` or `planning_store.reviewers`, and `policy` reads them
- **THEN** `policy` exits 3 with `lookup_failed` naming the key, writes no reviewer config, and authorizes no merge

#### Scenario: A report that is not a mapping
- **WHEN** a reviewer's `report` is `[check, x]`
- **THEN** every reader stops with its settings error naming `report`

#### Scenario: The cheap tier on a wrong shape
- **WHEN** `pr:` is a list and `pr-pair.sh tier --code <code>` runs
- **THEN** it exits 0 with `"cheap_tier": false` and a `note` naming `pr`

#### Scenario: A review section that is not a mapping
- **WHEN** `review:` is written as a block list, a flow list, a scalar or an empty string `''`, and the review runner starts
- **THEN** it exits 1 with `bad_settings` naming `review`, before any reviewer CLI is probed or run

#### Scenario: A release or pr section that is not a mapping
- **WHEN** `release:` or `pr:` is written as a block list, a flow list, a scalar or an empty string `''`, and `release.sh check` runs
- **THEN** it exits 1 with `bad_settings` naming the key, and no git call is made

#### Scenario: A flow list in a message
- **WHEN** the settings hold `reviewers: [a, b]` under `pr:` and `pr-pair.sh context --code <code>` runs
- **THEN** it exits 2 with `bad_setting`, and its message names `pr.reviewers` and `[a, b]`, as written

### Requirement: Deeply nested settings stop without a crash
A settings file nested beyond any depth a reader can hold SHALL be refused with the reader's settings error naming a line, and SHALL never crash a command, print a stack trace or pass as valid.

#### Scenario: Ordinary nesting
- **WHEN** the settings nest `pr.reviewers.<login>.report.check` four levels deep
- **THEN** every reader reads the value

#### Scenario: A local file nested 100,000 levels
- **WHEN** the work-tree settings hold a flow mapping nested 100,000 levels deep and `pr-pair.sh context --code <code>` runs
- **THEN** it exits 2 with `"error": "bad_setting"` naming a line, and no stack trace is printed

#### Scenario: A remote file nested 100,000 levels
- **WHEN** the ready head's settings file on GitHub is nested 100,000 levels deep and `policy` reads it
- **THEN** `policy` exits 3 with `"error": "lookup_failed"` and merges nothing

### Requirement: sw pr ignores an inherited GH_REPO
Every `gh` call that one of the nineteen `sw pr` subcommands makes, account-scoped calls such as `gh api user` and `gh auth token` included, SHALL run with `GH_REPO` removed from its environment. Each repository-scoped call SHALL also name its repository (`--repo` or `repos/<owner>/<name>/...`), so an inherited `GH_REPO` never picks the repository. `sw` does this itself, as the `pr-pair.sh` shim's `unset GH_REPO` did.

#### Scenario: GH_REPO not set
- **WHEN** `GH_REPO` is not set and `<sw> pr discover --repo o/store --branch feat/a` runs
- **THEN** every `gh` call names `o/store` and the PR list is that repository's

#### Scenario: Inherited GH_REPO names the code repo
- **WHEN** `GH_REPO` is `o/code` and `<sw> --project <code> pr discover --repo o/store --branch feat/a` runs in the store
- **THEN** every repository-scoped `gh` call targets `o/store`, no `gh` call sees `GH_REPO`, the account lookups (`gh auth token`, `gh api user`) included, and no PR of `o/code` is listed

### Requirement: Cleanup commands name the code project
Every `sw` command that `sw pr cleanup-plan` prints for a repository, the branch check and the fenced pull included, SHALL start with the running `sw`'s absolute path and a leading `--project <code>`, keep that repository as its working directory and keep every other argument unchanged.

#### Scenario: Store cleanup after merge
- **WHEN** a store-backed change's PRs merged and `<sw> pr cleanup-plan` runs
- **THEN** the store's branch-check and fenced pull commands each start with the running `sw`'s path and `--project <code>`, and their `cwd` is the store

#### Scenario: Store with no VERSION runs a printed command
- **WHEN** a printed store branch-check command runs in a store that has no `openspec/.specwright/VERSION`
- **THEN** `sw` checks the code checkout's `VERSION`, the check runs in the store, and the result is not `sw_mismatch`

### Requirement: Windows record replacement retries a transient refusal
On Windows, a failed feedback record replace made under the record's lock SHALL be retried at most 5 times, each after a requested 20 ms pause (not a wall-clock deadline), while its temporary source is known to exist. Otherwise the first replacement error SHALL be reported unchanged. The lock create and publication SHALL NOT be retried.

#### Scenario: A refusal that clears within the retry window
- **WHEN** on Windows the first replace fails and a retry succeeds while the temporary source exists
- **THEN** the call writes the record and reports success

#### Scenario: A refusal that persists
- **WHEN** on Windows all 6 attempts fail
- **THEN** the call reports the first replacement error, not record_busy, the failed replaces leave the record as they found it, and the call tries to remove its temporary file; a failure of that removal does not replace the first error

#### Scenario: The temporary source is gone after the first attempt
- **WHEN** the first replace fails and the temporary source no longer exists
- **THEN** no retry is made and that error is reported

#### Scenario: The temporary source disappears during a pause
- **WHEN** on Windows the temporary source is removed during a pause between attempts
- **THEN** no further attempt is made and the first error is reported

#### Scenario: Other platforms
- **WHEN** on a platform other than Windows the record replace fails
- **THEN** the error is reported at once, with no retry

#### Scenario: The lock create and publication are not retried
- **WHEN** a lock create or publication's create fails
- **THEN** the error is reported at once, as before, with no retry

#### Scenario: Concurrent adoption on Windows
- **WHEN** several calls adopt one freshly written record at once on Windows, all from its valid current owner, each to its own new owner different from that one, no publication or deletion of the record runs at the same time, and every refusal clears within the retries
- **THEN** every call reports a result, exactly one succeeds, every other reports record_busy or not_owner, and the record equals the record before the race except for the owner, which is the one that succeeded

### Requirement: A PR call's new helper refusal keeps its exit with a fixed diagnostic
On Windows, when a `sw pr reply` or `sw pr snapshot` `gh` call is refused by a launch check this change adds (such as a helper line over the limit), the command SHALL report `cannot start the helper: its command line is too long` where the OS text of the failed start was, with the same exit. An older check SHALL keep its diagnostic (`unrepresentable command line` or `unsafe batch argument`). Where this differs from the two PR parity requirements, it SHALL take precedence.

#### Scenario: A reaction whose gh line fits only without the helper
- **WHEN** on Windows `sw pr reply ... react` reaches its pending check with a `gh` line that fits alone but not behind the helper
- **THEN** neither the helper nor `gh` starts, the fixed diagnostic is relayed on stderr, and the reply exits 127 as before this change

#### Scenario: A snapshot query that fits only without the helper
- **WHEN** on Windows a `sw pr snapshot` GraphQL `gh` line fits alone but not behind the helper
- **THEN** neither the helper nor `gh` starts, and the snapshot relays the fixed diagnostic where it relayed the OS text, with the same exit

#### Scenario: A PR call refused by an older check
- **WHEN** on Windows a reply or snapshot `gh` line is over 32,767 visible units as given or once `gh` resolves to a native executable
- **THEN** the command reports `unrepresentable command line` as before this change; a resolved line of exactly 32,767 units is a new refusal and reports the fixed diagnostic

#### Scenario: A PR call whose batch payload is too long
- **WHEN** on Windows `gh` resolves to a `.cmd` shim and the call's batch payload is over 8,191 units
- **THEN** the command reports `unsafe batch argument` as before this change

### Requirement: Fixed snapshot defects are exceptions to the scripts' contract
The three requirements below fix defects `sw pr snapshot` kept from `pr-snapshot.sh`. Where they differ from "sw pr snapshot and sw pr reply keep the scripts' contracts" or from "PR snapshots and replies run in the project's sw", they SHALL take precedence for `sw pr snapshot` only. Every other output, except the new helper refusal above, still follows both requirements and the frozen oracle records.

#### Scenario: A fixed case differs from its record
- **WHEN** the parity eval runs a case whose output one of these fixes changes
- **THEN** that case is listed as a difference and its new outcome is asserted by its own test, while the frozen record is left unchanged

#### Scenario: An unaffected case still matches its record
- **WHEN** the parity eval runs any other snapshot case
- **THEN** its exit status, stdout and stderr match the frozen record as before

### Requirement: sw pr snapshot reads --timeout as decimal seconds
`sw pr snapshot --timeout` SHALL take a whole number of seconds written in ASCII decimal digits, from 0 to 9223372036854775807, so every digit string accepted now still is; leading zeros SHALL be read as decimal. The value SHALL be checked when the options are read. Any other value SHALL be a usage error: exit 2, a stderr line naming `--timeout` and the value, and no `gh` call.

#### Scenario: A leading zero
- **WHEN** `sw pr snapshot 12 --wait --until attention --timeout 08 --interval 2` runs under a controlled clock, with polls that take no time and nothing changing
- **THEN** the wake is `timeout` once the clock reaches 8 seconds, after the polls at 2, 4, 6 and 8 seconds, with no error on stderr

#### Scenario: A value that is not a number
- **WHEN** `sw pr snapshot 12 --wait --until attention --timeout abc` runs, or the value is `+5`, `-3` or `0x10`
- **THEN** it exits 2, stderr names `--timeout` and the value, no wake document is printed and no `gh` call is made

#### Scenario: A value out of range
- **WHEN** `sw pr snapshot 12 --wait --until attention --timeout 9223372036854775808` runs, or the value is `99999999999999999999`
- **THEN** it exits 2 naming `--timeout` and the value, before any `gh` call

#### Scenario: Large values stay accepted
- **WHEN** `sw pr snapshot 12 --wait --until attention --timeout 2147483648 --interval 2` runs under a controlled clock, with nothing changing, and again with `--timeout 9223372036854775807`
- **THEN** neither reports a usage error, and each runs its first poll

### Requirement: sw pr snapshot names a material file it cannot write
When `sw pr snapshot` cannot write the reviewer evaluator's material file, the poll SHALL fail with exit 1 and a stderr line naming the file and the operating system's reason, where it now fails with nothing on stderr.

#### Scenario: The material file cannot be written
- **WHEN** the write of the snapshot's material temp file fails
- **THEN** the poll fails with exit 1 and stderr names that path and the reason

#### Scenario: Material file written
- **WHEN** the material file can be written
- **THEN** nothing about it is printed on stderr

### Requirement: Snapshot logs keep the order their output arrived in
`sw pr snapshot --logs` SHALL read the failed job's log call with its stdout and stderr merged in the order their output reached `sw`, then keep the last 80 lines of that merged output. Output written on one stream after a pause in which the other stream's earlier output was delivered SHALL follow that output; writes close together MAY interleave in either order, even inside a line. The merged call SHALL accept at most 32 MiB from both streams together.

#### Scenario: stderr that arrives partway through the log
- **WHEN** the failed-log call's output reaches `sw` as 50 stdout lines, then one stderr line, then 50 more stdout lines, each delivered after the one before it
- **THEN** the merged output has 101 lines, the tail is its last 80, the stderr line is line 30 of the tail, and stdout line 100 is its last line

#### Scenario: A line split across chunks
- **WHEN** a stdout line reaches `sw` in two chunks and a stderr chunk arrives between them
- **THEN** the merged output holds the stderr bytes between the two parts of that line, which may split a UTF-8 sequence, and the snapshot still exits as it would without the split

#### Scenario: The snapshot keeps the merged order
- **WHEN** the failed-log call's merged output holds a stderr line between two runs of stdout lines, so that separate stdout and stderr buffers would put it last
- **THEN** the snapshot's log tail shows the stderr line between those runs, not at the end

#### Scenario: A long log through the helper
- **WHEN** the failed-log call runs through the bounded helper and writes 101 numbered lines, `line 1` to `line 101`, to stdout
- **THEN** the snapshot's log tail is `line 22` to `line 101`, in order

#### Scenario: Helper protocol bytes never reach the log
- **WHEN** the failed-log call runs through the bounded helper
- **THEN** the merged output holds what the target wrote and never the helper's startup frames

#### Scenario: The log call fails to start
- **WHEN** the failed-log call's target cannot start, or the call is refused before any start
- **THEN** the snapshot shows that call's start-failure text in place of the log, as it does now

#### Scenario: Two streams that fit alone but not together
- **WHEN** the failed-log call writes 20 MiB on stdout and 20 MiB on stderr
- **THEN** the first chunk past 32 MiB is rejected, the call is stopped, no partial log is kept, and the snapshot shows the `response_too_large` limit line in place of the log

#### Scenario: The log call passes a bound
- **WHEN** the failed-log call passes its deadline or output bound
- **THEN** the snapshot shows the limit line in place of the log, as before
