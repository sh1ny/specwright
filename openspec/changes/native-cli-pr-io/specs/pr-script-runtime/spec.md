# Spec Delta

## ADDED Requirements

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
`sw pr snapshot` and `sw pr reply`, run through the scripts' shims, SHALL accept the arguments the scripts accepted before this change and SHALL print the same bytes on stdout, the same messages on stderr and the same exit statuses for the same GitHub answers: the snapshot line, `--full`, the `--wait` wake document, markers, revision checks, reactions and resolutions included.

#### Scenario: Unchanged black-box evals pass on sw
- **WHEN** `evals/pr-pair/test_pr_snapshot.py`, `test_pr_reply.py` and every other eval that runs the two scripts run in CI on Linux, Windows and macOS against the `sw` built from the tree
- **THEN** every test passes with its assertions unchanged from before this change

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
- **THEN** `sw` picks the owner by comparing the nonces as bytes, the old script compares them by the locale's collation, and the two may each see themselves as owner. This is accepted and is not a parity failure

#### Scenario: State directory cannot be created
- **WHEN** `SPECWRIGHT_STATE_DIR` names a path under a regular file and `pr-snapshot.sh 12 --wait` runs
- **THEN** stderr says `pr-snapshot: cannot create the watch state directory; ownership is off for PR 12 (this watcher polls unowned)` and the watch goes on unowned

### Requirement: Reviewer evaluation stays in reviewers.py until it is ported
`sw pr snapshot` SHALL check the `--reviewer-config` file with `reviewers.py --check-config` before any `gh` call, and SHALL decide reviewer states by running `reviewers.py` from the scripts directory of the `pr-snapshot.sh` that started it, under the same deadline and the same temp-file rules as before this change.

#### Scenario: Reviewer states come from reviewers.py
- **WHEN** `pr-snapshot.sh 12 --reviewer-config cfg.json` runs and `cfg.json` lists `chatgpt-codex-connector[bot]` as a reviewer that has posted its report
- **THEN** the snapshot's `reviewers` entry for that login has the state `reviewers.py` decided, and `reviewer_config` holds the file's digest

#### Scenario: Bad reviewer config
- **WHEN** `cfg.json` is not valid JSON
- **THEN** the exit status is 2, stderr holds the one line `reviewers.py --check-config` printed, and no `gh` call was made

#### Scenario: The evaluator's material file is removed
- **WHEN** the reviewer evaluation is stopped at its deadline
- **THEN** the snapshot fails as before this change and no material file is left in the system temp directory
