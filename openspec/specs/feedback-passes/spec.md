# feedback-passes Specification

## Purpose
Keeps a PR feedback pass recoverable and exclusive: a pass is recorded before its first fix, owned by one session, stored under a key unique to its repository and change, and finished from evidence after an interruption, for repo-local and store-backed changes alike.

## Requirements

### Requirement: A feedback pass has one owner
Writing a feedback pass record SHALL fail when a record for the same repository and change exists, with no window in which two sessions can both create it. The record SHALL hold an owner id. Removing or handing over a record SHALL require the owner id it holds. A record owned by another session SHALL never be removed or taken over automatically: Specwright SHALL show its owner and ask the user.

#### Scenario: Two sessions start a pass for one change
- **WHEN** two sessions write a pass record for the same repository and change at the same time
- **THEN** exactly one write succeeds, the other is refused with `record_exists`, and the record holds the intent and owner id of the session that succeeded

#### Scenario: Resume by the owning session
- **WHEN** the session that wrote a record plans and completes the pass with its own owner id
- **THEN** the plan reports the record as owned by this session, and the record is removed once every applicable step is done

#### Scenario: Record left by another session
- **WHEN** a run finds a pass record whose owner id is not its own
- **THEN** it posts, commits and pushes nothing for that pass, shows the owner (when it was written and from which checkout), and asks the user whether that session is gone

#### Scenario: User confirms the owner is gone
- **WHEN** the user confirms that the session owning a record is gone, and the run hands the record over naming the owner id it was shown
- **THEN** the record keeps its round and findings, holds the new owner id, and the run resumes that pass

#### Scenario: Handover races another session
- **WHEN** a handover names an owner id that no longer matches the record, because another session took the record over first
- **THEN** the handover is refused with `not_owner`, and the record is unchanged

#### Scenario: Lock left by an interrupted handover
- **WHEN** a handover or removal finds the record's lock directory already present
- **THEN** it exits with `record_busy` naming the lock path, the record and the lock are unchanged, and the lock is not removed automatically

#### Scenario: Record write fails while it is created
- **WHEN** `pass write` creates the record without hard-link support and writing it fails
- **THEN** no record is left at the key, the error is reported, and a later `pass write` for that change can create the record

#### Scenario: Removal by a non-owner
- **WHEN** a run that does not hold the record's owner id asks to remove a complete pass record
- **THEN** the removal is refused with `not_owner`, and the record remains

### Requirement: Pass records are keyed per repository and change
Each pass record SHALL be stored under a key that keeps the repository owner, the repository name and the change name apart, compared without regard to case, so that two different repositories or changes never share a record. A record stored under the key used by 0.1.9 SHALL be moved to its new key on first use when its recorded repository and change match the lookup, and left in place otherwise.

#### Scenario: Hyphenated owners and names
- **WHEN** `acme-tools/widget` and `acme/tools-widget` each start a feedback pass for a change named `fix-login`
- **THEN** both records exist side by side, and each repository's plan reads only its own record

#### Scenario: Record from 0.1.9
- **WHEN** a pass record written by 0.1.9 exists under the old key for this repository and change, and no record exists under the new key
- **THEN** the record is moved to the new key, its contents unchanged, and the plan resumes it as a record with no owner id

#### Scenario: Old key belongs to another repository
- **WHEN** a record under the old key exists whose recorded repository or change differs from the lookup
- **THEN** that file is left in place, and the lookup reports no record

#### Scenario: Old key cannot be read
- **WHEN** no record exists under the new key, and a file under the old key exists whose contents cannot be parsed, so its repository and change are unknown
- **THEN** the lookup stops with `record_unreadable` naming that file, and no new pass is allowed

#### Scenario: Old key denied by the filesystem
- **WHEN** a valid record exists under the new key, and reading the file under the old key fails with a permission error
- **THEN** the plan uses the new record and reports the old file as ignored; without a new-key record, the lookup stops with `record_unreadable`

#### Scenario: Unreadable old key beside a valid record
- **WHEN** a valid record exists under the new key, and the file under the old key cannot be parsed
- **THEN** the plan and `pass done` use the new record, and the old file is reported as ignored

#### Scenario: Longest repository and change names
- **WHEN** a pass starts for a 39-character owner, a 100-character repository name and an 80-character change name
- **THEN** the record and its lock can be created, and the pass can be handed over and completed

#### Scenario: Two callers move one old record
- **WHEN** two `pass` calls find the same 0.1.9 record, and the other caller removes the old file after this one published the new key
- **THEN** both calls continue with the record under the new key, and neither fails

#### Scenario: Copy left by an interrupted move
- **WHEN** a record under the old key is byte-identical to the record under the new key, because a move was interrupted after the new key was written
- **THEN** the old file is removed, and once the pass is done no record for the change remains

### Requirement: A pass intent is validated before it is written
`pass write` SHALL refuse an intent with `invalid_intent`, writing no record, unless `branch` is a non-empty string, `round` is a positive integer, `prs` is an object whose `code` and `store` entries are absent, null or an object with `repo` as `<owner>/<name>` and `number` as a positive integer, and every finding has the fields a plan reads.

#### Scenario: Well-formed intent
- **WHEN** an intent has a branch name, round 2, a code PR entry `{"repo": "acme/app", "number": 5}` and well-formed findings
- **THEN** the record is written, and a plan of it reads without error

#### Scenario: `prs` is a string
- **WHEN** an intent sets `prs` to the string `"acme/app#5"`
- **THEN** `pass write` exits with `invalid_intent` naming `prs`, and no record exists

#### Scenario: Round is not a positive integer
- **WHEN** an intent sets `round` to `0`, `"2"` or `true`
- **THEN** `pass write` exits with `invalid_intent` naming `round`, and no record exists

#### Scenario: Thread finding without a usable root id
- **WHEN** a thread finding has no `root_id`, or its `root_id` is `"abc"`
- **THEN** `pass write` exits with `invalid_intent` naming `root_id`, and no record exists

#### Scenario: Repo-local intent names a store PR
- **WHEN** a repo-local intent sets `prs.store` to `{"repo": "acme/plans", "number": 3}`
- **THEN** `pass write` exits with `invalid_intent` naming `prs`, and no record exists

### Requirement: Repo-local changes recover an interrupted pass
A repo-local change SHALL record its feedback pass, count its rounds and resume an interrupted pass the same way a store-backed change does, with the code repo as its only repo. A pass whose fix commit carries the round at the limit SHALL be finished under that round, not answered as after the limit.

#### Scenario: Interrupted after the last allowed fix was pushed
- **WHEN** `max_fix_rounds` is 2 in a repo-local change, pass 2's fix commit is pushed, and the run stopped before posting replies
- **THEN** the next run re-requests review if due and posts pass 2's replies under round 2, makes no new fix, and posts no `Waiting on owner` reply for those findings

#### Scenario: Repo-local pass completes
- **WHEN** a repo-local pass has its fix pushed, every reply posted, every resolution and reaction done
- **THEN** the plan reports `complete`, and the record is removed

#### Scenario: Repo-local record names a store edit
- **WHEN** a repo-local intent has a finding whose destination is `store`
- **THEN** `pass write` exits with `misrouted`, and no record exists

### Requirement: A re-request counts once per head when the push time is missing
`pass plan` SHALL mark a review request done when a matching comment from its poster was created at or after the head's push time. With no push for the head in the activity log, the cutoff SHALL be the earliest time a snapshot on this machine saw that head, or, only when no such record can be read, the time the pass record was written. Feedback SHALL snapshot each pushed PR before re-requesting. The plan SHALL state which cutoff it used.

#### Scenario: Push time known
- **WHEN** the head's push is in the activity log and the matching request was posted after it
- **THEN** the re-request row is `done`, with cutoff source `push`

#### Scenario: Push missing, request posted after the head was seen
- **WHEN** the head's push is missing from the activity log, a snapshot first saw the head at 12:00, and the matching request was posted at 12:05
- **THEN** the re-request row is `done` with cutoff source `first_seen`, and repeated plans schedule no further request for that head

#### Scenario: Push missing and no first-seen record
- **WHEN** the head's push is missing, no first-seen record for the head can be read, the pass record was written at 11:50, and the matching request was posted at 12:05
- **THEN** the re-request row is `done`, with cutoff source `pass_written`

#### Scenario: Only an earlier head's request exists
- **WHEN** the head's push is missing, the snapshot first saw the head at 12:00, and the only matching request comment was posted at 10:00 for the previous head
- **THEN** the re-request row is `todo`

#### Scenario: Request posted before any snapshot saw the head
- **WHEN** the head's push is missing, the request for that head was posted at 12:05 before any snapshot saw the head, and a snapshot at 12:10 then records the head's first sighting
- **THEN** the next plan's re-request row is `todo`, and once a second matching request is posted after 12:10 the row is `done` and no further request is scheduled for that head

#### Scenario: Second head pushed in the same pass
- **WHEN** the push of head H2 is missing, a request for the pass's earlier head H1 was posted at 12:05, and a snapshot first saw H2 at 12:20
- **THEN** the re-request row for H2 is `todo`, with cutoff source `first_seen`

#### Scenario: Feedback snapshots the pushed head before re-requesting
- **WHEN** a feedback pass has pushed its fix and is about to re-request review
- **THEN** the `specwright-pr` text has the agent take a fresh snapshot of each pushed PR and run `pass plan` with it before posting any request, and post only the requests whose row is not `done`. The general **Re-request review** rule's "post anyway when the push time is not found" applies only outside a feedback pass

#### Scenario: Record written before this change
- **WHEN** a pass record from 0.1.12 has no write time, the push is missing and no first-seen record can be read
- **THEN** the plan uses the record owner's `at` as the cutoff and does not fail

### Requirement: PR-item issues are found in one read per pass
With `pr.after_limit: issues`, a feedback pass SHALL find the existing issues for its actionable items in one bounded read of each repository's issues (one for a repo-local pass, at most two for a store-backed one), as that repository's login, whatever the number of items. Each item is matched by its `specwright:pr-item <item id>` marker line. When the read fails or passes its bound, the pass SHALL create no issue for any item and SHALL report the lookup as not done.

#### Scenario: Several findings, some already tracked
- **WHEN** a pass past the round limit has three actionable items, and an issue with the marker of the second one already exists
- **THEN** the repository's issue list is read once, the second item is answered with that issue, and only the first and third get new issues

#### Scenario: Store-backed pass with items in both repositories
- **WHEN** a store-backed pass past the round limit has two actionable items on the code PR and one on the store PR
- **THEN** the code repository's issues are read once as the code login and the store's once as the store login, and each item is matched only in its own repository

#### Scenario: Pull requests carrying the marker
- **WHEN** a pull request's body, not an issue's, contains an item's marker
- **THEN** the pull request is not taken as that item's issue, and the item gets a new issue

#### Scenario: Issue list cannot be read
- **WHEN** the issue read fails or passes its deadline or size bound
- **THEN** no issue is created in that pass, each item is left unanswered, and the pass reports the lookup as not done with the error name
