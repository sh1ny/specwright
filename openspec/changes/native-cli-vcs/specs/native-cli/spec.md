# Spec Delta

## MODIFIED Requirements

### Requirement: A missing or mismatched sw stops with one message
When the project has no `VERSION`, or a version that is not `x.y.z` (with an optional pre-release or build suffix), or the binary is missing, cannot run, prints anything other than one JSON object with both fields, or reports another `version` or `interface`, the resolver SHALL print `sw missing or mismatched: rerun the install prompt` and the detail (the path and what was found) on stderr, print nothing on stdout, and exit 1. It SHALL never fall back to another version's binary, or to an `sw` on `PATH`, and SHALL never look for a binary outside `<home>/.specwright/bin/`.

#### Scenario: Binary missing
- **WHEN** `VERSION` reads `0.24.0` and `<home>/.specwright/bin/0.24.0/` holds no `sw`
- **THEN** the resolver exits 1 with the stop message and the expected path, even when `<home>/.specwright/bin/0.23.0/sw` exists

#### Scenario: Interface mismatch
- **WHEN** the binary reports `"version": "0.24.0"` and an interface other than the skills' interface
- **THEN** the resolver exits 1 with the stop message, naming both interfaces

#### Scenario: Version report is not JSON
- **WHEN** the file at the path prints text that is not one JSON object, or exits non-zero
- **THEN** the resolver exits 1 with the stop message, and prints nothing on stdout

#### Scenario: VERSION names a path
- **WHEN** `VERSION` reads `../../../planted/.specwright/bin/0.25.0` and a matching `sw` exists at that path
- **THEN** the resolver exits 1 with the stop message saying the value is not a version, and runs no binary
