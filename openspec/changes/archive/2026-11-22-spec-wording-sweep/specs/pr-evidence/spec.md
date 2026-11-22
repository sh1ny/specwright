# Spec Delta

## MODIFIED Requirements

### Requirement: A reply is posted only for the revision that was judged
`sw pr reply` SHALL accept the revision of the item being answered. Given one, it SHALL read the item from GitHub before it posts a reply or resolves a thread, and SHALL post nothing and resolve nothing when the item's current revision differs (exit 5, naming both revisions) or cannot be read (exit 3). Without a revision it SHALL behave as in 0.1.10.

#### Scenario: Item unchanged
- **WHEN** feedback answers a thread with the `rev` from its snapshot and nobody has changed the thread since
- **THEN** the reply is posted, the thread is resolved when `--resolve` was given, and the exit status is 0

#### Scenario: Reviewer edited the finding during the fix
- **WHEN** the reviewer edits the thread's comment after the snapshot was taken, and feedback then answers it with the snapshot's `rev`
- **THEN** no reply is posted, the thread stays unresolved, no reaction is added, and the exit status is 5 with the judged and the current revision on stderr

#### Scenario: Item cannot be read
- **WHEN** a revision is given and the item cannot be read from GitHub
- **THEN** nothing is posted or resolved, and the command exits 3

#### Scenario: Reply from an older session
- **WHEN** `sw pr reply` is called without a revision
- **THEN** it posts and resolves as before, with no re-read

### Requirement: Clipped items are read in full before they are judged
`sw pr snapshot --full <item id>` SHALL print the item's full body and revision as one JSON line. Feedback SHALL read the full body of every clipped item before judging, answering or dropping it, and SHALL hand over to the user when it cannot be read.

#### Scenario: Finding after the cut
- **WHEN** a review's actionable finding sits after its 1200th character
- **THEN** feedback reads the item with `--full` and judges it on the full body, not as a summary to drop

#### Scenario: Full body cannot be read
- **WHEN** `--full` exits non-zero for a clipped item
- **THEN** feedback neither drops nor answers that item, and reports it to the user as needing a manual read

#### Scenario: Unknown item id
- **WHEN** `--full` is given an id that names no comment or review on GitHub
- **THEN** it prints `{"ok": false, "error": "not_found"}` and exits 1

### Requirement: A reply is never posted without its body
`sw pr reply` SHALL check that the body file of a `thread` or `comment` reply exists, is readable and is not empty, and that the reply with its marker was written in full, before any GitHub call. When a check fails, it SHALL exit non-zero, name the body file on stderr, and post, resolve and react to nothing.

#### Scenario: Body file present
- **WHEN** feedback answers a thread with a non-empty, readable body file
- **THEN** the reply holds that body followed by the handled marker, and the exit status is 0

#### Scenario: Body file missing
- **WHEN** `sw pr reply` is called with a body file path that does not exist
- **THEN** the exit status is non-zero, stderr names the path, and no GitHub request is made

#### Scenario: Body file empty
- **WHEN** the body file exists and is empty
- **THEN** the exit status is non-zero, stderr names the path, and no GitHub request is made

#### Scenario: Body file unreadable
- **WHEN** the body file exists but cannot be read
- **THEN** the exit status is non-zero, stderr names the path, and no GitHub request is made

### Requirement: A bad report rule stops the snapshot
An unknown `report` key, a pattern that does not compile, or a `sha_pattern` with no capture group SHALL stop the snapshot with exit 2 naming the reviewer and the key, before any `gh` call.

#### Scenario: Bad rule
- **WHEN** `report.sha_pattern` is `([0-9a-f`
- **THEN** `sw pr snapshot` exits 2 with a message naming the reviewer and `sha_pattern`, and prints no snapshot

#### Scenario: Unknown key
- **WHEN** `report` sets `checks: Bot Code Review`
- **THEN** `sw pr snapshot` exits 2 with a message naming the reviewer and `checks`

#### Scenario: Python-only syntax is refused
- **WHEN** `report.sha_pattern` is `\Areviewed (?P<sha>[0-9a-f]{7,40})`, or `report.ignore` is `(?i)in progress`
- **THEN** `sw pr snapshot` exits 2 with a message naming the reviewer and the key, before any `gh` call, and no reviewer state is decided with that pattern

#### Scenario: Sha pattern without a capture group
- **WHEN** `report.sha_pattern` is `reviewed [0-9a-f]+`
- **THEN** `sw pr snapshot` exits 2 with a message naming the reviewer and `sha_pattern`

### Requirement: Reviewer settings reach the snapshot as a file
`sw pr snapshot` SHALL read reviewers only from `--reviewer-config <file>`, a JSON file that `sw pr context` and `policy` write from the settings they read and whose path they print. `--reviewer` SHALL exit 2 naming `--reviewer-config`. A config file that is missing, unreadable or not the expected JSON SHALL exit 2. Both SHALL happen before any `gh` call. When the state directory is unwritable, the config file SHALL be written under the system temp directory instead.

#### Scenario: Policy writes main's reviewers
- **WHEN** `policy` reads main's `pr.reviewers` with a `report.check` for one reviewer, and watch starts its wait with the printed `reviewer_config.main.code` path
- **THEN** the snapshot applies that reviewer's `check` rule, and no reviewer from the local checkout's settings appears in it

#### Scenario: Old flag
- **WHEN** a snapshot runs with `--reviewer some-bot:required:1200`
- **THEN** it exits 2 with a message naming `--reviewer-config`, and makes no `gh` call

#### Scenario: Missing file
- **WHEN** `--reviewer-config` names a file that does not exist
- **THEN** the snapshot exits 2 naming the file, and makes no `gh` call

#### Scenario: Unwritable state directory
- **WHEN** the state directory is unwritable
- **THEN** `context` still prints a `reviewer_config` path, and the snapshot reports reviewers

#### Scenario: Regex characters in a rule
- **WHEN** a reviewer's `report.sha_pattern` contains backticks, backslashes, quotes and colons, written single-quoted in the settings
- **THEN** the pattern in the config file is byte-for-byte the value read from the settings, and the snapshot matches with it

### Requirement: A snapshot names the reviewer rules it used
The snapshot SHALL carry `reviewer_config`: the SHA-256 digest of the config file it ran with. `policy` SHALL count a set's required reviewers as reported only when that digest equals the digest of the config it writes for the set, and SHALL otherwise report `rules_mismatch` for the set. The config SHALL carry `"format": 2`, naming the JavaScript pattern dialect, and the evaluator SHALL refuse any other format, so a snapshot decided under the Python dialect (`"format": 1`) never matches.

#### Scenario: Wait started with the work tree's rules
- **WHEN** main gives required `rev-bot` a `marker` rule, the wait ran with a config from the work tree where `rev-bot` has no `report`, and the snapshot reports `rev-bot` `reported` `by: output`
- **THEN** `policy` reports `rules_mismatch` for main's set and not `ok`, and no merge request is sent

#### Scenario: Same rules
- **WHEN** the work tree's reviewer settings equal main's and the snapshot reports every required reviewer `reported`
- **THEN** the digests are equal, and `policy` reports `ok` for main's set

#### Scenario: Snapshot from before the dialect change
- **WHEN** main sets required `rev-bot` with `report.ignore: '\W'`, the work tree's settings are the same, and the saved snapshot reports `rev-bot` `reported` with the digest of the `"format": 1` config the Python evaluator ran with
- **THEN** `policy` reports `rules_mismatch` for main's set and not `ok`, and no merge request is sent

#### Scenario: Config of the earlier format
- **WHEN** `sw pr reviewers --check-config cfg.json` runs and `cfg.json` holds `"format": 1`
- **THEN** it exits 2 with `reviewers.py: cfg.json: format must be 2` on stderr, and `sw pr snapshot --reviewer-config cfg.json` exits 2 before any `gh` call
