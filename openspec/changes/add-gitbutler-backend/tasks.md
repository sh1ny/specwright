# Tasks

## Test map

Every real-`but` test lives in `evals/vcs/` (D10) and uses `evals/vcs/butenv.py` (scratch repo, local bare remote, fake `gh`). Every such test skips with `but not installed` locally unless `SPECWRIGHT_REQUIRE_BUT=1`. The `as.sh` tests in `evals/pr-pair/test_as_gitbutler.py` use a fake `but` that records its environment, so they need no real `but`.

| Requirement | Scenario | Test file | Test name | State |
|---|---|---|---|---|
| vcs-backends → The backend is chosen per repo | Unset means Git | evals/vcs/test_settings.py | test_unset_vcs_is_git | green |
| vcs-backends → The backend is chosen per repo | Store keeps its own backend | evals/vcs/test_settings.py | test_store_vcs_not_inherited | green |
| vcs-backends → The backend is chosen per repo | GitButler code repo with a Git store | evals/vcs/test_settings.py | test_gitbutler_code_with_git_store | red |
| vcs-backends → The backend is chosen per repo | Unknown value | evals/vcs/test_settings.py | test_unknown_vcs_stops | red |
| vcs-backends → The backend is chosen per repo | GitButler store | evals/vcs/test_settings.py | test_gitbutler_store_unsupported_vcs | red |
| vcs-backends → The backend is chosen per repo | GitButler with a local finish | evals/vcs/test_settings.py | test_gitbutler_local_finish_unsupported | red |
| vcs-backends → The backend is chosen per repo | GitButler with no finish setting | evals/vcs/test_settings.py | test_gitbutler_absent_finish_unsupported | red |
| vcs-backends → The GitButler backend is probed before any `but` command | `but` missing | evals/vcs/test_gitbutler_probe.py | test_but_missing_stops_before_write | red |
| vcs-backends → The GitButler backend is probed before any `but` command | Repo not managed by GitButler | evals/vcs/test_gitbutler_probe.py | test_unmanaged_repo_not_set_up | red |
| vcs-backends → The GitButler backend is probed before any `but` command | Target is another branch | evals/vcs/test_gitbutler_probe.py | test_target_mismatch_stops | red |
| vcs-backends → The GitButler gate applies the change branch beside the others | Other branches applied | evals/vcs/test_gitbutler_branch.py | test_branch_create_beside_applied | red |
| vcs-backends → The GitButler gate applies the change branch beside the others | Name already taken | evals/vcs/test_gitbutler_branch.py | test_branch_create_name_taken | red |
| vcs-backends → On GitButler the change branch is resolved by name | Workspace HEAD | evals/vcs/test_gitbutler_state.py | test_state_reads_branch_not_head | red |
| vcs-backends → On GitButler the change branch is resolved by name | Another agent's edits during the completion check | evals/vcs/test_gitbutler_state.py | test_clean_ignores_other_branch_paths | red |
| vcs-backends → On GitButler the change branch is resolved by name | Own unnamed edit at the completion check | evals/vcs/test_gitbutler_state.py | test_own_unassigned_edit_not_clean | red |
| vcs-backends → On GitButler the change branch is resolved by name | Finish commits the archive on the change branch | evals/vcs/test_gitbutler_commit.py | test_archive_commit_names_exact_paths | red |
| vcs-backends → On GitButler the change branch is resolved by name | Cleanup switches to main | evals/vcs/test_gitbutler_state.py | test_switch_to_main_is_noop | red |
| vcs-backends → On GitButler the change branch is resolved by name | Branch unapplied mid-change | evals/vcs/test_gitbutler_state.py | test_branch_not_applied_stops | red |
| vcs-backends → On GitButler a commit takes only its named paths into the change branch | Unrelated edits stay uncommitted | evals/vcs/test_gitbutler_commit.py | test_commit_takes_only_named_paths | red |
| vcs-backends → On GitButler a commit takes only its named paths into the change branch | Path belongs to another branch | evals/vcs/test_gitbutler_commit.py | test_commit_path_owned_elsewhere_stops | red |
| vcs-backends → On GitButler a commit takes only its named paths into the change branch | Short path that looks like an ID | evals/vcs/test_gitbutler_commit.py | test_commit_short_path_not_cli_id | red |
| vcs-backends → On GitButler a commit takes only its named paths into the change branch | Trailers kept | evals/vcs/test_gitbutler_commit.py | test_commit_keeps_trailers | red |
| vcs-backends → Change ranges read the change branch tip | Other applied branches | evals/vcs/test_gitbutler_ranges.py | test_preship_range_uses_branch_tip | red |
| vcs-backends → Change ranges read the change branch tip | Gate after the archive commit | evals/vcs/test_gitbutler_ranges.py | test_gate_after_archive_resolves_branch_tip | red |
| vcs-backends → Change ranges read the change branch tip | Version check ignores other branches | evals/vcs/test_gitbutler_ranges.py | test_release_check_reads_branch_tip | red |
| vcs-backends → Change ranges read the change branch tip | Branch not given | evals/vcs/test_gitbutler_ranges.py | test_without_branch_stops | red |
| vcs-backends → Change ranges read the change branch tip | Branch moved after the review | evals/vcs/test_gitbutler_ranges.py | test_branch_moved_voids_record | red |
| vcs-backends → Change ranges read the change branch tip | Git unchanged | evals/review-routes/test_review_run.py | test_record_preship_repo_local_keyed_by_code_head | green |
| vcs-backends → A GitButler push publishes only the change branch | Ship with another branch applied | evals/vcs/test_gitbutler_push.py | test_push_only_change_branch | red |
| vcs-backends → A GitButler push publishes only the change branch | Rewritten branch | evals/vcs/test_gitbutler_push.py | test_push_rejected_never_forced | red |
| vcs-backends → The GitButler pull never rebases another branch | Cleanup alone in the workspace | evals/vcs/test_gitbutler_pull.py | test_pull_alone_runs_fenced | red |
| vcs-backends → The GitButler pull never rebases another branch | Another branch applied | evals/vcs/test_gitbutler_pull.py | test_pull_skipped_other_branch | red |
| vcs-backends → The GitButler pull never rebases another branch | Linked worktree | evals/vcs/test_gitbutler_pull.py | test_pull_skipped_linked_worktree | red |
| vcs-backends → The GitButler pull never rebases another branch | Finish after a skipped pull | evals/vcs/test_gitbutler_pull.py | test_finish_reads_fetched_main | red |
| vcs-backends → A GitButler branch is deleted only once merged | Squash-merged PR | evals/vcs/test_gitbutler_delete.py | test_delete_after_squash_merge | red |
| vcs-backends → A GitButler branch is deleted only once merged | Pull skipped | evals/vcs/test_gitbutler_delete.py | test_delete_left_applied_when_base_lacks_merge | red |
| vcs-backends → A GitButler branch is deleted only once merged | Not merged | evals/vcs/test_gitbutler_delete.py | test_delete_unmerged_left_applied | red |
| vcs-backends → A GitButler branch is deleted only once merged | `but` write fails with `core.autocrlf=true` (design.md Risks, Line endings) | evals/vcs/test_gitbutler_delete.py | test_but_error_names_autocrlf | red |
| vcs-backends → No other Git write runs under GitButler | Full PR flow on GitButler | evals/vcs/test_gitbutler_flows.py | test_full_pr_flow_git_write_boundary | red |
| vcs-backends → No other Git write runs under GitButler | GitButler code repo with a Git store | evals/vcs/test_gitbutler_flows.py | test_cleanup_plan_routes_code_repo_through_vcs | red |
| vcs-backends → No other Git write runs under GitButler | Feedback pass with another agent's edits | evals/vcs/test_gitbutler_flows.py | test_feedback_pass_ignores_other_and_preexisting_paths | red |
| vcs-backends → The Git backend refuses to write in a GitButler workspace | `vcs` unset in a GitButler workspace | evals/vcs/test_gitbutler_probe.py | test_git_backend_refuses_workspace_head | red |
| vcs-backends → The Git backend refuses to write in a GitButler workspace | `vcs` unset with one applied branch | evals/vcs/test_gitbutler_probe.py | test_git_backend_refuses_single_branch_mode | red |
| vcs-backends → The Git backend refuses to write in a GitButler workspace | GitButler metadata with HEAD on main | evals/vcs/test_gitbutler_probe.py | test_git_backend_refuses_head_on_main | red |
| vcs-backends → Debug never stashes on GitButler | Dirty workspace during a reproduction | evals/git-workflow/test_instructions.py | test_debug_never_stashes_on_gitbutler | red |
| vcs-backends → The archive undo plan uses GitButler on a GitButler repo | Undo a deferred archive | evals/vcs/test_gitbutler_undo.py | test_undo_plan_uses_but_commit | red |
| vcs-backends → GitButler's agent skills are offered, never installed silently | Skill not installed | evals/git-workflow/test_instructions.py | test_branch_gate_notes_missing_but_skill | red |
| vcs-backends → GitButler's agent skills are offered, never installed silently | Install without consent | evals/git-workflow/test_instructions.py | test_but_skill_install_only_on_yes | red |
| preship-review → The pre-ship review runs when every task is committed | Default settings | evals/review-routes/test_skill_text.py | test_commit_step3_runs_preship_before_handoff | green |
| preship-review → The pre-ship review runs when every task is committed | Opted out | evals/review-routes/test_skill_text.py | test_commit_step3_preship_false_skips | green |
| preship-review → The pre-ship review runs when every task is committed | Store-backed change | evals/review-routes/test_skill_text.py | test_subagent_preship_dispatch_names_root_and_store | green |
| preship-review → The pre-ship review runs when every task is committed | GitButler workspace | evals/review-routes/test_skill_text.py | test_preship_range_names_branch_tip | red |
| github-identity → GitButler pulls are fenced like git | Cleanup pull | evals/pr-pair/test_as_gitbutler.py | test_but_pull_uses_fenced_token | red |
| github-identity → GitButler pulls are fenced like git | Other `but` subcommand | evals/pr-pair/test_as_gitbutler.py | test_but_other_subcommand_refused | red |
| github-identity → GitButler pulls are fenced like git | Directory option | evals/pr-pair/test_as_gitbutler.py | test_but_directory_option_refused | red |
| eval-runner → Suites that need GitButler run with a pinned `but` in CI | CI run | evals/runner/test_ci_workflow.py | test_workflow_installs_pinned_but_for_vcs_only | red |
| eval-runner → Suites that need GitButler run with a pinned `but` in CI | Upstream released a new version | evals/runner/test_ci_workflow.py | test_workflow_pins_but_build_url | red |
| eval-runner → Suites that need GitButler run with a pinned `but` in CI | Downloaded bytes differ | evals/runner/test_ci_workflow.py | test_workflow_checks_but_sha256_before_use | red |
| eval-runner → Suites that need GitButler run with a pinned `but` in CI | Local run without `but` | evals/runner/test_butenv.py | test_but_missing_skips_with_reason | red |
| eval-runner → Suites that need GitButler run with a pinned `but` in CI | Required but missing | evals/runner/test_butenv.py | test_but_missing_required_fails | red |

## 1. Feasibility checks and ADR 0018

Every check runs only in a new scratch repo under `$TEMP/specwright-add-gitbutler-backend/`, never in this repo or another existing one. A failed check stops apply and returns the design for a new review round.

- [ ] 1.1 Check whether local `but` reads and writes (`status --json`, `commit -b`, `branch new`, `branch delete`) reach the network. Use a scratch repo with a logging bare remote (fetch attempts) and the fake `gh` plus an unroutable forge host (API calls). Verify: the log and the fake `gh` record no call. Record the result in design.md's Risks; if any call is recorded, stop apply (design.md Risks, first item)
- [ ] 1.2 Check which GitButler value holds the workspace base (`gitbutler/target` or `mergeBase` from `but status --json`). In a scratch repo with a remote, it must stay unchanged after `git fetch origin` moves `origin/<main>`, and move after `but pull`. Verify: a scripted run prints both readings; fix the chosen value in D8. If no value behaves that way, stop apply
- [ ] 1.3 Check how `but commit -b <branch> -F <file> <paths>` commits a deleted directory and a renamed archive directory named by exact path, and that it leaves another change's planning files uncommitted. Verify: the result is recorded in design.md's archive-commit gap and D5 follows it
- [ ] 1.4 Check that `but pull` fetches through system Git and honours `as.sh`'s `GIT_CONFIG_*` credential fence. Verify: the logging remote sees the fenced credential helper. If it does not, `pull` on GitButler always reports `pull_skipped` with reason `unfenced` (design.md Risks), and the pull tests in group 6 assert that instead
- [ ] 1.5 Write `docs/adr/0018-vcs-backends-git-jj-gitbutler.md` (D12): restate 0017 and add GitButler. Mark 0017 superseded, and replace its row in `openspec/architecture.md`'s index and the `vcs.sh` Components row. Verify: `python evals/run.py --changed main` passes the ADR and architecture checks

## 2. Eval harness and CI for `but`

- [ ] 2.1 Write failing `evals/runner/test_butenv.py` (`test_but_missing_skips_with_reason`, `test_but_missing_required_fails`) and the CI tests in `evals/runner/test_ci_workflow.py` (`test_workflow_installs_pinned_but_for_vcs_only`, `test_workflow_pins_but_build_url`, `test_workflow_checks_but_sha256_before_use`). Verify they fail because `butenv.py`, `BUT_VERSION` and the CI step are missing
- [ ] 2.2 Add `evals/vcs/butenv.py` (scratch repo set up by `but`, local bare remote, fake `gh`, isolated GitButler app data with metrics disabled, `GIT_CONFIG_NOSYSTEM=1` and `core.autocrlf=false`, skip or fail per `SPECWRIGHT_REQUIRE_BUT`). Add `BUT_VERSION` (`0.23.1-3317`) and, in `.github/workflows/evals.yml`, an install step only in the `vcs` job: `curl --fail` the versioned Linux `but` URL, `sha256sum --check` it against `57e442543839c912f164fb91a20ea934826fc0023ddf552a70f2ed63ba514a73` before making it executable, put it on `PATH`, fail unless `but --version` names the version part of `BUT_VERSION` (derived in the step), and set `SPECWRIGHT_REQUIRE_BUT=1` in every suite job (D10). Map the new files in `evals/suites.json`, with `pr-pair.sh`, `as.sh`, `review-run.sh`, `release.sh` and `finish.sh` also mapped to `vcs`. Verify: the five tests pass, flip their rows green, and the suite-map test in `evals/runner` passes

## 3. Settings, probe and the Git-backend refusal

- [ ] 3.1 Write failing tests for every red row of "The backend is chosen per repo", "The GitButler backend is probed before any `but` command" and "The Git backend refuses to write in a GitButler workspace". Verify they fail for the right reason, and that the `probe` tests assert no `.git/gitbutler/` is created
- [ ] 3.2 Accept `gitbutler` for the code repo in `pr-pair.sh vcs` and `vcs.sh get_settings`, refuse it for the store (`unsupported_vcs`) and without `finish: pr` (`unsupported_combination`). Add the GitButler `probe` (Git reads first, then `but --version` outside the repo) and the `gitbutler_workspace` stop on the Git backend (D1, D2, D14). Verify the 3.1 tests pass, flip their rows green, and re-run `test_unset_vcs_is_git` and `test_store_vcs_not_inherited` (still green)
- [ ] 3.3 Document `vcs: gitbutler` (code repo, PR only) in `templates/openspec/specwright.yaml` and README, and the GitButler limits: `core.autocrlf=true` (design.md Risks, Line endings). Verify: `python evals/run.py --changed main` passes the template and skill-text tests

## 4. State, branch creation and switch

- [ ] 4.1 Write failing tests for the rows of "The GitButler gate applies the change branch beside the others" and "On GitButler the change branch is resolved by name", except the archive commit row (group 5)
- [ ] 4.2 Implement `state --branch` (resolved by name; tip, target, paths split into own, unassigned and other branches'; 16 MiB cap on `but status`), `branch-create` with `but branch new`, `switch` to main as a no-op and `branch_not_applied` (D3, D4). Verify the 4.1 tests pass and flip their rows green

## 5. Commit with named paths

- [ ] 5.1 Write failing tests for the rows of "On GitButler a commit takes only its named paths into the change branch" and `test_archive_commit_names_exact_paths` (cases: every file renamed unchanged, some files changed while moved, and only the new directory named, which stops with `commit_mismatch`)
- [ ] 5.2 Implement `commit` on GitButler: check that each named path is unassigned or the change's own, normalize the paths (`bad_path` on glob characters), stop with `nothing_to_commit` when no named path changed, run `but commit -b <branch> -F <msgfile> --json <paths...>` with the named paths that cover a listed change (a path covering only a rename's source is left out), never CLI IDs, then verify the parent, the committed file set (read with `--no-renames`, held to every named path), the message and every other branch's tip, otherwise `commit_mismatch` (D5). Verify the 5.1 tests pass and flip their rows green
- [ ] 5.3 Document in README that `but commit` does not run the pre-commit or commit-msg hooks. Verify: the README skill-text test passes

## 6. Push, pull, fetch and delete

- [ ] 6.1 Write failing tests for the rows of "A GitButler push publishes only the change branch", "The GitButler pull never rebases another branch" (in `evals/vcs/`) and "A GitButler branch is deleted only once merged", including `test_but_error_names_autocrlf` (a fake failing `but` is enough)
- [ ] 6.2 Implement `push` (fenced `git push origin refs/heads/<b>:refs/heads/<b>`, no force, no `-u`, `push_rejected`), `pull` (fenced `but pull` only when nothing else is applied and no linked worktree exists, otherwise `pull_skipped`), `fetch-main` (`FETCH_HEAD` only), `delete-branch` (base from task 1.2, `--merged-commit`, `left_applied`; `norm_pr` carries `merge_commit_sha`, and cleanup passes it as `--merged-commit`) and the `merge` stop (D6, D7, D8); a failed `but` write in a repo whose effective `core.autocrlf` is `true` adds the autocrlf hint to `but_error` (design.md Risks, Line endings). Verify the 6.1 tests pass and flip their rows green

## 7. `as.sh` fence for `but pull`

- [ ] 7.1 Write failing tests in `evals/pr-pair/test_as_gitbutler.py` for the three github-identity rows
- [ ] 7.2 Fence `but pull` in `as.sh`, refuse every other `but` subcommand and `-C`/`--current-dir` with exit 3. Verify the 7.1 tests pass, flip their rows green, and re-run `evals/pr-pair/test_as_sh.py` and `test_as_jj.py` (still green)

## 8. Reads use the branch tip

- [ ] 8.1 Write failing tests for the "Change ranges read the change branch tip" rows (red ones), `test_finish_reads_fetched_main` and `test_preship_range_names_branch_tip`
- [ ] 8.2 Add `--branch` to `review-run.sh` (range, record key, after-archive lookup, task evidence), `release.sh check` and `finish.sh`, each resolving the tip on every call and stopping on GitButler without it. Update the reviewer agents (`agents/*/specwright-reviewer.md`) to diff against the branch and read surrounding code with `git show <branch>:<path>`, and update the skills' call sites listed in D4. Verify the 8.1 tests pass, flip their rows green, and re-run `test_record_preship_repo_local_keyed_by_code_head` and the three green preship rows (still green)

## 9. PR-pair routing and the Git-write boundary

- [ ] 9.1 Write failing tests `test_full_pr_flow_git_write_boundary`, `test_cleanup_plan_routes_code_repo_through_vcs` and `test_feedback_pass_ignores_other_and_preexisting_paths`. The flow test records every Git write through a wrapper and allows only the push, the read-only fetch and the release tag
- [ ] 9.2 Route `pr-pair.sh cleanup-plan`, `remote_contains` and `branch-check` through `vcs.sh` for every backend other than Git, and pass the PR's `merge_commit_sha` (carried by `norm_pr`) as `--merged-commit`, make the feedback pass ignore other branches' paths and the unassigned paths present at its start (D13). Verify the 9.1 tests pass and flip their rows green

## 10. Skills, debug, undo and GitButler's skills

- [ ] 10.1 Write failing tests `test_debug_never_stashes_on_gitbutler`, `test_branch_gate_notes_missing_but_skill`, `test_but_skill_install_only_on_yes` and `test_undo_plan_uses_but_commit`
- [ ] 10.2 Update `specwright-branch` (workspace gate, `but skill check` note), `-commit`, `-finish` (PR-only stop, exact archive paths, cleanup), `-pr`, `-roadmap` (pull skip, `--branch` for roadmap branches), `-review`, `-release`, `-debug` (no stash on GitButler), `finish.sh`'s undo plan (`but commit -b`, `git cat-file --filters`), and the README and install prompt offer of `but skill install --path` (D9, D11). Verify the 10.1 tests pass and flip their rows green

## 11. Integration and release

- [ ] 11.1 Check that every Test map row is green, `openspec validate add-gitbutler-backend --strict` passes, and `python evals/run.py --changed main` passes. Every suite then runs in PR CI with `but` installed
- [ ] 11.2 Run `release.sh bump --to 0.12.0` and rewrite the summary of the proposal's `## Release Notes` to describe the whole release. Verify with `release.sh check` and `release.sh notes --proposal openspec/changes/add-gitbutler-backend/proposal.md`

## Workflow follow-up

- Archive with `/opsx:archive`, then `specwright-finish` pushes the archive commit to the PR (finish: pr).
- After the merge, publish v0.12.0 with `specwright-release`.
- Dogfood the backend on a GitButler project before closing M5 (a user-verified criterion; it does not block the close).
