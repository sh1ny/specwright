# Spec Delta

## ADDED Requirements

### Requirement: Roadmap init suggests packs and never enables one by itself
Roadmap **init** SHALL compare the code checkout's tracked and untracked, non-ignored files with the `signals` of every pack in the catalogue of `openspec/.specwright/packs.json` and offer each matching pack that is not enabled, with the signal and the packs it requires, as one offer. Only on the user's yes SHALL it add the pack under `packs:` in `openspec/specwright.yaml`, and it SHALL then tell the user to rerun the install prompt and run roadmap **pack** `<name>`.

#### Scenario: A Godot project is offered the game packs
- **WHEN** init runs in a checkout holding `project.godot` and no pack is enabled
- **THEN** init offers `gamedev` and `godot`, naming `project.godot` as the signal and `ui-prototyping` as required by `gamedev`, even when `project.godot` is not committed yet, says that packs install only into in-repo skills directories and that a user-level install refuses them, and `specwright.yaml` is unchanged until the user answers

#### Scenario: The user declines
- **WHEN** the user declines an offered pack
- **THEN** `packs:` is unchanged and init continues with its core interview

### Requirement: Roadmap init's pack offer names the in-repo install need
Every pack offer roadmap **init** makes SHALL say that packs install only into in-repo skills directories and that an install at user level refuses them (`packs_user_level`).

#### Scenario: A pack offer in a project that installs at user level
- **WHEN** init offers any catalogued pack whose signal matches the checkout
- **THEN** the offer says that packs install only into in-repo skills directories and that a user-level install refuses them with `packs_user_level`

### Requirement: Roadmap init offers no pack where the install refuses packs
Roadmap **init** SHALL offer no pack when the planning root is a store, where the install refuses packs in v1, and SHALL say that packs are not supported there yet.

#### Scenario: A project where packs cannot be installed
- **WHEN** init runs with a store-backed planning root, in a checkout holding `project.godot`
- **THEN** init offers no pack, says that packs are not supported there yet, and `specwright.yaml` gains no `packs:` key

#### Scenario: A repo-local Git project
- **WHEN** init runs with `vcs: git`, a repo-local planning root and `project.godot`
- **THEN** init offers the matching packs as above

### Requirement: Roadmap init includes enabled packs' questions and documents
When packs are enabled in `openspec/.specwright/packs.json`, roadmap **init** SHALL ask their init questions within its at most two batched rounds, each with a recommended default, write the answers into each pack document, and name those documents in the baseline review request as context. Pack documents SHALL NOT be gated content: editing one never voids a baseline verdict.

#### Scenario: Pack questions join the interview
- **WHEN** `gamedev` is installed with four init questions and init interviews the user
- **THEN** the four questions are asked in init's batched rounds, no third round is added, and the baseline review request names `docs/game/gdd.md` as context

#### Scenario: A pack document edited after the baseline passed
- **WHEN** the baseline holds `VERDICT: APPROVE` and a later change edits `docs/game/gdd.md`
- **THEN** the baseline verdict stands and no new baseline round is started

#### Scenario: A pack document is missing at init
- **WHEN** `packs.json` lists `docs/game/gdd.md` and the file does not exist
- **THEN** init tells the user to rerun the install prompt to create it, and does not create it from memory

### Requirement: Roadmap pack mode sets up a pack enabled later
Roadmap **pack** `<name>` SHALL run for an enabled, installed pack: it SHALL ask the pack's init questions in one batched round with recommended defaults and write the answers into the pack's documents without removing user content. It SHALL run no review round and change no baseline verdict, and SHALL commit the documents it wrote through the roadmap's procedure for committing project files, on branch `docs/pack-<name>`, never on main.

#### Scenario: Setting up a pack after the baseline
- **WHEN** a project with an approved baseline installs `web` and runs roadmap **pack** `web`
- **THEN** the web questions are asked once, the web documents hold the answers in a commit on `docs/pack-web` finished per the `finish` setting, main's working tree is clean, and `openspec/architecture-review.md` is unchanged

#### Scenario: The pack is not installed
- **WHEN** roadmap **pack** `web` runs and `packs.json` does not list `web`
- **THEN** it writes no file and says to add `web` under `packs:` and rerun the install prompt
