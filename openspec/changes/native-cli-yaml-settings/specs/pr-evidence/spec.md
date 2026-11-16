# Spec Delta

## MODIFIED Requirements

### Requirement: Reviewer settings are read strictly everywhere
`context` SHALL read the settings file with the one reader `policy` uses. A file that reader refuses SHALL stop `context` with `bad_setting`, exit 2, naming the line, so ship, finish, cleanup and watch stop with it. A problem with a value that was read SHALL be printed as `settings_problem` (`key: why`) without exiting: watch SHALL stop before its first wait when it is set, and ship, finish and cleanup SHALL ignore it. Every `report:` example in the README and the settings template SHALL pass that reader.

#### Scenario: Double-quoted escape
- **WHEN** `report.sha_pattern` is written as `"Reviewed commit:\*\*"` in double quotes, an escape YAML does not define
- **THEN** `context` exits 2 with `bad_setting` naming the line, watch starts no wait, and ship pushes nothing

#### Scenario: Single-quoted pattern
- **WHEN** the same pattern is written as `'Reviewed commit:\*\*'`
- **THEN** `context` and `policy` both read it, and the config files they write hold the same pattern

#### Scenario: A value problem keeps ship running
- **WHEN** the settings parse and `pr.settle` holds a value it does not accept
- **THEN** `context` exits 0 with `settings_problem` naming `pr.settle`, watch starts no wait and shows it, and ship still runs
