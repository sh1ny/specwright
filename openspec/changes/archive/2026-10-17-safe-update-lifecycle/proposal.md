# Proposal

## Why

An update can break the work it lands on (#36). The install/update prompt (README Step 4) deletes each installed `specwright-*` skill directory before copying the new one, and it overwrites the schema in place. As a result:

- an interrupted update leaves a loaded skill whose scripts are gone;
- a change in flight that was planned under one workflow is picked up by skills and a schema from another;
- in a shared planning store, one project's update replaces the schema that every other project of the store uses, while the version stamp lives only in that project's code checkout.

This is change 4 of milestone **M3 - Distribution** (release 0.6.0). It serves these exit criteria:

- an eval interrupts an update at every step before the swap, shows the previous version still runnable each time, and the interrupted update then resumes or rolls back cleanly;
- an update across a workflow change with a change in flight refuses, or proceeds only after preserving or migrating that change, which then still validates and ships;
- with two projects sharing one store, an update of one leaves the other unaffected, and the store records its schema version and owner;
- a dogfood project updates from one tagged release to the next with a change in flight, and that change still ships (user-verified);
- every issue is closed by a merged PR with a regression test in `evals/`, the eval suites pass, and the change ships as its own release.

It builds on the release tags from #28 (`add-release-workflow`, 0.5.0).

## What Changes

- **Staged update, swapped in last.** A new script, `scripts/update.sh`, runs from the downloaded copy and takes over the file work of install Step 4. It stages every new skill directory, agent file and the schema next to its target, verifies the staged copy, and only then swaps it in. Before the swap the installed version is untouched and runnable. The swap is recorded step by step in a journal. A rerun after an interruption either resumes the swap or rolls it back to the previous version, and says which it did. The previous copy is removed only after the version stamp is written.
- **Tagged releases.** The prompt downloads the latest release tag (`v<version>`) by default, or a version the user names. It falls back to `main` only when the user asks for it or no tag exists, and the report says which ref was installed.
- **Workflow updates with changes in flight.** An update is a workflow update when its minor or major version differs from the installed one. A patch update needs no validation of changes in flight. Before a workflow update swaps anything in, the script validates every change in flight against the staged schema: change directories in the working tree, and local change branches whose change main has not archived. It validates again at the swap. Changes seen only on a remote branch are reported as warnings. When all of them validate, the update proceeds and lists them. When any fails, it refuses before the swap, naming the change and the validation error, and nothing is written.
- **Restart notice.** After a swap, the report says that running agent sessions still hold the previous skills and must be restarted before they continue a change. It names the previous and the new version.
- **Store ownership** (**BREAKING** for a shared store). A store records its schema version and its owner, the code repo that installed the schema, in `<root>/openspec/.specwright/STORE`. Only the owner's update replaces the store's schema and `config.yaml` context, and only while the store is on its main with no change in progress. While a change holds the store, a patch with an unchanged schema updates only the project's own files, and any other update waits. The owner's workflow update is also refused while a change of another project is in flight in the store. Any other project's update installs only its code-side files (skills, agents, `specwright.yaml`) and leaves the store as it is. When that project's minor version no longer matches the store's, `specwright-branch` refuses to start a change there and says to update that project. An interrupted store swap holds the store's gate lock until the update is rerun from the same checkout. A store with no `STORE` record is claimed by the first project that updates it, and the report says so.
- **Regression coverage.** Script tests in a new `evals/update/` suite:
  - an interruption injected at every step before the swap, and at every step of the swap;
  - resume and rollback after an interruption;
  - a workflow update over a change that validates and over one that does not;
  - two projects sharing one store, where only the owner replaces the schema and the other project's change in flight still validates.

  Text tests cover the prompt's new steps and the gate's version check.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `install-update`: Step 4 becomes a staged, journaled swap through `scripts/update.sh`, with resume and rollback. The prompt installs a release tag by default. A workflow update validates the changes in flight and refuses on any failure. The report adds the restart notice.
- `planning-stores`: the install procedure records the store's schema version and owner. Only the owner replaces the store schema, and only when no other project's change is in flight. `specwright-branch` refuses to start a change when the project's minor version differs from the store's.

## Impact

- New `scripts/update.sh` at the repo root. It runs from the download and is not copied into projects. It needs `bash`, `git` and `python3`, which the install's core prerequisites already require.
- `README.md`:
  - install Steps 3 (tag selection), 4 (the script), 7 (stamp, then cleanup of the previous copy) and 8 (restart notice, ref installed, store owner);
  - the Stores section (ownership);
  - an ADR for staged updates and store ownership.
- `skills/specwright-branch/SKILL.md`: the store version check in the gate, and the message for a lock held by an update.
- `skills/specwright-roadmap/SKILL.md`: the same update-lock message in its store lock step.
- New files written into projects: `openspec/.specwright/update.json`, a journal that exists only while an update is unfinished, and `<root>/openspec/.specwright/STORE` in a store. The journal is recoverable working state, kept in the project rather than `~/.cache` (an exception to ADR 0003). `STORE` is a committed per-store state file, a second departure from ADR 0003 that the new ADR records. `openspec/.specwright/VERSION` keeps its format.
- New `evals/update/` suite; text tests in `evals/git-workflow/test_instructions.py`.
- A new workflow step and a new file format, so the release is a minor version (0.6.0). `VERSION`, the README badge and `metadata.version` in every `skills/*/SKILL.md` move to 0.6.0.
- Adopters with a shared store: the first project that updates after 0.6.0 becomes the store's owner. Until other projects update to the same minor version, `specwright-branch` refuses to start a change from them.
