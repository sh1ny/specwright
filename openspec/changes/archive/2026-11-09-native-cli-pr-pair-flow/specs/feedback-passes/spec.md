## MODIFIED Requirements

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
- **WHEN** a handover or removal finds the record's `.lock` path already occupied, by a native lock file or a legacy lock directory
- **THEN** it exits with `record_busy` naming the lock path, the record and the lock are unchanged, and the lock is not removed automatically

#### Scenario: Record write fails while it is created
- **WHEN** `pass write` creates the record without hard-link support and writing it fails
- **THEN** no record is left at the key, the error is reported, and a later `pass write` for that change can create the record

#### Scenario: Removal by a non-owner
- **WHEN** a run that does not hold the record's owner id asks to remove a complete pass record
- **THEN** the removal is refused with `not_owner`, and the record remains
