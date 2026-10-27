## ADDED Requirements

### Requirement: The pre-ship review checks the Release Notes section against the diff
With `release.enabled` true, the pre-ship brief SHALL ask the reviewer to check the proposal's `## Release Notes` section: a missing section, a section that breaks the format rules of the `releases` capability, or an item the diff does not ship SHALL each be a P1 `docs` finding; a user-visible change the diff ships with no item SHALL be a P2 `docs` finding. With releases off, no finding SHALL concern the section.

#### Scenario: Item the diff does not ship
- **WHEN** `release.enabled` is true, the section lists `Added: --dry-run flag (#140)` and the diff adds no such flag
- **THEN** the review returns a P1 `docs` finding naming that item, and ship waits for a fix or a waiver

#### Scenario: Shipped change with no item
- **WHEN** `release.enabled` is true and the diff adds a new `release.sh` subcommand that no item mentions
- **THEN** the review returns a P2 `docs` finding, and the review can still pass

#### Scenario: Section missing with releases on
- **WHEN** `release.enabled` is true and the proposal has no `## Release Notes` section
- **THEN** the review returns a P1 `docs` finding saying the section is missing

#### Scenario: Section breaks the format
- **WHEN** `release.enabled` is true and the section has a `### Security` heading
- **THEN** the review returns a P1 `docs` finding naming `Security` and its line, and ship waits for a fix or a waiver

#### Scenario: Releases off
- **WHEN** `release.enabled` is false and the proposal still holds a `## Release Notes` section with a stale item, or no section at all
- **THEN** no finding concerns release notes
