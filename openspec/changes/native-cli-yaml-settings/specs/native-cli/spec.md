# Spec Delta

## MODIFIED Requirements

### Requirement: The shipped dependencies stay hook-free and carry their notices
`sw` SHALL stay one single-file executable with no dependency that declares build hooks, and SHALL ship a third-party notice covering every package in its resolved runtime closure.

#### Scenario: Current dependency set
- **WHEN** the dependency check runs after `dart pub get`
- **THEN** no package in the closure declares build hooks, and the notice names each package in the closure with its licence text

#### Scenario: The settings parser joins the closure
- **WHEN** `yaml` is a runtime dependency of `cli/` and the dependency check runs after `dart pub get`
- **THEN** the check passes, and the notice names `yaml` and each package it brings into the runtime closure, `collection`, `source_span` and `string_scanner` among them, with its licence text

#### Scenario: A hook package enters the lock file
- **WHEN** a package with build hooks enters `cli/pubspec.lock`
- **THEN** the dependency check fails naming that package

#### Scenario: A dependency without a notice
- **WHEN** the resolved closure holds a package the notice does not name
- **THEN** the notice check fails naming that package
