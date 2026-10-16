# Tasks

## Test map

Script tests run `scripts/update.sh` against scratch projects, downloads and stores built by `evals/update/fixtures.py`, with the pinned `openspec` 1.14.1 on `PATH`. Prompt and skill text tests live in `evals/git-workflow/test_instructions.py`. Graded agent evals live in `evals/git-workflow/evals.json`.

| Requirement | Scenario | Test file | Test name | State |
|---|---|---|---|---|
| install-update → Update stages the new version before it swaps it in | Update completes | evals/update/test_update.py | TestStage.test_update_completes | red |
| install-update → Update stages the new version before it swaps it in | Interrupted before the swap | evals/update/test_interrupt.py | TestInterrupt.test_kill_before_swap_leaves_previous_runnable | red |
| install-update → Update stages the new version before it swaps it in | Staged copy fails verification | evals/update/test_update.py | TestStage.test_staged_copy_fails_verification | red |
| install-update → Interrupted swap resumes or rolls back | Rerun after an interruption before the swap | evals/update/test_update.py | TestRecover.test_rerun_discards_unswapped_staging | red |
| install-update → Interrupted swap resumes or rolls back | Interrupted during the swap, staged copy complete | evals/update/test_interrupt.py | TestInterrupt.test_kill_during_swap_resumes | red |
| install-update → Interrupted swap resumes or rolls back | Interrupted during the swap, staged copy incomplete | evals/update/test_update.py | TestRecover.test_damaged_staging_rolls_back | red |
| install-update → Interrupted swap resumes or rolls back | Journal from another version | evals/update/test_update.py | TestRecover.test_journal_for_other_version_recovered_first | red |
| install-update → Update installs a release tag by default | Latest tag | evals/git-workflow/test_instructions.py | InstallUpdateLifecycle.test_step3_installs_latest_tag | red |
| install-update → Update installs a release tag by default | Named version has no tag | evals/git-workflow/test_instructions.py | InstallUpdateLifecycle.test_step3_named_version_without_tag_stops | red |
| install-update → Update installs a release tag by default | Named version predates the update script | evals/git-workflow/test_instructions.py | InstallUpdateLifecycle.test_step3_refuses_below_minimum_release | red |
| install-update → Update installs a release tag by default | Latest tag predates the update script | evals/git-workflow/evals.json | eval-install-latest-tag-predates-script | red |
| install-update → Update installs a release tag by default | Script interface differs from the prompt | evals/update/test_update.py + evals/git-workflow/test_instructions.py | TestPlan.test_plan_reports_interface; InstallUpdateLifecycle.test_step3_checks_script_interface | red |
| install-update → Update installs a release tag by default | No tags | evals/git-workflow/test_instructions.py | InstallUpdateLifecycle.test_step3_falls_back_to_main_without_tags | red |
| install-update → Workflow update validates changes in flight | Changes in flight still validate | evals/update/test_inflight.py | TestInflight.test_valid_change_allows_workflow_update | red |
| install-update → Workflow update validates changes in flight | A change in flight fails | evals/update/test_inflight.py | TestInflight.test_failing_change_refuses_workflow_update | red |
| install-update → Workflow update validates changes in flight | Change started after planning | evals/update/test_inflight.py | TestInflight.test_change_started_after_plan_stops_swap | red |
| install-update → Workflow update validates changes in flight | Patch update with a change in flight | evals/update/test_inflight.py | TestInflight.test_patch_update_skips_validation | red |
| install-update → Update finds changes in flight on their branches | Change in flight on its branch only | evals/update/test_inflight.py | TestCollect.test_change_on_branch_only_is_found | red |
| install-update → Update finds changes in flight on their branches | Branch whose change is archived | evals/update/test_inflight.py | TestCollect.test_archived_change_not_in_flight | red |
| install-update → Update finds changes in flight on their branches | Archive of a longer name | evals/update/test_inflight.py | TestCollect.test_archive_name_matched_exactly | red |
| install-update → Update finds changes in flight on their branches | Change only on a remote branch | evals/update/test_inflight.py | TestCollect.test_remote_only_change_is_warning | red |
| install-update → Update report tells running sessions to restart | Version changed | evals/git-workflow/test_instructions.py | InstallUpdateLifecycle.test_step8_restart_notice_after_swap | red |
| install-update → Update report tells running sessions to restart | Refused update | evals/git-workflow/test_instructions.py + evals/update/test_update.py | InstallUpdateLifecycle.test_step8_no_restart_notice_when_unchanged; TestPlan.test_refusal_reports_unchanged | red |
| planning-stores → A store records its schema version and owner | First update claims the store | evals/update/test_store.py | TestStoreRecord.test_first_update_claims_store | red |
| planning-stores → A store records its schema version and owner | Two projects claim at once | evals/update/test_store.py | TestStoreRecord.test_second_claimer_names_owner | red |
| planning-stores → A store records its schema version and owner | Unreadable record | evals/update/test_store.py | TestStoreRecord.test_unreadable_record_stops | red |
| planning-stores → Only the owner replaces a store's schema | Owner updates | evals/update/test_store.py | TestOwner.test_owner_update_leaves_other_project_unchanged | red |
| planning-stores → Only the owner replaces a store's schema | Another project updates within the store's version | evals/update/test_store.py | TestOwner.test_other_project_patch_leaves_store_unchanged | red |
| planning-stores → Only the owner replaces a store's schema | Another project would leave the store's version | evals/update/test_store.py | TestOwner.test_other_project_minor_refused_names_matching_tag | red |
| planning-stores → The store schema is swapped only on a free store | Store busy, schema unchanged | evals/update/test_store.py | TestFreeStore.test_busy_store_patch_same_schema_code_side_only | red |
| planning-stores → The store schema is swapped only on a free store | Store busy, schema changed | evals/update/test_store.py | TestFreeStore.test_busy_store_schema_change_refused | red |
| planning-stores → The store schema is swapped only on a free store | Only this update's staging is untracked | evals/update/test_store.py | TestFreeStore.test_own_staging_does_not_make_store_busy | red |
| planning-stores → A store workflow update waits for other projects' changes | Another project's change in flight | evals/update/test_store.py | TestAttribution.test_other_projects_change_refuses_owner_update | red |
| planning-stores → A store workflow update waits for other projects' changes | Only the owner's change in flight | evals/update/test_store.py | TestAttribution.test_owner_change_validated_and_update_completes | red |
| planning-stores → An interrupted store swap is recovered from its own checkout | Rerun from the same checkout | evals/update/test_interrupt.py | TestStoreInterrupt.test_kill_during_store_swap_rerun_recovers_and_releases_lock | red |
| planning-stores → An interrupted store swap is recovered from its own checkout | Interrupted after taking the lock, before the first rename | evals/update/test_interrupt.py | TestStoreInterrupt.test_kill_after_lock_before_rename_discards_and_releases | red |
| planning-stores → An interrupted store swap is recovered from its own checkout | Rollback after Step 7 failed, store untouched since | evals/update/test_store.py | TestStoreRollback.test_rollback_after_step7_restores_schema_config_and_record | red |
| planning-stores → An interrupted store swap is recovered from its own checkout | Another project's gate meets the update lock | evals/git-workflow/test_instructions.py + evals/git-workflow/evals.json | BranchGateStoreVersion.test_gate_names_update_lock_without_removal; eval-branch-store-update-lock | red |
| planning-stores → An interrupted store swap is recovered from its own checkout | Rollback after another project moved on | evals/update/test_store.py | TestStoreRollback.test_rollback_refused_when_store_busy_keeps_swapped_state | red |
| planning-stores → Change gate checks the store's version | Versions match | evals/git-workflow/evals.json | eval-branch-store-version-match | red |
| planning-stores → Change gate checks the store's version | Project behind the store | evals/git-workflow/test_instructions.py + evals/git-workflow/evals.json | BranchGateStoreVersion.test_gate_compares_major_minor; eval-branch-store-version-behind | red |
| planning-stores → Change gate checks the store's version | Store behind the project | evals/git-workflow/test_instructions.py | BranchGateStoreVersion.test_gate_says_owner_updates_store_first | red |
| planning-stores → Change gate checks the store's version | Project has no completed install | evals/git-workflow/test_instructions.py | BranchGateStoreVersion.test_gate_stops_without_version_file | red |

## 1. ADR and architecture

- [x] 1.1 Write `docs/adr/0011-staged-updates-and-store-ownership.md` (MADR-short, `Status: accepted`, today's date, no `Supersedes`). It records:
  - D1-D3: a journaled script stages and swaps, and the prompt keeps the questions;
  - D5: the owner-only store schema swap on a free store, the gate-lock token and its recovery;
  - the journal in the project as an exception to ADR 0003's local-state location;
  - `STORE` as a second departure from ADR 0003;
  - the `STORE` format and owner id;
  - the rejected alternatives from design.md.

  Add its row to the in-force table in `openspec/architecture.md`, and update any architecture section that describes install/update. Leave `docs/adr/0001-*.md` unchanged. Verify with `grep -n 0011 openspec/architecture.md` and `git diff --stat docs/adr/0001*` (empty).

## 2. Fixtures and staging

- [ ] 2.1 Create `evals/update/fixtures.py`. It builds:
  - a scratch code checkout (git, `openspec/config.yaml`, `openspec/.specwright/VERSION`, chosen skills and agents directories);
  - download trees for two or more versions, made from this repo's `skills/`, `agents/`, `schemas/` and `scripts/` with `VERSION` rewritten and an optional schema edit;
  - a store pair (store repo with its own root, two code repos A and B declaring it);
  - helpers that create change directories in the working tree, on local branches, and on `refs/remotes/origin/*`.

  Also add `evals/update/shims/` with `mv`, `cp` and `rm` wrappers. Each counts its calls in `$UPDATE_SHIM_COUNT`, and at call `$UPDATE_KILL_AT` sends `SIGKILL` to `$UPDATE_KILL_PID` before acting. Verify with a fixture self-test, `evals/update/test_fixtures.py`, that builds each layout and runs the real `openspec validate` in it.
- [ ] 2.2 Write failing tests `TestPlan.test_plan_reports_interface`, `TestPlan.test_refusal_reports_unchanged`, `TestStage.test_update_completes` and `TestStage.test_staged_copy_fails_verification` in `evals/update/test_update.py`. Verify they fail because `scripts/update.sh` does not exist.
- [ ] 2.3 Implement `scripts/update.sh`:
  - one JSON document per subcommand, `release.sh` style;
  - external `mv`/`cp`/`rm` only for file operations;
  - the update lock `openspec/.specwright/update.lock` (pid and host; same-host dead pid replaced and reported);
  - `plan`: `interface: 1`, from/to, `kind` (`fresh|patch|workflow|reinstall|downgrade`), role `none` for now, no writes outside `<download>/.update-scratch/`;
  - `stage`: sibling `.specwright-update-<basename>/new/` per target (D2), agent `model:` lines carried over, SHA-256 manifest, atomic journal `format: 1`;
  - `swap`: two renames per target, journal written before each;
  - `finish`: removes `old/`, the staging and the journal when `VERSION` reads `to`.

  Verify that the four tests pass and flip their rows green.

## 3. Recovery and the interruption criterion

- [ ] 3.1 Write failing tests in `evals/update/test_update.py`:
  - `TestRecover.test_rerun_discards_unswapped_staging`;
  - `TestRecover.test_damaged_staging_rolls_back`;
  - `TestRecover.test_journal_for_other_version_recovered_first`.

  Write failing tests in `evals/update/test_interrupt.py`:
  - `TestInterrupt.test_kill_before_swap_leaves_previous_runnable`, which kills at every counted operation before the first swap rename and asserts the installed files are byte-identical to the previous version, `VERSION` is unchanged and `openspec schema validate specwright` passes;
  - `TestInterrupt.test_kill_during_swap_resumes`, which kills at every operation of the swap, reruns, and asserts the result is exactly the previous or exactly the new version, with no journal, staging or lock left.

  Verify that they fail for the missing `recover`.
- [ ] 3.2 Implement `recover` (discard / resume / roll back / finish-only, per D3) and call it at the start of `plan` when a journal exists. Report `discarded unfinished update to <to>`, `resumed update to <to>` or `rolled back to <prev>`. Verify that the five tests pass and flip their rows green.

## 4. Changes in flight

- [ ] 4.1 Write failing tests in `evals/update/test_inflight.py`:
  - `TestCollect`: branch only, archived, archive of a longer name, remote only;
  - `TestInflight`: valid, failing, started after plan, patch.

  The failing-change fixture uses a download whose schema adds a required artifact ahead of `proposal`. Verify that they fail.
- [ ] 4.2 Implement the D4 collection and validation:
  - working-tree change directories;
  - local `refs/heads/{feat,bugfix,refactor,docs,chore}/*` holding an unarchived change, with an exact archive-name match;
  - remote-only changes as `warnings`;
  - `git archive` extraction into a per-change scratch root;
  - the three checks (`schema validate`, `validate`, `status --json` with its error and dependency rule);
  - repeating the collection and validation in `swap` for every role on a workflow update, stopping on any difference.

  Verify that the eight tests pass and flip their rows green.

## 5. Store ownership

- [ ] 5.1 Write failing tests in `evals/update/test_store.py`:
  - `TestStoreRecord` (claim, second claimer, unreadable);
  - `TestOwner` (owner update, other within version, other refused naming the highest matching tag);
  - `TestFreeStore` (busy with same schema, busy with changed schema, own staging only);
  - `TestAttribution` (other project's change, owner's own change);
  - `TestStoreRollback` (after Step 7 restores schema, `config.yaml` and `STORE`; refused when busy).

  Write failing tests in `evals/update/test_interrupt.py`:
  - `TestStoreInterrupt.test_kill_during_store_swap_rerun_recovers_and_releases_lock`;
  - `TestStoreInterrupt.test_kill_after_lock_before_rename_discards_and_releases`.

  Verify that they fail.
- [ ] 5.2 Implement D5:
  - roles `none|claim|owner|other` from `STORE` and the normalised `origin` id;
  - code-side-only staging for `other`, and the version refusal naming the highest matching tag (from `git ls-remote --tags` on the download's origin);
  - in `swap`: the token in the journal, then `mkdir` of `specwright-gate.lock`, then the `owner` file;
  - under the lock: re-read `STORE`, the free check (own staging and journal-recorded paths excluded), the repeated in-flight check, saving the previous `config.yaml`/`STORE`, swapping the schema, writing `STORE`, and releasing the lock;
  - `store_written` in the `swap` JSON;
  - `recover` taking over and releasing a lock with this checkout's token, and sending a lock whose `owner` file is missing or empty to the user;
  - a rollback that re-runs the store checks.
- [ ] 5.3 Add `update.sh note-config`. The prompt runs it right after Step 5, and it records the merged `<root>/openspec/config.yaml` content hash in the journal, so the recovery free check accepts it (re-check note in review.md). Cover it in `TestStoreRollback.test_rollback_after_step7_restores_schema_config_and_record`, which runs `note-config` between `swap` and the failed Step 7. Verify that every test from 5.1 passes and flip the rows green.

## 6. Install prompt and docs

- [ ] 6.1 Write failing text tests in `evals/git-workflow/test_instructions.py`, class `InstallUpdateLifecycle`, for the six Step 3, Step 4, Step 5, Step 7 and Step 8 rows of the test map, plus:
  - Step 4 runs `update.sh plan`/`stage`/`swap` and acts on refusals;
  - Step 5 runs only for role `none` or `store_written: true`, then `note-config`;
  - Step 7 reports `store config managed by owner <id>` otherwise, and runs `finish` after the stamp.

  Add the graded agent eval `eval-install-latest-tag-predates-script` to `evals/git-workflow/evals.json`, with grader checks in `grade.py` and grader tests in `test_grade.py`. Its fixture is a local repo whose only tag is `v0.5.0`. Verify that the text tests fail.
- [ ] 6.2 Rewrite README install Steps 3-8 to match:
  - Step 3: tag choice, minimum release 0.6.0, interface 1, the offer of `main`;
  - Step 4: the script calls and the restart-relevant `swapped` flag;
  - Step 5: the store role gate and `note-config`;
  - Step 7: the stamp, `store config managed by owner`, then `finish`;
  - Step 8: the restart notice only after a swap, the ref installed, the store role and owner, and remote-only warnings.

  Update the Stores section (owner, `STORE`, transfer by a manual commit, the busy-store rule) and the Evals section (`evals/update`). Add `.specwright-update-*/` to `.gitignore`, and tell adopters they may do the same. In `CONTRIBUTING.md` Testing, name `python -m unittest discover evals/update`. Verify that the text tests pass, run the agent eval and flip the rows green.

## 7. Gates

- [ ] 7.1 Write failing text tests in `evals/git-workflow/test_instructions.py`, class `BranchGateStoreVersion`:
  - the major.minor comparison;
  - "owner updates the store first";
  - the missing `VERSION` stop;
  - the update-lock message without a removal offer, in both `skills/specwright-branch/SKILL.md` and `skills/specwright-roadmap/SKILL.md`.

  Add graded agent evals `eval-branch-store-version-match`, `eval-branch-store-version-behind` and `eval-branch-store-update-lock` with grader checks and grader tests. Verify that the text tests fail.
- [ ] 7.2 Edit `skills/specwright-branch/SKILL.md`: in store step 2, with the lock held, read `VERSION` and `STORE` in one shell call, compare `major.minor`, and stop on a mismatch, a missing `VERSION` or an unreadable `STORE`, naming both versions and the owner. In store step 1, an `owner` whose `change:` starts with `specwright-update` gives "rerun the update from <code>" and no removal offer. Make the same lock-message edit in `skills/specwright-roadmap/SKILL.md` (Committing project files, store step 1). Verify that the text tests pass, re-install the skills, run the three agent evals and flip the rows green.

## 8. Release 0.6.0 bump and integration

- [ ] 8.1 Bump to 0.6.0 with `bash skills/specwright-release/scripts/release.sh bump --to 0.6.0`. Verify that `release.sh check` reports 0.6.0 across every version file, and that `grep -rn '0\.5\.0' VERSION README.md skills/*/SKILL.md` has no version-file hits.
- [ ] 8.2 Run the full suites: `python -m unittest discover evals/update`, `evals/release`, `evals/pr-pair`, `evals/review-routes` and `evals/git-workflow`, plus `openspec schema validate specwright` and `openspec validate safe-update-lifecycle --strict`. All must pass.

## Workflow follow-up

- After the PR merges, publish 0.6.0 with `specwright-release` (v0.6.0 on the merge commit, with a GitHub release). Until it is published, the new prompt stops on the default path, because the highest tag (v0.5.0) predates the update script.
- Re-run the install prompt in this repo from v0.6.0, so the installed copies match.
- M3 dogfood criterion (user-verified): in mythspine or blackgrid, with a change in flight, update from one tagged release to the next, then ship that change.
- Close #36 through the PR.
