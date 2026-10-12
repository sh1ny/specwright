# Spec Delta

## ADDED Requirements

### Requirement: The description lists spec amendments and open review findings
A PR description written by Specwright SHALL list each spec amendment made in response to the pre-ship review (each commit with an `Amendment:` trailer, with its class: clarification or user-approved behaviour change), each P2 or P3 pre-ship finding left unfixed, and each P0 or P1 finding the user waived, with the user's reason. A change with none of these SHALL have no such section.

#### Scenario: Clarification after pre-ship review
- **WHEN** the change has one `<type>(<change>): amend specs` commit with the trailer `Amendment: clarification`
- **THEN** the description's spec amendments section names that commit and says `clarification`

#### Scenario: Open P3 finding
- **WHEN** the passing pre-ship review left a P3 finding unfixed
- **THEN** the description lists that finding with its file and summary

#### Scenario: Waived P1 finding
- **WHEN** the user waived P1 finding `f2` with the reason `out of scope, tracked as #90`
- **THEN** the description lists `f2` as waived with that reason

#### Scenario: Drift amendment during apply
- **WHEN** the change's only `amend specs` commit was made during apply under the drift rule and has no `Amendment:` trailer
- **THEN** the description lists no spec amendment

#### Scenario: Nothing to list
- **WHEN** the change has no commit with an `Amendment:` trailer, no unfixed P2 or P3 finding and no waived finding
- **THEN** the description has no spec amendments or open findings section
