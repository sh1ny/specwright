# Spec Delta

## Purpose

Lets a project opt in to domain packs: bundles of skills, artifact rules, context lines, project documents and init questions that add to Specwright's workflow without removing a step or relaxing a gate.

## ADDED Requirements

### Requirement: A pack is a directory with a JSON manifest
A pack SHALL be a directory `packs/<name>/` in the Specwright download holding `pack.json`. The manifest SHALL be a JSON object with `format: 1`, `name` equal to the directory name, and `description`; the optional fields SHALL be `requires`, `skills`, `context`, `rules`, `operations`, `documents`, `init` and `signals`. Any other field, or `source`, SHALL be refused: v1 installs only packs shipped in the download.

#### Scenario: A valid manifest is accepted
- **WHEN** `update.sh pack-check` reads `packs/web/pack.json` with `format: 1`, `name: "web"`, a description and a `rules.proposal` list
- **THEN** it reports pack `web` with `"ok": true` and no refusal

#### Scenario: Malformed or unsupported manifests are refused
- **WHEN** a manifest is not valid JSON, has `format: 2`, names `webapp` in `packs/web/`, or sets `source`
- **THEN** pack-check exits 1 with a refusal naming the pack and the code `manifest_invalid`, `format_unsupported`, `name_mismatch` or `external_pack_unsupported`

### Requirement: Documents, questions and signals are checked before release
Each `documents` entry's template SHALL exist in the pack and its default path SHALL be relative without `..`; `init.questions` and `signals` SHALL be lists of non-empty single-line strings. pack-check SHALL refuse a pack that breaks this, so the pack fails this repo's CI and never a user's install after the stamp.

#### Scenario: A complete document entry
- **WHEN** `gamedev` declares `gdd` with template `documents/gdd.md`, present in the pack, and default path `docs/game/gdd.md`
- **THEN** pack-check accepts the entry

#### Scenario: Broken documents, questions or signals are refused
- **WHEN** a `documents` entry names a template file the pack does not have, or a default path that is absolute or contains `..`, or `init.questions` or `signals` is not a list of non-empty single-line strings
- **THEN** pack-check refuses with code `document_invalid`, `init_invalid` or `signals_invalid`, naming the pack and the entry

### Requirement: Pack and skill names keep packs apart from core and from each other
A pack name SHALL match `^[a-z][a-z0-9-]*$` and SHALL NOT be `specwright`, `openspec` or `opsx` or start with one of them followed by `-`. Each listed skill SHALL be `packs/<name>/skills/<skill>/` holding `SKILL.md`, every skill directory there SHALL be listed, and the pack whose `<pack>-` prefix is the longest match of the skill name SHALL be this pack.

#### Scenario: Prefixed skills are accepted
- **WHEN** pack `gamedev` lists `gamedev-design` and `packs/gamedev/skills/gamedev-design/SKILL.md` exists
- **THEN** pack-check accepts the skill

#### Scenario: A core or foreign skill name is refused
- **WHEN** pack `gamedev` lists `specwright-commit`, `web-ux`, or a skill with no `SKILL.md`, or ships an unlisted skill directory
- **THEN** pack-check refuses with code `skill_name` or `skill_missing` or `skill_unlisted`, naming the pack and the skill

#### Scenario: A skill in a longer pack's namespace
- **WHEN** the download has packs `react` and `react-native`, and `react` lists `react-native-nav`
- **THEN** pack-check refuses `react` with code `skill_name`, naming `react-native-nav` and pack `react-native`, and accepts `react-native` listing `react-native-nav`

### Requirement: Rules and guidance attach only to known artifacts and operations
Each key of `rules` SHALL be an artifact id of the downloaded specwright schema, and each key of `operations` SHALL be `apply` or `archive`. A pack SHALL NOT replace an artifact's instruction, template or dependencies: it has no field for them.

#### Scenario: A known artifact receives rules
- **WHEN** a manifest has `rules.review` and `rules.tasks` and the schema defines `review` and `tasks`
- **THEN** pack-check accepts both keys

#### Scenario: An unknown artifact or operation is refused
- **WHEN** a manifest has `rules.playtest` or `operations.verify`
- **THEN** pack-check refuses with code `unknown_artifact` or `unknown_operation`, naming the pack and the key, so no rule is silently dropped by OpenSpec

### Requirement: Every pack line is one owned, bounded line
Each entry of `context`, of each `rules` list and of each `operations` list SHALL be a non-empty single-line string of at most 500 characters that does not start with `[pack:`, a pack SHALL have at most 40 such lines in total, and its `context` lines at most 2048 bytes in UTF-8. The installer, not the author, SHALL add the `[pack:<name>] ` prefix that marks the line as the pack's.

#### Scenario: A plain line is accepted
- **WHEN** a rules entry reads `Player-visible work ends with a playtest task.`
- **THEN** pack-check accepts it and the installed line reads `[pack:gamedev] Player-visible work ends with a playtest task.`

#### Scenario: A multi-line, prefixed or oversized line is refused
- **WHEN** an entry holds a newline, starts with `[pack:web]`, is empty or is 501 characters long
- **THEN** pack-check refuses with code `line_invalid`, naming the pack, the field and the entry's index

#### Scenario: Too many lines
- **WHEN** a pack has 41 lines across `context`, `rules` and `operations`, or 2049 bytes of `context`
- **THEN** pack-check refuses with code `too_many_lines` or `context_too_large`, naming the pack and the count

### Requirement: Packs compose through requires
`requires` SHALL list pack names, without versions. Every required pack SHALL exist in the download and SHALL be enabled in the project too; the installer SHALL NOT enable a required pack on its own. A cycle in `requires` SHALL be refused.

#### Scenario: A domain pack with its shared pack enabled
- **WHEN** `gamedev` requires `ui-prototyping` and the project enables both
- **THEN** plan accepts both packs and installs the skills of each

#### Scenario: A missing requirement or a cycle is refused
- **WHEN** the project enables `gamedev` without `ui-prototyping`, or `a` requires `b` and `b` requires `a`
- **THEN** the install stops before any write with refusal `pack_requires` naming `gamedev` and `ui-prototyping`, or `pack_cycle` naming both packs

### Requirement: Gate-relaxing wording is refused on a best-effort basis
pack-check SHALL refuse a pack line that contains both a gate term and a relaxing term from the lists in `packs/README.md` (tier names matched in capitals only, `trip` only when negated), naming the pack, the field, the index and the line. The check is best effort: the structural rules above are the guarantee, and the README SHALL say that the check is deliberately simple.

#### Scenario: A line that relaxes a gate is refused
- **WHEN** a `rules.design` entry reads `Actor-local state machines do not trip T2 on their own.`
- **THEN** pack-check exits 1 with code `relaxes_gate`, naming the pack, `rules.design`, index 0 and the line

#### Scenario: Strict wording passes
- **WHEN** an entry reads `Never skip the playtest task.` (a relaxing term, no gate term), `The review checks contrast ratios.` (a gate term, no relaxing term), `A change to the save format must trip T4.` (`trip` not negated) or `Skip full-screen effects on the title screen.` (`full` not in capitals)
- **THEN** pack-check accepts it

### Requirement: pack-check reports in one JSON document
`update.sh pack-check` SHALL read every pack in the download, or only those named with `--pack`, and SHALL print one JSON document with `ok`, `packs` (each with `name` and `ok`) and `refusals` (each with `code`, `pack`, `field` when it applies, `message`). It SHALL exit 0 when every pack passes and 1 otherwise, and SHALL write no file.

#### Scenario: All packs pass
- **WHEN** pack-check runs on a download whose packs are all valid
- **THEN** it exits 0 with `"ok": true` and an empty `refusals`

#### Scenario: A named pack is missing
- **WHEN** pack-check runs with `--pack mobile` and `packs/mobile/` does not exist
- **THEN** it exits 1 with refusal `pack_unknown` naming `mobile`, and lists the packs the download has

### Requirement: A project opts in to packs in specwright.yaml
A project SHALL enable packs under `packs:` in `openspec/specwright.yaml`, keyed by pack name, each with an optional `documents:` map of path overrides. With no `packs:` key or an empty map, the install SHALL install no pack skill, add no pack line and create no pack document; `openspec/.specwright/packs.json` then lists no enabled pack and holds only the catalogue, which no agent session loads.

#### Scenario: A project with no packs
- **WHEN** `specwright.yaml` has no `packs:` key and Specwright is installed
- **THEN** no pack skill directory is added to any chosen skills directory, `config.yaml` gains no `[pack:` line, and `packs.json` lists no enabled pack

#### Scenario: An unknown pack is named
- **WHEN** `packs:` names `mobile` and the download has no `packs/mobile/`
- **THEN** the install stops before any write with refusal `pack_unknown` naming `mobile` and the packs the download has

### Requirement: Pack documents are created once and never overwritten
For each enabled pack's `documents` entry, the installer SHALL create the file from the pack's template at the `specwright.yaml` override or else the manifest's default, only when no file exists there. A path that is absolute, contains `..`, leaves the code toplevel or names a directory SHALL be refused before any write. Removing a pack SHALL keep its documents.

#### Scenario: A missing document is created
- **WHEN** `gamedev` declares `gdd` with default path `docs/game/gdd.md` and the file does not exist
- **THEN** the install creates it from the template and reports it as created

#### Scenario: An existing document is kept
- **WHEN** `docs/game/gdd.md` already exists, or the pack is removed later
- **THEN** the file's content is unchanged and the report lists it as kept

#### Scenario: A document path outside the project
- **WHEN** an override sets `gdd` to `../shared/gdd.md` or `/tmp/gdd.md`
- **THEN** plan exits 1 with refusal `pack_doc_path` naming the pack, the document and the path, and no file changes

### Requirement: Packs are refused on a planning store in v1
When the planning root is a store (update.sh role `claim`, `owner` or `other`), an install with any pack enabled SHALL stop before any write with refusal `packs_on_store`, because pack lines in a store's `config.yaml` would apply to every project that uses the store.

#### Scenario: Repo-local project with packs
- **WHEN** role is `none` and `packs:` enables `web`
- **THEN** plan reports no `packs_on_store` refusal

#### Scenario: Store-backed project with packs
- **WHEN** role is `owner` and `packs:` enables `web`
- **THEN** plan exits 1 with refusal `packs_on_store`, and no installed file changes

### Requirement: Packs are refused for skills directories outside the project in v1
When any chosen skills directory is outside the code checkout's toplevel (a user-level directory, as GitButler projects require), an install with any pack enabled SHALL stop before any write with refusal `packs_user_level` naming the directory, because several projects would then share, and remove, the same pack skills.

#### Scenario: Project-level skills directories
- **WHEN** the only skills directory is `<code>/.claude/skills` and `packs:` enables `web`
- **THEN** plan reports no `packs_user_level` refusal

#### Scenario: A user-level skills directory
- **WHEN** a chosen skills directory is `~/.claude/skills` and `packs:` enables `web`
- **THEN** plan exits 1 with refusal `packs_user_level` naming `~/.claude/skills`, and no installed file changes
