# Tasks

## Test map

Test files, shortened: `snap` = `evals/pr-pair/test_pr_snapshot.py`, `pair` = `evals/pr-pair/test_pr_pair.py`, `text` = `evals/pr-pair/test_skill_text.py`, `rev` = `evals/pr-pair/test_reviewers.py` (new), `route` = `evals/review-routes/test_review_run.py`.

| Requirement | Scenario | Test file | Test name | State |
|---|---|---|---|---|
| pr-evidence → Reviewer reports count only for the current head | Push time known | snap | test_snapshot_cutoff_uses_push_time (moved to a `marker` config) | red |
| pr-evidence → Reviewer reports count only for the current head | Previous-head report with push activity missing | snap | test_snapshot_rejects_previous_head_reports_without_push_activity (config-driven) | red |
| pr-evidence → Reviewer reports count only for the current head | Report after the head was first seen | snap | test_snapshot_counts_report_after_first_seen | red |
| pr-evidence → Reviewer reports count only for the current head | First-seen time survives a new process | snap | test_snapshot_first_seen_persists_across_processes | red |
| pr-evidence → Reviewer reports count only for the current head | First-seen record cannot be written | snap | test_snapshot_first_seen_unsaved_keeps_process_time | red |
| pr-evidence → Reviewer reports count only for the current head | Waiting with an unwritable state directory | snap | test_wait_unwritable_state_reports_and_times_out | red |
| pr-evidence → Reviewer reports count only for the current head | Commit-precise reviewers | snap | test_snapshot_sha_pattern_counts_without_push_activity (renamed from test_snapshot_codex_sha_counts_without_push_activity) | red |
| pr-evidence → Reviewers are detected by generic rules | Review bound to the head | rev | test_review_on_head_reports_whatever_the_cutoff | green |
| pr-evidence → Reviewers are detected by generic rules | Review bound to an older commit | rev | test_review_on_older_commit_is_waiting | green |
| pr-evidence → Reviewers are detected by generic rules | A check of the reviewer's app without a rule | rev | test_app_check_without_rule_does_not_report | green |
| pr-evidence → Reviewers are detected by generic rules | Formerly built-in login without a rule | rev | test_former_builtin_login_uses_output_rule | green |
| pr-evidence → A report rule decides for its reviewer | Sha pattern names the head | rev | test_sha_pattern_prefix_of_head_reports | green |
| pr-evidence → A report rule decides for its reviewer | Sha pattern names an older commit | rev | test_sha_pattern_older_sha_waits | green |
| pr-evidence → A report rule decides for its reviewer | Named check | rev | test_named_check_reports_other_name_does_not | green |
| pr-evidence → A report rule decides for its reviewer | Marker comment in progress | rev | test_marker_ignored_until_edited_again | green |
| pr-evidence → A report rule decides for its reviewer | Review on the head under a marker rule | rev | test_review_on_head_counts_under_marker_rule | green |
| pr-evidence → A report rule decides for its reviewer | Marker with regex characters | rev | test_marker_is_literal | green |
| pr-evidence → A bad report rule stops the snapshot | Bad rule | snap | test_bad_pattern_exits_2_without_gh | red |
| pr-evidence → A bad report rule stops the snapshot | Unknown key | snap | test_unknown_report_key_exits_2_without_gh | red |
| pr-evidence → The snapshot shows each reviewer's evidence | Announcement and finished review | rev | test_evidence_newest_first_with_excerpts | green |
| pr-evidence → The snapshot shows each reviewer's evidence | Nothing on the head | rev | test_evidence_empty_for_previous_head_only | green |
| pr-evidence → Reviewer settings reach the snapshot as a file | Policy writes main's reviewers | pair | test_policy_config_carries_main_check_rule (plus snap test_snapshot_applies_config_check_rule) | red |
| pr-evidence → Reviewer settings reach the snapshot as a file | Old flag | snap | test_reviewer_flag_exits_2_naming_reviewer_config | red |
| pr-evidence → Reviewer settings reach the snapshot as a file | Missing file | snap | test_missing_reviewer_config_exits_2_without_gh | red |
| pr-evidence → Reviewer settings reach the snapshot as a file | Unwritable state directory | pair | test_context_config_falls_back_to_temp_dir (plus snap test_snapshot_with_fallback_config_reports_reviewers) | red |
| pr-evidence → Reviewer settings reach the snapshot as a file | Regex characters in a rule | pair | test_config_pattern_byte_for_byte | green |
| pr-evidence → Reviewer settings are read strictly everywhere | Double-quoted escape | pair | test_context_prints_settings_problem_without_exiting (plus text test_watch_stops_on_settings_problem) | red |
| pr-evidence → Reviewer settings are read strictly everywhere | Single-quoted pattern | pair | test_readme_and_template_report_examples_pass_both_readers | red |
| pr-evidence → A snapshot names the reviewer rules it used | Wait started with the work tree's rules | pair | test_reported_check_digest_mismatch_is_rules_mismatch | green |
| pr-evidence → A snapshot names the reviewer rules it used | Same rules | pair | test_reported_check_equal_digest_ok | green |
| pr-merge → Agent mode archives before merging without asking | Ready change, not archived | text | test_agent_mode_archives_without_asking | green |
| pr-merge → Agent mode archives before merging without asking | Archive fails | text | test_agent_mode_archive_failure_stops_no_merge | green |
| pr-merge → Agent mode archives before merging without asking | Branch-only agent mode asks first | text | test_drift_without_head_agent_asks_nothing | green |
| pr-merge → Agent mode archives before merging without asking | Looser rules at the archive decision | text | test_archive_decision_rules_mismatch_waits_without_asking | red |
| pr-merge → Only the ready head is merged | Merge with the configured method | pair | test_merge_sends_method_and_head_sha_fenced | green |
| pr-merge → Only the ready head is merged | Head moved after ready | pair | test_merge_head_changed_409_reports_head_changed | green |
| pr-merge → Only the ready head is merged | Commit after the archive head | text | test_reviewerless_archive_head_merged_only_if_unchanged (reworded to the carry-over) | red |
| pr-merge → Only the ready head is merged | Invalid method | pair | test_merge_invalid_method_usage_no_request | green |
| pr-merge → Required reviewers are those of the authorizing set | Wait started with an edited set | pair | test_snapshot_without_main_required_reviewer_not_ok | green |
| pr-merge → Required reviewers are those of the authorizing set | Authorizing reviewer reported | pair | test_main_required_reviewer_reported_ok (with matching digest) | green |
| pr-merge → Required reviewers are those of the authorizing set | Wait started with looser rules | pair | test_reported_check_digest_mismatch_is_rules_mismatch | green |
| pr-merge → Required reviewers are those of the authorizing set | Archive head carry-over | pair | test_reviewed_head_carry_over_checks_main_set | green |
| pr-merge → Required reviewers are those of the authorizing set | Store-backed pair with main's reviewers | pair | test_store_adds_the_store_reviewers_side (with digests) | green |
| pr-watch → The archive head gets no new review round | Archive pushed after a clean review | text | test_watch_archive_head_no_request_no_reviewers (reworded: carry-over, `--reviewer-config`) | red |
| pr-watch → The archive head gets no new review round | Setting turned on | text | test_watch_review_after_archive_true_rerequests | green |
| pr-watch → The archive head gets no new review round | Archive commit touches other files | route | test_archive_only_false_outside_paths | green |
| pr-watch → The archive head gets no new review round | Another commit after the reviewed head | route | test_archive_only_false_two_commits | green |
| pr-watch → The archive head gets no new review round | Branch protection wants a fresh approval | text | test_watch_archive_review_required_asks_once | green |
| pr-watch → The archive head gets no new review round | Store-backed archive | route | test_archive_only_in_store_dir | green |
| pr-watch → A wait can skip wakes that are only check progress | A check passes while others run | snap | test_check_progress_is_filtered | green |
| pr-watch → A wait can skip wakes that are only check progress | The last check finishes | snap | test_last_check_done_wakes | green |
| pr-watch → A wait can skip wakes that are only check progress | CI finishes before the reviewer's check | snap | test_ci_done_wakes_while_reviewer_check_pending | red |
| pr-watch → A wait can skip wakes that are only check progress | Only a reviewer's check is pending | snap | test_reviewer_check_progress_alone_wakes | red |
| pr-watch → A wait can skip wakes that are only check progress | A check fails | snap | test_new_failure_wakes | green |
| pr-watch → A wait can skip wakes that are only check progress | Feedback arrives during check progress | snap | test_feedback_during_checks_wakes | green |
| pr-watch → A wait can skip wakes that are only check progress | A conflict appears | snap | test_dirty_wakes | green |
| pr-watch → A wait can skip wakes that are only check progress | Unknown mode or no wait | snap | test_bad_until_exits_2_without_gh | green |
| pr-watch → Watch waits for attention | Watch's wait command | text | test_watch_waits_until_attention (three timeouts and conditions) | red |
| pr-watch → Watch waits for attention | Ready after a quiet wait with a check re-run | snap | test_rerun_back_to_baseline_times_out (plus text test_watch_timeout_wake_is_quiet_window) | red |
| pr-watch → Watch waits for attention | Default settle window | pair | test_context_settle_default_300 | green |
| pr-watch → Watch waits for attention | Long wait ends quiet | text | test_watch_timeout_wake_is_quiet_window | red |
| pr-watch → Watch waits for attention | Pending check makes the merge state unstable | text | test_watch_ready_accepts_unstable_without_ci_pending | red |
| pr-watch → Watch waits for attention | Not yet ready | text | test_watch_uses_1800_until_otherwise_ready | red |
| pr-watch → Watch waits for attention | Bad settle value | pair | test_context_bad_settle_is_settings_problem | green |
| pr-watch → An advisory reviewer's named check stops blocking once it reported | Advisory reviewer timed out with its check pending | rev | test_advisory_timed_out_check_moves_to_advisory_pending | green |
| pr-watch → An advisory reviewer's named check stops blocking once it reported | Required reviewer's check pending | rev | test_required_reviewer_check_pending_not_ci | green |
| pr-watch → An advisory reviewer's named check stops blocking once it reported | Shared app | rev | test_shared_app_checks_stay_ci | green |
| pr-watch → An advisory reviewer's named check stops blocking once it reported | Bot that is not configured | rev | test_unconfigured_app_check_is_ci | green |
| pr-watch → An archive-only head needs no further quiet window | CI already green | text | test_archive_head_ready_after_settle_unstable | red |
| pr-watch → An archive-only head needs no further quiet window | Snapshot before CI exists | text | test_archive_head_waits_rest_of_settle_before_judging | red |
| pr-watch → An archive-only head needs no further quiet window | CI still running | text | test_archive_head_ready_on_ci_pending_zero_wake | red |
| pr-watch → An archive-only head needs no further quiet window | Feedback on the archive head | text | test_archive_head_feedback_runs_feedback | red |
| pr-watch → An archive-only head needs no further quiet window | Failing CI on the archive head | text | test_archive_head_ci_failure_handled_as_any_head | red |
| pr-watch → An announced review can extend the wait | Announcement only | text | test_watch_announcement_only_waits | red |
| pr-watch → An announced review can extend the wait | Timeout passed after an announcement | text | test_watch_announcement_timeout_reports_and_asks | red |
| change-finish → An archive-only push skips the code validate | Archive of a reviewed head | text | test_ship_skips_validate_for_archive_only_push | red |
| change-finish → An archive-only push skips the code validate | Store-backed archive | text | test_ship_store_archive_runs_store_validate_only | red |
| change-finish → An archive-only push skips the code validate | Archive commit with other files | text | test_ship_runs_validate_when_not_archive_only | red |
| change-finish → An archive-only push skips the code validate | No ready head | text | test_ship_runs_validate_without_ready_head | red |
| change-finish → An archive-only push skips the code validate | Check fails to run | text | test_ship_runs_validate_and_names_archive_only_error | red |

## 1. Records: ADR, architecture, roadmap

- [x] 1.1 Write `docs/adr/0022-reviewer-detection-is-generic.md` ("Reviewer detection is generic; bot-specific rules live in settings": adds to 0020 that the compared reviewer settings include `report`, a report counts only under the authorizing set's rules by digest, scripts name no reviewer, the agent may only add waiting). Verify: the file exists with Status/Context/Decision/Consequences like 0021.
- [x] 1.2 Update `openspec/architecture.md`: the `specwright-pr` component row (`reviewers.py`), a State ownership row for the reviewer-config file, Resource bounds (20 reviewers, 500-character patterns, 10 evidence items), In-force ADRs (0022). Verify: `grep -n "0022\|reviewers.py" openspec/architecture.md` shows each.
- [x] 1.3 Update `openspec/roadmap.md`: add `generic-reviewer-detection` (0.15.0, #166) to M6 before the packs, renumber pack-mechanism to 0.16.0 and gamedev-pack to 0.17.0, and update the release exit criterion. Verify: `grep -n "0.15.0\|0.16.0\|0.17.0" openspec/roadmap.md`.
- [x] 1.4 Add a `suites.json` rule or `no_eval` entry for every new tracked file (ADR, `reviewers.py`, `evals/pr-pair/test_reviewers.py`). Verify: `python -m unittest evals/runner/test_suite_map.py` passes.

## 2. Rule evaluator `reviewers.py`

- [x] 2.1 Write `evals/pr-pair/test_reviewers.py` with the `rev` rows of the test map: material and config fixtures in, compact snapshot out (generic rules, each `report` key, `ignore`, evidence, `ci_pending`/`advisory_pending`, config validation: format, unknown key, bad regex, bounds of 20 reviewers and 500 characters). Verify red: `python -m unittest evals/pr-pair/test_reviewers.py` fails because the module is missing.
- [x] 2.2 Implement `skills/specwright-pr/scripts/reviewers.py` (D1, D3: `--material`, `--config`, `--head`; `re.search`, case-sensitive; sha prefix 7–40 hex; literal marker on the last edit at or after the cutoff; review on the head commit always counts; checks only via `report.check`; evidence 10 items, 300-character excerpts; `json.dumps` compact; exit 2 naming reviewer and key). Verify: `python -m unittest evals/pr-pair/test_reviewers.py` green; flip the `rev` rows green.

## 3. Reviewer config and settings in `pr-pair.sh`

- [x] 3.1 Write failing tests in `pair`: `reviewers_of` keeps a normalized `report`, and drift covers it; `context` and `policy` write canonical content-addressed configs (`reviewer_config`, `reviewer_config.{main,head}.{code[,store]}`), fall back to the temp dir when the state dir is unwritable, keep patterns byte-for-byte; `policy` drops `reviewer_args`; `reported_check` compares digests and returns `rules_mismatch`; `pr.settle` default 300 and a bad value or `too_many_reviewers` as `settings_problem` in `context` (exit 2 in `policy`); `context` prints `settings_problem` for a strict-reader problem without exiting; README and template `report:` examples pass both readers. Verify red: `python -m unittest evals/pr-pair/test_pr_pair.py -k <each new name>` fails for the right reason.
- [x] 3.2 Implement in `skills/specwright-pr/scripts/pr-pair.sh` (D2, D4, D5, D6, D10) and update existing `pair` tests that read `reviewer_args`. Verify: the new and touched `pair` tests pass; flip their rows green; re-run the `green` `pair` rows (`test_merge_sends_method_and_head_sha_fenced`, `test_merge_head_changed_409_reports_head_changed`, `test_merge_invalid_method_usage_no_request`, `test_snapshot_without_main_required_reviewer_not_ok`, `test_reviewed_head_carry_over_checks_main_set`).

## 4. Snapshot: config file, generic detection, CI-only filter

- [ ] 4.1 Move `snap` fixtures from `--reviewer` to `--reviewer-config` files, replace the Codex, Kody and Mira cases with `sha_pattern`, `check` and `marker` configs, and add the new `snap` rows (old flag, missing file, bad pattern, unknown key, CI finishes before the reviewer's check, reviewer check progress alone wakes, config check rule applied, fallback config). Verify red: the touched tests fail against the current script.
- [ ] 4.2 Change `skills/specwright-pr/scripts/pr-snapshot.sh`: remove every bot name and format (lines ~343–372 and `$review_check`); parse `--reviewer-config`, make `--reviewer` exit 2 naming it, validate the config before any `gh` call; emit raw material to a system-temp `mktemp` file (`cygpath -m` where present, trap removal) and run `bounded.py -- python -I reviewers.py`; output carries `now`, `reviewer_config` digest, `evidence`, `by`, `checks.ci_pending`; `only_progress` tests `"ci_pending":[1-9]`. Verify: every `snap` test passes locally for the touched cases (`python -m unittest evals/pr-pair/test_pr_snapshot.py`, this one module only), a compact-JSON wake test included; `grep -nE "codex|kody|mira|kintsugi" skills/specwright-pr/scripts/` finds nothing; flip the `snap` rows green and re-run the `green` `snap` rows.

## 5. Skill text: watch, merge, ship, finish

- [ ] 5.1 Write failing `text` tests for the red `text` rows: three wait timeouts with conditions, any `timeout` wake as the quiet window, CLEAN or UNSTABLE ready rule, `settings_problem` stops watch, announced-review rule, archive head judged once `pr.settle` has passed since the push, `rules_mismatch` at the archive decision waits without asking, the carry-over wording, `ready head:` hand-off and ship's archive-only validate skip. Verify red: `python -m unittest evals/pr-pair/test_skill_text.py` fails on the new names only.
- [ ] 5.2 Edit `skills/specwright-pr/SKILL.md` (Reviewers section without built-in bots, settings block with `report` and `pr.settle`, ship validate, watch steps 1 and 3, archive step, merge reviewer check with `--reviewer-config`) and `skills/specwright-finish/SKILL.md` `## pr` (passes `ready head:` on to ship). Update `evals/git-workflow/test_grade.py` if it greps `--reviewer`. Verify: `test_skill_text.py` green; re-run the `green` `text` rows; flip the red ones green; `grep -rn "\-\-reviewer " skills/` finds nothing.

## 6. Template and README

- [ ] 6.1 Update `templates/openspec/specwright.yaml` and the README reviewer section: generic placeholder bot names, `report:` keys, single-quoted copyable examples for the three former built-in formats without naming any tool the design came from, `pr.settle`, and the migration note for `--reviewer`. Verify: `test_readme_and_template_report_examples_pass_both_readers` passes; `grep -n "Code review in progress\|mira-walkthrough" README.md templates/` finds nothing outside the examples.
- [ ] 6.2 Confirm the `report:` blocks for the dogfood projects' bots against live PRs of mythspine and blackgrid (design Open Question), and correct the README examples if a format differs. Verify: each example matches one real comment or check, noted in the PR description.

## 7. Release

- [ ] 7.1 `bash skills/specwright-release/scripts/release.sh bump --to 0.15.0`, and rewrite the summary of the proposal's `## Release Notes` to describe the whole release. Verify: `release.sh check` and `release.sh notes --proposal openspec/changes/generic-reviewer-detection/proposal.md` pass.
- [ ] 7.2 Integration check: `openspec validate --all --strict` passes, and the PR's CI (`.github/workflows/evals.yml`) is green on Linux, Windows and macOS. Verify: the CI run link in the PR.

## Workflow follow-up

- After merge, add `report:` blocks to the dogfood projects' `openspec/specwright.yaml` (mythspine, blackgrid) for bots that relied on the built-in rules.
- Milestone M6 close needs a green `gh workflow run evals.yml --ref main` on the closing head.
