# Spec Delta

## ADDED Requirements

### Requirement: Watch offers a release after an agent merge
With `release.enabled` true, after a confirmed agent merge and its cleanup, watch SHALL read `release.sh untagged` and offer `specwright-release` publish for each listed version oldest first, or with `release.auto` publish them oldest first, stopping at the first failure, before the roadmap offer. A publish failure SHALL NOT undo the merge or the cleanup.

#### Scenario: Unattended agent merge with auto release
- **WHEN** `pr.merge` is `agent`, `release.auto` is true, the merged PR moved `VERSION` to 0.5.0, and cleanup finished
- **THEN** watch runs publish, `v0.5.0` is on origin at the merge commit, and the roadmap mode is then offered

#### Scenario: Offer without auto
- **WHEN** `release.auto` is false and the merged version has no tag
- **THEN** watch offers publish for that version and creates no tag until the user accepts

#### Scenario: An earlier version was left untagged
- **WHEN** `release.auto` is true, 0.5.0 was never published and the agent merge moved `VERSION` to 0.5.1
- **THEN** watch publishes `v0.5.0`, then `v0.5.1`

#### Scenario: Cleanup stopped
- **WHEN** cleanup stops because `git pull --ff-only` on main failed
- **THEN** no release is offered or run, because cleanup did not finish

#### Scenario: Publish fails after the merge
- **WHEN** `release.auto` is true and publish exits non-zero
- **THEN** the PR stays merged, the report names the publish error and says a re-run of publish resumes it
