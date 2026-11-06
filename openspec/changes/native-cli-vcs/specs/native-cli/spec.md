# Spec Delta

## ADDED Requirements

### Requirement: The resolver reads only a version from VERSION
The resolver SHALL accept the project's `VERSION` only when it is `x.y.z`, with an optional pre-release or build suffix. Any other value SHALL stop it with `sw missing or mismatched: rerun the install prompt` and a detail saying the value is not a version, before it builds a path or runs a binary, so it never looks outside `<home>/.specwright/bin/`.

#### Scenario: VERSION names a path
- **WHEN** `VERSION` reads `../../../planted/.specwright/bin/0.25.0` and a matching `sw` exists at that path
- **THEN** the resolver exits 1 with the stop message saying the value is not a version, prints nothing on stdout, and runs no binary
