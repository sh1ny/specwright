# Spec Delta

## ADDED Requirements

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
