# Tasks

## Test map

Red means added/changed coverage to prove before implementation; inherited green rows are rerun in their owning group.

| Requirement | Scenario | Test file | Test name | State |
|---|---|---|---|---|
| github-identity → GitHub connection settings keep the fenced public default | Existing settings | `evals/pr-pair/test_as_sh.py` | `test_configured_login_pins_its_token_not_the_active_one` | green |
| github-identity → GitHub connection settings keep the fenced public default | Invalid host or fence value | `evals/pr-pair/test_as_sh.py` | `test_invalid_connection_values_stop_before_gh` | green |
| github-identity → Ambient authentication is an explicit opt-out | SSH transport and an environment token only | `evals/pr-pair/test_pr_pair.py` | `test_ship_and_watch_with_ssh_and_token_only` | green |
| github-identity → Ambient authentication is an explicit opt-out | Token-only HTTPS automation | `evals/pr-pair/test_pr_pair.py` | `test_ship_on_https_with_caller_token_and_no_stored_login` | green |
| github-identity → Ambient authentication is an explicit opt-out | A named identity conflicts with ambient authentication | `evals/pr-pair/test_pr_pair.py` | `test_ambient_workflow_rejects_each_named_identity` | green |
| github-identity → Ambient authentication is an explicit opt-out | SSH remains disabled by the default fence | `evals/vcs/test_sw_fence.py` | `test_github_ssh_still_refused_by_default_fenced_push` | green |
| github-identity → Fenced calls target the configured GitHub host | Enterprise host in the environment with default settings | `evals/pr-pair/test_as_sh.py` | `test_gh_host_and_enterprise_tokens_unset` | green |
| github-identity → Fenced calls target the configured GitHub host | Host variables set but empty | `evals/pr-pair/test_as_sh.py` | `test_empty_gh_host_targets_github` | green |
| github-identity → Fenced calls target the configured GitHub host | Fenced Enterprise ship and watch | `evals/pr-pair/test_pr_pair.py` | `test_enterprise_ship_and_watch_keep_host_and_identity` | green |
| github-identity → Fenced calls target the configured GitHub host | Another host requests the credential | `evals/pr-pair/test_as_sh.py` | `test_enterprise_helper_refuses_other_hosts_and_protocols` | green |
| github-identity → Push authentication follows the actual destinations | A non-GitHub fetch URL has a GitHub push URL | `evals/vcs/test_sw_fence.py` | `test_push_fences_effective_github_target_with_off_host_fetch` | green |
| github-identity → Push authentication follows the actual destinations | GitHub fetch and non-GitHub push | `evals/vcs/test_sw_fence.py` | `test_push_uses_ambient_credentials_for_off_host_push_urls` | green |
| github-identity → Push authentication follows the actual destinations | Push destinations need incompatible authentication | `evals/vcs/test_sw_fence.py` | `test_mixed_effective_push_hosts_launch_nothing` | green |
| github-identity → Push authentication follows the actual destinations | Indexed URL rewrites survive fenced publication | `evals/pr-pair/test_pr_pair.py` | `test_fenced_ship_keeps_indexed_rewrites_and_gh_target` | green |
| github-identity → Push authentication follows the actual destinations | Launched Git would differ from the PR plan | `evals/pr-pair/test_pr_pair.py`, `evals/vcs/test_sw_fence.py` | `test_fenced_ship_refuses_effective_target_change`, `test_standalone_push_refuses_changed_effective_destination`, `test_standalone_fenced_push_refuses_indexed_routing_drift` | green |
| github-identity → Every GitHub call of a run is fenced to the run login | Configured login | `evals/pr-pair/test_as_sh.py` | `test_configured_login_pins_its_token_not_the_active_one` | green |
| github-identity → Every GitHub call of a run is fenced to the run login | Token resolves to someone else | `evals/pr-pair/test_as_sh.py` | `test_token_for_other_login_exits_3_command_not_run` | green |
| github-identity → An empty login is resolved once per run | Switch mid-run | `evals/pr-pair/test_as_sh.py` | `test_resolved_login_survives_auth_switch` | green |
| github-identity → An empty login is resolved once per run | Switch during watch | `evals/pr-pair/test_pr_pair.py`, `evals/pr-pair/test_skill_text.py` | `test_fenced_initial_lookup_is_deferred_then_bound`, `test_run_login_handed_to_watch_feedback_archive` | green |
| github-identity → An empty login is resolved once per run | Handed-off step without its run login | `evals/pr-pair/test_pr_pair.py` | `test_expected_missing_handoff_does_not_resolve_accounts`, `test_store_only_feedback_cannot_rebind_a_missing_handoff` | green |
| github-identity → An empty login is resolved once per run | Deferred first login is handed to ship | `evals/pr-pair/test_pr_pair.py` | `test_fenced_initial_lookup_is_deferred_then_bound` | green |
| github-identity → An empty login is resolved once per run | No active account in a step that needs GitHub | `evals/pr-pair/test_pr_pair.py` | `test_expected_discovers_only_after_account_resolution` | green |
| github-identity → An empty login is resolved once per run | No gh account in a step that accepts local refs | `evals/vcs/test_sw_fence.py` | `test_no_account_leaves_local_main_available` | green |
| github-identity → An empty login is resolved once per run | Ambient token variables do not choose the login | `evals/pr-pair/test_as_sh.py` | `test_resolve_ignores_gh_token_env` | green |
| github-identity → Login fallbacks end at the run login | Review requests with every login empty | `evals/pr-pair/test_skill_text.py` | `test_review_request_poster_falls_back_to_run_login_fenced` | green |
| github-identity → Login fallbacks end at the run login | Store login empty | `evals/pr-pair/test_pr_pair.py` | `test_fenced_initial_lookup_is_deferred_then_bound` | green |
| github-identity → Login fallbacks end at the run login | Feedback uses the explicitly configured store account instead of a different handed-off code login | `evals/pr-pair/test_pr_pair.py` | `test_feedback_uses_explicit_store_login_over_handed_code_login` | green |
| github-identity → Login fallbacks end at the run login | Fallback login has no credential | `evals/pr-pair/test_as_sh.py` | `test_request_as_without_credential_exits_3` | green |
| github-identity → Login fallbacks end at the run login | Store reads with both logins empty | `evals/vcs/test_sw_fence.py` | `test_fenced_store_fetch_refuses_userinfo_with_empty_logins` | green |
| github-identity → Main refreshes and pulls from GitHub are fenced | Cleanup pull after merge | `evals/pr-pair/test_pr_pair.py` | `test_cleanup_plan_pull_runs_through_as_sh` | green |
| github-identity → Main refreshes and pulls from GitHub are fenced | Branch gate fetch over SSH | `evals/vcs/test_sw_fence.py` | `test_fenced_ssh_main_refresh_cannot_use_ambient_key` | green |
| github-identity → Main refreshes and pulls from GitHub are fenced | Origin that pushes to a fork | `evals/vcs/test_sw_fence.py` | `test_main_fetch_auth_uses_fetch_url_not_fork_push_url` | green |
| github-identity → Main refreshes and pulls from GitHub are fenced | Post-merge pull refused | `evals/vcs/test_sw_fence.py` | `test_refused_pull_leaves_branch_and_refs_unchanged` | green |
| github-identity → Main refreshes and pulls from GitHub are fenced | The legacy upstream is on the configured GitHub host | `evals/vcs/test_sw_fence.py` | `test_legacy_pull_fences_effective_upstream` | green |
| github-identity → Main refreshes and pulls from GitHub are fenced | The legacy upstream is not on the configured GitHub host | `evals/vcs/test_sw_fence.py` | `test_legacy_pull_does_not_fence_off_host_upstream` | green |
| github-identity → The post-merge PR check is fenced | Merged PR check with a login set | `evals/pr-pair/test_pr_pair.py` | `test_closed_check_reads_each_repo_through_its_login` | green |
| github-identity → The post-merge PR check is fenced | Check cannot authenticate | `evals/pr-pair/test_pr_pair.py` | `test_closed_check_lookup_failure_is_unknown` | green |
| github-identity → Credentials in a URL are refused | Credential-free HTTPS URL | `evals/pr-pair/test_as_sh.py` | `test_enterprise_helper_returns_verified_enterprise_token` | green |
| github-identity → Credentials in a URL are refused | Token in the fetch URL | `evals/pr-pair/test_as_sh.py` | `test_token_in_fetch_url_refused_no_request` | green |
| github-identity → Credentials in a URL are refused | Token in one of several push URLs | `evals/pr-pair/test_as_sh.py` | `test_token_in_second_push_url_refused` | green |
| github-identity → Credentials in a URL are refused | Credential added by a URL rewrite | `evals/pr-pair/test_as_sh.py` | `test_enterprise_userinfo_rewrite_refused_without_request` | green |
| github-identity → Credentials in a URL are refused | Token in the username slot | `evals/pr-pair/test_as_sh.py` | `test_token_in_username_slot_refused_masked` | green |
| github-identity → Credentials in a URL are refused | Git pointed at another repository | `evals/pr-pair/test_as_sh.py` | `test_git_selecting_another_repo_refused` | green |
| github-identity → Credentials in a URL are refused | Username without a secret | `evals/pr-pair/test_as_sh.py` | `test_bare_username_refused` | green |
| github-identity → Credentials in a URL are refused | Credential rule for another host | `evals/pr-pair/test_as_sh.py` | `test_gitlab_token_rule_ignored` | green |
| github-identity → Non-GitHub remotes stay outside the fence | Local mode with a self-hosted remote | `evals/vcs/test_sw_fence.py` | `test_off_host_fetch_preserves_original_enterprise_environment` | green |
| github-identity → Non-GitHub remotes stay outside the fence | PR mode with a non-GitHub origin | `evals/pr-pair/test_pr_pair.py` | `test_expected_refuses_off_host_code_remote_before_push` | green |
| github-identity → The trailing-dot host is github.com | Token in a trailing-dot URL | `evals/pr-pair/test_as_sh.py` | `test_trailing_dot_token_in_fetch_url_refused` | green |
| github-identity → The trailing-dot host is github.com | Trailing-dot URL argument or rewrite | `evals/pr-pair/test_as_sh.py` | `test_enterprise_trailing_dot_userinfo_refused` | green |
| github-identity → The trailing-dot host is github.com | Credential-free trailing-dot URL | `evals/pr-pair/test_as_sh.py` | `test_enterprise_trailing_dot_helper_uses_canonical_host` | green |
| github-identity → The trailing-dot host is github.com | Look-alike host | `evals/pr-pair/test_as_sh.py` | `test_lookalike_host_not_github` | green |
| github-identity → The trailing-dot host is github.com | Trailing-dot store remote | `evals/pr-pair/test_pr_pair.py` | `test_trailing_dot_store_remote_is_fenced` | green |
| github-identity → Unfenced git keeps the caller's enterprise host settings | Enterprise store read by rounds | `evals/pr-pair/test_pr_pair.py` | `test_rounds_off_host_store_hands_off_without_reading_history` | green |
| github-identity → Unfenced git keeps the caller's enterprise host settings | Explicit fetch for another host | `evals/vcs/test_sw_fence.py` | `test_off_host_fetch_preserves_original_enterprise_environment` | green |
| github-identity → Unfenced git keeps the caller's enterprise host settings | Variables were unset | `evals/vcs/test_sw_fence.py` | `test_off_host_fetch_keeps_absent_enterprise_environment` | green |
| github-identity → Unfenced git keeps the caller's enterprise host settings | Fenced calls stay on github.com | `evals/pr-pair/test_as_sh.py` | `test_gh_host_and_enterprise_tokens_unset` | green |
| github-identity → jj network commands are fenced like git | Push on jj | `evals/pr-pair/test_as_jj.py` | `test_jj_push_uses_fenced_token` | green |
| github-identity → jj network commands are fenced like git | Repository option | `evals/pr-pair/test_as_jj.py` | `test_jj_repository_option_refused` | green |
| github-identity → jj network commands are fenced like git | Config override | `evals/pr-pair/test_as_jj.py` | `test_jj_config_option_refused` | green |
| github-identity → jj network commands are fenced like git | Other jj subcommand | `evals/pr-pair/test_as_jj.py` | `test_jj_other_subcommand_refused` | green |
| github-identity → GitButler pulls are fenced like git | Cleanup pull | `evals/pr-pair/test_as_gitbutler.py` | `test_but_pull_uses_fenced_token` | green |
| github-identity → GitButler pulls are fenced like git | Other `but` subcommand | `evals/pr-pair/test_as_gitbutler.py` | `test_but_other_subcommand_refused` | green |
| github-identity → GitButler pulls are fenced like git | Directory option | `evals/pr-pair/test_as_gitbutler.py` | `test_but_directory_option_refused` | green |
| github-identity → The fence runs in the project's sw | Fenced gh call with a matching sw | `evals/pr-pair/test_as_sh.py` | `test_configured_login_pins_its_token_not_the_active_one` | green |
| github-identity → The fence runs in the project's sw | Resolve through sw | `evals/pr-pair/test_as_sh.py` | `test_resolve_prints_the_active_login_only` | green |
| github-identity → The fence runs in the project's sw | A refusal keeps its exit status | `evals/pr-pair/test_as_sh.py` | `test_token_in_second_push_url_refused` | green |
| github-identity → The fence runs in the project's sw | Fenced store call selects the code project | `evals/cli/test_sw_project_version.py` | `test_store_fence_uses_code_project_host` | green |
| github-identity → The fence runs in the project's sw | Selected project does not change target validation | `evals/cli/test_sw_project_version.py` | `test_store_fence_checks_store_remote_from_store_cwd` | green |
| github-identity → The fence runs in the project's sw | Resolve in a project of another version | `evals/cli/test_sw_project_version.py` | `test_resolve_refuses_project_with_another_version` | green |
| github-identity → The fence runs in the project's sw | Missing selected binary refuses without fallback | `evals/cli/test_sw_project_version.py` | `test_fence_has_no_fallback_when_selected_binary_is_missing` | green |
| github-identity → The fence runs in the project's sw | Malformed fence project prefix is refused | `evals/cli/test_sw_project_version.py` | `test_fence_refuses_malformed_project_prefix` | green |
| github-identity → sw as keeps as.sh's contract | Unchanged black-box evals pass on sw | `evals/pr-pair/test_as_sh.py` | `test_configured_login_pins_its_token_not_the_active_one` | green |
| github-identity → sw as keeps as.sh's contract | Exit codes | `cli/test/fence/fence_test.dart` | `no arguments is the usage line, exit 1 / a login with no command is exit 2` | green |
| github-identity → sw as keeps as.sh's contract | A hung token lookup | `evals/pr-pair/test_as_sh.py` | `test_resolve_token_lookup_hung_exits_3_named` | green |
| github-identity → sw as keeps as.sh's contract | A nested fence keeps the outer originals | `evals/pr-pair/test_as_sh.py` | `test_nested_fence_restores_original_off_host_git_environment` | green |
| native-cli → The project is chosen by --project, then the command's own argument | A store-started call | `evals/cli/test_sw_project_version.py`, `evals/pr-pair/test_pr_pair.py` | `test_store_started_call_with_project`, `test_expected_uses_selected_project_connection_without_switching_targets` | green |
| native-cli → The project is chosen by --project, then the command's own argument | Store-started call without --project | `evals/cli/test_sw_project_version.py` | `test_store_started_call_without_project_is_sw_mismatch` | green |
| native-cli → The project is chosen by --project, then the command's own argument | Two leading --project options | `evals/cli/test_sw_project_version.py` | `test_two_leading_project_options_is_usage` | green |
| native-cli → The project is chosen by --project, then the command's own argument | A relative --code in the undo planner | `evals/finish/test_finish_shim.py` | `test_relative_code_is_anchored_at_the_planning_root` | green |
| native-cli → The project root is found from the physical path | A project path through a link and `..` | `evals/cli/test_sw_project_version.py` | `test_project_through_link_and_dotdot_is_physical` | green |
| native-cli → The project root is found from the physical path | Stale settings in a shared store do not choose its GitHub host | `evals/cli/test_sw_project_version.py` | `test_store_fence_uses_code_project_host` | green |
| planning-stores → A store without a PR is a manual handoff | Feedback rounds with an off-host store | `evals/pr-pair/test_pr_pair.py` | `test_rounds_off_host_store_hands_off_without_reading_history` | green |
| planning-stores → A store without a PR is a manual handoff | PR finish with a local-only store | `evals/git-workflow/evals.json` | `eval-store-archive-before-merge-local-store` | green |
| planning-stores → A store without a PR is a manual handoff | Archive edits already exist at PR finish | `evals/git-workflow/evals.json` | `eval-store-archive-before-merge-preedited` | green |
| planning-stores → A store without a PR is a manual handoff | `finish: local` keeps its existing behavior | `evals/git-workflow/evals.json` | `eval-store-finish-local` | green |
| planning-stores → A change name is used once | Name of an archived change | `evals/git-workflow/evals.json` | `eval-store-branch-reused-name` | green |
| planning-stores → A change name is used once | Archived from another checkout | `evals/git-workflow/evals.json` | `eval-store-branch-reused-name-selected` | green |
| planning-stores → The expected PR set follows the change's work and transport | Planning-only change with a GitHub store | `evals/pr-pair/test_pr_pair.py` | `test_expected_planning_only_github_store` | green |
| planning-stores → The expected PR set follows the change's work and transport | Planning-only change with no GitHub store | `evals/pr-pair/test_pr_pair.py` | `test_expected_planning_only_local_store` | green |
| planning-stores → The expected PR set follows the change's work and transport | Local-only store with code to ship | `evals/pr-pair/test_pr_pair.py` | `test_fenced_ship_keeps_indexed_rewrites_and_gh_target` | green |
| planning-stores → The expected PR set follows the change's work and transport | Code PR required but the code remote is missing | `evals/pr-pair/test_pr_pair.py` | `test_expected_refuses_required_code_target_before_publication` | green |
| planning-stores → The expected PR set follows the change's work and transport | Store publication still requires code identity | `evals/pr-pair/test_pr_pair.py` | `test_expected_refuses_off_host_code_remote_before_push` | green |
| planning-stores → The expected PR set follows the change's work and transport | Code fix turns a planning-only change into a pair | `evals/pr-pair/test_pr_pair.py` | `test_expected_gains_code_pr_after_code_commit` | green |
| planning-stores → The expected PR set follows the change's work and transport | Fresh watch after the code PR merged | `evals/pr-pair/test_pr_pair.py` | `test_pair_state_merged_code_pr_stays_expected` | green |
| planning-stores → The expected PR set follows the change's work and transport | An unreadable code range is not an empty range | `evals/pr-pair/test_pr_pair.py` | `test_expected_refuses_failed_code_commit_count` | green |
| planning-stores → The expected PR set follows the change's work and transport | A merged code PR remains expected without a local change branch | `evals/pr-pair/test_pr_pair.py` | `test_cleanup_plan_rerun_code_branch_gone` | green |
| planning-stores → The expected PR set follows the change's work and transport | A failed remote lookup does not make the store local | `evals/pr-pair/test_pr_pair.py` | `test_expected_distinguishes_refused_url_reads_from_absence` | green |
| planning-stores → The expected PR set follows the change's work and transport | Fetch and push disagree about the GitHub host | `evals/pr-pair/test_pr_pair.py` | `test_expected_mixed_store_hosts_are_never_local` | green |
| planning-stores → The expected PR set follows the change's work and transport | Code and store select the same repository | `evals/pr-pair/test_pr_pair.py` | `test_expected_same_canonical_repo_stops_before_discovery` | green |
| planning-stores → The expected PR set follows the change's work and transport | No GitHub operation is needed | `evals/pr-pair/test_pr_pair.py` | `test_expected_fully_local_needs_no_identity` | green |
| planning-stores → PR finish pairs the store PR with the code PR | Ship opens both PRs | `evals/pr-pair/test_pr_pair.py` | `test_ship_sequence_links_both` | green |
| planning-stores → PR finish pairs the store PR with the code PR | Code PR already open without the link | `evals/pr-pair/test_pr_pair.py` | `test_link_existing_code_pr_by_comment` | green |
| planning-stores → PR finish pairs the store PR with the code PR | Ship re-run after an interrupted first run | `evals/pr-pair/test_pr_pair.py` | `test_ship_sequence_rerun_is_idempotent` | green |
| planning-stores → PR finish pairs the store PR with the code PR | Code PR replaced after closing unmerged | `evals/pr-pair/test_pr_pair.py` | `test_link_updates_own_comment_for_new_peer` | green |
| planning-stores → PR finish pairs the store PR with the code PR | Existing code PR targets another branch | `evals/pr-pair/test_pr_pair.py` | `test_ensure_pr_stops_on_wrong_base` | green |
| planning-stores → PR finish pairs the store PR with the code PR | Fetch and push URLs name different repositories | `evals/pr-pair/test_pr_pair.py` | `test_expected_mismatched_store_stops_the_set` | green |
| planning-stores → PR finish pairs the store PR with the code PR | Matching PR beyond the first page | `evals/pr-pair/test_pr_pair.py` | `test_discover_paginates_past_fork_prs` | green |
| planning-stores → PR finish pairs the store PR with the code PR | Inherited GH_REPO names the code repo | `evals/pr-pair/test_pr_pair.py` | `test_gh_repo_env_ignored` | green |
| planning-stores → PR finish pairs the store PR with the code PR | Store push rejected | `evals/pr-pair/test_skill_text.py` | `test_ship_pushes_every_repo_before_any_pr` | green (skill contract) |
| planning-stores → Watch covers the expected PR set | Code PR green, store PR waiting | `evals/pr-pair/test_pr_pair.py` | `test_pair_state_ready_only_when_both_pass` | green |
| planning-stores → Watch covers the expected PR set | Store PR alone is ready | `evals/pr-pair/test_pr_pair.py` | `test_pair_state_single_store_pr_ready` | green |
| planning-stores → Watch covers the expected PR set | One PR of the pair merged | `evals/pr-pair/test_pr_pair.py` | `test_pair_state_split_hands_off` | green |
| planning-stores → Watch covers the expected PR set | Archive before merge with no store PR | `evals/pr-pair/test_pr_pair.py` | `test_pair_state_local_store_never_ready_with_green_code` | green |
| planning-stores → Watch covers the expected PR set | A publishable store PR has not been opened | `evals/pr-pair/test_pr_pair.py` | `test_pair_state_missing_pr_needs_ship` | green |
| planning-stores → Watch covers the expected PR set | Store snapshot of an old head | `evals/pr-pair/test_pr_pair.py` | `test_pair_state_refreshes_an_old_head_snapshot` | green |
| planning-stores → Watch covers the expected PR set | Snapshot of another PR | `evals/pr-pair/test_pr_pair.py` | `test_pair_state_refreshes_a_snapshot_of_another_pr` | green |
| planning-stores → Watch covers the expected PR set | Snapshot without a head | `evals/pr-pair/test_pr_pair.py` | `test_pair_state_refreshes_a_snapshot_without_a_head` | green |
| planning-stores → Feedback rounds span the PR pair | Spec fix requested on the code PR | `evals/pr-pair/test_pr_pair.py` | `test_pass_plan_routes_spec_fix_to_store` | green |
| planning-stores → Feedback rounds span the PR pair | Round limit across both repos | `evals/pr-pair/test_pr_pair.py` | `test_rounds_highest_across_branches` | green |
| planning-stores → Feedback rounds span the PR pair | Finishing an interrupted final pass | `evals/pr-pair/test_pr_pair.py` | `test_pass_plan_final_pass_push_pending` | green |
| planning-stores → Feedback rounds span the PR pair | Recovered partial fix | `evals/pr-pair/test_pr_pair.py` | `test_pass_plan_trailer_commit_with_part_of_the_edits_is_not_done` | green |
| planning-stores → Feedback rounds span the PR pair | Legacy branch without trailers | `evals/pr-pair/test_pr_pair.py` | `test_rounds_legacy_subject_count_without_trailers` | green |
| planning-stores → Fix rounds are counted across both branches | Round below the limit | `evals/pr-pair/test_pr_pair.py` | `test_rounds_store_only_round_makes_the_next_pass_round_two` | green |
| planning-stores → Fix rounds are counted across both branches | Trailer and legacy commits mixed | `evals/pr-pair/test_pr_pair.py` | `test_rounds_ignores_code_subjects_when_store_has_a_trailer` | green |
| planning-stores → Ship pushes every expected repo before it opens a PR | Both pushes succeed | `evals/pr-pair/test_skill_text.py` | `test_ship_pushes_every_repo_before_any_pr` | green (skill contract) |
| planning-stores → Ship pushes every expected repo before it opens a PR | Code push rejected after the store push | `evals/pr-pair/test_skill_text.py` | `test_ship_pushes_every_repo_before_any_pr` | green (skill contract) |
| planning-stores → Ship pushes every expected repo before it opens a PR | Code push rejected with an existing store PR | `evals/pr-pair/test_skill_text.py` | `test_ship_pushes_every_repo_before_any_pr` | green (skill contract) |
| planning-stores → Ship pushes every expected repo before it opens a PR | Store push rejected | `evals/pr-pair/test_skill_text.py` | `test_ship_pushes_every_repo_before_any_pr` | green (skill contract) |
| planning-stores → Cleanup after merge covers every expected PR | Both PRs merged | `evals/pr-pair/test_pr_pair.py` | `test_cleanup_plan_both_merged` | green |
| planning-stores → Cleanup after merge covers every expected PR | Only one PR merged | `evals/pr-pair/test_pr_pair.py` | `test_cleanup_plan_split` | green |
| planning-stores → Cleanup after merge covers every expected PR | Cleanup re-run after the store PR merges | `evals/pr-pair/test_pr_pair.py` | `test_cleanup_plan_rerun_code_branch_gone` | green |
| planning-stores → Cleanup after merge covers every expected PR | Code PR merged beside a local-only store | `evals/pr-pair/test_pr_pair.py` | `test_cleanup_plan_keeps_a_store_branch_shared_by_hand` | green |
| pr-script-runtime → PR evidence is scoped to its GitHub host | Identical PR coordinates on two hosts | `evals/pr-pair/test_snapshot_native.py`, `evals/pr-pair/test_pr_pair.py` | `test_watch_claims_and_head_records_are_isolated_by_host`, `test_feedback_record_is_isolated_by_host` | green |
| pr-script-runtime → PR evidence is scoped to its GitHub host | Snapshot from the wrong host | `evals/pr-pair/test_pr_pair.py` | `test_pair_state_requires_snapshot_host_to_match_discovery` | green |
| pr-script-runtime → PR evidence is scoped to its GitHub host | Wrong PR evidence does not authorize merge or feedback | `evals/pr-pair/test_pr_pair.py` | `test_policy_refuses_same_head_from_other_host_or_pr`, `test_feedback_refuses_same_head_from_other_host_or_pr` | green |
| pr-script-runtime → Reply mutations verify the addressed PR item | A thread and its root belong to the target PR | `evals/pr-pair/test_pr_reply.py` | `test_reply_only_mutates_verified_thread_and_its_actual_root` | green |
| pr-script-runtime → Reply mutations verify the addressed PR item | An ID belongs to a different PR | `evals/pr-pair/test_pr_reply.py` | `test_reply_rejects_node_from_other_pr_including_standalone_actions` | green |
| pr-script-runtime → PR snapshots and replies run in the project's sw | Snapshot with a matching sw | `evals/pr-pair/test_snapshot_native.py` | `test_snapshot_without_python` | green |
| pr-script-runtime → PR snapshots and replies run in the project's sw | Reply with a matching sw | `evals/pr-pair/test_pr_reply.py` | `test_reply_with_matching_rev_posts_and_resolves` | green |
| pr-script-runtime → PR snapshots and replies run in the project's sw | A refusal keeps its exit status | `evals/pr-pair/test_pr_reply.py` | `test_reply_refuses_missing_body_file` | green |
| pr-script-runtime → PR snapshots and replies run in the project's sw | Store-started snapshot selects the code project | `evals/pr-pair/test_snapshot_native.py` | `test_store_snapshot_selects_code_project` | green |
| pr-script-runtime → PR snapshots and replies run in the project's sw | Store-started reply selects the code project | `evals/pr-pair/test_snapshot_native.py` | `test_store_reply_selects_code_project` | green |
| pr-script-runtime → PR snapshots and replies run in the project's sw | Missing selected binary refuses without fallback | `evals/pr-pair/test_snapshot_native.py` | `test_missing_selected_binary_has_no_fallback` | green |
| pr-script-runtime → PR snapshots and replies run in the project's sw | Malformed project prefix | `evals/pr-pair/test_snapshot_native.py` | `test_malformed_project_prefix_is_usage` | green |
| pr-script-runtime → PR snapshots and replies run in the project's sw | The same PR number exists on another remote | `evals/pr-pair/test_snapshot_native.py` | `test_snapshot_infers_selected_remote_not_gh_default` | green |
| pr-script-runtime → PR snapshots and replies run in the project's sw | Multiple PR selectors cannot override one another | `evals/pr-pair/test_snapshot_native.py` | `test_multiple_pr_selectors_are_refused_before_github` | green |
| pr-script-runtime → PR snapshots and replies run in the project's sw | Store snapshot infers its planning remote | `evals/pr-pair/test_snapshot_native.py` | `test_store_snapshot_infers_selected_planning_remote` | green |
| pr-script-runtime → PR snapshots and replies run in the project's sw | Selected remote is unusable and no repo is given | `evals/pr-pair/test_snapshot_native.py` | `test_repo_omitted_stops_before_gh_when_selected_remote_is_unusable` | green |
| releases → The release commit is found on main | Squash-merged change | `evals/release/test_release.py` | `test_squash` | green |
| releases → The release commit is found on main | Merge-commit change | `evals/release/test_release.py` | `test_merge_commit` | green |
| releases → The release commit is found on main | Version not on main | `evals/release/test_release.py` | `test_not_on_main`, `test_off_host_publish_refuses_history_not_on_local_main` | green |
| releases → The release commit is found on main | Publication destination changes after main was fetched | `evals/release/test_release.py` | `test_release_proof_rejected_after_remote_changes` | green |
| releases → The release commit is found on main | Fetched main has a custom refspec | `evals/release/test_release.py` | `test_release_proof_ignores_stale_standard_tracking_ref` | green |
| releases → The release commit is found on main | The selected GitHub remote alone tracks `master` | `evals/release/test_release.py` | `test_release_main_can_be_detected_from_selected_remote_tracking_branch` | green |
| releases → The release commit is found on main | Another fetch finishes before the release proof is read | `evals/release/test_release.py` | `test_release_proof_keeps_its_own_commit_across_other_fetch` | green |
| releases → Notes list the changes merged since the previous release | One change in the range | `evals/release/test_release.py` | `test_one_change` | green |
| releases → Notes list the changes merged since the previous release | Several changes in the range | `evals/release/test_release.py` | `test_several_changes_in_order` | green |
| releases → Notes list the changes merged since the previous release | No change in the range | `evals/release/test_release.py` | `test_empty_range` | green |
| releases → Notes list the changes merged since the previous release | Backfill in a clone without the tags | `evals/release/test_release.py` | `test_backfill_boundary_counts_origin_only_tags` | green |
| releases → Notes list the changes merged since the previous release | Backfill with no earlier tag | `evals/release/test_release.py` | `test_backfill_no_tag` | green |
| releases → Notes list the changes merged since the previous release | No change in the range has a section | `evals/release/test_release.py` | `test_no_sections_gives_todays_notes_byte_for_byte` | green |
| releases → Store-backed notes use the code-merge proof | Code PR merged in the range | `evals/release/test_release.py` | `test_merged_pr_in_range` | green |
| releases → Store-backed notes use the code-merge proof | PR from another prefix | `evals/release/test_release.py` | `test_other_prefix_is_not_proof` | green |
| releases → Store-backed notes use the code-merge proof | Code still pending | `evals/release/test_release.py` | `test_pending_left_out` | green |
| releases → Store-backed notes use the code-merge proof | PR discovery fails | `evals/release/test_release.py` | `test_discovery_failure_stops` | green |
| releases → Store-backed notes use the code-merge proof | Store and code use separate named remotes | `evals/release/test_release.py` | `test_release_notes_resolve_independent_named_remotes` | green |
| releases → Store-backed notes use the code-merge proof | Local-store archive has not reached store main | `evals/release/test_release.py` | `test_release_notes_exclude_archive_only_on_manual_share_branch` | green |
| releases → Publish creates and pushes an annotated tag | New release | `evals/release/test_release.py` | `test_publish_release_targets_enterprise_host` | green |
| releases → Publish creates and pushes an annotated tag | GitHub URL rewrites to an off-host repository for both fetch and push | `evals/release/test_release.py` | `test_github_release_refuses_off_host_fetch_and_push_rewrite` | green |
| releases → Publish creates and pushes an annotated tag | Tag template without the version | `evals/release/test_release.py` | `test_tag_template_without_version_refused` | green |
| releases → Publish creates and pushes an annotated tag | Push refused by the fence | `evals/release/test_release.py` | `test_push_failure` | green |
| releases → Publish creates and pushes an annotated tag | Store-backed project | `evals/release/test_release.py` | `test_store_not_tagged` | green |
| releases → Older untagged versions are published first | Older version untagged | `evals/release/test_release.py` | `test_older_blocks_newer` | green |
| releases → Older untagged versions are published first | Tag push failed earlier | `evals/release/test_release.py` | `test_local_only_tag_is_not_published` | green |
| releases → Older untagged versions are published first | First release's tag push failed | `evals/release/test_release.py` | `test_first_release_push_failed` | green |
| releases → Older untagged versions are published first | Backfill below the latest tag | `evals/release/test_release.py` | `test_backfill_below_latest` | green |
| releases → Re-runs never move a published tag | Re-run after an interrupted publish | `evals/release/test_release.py` | `test_rerun_creates_only_release` | green |
| releases → Re-runs never move a published tag | Tag exists only on the selected remote | `evals/release/test_release.py` | `test_publish_release_targets_enterprise_host` | green |
| releases → Re-runs never move a published tag | Tag on another commit | `evals/release/test_release.py` | `test_conflicting_tag_stops` | green |
| releases → Re-runs never move a published tag | Lightweight tag | `evals/release/test_release.py` | `test_lightweight_tag_stops` | green |
| releases → Re-runs never move a published tag | Remote tags unreadable | `evals/release/test_release.py` | `test_ls_remote_failure` | green |
| releases → The tag is pushed where it was checked | Push URL elsewhere | `evals/release/test_release.py` | `test_publish_refuses_named_remote_push_to_fork` | green |
| releases → The tag is pushed where it was checked | Rewrite to another GitHub repository | `evals/release/test_release.py` | `test_publish_refuses_rewrite_to_other_enterprise_repo` | green |
| releases → A release uses the tag on origin | Lost push race | `evals/release/test_release.py` | `test_lost_push_race_stops` | green |
| releases → The GitHub release is optional and created once | Shorthand rewritten to GitHub | `evals/release/test_release.py` | `test_shorthand_rewritten_to_github_creates_release` | green |
| releases → The GitHub release is optional and created once | Release created | `evals/release/test_release.py` | `test_created_with_tag_message` | green |
| releases → The GitHub release is optional and created once | Release created on GitHub Enterprise | `evals/release/test_release.py` | `test_publish_release_targets_enterprise_host` | green |
| releases → The GitHub release is optional and created once | Release already exists | `evals/release/test_release.py` | `test_rerun_after_tag_reports_no_warnings` | green |
| releases → The GitHub release is optional and created once | Release creation fails | `evals/release/test_release.py` | `test_create_failure_resumable` | green |
| releases → Untagged versions can be read from local tags only | Local tags only | `evals/release/test_release.py` | `test_local_flag_reads_no_remote` | green |
| releases → Untagged versions can be read from local tags only | Local read with a local-only tag | `evals/release/test_release.py` | `test_local_flag_counts_local_tag_and_says_so` | green |
| releases → Ship, local merge and watch check the version against main | Ship of a duplicate version | `evals/release/test_release.py` | `test_duplicate_bump_refused` | green |
| releases → Ship, local merge and watch check the version against main | Main merged a duplicate while the PR waited | `evals/release/test_release.py` | `test_duplicate_after_main_merged_in_refused` | green |
| releases → Ship, local merge and watch check the version against main | Local merge of a duplicate version | `evals/release/test_release.py` | `test_duplicate_after_main_merged_in_refused` | green |
| releases → Ship, local merge and watch check the version against main | Releases disabled | `evals/release/test_release.py` | `test_disabled_refuses` | green |
| releases → A cut-off tag push or release creation is decided by a read-back | Push cut off after it landed | `evals/release/test_release.py` | `test_push_cut_off_after_landing_counts_done` | green |
| releases → A cut-off tag push or release creation is decided by a read-back | Push cut off while another clone's tag won | `evals/release/test_release.py` | `test_push_cut_off_other_tag_object_is_tag_mismatch` | green |
| releases → A cut-off tag push or release creation is decided by a read-back | Push cut off with remote's tag on another commit | `evals/release/test_release.py` | `test_push_cut_off_other_commit_is_tag_conflict` | green |
| releases → A cut-off tag push or release creation is decided by a read-back | Release creation cut off before it landed | `evals/release/test_release.py` | `test_release_create_cut_off_not_found` | green |
| releases → A cut-off tag push or release creation is decided by a read-back | Read-back fails too | `evals/release/test_release.py` | `test_push_cut_off_read_back_fails_state_unknown` | green |
| releases → A cut-off tag push or release creation is decided by a read-back | Remote retargeted after the tag push is cut off | `evals/release/test_release.py` | `test_publish_readback_does_not_follow_retargeted_remote` | green |
| vcs-backends → Each repository selects one network remote | Code and store use different remote names | `evals/vcs/test_fetch_pull.py` | `test_code_and_store_refresh_only_their_selected_remote` | green |
| vcs-backends → Each repository selects one network remote | A selected Git remote uses a custom fetch refspec | `evals/vcs/test_fetch_pull.py` | `test_custom_fetch_refspec_cannot_return_stale_selected_main` | green |
| vcs-backends → Each repository selects one network remote | The store does not inherit the code's remote name | `evals/vcs/test_fetch_pull.py` | `test_store_defaults_to_origin_even_when_code_remote_is_set` | green |
| vcs-backends → Each repository selects one network remote | A selected remote is missing | `evals/vcs/test_fetch_pull.py` | `test_fetch_and_push_refuse_missing_selected_remote` | green |
| vcs-backends → Each repository selects one network remote | Git main has a different upstream | `evals/vcs/test_fetch_pull.py` | `test_git_pull_without_remote_keeps_non_origin_upstream` | green |
| vcs-backends → Each repository selects one network remote | Explicit origin is not the default pull | `evals/vcs/test_fetch_pull.py` | `test_git_pull_explicit_origin_uses_origin_main` | green |
| vcs-backends → Each repository selects one network remote | jj reads main from a selected remote | `evals/vcs/test_fetch_pull.py` | `test_jj_main_refresh_tracks_selected_remote_without_moving_bookmarks` | green |
| vcs-backends → The Git backend keeps today's commands | Git commit by name | `evals/vcs/test_git_backend.py` | `test_git_commit_commands_exact` | green |
| vcs-backends → The Git backend keeps today's commands | Git push | `evals/vcs/test_git_backend.py` | `test_git_push_command_exact_no_deadline` | green |
| vcs-backends → The Git backend keeps today's commands | Git pull without a remote setting | `evals/vcs/test_git_backend.py` | `test_git_pull_call_site_forms` | green |
| vcs-backends → The Git backend keeps today's commands | Git commit with nothing to commit | `evals/vcs/test_git_backend.py` | `test_git_commit_nothing_fails_like_git` | green |
| vcs-backends → Fetches for reading move no jj bookmark | Remote main ahead, main tracked | `evals/vcs/test_fetch_pull.py` | `test_fetch_main_tracked_moves_nothing` | green |
| vcs-backends → Fetches for reading move no jj bookmark | Local main diverged before a read | `evals/vcs/test_fetch_pull.py` | `test_fetch_main_diverged_no_conflict` | green |
| vcs-backends → Fetches for reading move no jj bookmark | Release publish on jj with main tracked | `evals/release/test_release_jj.py` | `test_publish_jj_base_by_name_no_bookmark_moves` | green |
| vcs-backends → The GitButler backend is probed before any `but` command | `but` missing | `evals/vcs/test_gitbutler_probe.py` | `test_but_missing_stops_before_write` | green |
| vcs-backends → The GitButler backend is probed before any `but` command | Repo not managed by GitButler | `evals/vcs/test_gitbutler_probe.py` | `test_unmanaged_repo_not_set_up` | green |
| vcs-backends → The GitButler backend is probed before any `but` command | Target is another branch | `evals/vcs/test_gitbutler_probe.py` | `test_target_mismatch_stops` | green |
| vcs-backends → The GitButler backend is probed before any `but` command | Target is on another remote | `evals/vcs/test_gitbutler_probe.py` | `test_explicit_remote_rejects_gitbutler_target_for_other_remote` | green |
| vcs-backends → The GitButler backend is probed before any `but` command | An explicit remote cannot be verified from a local target | `evals/vcs/test_gitbutler_probe.py` | `test_explicit_remote_rejects_gitbutler_local_only_target` | green |
| vcs-backends → A GitButler push publishes only the change branch | Ship with another branch applied | `evals/vcs/test_gitbutler_push.py` | `test_push_only_change_branch` | green |
| vcs-backends → A GitButler push publishes only the change branch | Rewritten branch | `evals/vcs/test_gitbutler_push.py` | `test_push_rejected_never_forced` | green |
| vcs-backends → The GitButler pull never rebases another branch | Cleanup alone in the workspace | `evals/vcs/test_gitbutler_pull.py` | `test_pull_alone_runs_fenced` | green |
| vcs-backends → The GitButler pull never rebases another branch | Another branch applied | `evals/vcs/test_gitbutler_pull.py` | `test_pull_skipped_other_branch` | green |
| vcs-backends → The GitButler pull never rebases another branch | Linked worktree | `evals/vcs/test_gitbutler_pull.py` | `test_pull_skipped_linked_worktree` | green |
| vcs-backends → The GitButler pull never rebases another branch | Finish after a skipped pull | `evals/vcs/test_gitbutler_pull.py` | `test_finish_reads_fetched_main` | green |
| vcs-backends → sw vcs reads settings and fences identity in process | Settings read through pr-pair.sh | `evals/pr-pair/test_pr_pair.py` | `test_pr_pair_reads_selected_role_remote` | green |
| vcs-backends → sw vcs reads settings and fences identity in process | Unknown backend in the settings | `evals/vcs/test_sw_scripts.py` | `test_unknown_backend_stops_as_before` | green |
| vcs-backends → sw vcs reads settings and fences identity in process | Scripts installed under a non-UTF-8 directory | `evals/vcs/test_sw_scripts.py` | `test_scripts_under_non_utf8_directory_is_not_utf8` | green |
| vcs-backends → sw vcs reads settings and fences identity in process | Unpinned settings stop a GitButler push | `evals/vcs/test_gitbutler_push.py` | `test_unassigned_settings_edit_stops_push` | green |
| vcs-backends → sw vcs reads settings and fences identity in process | Fenced push | `evals/vcs/test_sw_fence.py` | `test_fenced_push_runs_in_process` | green |
| vcs-backends → sw vcs reads settings and fences identity in process | Refused fence | `evals/vcs/test_sw_fence.py` | `test_refused_fence_maps_to_fence_failed` | green |
| vcs-backends → sw vcs reads settings and fences identity in process | Login resolved in process | `evals/vcs/test_sw_fence.py` | `test_login_resolved_in_process` | green |
| vcs-backends → sw vcs reads settings and fences identity in process | No gh account to resolve | `evals/vcs/test_sw_fence.py` | `test_no_gh_account_is_fence_failed` | green |
| vcs-backends → sw vcs reads settings and fences identity in process | Store without a Specwright version | `evals/vcs/test_sw_fence.py` | `test_store_without_version_pulls` | green |
| vcs-backends → sw vcs reads settings and fences identity in process | Fenced commands stay unbounded | `evals/vcs/test_sw_fence.py` | `test_fenced_command_has_no_deadline` | green |
| vcs-backends → sw vcs reads settings and fences identity in process | Non-GitHub remote runs unfenced | `evals/vcs/test_sw_fence.py` | `test_non_github_remote_runs_unfenced` | green |

## 1. Record the connection contract

- [x] 1.1 Write ADR 0045 for configured host and safe default fence, independent role remotes, and physical-project settings selection (C1–C3). Record the #260 ship-only boundary and unchanged committed-task requirement. Update the architecture index and affected sections; verify the index target and run the suite map test after adding the ADR.

## 2. Project settings, identity and fence

- [x] 2.1 Before implementation, write and run the new or adapted settings, ambient refusal, Enterprise host/token, indexed credential isolation, selected-project and fence refusal cases in `evals/cli/test_sw_project_version.py` and `evals/pr-pair/test_as_sh.py`; keep the matching public-default cases as regressions. Rework the touched lookup cutoff tests to inject the limit instead of depending on runner speed.
- [x] 2.2 Implement the typed host, fence and role remote, physical code-project selection, shared host/URL normalization, and Enterprise and ambient dispatch. Keep the existing fenced HTTPS and userinfo rules and preserve scoped caller environment for plain Git. Verify the focused modules from 2.1 plus the mapped default fence adapter cases. Update the settings template and README settings and authentication examples, including how to opt out and why defaults remain safe.

## 3. Selected VCS transport and ref policy

- [x] 3.1 Write and run the red Git/jj/GitButler selected-remote, actual Git upstream, fetch and all-effective-push cases in the mapped VCS modules, including explicit off-host fetch for set and unset Enterprise variables and the deterministic deadline test migration. Use real temporary repos with distinct refs, and assert refusal launch/order rather than wall time.
- [x] 3.2 Apply remote settings to fetch, push, upstream pulls and cleanup ref targets. Preserve bare pull when remote is omitted; verify an explicit GitButler target matches the selected remote. Verify 3.1 and rerun mapped unchanged Git/jj/GitButler checks through the focused modules. Update the README VCS table and the branch/roadmap commands for selected refs; verify reused-name exclusion in the planning repo against its selected remote before branch creation.

## 4. Ship, expected set and manual handoff

- [x] 4.1 Write the PR plan, login handoff, ship, watch, finish and rounds boundary tests in `evals/pr-pair/test_pr_pair.py` before changing those paths. Write the two fenced-publication cases first using distinguishable temporary remote refs and recorded `gh` targets. Exercise both indexed rewrite kinds, and show a mismatched final target pushes to neither remote and opens no PR. Replace off-host rounds checks with a committed-fix fixture asserting no store history/network reads, credential helper or emitted round decision. Include the code-only ship, green-code manual watch, clean and pre-edited finish, mixed targets, shared repo, missing login handoff and post-merge code cleanup cases.
- [x] 4.2 Resolve the expected set and carry bound/deferred login across native and skill calls (C5, C11). Confirm the PR push destination in the actual launched environment (C8). Ship only expected members, and hand back local-only stores before watch readiness, finish archive edits or store feedback work (C10); leave explicit local finish and paired workflows intact. Rerun 4.1 and existing pair, feedback, cleanup and unchanged GitHub identity cases from the map. Update the ship/watch/finish skills and README workflow table, with the manual sharing and archiving message.

## 5. PR evidence and bounded mutation routing

- [x] 5.1 Write and run the new host partition, stale/foreign PR snapshot, target inference, and item parent and root cases first in the mapped `test_pr_pair.py`, `test_snapshot_native.py` and `test_pr_reply.py` files. Use the same slug, PR number or SHA on distinct hosts where needed so passing requires checking the target.
- [x] 5.2 Bind discovery, policy, feedback, snapshot and reply evidence to configured host and expected repo/PR; reject other item parents; partition watch and feedback state while retaining github.com's layout (C4, C6, C9). Verify 5.1 and rerun the matching default-target and selected-project regression modules. Update the affected skill instructions and README PR call options.

## 6. Release history and publication target

- [x] 6.1 Write the two release-proof cases first. Use a real custom refspec with a stale ordinary tracking ref, then deterministically schedule a second completed fetch before the first proof reads its commit. Verify exact release commit/tag target and unchanged user refs; no sleeps. Write the remaining red cases in `evals/release/test_release.py` and `test_release_jj.py`: selected remote/host, store main, between-command retarget, read-back after retarget, and deterministic bounded transport outcomes.
- [x] 6.2 Bind the exact fetched main to the selected release target and qualify `gh` calls (C12); retain notes from store main and merged-code evidence only (C7). Rerun the focused release modules, including the existing version guards, tag conflicts, release resumption and jj behavior. Update the release skill and README how-to with remote agreement, stable configuration and manual archive reaching store main.

## 7. Integration and version

- [x] 7.1 Verify the mapped cross-platform integration cases exercising SSH, Enterprise, token-only GitHub and non-default remotes. Locally run the focused changed test cases, not whole suites; guard any heavy local operation with the gaming check. Verify the change and schema with strict OpenSpec validation and the suite map for new tracked files. Run the required Linux, Windows and macOS CI matrices on the PR before reporting readiness.
- [x] 7.2 Run `<sw> release bump --to 0.41.0`; verify `<sw> release check` and `<sw> release notes --proposal openspec/changes/github-connection-options/proposal.md`. Ensure the summary describes the complete release, the default fence and ship-only #260.

## Workflow follow-up

- Sync Itsaplan after each Specwright step. Run pre-ship review, ship and watch the PR to green on all three platforms and resolve review rounds.
- Archive on the PR branch before reporting it ready. Report the PR, checks and reviews; leave merge to the owner.
