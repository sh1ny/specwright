# pr-script-runtime Specification

## Purpose
Keeps the PR scripts working on every Python version they accept, keeps their failures machine-readable, and makes their prerequisites visible before the PR flow starts.

## Requirements

### Requirement: Pass records can be written on Python 3.8
`pr-pair.sh pass write` SHALL write its feedback-pass record on every Python version the script accepts (3.8 and later). The record SHALL be UTF-8 JSON with LF line endings, replaced atomically.

#### Scenario: Pass write on Python 3.8
- **WHEN** the only Python on `PATH` is 3.8 and a valid store-backed `pass write` runs
- **THEN** the script exits 0 with `"ok": true`, and the record file exists, parses as JSON and contains no CR bytes

#### Scenario: No Python 3.8 available to the test
- **WHEN** the minimum-runtime test finds no Python 3.8 interpreter
- **THEN** the test is reported as skipped, naming the missing interpreter, not as passed, and an always-run check still confirms that the script's embedded Python passes no `newline=` argument to `write_text` or `read_text`

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
The README prerequisites and install Step 1 SHALL list `bash` with a POSIX userland, `git` and Python 3.8+ as core requirements (the review scripts run every design and pre-ship review), and `gh` 2.40+ as a requirement of the PR skills. Install SHALL check each one. A missing core requirement SHALL stop the install. A missing PR requirement SHALL be reported as `PR workflow not ready: <missing>` without blocking the install. `specwright-pr` SHALL state the same script dependencies.

#### Scenario: All prerequisites present
- **WHEN** install runs where bash, git, gh 2.45 and Python 3.11 are available
- **THEN** Step 1 passes and the final report shows no `PR workflow not ready` line

#### Scenario: Python missing
- **WHEN** install runs where neither `python3` nor `python` reports version 3.8 or later
- **THEN** the install stops at Step 1 and tells the user to install Python 3.8 or later

#### Scenario: gh missing
- **WHEN** install runs where `gh` is missing or older than 2.40, and every core requirement is present
- **THEN** the install completes and its report includes `PR workflow not ready: gh 2.40+`

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
`pr-snapshot.sh` and `pr-reply.sh` SHALL keep their paths, arguments and output contracts, and SHALL carry out every call by resolving the project's `sw` with the shared resolver and running `sw pr snapshot` and `sw pr reply`. The project is found from the current directory, up to the first directory holding a `.git` entry, with no Git command. Their stdout, stderr and exit status SHALL be those of `sw`. No other implementation SHALL remain in either script.

#### Scenario: Snapshot with a matching sw
- **WHEN** a matching `sw` is installed and `as.sh sh1ny bash pr-snapshot.sh 12 --repo o/r` runs against a PR with one unresolved thread
- **THEN** stdout is one JSON line listing that thread with its `id`, `rev` and body, and the exit status is 0

#### Scenario: Reply with a matching sw
- **WHEN** a matching `sw` is installed and `pr-reply.sh 12 thread <thread-id> <root-id> body.md --resolve --repo o/r` runs
- **THEN** one reply is posted whose body is the file's bytes followed by `<!-- specwright:handled <thread-id> resolve -->`, the thread is resolved, and the exit status is 0

#### Scenario: A refusal keeps its exit status
- **WHEN** `pr-reply.sh 12 comment <id> missing.md --repo o/r` runs and `missing.md` does not exist
- **THEN** the exit status is 4, stderr names the body file, and no `gh` call was made, as before this change

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

### Requirement: pr-pair settings and policy subcommands run in the project's sw
`pr-pair.sh identity`, `vcs`, `tier`, `context` and `policy` SHALL keep their path and arguments, and SHALL carry out each call by resolving the project's `sw` with the shared resolver and running `sw pr <subcommand>`, with stdout, stderr and exit status those of `sw`. The other subcommands, and a missing or unknown one, SHALL run as before this change.

#### Scenario: Context with a matching sw
- **WHEN** a matching `sw` is installed and `pr-pair.sh context --code <code>` runs in a repo-local project
- **THEN** stdout is one JSON line with `"ok": true`, the code repo's `login`, `main` and `reviewer_config`, and the exit status is 0, as before this change

#### Scenario: An unported subcommand keeps the script
- **WHEN** a matching `sw` is installed and `pr-pair.sh discover --repo o/r --branch feat/a` runs
- **THEN** the answer is the one the script gave before this change, and `sw pr discover` was not run

#### Scenario: Identity of a store from the code checkout
- **WHEN** a matching `sw` is installed for the code project, the store checkout has no `openspec/.specwright/VERSION`, and `pr-pair.sh identity <store toplevel>` runs from the code checkout
- **THEN** stdout is one JSON line with the store's `<owner>/<name>` from its `origin`, and the exit status is 0, as before this change

#### Scenario: Missing subcommand
- **WHEN** `pr-pair.sh` runs with no arguments
- **THEN** it exits 2 with the usage line that lists all 19 subcommands, as before this change

### Requirement: A missing or mismatched sw stops the ported pr-pair subcommands
When the resolver stops, `pr-pair.sh identity`, `vcs`, `tier`, `context` and `policy` SHALL print one JSON line on stdout with `"ok": false`, `"error": "sw_missing"` and a `message` that starts with `sw missing or mismatched: rerun the install prompt` and holds the resolver's detail, and exit 1. They SHALL make no `gh` call, write no reviewer config, and never fall back to the embedded Python or another `sw`.

#### Scenario: Policy with no sw
- **WHEN** no matching `sw` is installed and `pr-pair.sh policy --repo o/r --head <sha> --snapshot code=s.json` runs
- **THEN** the exit status is 1, stdout is one JSON line with `"error": "sw_missing"`, and no `gh` call was made

#### Scenario: An unported subcommand needs no sw
- **WHEN** no matching `sw` is installed and `pr-pair.sh branch-check --dir <d> --branch feat/a --main main` runs
- **THEN** it answers as before this change

#### Scenario: No Python
- **WHEN** no `python3` or `python` 3.8+ is on `PATH` and `pr-pair.sh context --code <code>` runs
- **THEN** it exits 2 with its `no_python` JSON line, as before this change, and `sw` did not run

### Requirement: The ported pr-pair subcommands keep the script's contracts
`sw pr identity`, `vcs`, `tier`, `context` and `policy`, run through the shim, SHALL accept the arguments `pr-pair.sh` accepted and SHALL print a JSON line with the same field names and values and exit with the same status for the same settings files, repositories and GitHub answers. That covers the settings problems, the reviewer-config bytes (apart from `"format": 2`), path and digest, the GitButler pin, and the policy checks.

#### Scenario: Policy's remote settings read is strict
- **WHEN** `policy` reads a settings file from the remote and it holds a construct the strict reader cannot read whole
- **THEN** `policy` stops with `lookup_failed` and merges nothing, and never decides from a best-effort parse

#### Scenario: Git Bash path forms
- **WHEN** on Windows a subcommand is given a directory or snapshot file as a Git Bash path such as `/c/work/repo`
- **THEN** it reads the same repository or file as with `C:/work/repo`, and a path it reports is in the `C:/` form

#### Scenario: Unchanged black-box evals pass on sw
- **WHEN** the `evals/pr-pair` and `evals/vcs` tests that run these five subcommands run in CI on Linux, Windows and macOS against the `sw` built from the tree
- **THEN** every test passes with its assertions unchanged from before this change, apart from the format migration (D10): the expected `"format"` value, the reviewer-config digests and content-addressed paths derived from it, and the format refused by the config check; the regex dialect cases (pr-evidence); and assertions on free text, which check its prefix instead (see the message-text requirement). Every other field, error code and exit status is compared exactly

#### Scenario: Differential run against the frozen script
- **WHEN** the parity eval runs a case of each subcommand through the frozen copy of `pr-pair.sh` and through the shim, against the same repositories and fake-gh state
- **THEN** both exit with the same status, make the same `gh` calls, and print stderr with the same lines up to each line's prefix. Their stdout is the same JSON line, apart from free text compared by its prefix and except that each `reviewer_config` digest and config path names that side's own file. Each side writes a reviewer config whose bytes are checked exactly on their own: the frozen script's with `"format": 1`, the shim's the same with `"format": 2`. Each file is named by the digest of its own bytes, and each digest field in stdout equals that digest

#### Scenario: A malformed settings file names its line
- **WHEN** `openspec/specwright.yaml` holds a tab in its indentation on line 7 and `pr-pair.sh context --code <code>` runs
- **THEN** `settings_problem` starts with `line 7:` as before this change, and the exit status is the same

#### Scenario: Settings not pinned on GitButler
- **WHEN** `vcs` is `gitbutler`, the work-tree `openspec/specwright.yaml` differs from the one committed on `feat/a`, and `pr-pair.sh context --code <code> --branch feat/a` runs
- **THEN** it exits 1 with `"error": "settings_not_pinned"`, naming the file and the ref, as before this change

### Requirement: Message text of the ported subcommands may be reworded
In the output of `sw pr identity`, `vcs`, `tier`, `context`, `policy` and `reviewers`, free text SHALL keep its prefix and MAY be worded differently from the script's. Free text is the `message` field, `settings_problem` after its `line N:` prefix, and each stderr line after its `pr-pair.sh:` or `reviewers.py:` prefix. Every other field, error code and exit status SHALL stay as the script had it.

#### Scenario: A reworded stop keeps its code
- **WHEN** `pr-pair.sh policy` reads a default-branch settings file whose content is not valid base64
- **THEN** stdout has `"error": "lookup_failed"` and the exit status is 3, as before this change, and `message` starts with `merge policy unknown: unreadable openspec/specwright.yaml at <ref>:`

### Requirement: sw pr reviewers keeps the evaluator's contract
`sw pr reviewers --check-config FILE` and `sw pr reviewers --config FILE --material FILE --head OID` SHALL print the same output fields, one stderr line prefixed `reviewers.py:` where `reviewers.py` printed one, naming the same reviewer and key, and exit with the same status as `reviewers.py` did, except where a report pattern compiles differently or the config's format is not 2 (see pr-evidence).

#### Scenario: Unchanged evaluator tests
- **WHEN** `evals/pr-pair/test_reviewers.py` runs against `sw pr reviewers` in CI on Linux, Windows and macOS
- **THEN** every test passes with its assertions unchanged from before this change, apart from the format migration (D10): the expected `"format"` value, the reviewer-config digests and content-addressed paths derived from it, and the format refused by the config check; the regex dialect cases (pr-evidence); and assertions on free text, which check its prefix instead (see the message-text requirement). Every other field, error code and exit status is compared exactly

#### Scenario: Material that is not its head
- **WHEN** `sw pr reviewers --config cfg.json --material m.json --head <oid>` runs and `m.json` is for another head
- **THEN** it exits 1 with nothing on stdout, as `reviewers.py` did

### Requirement: Snapshots evaluate reviewers through sw
`sw pr snapshot` SHALL check the `--reviewer-config` file before any `gh` call, and SHALL decide reviewer states by running its own binary as `sw pr reviewers`, under the deadline, byte bound, limit line and temp-file rules `reviewers.py` ran under, starting no Python evaluator. Only the existing `no_python` version check stays until `native-cli-retire-scripts`.

#### Scenario: Reviewer states decided in sw
- **WHEN** `pr-snapshot.sh 12 --reviewer-config cfg.json` runs and `cfg.json` lists `chatgpt-codex-connector[bot]` as a reviewer that has posted its report
- **THEN** that login's `reviewers` entry has the state `reviewers.py` decided before this change, `reviewer_config` holds the file's digest, and no `reviewers.py` process was started

#### Scenario: A pattern that backtracks past the deadline
- **WHEN** a reviewer's `report.ignore` backtracks on a comment body for longer than the evaluator's deadline
- **THEN** the evaluation is stopped at the deadline, stderr holds the limit line naming `reviewers.py` as before this change, the poll fails, and no evaluator process or material file is left

#### Scenario: Bad reviewer config
- **WHEN** `cfg.json` is not valid JSON and `pr-snapshot.sh 12 --reviewer-config cfg.json` runs
- **THEN** the exit status is 2, stderr holds one line prefixed `reviewers.py:` that says the file is not valid JSON, and no `gh` call was made
