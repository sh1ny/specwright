# Spec Delta

## MODIFIED Requirements

### Requirement: Every seeded PR body for an issue check has a recorded rendering
Every merged PR body that a git-workflow fixture seeds for the closed-check SHALL be among the bodies the markdown recorder renders and the recordings coverage test checks. The coverage test SHALL fail for a seeded body with no recording.

#### Scenario: Finish fixtures' body
- **WHEN** the finish fixtures seed PR #7 with `Adds greet and farewell.\n\nCloses #12`
- **THEN** `markdown.json` has a recording for it, and `sw pr closed-check` against that fixture exits with the issue's state instead of `GitHub state unknown: no recorded rendering`

#### Scenario: A new fixture body without a recording
- **WHEN** a fixture seeds a merged PR body that has no recording
- **THEN** the recordings coverage test fails and names that body
