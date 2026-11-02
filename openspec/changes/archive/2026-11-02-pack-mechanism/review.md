# Review

## Metadata

- **Round:** 4
- **Prior round:** 3 APPROVE_WITH_CHANGES (0 Critical; required M1 previous enabled packs read from the swapped `packs.json`, fixed by `prev_packs`/`packs_previous`; M2 Flow & State Gaps and Risks still on the catalogue rule; M3 D4 orphan rule contradicted the spec; all three applied and re-checked, CHANGES_APPLIED: yes)
- **Reviewer:** fresh-context subagent (Claude Code, specwright-reviewer)
- **Reviewed:** openspec/changes/pack-mechanism/proposal.md, design.md, tasks.md, specs/packs/spec.md, specs/install-update/spec.md, specs/project-planning/spec.md (`openspec validate pack-mechanism --strict`: valid); review.md (round 3); `git diff HEAD -- openspec/changes/pack-mechanism` (the post-rebase edits: OpenSpec 1.16.0, update.sh line numbers, 0.16.0/0.17.0/0.18.0 versions, ADR 0023, D9/D10 and the specs dropping the GitButler refusal); `git diff origin/main -- openspec/roadmap.md`; openspec/architecture.md (in-force index, Install prompt row); ADRs 0021 and 0022 (and 0019 as superseded by 0021); README.md install prompt Steps 2, 3, 6 and "Where the skills live"; scripts/update.sh (header for plan, stage, swap, finish and recover; `INTERFACE` :906, journal reader :986, `yaml_setting` :1015, `run_openspec` :1159, `inflight_entries` :1242, `build_groups` :1728-1756, `swap_loop` :722, `recover_core` :570); skills/specwright-roadmap/SKILL.md "Committing project files"; installed OpenSpec 1.16.0 (`npm root -g`/@fission-ai/openspec/dist: core/project-config.js :6 `OPERATION_IDS`, :183 `MAX_CONTEXT_SIZE`, :191 `describeRulesShapeError`, :275 context ignore, :406-411 `validateConfigRules`, :106-120 guidance parsing; commands/workflow/instructions.js :388 apply and :641 archive guidance). Installed project skills named by the request: none. No referenced stores. Re-check runs (Required Changes only, plus S1 and S2 as applied): design.md D9, D10, ADRs, Flow & State Gaps, Context; specs/project-planning/spec.md (the new requirement "Roadmap init's pack offer names the in-repo install need" and the Godot scenario); tasks.md test map, 1.1, 6.1 and 7.1; the schema's tasks instruction (schema.yaml:427, the test map must map every scenario); `openspec validate pack-mechanism --strict` (valid). The first re-check found the new scenario's test map row missing; the second re-check found it added.

<!-- This verdict covers only the contents reviewed. Editing proposal, specs or design afterward (other than applying Required Changes, or an edit confined to the proposal's `## Release Notes` section) voids it. -->

## Findings

Checked against current main and holding:

- **OpenSpec 1.16.0 claims hold.** In the installed 1.16.0 dist, `OPERATION_IDS = ['apply', 'archive']` is at project-config.js:6, `MAX_CONTEXT_SIZE` at :183, the context ignore at :275, `describeRulesShapeError` at :191 (a non-string entry drops the artifact's whole rules list), and the unknown-artifact warning in `validateConfigRules` at :406-411. Guidance lists behave the same way as rules lists: a non-string entry drops that operation's guidance (:110-113). So D5's double-quoting rule is needed for `operations.<op>.guidance` as well as for `rules`. D5 applies it to "list entries", which covers both. `instructions apply` and `instructions archive` read operation guidance (instructions.js:388, :641), as pack-verify assumes.
- **update.sh references hold**, with one off by two (S2): `INTERFACE = 1` :906, `yaml_setting` :1015, `run_openspec` :1159, `inflight_entries` :1242, the `specwright-*` glob :1731 and the orphan glob :1741. The journal reader refuses any format other than 1 (:986), so D3's claim that an older download refuses a format-2 journal as unreadable is true.
- **The resumed `swapped` path keeps the journal.** plan runs recover first when a journal is pending. For phase `swapped`, recover resumes and keeps the journal (header, recover "resumed"), so D5's `packs_previous` "from the journal when one is pending" can be read on the documented rerun. There is one exception, covered in S1.
- **D9/D10 after ADR 0021.** GitButler is no longer refused, which ADR 0021's Consequences expect ("GitButler projects can install in the repo ... and can use packs"). The project-planning requirement, the test map (`test_roadmap_init_no_packs_on_store`), tasks 1.2 and 7.1, the Mechanism ledger and the proposal all drop the GitButler case consistently. The ADR is 0023, the next free number after 0022.
- **ADR 0022 and the other merged changes.** Nothing conflicts. Reviewer rules live under `pr.reviewers.<login>.report`, which README Step 6 already treats as user data (README:319). `packs.` joins that list, and no merge-policy comparison (ADR 0020/0022) reads `packs:`. The roadmap edit matches the proposal: change 7 at 0.16.0, `user-verified-tasks` at 0.17.0, `gamedev-pack` at 0.18.0, and the release list extended.

### Critical (blocking)

None.

### Moderate

**M1. `packs_user_level` conflicts with ADR 0021 as written, and users first hear about it at plan, after the README has told them to choose freely.** (Decisions: contradiction with an in-force ADR)
ADR 0021's Decision says Specwright "warns where the risk is chosen ... and never refuses to run because of where or how the skills are installed". README Step 2 ends with "This is a warning only: install where the user chooses" (README:124). For GitButler it recommends the user-level install as the way to avoid sharing skills across branches (README:126-130). D9 and the packs requirement "Packs are refused for skills directories outside the project in v1" refuse every user-level target that has a pack enabled. ADR 0021's own Context foresees this ("Pack skills in a shared user-level folder cannot be owned per project"), but its Decision text does not carve it out. The design's ADRs entry lists 0021 as constraining without naming the tension, and the schema requires the design to be coherent with in-force ADRs or flag the conflict.

This has three concrete consequences:
- (a) ADR 0023 as planned (task 1.1) does not say that it narrows 0021. The pre-ship review, or a later reader of the in-force index, finds a refusal that the index says Specwright never makes.
- (b) A GitButler user who follows Step 2's advice and installs at user level, then enables a pack, is stopped at plan with `packs_user_level`. Nothing earlier tells them, and task 6.1 tests nothing in Step 2.
- (c) Roadmap init (D10, the requirement "Roadmap init offers no pack where the install refuses packs") now checks only for a store. In a user-level project it offers `gamedev`, writes `packs:` on the user's yes and says to rerun the install, which then refuses. From then on every update refuses until the user removes `packs:` or reinstalls in the repo. Before round 4 the GitButler check covered the main user-level case. Dropping it left this path open.

Nothing is written before the refusal, so no data is lost. The fix is cheap and keeps the decision.

**Re-check:** (a), (b) and (c) are all applied (see Required Changes).

### Suggestions

**S1. A resumed swap that recover finishes on its own loses `prev_packs`.** The update.sh header (recover, "resumed") says that when the pending update is not the download's own version, recover writes VERSION and finishes the update, which removes the journal. This happens when the user reruns the prompt with a newer download after an interrupted swap. The plan that triggered recover then reads `packs_previous` from the swapped `packs.json`. A pack removed in the interrupted run is not in that list, so its `[pack:<name>] ` lines are kept as "not managed" from then on. The report shows them, so the user can see the problem, but no update removes them. A cheap fix: on that path, carry the journal's `prev_packs` in plan's `recovered` object (`recovered.prev_packs`), and have plan merge it into `packs_previous`. Add a UP test. If this is not fixed, give the case one line under Flow & State Gaps.

**Re-check:** applied as the fallback. Flow & State Gaps has a new entry, "Removal interrupted after the swap, then rerun with a newer download", which says that the newer download's plan recovers the pending update and deletes the journal. It accepts the case for v1 because the report names the lines. This matches the update.sh header.

**S2. Context line reference.** "one group per target directory (`scripts/update.sh:1730`)": `build_groups` starts at :1728. Change it to `:1728`.

**Re-check:** applied (Context now cites `:1728`).

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. M1(a): In design.md's ADRs section, change the 0021 entry to say that ADR 0023 narrows ADR 0021 for packs only. 0021 lets the user choose the install location and never refuses because of it. Packs, which need per-project ownership, refuse a user-level skills target (`packs_user_level`). Core skills and agents still install wherever the user chooses. Add the same sentence to task 1.1's ADR content, and make the index row read "adds to 0021". **Checked: applied.** The ADRs entry for 0021 and D9 now state the packs-only narrowing in those terms. Task 1.1 states that ADR 0023 narrows 0021 for packs only and gives its index row as "adds to 0021".
2. M1(b): In tasks.md 6.1, add a TI test that README Step 2 says, when `packs:` enables a pack, that packs need in-repo skills directories and that a user-level target will be refused (`packs_user_level`). Make the same note in the GitButler bullet, which recommends user level. Task 6.2 then makes the edit. Add "Step 2 warns that packs need in-repo skills directories" to the README bullet in D9 or D11. **Checked: applied.** Task 6.1 now covers the Step 2 note and the GitButler bullet. D9 says that README Step 2 warns, including in its GitButler bullet. Task 6.2 edits Steps 2-8.
3. M1(c): In specs/project-planning/spec.md, requirement "Roadmap init suggests packs and never enables one by itself", require init's pack offer to say that packs install only into in-repo skills directories, and that an install at user level refuses them. Add the matching THEN clause to "A Godot project is offered the game packs". Update D10 to say the same. Add this to task 7.1's test list. **Checked: applied.** The author put the rule in its own requirement, "Roadmap init's pack offer names the in-repo install need", with the scenario "A pack offer in a project that installs at user level", so that strict validation passes. That is acceptable. The Godot scenario's THEN has the clause, D10 says the same and task 7.1 lists the test. The test map now has the row for the new scenario (`test_roadmap_init_offer_names_in_repo_need`, after "The user declines"), so every scenario is mapped as schema.yaml:427 requires. `openspec validate pack-mechanism --strict` passes.

<!-- yes (applied, and re-checked by the reviewer - only the reviewer sets it) | no (outstanding) | n/a (any other verdict) -->
CHANGES_APPLIED: yes

## Rebuttals

None needed. The author applied all three Required Changes, and the reviewer re-checked them in separate runs. The first re-check found that Required Change 3 lacked a test map row; that row is now present. S1 was answered with the documented fallback, which is acceptable for a Suggestion, and S2 is applied.
