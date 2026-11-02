# Spec Delta

## ADDED Requirements

### Requirement: Enabled packs' skills are installed with Specwright's own
The install SHALL pass each pack enabled in `specwright.yaml` to `update.sh` (`--pack <name>`). `plan` SHALL run the pack checks on them, and `stage` and `swap` SHALL stage, verify and swap each pack skill directory into every chosen skills directory with the same journal and recovery as the `specwright-*` directories.

#### Scenario: A pack's skills are installed
- **WHEN** `packs:` enables `web` with skills `web-ux` and `web-a11y`, and the user chose `.claude/skills` and `.agents/skills`
- **THEN** after the install both skill directories exist in both skills directories with the download's content, and the report lists them under pack `web`

#### Scenario: An interrupted pack install is recovered
- **WHEN** the swap stops after `web-ux` is swapped and before `web-a11y` is
- **THEN** the next run's `recover` resumes or rolls back both pack skills with the `specwright-*` targets, and no staging directory or journal is left

#### Scenario: An interrupted pack removal is recovered
- **WHEN** the swap stops after a removed pack's skill was moved to `old/` and before the next install item
- **THEN** `recover` counts the swap as started and either resumes it (the removal stays done, the rest is swapped) or rolls it back (the removed skill and the previous `packs.json` are restored)

#### Scenario: A pack that fails its checks installs nothing
- **WHEN** an enabled pack fails pack-check
- **THEN** plan exits 1 with the pack-check refusals, and no installed file changes

### Requirement: The install records which skills belong to which pack
A finished install SHALL leave `openspec/.specwright/packs.json` in the code checkout listing each enabled pack with the Specwright version, its skill names, document paths and init questions, plus a catalogue (name, description, requires, signals) of every pack in the download. It SHALL be written in the swap, after the skill renames and under the journal, and a rollback SHALL restore the previous record or its absence.

#### Scenario: The record matches the installed packs
- **WHEN** an install enables `gamedev` and `ui-prototyping` at 0.18.0
- **THEN** `packs.json` lists both packs with version `0.18.0` and each pack's skill names, and no other pack

#### Scenario: A rollback restores the old record
- **WHEN** an update that enables `web` is rolled back with `recover --rollback`
- **THEN** `packs.json` holds its previous content, or is absent when it was absent before

### Requirement: A pack that is no longer enabled is removed
When `packs.json` lists a pack that `specwright.yaml` no longer enables, the swap SHALL remove that pack's recorded skill directories from every chosen skills directory (kept in the staging `old/` until finish), and the config merge SHALL remove every line starting with `[pack:<name>] `. The pack's documents SHALL be kept.

#### Scenario: Removing a pack
- **WHEN** `web` is recorded and the user deletes it from `packs:` and reruns the install
- **THEN** `web-ux` and `web-a11y` are gone from every chosen skills directory, `config.yaml` has no `[pack:web] ` line, the project's web documents are unchanged and `packs.json` no longer lists `web`

#### Scenario: A removal that would break a requirement
- **WHEN** the user removes `ui-prototyping` while `gamedev`, which requires it, stays enabled
- **THEN** plan stops before any write with refusal `pack_requires` naming both packs

### Requirement: The install never touches a skill it did not install
A skill directory named like an enabled pack's skill, not recorded in `packs.json` for that pack, SHALL be adopted when its content equals the download's byte for byte, and otherwise SHALL make `plan` stop before any write with refusal `unmanaged_skill`, naming the directory. A recorded pack skill whose name the download no longer ships SHALL be listed in `orphans`, as `specwright-*` orphans are.

#### Scenario: A hand-copied skill with a pack skill's name
- **WHEN** `.claude/skills/gamedev-design/` exists, was copied by hand, and `gamedev` is enabled for the first time
- **THEN** plan exits 1 with refusal `unmanaged_skill` naming `.claude/skills/gamedev-design`, and the directory is unchanged

#### Scenario: A clone without the record
- **WHEN** a fresh clone has committed `.claude/skills/web-ux/`, identical to the download's, and no `packs.json`
- **THEN** plan adopts it, reports it as adopted, and the install records it for `web`

#### Scenario: A hand copy of a pack that is not enabled
- **WHEN** `.claude/skills/gamedev-design/` was copied by hand, the catalogue has `gamedev`, the project does not enable it and no record lists it
- **THEN** plan does not list it in `orphans` and the install leaves it unchanged

#### Scenario: A user's unrelated skill
- **WHEN** `.claude/skills/my-tool/` exists and no enabled pack ships `my-tool`
- **THEN** the install neither lists nor changes it

### Requirement: Pack lines are merged by prefix and verified through OpenSpec
The config merge SHALL remove each `[pack:<name>] ` line whose `<name>` is enabled now or in `packs_previous` (below), then add each enabled pack's lines once as double-quoted YAML scalars, keeping and reporting every other `[pack:` line. `update.sh pack-verify` SHALL confirm through `openspec instructions` in a scratch root that each line reaches its target once, that no line of a pack enabled before and not now does, and that every core context line is still delivered.

#### Scenario: Lines reach their artifacts
- **WHEN** `gamedev` has two `rules.proposal` lines and one `operations.apply` line and the merge ran
- **THEN** pack-verify reports `"ok": true`, having found each line once in `openspec instructions proposal` and `openspec instructions apply` output

#### Scenario: A missing, duplicated or stale line
- **WHEN** a gamedev line is missing, appears twice, or a `[pack:web] ` line is left after `web` was removed from `packs:`
- **THEN** pack-verify exits 1 naming each line, its artifact or operation and `missing`, `duplicate` or `not_enabled`, and the install does not stamp `VERSION`

#### Scenario: A removed pack's lines after a rerun past the swap
- **WHEN** the user removed `web` from `packs:`, the swap finished, the run stopped before Step 5, and the next run skips `stage` and `swap`
- **THEN** plan reports `packs_previous` with `web` from the journal, Step 5 removes every `[pack:web] ` line, and pack-verify reports any line left as `not_enabled`

#### Scenario: Hand-written lines of a pack the project never enabled
- **WHEN** `config.yaml` holds hand-written `[pack:gamedev] ` rules, the catalogue may or may not have `gamedev`, the project does not enable it and no record lists it
- **THEN** the merge keeps them, the report lists them as not managed (enable `gamedev` to have Specwright manage them), and pack-verify passes

### Requirement: The settings merge treats packs as user data
The install's settings merge SHALL treat every key under `packs.` in `openspec/specwright.yaml` as user data, like `pr.reviewers.`: never compared with the template, never added and never listed as removed.

#### Scenario: Enabled packs survive an update
- **WHEN** `specwright.yaml` has `packs.gamedev.documents.gdd` and the template has only a commented `packs:` example
- **THEN** the settings merge lists no `packs.` key as removed and leaves the entry unchanged

#### Scenario: A template key under packs
- **WHEN** a later template adds an uncommented example key under `packs:`
- **THEN** the merge does not add it to the user's file

### Requirement: The install prompt drives update-script interface 2
`update.sh` SHALL report `interface: 2` and SHALL write journal format 2; a format-1 journal is still recovered, and an older download refuses a format-2 journal as unreadable. The install prompt SHALL accept interface 2, and interface 1 only when `specwright.yaml` enables no pack and the installed `packs.json`, if any, lists no enabled pack; otherwise it SHALL stop before any write, naming the interface found and the one needed.

#### Scenario: Matching interface
- **WHEN** the prompt runs a download whose `plan` reports `interface: 2`
- **THEN** the install continues to `stage`

#### Scenario: An older download without packs
- **WHEN** the prompt installs 0.12.3 (`interface: 1`) in a project with no `packs:` key and no enabled pack in `packs.json`
- **THEN** the install continues as before this change and writes no pack state

#### Scenario: An older download with packs enabled
- **WHEN** the prompt runs a download whose `plan` reports `interface: 1`, and `packs:` enables `web` or the installed `packs.json` still lists `web` as enabled
- **THEN** the prompt stops before `stage`, says that download predates packs (remove the packs with a 0.16.0 or later release first) and names interfaces 1 and 2, and no file changes

### Requirement: Pack documents are created by an idempotent step after the stamp
`update.sh pack-docs` SHALL create each missing pack document from its template, never overwrite one, and report each as `created` or `kept`. It SHALL depend on no journal, so a rerun after an interruption completes it; the prompt SHALL run it after the stamp.

#### Scenario: Documents after a finished install
- **WHEN** the stamp is written and `docs/game/gdd.md` does not exist
- **THEN** pack-docs creates it from the gamedev template and reports `created`

#### Scenario: Interrupted document creation
- **WHEN** pack-docs stops after creating one of two documents and is run again
- **THEN** the first is reported `kept` with its content unchanged and the second `created`

### Requirement: The previously enabled packs come from the start of the update
`stage` SHALL write the enabled packs of `packs.json` as it was before the update into the journal as `prev_packs`, and `plan` SHALL report `packs_previous`: from a pending journal when there is one, else from `packs.json`. Step 5 and `pack-verify` SHALL use `packs_previous`, never the `packs.json` the swap wrote.

#### Scenario: An uninterrupted update that removes a pack
- **WHEN** `packs.json` lists `web` enabled, the user removes `web` from `packs:` and runs the install
- **THEN** plan reports `packs_previous` `["web"]`, and after the swap Step 5 still removes the `[pack:web] ` lines although the new `packs.json` no longer lists `web`

#### Scenario: No previous record
- **WHEN** a project updates from 0.13.0, which wrote no `packs.json`
- **THEN** plan reports `packs_previous` as an empty list, and Step 5 removes no `[pack:` line of a pack that is not enabled now
