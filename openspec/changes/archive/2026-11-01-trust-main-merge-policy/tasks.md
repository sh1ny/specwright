# Tasks

## Test map

| Requirement | Scenario | Test file | Test name | State |
|---|---|---|---|---|
| pr-merge → The merge policy comes from main | Policy unchanged by the PR | evals/pr-pair/test_pr_pair.py | Policy.test_same_policy_no_drift_main_values | green |
| pr-merge → The merge policy comes from main | Branch turns on agent merge | evals/pr-pair/test_pr_pair.py | Policy.test_head_turns_on_agent_merge_drifts | green |
| pr-merge → The merge policy comes from main | Local checkout edited, remote unchanged | evals/pr-pair/test_pr_pair.py | Policy.test_work_tree_settings_are_ignored | green |
| pr-merge → The merge policy comes from main | No settings file on main | evals/pr-pair/test_pr_pair.py | Policy.test_missing_file_on_main_is_user_mode | green |
| pr-merge → The merge policy comes from main | Invalid method on main | evals/pr-pair/test_pr_pair.py | Policy.test_bad_method_on_main_is_bad_setting | green |
| pr-merge → The merge policy comes from main | Main branch renamed in the PR | evals/pr-pair/test_pr_pair.py | Policy.test_default_branch_from_github_not_main_branch | green |
| pr-merge → Required reviewers are those of the authorizing set | Wait started with an edited set | evals/pr-pair/test_pr_pair.py | PolicyReviewers.test_snapshot_without_main_required_reviewer_not_ok | green |
| pr-merge → Required reviewers are those of the authorizing set | Authorizing reviewer reported | evals/pr-pair/test_pr_pair.py | PolicyReviewers.test_main_required_reviewer_reported_ok | green |
| pr-merge → Required reviewers are those of the authorizing set | Archive head carry-over | evals/pr-pair/test_pr_pair.py | PolicyReviewers.test_reviewed_head_carry_over_checks_main_set | green |
| pr-merge → Required reviewers are those of the authorizing set | Store-backed pair with main's reviewers | evals/pr-pair/test_pr_pair.py | PolicyReviewers.test_store_snapshot_checked_against_store_head | green |
| pr-merge → A policy difference needs the user | Required reviewer replaced | evals/pr-pair/test_pr_pair.py | Policy.test_reviewer_set_difference_listed | green |
| pr-merge → A policy difference needs the user | User confirms the difference | evals/pr-pair/test_skill_text.py | AgentMerge.test_drift_yes_merges_with_head_method | green |
| pr-merge → A policy difference needs the user | User declines | evals/pr-pair/test_skill_text.py | AgentMerge.test_drift_no_reports_ready_without_merge | green |
| pr-merge → A policy difference needs the user | Neither copy opts in | evals/pr-pair/test_skill_text.py | AgentMerge.test_drift_without_head_agent_asks_nothing | green |
| pr-merge → A policy difference needs the user | PR turns agent merge off | evals/pr-pair/test_pr_pair.py | Policy.test_head_turns_agent_merge_off_drifts_and_main_stays_agent | green |
| pr-merge → A policy difference needs the user | Head moves after the answer | evals/pr-pair/test_skill_text.py | AgentMerge.test_drift_answer_covers_one_head | green |
| pr-merge → A policy difference needs the user | Formatting only | evals/pr-pair/test_pr_pair.py | Policy.test_formatting_only_difference_is_no_drift | green |
| pr-merge → An unknown policy merges nothing | Read fails | evals/pr-pair/test_pr_pair.py | Policy.test_failed_read_is_unknown_exit_3 | green |
| pr-merge → An unknown policy merges nothing | No settings file at the head | evals/pr-pair/test_pr_pair.py | Policy.test_missing_file_at_head_is_unknown | green |
| pr-merge → An unknown policy merges nothing | Read succeeds after a failure | evals/pr-pair/test_pr_pair.py | Policy.test_read_after_failure_succeeds | green |
| pr-merge → Merging is opt-in | Default project never merges | evals/pr-pair/test_pr_pair.py | Policy.test_no_merge_key_anywhere_is_user | green |
| pr-merge → Merging is opt-in | Opted-in project merges | evals/pr-pair/test_skill_text.py | AgentMerge.test_merge_decided_by_policy_not_context | green |
| pr-merge → Merging is opt-in | Unrecognised value | evals/pr-pair/test_pr_pair.py | Policy.test_unrecognised_merge_value_noted_as_user | green |
| pr-merge → Merging is opt-in | Local finish ignores the setting | evals/pr-pair/test_skill_text.py | AgentMerge.test_watch_merges_only_with_pr_merge_agent (existing) | green |
| pr-merge → Agent mode archives before merging without asking | Ready change, not archived | evals/pr-pair/test_skill_text.py | AgentMerge.test_archive_without_asking_needs_policy_from_main | green |
| pr-merge → Agent mode archives before merging without asking | Archive fails | evals/pr-pair/test_skill_text.py | AgentMerge.test_agent_mode_archive_failure_stops_no_merge (existing) | green |
| pr-merge → Agent mode archives before merging without asking | Branch-only agent mode asks first | evals/pr-pair/test_skill_text.py | AgentMerge.test_archive_without_asking_needs_policy_from_main | green |

Extra tests, no row: `evals/pr-pair/test_fake_gh.py` `Contents` (the fake's contents endpoint: file, 404, non-file, ref by branch and by sha).

## 1. ADR 0020

- [x] 1.1 Write `docs/adr/0020-agent-merge-takes-its-policy-from-the-default-branch.md` (Status: accepted, today's date, "adds to 0009"), recording design D1-D6: the policy keys, read from GitHub's default branch and at the ready head before the archive decision and each merge request, normalized comparison, a yes only for a head with `pr.merge: agent` whose required reviewers reported, reviewer reports checked against the authorizing set per repository, unknown merges nothing. Add its row to the in-force index in `openspec/architecture.md`. Verify the index row links the file and `python -m unittest evals/runner/test_suite_map.py` passes.

## 2. Fake gh contents endpoint

- [x] 2.1 Write `Contents` tests in `evals/pr-pair/test_fake_gh.py`: `repos/<o>/<n>/contents/<path>?ref=<branch or sha>` returns `{type: file, encoding: base64, content}` from seeded state, 404 (`(HTTP 404)` on stderr) for a missing path, a JSON list for a directory, and `repos/<o>/<n>` returns the seeded `default_branch`. Run `python -m unittest evals/pr-pair/test_fake_gh.py` and see them fail.
- [x] 2.2 Add the endpoint and its seed shape to `evals/fakes/gh.py` (state written as the fake already writes it); verify the `Contents` tests pass.

## 3. `pr-pair.sh policy`: reads, drift and unknown

- [x] 3.1 Write the `Policy` tests in `evals/pr-pair/test_pr_pair.py` for every `Policy.*` row of the test map, against the fake `gh` (main and head copies seeded through the contents endpoint, a work-tree copy that differs). Run the module and see them fail for the missing subcommand.
- [x] 3.2 Implement `policy --repo --head [--store]` in `skills/specwright-pr/scripts/pr-pair.sh`: `default_branch` from `repos/<o>/<n>`, the two contents reads through `gh` (fenced, bounded), base64 decode and `parse_yaml`, the shared normalization with `contexts`/`reviewers_of` (factor it out so `context` keeps its output byte for byte), `drift`, the main-side effective values with `bad_setting` (exit 2), and exit 3 `lookup_failed` with `merge policy unknown: ...` for a failed, cut-off, non-file or unparseable read and for a 404 at the head; a 404 on main is an empty file. Document it in the script header. Verify the `Policy` rows turn green and the existing `Context` and `ContextPin` tests still pass; flip the rows green.

## 4. `policy` reviewer check

- [x] 4.1 Write the `PolicyReviewers` tests for every `PolicyReviewers.*` row (snapshot files as `pr-snapshot.sh` writes them: `head_oid`, `reviewers` with `login`, `role`, `state`), plus a usage test that `--store` without `--snapshot store=` and `--reviewed-head store=` is exit 2. Run the module and see them fail.
- [x] 4.2 Implement `--snapshot code=|store=` and `--reviewed-head code=|store=` in `policy`: `reported.main|head.code|store` (`ok`, `missing`, `head_mismatch`) checked per repository against that repository's reviewed head, and `reviewer_args.main|head.code|store` (`login:role:seconds`). Document it in the header. Verify the `PolicyReviewers` rows turn green; flip them.

## 5. Watch reads the policy

- [x] 5.1 Write the `AgentMerge` skill-text tests for every `AgentMerge.*` red row in `evals/pr-pair/test_skill_text.py`: watch runs `pr-pair.sh policy` with the snapshot(s) at the archive decision and again after the Version check before each merge request, archives without asking only on main's `agent`, no drift and `reported.main` ok, lists drift and asks only for a head with `pr.merge: agent` and `reported.head` ok, merges on yes with the head's `merge_method` at that head only, restarts the wait with `reviewer_args` of the authorizing set (never the head's before a yes) when it is not ok, and reports `merge policy unknown` and merges nothing on exit 3. Run the module and see them fail.
- [x] 5.2 Update `skills/specwright-pr/SKILL.md`: the Agent merge paragraph and settings block (main decides; `context`'s `merge` is the start-of-watch read only), watch's merge-settings paragraph, **Archive before merge**, the archive-only carry-over (`--reviewed-head <repo>=<R>`), **Merge** and the store pair. Verify the `AgentMerge` rows turn green, the existing `SkillText`, `RunLogin` and `AgentMerge` tests pass, and flip the rows green.

## 6. Release 0.13.0

- [x] 6.1 Run `python -m unittest evals/runner/test_suite_map.py` for the files this change adds (ADR 0020), and add a `suites.json` rule or `no_eval` entry where it fails. Then run `bash skills/specwright-release/scripts/release.sh bump --to 0.13.0` and rewrite the summary of this proposal's `## Release Notes` to describe the whole release. Verify with `release.sh check` and `bash skills/specwright-release/scripts/release.sh notes --proposal openspec/changes/trust-main-merge-policy/proposal.md`, both exit 0.

## Workflow follow-up

- Push the branch and open the PR with `specwright-pr` ship; the pre-ship review runs first. CI runs every suite on Linux, Windows and macOS, and every job must pass (M6 exit criterion).
- After the merge, publish 0.13.0 (`specwright-release` publish) and confirm #141 is closed by the merged PR.
