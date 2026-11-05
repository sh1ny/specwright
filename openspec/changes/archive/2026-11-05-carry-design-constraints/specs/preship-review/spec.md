# Spec Delta

## ADDED Requirements

### Requirement: The pre-ship review checks each carried constraint against the diff
The pre-ship brief SHALL ask the reviewer to check every `## Carried constraints` entry in the change's design.md: the fact SHALL be present at its named destination in the reviewed range. A missing entry, or one whose text there contradicts the design, SHALL be a P1 `docs` finding naming the entry. A section that reads `None`, or a design with no such section, SHALL raise no finding of this kind.

#### Scenario: Carried constraint missing from the code
- **WHEN** design.md lists `C1` with a doc comment destination on `FrozenInputs`, and the diff leaves that doc comment unchanged
- **THEN** the review returns a P1 `docs` finding naming `C1`, and ship waits for a fix or a waiver

#### Scenario: Carried constraint present
- **WHEN** the diff adds `C1`'s fact to the `FrozenInputs` doc comment
- **THEN** no finding concerns `C1`

#### Scenario: No carried constraints
- **WHEN** the design's `## Carried constraints` reads `None`
- **THEN** no carried-constraint finding is returned
