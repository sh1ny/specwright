# Proposal

## Why

Specwright's workflow is domain-neutral, but real projects need domain knowledge on top of it: a game needs a GDD, a playtest and engine conventions; a web app needs UX flows, accessibility and a browser check; a CLI needs a command reference and golden output. Today the only way to add that is what Tower of Lament does: hand-copied skills and hand-edited `[pack:gamedev]` lines in `openspec/config.yaml`, which no update knows about and nothing checks (#68). This change adds **packs**: opt-in bundles that add skills, rules, documents and questions to a project without changing Specwright's flow, built so that many packs can follow (gamedev first, then web, cli/tui, desktop and stack packs such as godot or react).

It serves **M6 - Packs**, change 7 (0.16.0). "Carries no pack descriptions" is read as: no pack skill is installed and no pack line reaches OpenSpec; the catalogue in `packs.json` is a state file no session loads. It advances the exit criteria "a project opts in to a pack in `openspec/specwright.yaml`; install, update and remove add and remove only that pack's files, and a project with no packs installs nothing extra and carries no pack descriptions" and "the installer rejects a pack that removes a step or relaxes the triage, review or verify gate where it can detect it, and names the rule". The design decisions below were agreed with the user before this proposal (2026-11-01).

## What Changes

- **Pack format.** A pack is a directory `packs/<name>/` in this repo with a `pack.json` manifest (JSON, so no script needs a YAML parser), its skills (each named `<name>-*`) and its document templates. The manifest declares: a description, the packs it requires, its skills, `context` lines, per-artifact `rules` (any artifact id of the specwright schema, including `review`), `operations` guidance (`apply`, `archive`), project documents (a default path and a template), init questions, and repo signals used to suggest the pack. A `source` field is reserved so external packs (a git URL pinned to a commit) can come later without a format change; v1 installs only packs shipped in the Specwright download.
- **Composition.** A pack may `require` other packs, by name, with no version ranges (all first-party packs ship in one release). This lets domain packs (gamedev, web) share a common pack (ui-prototyping) and lets stack packs (godot, react) add one stack's knowledge to a domain. A missing requirement or a cycle is refused.
- **Opt in.** `openspec/specwright.yaml` gains a `packs:` map, keyed by pack name, with optional per-document path overrides. No `packs:` key, or an empty one, installs nothing extra.
- **Install, update and remove go through the existing install prompt and `scripts/update.sh`.** The script stages and swaps each enabled pack's skill directories with Specwright's own (same journal, same recovery), records which skills belong to which pack, with a catalogue of the download's packs, in `openspec/.specwright/packs.json`, and removes the skills of a pack that is no longer enabled. It never touches a skill directory it did not install: a hand-copied skill with a pack skill's name stops the install unless it is identical to the download's. The prompt merges each pack's lines into `config.yaml` with a `[pack:<name>]` prefix (replacing only lines of packs the project enables or enabled before), keeps `packs:` settings as user data, creates missing pack documents from their templates (never overwriting), and verifies through `openspec instructions` that every pack line reaches its artifact exactly once. The update-script interface becomes 2; the prompt still installs older releases when no pack is enabled.
- **Additive only, enforced mostly by structure.** A pack can add only through the channels above. A new `update.sh pack-check` refuses a manifest that names a `specwright-*` skill or another pack's prefix, a rule keyed to an artifact id the schema does not have, an unknown operation, a line that already carries a `[pack:` prefix or spans lines, or an unmet requirement. On top of that, a deliberately crude, documented best-effort text check refuses a line that pairs a gate term (triage, T1-T6, LIGHT/FULL, verdict, review, verify, gate) with a relaxing term (skip, waive, relax, bypass, exempt, ...), naming the pack, the field and the line.
- **Shared installs.** Packs are refused in v1, before any write, on a store-backed project (`packs_on_store`) and when a skills directory is outside the project, a user-level install on any backend (`packs_user_level`; GitButler projects install in the repo since ADR 0021): in both cases several projects would share one pack's lines or skills. A follow-up issue tracks both.
- **Roadmap.** `specwright-roadmap init` suggests packs from repo signals (for example `project.godot`) and never enables one by itself; it asks the enabled packs' init questions within its two batched rounds, writes the answers into their documents and gives those documents to the baseline review as context (a living GDD never voids the baseline). A new **pack** mode asks a later-enabled pack's questions and fills its documents.
- **Docs.** `packs/README.md`, "Writing a pack": the manifest fields, the prefix rule, the additive-only rule, conditional wording for rules that apply only to some changes, and that pack skills never take over Specwright's commit, review or verify ownership. A new ADR records the pack model.
- **Roadmap edit (this branch).** M6 gains `user-verified-tasks` (0.17.0) before the first pack: tasks only the user ticks (a playtest verdict, a UX sign-off) and evidence tasks are a core need of every domain, so they go in core, not in a pack. `gamedev-pack` moves to 0.18.0 and ships three packs: `ui-prototyping`, `gamedev` and `godot`. Spike changes are filed as an issue for a later milestone.

No pack is shipped in this change; `gamedev-pack` ships the first ones. This change ships the format, the tooling and an eval fixture pack.

## Capabilities

### New Capabilities
- `packs`: the pack format and its manifest, composition through `requires`, the opt-in in `specwright.yaml`, the additive-only checks (structural and textual), the `[pack:<name>]` line ownership, pack documents, and the store refusal.

### Modified Capabilities
- `install-update`: the install prompt and `update.sh` install, update and remove enabled packs' skills with the existing staging and journal, record pack ownership, refuse unmanaged skill clashes and stores, merge and verify pack lines, and drive update-script interface 2.
- `project-planning`: roadmap **init** suggests packs from repo signals, runs enabled packs' questions, and gives their documents to the baseline review as context; a new **pack** mode does this for a pack enabled later.

## Impact

- `scripts/update.sh`: `--pack` and `--pack-doc` handling in `plan`, `stage`, `swap`, `recover` and `finish` (documents are created by `pack-docs`, not `finish`), `remove` journal items (journal format 2), the `packs.json` record, new `pack-check`, `pack-verify` and `pack-docs` subcommands, interface 2.
- `README.md` install prompt (Steps 2, 4, 5, 6, 7 and 8), `templates/openspec/specwright.yaml` (`packs:` commented example).
- `skills/specwright-roadmap/SKILL.md` (init and the new **pack** mode).
- New: `packs/README.md`, `docs/adr/0023-*.md`, its row in `openspec/architecture.md`, a component note there.
- Evals: a new `evals/packs` suite (manifest checks, gate wording, fixture packs) and pack install, update, remove and recovery cases in `evals/update`; `evals/suites.json` rules for `packs/**`.
- `openspec/roadmap.md` (M6 changes, versions and exit criteria).
- Version files to 0.16.0.

## Release Notes

0.16.0 adds packs: opt-in bundles of domain skills, rules, documents and init questions that add to Specwright's flow. A project lists them under `packs:` in `openspec/specwright.yaml`; the install prompt installs, updates and removes them with Specwright's own skills, records their ownership in `packs.json` and checks their config lines through OpenSpec. A pack that relaxes a gate is refused, as are packs on a planning store or a user-level skills directory. Roadmap init suggests packs from the repo's files. No pack ships yet; the first ones (ui-prototyping, gamedev, godot) follow in 0.18.0.

### Added
- Packs: a `pack.json` format, `packs:` in `openspec/specwright.yaml`, pack install, update and remove through the install prompt and `update.sh`, and `update.sh pack-check`, which refuses a pack that names a core skill, targets an unknown artifact or relaxes a gate (#68)
- `update.sh pack-verify`, which checks the merged pack lines through `openspec instructions`, and `update.sh pack-docs`, which creates missing pack documents after the stamp and never overwrites one (#68)
- `specwright-roadmap` suggests packs from repo signals during init, asks their questions and reviews their documents with the baseline, and a new **pack** mode sets up a pack enabled later (#68)

### Changed
- The update script reports interface 2 and writes journal format 2; the install prompt still installs an older release when no pack is enabled, and every install now writes `openspec/.specwright/packs.json`, which is treated like `VERSION` (#68)
