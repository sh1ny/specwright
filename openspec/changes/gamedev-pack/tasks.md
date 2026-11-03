# Tasks

## Test map

Two new modules, each following design D6:
- `evals/packs/test_shipped_packs.py` (**P**) holds the static checks, `pack-check`, the Step 5 merge with real `openspec instructions` (artifacts, `apply`, `archive`), and `pack-docs`. Each static check is a function over a pack tree. Its failure scenarios run the same function on a scratch copy of the real `packs/` with one deliberate defect, and assert the failure names the pack, the skill, the path or the setting. The line checks assert fixed keywords held in the test (design D10 table), never values read from the manifest under test.
- `evals/update/test_shipped_packs.py` (**U**) runs the real installer through the `evals/update/test_packs.py` end-to-end harness, with the repository's `packs/` as the download's packs, plus signal matching over the catalogue the install writes.

Both modules are written in group 1, before any pack content, and run red first.

| # | Requirement | Scenario | Test file | Test name | State |
|---|---|---|---|---|---|
| 1 | The download ships the ui-prototyping, gamedev and godot packs | The shipped packs pass pack-check | P | ShippedPackCheck.test_three_packs_pass | red |
| 2 | The download ships the ui-prototyping, gamedev and godot packs | gamedev without its shared pack | U | ShippedInstall.test_gamedev_without_ui_prototyping_refused | red |
| 3 | The download ships the ui-prototyping, gamedev and godot packs | godot on its own | U | ShippedInstall.test_godot_alone | red |
| 4 | Each pack ships its listed skills | Skills installed with their packs | U | ShippedInstall.test_all_three_install_six_skills | red |
| 5 | Each pack ships its listed skills | A description too long | P | SkillStatic.test_description_cap | red |
| 6 | Files a pack skill names exist in that skill | References resolve | P | SkillStatic.test_named_files_exist | red |
| 7 | Files a pack skill names exist in that skill | A reference left behind by the split | P | SkillStatic.test_missing_named_file_fails | red |
| 8 | Pack skills carry no third-party notice | Clean skill trees | P | SkillStatic.test_no_third_party_markers | red |
| 9 | Pack skills carry no third-party notice | A leftover credit | P | SkillStatic.test_leftover_credit_fails | red |
| 10 | gamedev creates the GDD and no other document | GDD created at install | P | ShippedDocs.test_gdd_only_created | red |
| 11 | gamedev creates the GDD and no other document | An existing GDD | P | ShippedDocs.test_existing_and_overridden_gdd_kept | red |
| 12 | gamedev creates the GDD and no other document | Templates shipped with their skills | P | SkillStatic.test_document_templates_exist | red |
| 13 | Only gamedev asks init questions | Questions with a home | P | Questions.test_six_questions_match_gdd_headings | red |
| 14 | Only gamedev asks init questions | A question with no document | P | Questions.test_question_without_document_fails | red |
| 15 | gamedev proposal lines | Proposal lines delivered | P | Delivered.test_gamedev_proposal_lines | red |
| 16 | gamedev proposal lines | No pack enabled | P | Delivered.test_no_packs_no_pack_lines | red |
| 17 | gamedev specs lines | gamedev specs lines delivered | P | Delivered.test_gamedev_specs_lines | red |
| 18 | gamedev design lines | gamedev design lines delivered | P | Delivered.test_gamedev_design_lines | red |
| 19 | gamedev tasks and apply lines | Tasks and apply lines delivered | P | Delivered.test_gamedev_tasks_apply_lines | red |
| 20 | gamedev tasks and apply lines | Engine-neutral wording | P | SkillStatic.test_engine_neutral_lines_and_files | red |
| 21 | ui-prototyping settles undecided layout with a prototype | Prototype line delivered | P | Delivered.test_ui_prototyping_proposal_line | green |
| 22 | ui-prototyping settles undecided layout with a prototype | The line's pack is removed | U | ShippedInstall.test_removal_keeps_gdd_drops_lines | red |
| 23 | ui-prototyping defaults are neutral | Neutral template | P | SkillStatic.test_neutral_prototype_template | green |
| 24 | ui-prototyping defaults are neutral | Game settings passed | P | SkillStatic.test_gamedev_ux_passes_game_settings | red |
| 25 | ui-prototyping defaults are neutral | A missing game setting | P | SkillStatic.test_missing_game_setting_fails | red |
| 26 | godot asks for an in-engine evidence task | godot with gamedev | P | Delivered.test_godot_evidence_line_with_gamedev | red |
| 27 | godot asks for an in-engine evidence task | Not tied to one tool | P | SkillStatic.test_godot_line_tool_neutral | red |
| 28 | godot keeps tunables in resources | Design line delivered | P | Delivered.test_godot_design_line | red |
| 29 | Signals suggest the packs for game projects | A nested Godot project | U | Signals.test_nested_project_godot_offers_gamedev_and_godot | red |
| 30 | Signals suggest the packs for game projects | No engine file | U | Signals.test_no_engine_file_no_offer | red |
| 31 | Signals match under either reading of a nested glob | Root file under the strict reading | U | Signals.test_root_file_both_readings | red |
| 32 | Signals match under either reading of a nested glob | A nested signal without its root form | P | SkillStatic.test_nested_signal_needs_root_form | green |

## How each skill is written (design D8)

Every skill task below is done by a **fresh-context implementer**: a subagent (never a fork of the orchestrator), started with a prompt that holds only:
- this change's `specs/domain-packs/spec.md`;
- `packs/README.md`;
- the task text.

It may use public documentation (ctx7 for Godot). The orchestrator reviews the result against the task's jobs and files, and sends gaps back to the same implementer as requirement-level requests.

## 1. Test harness and ui-prototyping

- [x] 1.1 Give `evals/packs/packenv.py` `make_download` a `source` argument (default: the fixtures) so it can copy the repository's `packs/`. Verify that `python -m unittest evals/packs/test_pack_verify.py evals/packs/test_pack_docs.py` still passes unchanged.
- [x] 1.2 Create `evals/packs/test_shipped_packs.py` (P) with every P row of the test map:
  - the static-check functions: description cap, named `references/`, `assets/` and `templates/` paths, document templates, third-party notices, engine-neutral lines and files, the neutral prototype template, the D9 settings (`stage`, `scaling`, `font`, `input model`, `save folder`) in both skills, the godot line wording, and nested signals with a root form;
  - the `ShippedPackCheck`, `SkillStatic`, `ShippedDocs`, `Questions` and `Delivered` classes. The failure scenarios use scratch copies with one defect. The `Delivered` checks hold the D10 keywords in the test.

  Run `python -m unittest evals/packs/test_shipped_packs.py` and see every row fail because `packs/` holds none of the three packs.
- [x] 1.3 Create `evals/update/test_shipped_packs.py` (U) on the `test_packs.py` end-to-end harness, with the repository's `packs/` in the download. It holds:
  - `ShippedInstall` (rows 2, 3, 4 and 22): the six skill trees are byte-equal to the download in every chosen skills directory; `packs.json` ownership; `pack_requires` with no file changed; `godot` alone; removal keeps an edited GDD and drops every `[pack:` line;
  - `Signals` (rows 29-31), over the catalogue the install writes, matched against root, nested and no-match file lists under both readings of `**/`.

  Run `python -m unittest evals/update/test_shipped_packs.py` and see the rows fail because the packs do not exist.
- [x] 1.4 Write `packs/ui-prototyping/skills/ui-prototyping-html/` (fresh-context writer, see above). It holds:
  - `SKILL.md`, with the D9 parameter table naming `stage`, `scaling`, `font`, `input model` and `save folder` (plus the other contract settings), each with its neutral default;
  - the prototyping reference;
  - the token schema with its CSS mapping;
  - `assets/prototype-template.html`, with neutral defaults: a `system-ui` font stack, a stage that follows the window, mouse and keyboard, a state switcher and a small exposed state object.

  Write `packs/ui-prototyping/pack.json`: no signals, no init questions, and the proposal line naming `ui-prototyping-html`. Verify that the ui-prototyping rows of P pass and `bash scripts/update.sh pack-check --pack ui-prototyping` exits 0. Open the template in a browser once to check it works. Flip rows 21, 23 and 32 green, and rows 1, 5-9 and 20 once groups 2-3 also pass them.
- [x] 1.5 Add a `## Packs` section to `README.md`: what a pack is, enabling packs under `packs:` and rerunning the install prompt, and a row for `ui-prototyping`. Add a "Pack layers" note to `packs/README.md`: domain packs require shared packs, stack packs stand alone, and shared packs take settings from the calling skill (D9). Verify with `python -m unittest evals/runner/test_suite_map.py` (README and packs paths are already mapped).

## 2. gamedev

- [ ] 2.1 Write `packs/gamedev/skills/gamedev-design/` (fresh-context writer). It holds:
  - `SKILL.md`, with the request classification and the document lookup (D4). The classification sets only the GDD work before the proposal; every class, tuning included, then goes through the normal Specwright change, and the skill never edits data, code or tests;
  - references: the GDD guide (pressure questions per heading), ideation techniques, the genre guide, `systems-and-balance.md`, `levels-and-encounters.md`, `game-architecture.md` and the game code checks;
  - `templates/brief.md` and `templates/decisions.md`.

  Verify that its static rows pass and that the files listed above are all present.
- [ ] 2.2 Write `packs/gamedev/skills/gamedev-narrative/` (fresh-context writer): `SKILL.md`, the story-craft and delivery references, and `templates/narrative.md`, with the light-narrative option (no `narrative.md` at low weight). Verify the same way.
- [ ] 2.3 Write `packs/gamedev/skills/gamedev-ux/` (fresh-context writer). It holds:
  - `SKILL.md`, which hands prototypes to `ui-prototyping-html` with a value for each D9 setting: the game stage and integer scaling, the font, gamepad-first input and `docs/game/prototypes/` as the save folder;
  - the game UX references, including `references/ux-example.md`, a short worked example;
  - `templates/ux.md`.

  Verify the same way, including rows 24-25.
- [ ] 2.4 Write `packs/gamedev/skills/gamedev-playtest/` (fresh-context writer). It covers:
  - the question and its observable signal;
  - the `[user]` task: what to play, what to judge, who plays;
  - the confidence mark for designer-only verdicts;
  - routing findings;
  - the feel-word-to-values map;
  - recording in `decisions.md` through `gamedev-design`'s template, by skill name;
  - never ticking the task.

  Verify the same way.
- [ ] 2.5 Write `packs/gamedev/pack.json` and `packs/gamedev/documents/gdd.md`:
  - `requires: ["ui-prototyping"]`;
  - the four skills;
  - one context line on where the game documents live;
  - the D10 lines, each concern under exactly one artifact:
    - proposal: classification, sources and sinks, feel words;
    - specs: save compatibility, feel vs layout, idle doesn't win;
    - design: tuning in data, frame budget;
    - tasks: the playtest with who plays, input-device evidence;
    - `apply`: the game code checks;
    - `archive`: the existing line;
  - the `gdd` document at `docs/game/gdd.md`, using the D2 skeleton;
  - six init questions, each starting with the heading it fills;
  - the D3 signals, with root forms.

  Every line is engine-neutral and conditional. Verify that the gamedev rows of P pass and `bash scripts/update.sh pack-check` exits 0. Flip rows 10-19 and 24-25 green.
- [ ] 2.6 Add the `gamedev` row to the README packs section. Add "Moving a hand-made pack" to `packs/README.md`: delete hand copies first, or plan stops with `unmanaged_skill`, and the managed lines replace hand-written `[pack:<name>]` lines. Verify by reading both against the refusal code and ADR 0023 D5.

## 3. godot

- [ ] 3.1 Write `packs/godot/skills/godot-engine/` (fresh-context writer). It covers:
  - the evidence routes: a headless log after an `--import` pass, a scan of the output for errors, and a timeout; a screenshot through a windowed or editor run or `--write-movie`;
  - Resources as data, and never `.tres`/`.res` for player saves;
  - hand-editing rules for `.tscn`/`.tres`;
  - Theme, Control and focus, pixel-art scaling, and localization;
  - test runners, scripted input runs and a debug-only state dump;
  - the 3→4 and 4.4+ tables.

  Check each engine fact against current Godot docs (ctx7). Verify that its static rows pass.
- [ ] 3.2 Write `packs/godot/pack.json`:
  - no `requires`, no document, no questions;
  - signals `project.godot` and `**/project.godot`;
  - the design line on `.tres` tunables;
  - the tool-neutral tasks line: an `[evidence]` task naming the screen or state and how the run reaches it, a headless log or a screenshot from a windowed run or `--write-movie`, a configured Godot MCP server when there is one, before any playtest task.

  Verify that rows 26-28 pass and `bash scripts/update.sh pack-check` exits 0. Flip rows 26-28 green, and rows 1, 5-9 and 20 once all three packs pass them.
- [ ] 3.3 Add the `godot` row to the README packs section. Verify with `python -m unittest evals/packs/test_pack_check.py` (the shipped-pack and context-size checks now read three real packs).

## 4. Real install

- [ ] 4.1 Run `python -m unittest evals/update/test_shipped_packs.py` and see rows 2-4, 22 and 29-31 pass. If one fails, fix the pack, not the test. Flip them green.
- [ ] 4.2 Review the written skills' wording, and have the writer restate any passage that reads as carried over rather than written for Specwright.
- [ ] 4.3 Review the skills' structure (headings, templates, checklists, worked examples) the same way, and have the writer regroup any match the domain does not dictate.

## 5. Map and release

- [ ] 5.1 Run `python -m unittest evals/runner/test_suite_map.py` to confirm that `evals/suites.json` covers both new test modules and every new file under `packs/`. Add a rule if it reports one uncovered.
- [ ] 5.2 Run `release.sh bump --to 0.20.0` and rewrite the summary of the proposal's `## Release Notes` to describe the whole release. Verify with `release.sh check` and `release.sh notes --proposal openspec/changes/gamedev-pack/proposal.md`.

## Workflow follow-up

- CI (`.github/workflows/evals.yml`) runs every suite on Linux, Windows and macOS on the PR. No full local suite run.
- The PR closes #68. Issues #189-#194 stay open as follow-ups (#192-#194: Unity, Unreal and Defold stack packs).
- Archive with `/opsx:archive`, then `specwright-finish` (pr mode). This is the last M6 change, so **close** M6 follows.
- Deferred dogfood check (roadmap, Later): use the packs for a real change in Tower of Lament once 0.20.0 is out.
