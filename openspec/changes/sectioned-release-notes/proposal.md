# Proposal

## Why

Release notes today say why a change was needed, not what shipped (#130). `release.sh` writes one line per archived change, taken from the first sentence of its proposal's `## Why`, so v0.8.1 reads "fix-m4-gaps (#129): M4 closed with eight known gaps filed as issues." To learn what it fixed, a reader opens the PR and every issue. This change serves M5 (Commits and VCS backends) and its exit criteria: notes written by `release.sh` open with the release summary, then list every item under its `Added`, `Changed`, `Fixed` or `Removed` heading with its issue or PR reference, and a change without the section falls back to its Why line under `Changes`. It ships as 0.9.0, its own release.

## What Changes

- A `## Release Notes` section in `proposal.md`: a one- or two-sentence summary, then `### Added`, `### Changed`, `### Fixed` and `### Removed` lists (empty ones left out), each item naming its issue or PR (`#123`). The schema's proposal instruction and template ask for it when `release.enabled` is true; it is optional otherwise.
- The section is written with the proposal and kept current during apply: a task that changes what the change ships updates the section in the same commit. An edit confined to the section does not void the design review verdict; any other proposal edit still does.
- The pre-ship review checks the section against the diff: an item the diff does not ship, or a user-visible change with no item, is a `docs` finding.
- `release.sh` builds the notes from the sections of every change in the release: the release summary first, then one `Added:`, `Changed:`, `Fixed:` and `Removed:` list each, merged across changes in main's first-parent order. An item without its own reference gets its change's PR. A change without a section (every change archived before this one) is listed under a final `Changes:` heading with its Why line. A release in which no change has a section gets today's notes unchanged, so backfills of older versions still work.
- The release summary is the summary of the change that bumps the version, found by its ticked `release.sh bump --to <version>` task (else the last change with a section). The version-bump task writes it to describe the whole release, so the tag message is rebuilt from the repo alone.
- `release.sh notes --proposal <file>` parses one proposal's section and reports its summary, items and any error, so apply and the bump task can check the section before it merges. A section that does not parse makes `status` and `publish` fall back to that change's Why line and name the change in a warning; it never stops a release.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `releases`: notes come from the changes' Release Notes sections (summary, grouped items, PR added to unreferenced items) with the Why line as the fallback; the section's format and the `notes --proposal` check are specified.
- `preship-review`: the pre-ship review checks a change's Release Notes section against its diff.
- `design-review-gate`: an edit confined to the proposal's Release Notes section does not void the design review verdict, so apply can keep the section current.

## Impact

- Code: `skills/specwright-release/scripts/release.sh` (section parser, `build_notes`, the `notes` subcommand, the header comment).
- Workflow text: `schemas/specwright/schema.yaml` (proposal instruction, the review instruction's voiding rule, tasks rule for the bump task, apply instruction), `schemas/specwright/templates/proposal.md` and `schemas/specwright/templates/review.md` (its voiding comment); `skills/specwright-release/SKILL.md` (format, summary, `notes`); `skills/specwright-review/references/brief.md` (the check); `skills/specwright-commit/SKILL.md` (keep the section current).
- Architecture: `openspec/architecture.md`: the `specwright-release` component row (the `notes` subcommand, `warnings`), the "Release publish" Resource Bounds row (150 items, the 1 000-change parse bound, the size pass), the "Releases" data-format bullet (the `## Release Notes` section format) and the in-force index row for the new ADR 0015 (see design).
- Tests: `evals/release` (parser, notes, fallback, store-backed notes), `evals/git-workflow` text tests where they pin the schema or skill wording.
- Compatibility: notes for a release made only of changes without a section are byte-for-byte today's, so backfills of older versions do not change. Published tags are never rewritten (ADR 0010); only new tags get the new shape.

## Release Notes

Release notes now say what each release shipped: a summary, then the items each change added, changed, fixed or removed, with their issue or PR references.

### Added
- A `## Release Notes` section in every proposal of a project with releases on, written with the proposal, kept current during apply and checked against the diff in the pre-ship review (#130)
- `release.sh notes --proposal <file>` checks one proposal's section and prints what the notes will hold (#130)

### Changed
- `release.sh` builds the tag message and GitHub release body from the changes' sections, grouped under `Added`, `Changed`, `Fixed` and `Removed`, with the release summary first; changes without a section keep their Why line under `Changes` (#130)
