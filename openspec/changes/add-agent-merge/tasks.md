# Tasks

## Test map

Script behaviour is tested against the fake `gh` (`evals/fakes/gh.py`) and real `git`: `evals/pr-pair/test_pr_pair.py` covers the new `pr-pair.sh merge` and `delete-remote` subcommands, which is where the GitHub-facing guarantees (head guard, read-back, refusal, ref checks) live. The agent-instruction rules (when watch merges, what it never does, the hand-offs) are checked by position and key terms: `evals/pr-pair/test_skill_text.py` covers `specwright-pr`, and `evals/git-workflow/test_instructions.py` covers `specwright-finish`. The milestone's exit criterion "an agent-merge eval merges a ready PR … and never merges when it does not" is met by two graded agent evals in `evals/git-workflow/evals.json` (rows marked *graded*), run and graded with `grade.py`.

| Requirement | Scenario | Test file | Test name | State |
|---|---|---|---|---|
| pr-merge → Merging is opt-in | Default project never merges | evals/git-workflow/evals.json (graded) + evals/pr-pair/test_skill_text.py | eval-watch-merge-default-user; test_watch_merges_only_with_pr_merge_agent | red |
| pr-merge → Merging is opt-in | Opted-in project merges | evals/git-workflow/evals.json (graded) | eval-watch-agent-merge | red |
| pr-merge → Merging is opt-in | Unrecognised value | evals/pr-pair/test_pr_pair.py | test_context_merge_unknown_value_reported_as_user | red |
| pr-merge → Merging is opt-in | Local finish ignores the setting | evals/git-workflow/test_instructions.py | test_finish_local_merge_ignores_pr_merge | red |
| pr-merge → An agent merge needs a required reviewer | Required reviewer configured | evals/pr-pair/test_pr_pair.py | test_context_merge_ready_with_required_reviewer | red |
| pr-merge → An agent merge needs a required reviewer | No required reviewer | evals/pr-pair/test_pr_pair.py | test_context_merge_blocked_without_required_reviewer | red |
| pr-merge → An agent merge needs a required reviewer | Store without a required reviewer | evals/pr-pair/test_pr_pair.py | test_context_merge_blocked_store_reviewers_empty | red |
| pr-merge → Agent mode archives before merging without asking | Ready change, not archived | evals/pr-pair/test_skill_text.py | test_agent_mode_archives_without_asking | red |
| pr-merge → Agent mode archives before merging without asking | Archive fails | evals/pr-pair/test_skill_text.py | test_agent_mode_archive_failure_stops_no_merge | red |
| pr-merge → Only the ready head is merged | Merge with the configured method | evals/pr-pair/test_pr_pair.py | test_merge_sends_method_and_head_sha_fenced | red |
| pr-merge → Only the ready head is merged | Head moved after ready | evals/pr-pair/test_pr_pair.py | test_merge_head_changed_409_reports_head_changed | red |
| pr-merge → Only the ready head is merged | Commit after the archive head | evals/pr-pair/test_skill_text.py | test_reviewerless_archive_head_merged_only_if_unchanged | red |
| pr-merge → Only the ready head is merged | Invalid method | evals/pr-pair/test_pr_pair.py | test_merge_invalid_method_usage_no_request | red |
| pr-merge → A refused merge stops | Method disallowed | evals/pr-pair/test_pr_pair.py | test_merge_405_refused_single_request | red |
| pr-merge → A refused merge stops | Merge queue required | evals/pr-pair/test_pr_pair.py + evals/pr-pair/test_skill_text.py | test_merge_queue_refusal_no_auto_merge; test_never_admin_auto_queue_or_other_method | red |
| pr-merge → The merge is confirmed before cleanup | Merge confirmed | evals/pr-pair/test_pr_pair.py | test_merge_reads_back_merged | red |
| pr-merge → The merge is confirmed before cleanup | Read-back fails | evals/pr-pair/test_pr_pair.py | test_merge_readback_failure_exit3_unknown | red |
| pr-merge → Cleanup after an agent merge | Squash merge cleans up | evals/git-workflow/evals.json (graded) | eval-watch-agent-merge (squash variant assertions) | red |
| pr-merge → Cleanup after an agent merge | Pull fails after the merge | evals/pr-pair/test_skill_text.py | test_agent_cleanup_pull_failure_deletes_nothing | red |
| pr-merge → The remote branch is deleted only at the merged head | Remote branch deleted | evals/pr-pair/test_pr_pair.py | test_delete_remote_at_head_deletes | red |
| pr-merge → The remote branch is deleted only at the merged head | Remote branch moved | evals/pr-pair/test_pr_pair.py | test_delete_remote_moved_keeps_branch | red |
| pr-merge → The remote branch is deleted only at the merged head | Another PR is based on the branch | evals/pr-pair/test_pr_pair.py | test_delete_remote_based_on_keeps_branch | red |
| pr-merge → The remote branch is deleted only at the merged head | User mode keeps remote branches | evals/pr-pair/test_skill_text.py + evals/git-workflow/test_instructions.py | test_delete_remote_only_in_agent_mode; test_finish_resume_delete_remote_agent_mode_only | red |
| pr-merge → The remote branch is deleted only at the merged head | Already deleted by GitHub | evals/pr-pair/test_pr_pair.py | test_delete_remote_missing_ref_gone | red |
| pr-merge → Store-backed changes merge as a pair | Both merge | evals/pr-pair/test_skill_text.py | test_store_pair_merges_store_then_code_on_pair_ready | red |
| pr-merge → Store-backed changes merge as a pair | Code merge refused | evals/pr-pair/test_skill_text.py | test_store_split_reports_planning_merged_code_pending | red |
| pr-merge → Store-backed changes merge as a pair | Watch after a split | evals/pr-pair/test_pr_pair.py | test_pair_state_split_hand_off (existing, re-run) | green |
| pr-merge → Store-backed changes merge as a pair | Only one PR ready | evals/pr-pair/test_skill_text.py | test_store_pair_merges_store_then_code_on_pair_ready | red |
| pr-merge → Roadmap branches merge like changes | Close branch merges | evals/pr-pair/test_skill_text.py | test_agent_merge_branch_kinds | red |
| pr-merge → Roadmap branches merge like changes | Unknown branch | evals/pr-pair/test_skill_text.py | test_agent_merge_branch_kinds | red |
| pr-merge → Finish hands a PR to watch in agent mode | Archive outside watch | evals/git-workflow/test_instructions.py | test_finish_pr_agent_mode_starts_watch | red |
| pr-merge → Finish hands a PR to watch in agent mode | Ship fails | evals/git-workflow/test_instructions.py | test_finish_pr_agent_mode_ship_failure_no_watch | red |

## 1. ADR 0009

- [x] 1.1 Write `docs/adr/0009-opt-in-agent-merge-at-the-ready-head.md` (MADR-short, `Status: proposed`) from design D1-D7 and D4a: merge only with `pr.merge: agent` and `finish: pr`, from watch's ready state, with at least one required reviewer, at the ready head SHA through the REST merge with read-back, and a reviewer-less archive head only when it is the head `archive-only` judged. Store first, then code, with the split stop. No admin rights, auto-merge, queueing, method fallback or review dismissal. Remote deletion only at the merged head with no PR based on it. Include the rejected alternatives (`gh pr merge`, a separate merge mode, lease push delete) and the reversal cost. Verify: the file exists with every section.
- [ ] 1.2 Accept it: `Status: accepted`, Date 2026-10-13 (this change's design review passed), and add its row to the in-force index in `openspec/architecture.md`. In the same file, update the `specwright-pr` component row (the merge and delete-remote subcommands) and the State ownership table (the PR merge state, read back from GitHub; the remote change branch deleted by `delete-remote` in agent mode). Verify: `grep -n "0009" openspec/architecture.md` shows the index row.

## 2. Settings in `pr-pair.sh context`

- [ ] 2.1 Write the failing `test_pr_pair.py` tests for the settings rows. `context` reports `merge` (`user` | `agent`; any other value → `user` with a `merge_note` naming the value), `merge_method` (any value other than merge/squash/rebase → `ok: false`, exit 2, error `bad_setting`), `delete_branch` (a non-boolean → exit 2 `bad_setting`), and `merge_ready` per repo: `false` with reason `no_required_reviewer` when that repo's reviewer set (`pr.reviewers`; store: `planning_store.reviewers`) has no `required` entry. Cover the rows Unrecognised value, Required reviewer configured, No required reviewer, and Store without a required reviewer. Verify that they fail for the right reason.
- [ ] 2.2 Implement them in `contexts`/`repo_ctx` (`pr-pair.sh:500-534`) with the defaults `user`, `merge`, `true`. Watch reads them when it starts (review S3), so bad values stop it before any wait. Verify: the 2.1 tests and the whole `evals/pr-pair` suite pass; flip the rows green.

## 3. `pr-pair.sh merge`

- [ ] 3.1 Extend the fake `gh` (`evals/fakes/gh.py` `cmd_api`). `PUT repos/o/n/pulls/N/merge` merges an open PR whose head matches `sha` and whose method is in the repo's `allowed_methods`: it sets `merged_at`, `merge_commit_sha` and state closed, and logs the call. A head mismatch → HTTP 409, a disallowed method or `merge_queue: true` → 405, an already merged PR → 405. A test can make the next call fail with no HTTP status (`inject_failure`). Add `GET`/`DELETE repos/o/n/git/ref(s)/heads/<b>` backed by per-repo branch heads. Verify: new cases in `evals/pr-pair/test_fake_gh.py` pass.
- [ ] 3.2 Write the failing `test_pr_pair.py` tests for `merge --repo --pr --method --head` (design D2): the method and head SHA are sent, and the call goes through the repo's login; read-back MERGED → `status: merged` with `head_sha`/`merge_commit_sha`, including a PR a person merged first (PUT 405, read-back MERGED); 409 → `refused`, `reason: head_changed`; 405 → `refused` with GitHub's message and exactly one PUT in the log; a queue refusal sends no auto-merge or queue call; a failed read-back or a PUT with no HTTP status and an unreadable read-back → exit 3 `unknown`; a bad `--method` or `--head` → exit 2 with no request. Verify that they fail.
- [ ] 3.3 Implement `cmd_merge` with `gh_obj` (`pr-pair.sh:584`) and the usage header, and register it in `COMMANDS`. Verify: the 3.2 tests pass; flip the rows green.

## 4. `pr-pair.sh delete-remote`

- [ ] 4.1 Write the failing tests for `delete-remote --repo --branch --head` (design D3): ref at the head and no open PR based on it → `deleted`, and the ref is gone; ref at another SHA → `moved` with that SHA, nothing deleted; an open PR with `base=<branch>` → `based_on` with its number, nothing deleted; missing ref → `gone`; failed ref read or PR list → exit 3, nothing deleted; DELETE refused → `kept` with GitHub's message, exit 1. Verify that they fail.
- [ ] 4.2 Implement `cmd_delete_remote` (paginated `gh_list` for `pulls?state=open&base=<branch>`), register it and document it in the header. Verify: the 4.1 tests and the whole `evals/pr-pair` suite pass; flip the rows green.

## 5. `specwright-pr` skill text: watch merge and cleanup

- [ ] 5.1 Write the failing `evals/pr-pair/test_skill_text.py` tests:
  - watch step 3 merges only with `pr.merge: agent` (the `merge` from `context`), and only when `merge_ready` holds;
  - in agent mode, Archive before merge runs without the question, and an archive failure stops with no merge;
  - after a reviewer-less archive watch, the merge runs only when the ready head is the archive head; any other head re-runs `archive-only` or returns to watching with reviewers;
  - the merge is `[as] bash scripts/pr-pair.sh merge ... --head <ready head>`: `merged` → Cleanup after merge, `head_changed` → watch again (repo-local), any other refusal → stop with GitHub's message, exit 3 → unknown with no deletion;
  - store-backed merges run only on `pair-state` `ready`, store then code, and a non-`merged` code result reports `planning merged, code pending` and cleans up the store only;
  - branch kinds: `<prefix>/<change-name>`, `docs/project-baseline`, `docs/close-*` merge; others are reported;
  - Cleanup after merge runs `delete-remote` only in agent mode with `delete_branch`, after the pull succeeded, and a failed pull deletes nothing;
  - the Never list keeps "merge" except for this path and names admin rights, auto-merge, merge queues, another method and review dismissal;
  - the merge report repeats the share-by-hand store reminder (review S4).

  Verify that they fail.
- [ ] 5.2 Update `skills/specwright-pr/SKILL.md`: the settings block (`pr.merge`, `pr.merge_method`, `pr.delete_branch`), watch step 3 (`:131-138`), Cleanup after merge (`:141-146`), the Never list (`:150`), and the store-backed `cleanup` path. Verify: the 5.1 tests and the whole `evals/pr-pair` suite pass; flip the rows green.

## 6. `specwright-finish` skill text

- [ ] 6.1 Write the failing `evals/git-workflow/test_instructions.py` tests. The `pr` path with `pr.merge: agent`: when watch started the archive, it hands back to watch (review S1); otherwise it starts watch with the run login and does not print `Ready to merge on GitHub`, and a failed ship starts no watch. "Never merge the PR" is scoped to `pr.merge: user`. **After the PR is merged** runs `delete-remote` after the pull and branch-check, only in agent mode with `delete_branch` (review S2, the repo-local resume path). `## local` does not read `pr.merge`. Verify that they fail.
- [ ] 6.2 Update `skills/specwright-finish/SKILL.md` (`:78-83`). Verify: the 6.1 tests and the whole `evals/git-workflow` suite pass; flip the rows green.

## 7. Graded agent evals (the M2 exit criterion)

- [ ] 7.1 Add the fixtures and `evals.json` entries:
  - `eval-watch-agent-merge`: repo-local, `finish: pr`, `pr.merge: agent`, `pr.merge_method: squash`, a required reviewer that has reported, an archived change whose PR #7 is ready in the fake `gh`. Assertions: exactly one merge PUT with `squash` and the ready head; the PR is MERGED; on main, which has the merge; the local branch is deleted; the remote ref is deleted; next/close is offered.
  - `eval-watch-merge-default-user`: the same fixture without `pr.merge`. Assertions: no merge PUT and no ref DELETE in the gh log; still on the branch; the report says ready.

  Add the `grade.py` checks the assertions need. Verify: `python -m unittest discover evals/git-workflow` passes, including `test_fixtures_shim` and `test_grade`.
- [ ] 7.2 Run both evals through the git-workflow runner and grade them with `python evals/git-workflow/grade.py <iteration-dir>`. Verify: both pass every assertion; flip the graded rows green. Record the run in the PR description as the exit-criterion evidence.

## 8. Settings template, docs and release 0.4.0

- [ ] 8.1 Add `merge: user`, `merge_method: merge` and `delete_branch: true` under `pr:` in `templates/openspec/specwright.yaml`, with comments: agent mode needs a required reviewer; GitHub records the run login as the merger; agent mode archives without asking; remote branches are deleted only at the merged head. Add the same keys and the 0.4.0 notes to the README settings block. Verify: the install-update eval and `test_instructions.py` pass.
- [ ] 8.2 Bump `VERSION`, the README badge and every `skills/*/SKILL.md` `metadata.version` to 0.4.0. Verify: `cat VERSION` prints `0.4.0`, and `grep -L "version: 0.4.0" skills/*/SKILL.md` lists nothing.

## 9. Integration

- [ ] 9.1 Run every eval suite (`python -m unittest discover evals/pr-pair`, `evals/git-workflow`, `evals/review-routes`), `openspec validate --all --strict` and `openspec schema validate specwright`. Verify: all pass, and every test-map row is green.

## Workflow follow-up

- Archive with `/opsx:archive`, then `specwright-finish` (pr mode: ship, watch; this repo keeps `pr.merge: user` until the dogfood trial).
- The PR closes #15.
- The user-verified exit criterion (one dogfood change from ship to merge with agent merge) runs in mythspine or blackgrid after 0.4.0 is installed, before `specwright-roadmap close` for M2.
- At M2 close, the strategy line (`openspec/strategy.md:14`) on merges is reworded for the opt-in agent merge (the roadmap owns that file).
