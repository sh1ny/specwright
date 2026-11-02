# Tasks

## Test map

Test files: `evals/packs/test_pack_check.py` (PC), `evals/packs/test_pack_verify.py` (PV), `evals/packs/test_pack_docs.py` (PD), `evals/update/test_packs.py` (UP), `evals/git-workflow/test_instructions.py` class `Packs` (TI). Fixture packs live in `evals/packs/fixtures/`.

| Requirement | Scenario | Test file | Test name | State |
|---|---|---|---|---|
| packs → A pack is a directory with a JSON manifest | A valid manifest is accepted | PC | test_valid_manifest_accepted | red |
| packs → A pack is a directory with a JSON manifest | Malformed or unsupported manifests are refused | PC | test_malformed_manifests_refused | red |
| packs → Documents, questions and signals are checked before release | A complete document entry | PC | test_complete_document_entry | red |
| packs → Documents, questions and signals are checked before release | Broken documents, questions or signals are refused | PC | test_broken_documents_questions_signals | red |
| packs → Pack and skill names keep packs apart | Prefixed skills are accepted | PC | test_prefixed_skills_accepted | red |
| packs → Pack and skill names keep packs apart | A core or foreign skill name is refused | PC | test_core_or_foreign_skill_refused | red |
| packs → Pack and skill names keep packs apart | A skill in a longer pack's namespace | PC | test_longest_prefix_owns_skill | red |
| packs → Rules and guidance attach only to known artifacts | A known artifact receives rules | PC | test_known_artifacts_accepted | red |
| packs → Rules and guidance attach only to known artifacts | An unknown artifact or operation is refused | PC | test_unknown_artifact_or_operation | red |
| packs → Every pack line is one owned, bounded line | A plain line is accepted | PC, PV | test_plain_line_accepted, test_installed_line_prefixed | red |
| packs → Every pack line is one owned, bounded line | A multi-line, prefixed or oversized line is refused | PC | test_invalid_lines_refused | red |
| packs → Every pack line is one owned, bounded line | Too many lines | PC | test_too_many_lines_or_context_bytes | red |
| packs → Packs compose through requires | A domain pack with its shared pack enabled | UP | test_requires_both_enabled_installs_both | red |
| packs → Packs compose through requires | A missing requirement or a cycle is refused | UP | test_missing_requirement_and_cycle_refused | red |
| packs → Gate-relaxing wording is refused | A line that relaxes a gate is refused | PC | test_relaxing_line_refused | red |
| packs → Gate-relaxing wording is refused | Strict wording passes | PC | test_strict_wording_passes | red |
| packs → pack-check reports in one JSON document | All packs pass | PC | test_all_packs_pass_and_shipped_packs_pass | red |
| packs → pack-check reports in one JSON document | A named pack is missing | PC | test_named_pack_missing | red |
| packs → A project opts in to packs | A project with no packs | UP | test_no_packs_installs_nothing_extra | red |
| packs → A project opts in to packs | An unknown pack is named | UP | test_unknown_pack_refused | red |
| packs → Pack documents are created once | A missing document is created | PD | test_missing_document_created | red |
| packs → Pack documents are created once | An existing document is kept | PD | test_existing_document_kept | red |
| packs → Pack documents are created once | A document path outside the project | UP | test_pack_doc_path_refused | red |
| packs → Packs are refused on a planning store | Repo-local project with packs | UP | test_repo_local_packs_allowed | red |
| packs → Packs are refused on a planning store | Store-backed project with packs | UP | test_store_packs_refused | red |
| packs → Packs refused for skills dirs outside the project | Project-level skills directories | UP | test_project_level_skills_allowed | red |
| packs → Packs refused for skills dirs outside the project | A user-level skills directory | UP | test_user_level_skills_refused | red |
| install-update → Enabled packs' skills are installed | A pack's skills are installed | UP | test_pack_skills_installed_in_every_dir | red |
| install-update → Enabled packs' skills are installed | An interrupted pack install is recovered | UP | test_interrupted_pack_install_recovered | red |
| install-update → Enabled packs' skills are installed | An interrupted pack removal is recovered | UP | test_interrupted_pack_removal_recovered | red |
| install-update → Enabled packs' skills are installed | A pack that fails its checks installs nothing | UP | test_failing_pack_installs_nothing | red |
| install-update → The install records which skills belong to which pack | The record matches the installed packs | UP | test_record_matches_installed_packs | red |
| install-update → The install records which skills belong to which pack | A rollback restores the old record | UP | test_rollback_restores_record | red |
| install-update → A pack that is no longer enabled is removed | Removing a pack | UP, TI | test_removing_pack_removes_skills, test_readme_step5_removes_previous_pack_lines | red |
| install-update → A pack that is no longer enabled is removed | A removal that would break a requirement | UP | test_removal_breaking_requirement_refused | red |
| install-update → The install never touches a skill it did not install | A hand-copied skill with a pack skill's name | UP | test_unmanaged_skill_refused | red |
| install-update → The install never touches a skill it did not install | A clone without the record | UP | test_identical_unrecorded_skill_adopted | red |
| install-update → The install never touches a skill it did not install | A hand copy of a pack that is not enabled | UP | test_hand_copy_of_disabled_pack_untouched | red |
| install-update → The install never touches a skill it did not install | A user's unrelated skill | UP | test_unrelated_skill_untouched | red |
| install-update → Pack lines are merged by prefix and verified | Lines reach their artifacts | PV | test_lines_reach_artifacts_and_operations | red |
| install-update → Pack lines are merged by prefix and verified | A missing, duplicated or stale line | PV | test_missing_duplicate_stale_lines | red |
| install-update → Pack lines are merged by prefix and verified | A removed pack's lines after a rerun past the swap | UP, PV | test_packs_previous_from_journal_after_swap, test_previous_pack_line_not_enabled | red |
| install-update → Pack lines are merged by prefix and verified | Hand-written lines of a pack the project never enabled | PV, TI | test_unmanaged_pack_lines_pass, test_readme_step5_keeps_unmanaged_pack_lines | red |
| install-update → The settings merge treats packs as user data | Enabled packs survive an update | TI | test_readme_step6_packs_are_user_data | red |
| install-update → The settings merge treats packs as user data | A template key under packs | TI | test_readme_step6_never_adds_packs_keys | red |
| install-update → The install prompt drives update-script interface 2 | Matching interface | UP, TI | test_plan_reports_interface_2, test_readme_accepts_interface_2 | red |
| install-update → The install prompt drives update-script interface 2 | An older download without packs | TI | test_readme_accepts_interface_1_without_packs | red |
| install-update → The install prompt drives update-script interface 2 | An older download with packs enabled | TI | test_readme_refuses_interface_1_with_packs | red |
| install-update → Pack documents are created by an idempotent step | Documents after a finished install | PD | test_pack_docs_creates_after_stamp | red |
| install-update → Pack documents are created by an idempotent step | Interrupted document creation | PD | test_pack_docs_rerun_completes | red |
| install-update → The previously enabled packs come from the start | An uninterrupted update that removes a pack | UP | test_packs_previous_from_record | red |
| install-update → The previously enabled packs come from the start | No previous record | UP | test_packs_previous_empty_without_record | red |
| project-planning → Roadmap init suggests packs | A Godot project is offered the game packs | TI | test_roadmap_init_offers_packs_with_requirements | red |
| project-planning → Roadmap init suggests packs | The user declines | TI | test_roadmap_init_enables_only_on_yes | red |
| project-planning → Roadmap init's pack offer names the in-repo install need | A pack offer in a project that installs at user level | TI | test_roadmap_init_offer_names_in_repo_need | red |
| project-planning → Roadmap init offers no pack where refused | A project where packs cannot be installed | TI | test_roadmap_init_no_packs_on_store | red |
| project-planning → Roadmap init offers no pack where refused | A repo-local Git project | TI | test_roadmap_init_offers_packs_repo_local | red |
| project-planning → Roadmap init includes enabled packs | Pack questions join the interview | TI | test_roadmap_init_asks_pack_questions_in_two_rounds | red |
| project-planning → Roadmap init includes enabled packs | A pack document edited after the baseline passed | TI | test_pack_documents_are_not_gated | red |
| project-planning → Roadmap init includes enabled packs | A pack document is missing at init | TI | test_roadmap_init_missing_pack_document | red |
| project-planning → Roadmap pack mode | Setting up a pack after the baseline | TI | test_roadmap_pack_mode_commits_on_docs_branch | red |
| project-planning → Roadmap pack mode | The pack is not installed | TI | test_roadmap_pack_mode_needs_installed_pack | red |

## 1. ADR, architecture and follow-up issues

- [x] 1.1 Write `docs/adr/0023-packs-are-additive-bundles-in-the-release.md` (MADR short, `Status: accepted`, today's date) from design D1, D2, D4, D5, D6, D9 and D10, naming `packs.json` as a third departure from ADR 0003 and stating that it narrows ADR 0021 for packs only (design D9: a pack-enabled install refuses a user-level skills target; core skills and agents still install where the user chooses); add its row, reading "adds to 0021", to the in-force index in `openspec/architecture.md` and a `packs/` + `pack-check`/`pack-verify`/`pack-docs` note in Components. Verify: `python -m unittest evals/git-workflow/test_specs_strict.py` passes and the index lists 0023.
- [x] 1.2 File two GitHub issues as KintsugiBot (fenced per `as.sh`): "Packs on planning stores and user-level skills directories" (D9's refusals, with the design's reasons) and "Spike changes for exploratory work (find the fun)" (from #68); reference both from #68. Verify: `gh issue view` shows each open and linked from #68.

## 2. pack-check and the pack format

- [ ] 2.1 Create the `evals/packs` suite with fixture packs (`valid-web`, `valid-ui-base` + `valid-domain` requiring it, and one broken fixture per refusal code), add `packs/**` and `evals/packs/**` rules to `evals/suites.json`, and write the PC tests from the test map; verify they fail (`python -m unittest evals/packs/test_pack_check.py`: no `pack-check` subcommand) and `python -m unittest evals/runner/test_suite_map.py` passes.
- [ ] 2.2 Implement `update.sh pack-check [--pack <name>]...`: manifest shape and `format`, name rules (reserved `specwright`/`openspec`/`opsx`), longest-prefix skill ownership, skill directories and `SKILL.md`, artifact ids from the download's `schemas/specwright/schema.yaml`, operations `apply`/`archive`, line rules (single line, ≤500 chars, no `[pack:`), 40 lines and 2048 context bytes per pack, documents/init/signals checks, `requires` existence and cycles, and the gate-term × relaxing-term check (capitals-only `LIGHT`/`FULL`, negated `trip`); one JSON document, exit 0/1, no writes. Verify: every PC test passes; flip the PC rows green.
- [ ] 2.3 Write `packs/README.md` ("Writing a pack"): layout, every `pack.json` field, the prefix and longest-prefix rules, additive-only (structural guarantee, then the two term lists, documented as deliberately crude), conditional wording for rules, bounds, `requires`, documents and init questions, signals, that pack skills never take over Specwright's commit, review or verify ownership, and the v1 refusals (stores, user-level skills). Add a PC test that the README's term lists equal the script's. Verify: `test_readme_term_lists_match_script` passes.

## 3. Plan with packs

- [ ] 3.1 Write the UP plan tests (no packs, unknown pack, requires, cycle, removal breaking a requirement, store and user-level refusals, project-level allowed, unmanaged/adopted/hand-copy/unrelated skills, `pack_doc_path`, failing pack, interface 2, `packs_previous` from record and empty) against a fixture download holding the fixture packs; verify they fail for the right reason (`python -m unittest evals/update/test_packs.py`).
- [ ] 3.2 Implement in `update.sh plan`: `--pack` and `--pack-doc <pack>.<id>=<path>` options, pack-check on the enabled packs, requires closure and install order, `packs_on_store` and `packs_user_level`, pack skill items in each skills group, adoption of byte-identical unrecorded skills and `unmanaged_skill` otherwise, recorded-but-unshipped skills as orphans (hand copies of disabled packs neither listed nor touched), `remove` items for recorded skills of packs no longer enabled (only where the target holds them), `pack_doc_path` checks and document existence, `packs_previous`, `packs` and `INTERFACE = 2` in the document. Update the header comment. Verify: the 3.1 tests pass; flip their rows green.

## 4. Stage, swap, recover and the record

- [ ] 4.1 Write the UP tests for installing skills into two skills dirs, an interrupted install, an interrupted removal (resume and rollback), the record's content, a rollback restoring the record or its absence, removing a pack, and `packs_previous` from the journal after the swap; verify they fail.
- [ ] 4.2 Implement journal format 2 (format 1 still recovered; `prev_packs` written by `stage`), `remove` items in `swap_loop`, `recover_core` (a removal past `pending` means started; `old/<name>` with no target counts as done on resume) and `recover_rollback`, and `openspec/.specwright/packs.json` (format 1: enabled packs with version, skills, document paths, init questions; catalogue of every downloaded pack) staged and swapped as a file item, always written. Verify: the 4.1 tests and the existing `evals/update/test_interrupt.py` pass; flip the rows green.

## 5. pack-verify and pack-docs

- [ ] 5.1 Write the PV tests (lines reach rules, apply and archive guidance and context exactly once through real `openspec instructions` in a scratch root; missing, duplicate and `not_enabled` lines with `--previous`; unmanaged `[pack:` lines pass; core context lines still delivered, including a context pushed over 50 KB) and the PD tests (created after stamp, existing kept, rerun completes); verify they fail.
- [ ] 5.2 Implement `update.sh pack-verify --previous <name>...` (scratch root under `<download>/.update-scratch/` with the merged `config.yaml`, the download's schema and an empty change; uses `run_openspec`'s deadline) and `update.sh pack-docs` (no journal; creates missing documents from templates, reports `created`/`kept`). Verify: PV and PD tests pass; flip the rows green.

## 6. Install prompt and settings template

- [ ] 6.1 Write the TI README tests (Step 3 accepts interface 2, and 1 only with no pack enabled and none in `packs.json`; Step 4 passes `--pack`/`--pack-doc` and reports pack refusals; Step 5 removes only lines of packs enabled now or in `packs_previous`, writes double-quoted entries, keeps and reports other `[pack:` lines, runs pack-verify; Step 6 treats `packs.` as user data; Step 7 checks pack skills and pack-verify; after the stamp `pack-docs`; Step 8 reports packs, adopted skills, unmanaged lines and documents; README says to treat `packs.json` like `VERSION`; Step 2 says, when `packs:` enables a pack, that packs need in-repo skills directories and a user-level target is refused (`packs_user_level`), also in its GitButler bullet); verify they fail.
- [ ] 6.2 Edit the README install prompt Steps 2-8 accordingly, add a commented `packs:` example to `templates/openspec/specwright.yaml`, and add a short "Packs" section to the README pointing at `packs/README.md`. Verify: the 6.1 tests and `python -m unittest evals/git-workflow/test_instructions.py` pass; flip the rows green.

## 7. Roadmap init and pack mode

- [ ] 7.1 Write the TI roadmap tests (init matches signals over tracked and untracked files from the `packs.json` catalogue, offers a pack with its requirements and says packs install only into in-repo skills directories (a user-level install refuses them), enables only on yes and then says to rerun the install and run **pack**; offers none on a store; asks enabled packs' questions within the two batched rounds; names pack documents as context, never gated; missing document → rerun the install; **pack** mode asks one round, commits on `docs/pack-<name>`, runs no review, needs an installed pack); verify they fail.
- [ ] 7.2 Edit `skills/specwright-roadmap/SKILL.md`: init steps 1-2 and 5, a new **pack** section, and the "Committing project files" procedure covering **pack**. Verify: the 7.1 tests pass; flip the rows green.

## 8. End-to-end and release

- [ ] 8.1 Add one UP end-to-end test: install the `valid-domain` + `valid-ui-base` fixture packs into a fixture project with `update.sh plan/stage/swap`, merge their lines as Step 5 specifies (test helper), run `pack-verify`, stamp, `finish`, `pack-docs`; then remove both and verify the skills, lines and record are gone and the documents kept. Verify: the test passes on this machine; CI runs it on all three OSes.
- [ ] 8.2 Run `bash skills/specwright-release/scripts/release.sh bump --to 0.16.0` and rewrite the summary of the proposal's `## Release Notes` to describe the whole release. Verify: `release.sh check` and `release.sh notes --proposal openspec/changes/pack-mechanism/proposal.md` pass.

## Workflow follow-up

- Ship through the PR flow; CI runs every suite on Linux, Windows and macOS (no local full suite runs).
- After merge and archive, publish v0.16.0 and offer roadmap **next** (`user-verified-tasks`).
