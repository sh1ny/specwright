# Tasks

## Test map

Script behaviour is tested at the real boundary: the scripts run through `bash` against real git repositories and the fake `gh` (`evals/fakes/gh.py`). That covers `pr-pair.sh` in `evals/pr-pair/test_pr_pair.py`, and `pr-snapshot.sh` and `pr-reply.sh` in the new `evals/pr-pair/test_pr_snapshot.py` and `evals/pr-pair/test_pr_reply.py`. The fake hands every non-trivial `--jq` filter to an external evaluator. The new tests use `gojq` (what real `gh --jq` runs) when it is installed, otherwise `jq`, and the module reports which one ran (review S4). Skill-text rules are checked by position and key terms in `evals/pr-pair/test_skill_text.py`.

| Requirement | Scenario | Test file | Test name | State |
|---|---|---|---|---|
| pr-evidence → Reviewer reports count only for the current head | Push time known | evals/pr-pair/test_pr_snapshot.py | test_snapshot_cutoff_uses_push_time | green |
| pr-evidence → Reviewer reports count only for the current head | Previous-head report with push activity missing | evals/pr-pair/test_pr_snapshot.py | test_snapshot_rejects_previous_head_reports_without_push_activity | green |
| pr-evidence → Reviewer reports count only for the current head | Report after the head was first seen | evals/pr-pair/test_pr_snapshot.py | test_snapshot_counts_report_after_first_seen | green |
| pr-evidence → Reviewer reports count only for the current head | First-seen time survives a new process | evals/pr-pair/test_pr_snapshot.py | test_snapshot_first_seen_persists_across_processes | green |
| pr-evidence → Reviewer reports count only for the current head | First-seen record cannot be written | evals/pr-pair/test_pr_snapshot.py | test_snapshot_first_seen_unsaved_keeps_process_time | green |
| pr-evidence → Reviewer reports count only for the current head | Waiting with an unwritable state directory | evals/pr-pair/test_pr_snapshot.py | test_wait_unwritable_state_reports_and_times_out | green |
| pr-evidence → Reviewer reports count only for the current head | Commit-precise reviewers | evals/pr-pair/test_pr_snapshot.py | test_snapshot_codex_sha_counts_without_push_activity | green |
| pr-evidence → A reply is posted only for the revision that was judged | Item unchanged | evals/pr-pair/test_pr_reply.py | test_reply_with_matching_rev_posts_and_resolves | green |
| pr-evidence → A reply is posted only for the revision that was judged | Reviewer edited the finding during the fix | evals/pr-pair/test_pr_reply.py | test_reply_refuses_a_changed_rev | green |
| pr-evidence → A reply is posted only for the revision that was judged | Item cannot be read | evals/pr-pair/test_pr_reply.py | test_reply_exits_3_when_the_item_is_unreadable | green |
| pr-evidence → A reply is posted only for the revision that was judged | Reply from an older session | evals/pr-pair/test_pr_reply.py | test_reply_without_rev_posts_as_before | green |
| pr-evidence → Handled markers are bound to a revision | Edit lands between the re-read and the reply | evals/pr-pair/test_pr_snapshot.py | test_snapshot_relists_comment_edited_before_bound_reply | green |
| pr-evidence → Handled markers are bound to a revision | Thread edited before a resolving reply | evals/pr-pair/test_pr_snapshot.py; evals/pr-pair/test_skill_text.py | test_snapshot_relists_resolved_thread_as_rebound; test_feedback_judges_rebound_threads | green |
| pr-evidence → Handled markers are bound to a revision | Answered item stays answered | evals/pr-pair/test_pr_snapshot.py | test_snapshot_bound_reply_keeps_items_answered | green |
| pr-evidence → Handled markers are bound to a revision | Marker from 0.1.10 | evals/pr-pair/test_pr_snapshot.py | test_snapshot_legacy_marker_uses_the_time_rule | green |
| pr-evidence → Clipped bodies are marked | Long review | evals/pr-pair/test_pr_snapshot.py | test_snapshot_marks_a_clipped_review | red |
| pr-evidence → Clipped bodies are marked | Body at the limit | evals/pr-pair/test_pr_snapshot.py | test_snapshot_body_at_the_limit_is_not_clipped | red |
| pr-evidence → Clipped items are read in full before they are judged | Finding after the cut | evals/pr-pair/test_pr_snapshot.py; evals/pr-pair/test_skill_text.py | test_full_prints_the_unclipped_body; test_feedback_reads_clipped_items_in_full | red |
| pr-evidence → Clipped items are read in full before they are judged | Full body cannot be read | evals/pr-pair/test_skill_text.py | test_feedback_hands_over_an_unreadable_clipped_item | red |
| pr-evidence → Clipped items are read in full before they are judged | Unknown item id | evals/pr-pair/test_pr_snapshot.py | test_full_unknown_id_is_not_found | red |
| pr-watch → The newest watcher owns a PR | Newer watcher takes over | evals/pr-pair/test_pr_snapshot.py | test_watch_newer_watcher_takes_over | green |
| pr-watch → The newest watcher owns a PR | Cleanup interleaved with a takeover | evals/pr-pair/test_pr_snapshot.py | test_watch_exit_leaves_a_newer_claim | green |
| pr-watch → The newest watcher owns a PR | Two watchers claim at once | evals/pr-pair/test_pr_snapshot.py | test_watch_simultaneous_claims_leave_one_owner | green |
| pr-watch → The newest watcher owns a PR | Owner crashed | evals/pr-pair/test_pr_snapshot.py | test_watch_claim_beats_a_crashed_owner | green |
| pr-watch → Watch keys are unique per repository and PR | Hyphenated owners and names | evals/pr-pair/test_pr_snapshot.py | test_watch_keys_do_not_alias_hyphenated_identities | green |
| pr-watch → Watch keys are unique per repository and PR | Same PR spelled with different case | evals/pr-pair/test_pr_snapshot.py | test_watch_key_ignores_case | green |
| pr-watch → Watch keys are unique per repository and PR | State directory cannot be created | evals/pr-pair/test_pr_snapshot.py | test_watch_without_a_state_dir_polls_unowned | green |
| planning-stores → Commands run where they resolve correctly | Store push with a repository-local auth header | evals/pr-pair/test_as_sh.py | test_scrubs_header_local_to_the_store | green |
| planning-stores → Commands run where they resolve correctly | Store login override | evals/pr-pair/test_pr_pair.py | test_context_login_per_repo | green |
| planning-stores → Commands run where they resolve correctly | Schema lookup with a root nested in the store repo | evals/git-workflow/evals.json | eval-install-nested-store | green |
| planning-stores → Commands run where they resolve correctly | Private store readable only by the store login | evals/pr-pair/test_pr_pair.py | test_rounds_and_pass_plan_read_a_private_store_remote_as_the_store_login | green |
| planning-stores → Commands run where they resolve correctly | Store login has no credential | evals/pr-pair/test_pr_pair.py | test_store_git_reads_stop_without_a_store_credential | green |
| planning-stores → Watch covers the expected PR set | Code PR green, store PR waiting | evals/pr-pair/test_pr_pair.py | test_pair_state_waits_for_both | green |
| planning-stores → Watch covers the expected PR set | Store PR alone is ready | evals/pr-pair/test_pr_pair.py | test_pair_state_single_store_pr_ready | green |
| planning-stores → Watch covers the expected PR set | One PR of the pair merged | evals/pr-pair/test_pr_pair.py | test_pair_state_split_hands_off | green |
| planning-stores → Watch covers the expected PR set | Archive before merge with no store PR | evals/git-workflow/evals.json | eval-store-archive-before-merge-local-store | green |
| planning-stores → Watch covers the expected PR set | Store snapshot of an old head | evals/pr-pair/test_pr_pair.py; evals/pr-pair/test_skill_text.py | test_pair_state_refreshes_an_old_head_snapshot; test_watch_refreshes_on_a_refresh_blocker | green |
| planning-stores → Watch covers the expected PR set | Snapshot of another PR | evals/pr-pair/test_pr_pair.py; evals/pr-pair/test_skill_text.py | test_pair_state_refreshes_a_snapshot_of_another_pr; test_watch_moves_its_wait_to_the_replaced_pr | green |
| planning-stores → Watch covers the expected PR set | Snapshot without a head | evals/pr-pair/test_pr_pair.py | test_pair_state_refreshes_a_snapshot_without_a_head | green |

## 1. Test harness for the snapshot and reply scripts

- [x] 1.1 Extend the fake `gh` (`evals/fakes/gh.py`) and document each new form in its docstring:
  - **PR snapshot GraphQL query:** a query containing `reviewThreads(` returns `data.viewer` and `data.repository.pullRequest` from per-PR state: threads with comments (`databaseId`, author, body, `createdAt`, `lastEditedAt`, `isResolved`), PR comments, reviews, check contexts, `headRefOid`/`headRefName`/`headRepository`, `commits.committedDate`. `GH_TOKEN` picks the viewer. The shipped `--jq` filter runs unchanged.
  - **`api -i rate_limit`:** a `Date:` header from a fake clock (`st["clock"]`, RFC 1123), which tests advance.
  - **`node(id)` reads:** a thread's comments; an IssueComment or PullRequestReview; a PullRequestReviewComment. Unknown ids → `node: null`.
  - **Writes:** the REST reply POST `repos/<o>/<n>/pulls/<pr>/comments/<id>/replies`; `pr comment --body-file`; the `resolveReviewThread` and `addReaction` mutations. Each is appended to the PR state with the clock's time and the token's viewer.

  Verify with new cases in `evals/pr-pair/test_fake_gh.py` (each form returns the documented shape; an unknown node returns null) and `python -m unittest evals.pr-pair.test_fake_gh`.
- [x] 1.2 Add the shared fixture module for the new tests:
  - pick `gojq` when on `PATH`, else `jq`, and expose which one in the test output;
  - run `pr-snapshot.sh` and `pr-reply.sh` with `SPECWRIGHT_STATE_DIR` in a temp directory;
  - helpers to add threads, comments, reviews and edits at a clock time.

  Verify with a smoke test that snapshots an empty PR and parses its JSON.

## 2. Pair readiness bound to the discovered PR and head (#31, D1)

- [x] 2.1 Write the failing tests (rows "Store snapshot of an old head", "Snapshot of another PR", "Snapshot without a head"):
  - `pair-state` returns `action: wait`, `refresh: ["store"]` and a `refresh:head:<a7>!=<b7>` blocker for a ready snapshot of an old head;
  - a `refresh:pr:7!=9` blocker for a snapshot of another PR;
  - a `refresh` blocker for a snapshot with no `head_oid` or `number`.

  Verify that they fail because `pair-state` reports `ready`.
- [x] 2.2 Update the `snap()` helper in `evals/pr-pair/test_pr_pair.py` to take the PR's `number`, `url` and `head_oid` from the fake PR state. Verify that the green rows `test_pair_state_waits_for_both`, `test_pair_state_single_store_pr_ready` and `test_pair_state_split_hands_off` still pass.
- [x] 2.3 Implement the binding in `cmd_pair_state` (`pr-pair.sh`): compare each snapshot's `url` (owner/name, number) and `head_oid` with the discovered PR's `url`, `number` and `head_sha`. Add the `refresh:*` blockers and `refresh: [<side>]`, and never report ready on a mismatch. Verify that the 2.1 tests pass, and flip their `pr-pair` rows green.
- [x] 2.4 Write the failing skill-text tests `test_watch_refreshes_on_a_refresh_blocker` and `test_watch_moves_its_wait_to_the_replaced_pr`. Then edit SKILL.md watch step 2 (store-backed) with the D1 rules:
  - `refresh:head` → a one-off snapshot of the same PR;
  - `refresh:pr` → stop that side's wait, snapshot the PR in `prs.<side>`, and restart the wait on that number;
  - still mismatched → back to waiting.

  Verify that the tests pass, and flip the rows green.

## 3. Reviewer cutoff when push activity is missing (#31, D2)

- [x] 3.1 Write the failing tests for the seven "Reviewer reports count only for the current head" rows. Model the sequences on the fake clock: commit(B) 09:00, report(A) 10:00, push(B) 11:00 absent from activity, first snapshot 12:00. Use Mira (`kintsugimira`) and a required generic reviewer. The `--wait` case uses `--interval 1` and advances the clock between polls, with the state directory replaced by a regular file so it cannot be created. Verify that they fail for the expected reason: the commit-date cutoff marks A's report `reported`.
- [x] 3.2 Implement D2 in `prepare_cfg` (`pr-snapshot.sh`):
  - **Record:** `<state>/heads/<owner>/<name>/<pr>/<oid>`, lower case, written to a temp file and published by a no-clobber hard link. Remove the temp file. Remove the sibling heads of the same PR once the record is published.
  - **Read:** a later process reads the record. An unreadable or unparseable record falls back to the in-process first-seen time, kept across polls.
  - **Cutoff:** `since` = push time, else first-seen. Never the commit date.
  - **Output:** `head_cutoff: {source, at}`.

  Verify that the 3.1 tests pass, and flip the rows green.
- [x] 3.3 Update `openspec/architecture.md`: the "Reviewer report cutoff" resource row, and a State ownership row for the first-seen record. Verify with `grep -n "first-seen" openspec/architecture.md`.

## 4. Replies bound to the revision they answer (#33, D3)

- [x] 4.1 Write the failing `pr-reply.sh` tests for the four "A reply is posted only for the revision that was judged" rows:
  - matching `--rev` → posts and resolves, exit 0;
  - changed `--rev` → exit 5 with nothing posted, resolved or reacted;
  - unreadable item (fake `fail` pattern on the node read) → exit 3 with nothing posted;
  - no `--rev` → as before, with no node read in `$FAKE_GH_LOG`.

  Verify that they fail because `--rev` is unknown.
- [x] 4.2 Implement `--rev` in `pr-reply.sh` for `thread`, `comment` and `resolve`:
  - re-read through `node(id)` and compute the revision with the snapshot's formula;
  - exit 5 naming both revisions, or exit 3 on a read failure;
  - add `rev=<rev>` to the `handled` and `waiting` markers, after `resolve`;
  - update the usage header.

  Verify that the 4.1 tests pass, plus one test that the `rev` from a real snapshot is accepted unchanged. Flip the rows green.
- [x] 4.3 Write the failing snapshot tests for the four "Handled markers are bound to a revision" rows:
  - a PR comment edited before a bound reply is listed again;
  - a resolved thread edited before a bound `--resolve` reply is listed with `rebound: true` and `awaiting_reviewer: false`;
  - a bound reply with no later activity keeps the item answered;
  - a marker without `rev=` follows the time rule.

  Verify that they fail.
- [x] 4.4 Implement the snapshot marker rules in `pr-snapshot.sh`:
  - **Parsing:** `marks()` reads an optional `rev=`.
  - **PR comments and reviews:** with any `rev=` marker for the item, it is handled only while one equals its `rev`; otherwise the time rule applies.
  - **Threads:** `$rebound` compares the latest marker reply's `rev` with the revision over the comments whose `databaseId` is lower than the reply's. The `select` includes `$rebound`. Output `rebound`, and add it to `sig`.
  - **`waiting` markers** get the same rules.
  - **Mixed versions:** the duplicate-reply edge (review S1) is fail-safe and goes in the script comment.

  Verify that the 4.3 tests pass and `test_pr_reply.py` still passes, and flip the rows green.
- [x] 4.5 Edit SKILL.md feedback with failing skill-text tests first (`test_feedback_judges_rebound_threads`, plus a test that step 8 passes `--rev`):
  - **Step 8:** pass `--rev <the item's snapshot rev>` on every `pr-reply.sh thread|comment|resolve` call. Exit 5 → take fresh snapshots and judge the item again. Exit 3 → stop and report.
  - **Step 2 resume:** reply rows pass the finding's recorded `revision.rev`.
  - **Step 4:** the `rebound` rule worded as in design D3.
  - `--rev` never takes a value from `--full` (review S2).

  Verify with `python -m unittest evals.pr-pair.test_skill_text`, and flip the rows green.
- [x] 4.6 Update `openspec/architecture.md`: the PR markers row of State ownership (`rev=` suffix, binding rule; the #33 gap is resolved). Verify by reading the row.

## 5. Store git transport under the store login (#35, D4)

- [x] 5.1 Write the failing tests:
  - **Private store remote:** put a `git` shim first on `PATH`. For `ls-remote`/`fetch` against the store's GitHub URL, it asks `git credential fill` for `github.com` over HTTPS and fails with `Authentication failed` unless the password is the store login's token. Otherwise it forwards to the real git, mapping the URL to a local bare repository. `rounds` must report the store fix commit as pushed, and `pass plan` must report its `push` row `done`, with no `remote_unreadable`.
  - **Missing credential:** without a credential for `planning_store.login`, both `rounds` and `pass plan` exit 3 with `no_credential`, and the shim log shows no store network call.

  Verify that they fail with `remote_unreadable`.
- [x] 5.2 Implement D4 in `pr-pair.sh`:
  - the wrapper exports an absolute `PR_PAIR_DIR` (`pwd -P`, plus `cygpath -m` where available);
  - `git_net(d, *args)` maps `identity(d)` through `REPO_LOGIN`, calls `token_for` first, then runs `bash $PR_PAIR_DIR/as.sh <login> git ...` with `cwd=d`, or plain `git` when the repo is unmapped;
  - `remote_contains` uses `git_net`;
  - `cmd_rounds` with `--store` resolves the store slug and calls `read_store_as`, and resolves the store token before its `except Stop` loop, so a missing credential exits 3 instead of turning into `remote_unreadable`.

  Verify that the 5.1 tests pass and the whole `test_pr_pair.py` passes, and flip the rows green.
- [x] 5.3 Update `openspec/architecture.md`: the GitHub identity paragraph of Boundaries and contracts (store git calls now use the store login; #35 resolved). Verify by reading it.

## 6. Watch ownership by numbered claims (#39, D5)

- [x] 6.1 Write the failing tests for the seven pr-watch rows, using `--wait --interval 1` with short timeouts against the fake `gh`:
  - **Takeover:** A exits 4 when B starts.
  - **Exit after a takeover:** while A waits, a higher claim file is placed in the key directory. A exits at its timeout, and the higher claim is still present, so a watcher holding it keeps polling.
  - **Simultaneous claims:** two start together; exactly one exits 4.
  - **Crashed owner:** a pre-placed stale claim is beaten by a new watcher.
  - **Keys:** `acme-tools/widget#5` and `acme/tools-widget#5` both keep polling. `Acme/Widget#5` loses to a newer `acme/widget#5`.
  - **Unwritable state directory:** the watcher polls and prints the ownership-off notice on stderr.

  Verify that they fail against the current token file. Use no signals, so the tests also run on Windows.
- [x] 6.2 Implement D5 in `pr-snapshot.sh`:
  - key directory `<state>/watch/v2/<owner>/<name>/<pr>/` in lower case;
  - claim `n+1` with `set -C` (retry the next number on a collision), then remove lower claims;
  - `still_owner` = own file exists and none higher;
  - release removes the own file only;
  - stderr notice when the directory cannot be created;
  - update the header comment.

  Verify that the 6.1 tests pass, and flip the rows green.
- [ ] 6.3 Update `openspec/architecture.md`: the Watch ownership row of State ownership (claim directory, both #39 gaps resolved) and the Watch polling row of Resource bounds. Verify by reading them.

## 7. Clipped bodies flagged and read in full (#47, D6)

- [ ] 7.1 Write the failing snapshot tests:
  - a 5000-character review → `clipped: true`;
  - a 1200-character PR comment → whole body with `clipped: false`;
  - `--full <id>` prints `{"ok":true,"id","kind","body","rev","url"}` with the raw body, for a review, a PR comment and a thread comment;
  - an unknown id prints `not_found` and exits 1.

  Verify that they fail.
- [ ] 7.2 Implement `clipped` on thread comments, PR comments and reviews, and `--full <node id> [--repo]` in `pr-snapshot.sh`. A GitHub read failure exits 3. Update the usage header. Verify that the 7.1 tests pass, and flip the rows green.
- [ ] 7.3 Edit SKILL.md feedback step 1 with failing skill-text tests first (`test_feedback_reads_clipped_items_in_full`, `test_feedback_hands_over_an_unreadable_clipped_item`):
  - read every `clipped: true` item with `--full` before step 5 judges it;
  - a failed read → the item is reported as needing a manual read, neither dropped nor answered.

  Verify that the tests pass, and flip the rows green.
- [ ] 7.4 Update `openspec/architecture.md`: the "PR snapshot bodies" resource row (#47 resolved). Verify by reading it.

## 8. Release 0.1.11

- [ ] 8.1 Bump to 0.1.11:
  - `VERSION`;
  - the README badge;
  - `metadata.version` in all six `skills/*/SKILL.md`.

  Verify with `grep -rn "0\.1\.10" VERSION README.md skills/*/SKILL.md`, which must print nothing.
- [ ] 8.2 Check the README against the behaviour changes (CONTRIBUTING "README follows behaviour"). Wherever it describes `pr-reply.sh`, snapshot fields or watch ownership, update it. Verify by naming the sections checked in the commit body.

## 9. Integration checks

- [ ] 9.1 Run `python -m unittest discover evals/pr-pair` and `python -m unittest discover evals/git-workflow`. Both must pass, with the jq evaluator used reported. Every Test map row must be green.
- [ ] 9.2 Run `openspec validate fix-pr-evidence-freshness --strict` and `openspec schema validate specwright`. Both must pass.

## Workflow follow-up

- Re-install Specwright into this repo (README install prompt) after merge, so the session's installed `specwright-pr` copies run the 0.1.11 scripts.
- During this change's own PR watch, exercise the changed paths against the real PR, as CONTRIBUTING asks for PR scripts: a snapshot with `--reviewer`, a reply with `--rev`, and `--full` on a review. Report the results in the PR.
- After merge, cleanup's issues-left-open backstop checks that #31, #33, #35, #39 and #47 closed. Then this is the last change of M1: offer `/specwright-roadmap close`.
