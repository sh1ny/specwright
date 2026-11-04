# Spec Delta

## Purpose

Defines what each first-party domain pack shipped in the Specwright download adds to a project's workflow: its skills, artifact rules, operation guidance, documents, init questions, signals and required packs.

## ADDED Requirements

### Requirement: The download ships the ui-prototyping, gamedev and godot packs
The Specwright download SHALL hold `packs/ui-prototyping/`, `packs/gamedev/` and `packs/godot/`, and `update.sh pack-check` over the download SHALL accept all three. `gamedev` SHALL require `ui-prototyping`. `ui-prototyping` and `godot` SHALL require no pack.

#### Scenario: The shipped packs pass pack-check
- **WHEN** `update.sh pack-check` runs over the repository's own `packs/`
- **THEN** it exits 0 and reports `ui-prototyping`, `gamedev` and `godot`, each with `"ok": true`

#### Scenario: gamedev without its shared pack
- **WHEN** a project's `packs:` enables `gamedev` but not `ui-prototyping`
- **THEN** the install stops before any write with refusal `pack_requires` naming `gamedev` and `ui-prototyping`

#### Scenario: godot on its own
- **WHEN** a project's `packs:` enables only `godot`
- **THEN** plan reports no `pack_requires` refusal and installs only `godot-engine`

### Requirement: Each pack ships its listed skills
`ui-prototyping` SHALL ship `ui-prototyping-html`. `gamedev` SHALL ship `gamedev-design`, `gamedev-narrative`, `gamedev-ux` and `gamedev-playtest`. `godot` SHALL ship `godot-engine`. Each skill's `SKILL.md` SHALL have a `name` equal to its directory and a `description` of at most 600 characters, because the description loads into every session of a project that enables the pack.

#### Scenario: Skills installed with their packs
- **WHEN** a project enables `ui-prototyping`, `gamedev` and `godot` and the install finishes
- **THEN** each chosen skills directory holds exactly those six pack skills, and `packs.json` records each under its pack

#### Scenario: A description too long
- **WHEN** a shipped pack skill's `description` is 601 characters long
- **THEN** the shipped-pack eval fails, naming the skill and its length

### Requirement: Files a pack skill names exist in that skill
Every path under `references/`, `assets/` or `templates/` that a shipped pack skill's `SKILL.md` names SHALL exist in that skill's own directory, so a skill installed on its own never points at a file it does not carry.

#### Scenario: References resolve
- **WHEN** `gamedev-design/SKILL.md` names `references/systems-and-balance.md` and `ui-prototyping-html/SKILL.md` names `assets/prototype-template.html`
- **THEN** both files exist in the named skill's directory in the download

#### Scenario: A reference left behind by the split
- **WHEN** `gamedev-ux/SKILL.md` names `assets/prototype-template.html` but the file lives only in `ui-prototyping-html`
- **THEN** the shipped-pack eval fails, naming `gamedev-ux` and the missing path

### Requirement: Pack skills carry no third-party notice
No shipped pack skill SHALL carry a third-party licence file or credit line: no file under a pack's `skills/` or `documents/` has a name starting with `LICENSE`, `LICENCE`, `NOTICE` or `COPYING`, and none contains `Adapted from` or `Ported from`.

#### Scenario: Clean skill trees
- **WHEN** the shipped-pack eval reads every file under the three packs' `skills/` and `documents/`
- **THEN** no file name starts with `LICENSE`, `LICENCE`, `NOTICE` or `COPYING`, and no file contains `Adapted from` or `Ported from`

#### Scenario: A leftover credit
- **WHEN** a pack skill's `SKILL.md` ends with an `Adapted from` line
- **THEN** the shipped-pack eval fails, naming the skill and the file

### Requirement: gamedev creates the GDD and no other document
`gamedev` SHALL declare one document, `gdd`, with default path `docs/game/gdd.md` and a template holding a section heading for each init question. `ui-prototyping` and `godot` SHALL declare no document. The skills SHALL create `brief.md`, `narrative.md`, `ux.md` and `decisions.md` from templates under their own `templates/`, only when a design conversation first needs them.

#### Scenario: GDD created at install
- **WHEN** a project enables `ui-prototyping` and `gamedev`, has no `docs/game/gdd.md`, and the install finishes
- **THEN** `docs/game/gdd.md` exists with the pack template's content, and no `brief.md`, `narrative.md`, `ux.md` or `decisions.md` is created

#### Scenario: An existing GDD
- **WHEN** the project already has `docs/game/gdd.md`, or sets `packs.gamedev.documents.gdd` to `design/gdd.md` and that file exists
- **THEN** the file is unchanged and the report lists it as kept

#### Scenario: Templates shipped with their skills
- **WHEN** the shipped-pack eval reads the gamedev skills
- **THEN** `brief.md`, `decisions.md`, `narrative.md` and `ux.md` templates each exist under the `templates/` of the skill that names them

### Requirement: Only gamedev asks init questions
`gamedev` SHALL declare six init questions, one each on genre and reference games, core fantasy and pillars, what the first playable must prove, platforms and primary input, narrative weight, and the accessibility floor. `ui-prototyping` and `godot` SHALL declare none, because they have no document to hold the answers.

#### Scenario: Questions with a home
- **WHEN** the shipped-pack eval reads `gamedev`'s `init.questions`
- **THEN** there are six, and the GDD template has a section heading that each question names

#### Scenario: A question with no document
- **WHEN** `godot` or `ui-prototyping` declares an init question
- **THEN** the shipped-pack eval fails, naming the pack

### Requirement: gamedev proposal lines
With `gamedev` enabled, the proposal instructions SHALL carry lines that:
- class a gameplay, story or UI request as tuning (data only), tweak (edit the GDD section it cites) or new behaviour (designed in the GDD first);
- make a new resource, currency or reward cite the GDD lines naming its sources and sinks;
- carry the cited section's feel words into a scenario or the playtest question.

#### Scenario: Proposal lines delivered
- **WHEN** a fixture project enables `ui-prototyping` and `gamedev`, and `openspec instructions proposal` runs
- **THEN** its rules hold each `[pack:gamedev]` proposal line exactly once, including one naming tuning, tweak and new behaviour and one naming sources and sinks

#### Scenario: No pack enabled
- **WHEN** the same fixture project has no `packs:` key
- **THEN** no output of `openspec instructions` for any artifact, `apply` or `archive` contains `[pack:`

### Requirement: gamedev specs lines
With `gamedev` enabled, the specs instructions SHALL carry lines that:
- give a change to saved data a scenario that loads the previous version's save;
- leave timing and feel to the playtest, and let evidence or a test prove layout;
- give a changed fail state an automated check that doing nothing does not win.

#### Scenario: gamedev specs lines delivered
- **WHEN** a fixture project enables `ui-prototyping` and `gamedev`, and `openspec instructions specs` runs
- **THEN** its rules hold one `[pack:gamedev]` line each naming a previous version's save, the playtest for feel, and doing nothing, and no gamedev design line

### Requirement: gamedev design lines
With `gamedev` enabled, the design instructions SHALL carry lines that:
- keep tuning values as hypotheses in data the game loads;
- give a per-frame or hot-path change a measurable frame-time or memory budget, and say how it is measured.

#### Scenario: gamedev design lines delivered
- **WHEN** a fixture project enables `ui-prototyping` and `gamedev`, and `openspec instructions design` runs
- **THEN** its rules hold one `[pack:gamedev]` line each naming data the game loads and a frame budget, and no gamedev specs line

### Requirement: gamedev tasks and apply lines
With `gamedev` enabled, the tasks instructions SHALL carry lines that:
- end player-visible work with a `[user]` playtest task, which says whether the designer or a fresh player plays when it judges difficulty or learnability;
- give input changes evidence for each declared input device.

The apply instructions SHALL carry a line that checks game code against `gamedev-design`'s game code checks. The lines, and every file of the `gamedev` and `ui-prototyping` skills, SHALL name no engine.

#### Scenario: Tasks and apply lines delivered
- **WHEN** a fixture project enables `ui-prototyping` and `gamedev`, and `openspec instructions` runs for `tasks` and `apply`
- **THEN** the tasks rules hold the `[pack:gamedev]` lines exactly once, one naming the `[user]` marker and a fresh player, and the apply guidance holds one `[pack:gamedev]` line naming `gamedev-design`

#### Scenario: Engine-neutral wording
- **WHEN** the shipped-pack eval reads every `gamedev` and `ui-prototyping` line and every file under their `skills/` and `documents/`, references and templates included
- **THEN** none contains `Godot` (in any case), `.tres` or `MCP`

### Requirement: ui-prototyping settles undecided layout with a prototype
With `ui-prototyping` enabled, the proposal instructions SHALL carry a line saying that a UI change whose layout or flow is undecided is settled with a clickable prototype (`ui-prototyping-html`) before it is specified.

#### Scenario: Prototype line delivered
- **WHEN** a project enables `ui-prototyping` and `openspec instructions proposal` runs
- **THEN** the rules hold one `[pack:ui-prototyping]` line naming `ui-prototyping-html`

#### Scenario: The line's pack is removed
- **WHEN** `ui-prototyping` and `gamedev` are removed from `packs:` and the install reruns
- **THEN** no `[pack:ui-prototyping]` or `[pack:gamedev]` line remains in `config.yaml`, and `docs/game/gdd.md` is kept

### Requirement: ui-prototyping defaults are neutral
`ui-prototyping-html`'s prototype template SHALL default to a system font stack and a stage that follows the window, with no fixed pixel size. The calling skill supplies the stage, font, input model and save folder. `gamedev-ux` SHALL pass the game values and `docs/game/prototypes/` as the save folder.

#### Scenario: Neutral template
- **WHEN** the shipped-pack eval reads `ui-prototyping-html/assets/prototype-template.html`
- **THEN** it names `system-ui` in a font stack and sets no fixed stage width or height in pixels

#### Scenario: Game settings passed
- **WHEN** the shipped-pack eval reads `gamedev-ux/SKILL.md` and `ui-prototyping-html/SKILL.md`
- **THEN** `gamedev-ux` names `ui-prototyping-html` and gives a value for each of the settings `stage`, `scaling`, `font`, `input model` and `save folder`, the save folder being `docs/game/prototypes/`, and `ui-prototyping-html` lists the same five setting names with a neutral default each

#### Scenario: A missing game setting
- **WHEN** `gamedev-ux/SKILL.md` gives no value for `font`, or names a setting that `ui-prototyping-html` does not list
- **THEN** the shipped-pack eval fails, naming `gamedev-ux` and the setting

### Requirement: godot asks for an in-engine evidence task
With `godot` enabled, the tasks instructions SHALL carry a line asking that player-visible work in the Godot project gets an `[evidence]` task, placed before any playtest task. The task names the screen or state it captures and how the run reaches it, and saves under `evidence/`:
- a log from a headless run;
- or a screenshot from a windowed or editor run, or Movie Maker (`--write-movie`).

It uses a configured Godot MCP server when there is one.

#### Scenario: godot with gamedev
- **WHEN** a project enables `ui-prototyping`, `gamedev` and `godot`, and `openspec instructions tasks` runs
- **THEN** the rules hold the `[pack:gamedev]` playtest line and a `[pack:godot]` line naming `[evidence]` and `evidence/`, each exactly once

#### Scenario: Not tied to one tool
- **WHEN** the shipped-pack eval reads the `godot` tasks line
- **THEN** the line names a headless run for a log and `--write-movie` or a windowed run for a screenshot, and names no paid product

### Requirement: godot keeps tunables in resources
With `godot` enabled, the design instructions SHALL carry a line keeping tunables in `.tres` resources that the game loads.

#### Scenario: Design line delivered
- **WHEN** a project enables `godot` and `openspec instructions design` runs
- **THEN** the rules hold one `[pack:godot]` line naming `.tres`

### Requirement: Signals suggest the packs for game projects
`gamedev` SHALL list signals for common engine project files: `project.godot` at the root or nested, `*.uproject`, `ProjectSettings/ProjectVersion.txt` and `game.project`, plus `docs/game/gdd.md`. `godot` SHALL list `project.godot` at the root or nested. `ui-prototyping` SHALL list no signal: it is offered as a pack that `gamedev` requires.

#### Scenario: A nested Godot project
- **WHEN** roadmap init runs in a repo whose only engine file is `Source/Game/project.godot`
- **THEN** the catalogue's signals match it for `gamedev` and `godot`, and the `gamedev` offer names `ui-prototyping` as required

#### Scenario: No engine file
- **WHEN** roadmap init runs in a repo with no file matching any signal
- **THEN** no pack is offered

### Requirement: Signals match under either reading of a nested glob
Each shipped signal that uses `**/` SHALL have a root form beside it, so it matches the same files whether `**/` is read as zero or more leading directories or as at least one.

#### Scenario: Root file under the strict reading
- **WHEN** the repo's only engine file is `project.godot` at the root, and `**/` is read as at least one directory
- **THEN** `project.godot` still matches through its root-form signal, for both `gamedev` and `godot`

#### Scenario: A nested signal without its root form
- **WHEN** a shipped pack lists `**/game.project` but not `game.project`
- **THEN** the shipped-pack eval fails, naming the pack and the signal
