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
`pr-pair.sh` SHALL report any unexpected exception as one JSON line on stdout with `"ok": false`, `"error": "internal_error"` and a `message` naming the exception type, and SHALL exit 1. Existing structured stops SHALL keep their own error codes and exit statuses.

#### Scenario: Filesystem error during pass write
- **WHEN** `pass write` runs and the record's parent directory path is an existing regular file
- **THEN** stdout is a single JSON line with `"error": "internal_error"`, the exit status is 1, and stderr contains no `Traceback`

#### Scenario: Existing structured stop
- **WHEN** `pass write` runs for a round whose record already exists
- **THEN** it reports the same error code and exit status as before this change

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
