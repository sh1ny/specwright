# Spec Delta

## ADDED Requirements

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

## MODIFIED Requirements

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

## REMOVED Requirements

### Requirement: Reviewer evaluation stays in reviewers.py until it is ported
**Reason**: `reviewers.py` is ported to `sw pr reviewers` and removed; `sw pr snapshot` runs it as a bounded `sw pr reviewers` child.
**Migration**: None for callers of `pr-snapshot.sh`. Anything that ran `reviewers.py` directly runs `sw pr reviewers` with the same arguments.
