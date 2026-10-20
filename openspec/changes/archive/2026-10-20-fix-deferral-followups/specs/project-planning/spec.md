# Spec Delta

## ADDED Requirements

### Requirement: A parking change is never a milestone change
A parking change SHALL NOT be listed in a milestone's Changes, since it is never archived and so never done. When **next**, **close** or **status** find a listed change that is parked, they SHALL report it as parked and listed in error, SHALL neither start it nor count it done, and SHALL say that removing it from Changes is the user's planning edit. **next** and **close** SHALL then stop. The skill SHALL NOT edit the roadmap to remove it.

#### Scenario: Close with a parked change listed
- **WHEN** the Now milestone lists `platform-backlog`, whose `review.md` holds `VERDICT: DEFERRED`, and every other listed change is done
- **THEN** close reports `platform-backlog` as parked and listed in error, says removing it from Changes is the user's edit, does not close the milestone, and leaves `openspec/roadmap.md` unchanged

#### Scenario: Next reaches a parked listed change
- **WHEN** the first Now change with no archive is `platform-backlog`, which is parked
- **THEN** next does not start it, creates no branch and no change, and reports it as parked and listed in error

#### Scenario: Status with a parked listed change
- **WHEN** status runs while the Now milestone lists the parked `platform-backlog`
- **THEN** status lists it as `parked (listed in error)`, and does not report `milestone end: run close`

#### Scenario: Parking change not listed
- **WHEN** `platform-backlog` is parked, it is not listed in any milestone, and every listed change of Now is done
- **THEN** next reports `milestone end: run close` as before
