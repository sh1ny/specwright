# Proposal

## Why

`pack-mechanism` (0.16.0) shipped the pack format, the installer and `pack-check`, but `packs/` holds no pack yet. The only real one is hand-made in Tower of Lament: three hand-copied `gamedev-*` skills and four hand-written `[pack:gamedev]` lines in its `config.yaml`. No update knows about them, and nothing checks them (#68). A review of the prototype and of public game-design material showed what it lacks: levels and encounters, economy and balance, HUD context and notifications, playtest confidence, and agent-run checks in the engine. This change ships the first packs, `ui-prototyping`, `gamedev` and `godot`, with skills written fresh for Specwright.

It serves M6 - Packs, change 11 (0.20.0), the last change of the milestone, and advances these exit criteria:
- "An eval installs the gamedev pack in a fixture project and shows its additions (the GDD document and its rules for proposal, design and tasks) in the instructions OpenSpec gives for a change." A new eval in `evals/packs/` installs the shipped `gamedev` pack (with `ui-prototyping`) and reads those additions back through `openspec instructions`.
- "Every issue in the changes below is closed by a merged PR, and each code fix has a regression test in `evals/`." #68 is closed by this change's PR.
- "Each change ships as its own release ... and 0.20.0."

The milestone has no user-verified exit criterion. Using the gamedev pack for a real change in Tower of Lament is the deferred dogfood check under Later in the roadmap. It does not block this change or the close.

## What Changes

- **`packs/ui-prototyping/`** (new). A shared, domain-neutral pack with one skill, `ui-prototyping-html`: clickable single-file HTML prototypes that settle an undecided layout or flow before it is specified, and visual identity as design tokens. The skill owns the token schema and its CSS mapping. Its defaults are neutral (system font, responsive stage, mouse and keyboard). The calling skill supplies the stage, font, input model and save folder. Its proposal line says to settle an undecided layout or flow with a prototype first. It creates no document. Later domain packs (web, desktop) can require it.
- **`packs/gamedev/`** (new). Requires `ui-prototyping`. It is engine-neutral and has four skills:
  - `gamedev-design`: ideation, the brief, the GDD, genres, systems and balance, levels and encounters, engine-neutral game-architecture questions, and game code checks.
  - `gamedev-narrative`: story, world, cast, dialogue, objectives and localization readiness.
  - `gamedev-ux`: HUD by gameplay context, notifications, input and glyphs, teaching, transitions, UI feel and the accessibility floor. It hands prototypes to `ui-prototyping-html` with the game settings and `docs/game/prototypes/`.
  - `gamedev-playtest`: the question a playtest answers and its observable signal, the `[user]` task (what to play, what to judge, who plays), routing findings, and recording the verdict and the tuning it changes.

  The pack creates one document, the GDD (`docs/game/gdd.md`), from its own short template with a heading for each init question. The skills create `brief.md`, `narrative.md`, `ux.md` and `decisions.md` from templates they ship, when a design conversation first needs them. Every line below is conditional, so a change outside its domain is unaffected.
  - Proposal:
    - a gameplay request is classed as tuning (data only), tweak (edit the GDD section it cites) or new behaviour (designed in the GDD first);
    - a new resource, currency or reward cites the GDD lines naming its sources and sinks;
    - the cited section's feel words are carried into a scenario or the playtest question.
  - Specs and design:
    - tuning values are hypotheses kept in data the game loads;
    - a per-frame or hot-path change states a measurable frame-time or memory budget, and how it is measured;
    - a change to saved data loads a save from the previous version (migrated or rejected);
    - timing and feel are judged by the playtest, while layout may be proven by evidence or a test;
    - a changed fail state gets an automated check that doing nothing does not win.
  - Tasks:
    - player-visible work ends with a `[user]` playtest task, which says whether the designer or a fresh player plays when it judges difficulty or learnability;
    - input changes get evidence for each declared input device.
  - Apply: game code is checked against `gamedev-design`'s game code checks.

  Its init questions cover genre, pillars, the first playable, platforms and input, narrative weight and the accessibility floor. Its signals are common engine project files.
- **`packs/godot/`** (new). A stack pack with one skill, `godot-engine`:
  - the in-engine check;
  - Resources as data, and never `.tres` for player saves;
  - Theme, Control and focus;
  - pixel-art scaling and localization;
  - test runners, scripted input and a debug-only state dump;
  - changes since Godot 4.4.

  Its design line keeps tunables in `.tres` resources. Its tasks line puts an `[evidence]` task before any playtest. The task names the screen or state it captures and how the run reaches it. It saves a log from a headless run, or a screenshot from a windowed or editor run or Movie Maker (`--write-movie`). It uses a configured Godot MCP server when there is one; none is required. Its signal is `project.godot`.
- **Fresh content.** Fresh-context writers write each skill from the spec and its task. No skill carries a third-party licence file or credit line.
- **Docs.** The project README lists the shipped packs and how to enable them. `packs/README.md` gains a "Pack layers" note and a "Moving a hand-made pack" note: delete the hand copies first, or the install stops with `unmanaged_skill`. The managed lines replace hand-written `[pack:gamedev]` lines.
- **Evals.** New modules in `evals/packs/` and `evals/update/` install the shipped packs into fixture projects. They check that the GDD is created and that the lines reach proposal, specs, design, tasks and apply in `openspec instructions`. They also run static checks on every shipped skill: description length, named files, engine-neutral wording, no third-party notices and neutral prototype defaults. The existing check that every shipped pack passes `pack-check` now has real packs to read.

## Capabilities

### New Capabilities
- `domain-packs`: what each first-party pack shipped in the download adds. For this change that is `ui-prototyping`, `gamedev` and `godot`: their skills, rules, documents, questions, signals and `requires`, and the evidence and playtest tasks they ask for. Later packs (web, cli/tui, desktop, other stacks) add their requirements here.

### Modified Capabilities

## Impact

- New: `packs/ui-prototyping/`, `packs/gamedev/` and `packs/godot/` (manifests, skills with their `references/`, `assets/` and `templates/`, and the GDD template).
- Changed: `packs/README.md` (layers and migration notes), `README.md` (the packs list), and `evals/suites.json` if a new path needs a rule (`packs/**` and `evals/packs/**` already map to the `packs` and `update` suites).
- New eval modules under `evals/packs/` and `evals/update/`.
- No script, schema or core skill changes: the packs use only the v1 pack surface. Three core gaps found on the way are filed as separate issues: #189 (the pre-ship review sees no pack skills), #190 (learnings between changes) and #191 (P2/P3 findings in local mode). None blocks the packs.
- Projects without `packs:` are unchanged. Every pack skill description loads in each session of a project that enables the pack, so the descriptions are kept short.
- Tower of Lament keeps working as it is. Moving it to the managed packs is the deferred dogfood check.

## Decision Making

DECISION_MAKING: important
- **Source:** setting

### S1: How the skills split across the packs

- **Choice:** split by layer.
  - `ui-prototyping` (`ui-prototyping-html`): generic prototypes and tokens.
  - `gamedev`: `gamedev-design`, `gamedev-narrative`, `gamedev-ux` and `gamedev-playtest`, engine-neutral.
  - `godot`: `godot-engine`, with everything engine-specific.
- **Rejected:**
  - Shipping Tower of Lament's three skills unchanged in `gamedev`: a later web pack could not reuse the prototyping, and `gamedev` would stay tied to Godot.
  - `gamedev` + `godot` only, without the shared pack: the roadmap's shared pack would wait for the web pack, and its content would then move out of `gamedev-ux` later.
- **Reversal cost:** medium. Skill names and `requires` are what projects enable and record in `packs.json`.
- **Important:** yes. It binds future packs (later domain packs require `ui-prototyping`) and changes what users install.
- **Chosen by:** user

### S2: Which documents the gamedev pack creates

- **Choice:** the GDD only (`docs/game/gdd.md`), from the pack's own template, which has a heading for each init question. `brief.md`, `narrative.md`, `ux.md` and `decisions.md` are created by their skills from shipped templates when first needed.
- **Rejected:**
  - Creating GDD, narrative and UX at install: a game with no story would carry an empty `narrative.md`, and pack documents are never removed.
  - Also creating `decisions.md` at install: an append-only log is better started by its first entry.
  - Adapting a published GDD template: the ones we found are shaped like product requirements documents (epics, technical specifications, success metrics) that duplicate the roadmap, architecture and strategy, and have no heading for most of the init questions.
- **Reversal cost:** low. A later version can add a document entry. Documents already created stay.
- **Important:** yes. It changes files users see in their projects.
- **Chosen by:** user

### S3: How the in-engine check is done

- **Choice:** tool-neutral. The `godot` pack asks for an `[evidence]` task that names the screen or state it captures and how the run reaches it. A log comes from a headless run. A screenshot comes from a windowed or editor run, or Movie Maker (`--write-movie`), because a headless run renders nothing. A configured Godot MCP server is used when there is one.
- **Rejected:** requiring Godot MCP, as Tower of Lament's line does. Not every project has one configured, and projects without it could not meet the rule.
- **Reversal cost:** low
- **Important:** yes. It changes behaviour users see.
- **Chosen by:** user

### S4: Playtest support

- **Choice:** a `gamedev-playtest` skill, which the tasks rule points at. It covers the question and its observable signal, the `[user]` task, who plays, routing findings to bugs or tuning, and recording the verdict and the tuning changes.
- **Rejected:** a rule line only, as in Tower of Lament: the task would exist, but there would be no guidance on writing a playtest that answers a question.
- **Reversal cost:** low
- **Important:** yes. It changes behaviour users see.
- **Chosen by:** user

### S5: Where the skill content comes from

- **Choice:** written fresh for Specwright. Fresh-context writers write each skill from the spec and its task. No skill carries a third-party licence file or credit line.
- **Rejected:**
  - Shipping the Tower of Lament skills: they carry their own third-party licence, which every pack skill would then need.
- **Reversal cost:** low
- **Important:** yes. It decides what users receive and under which terms.
- **Chosen by:** user

### S6: Tower of Lament migration

- **Choice:** out of scope. Moving Tower of Lament to the managed packs is the deferred dogfood check. `packs/README.md` documents the steps: delete the hand copies, enable the packs, and let the managed lines replace the hand-written ones.
- **Rejected:** migrating Tower of Lament in this change. That writes to a dogfood project, which is the user's to do.
- **Reversal cost:** low
- **Important:** no. It is documentation plus an existing deferral.
- **Chosen by:** agent

### S7: The gamedev and godot rule lines

- **Choice:** the lines listed under What Changes.
  - gamedev: request classification, sources and sinks, feel words, tuning in data, frame budget, save compatibility, feel vs layout, idle doesn't win, the `[user]` playtest with who plays, input-device evidence, and an apply line naming the game code checks.
  - godot: `.tres` tunables, and the tool-neutral evidence task that names its state.
  - ui-prototyping: one line, the prototype-first proposal line.
- **Rejected:** only Tower of Lament's four lines. They leave performance, saves, economies and fail states to chance, and they let a designer's own play settle difficulty.
- **Reversal cost:** low. A later version can reword or drop a line. Installs replace managed lines every time.
- **Important:** yes. Every line appears in users' artifacts.
- **Chosen by:** user

### S8: How much of what was learned goes in

- **Choice:** the High and Medium items from the gap review go into the skills. Low items are left out.
- **Rejected:**
  - High items only: it would leave out the HUD context table, the notification queue and the playtest-confidence mark.
  - Everything: longer skills, for little gain.
- **Reversal cost:** low
- **Important:** yes. It sets what the skills teach.
- **Chosen by:** user

## Release Notes

The first domain packs ship with Specwright:
- `ui-prototyping`: clickable HTML prototypes and design tokens;
- `gamedev`: GDD, game design, systems and levels, narrative, game UX and playtests;
- `godot`: in-engine evidence, data-resource tunables and Godot 4 guidance.

Enable them under `packs:` in `openspec/specwright.yaml` and rerun the install prompt. A game project then gets a GDD, design skills, and rules that make gameplay changes cite their design and state their budgets. Each such change ends with an evidence check and your playtest verdict.

### Added
- The `ui-prototyping`, `gamedev` and `godot` packs, with skills written fresh for Specwright (#68).
