# Spec Delta

## MODIFIED Requirements

### Requirement: The download ships the ui-prototyping, gamedev and godot packs
The Specwright download SHALL hold `packs/ui-prototyping/`, `packs/gamedev/` and `packs/godot/`, and `sw update pack-check --download <tree>` over the download SHALL accept all three. `gamedev` SHALL require `ui-prototyping`. `ui-prototyping` and `godot` SHALL require no pack.

#### Scenario: The shipped packs pass pack-check
- **WHEN** `sw update pack-check --download <repo>` runs over the repository's own `packs/`
- **THEN** it exits 0 and reports `ui-prototyping`, `gamedev` and `godot`, each with `"ok": true`

#### Scenario: gamedev without its shared pack
- **WHEN** a project's `packs:` enables `gamedev` but not `ui-prototyping`
- **THEN** the install stops before any write with refusal `pack_requires` naming `gamedev` and `ui-prototyping`

#### Scenario: godot on its own
- **WHEN** a project's `packs:` enables only `godot`
- **THEN** plan reports no `pack_requires` refusal and installs only `godot-engine`
