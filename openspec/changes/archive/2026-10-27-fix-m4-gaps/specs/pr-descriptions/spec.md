# Spec Delta

## ADDED Requirements

### Requirement: A code span after a closing keyword ends the closing list
When GitHub renders a code span between a closing keyword and the next issue reference, that reference SHALL NOT be an intended issue, at ship's closing-reference check and at cleanup's issue backstop alike, wherever the keyword stands in the line. A code span SHALL still never join the text on either side into a keyword.

#### Scenario: Code span between keyword and reference
- **WHEN** a description has the line ``Fixes `later` #31``
- **THEN** 31 is not an intended issue

#### Scenario: Code span after a keyword in mid-line
- **WHEN** a description has the line ``Notes, then fixes `x` #33``
- **THEN** 33 is not an intended issue

#### Scenario: Code span after the list
- **WHEN** a description has the line ``Fixes #34 `see log` #35``
- **THEN** 34 is an intended issue and 35 is not

#### Scenario: Plain closing line
- **WHEN** a description has the line `Fixes #36`
- **THEN** 36 is an intended issue
