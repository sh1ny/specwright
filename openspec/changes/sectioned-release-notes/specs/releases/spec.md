## MODIFIED Requirements

### Requirement: Notes list the changes merged since the previous release
Notes for V SHALL list every change whose merge lands after the previous release commit and up to V's release commit: a change whose archived proposal has a valid `## Release Notes` section by that section's items, any other change by its change name, the first sentence of its archived proposal's Why, and its PR number when main's commit subject names one. The previous release commit SHALL be the release commit of the highest lower version whose tag exists locally or on origin, else the first-parent commit where the primary version file took the value before V.

#### Scenario: One change in the range
- **WHEN** publish runs for 0.4.2 and only `2026-10-15-pin-openspec-version` was archived between the 0.4.1 and 0.4.2 release commits, and its proposal has no `## Release Notes` section
- **THEN** the notes list `pin-openspec-version`, its first Why sentence and `#90`, and no other change

#### Scenario: Several changes in the range
- **WHEN** two changes were archived between the previous release commit and V's
- **THEN** the notes list both, in main's first-parent order

#### Scenario: No change in the range
- **WHEN** the range holds no archived change (only a roadmap `docs/close-*` merge)
- **THEN** the notes say no change was archived in this release and publish continues

#### Scenario: Backfill in a clone without the tags
- **WHEN** `v0.1.0` and `v0.4.0` exist only on origin (the clone never fetched tags) and publish runs for 0.3.0
- **THEN** the range starts at 0.1.0's release commit, and the notes list the 0.2.0 and 0.3.0 changes

#### Scenario: Backfill with no earlier tag
- **WHEN** no tag exists and publish runs for 0.4.1
- **THEN** the range starts at the commit where `VERSION` first read 0.4.0, and the notes list `fix-m2-gaps` with `#89`

#### Scenario: No change in the range has a section
- **WHEN** every change in V's range was archived without a `## Release Notes` section
- **THEN** the notes are byte-for-byte what they were before sections existed: `Changes in <tag>:`, then one `- <name> (#<pr>): <why>` line per change

## ADDED Requirements

### Requirement: A Release Notes section has one format
A proposal's `## Release Notes` section SHALL run to the next `##` heading or the end of the file and hold a summary of at most 600 characters, then one or more of the headings `### Added`, `### Changed`, `### Fixed` and `### Removed`, each at most once, each followed only by list items. Each item SHALL be at most 500 characters. Any other content SHALL make the section invalid.

#### Scenario: Valid section
- **WHEN** a section holds a one-sentence summary, `### Fixed` with two items and `### Added` with one
- **THEN** it parses to that summary and three items under `fixed` and `added`

#### Scenario: Unknown heading
- **WHEN** a section has a `### Security` heading
- **THEN** it is invalid, and the error names `Security` and its line

#### Scenario: Prose under a heading
- **WHEN** a line that is neither a list item, an indented continuation nor blank follows `### Changed`
- **THEN** it is invalid, and the error names that line

#### Scenario: No summary or no item
- **WHEN** a section starts with `### Added`, or has a summary and no list item
- **THEN** it is invalid, and the error says which is missing

#### Scenario: Item over the limit
- **WHEN** one item is 501 characters long after whitespace is collapsed
- **THEN** the section is invalid, and the error names the item's line

### Requirement: A Release Notes section tolerates comments, blank lines and wrapped items
Before parsing, HTML comments (`<!-- ... -->`, also across lines) SHALL be removed. Blank lines SHALL be allowed anywhere in the section. The summary SHALL be all text before the first `###` heading, joined with single spaces. A list item SHALL start with `-`, `*` or `+` and a space; a following line indented by at least one space or tab SHALL be joined to it.

#### Scenario: Template guidance comment left in
- **WHEN** a section still holds the template's `<!-- ... -->` guidance between the heading and the summary, and under `### Added`
- **THEN** it parses as if the comments were absent

#### Scenario: Only a comment
- **WHEN** a section holds nothing but the template's comment
- **THEN** it is invalid, and the error says the summary is missing

#### Scenario: Wrapped item
- **WHEN** an item's text continues on the next line, indented by two spaces
- **THEN** the two lines are one item, joined with a single space

#### Scenario: Unindented line after an item
- **WHEN** an unindented line that is not a list item follows an item under `### Fixed`
- **THEN** the section is invalid, and the error names that line

#### Scenario: Two-paragraph summary
- **WHEN** the summary is two sentences on two lines separated by a blank line
- **THEN** the summary is both sentences joined by one space

### Requirement: Notes open with the release summary and group the items
When at least one change in V's range has a valid section, the notes SHALL open with the release summary (next requirement), then list `Added:`, `Changed:`, `Fixed:` and `Removed:` in that order, each with every item from every change's section under that heading, in the changes' order, leaving out a heading with no item. Changes without a valid section SHALL follow under `Changes:`, one `- <name> (#<pr>): <why>` line each.

#### Scenario: One change with a section
- **WHEN** the range holds only `fix-m4-gaps` (#129), whose section has a summary and eight `Fixed` items
- **THEN** the notes are the summary, a blank line, `Fixed:` and the eight items, and nothing under `Added:`, `Changed:`, `Removed:` or `Changes:`

#### Scenario: Exact layout of several groups
- **WHEN** the range holds `old-x` (#7, no section) then `new-y` (#8), whose section has summary `S.`, `### Fixed` item `F (#5)` and `### Added` item `A`
- **THEN** the notes are exactly `S.`, blank, `Added:`, `- A (#8)`, blank, `Fixed:`, `- F (#5)`, blank, `Changes:`, `- old-x (#7): <why>`, with one blank line between groups and no trailing blank line

#### Scenario: Two changes with sections
- **WHEN** the range holds `add-a` then `add-b`, both with sections, and both have `Added` items
- **THEN** the notes open with `add-b`'s summary, and `Added:` lists `add-a`'s items before `add-b`'s

#### Scenario: A change with a section and an older one without
- **WHEN** the range holds `old-x` (no section) then `new-y` (a section with one `Changed` item)
- **THEN** the notes are `new-y`'s summary, `Changed:` with its item, then `Changes:` with `- old-x (#<pr>): <why>`

#### Scenario: Many items
- **WHEN** the sections in the range hold 170 items together
- **THEN** the notes list the first 150 in group and change order, the line `…and 20 more items` follows the 150th item directly with no blank line, a group whose items all fall past the 150th is left out, and `Changes:` (when present) follows after one blank line

#### Scenario: More than 100 changes in the range
- **WHEN** the range holds 120 changes, only the last of which (the bumping change) has a section
- **THEN** the notes open with that change's summary and list its items, and `Changes:` lists the first 100 of the other 119 by name only, then `…and 19 more`

### Requirement: The release summary comes from the bumping change
The release summary SHALL be the summary of the change in V's range whose archived `tasks.md` has a ticked task running `release.sh bump --to <V>` and whose section is valid. When no change or more than one matches, it SHALL be the summary of the last change with a valid section in the notes' order.

#### Scenario: Bumping change archived with another in the same commit
- **WHEN** the release commit adds the archives `2026-11-02-b-bump` (its `tasks.md` has `- [x] 3.1 release.sh bump --to 0.9.0`) and `2026-11-02-c-other`, both with valid sections, and `c-other` sorts last
- **THEN** the notes open with `b-bump`'s summary

#### Scenario: No change has a bump task
- **WHEN** no archived `tasks.md` in the range has a ticked `release.sh bump --to 0.9.0` task, and `add-a` then `add-b` have valid sections
- **THEN** the notes open with `add-b`'s summary

#### Scenario: Bumping change without a valid section
- **WHEN** the change with the bump task has no section, and an earlier change in the range has one
- **THEN** the notes open with the earlier change's summary

### Requirement: An item without a reference gets its change's PR
An item that names no issue or PR (`#<n>` or `<owner>/<repo>#<n>` outside a code span) SHALL be listed with ` (#<pr>)` appended, `<pr>` being its change's PR from main's commit subject or the store-backed code-merge proof. With no PR known, the item SHALL be listed as written.

#### Scenario: Item without a reference
- **WHEN** `add-a` merged as #140 and its section has the item `New --dry-run flag`
- **THEN** the notes list `- New --dry-run flag (#140)`

#### Scenario: Item with its own reference
- **WHEN** an item reads `Bounded tag push (#111)`
- **THEN** it is listed as written, without `(#140)` appended

#### Scenario: Reference only inside a code span
- **WHEN** an item reads ``Parse `#123` comments`` and its change merged as #140
- **THEN** it is listed with ` (#140)` appended

#### Scenario: Local merge with no PR
- **WHEN** a `finish: local` change whose merge subject names no PR has the item `New --dry-run flag`
- **THEN** it is listed as `- New --dry-run flag`

### Requirement: An invalid section falls back to the Why line
When an archived proposal's `## Release Notes` section is invalid, or the proposal is over 64 KB, `status` and `publish` SHALL list that change under `Changes:` as a change without a section, with a `warnings` entry naming the change and the first error. It SHALL NOT stop either subcommand. `warnings` describe the derived notes: publish reports them only when it creates the tag, and `[]` when the tag exists.

#### Scenario: Unknown heading in an archived proposal
- **WHEN** publish runs for V and one change's archived section has a `### Security` heading
- **THEN** the tag is created, the notes list that change under `Changes:` with its Why line, and the JSON's `warnings` names the change and `Security`

#### Scenario: Valid sections
- **WHEN** every section in the range is valid
- **THEN** `warnings` is an empty list

#### Scenario: Proposal over the read bound
- **WHEN** a change's archived `proposal.md` is 70 KB, with a valid section in its first 64 KB
- **THEN** that change is listed under `Changes:`, and `warnings` names it and the 64 KB limit

#### Scenario: Publish re-run after the tag exists
- **WHEN** publish runs again for V after its tag was created, and an archived section in the range is invalid
- **THEN** the notes reported are the tag's message, and `warnings` is `[]`

### Requirement: One proposal's section can be checked before it merges
`release.sh notes --proposal <file>` SHALL parse that file's section and print its summary, its items by heading and the line the notes would give each item (an unreferenced item's line ending in the literal ` (#<pr>)`), with no git or network call and whether or not releases are enabled. A valid section SHALL exit 0. An invalid one SHALL exit 1 with `release_notes_invalid` and every error, and a file without the section SHALL exit 1 with `no_release_notes`.

#### Scenario: Valid section
- **WHEN** the bump task runs `notes --proposal openspec/changes/add-a/proposal.md` on a valid section
- **THEN** it exits 0, and its JSON holds the summary and each item under its heading

#### Scenario: Two errors
- **WHEN** the section has an unknown heading and an item over 500 characters
- **THEN** it exits 1 with `release_notes_invalid` and both errors, each with its line

#### Scenario: No section
- **WHEN** the proposal has no `## Release Notes` heading
- **THEN** it exits 1 with `no_release_notes`

#### Scenario: Missing file
- **WHEN** `--proposal` names a file that does not exist
- **THEN** it exits 2 with a usage error naming the path

#### Scenario: File over the read bound
- **WHEN** `--proposal` names a 70 KB file whose first 64 KB hold a valid section
- **THEN** it exits 1 with `release_notes_invalid` and an error naming the 64 KB limit

### Requirement: The bump task writes the release summary
With `release.enabled` true, the task that bumps the version SHALL rewrite the summary of the bumping change's section to describe the whole release, and check it with `release.sh notes --proposal`. The proposal instruction SHALL ask for the section when `release.enabled` is true, and apply SHALL keep its items current with what the change ships.

#### Scenario: Bump task in a project with releases
- **WHEN** the tasks of a change in a project with `release.enabled: true` are written
- **THEN** the last group's bump task names rewriting the section's summary for the release and verifies it with `release.sh notes --proposal`

#### Scenario: Releases off
- **WHEN** `release.enabled` is false and a proposal is written
- **THEN** the instruction does not ask for a `## Release Notes` section, and no task checks one
