# Spec Delta

## Purpose

Makes every claim a design makes about existing code either cited and checked against that code, or recorded as an assumption that the review weighs and that apply verifies before relying on it.

## ADDED Requirements

### Requirement: A design cites the code behind each claim
Each design.md claim about how existing code, data or a format behaves SHALL cite the `path:line` range that shows it, narrowed to the lines that support the claim. A claim the author did not check against the code SHALL be an entry in a `## Assumptions` section, with an id (`A1`, `A2`...) and the decisions or tasks that depend on it.

#### Scenario: Claim checked against the code
- **WHEN** a design states that a function rejects a missing input and the author has read where it does
- **THEN** the claim carries a `path:line` citation of those lines

#### Scenario: Claim the author could not check
- **WHEN** a design depends on how an external service behaves and no code in reach shows it
- **THEN** the claim is entry `A1` under `## Assumptions`, naming the decisions or tasks that rely on it, and carries no citation

#### Scenario: Design with no claims about existing code
- **WHEN** a design builds only new files and makes no claim about existing behaviour
- **THEN** its `## Assumptions` section reads `None` and no citation is required

### Requirement: The design review checks each cited claim
The FULL design review SHALL re-read every range a design cites and check that it supports the claim. A claim about existing behaviour with no citation and no Assumptions entry, a citation that contradicts its claim or does not show it, and an assumption the reviewer settles by reading the code SHALL each be a finding. A contradicted claim that a decision or task depends on SHALL be Critical; any other claim finding SHALL be at least Moderate.

#### Scenario: Citation contradicts the claim
- **WHEN** design.md claims `fromGeneration` stages every indexed input, citing `pack.dart:146-254`, and a doc comment in that range says missing sources throw
- **THEN** the review records a Critical finding naming the claim and the contradicting lines, and its verdict is not `APPROVE`

#### Scenario: Claim without citation
- **WHEN** design.md states how an existing parser handles empty files, with no citation and no Assumptions entry
- **THEN** the review records a finding asking for a citation or an assumption entry

#### Scenario: Assumption the code settles
- **WHEN** an Assumptions entry says a config key defaults to `false` and the loader in the repo shows its default
- **THEN** the review records a finding to replace the assumption with a cited claim, or to correct the design if the default differs

#### Scenario: Cited range no longer exists
- **WHEN** a citation names a file or line range that is not in the checkout
- **THEN** the review records a finding that the citation does not show the claim

### Requirement: The LIGHT re-check also re-reads citations
For a `TIER: LIGHT` design, the author's triage re-check SHALL also re-read each cited range against its claim. A contradiction SHALL be fixed in design.md before `VERDICT: SKIPPED_LIGHT` is written, and a fix that makes a trigger apply SHALL make the design FULL and send it to the full review.

#### Scenario: LIGHT citations hold
- **WHEN** a LIGHT design's citations all support their claims and the triage still holds
- **THEN** review.md records `VERDICT: SKIPPED_LIGHT` as before

#### Scenario: LIGHT citation contradicts the claim
- **WHEN** the re-check finds a cited range that says the opposite of the claim
- **THEN** design.md is corrected before any verdict is written, and `SKIPPED_LIGHT` is written only when the corrected triage still has no trigger

### Requirement: Tasks verify load-bearing assumptions first
When design.md lists an assumption that a decision or task depends on, tasks.md SHALL hold a task that verifies it, placed before every task that relies on it. An assumption that a verify task disproves SHALL stop apply under the design drift rule.

#### Scenario: Assumption with dependent tasks
- **WHEN** design.md lists `A1` and decision D2 depends on it
- **THEN** tasks.md has a task naming `A1` that verifies it, ordered before the first task implementing D2

#### Scenario: Assumption disproved during apply
- **WHEN** the verify task for `A1` finds the assumption false
- **THEN** apply stops that work, design.md is amended and the review step runs again before the dependent tasks resume

#### Scenario: Assumption nothing depends on
- **WHEN** an Assumptions entry names no decision or task that depends on it
- **THEN** no verify task is required for it
