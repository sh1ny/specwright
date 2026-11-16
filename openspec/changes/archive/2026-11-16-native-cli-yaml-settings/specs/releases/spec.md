# Spec Delta

## MODIFIED Requirements

### Requirement: A misreadable settings line stops a release
Release subcommands that read `openspec/specwright.yaml` SHALL stop with `bad_settings`, exit 1, naming the line, when the settings reader refuses the file, a plain `yes` or `no` value included, before any git call, network call or write. `notes` reads no settings and SHALL be unaffected.

#### Scenario: Settings read as written
- **WHEN** `openspec/specwright.yaml` holds the shipped `release:` block with `enabled: true` and `release.sh check` runs
- **THEN** check exits 0 and reports the version

#### Scenario: Misreadable line
- **WHEN** `openspec/specwright.yaml` has a line under `release:` indented with a tab, or a `release:` key given twice, and `release.sh publish --version 0.5.0` runs
- **THEN** it exits 1 with `error: bad_settings` naming the line, and no tag is created, pushed or released

#### Scenario: A yes for enabled
- **WHEN** `release.enabled` is written `yes` and `release.sh publish --version 0.5.0` runs
- **THEN** it exits 1 with `error: bad_settings` naming the line, `true` and `false`, and no tag is created, pushed or released

#### Scenario: Notes ignores the settings
- **WHEN** the same settings file is present and `release.sh notes --proposal proposal.md` runs on a valid proposal
- **THEN** it exits 0 and prints the section's summary and items
