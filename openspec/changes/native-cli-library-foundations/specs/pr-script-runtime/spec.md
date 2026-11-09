## ADDED Requirements

### Requirement: Paginated GitHub lists read every page or decide nothing
A list read that spans pages SHALL use `gh api --paginate --slurp`, flatten the returned array of pages into one list in page order, and on any response other than an array of arrays SHALL report the read as unknown. An unknown read SHALL NOT lead to a GitHub mutation.

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

## MODIFIED Requirements

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

### Requirement: The ported pr-pair subcommands keep the script's contracts
`sw pr identity`, `vcs`, `tier`, `context` and `policy`, run through the shim, SHALL accept the argument forms shipped callers use and SHALL print a JSON line with the same parsed field names and values and exit with the same status for the same settings files, repositories and GitHub answers. That covers the settings problems, the reviewer-config bytes (apart from `"format": 2`), path and digest, the GitButler pin, and the policy checks.

#### Scenario: Policy's remote settings read is strict
- **WHEN** `policy` reads a settings file from the remote and it holds a construct the strict reader cannot read whole
- **THEN** `policy` stops with `lookup_failed` and merges nothing, and never decides from a best-effort parse

#### Scenario: Git Bash path forms
- **WHEN** on Windows a subcommand is given a directory or snapshot file as a Git Bash path such as `/c/work/repo`
- **THEN** it reads the same repository or file as with `C:/work/repo`, and a path it reports is in the `C:/` form

#### Scenario: Unchanged black-box evals pass on sw
- **WHEN** the `evals/pr-pair` and `evals/vcs` tests that run these five subcommands run in CI on Linux, Windows and macOS against the `sw` built from the tree
- **THEN** every test passes with its assertions unchanged from before this change, apart from the format migration (D10): the expected `"format"` value, the reviewer-config digests and content-addressed paths derived from it, and the format refused by the config check; the regex dialect cases (pr-evidence); assertions on free text, which check its prefix instead (see the message-text requirement); and assertions on stdout bytes, which compare the parsed value instead. Every other field, error code and exit status is compared exactly

#### Scenario: Differential run against the frozen script
- **WHEN** the parity eval runs a case of each subcommand through the frozen copy of `pr-pair.sh` and through the shim, against the same repositories and fake-gh state
- **THEN** both exit with the same status, make the same `gh` calls, and print stderr with the same lines up to each line's prefix. Their stdout parses to the same JSON value, apart from free text compared by its prefix and except that each `reviewer_config` digest and config path names that side's own file. Each side writes a reviewer config whose bytes are checked exactly on their own: the frozen script's with `"format": 1`, the shim's the same with `"format": 2`. Each file is named by the digest of its own bytes, and each digest field in stdout equals that digest

#### Scenario: A malformed settings file names its line
- **WHEN** `openspec/specwright.yaml` holds a tab in its indentation on line 7 and `pr-pair.sh context --code <code>` runs
- **THEN** `settings_problem` starts with `line 7:` as before this change, and the exit status is the same

#### Scenario: Settings not pinned on GitButler
- **WHEN** `vcs` is `gitbutler`, the work-tree `openspec/specwright.yaml` differs from the one committed on `feat/a`, and `pr-pair.sh context --code <code> --branch feat/a` runs
- **THEN** it exits 1 with `"error": "settings_not_pinned"`, naming the file and the ref, as before this change

### Requirement: sw pr reviewers keeps the evaluator's contract
`sw pr reviewers --check-config FILE` and `sw pr reviewers --config FILE --material FILE --head OID` SHALL print the same parsed output fields, one stderr line prefixed `reviewers.py:` where `reviewers.py` printed one, naming the same reviewer and key, and exit with the same status as `reviewers.py` did, except where a report pattern compiles differently, the config's format is not 2 (see pr-evidence), or the input holds a form JSON does not allow.

#### Scenario: Unchanged evaluator tests
- **WHEN** `evals/pr-pair/test_reviewers.py` runs against `sw pr reviewers` in CI on Linux, Windows and macOS
- **THEN** every test passes with its assertions unchanged from before this change, apart from the format migration (D10): the expected `"format"` value, the reviewer-config digests and content-addressed paths derived from it, and the format refused by the config check; the regex dialect cases (pr-evidence); assertions on free text, which check its prefix instead (see the message-text requirement); and assertions on stdout bytes, which compare the parsed value instead. Every other field, error code and exit status is compared exactly

#### Scenario: Material that is not its head
- **WHEN** `sw pr reviewers --config cfg.json --material m.json --head <oid>` runs and `m.json` is for another head
- **THEN** it exits 1 with nothing on stdout, as `reviewers.py` did
