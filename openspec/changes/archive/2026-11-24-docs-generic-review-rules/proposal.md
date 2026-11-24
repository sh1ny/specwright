# Proposal

## Why

The public standing-rules setup instructions describe one team's rollout instead of showing how any project can write its own criteria. This patch is maintenance for M9 (Adoption and configuration); the team's rollout stays outside Specwright.

## What Changes

- Give the README and shipped settings template the same neutral example: `rules/review-criteria.md`. Tell readers to create and commit their own file and declare it under `review.standing_rules`.
- Remove the team-specific migration paragraph from the README. The v0.40.0 GitHub release body was corrected separately without changing the tag.
- Ship the documentation correction as v0.40.1; archive this change in the patch PR so release notes are present at the release commit.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. The change updates examples and prose but does not change any requirement, so `skip_specs: true` applies.

## Impact

- `README.md`, `templates/openspec/specwright.yaml`, and the configured release version files.
- No configuration, review behavior, or adopting repository changes.

## Release Notes

The standing-rules documentation now shows how any project can declare and version its own review criteria. No configuration or behavior changes are required.

### Fixed

- The README and settings template use a neutral standing-rules example: create `rules/review-criteria.md` with your project's own criteria, commit it, and list its repository-relative path under `review.standing_rules` in `openspec/specwright.yaml`.
