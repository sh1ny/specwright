# Spec Delta

## ADDED Requirements

### Requirement: A review after the archive commit reads the archived artifacts
When a pre-ship review runs and the change's directory under `<P>/changes/<change>/` no longer exists because the archive moved it, the review SHALL be given the archived change's proposal, design, tasks and specs under `<P>/changes/archive/<archived-name>/`, on every route, CLI and subagent alike. While the active directory exists, the review SHALL use it.

#### Scenario: Recovery review after archive
- **WHEN** a `finish: local` gate reports `missing` after the archive commit (the review record is on another machine), and the recovery pre-ship review runs
- **THEN** the reviewer's input names the four artifact paths under `<P>/changes/archive/<date>-<change>/`, each of which exists, and none under `<P>/changes/<change>/`

#### Scenario: Subagent route after archive
- **WHEN** the selected route is `subagent` and the change is archived on the branch
- **THEN** the preflight output lists the archived artifact paths, and the dispatch passes those paths to the reviewer

#### Scenario: Active change
- **WHEN** a pre-ship review runs before archive, with `<P>/changes/<change>/` present
- **THEN** the input names the four artifact paths under `<P>/changes/<change>/`

#### Scenario: Several archives of the same name
- **WHEN** the active directory is gone and both `2026-09-01-<change>` and `2026-10-14-<change>` exist under the archive
- **THEN** the review is given the directory that the change's own archive commit in the reviewed range added, never the older one

#### Scenario: No artifacts anywhere
- **WHEN** neither the active directory nor any archived directory of the change exists
- **THEN** the input names the active paths as before, so the reviewer reports them as missing; no archived directory of another change is used
