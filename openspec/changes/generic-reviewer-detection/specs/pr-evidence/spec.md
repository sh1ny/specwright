# Spec Delta

## MODIFIED Requirements

### Requirement: Reviewer reports count only for the current head
A timestamp-based reviewer SHALL count as `reported` on a head only for output at or after that head's push time from the repository activity log. When the push is not in the log, the cutoff SHALL be the earliest GitHub time any snapshot on this machine saw that head, never the commit date. The snapshot SHALL state which cutoff it used.

#### Scenario: Push time known
- **WHEN** head B's push is in the activity log at 11:00, and a reviewer with a `marker` rule edits its marked comment at 11:30
- **THEN** the snapshot reports that reviewer `reported` on B, with cutoff source `push`

#### Scenario: Previous-head report with push activity missing
- **WHEN** head B was committed at 09:00, a reviewer with a `marker` rule and a required reviewer with no `report` rule reported on head A at 10:00 by comments, B was pushed at 11:00, B's push is missing from the activity log, and a snapshot first sees B at 12:00
- **THEN** both reviewers are `waiting` on B, not `reported`, and the cutoff source is `first_seen`

#### Scenario: Report after the head was first seen
- **WHEN** B's push is missing from the activity log, a snapshot first saw B at 12:00, and the reviewer with no `report` rule comments at 12:10
- **THEN** a later snapshot reports that reviewer `reported` on B

#### Scenario: First-seen time survives a new process
- **WHEN** one snapshot process saw head B at 12:00 and exited, and a new snapshot process reads B at 12:40 with its push still missing from the log
- **THEN** the new process uses 12:00 as both the report cutoff and the start of each reviewer's timeout

#### Scenario: First-seen record cannot be written
- **WHEN** the push is missing from the log, and the first-seen record for B can be neither created nor read, or exists but cannot be parsed
- **THEN** the snapshot uses the earliest GitHub time this process saw B as the cutoff and the timeout start, keeps that time across its polls, and reports cutoff source `first_seen_unsaved`

#### Scenario: Waiting with an unwritable state directory
- **WHEN** a `--wait` runs with an unwritable state directory, B's push is missing from the log, the watcher first saw B at 12:00, a reviewer with no `report` rule comments at 12:10, and a silent required reviewer has a 20-minute timeout
- **THEN** the next poll after 12:10 reports the commenting reviewer `reported`, and the first poll at or after 12:20 reports the required reviewer `timed_out`

#### Scenario: Commit-precise reviewers
- **WHEN** B's push is missing from the activity log, and a reviewer with a `sha_pattern` rule posts a result naming B's commit SHA that was created before any snapshot saw B
- **THEN** that reviewer is `reported` on B

## ADDED Requirements

### Requirement: Reviewers are detected by generic rules
A configured reviewer with no `sha_pattern`, `check` or `marker` rule SHALL count as `reported` on the head by the first of: a submitted review it authored on the head commit, or its output at or after the head's cutoff. Check runs SHALL count only through `report.check`. The snapshot SHALL give each reviewer `by`: `review`, `output` or the `report` key that matched, and SHALL name no reviewer login in its rules.

#### Scenario: Review bound to the head
- **WHEN** reviewer `rev-bot` with no `report` rule submits a review on commit B, and B is the head
- **THEN** the snapshot reports `rev-bot` `reported` with `by: review`, whatever the cutoff

#### Scenario: Review bound to an older commit
- **WHEN** `rev-bot` submitted its only review on commit A before the push of head B, and posted nothing after B's cutoff
- **THEN** `rev-bot` is `waiting` on B

#### Scenario: A check of the reviewer's app without a rule
- **WHEN** reviewer `github-actions` with no `report` rule posts nothing on head B, and a CI check run from app `github-actions` on B completes
- **THEN** `github-actions` is `waiting`, not `reported`

#### Scenario: Formerly built-in login without a rule
- **WHEN** `pr.reviewers` lists `kintsugimira` with no `report` rule, and it posts a comment at or after the cutoff that says only that a review is in progress
- **THEN** the snapshot reports it `reported` with `by: output`, exactly as for any other login

### Requirement: A report rule decides for its reviewer
The optional `pr.reviewers.<login>.report` SHALL accept `sha_pattern` and `ignore` (Python regular expressions, searched, case-sensitive), `marker` (a literal substring) and `check` (an exact check name). With any of `sha_pattern`, `check` or `marker` set, only those and a review on the head commit SHALL decide `reported`. `ignore` SHALL exclude matching comment and review bodies from every rule.

#### Scenario: Sha pattern names the head
- **WHEN** `report.sha_pattern` is `Reviewed commit: ([0-9a-f]{7,40})` and the reviewer comments `Reviewed commit: 1a2b3c4` with head `1a2b3c4d...`
- **THEN** the reviewer is `reported` with `by: sha_pattern`

#### Scenario: Sha pattern names an older commit
- **WHEN** the same reviewer's only matching comment names the previous head's SHA
- **THEN** the reviewer is `waiting`, even though the comment was posted after the cutoff

#### Scenario: Named check
- **WHEN** `report.check` is `Bot Code Review`, and a check of that name on the head completes
- **THEN** the reviewer is `reported` with `by: check`, and a completed check of another name from the same app does not count

#### Scenario: Marker comment in progress
- **WHEN** `report.marker` is `<!-- walkthrough -->`, `report.ignore` is `in progress`, and the marked comment was edited after the cutoff to say `Review in progress`
- **THEN** the reviewer is `waiting`, and becomes `reported` with `by: marker` once the comment is edited again without that text

#### Scenario: Review on the head under a marker rule
- **WHEN** a reviewer with a `marker` rule submits a review on the head commit and has not edited its marked comment
- **THEN** the reviewer is `reported` with `by: review`

#### Scenario: Marker with regex characters
- **WHEN** `report.marker` is `<!-- [bot] -->` and a comment contains `<!-- b -->` but not the marker text
- **THEN** that comment does not match the marker

### Requirement: A bad report rule stops the snapshot
An unknown `report` key, or a pattern that does not compile, SHALL stop the snapshot with exit 2 naming the reviewer and the key, before any `gh` call.

#### Scenario: Bad rule
- **WHEN** `report.sha_pattern` is `([0-9a-f`
- **THEN** `pr-snapshot.sh` exits 2 with a message naming the reviewer and `sha_pattern`, and prints no snapshot

#### Scenario: Unknown key
- **WHEN** `report` sets `checks: Bot Code Review`
- **THEN** `pr-snapshot.sh` exits 2 with a message naming the reviewer and `checks`

### Requirement: The snapshot shows each reviewer's evidence
Each reviewer entry SHALL carry `evidence`: the reviewer's reviews, comments and named check runs on the current head, at most 10, newest first, each with its kind, time, state or conclusion and a body excerpt of at most 300 characters. The snapshot SHALL carry GitHub's current time as `now`. `reported`, `waiting` and `timed_out` SHALL NOT depend on the excerpt length.

#### Scenario: Announcement and finished review
- **WHEN** a reviewer posted `Review started` after the cutoff and later submitted a review on the head
- **THEN** its `evidence` lists both, the review first

#### Scenario: Nothing on the head
- **WHEN** a reviewer posted only on the previous head
- **THEN** its `evidence` is an empty list and it is `waiting` or `timed_out`

### Requirement: Reviewer settings reach the snapshot as a file
`pr-snapshot.sh` SHALL read reviewers only from `--reviewer-config <file>`, a JSON file that `pr-pair.sh context` and `policy` write from the settings they read and whose path they print. `--reviewer` SHALL exit 2 naming `--reviewer-config`. A config file that is missing, unreadable or not the expected JSON SHALL exit 2. Both SHALL happen before any `gh` call. When the state directory is unwritable, the config file SHALL be written under the system temp directory instead.

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

### Requirement: Reviewer settings are read strictly everywhere
`context` SHALL check the settings file with the strict reader `policy` uses and print any problem as `settings_problem` (`line N: why`) without exiting. Watch SHALL stop before its first wait when `settings_problem` is set; ship, finish and cleanup SHALL ignore it. Every `report:` example in the README and the settings template SHALL pass that reader.

#### Scenario: Double-quoted escape
- **WHEN** `report.sha_pattern` is written as `"Reviewed commit:\*\*"` in double quotes
- **THEN** `context` prints `settings_problem` naming the line, watch starts no wait and shows it, and ship still runs

#### Scenario: Single-quoted pattern
- **WHEN** the same pattern is written as `'Reviewed commit:\*\*'`
- **THEN** `context` and `policy` both read it, and the config files they write hold the same pattern

### Requirement: A snapshot names the reviewer rules it used
The snapshot SHALL carry `reviewer_config`: the SHA-256 digest of the config file it ran with. `policy` SHALL count required reviewers as reported for a set only when the snapshot's digest equals the digest of the config it writes for that set, and SHALL otherwise report `rules_mismatch` for that set.

#### Scenario: Wait started with the work tree's rules
- **WHEN** main gives required `rev-bot` a `marker` rule, the wait ran with a config from the work tree where `rev-bot` has no `report`, and the snapshot reports `rev-bot` `reported` `by: output`
- **THEN** `policy` reports `rules_mismatch` for main's set and not `ok`, and no merge request is sent

#### Scenario: Same rules
- **WHEN** the work tree's reviewer settings equal main's and the snapshot reports every required reviewer `reported`
- **THEN** the digests are equal, and `policy` reports `ok` for main's set
