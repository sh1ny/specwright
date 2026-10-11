# pr-evidence Specification

## Purpose

Defines what `specwright-pr` may treat as evidence about a pull request: reviewer reports that belong to the current head, replies bound to the item revision they answer, and review bodies read in full before they are judged.

## Requirements

### Requirement: Reviewer reports count only for the current head
A timestamp-based reviewer SHALL count as `reported` on a head only for output at or after that head's push time from the repository activity log. When the push is not in the log, the cutoff SHALL be the earliest GitHub time any snapshot on this machine saw that head, never the commit date. The snapshot SHALL state which cutoff it used.

#### Scenario: Push time known
- **WHEN** head B's push is in the activity log at 11:00, and Mira posts its walkthrough at 11:30
- **THEN** the snapshot reports Mira `reported` on B, with cutoff source `push`

#### Scenario: Previous-head report with push activity missing
- **WHEN** head B was committed at 09:00, Mira and a required generic reviewer reported on head A at 10:00, B was pushed at 11:00, B's push is missing from the activity log, and a snapshot first sees B at 12:00
- **THEN** both reviewers are `waiting` on B, not `reported`, and the cutoff source is `first_seen`

#### Scenario: Report after the head was first seen
- **WHEN** B's push is missing from the activity log, a snapshot first saw B at 12:00, and the generic reviewer comments at 12:10
- **THEN** a later snapshot reports that reviewer `reported` on B

#### Scenario: First-seen time survives a new process
- **WHEN** one snapshot process saw head B at 12:00 and exited, and a new snapshot process reads B at 12:40 with its push still missing from the log
- **THEN** the new process uses 12:00 as both the report cutoff and the start of each reviewer's timeout

#### Scenario: First-seen record cannot be written
- **WHEN** the push is missing from the log, and the first-seen record for B can be neither created nor read, or exists but cannot be parsed
- **THEN** the snapshot uses the earliest GitHub time this process saw B as the cutoff and the timeout start, keeps that time across its polls, and reports cutoff source `first_seen_unsaved`

#### Scenario: Waiting with an unwritable state directory
- **WHEN** a `--wait` runs with an unwritable state directory, B's push is missing from the log, the watcher first saw B at 12:00, a generic reviewer comments at 12:10, and a silent required reviewer has a 20-minute timeout
- **THEN** the next poll after 12:10 reports the generic reviewer `reported`, and the first poll at or after 12:20 reports the required reviewer `timed_out`

#### Scenario: Commit-precise reviewers
- **WHEN** B's push is missing from the activity log, and Codex posts a result naming B's commit SHA that was created before any snapshot saw B
- **THEN** Codex is `reported` on B

### Requirement: A reply is posted only for the revision that was judged
`pr-reply.sh` SHALL accept the revision of the item being answered. Given one, it SHALL read the item from GitHub before it posts a reply or resolves a thread, and SHALL post nothing and resolve nothing when the item's current revision differs (exit 5, naming both revisions) or cannot be read (exit 3). Without a revision it SHALL behave as in 0.1.10.

#### Scenario: Item unchanged
- **WHEN** feedback answers a thread with the `rev` from its snapshot and nobody has changed the thread since
- **THEN** the reply is posted, the thread is resolved when `--resolve` was given, and the exit status is 0

#### Scenario: Reviewer edited the finding during the fix
- **WHEN** the reviewer edits the thread's comment after the snapshot was taken, and feedback then answers it with the snapshot's `rev`
- **THEN** no reply is posted, the thread stays unresolved, no reaction is added, and the exit status is 5 with the judged and the current revision on stderr

#### Scenario: Item cannot be read
- **WHEN** a revision is given and the item cannot be read from GitHub
- **THEN** nothing is posted or resolved, and the script exits 3

#### Scenario: Reply from an older session
- **WHEN** `pr-reply.sh` is called without a revision
- **THEN** it posts and resolves as before, with no re-read

### Requirement: Handled markers are bound to a revision
Each reply SHALL carry a handled marker naming the revision it answered. The snapshot SHALL count an item as answered by such a reply only while the item's reviewer content still has that revision; any later reviewer comment or edit SHALL list the item again. Markers without a revision SHALL keep the time-based rule.

#### Scenario: Edit lands between the re-read and the reply
- **WHEN** a reply bound to revision R is posted for a PR comment, and the reviewer's edit to that comment lands a second before the reply
- **THEN** the next snapshot lists the comment as unanswered, with its new `rev`

#### Scenario: Thread edited before a resolving reply
- **WHEN** a reviewer edits a comment in a thread, and then a reply bound to the thread's revision before that edit is posted with `--resolve` and the thread is resolved
- **THEN** the next snapshot lists the thread although it is resolved, with `rebound: true` and `awaiting_reviewer: false`

#### Scenario: Answered item stays answered
- **WHEN** a reply bound to the thread's current reviewer revision exists, and nobody has commented or edited since
- **THEN** the snapshot lists the thread as `awaiting_reviewer` or not at all, as it does for an answered thread today

#### Scenario: Marker from 0.1.10
- **WHEN** an item's only marker carries no revision, and the item was not edited after that reply
- **THEN** the snapshot treats the item as handled

### Requirement: Clipped bodies are marked
The snapshot SHALL set `clipped: true` on every thread comment, PR comment and review whose body it shortened, and `clipped: false` otherwise.

#### Scenario: Long review
- **WHEN** a review body is 5000 characters after its HTML comments are removed
- **THEN** the snapshot lists it with a shortened body and `clipped: true`

#### Scenario: Body at the limit
- **WHEN** a PR comment body is exactly 1200 characters
- **THEN** the snapshot lists the whole body with `clipped: false`

### Requirement: Clipped items are read in full before they are judged
`pr-snapshot.sh --full <item id>` SHALL print the item's full body and revision as one JSON line. Feedback SHALL read the full body of every clipped item before judging, answering or dropping it, and SHALL hand over to the user when it cannot be read.

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
`pr-reply.sh` SHALL check that the body file of a `thread` or `comment` reply exists, is readable and is not empty, and that the reply with its marker was written in full, before any GitHub call. When a check fails, it SHALL exit non-zero, name the body file on stderr, and post, resolve and react to nothing.

#### Scenario: Body file present
- **WHEN** feedback answers a thread with a non-empty, readable body file
- **THEN** the reply holds that body followed by the handled marker, and the exit status is 0

#### Scenario: Body file missing
- **WHEN** `pr-reply.sh` is called with a body file path that does not exist
- **THEN** the exit status is non-zero, stderr names the path, and no GitHub request is made

#### Scenario: Body file empty
- **WHEN** the body file exists and is empty
- **THEN** the exit status is non-zero, stderr names the path, and no GitHub request is made

#### Scenario: Body file unreadable
- **WHEN** the body file exists but cannot be read
- **THEN** the exit status is non-zero, stderr names the path, and no GitHub request is made
