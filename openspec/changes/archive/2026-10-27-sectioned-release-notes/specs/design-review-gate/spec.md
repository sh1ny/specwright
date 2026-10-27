## ADDED Requirements

### Requirement: Release Notes edits keep the design review verdict
An edit that changes only the proposal's `## Release Notes` section SHALL NOT void the change's design review verdict. Any edit outside that section, in the proposal, specs or design, SHALL void it as before.

#### Scenario: Release Notes item added during apply
- **WHEN** a task commit during apply adds a `### Fixed` item to the proposal's `## Release Notes` section and changes no other line of proposal, specs or design
- **THEN** the review's verdict still holds, and apply continues without a new design review

#### Scenario: Edit outside the section
- **WHEN** the same commit also rewords a line of the proposal's `## What Changes`
- **THEN** the verdict is void, and the drift rule's new review step applies
