# Spec Delta

## ADDED Requirements

### Requirement: An install whose VCS steps need a missing sw says so
When the installed version's `vcs.sh` runs `sw` (0.25.0 or newer) and, after the install, the resolver finds no matching `sw` for the project, the Step 8 report SHALL say that every branch, commit and finish step stops with `sw_missing` until one is placed, and SHALL name a tagged install and the contributor bootstrap in `CONTRIBUTING.md`. Otherwise it SHALL add no such warning.

#### Scenario: main install with no binary
- **WHEN** the user installs `main` at 0.25.0 or newer, and `<home>/.specwright/bin/<that version>/` holds no matching `sw`
- **THEN** the Step 8 report holds `sw not installed: main has no release binaries`, says VCS steps stop with `sw_missing`, and names a tagged install and the `CONTRIBUTING.md` bootstrap

#### Scenario: main install with a matching binary already placed
- **WHEN** the user installs `main` and the resolver accepts an `sw` already placed for that version
- **THEN** the Step 8 report holds no `sw_missing` warning

#### Scenario: Older tag whose scripts need no sw
- **WHEN** the user installs `v0.23.0`, which ships no `sw` and whose `vcs.sh` does not run one
- **THEN** the install completes as before and the Step 8 report holds no `sw_missing` warning

#### Scenario: Tagged install with sw placed
- **WHEN** a release tag's `sw-install` returns `installed`, `replaced` or `kept`
- **THEN** the Step 8 report holds no `sw_missing` warning

### Requirement: Contributors place a tree-built sw with one task
`mise run install-sw` in a Specwright checkout SHALL build `sw` from the tree and place it at `<home>/.specwright/bin/<tree VERSION>/sw[.exe]` (`<home>` as the resolver finds it), only after `sw-path.sh --file <built binary> --version <tree VERSION>` accepts the build, and SHALL replace an existing file there only by a rename. It SHALL print the placed path.

#### Scenario: Build placed
- **WHEN** `mise run install-sw` runs in a checkout whose `VERSION` reads `0.25.0`
- **THEN** `<home>/.specwright/bin/0.25.0/sw[.exe]` exists, `sw-path.sh --code <a project at 0.25.0>` prints it, and the task prints that path

#### Scenario: Build fails the check
- **WHEN** the built binary reports another version or interface than the tree's
- **THEN** the task exits non-zero, names the mismatch, and leaves any existing file under `<home>/.specwright/bin/0.25.0/` unchanged
