# 0042. Skills and sw move to interface 3

- Status: accepted
- Date: 2026-11-20
- Supersedes: — (replaces only the interface-2 pin of 0040)
- Amends: 0040 (its "Interface 2" point only)

## Context

ADR 0040 pins the skills and `sw` to interface 2 and has each skill stop unless `sw version --json` reports the project's version and interface 2. The `fix-sw-port-gaps` change alters the command-line contract again, so a binary of the old interface must not be served by the new skills, and the reverse.

## Decision

- `sw version --json` reports interface 3 (`interfaceVersion` in `cli/lib/src/commands/version.dart`), and the `interface` line of `skills/specwright-pr/SKILL.md` reads 3.
- The `<sw>` paragraph of every skill that runs `sw` requires interface 3, and tells the user to update a project whose binary reports interface 2 (or 1), never an unknown-option error.
- Nothing else of ADR 0040 changes: argument entry, the UTF-8 argument contract, version-pinned resolution with its entry check, the global `--project`, and the `bash -c` transport stand as written. The separate `sw update` interface contract is unchanged.

**Rejected: keeping interface 2 with listed exceptions,** because a reader could not tell from the number which contract a binary meets.

## Consequences

- The tests and evals that pin the reported or required interface move to 3, except those that model an older project.
- A project on an older `sw` stops with "update this project" under the new skills.
- Reversal cost: low.
