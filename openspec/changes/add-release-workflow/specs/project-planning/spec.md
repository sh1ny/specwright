# Spec Delta

## ADDED Requirements

### Requirement: Close offers untagged releases
With `release.enabled` true, roadmap **close** SHALL list the versions `release.sh untagged` lists (run fenced with the run login; a version is published when its tag is on origin, or with no origin remote a local tag), and offer to publish them oldest first. It SHALL NOT publish without the user's yes, and a refused or failed publish SHALL NOT block the close.

#### Scenario: Versions left untagged
- **WHEN** close runs, `v0.5.0` is the latest tag on origin and main's version history reads 0.5.0, 0.5.1, 0.6.0 with no tag on origin for the last two
- **THEN** close lists 0.5.1 and 0.6.0 and offers to publish them in that order

#### Scenario: Everything tagged
- **WHEN** every version since the latest published tag has its tag on origin, and no local tag is missing from origin
- **THEN** close offers no release

#### Scenario: No tag yet
- **WHEN** close runs in a project with no tag on origin and none locally, and main's version is 0.3.0
- **THEN** close offers to publish 0.3.0 only

#### Scenario: User declines
- **WHEN** close offers 0.6.0 and the user declines
- **THEN** no tag is created and close continues with the milestone move

#### Scenario: Releases disabled
- **WHEN** `release.enabled` is false
- **THEN** close lists no versions and offers no release
