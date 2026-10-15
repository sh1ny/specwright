# Spec Delta

## ADDED Requirements

### Requirement: Finish offers a release once the change is on main
With `release.enabled` true, once the change is on main (after the local merge, or after the PR is merged and cleanup finished), `specwright-finish` SHALL read `release.sh untagged`. It SHALL offer `specwright-release` publish for each listed version oldest first, or with `release.auto` publish them oldest first, stopping at the first failure, before the roadmap offer. With none listed, or releases disabled, it SHALL NOT mention a release.

#### Scenario: Untagged version after a PR merge
- **WHEN** releases are enabled, `release.auto` is false, the merged PR moved `VERSION` to 0.5.0 and no `v0.5.0` tag exists
- **THEN** finish offers publish for 0.5.0, then the roadmap mode

#### Scenario: Auto release
- **WHEN** releases are enabled with `release.auto` true and the version on main has no tag
- **THEN** finish runs publish without asking, reports its result, then offers the roadmap mode

#### Scenario: An earlier version was left untagged
- **WHEN** 0.5.0 was merged and never published, and the PR that moved `VERSION` to 0.5.1 is merged
- **THEN** finish offers publish for 0.5.0, then 0.5.1

#### Scenario: Version already tagged
- **WHEN** the merged change did not bump the version and the current version already has its tag
- **THEN** finish offers no release

#### Scenario: Releases disabled
- **WHEN** `release.enabled` is false or missing
- **THEN** finish's report and offers contain no release step

#### Scenario: Auto publish fails
- **WHEN** `release.auto` is true and publish exits non-zero
- **THEN** finish reports the publish error, keeps the merge and cleanup it already did, and still offers the roadmap mode

### Requirement: Local finish publishes no tag without a push decision
In `finish: local` the merge is never pushed, so the release commit is not on origin. Finish SHALL NOT run publish on its own in local mode, even with `release.auto` true. It SHALL report that the version is untagged and that publish runs once main is pushed.

#### Scenario: Local merge with auto release
- **WHEN** `finish` is `local`, `release.auto` is true and the local merge moved the version to 0.5.0
- **THEN** no tag is created or pushed, and the report says `v0.5.0` can be published after `main` is pushed

#### Scenario: Local merge after main was pushed
- **WHEN** the user later pushes main and asks for the release
- **THEN** publish finds the release commit on `origin/main` and tags it
