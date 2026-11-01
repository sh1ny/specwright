# Tasks

## Test map

| Requirement | Scenario | Test file | Test name | State |
|---|---|---|---|---|
| vcs-backends → On GitButler Specwright runs from wherever it was installed | Skills installed in the repo | evals/vcs/test_gitbutler_probe.py | TestInstallLocation.test_in_repo_scripts_probe_passes | red |
| vcs-backends → On GitButler Specwright runs from wherever it was installed | Skills installed at user level beside an in-repo copy | evals/vcs/test_gitbutler_probe.py | TestInstallLocation.test_user_level_scripts_with_in_repo_copy_probe_passes | red |
| install-update → Every backend takes in-repo and user-level targets | In-repo target for a GitButler project | evals/update/test_update.py | TestGitButlerTargets.test_gitbutler_project_accepts_in_repo_target | red |
| install-update → Every backend takes in-repo and user-level targets | User-level target for a GitButler project | evals/update/test_update.py | TestGitButlerTargets.test_gitbutler_project_accepts_user_level_target | green |
| install-update → The install prompt explains what a user-level install shares | The install prompt on GitButler | evals/git-workflow/test_instructions.py | GitButlerSkillText.test_readme_offers_both_locations_with_warnings | red |

Extra tests (no scenario row):
- `GitButlerSkillText.test_branch_gate_loads_gitbutler_skill_without_copy_check` replaces `test_branch_gate_loads_only_an_unchanged_repo_copy` (design D3).
- `GitButlerSkillText.test_no_user_level_only_wording_left` checks that no live text names `scripts_in_workspace` or `target_in_workspace`, or says user level only (design D2, D4).

## 1. ADR 0021 and the architecture file

- [ ] 1.1 Write `docs/adr/0021-installed-skills-are-the-users-to-manage.md` (MADR-short, `Status: accepted`, `Supersedes:` scoped as in design D4: 0019's install decision and the install part of its binding clause; the settings decision and its binding stay in force), with the decision from D4 and the Claude Code precedence consequence from D2. Leave `docs/adr/0019-*.md` unedited. Verify: `git diff --stat main -- docs/adr/0019-*` is empty, and the new file has Status, Date, Supersedes, Context, Decision and Consequences.
- [ ] 1.2 Update `openspec/architecture.md`: in the decision table, mark the 0019 row's install half (`scripts_in_workspace`, `target_in_workspace`) as superseded by 0021 and add the 0021 row; drop `scripts_in_workspace` from the `vcs.sh` row and `target_in_workspace` and the user-level-only wording from the install prompt row (D4). Verify: `grep -n -E "scripts_in_workspace|target_in_workspace" openspec/architecture.md` shows only the 0019 row's superseded marking; then run `python -m unittest evals/runner/test_suite_map.py` and add a `suites.json` rule or `no_eval` entry if the new ADR is uncovered.

## 2. vcs.sh runs from either location

- [ ] 2.1 In `evals/vcs/test_gitbutler_probe.py`, replace `TestScriptsOutsideWorkspace` with `TestInstallLocation`: `test_in_repo_scripts_probe_passes` (scripts copied under `<repo>/.claude/skills/specwright-pr/scripts/`, stub `but`, `probe` exits 0 with `ok: true`, `backend: gitbutler`) and `test_user_level_scripts_with_in_repo_copy_probe_passes` (scripts outside the repo, `.claude/skills/specwright-pr/` in the work tree, same result). Verify both fail with `scripts_in_workspace`: `python -m unittest evals/vcs/test_gitbutler_probe.py`.
- [ ] 2.2 Remove `WORKSPACE_COPIES`, `workspace_install` and the `scripts_in_workspace` raise from `probe_gitbutler` in `skills/specwright-pr/scripts/vcs.sh`, and any header or usage text naming the code. Verify: rows 1-2 pass and flip green, the rest of `test_gitbutler_probe.py` still passes, and `grep -n scripts_in_workspace skills/specwright-pr/scripts/vcs.sh` prints nothing.

## 3. update.sh takes in-repo targets on GitButler

- [ ] 3.1 In `evals/update/test_update.py` `TestGitButlerTargets`, replace `test_gitbutler_project_refuses_in_repo_target` with `test_gitbutler_project_accepts_in_repo_target` (`plan` and `stage` with `--skills <code>/.claude/skills` and `vcs: gitbutler` each exit 0, no refusal names the directory, and `stage` stages skills for it). Rename `test_fresh_install_has_no_workspace_refusal` so it no longer names the removed refusal, keeping its assertion that no refusal names the directory. Verify the new test fails with `target_in_workspace`: `python -m unittest evals/update/test_update.py -k TestGitButlerTargets`.
- [ ] 3.2 Remove `workspace_targets`, its call in plan (`refusals.extend(workspace_targets(o))`) and the header comment paragraph about `target_in_workspace` from `scripts/update.sh`. Verify: row 3 flips green, row 4 (`test_gitbutler_project_accepts_user_level_target`) still passes, and `grep -n target_in_workspace scripts/update.sh` prints nothing.

## 4. Skill text and README

- [ ] 4.1 In `evals/git-workflow/test_instructions.py` `GitButlerSkillText`, write the failing tests:
  - `test_readme_offers_both_locations_with_warnings` (row 5). Step 2 offers in-repo and user-level targets on every backend and, for GitButler, warns that applied branches share in-repo skills. A "Where the skills live" note says that:
    - a user-level install is shared by every project on the machine and, in Claude Code, overrides in-repo skills of the same name (agents resolve project over user);
    - moving to an in-repo install means updating or removing the user-level copies and restarting sessions, with `scripts_in_workspace` from an older copy as the symptom;
    - OpenSpec's `openspec-*` skills and `/opsx:*` commands are always in the repo;
    - on GitButler, in-repo install files are committed through a GitButler branch of the user's own.
  - `test_branch_gate_loads_gitbutler_skill_without_copy_check`, replacing `test_branch_gate_loads_only_an_unchanged_repo_copy`: no `git diff --quiet <main> HEAD -- <dir>` check, and `but skill check --local --json` still runs.
  - `test_no_user_level_only_wording_left`: README, `skills/specwright-branch/SKILL.md` and `openspec/architecture.md` name neither refusal code outside the 0019 superseded marking and the migration symptom.

  Remove `test_readme_gitbutler_choice_names_user_level_targets` and the user-level assertions it and the GitButler skill-offer test make. Verify they fail: `python -m unittest evals/git-workflow/test_instructions.py -k GitButlerSkillText`.
- [ ] 4.2 Rewrite the README:
  - install prompt Step 2's GitButler bullet (both locations, the GitButler warning);
  - Step 6's GitButler skill offer (drop "user level on this backend");
  - the GitButler section's skill bullet;
  - add the "Where the skills live" note with the points in 4.1. Keep it a warning only (ADR 0021).

  Verify: row 5 flips green.
- [ ] 4.3 Rewrite `skills/specwright-branch/SKILL.md`: drop `scripts_in_workspace` from step 1's error list; in the GitButler tool guidance, drop the unchanged-copy check and the user-level requirement, keeping the `but skill check --local --json` note (D3). Verify: `test_branch_gate_loads_gitbutler_skill_without_copy_check` and `test_no_user_level_only_wording_left` pass, and the whole `GitButlerSkillText` class passes.

## 5. Roadmap and release

- [ ] 5.1 Edit `openspec/roadmap.md` as design D5 states:
  - this change becomes M6 item 4 at 0.14.0;
  - `pack-mechanism` moves to item 5 at 0.15.0, and `gamedev-pack` to item 6 at 0.16.0;
  - the releases criterion ends at 0.16.0;
  - the Later gamedev dogfood check waits for 0.16.0.

  Verify: `grep -n -E "0\.1[4-6]\.0" openspec/roadmap.md` shows exactly those entries.
- [ ] 5.2 Run `release.sh bump --to 0.14.0`, and rewrite the summary of the proposal's `## Release Notes` to describe the whole release. Verify with `release.sh check` and `release.sh notes --proposal openspec/changes/gitbutler-in-repo-install/proposal.md`.

## Workflow follow-up

- After this change merges, rebase `feat/pack-mechanism` on main:
  - its ADR becomes 0022 and its release 0.15.0; `user-verified-tasks` moves to 0.17.0, and its roadmap lines are merged with 5.1's;
  - `packs_user_level` stops naming GitButler, and roadmap init's no-offer rule keys on user-level targets instead of `vcs: gitbutler`;
  - its design review is re-run for that edit.
