# Spec Delta

## MODIFIED Requirements

### Requirement: A report rule decides for its reviewer
The optional `pr.reviewers.<login>.report` SHALL accept `sha_pattern` and `ignore` (regular expressions in the dialect below), `marker` (a literal substring) and `check` (an exact check name, counted only from a check run of the reviewer's own GitHub App, whose slug is its login). With `sha_pattern`, `check` or `marker` set, only those and a review on the head commit SHALL decide `reported`. `ignore` SHALL exclude matching comment and review bodies from every rule.

#### Scenario: Sha pattern names the head
- **WHEN** `report.sha_pattern` is `Reviewed commit: ([0-9a-f]{7,40})` and the reviewer comments `Reviewed commit: 1a2b3c4` with head `1a2b3c4d...`
- **THEN** the reviewer is `reported` with `by: sha_pattern`

#### Scenario: Sha pattern names an older commit
- **WHEN** the same reviewer's only matching comment names the previous head's SHA
- **THEN** the reviewer is `waiting`, even though the comment was posted after the cutoff

#### Scenario: Named check
- **WHEN** `report.check` is `Bot Code Review`, and a check of that name on the head completes
- **THEN** the reviewer is `reported` with `by: check`, and a completed check of another name from the same app does not count

#### Scenario: Named check from another producer
- **WHEN** `report.check` is `Bot Code Review`, and the only check of that name on the head is a commit status or a check run of another app
- **THEN** the reviewer is not `reported` by it, and a pending one counts as CI

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
An unknown `report` key, a pattern that does not compile, or a `sha_pattern` with no capture group SHALL stop the snapshot with exit 2 naming the reviewer and the key, before any `gh` call.

#### Scenario: Bad rule
- **WHEN** `report.sha_pattern` is `([0-9a-f`
- **THEN** `pr-snapshot.sh` exits 2 with a message naming the reviewer and `sha_pattern`, and prints no snapshot

#### Scenario: Unknown key
- **WHEN** `report` sets `checks: Bot Code Review`
- **THEN** `pr-snapshot.sh` exits 2 with a message naming the reviewer and `checks`

#### Scenario: Python-only syntax is refused
- **WHEN** `report.sha_pattern` is `\Areviewed (?P<sha>[0-9a-f]{7,40})`, or `report.ignore` is `(?i)in progress`
- **THEN** `pr-snapshot.sh` exits 2 with a message naming the reviewer and the key, before any `gh` call, and no reviewer state is decided with that pattern

#### Scenario: Sha pattern without a capture group
- **WHEN** `report.sha_pattern` is `reviewed [0-9a-f]+`
- **THEN** `pr-snapshot.sh` exits 2 with a message naming the reviewer and `sha_pattern`

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
- **THEN** it exits 2 with `reviewers.py: format must be 2` on stderr, and `pr-snapshot.sh --reviewer-config cfg.json` exits 2 before any `gh` call

## ADDED Requirements

### Requirement: Report patterns are JavaScript regular expressions
`report.sha_pattern` and `report.ignore` SHALL be read as JavaScript regular expressions in Unicode mode, as Dart's `RegExp(pattern, unicode: true)` reads them (ADR 0030). They SHALL be searched, so a match anywhere in a body counts, case-sensitive and not multiline.

#### Scenario: The repository's own pattern under the new dialect
- **WHEN** `report.sha_pattern` is ``Reviewed commit:\*\* `([0-9a-f]{7,40})` `` and the reviewer comments ``**Reviewed commit:** `1a2b3c4` `` with head `1a2b3c4d...`
- **THEN** the reviewer is `reported` with `by: sha_pattern`, as before this change
