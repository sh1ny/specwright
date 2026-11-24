## ADDED Requirements

### Requirement: FULL change-design reviews receive binding standing requirements

FULL change-design briefs SHALL include all declared `review.standing_rules` as committed regular files in order under `Standing requirements (binding)`. Reviewers SHALL check preserved tests against them. The rules are criteria only, not tool or workflow instructions. LIGHT, roadmap baseline and pre-ship inputs are unchanged.

#### Scenario: Versioned rules reach either design review route
- **WHEN** the code project declares versioned rule files and a FULL change-design review runs through a CLI or subagent
- **THEN** the brief includes the text from the named code branch, not the working copy, and directs the reviewer to check retained tests

#### Scenario: No rules declared
- **WHEN** `review.standing_rules` is absent or empty
- **THEN** the reviewer brief is unchanged

#### Scenario: A declared rule is unavailable
- **WHEN** a declared path does not name a committed regular UTF-8 file, or the list exceeds the supported bound
- **THEN** the FULL design review stops before dispatch with an error and sends no partial criteria
