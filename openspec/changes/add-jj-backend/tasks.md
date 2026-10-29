# Tasks

## Test map

**How the tests run.**
- Script behaviour is tested in a new `evals/vcs` suite against real jj (0.46+). It uses scratch colocated repos under a short temp root, a local bare remote and the existing fake `gh`.
- Each test needing jj goes through one helper, `evals/vcs/jjenv.py`, which skips with `jj not installed` unless `SPECWRIGHT_REQUIRE_JJ=1` (eval-runner).
- Git calls that Specwright makes are logged by a `git` shim, `evals/vcs/gitlog.py`; jj's own Git child process bypasses it through `git.executable-path`.
- Skill rules are verified through executed commands and resulting repository state, not source-text assertions. Before removing an affected prose-pinning assertion, task 6.1 inventories its invariant and names the script behavior test or live-agent eval that covers it.
- Existing predicates in `evals/git-workflow/grade.py` and existing `test_grade.py` cases remain unchanged. Additive graders and fixtures may cover ordering invariants that have no existing behavioral coverage. Running the offline unittest suite is not evidence that a live-agent eval ran.
- Git compatibility cases preserve each call site's operation argv and inherited `GIT_TRACE`. Trace comparisons permit mandatory read-only probe/settings commands, but preserve operation order, branch guards and every write; no unexpected write is filtered out.
- Tasks 1-5 add and verify the backend before task 6.2 cuts the skill instructions over. Ask the user before each heavy live-agent eval run; a run awaiting approval remains incomplete.
- Test-map rows prefixed `Supplementary:` refine coverage of an existing requirement; they do not claim additional `#### Scenario:` blocks in the spec.

| Requirement | Scenario | Test file | Test name | State |
|---|---|---|---|---|
| vcs-backends → The backend is chosen per repo | Unset means Git | evals/vcs/test_settings.py | `test_unset_vcs_is_git` | green |
| vcs-backends → The backend is chosen per repo | Store keeps its own backend | evals/vcs/test_settings.py | `test_store_vcs_not_inherited` | green |
| vcs-backends → The backend is chosen per repo | Unknown value | evals/vcs/test_settings.py | `test_unknown_vcs_stops` | green |
| vcs-backends → The jj backend is probed before the branch is read | Colocated jj repo | evals/vcs/test_probe.py | `test_probe_colocated_passes` | green |
| vcs-backends → The jj backend is probed before the branch is read | jj not installed | evals/vcs/test_probe.py | `test_probe_tool_missing` | green |
| vcs-backends → The jj backend is probed before the branch is read | jj too old | evals/vcs/test_probe.py | `test_probe_tool_too_old` (version stub on PATH) | green |
| vcs-backends → The jj backend is probed before the branch is read | Not a jj repo | evals/vcs/test_probe.py | `test_probe_not_managed_runs_no_init` | green |
| vcs-backends → The jj backend is probed before the branch is read | Secondary jj workspace | evals/vcs/test_probe.py | `test_probe_secondary_workspace_not_colocated` | green |
| vcs-backends → A jj repo on the Git backend is reported, not blocked | Leftover jj metadata | evals/vcs/test_state.py, evals/git-workflow/evals.json, evals/git-workflow/grade.py | `test_git_state_reports_jj_present`, `eval-branch-git-jj-note` (live gate note and Git-only trace) | red |
| vcs-backends → A jj repo on the Git backend is reported, not blocked | Git repo on Git | evals/vcs/test_state.py | `test_git_state_no_jj_note_runs_no_jj` | green |
| vcs-backends → The Git backend keeps today's commands | Git commit by name | evals/vcs/test_git_backend.py | `test_git_commit_commands_exact` | green |
| vcs-backends → The Git backend keeps today's commands | Git push | evals/vcs/test_git_backend.py | `test_git_push_command_exact_no_deadline` | green |
| vcs-backends → The Git backend keeps today's commands | Git commit with nothing to commit | evals/vcs/test_git_backend.py | `test_git_commit_nothing_fails_like_git` | green |
| vcs-backends → The Git backend keeps today's commands | Supplementary: call-site fetch forms | evals/vcs/test_git_backend.py | `test_git_fetch_call_site_forms` (quiet, no-tags, plain; exact argv and real trace) | green |
| vcs-backends → The Git backend keeps today's commands | Supplementary: call-site pull forms | evals/vcs/test_git_backend.py | `test_git_pull_call_site_forms` (cleanup and explicit roadmap remote/main) | green |
| vcs-backends → The Git backend keeps today's commands | Supplementary: branch, merge and delete forms | evals/vcs/test_git_backend.py | `test_git_branch_merge_delete_forms` (checkout, merge message file, safe and guarded force delete) | green |
| vcs-backends → The Git backend keeps today's commands | Supplementary: trace inheritance and operation parity | evals/vcs/test_git_backend.py | Existing call-site cases also compare raw Git with `vcs.sh` through the unedited `grade.git_trace` parser; no duplicate permanent cases | green |
| vcs-backends → On jj a change branch is a bookmark at the parent of the working copy | Git reads after a jj commit | evals/vcs/test_commit.py | `test_git_reads_see_bookmark_tip` | green |
| vcs-backends → On jj a change branch is a bookmark at the parent of the working copy | Working copy left with other edits | evals/vcs/test_commit.py | `test_unrelated_edit_stays_in_wc` | green |
| vcs-backends → On jj the current change branch is resolved from bookmarks | One bookmark | evals/vcs/test_state.py | `test_state_one_bookmark_beside_main` | green |
| vcs-backends → On jj the current change branch is resolved from bookmarks | Two bookmarks at the parent | evals/vcs/test_state.py | `test_state_two_bookmarks_ambiguous` | green |
| vcs-backends → On jj the current change branch is resolved from bookmarks | Neither main nor a bookmark | evals/vcs/test_state.py | `test_state_off_main_no_branch` | green |
| vcs-backends → Fetches for reading move no jj bookmark | Remote main ahead, main tracked | evals/vcs/test_fetch_pull.py | `test_fetch_main_tracked_moves_nothing` | green |
| vcs-backends → Fetches for reading move no jj bookmark | Local main diverged before a read | evals/vcs/test_fetch_pull.py | `test_fetch_main_diverged_no_conflict` | green |
| vcs-backends → Fetches for reading move no jj bookmark | Release publish on jj with main tracked | evals/release/test_release_jj.py | `test_publish_jj_base_by_name_no_bookmark_moves` | red |
| vcs-backends → The jj gate creates the bookmark from a clean main | Gate on jj | evals/vcs/test_branch.py | `test_branch_create_at_parent` | green |
| vcs-backends → The jj gate creates the bookmark from a clean main | Carry-over on Windows | evals/vcs/test_paths.py | `test_backslash_paths_normalised` (captured Windows output, every platform) | green |
| vcs-backends → The jj gate creates the bookmark from a clean main | Dirty working copy | evals/vcs/test_state.py, evals/git-workflow/evals.json, evals/git-workflow/grade.py | `test_state_dirty_lists_paths`, `eval-branch-jj-dirty-no-stash` (live stop and no stash write) | red |
| vcs-backends → Moving the working copy on jj carries uncommitted edits | Switch with carry-over | evals/vcs/test_switch.py | `test_switch_carries_added_files` | green |
| vcs-backends → Moving the working copy on jj carries uncommitted edits | Carry conflicts | evals/vcs/test_switch.py | `test_switch_carry_conflict_rolls_back` | green |
| vcs-backends → On jj a commit takes only its named paths | Group commit on jj | evals/vcs/test_commit.py | `test_commit_named_paths_only` | green |
| vcs-backends → On jj a commit takes only its named paths | Nothing to commit | evals/vcs/test_commit.py | `test_commit_nothing_no_empty_commit` | green |
| vcs-backends → On jj a commit takes only its named paths | Named file jj did not snapshot | evals/vcs/test_commit.py | `test_commit_oversize_file_path_not_tracked` | green |
| vcs-backends → On jj a commit takes only its named paths | Message trailers kept | evals/vcs/test_commit.py | `test_git_reads_see_bookmark_tip` (also verifies complete trailers through Git and `task-cover.sh`) | green |
| vcs-backends → An interrupted jj commit is resumed without loss | Bookmark left behind by an interruption | evals/vcs/test_advance.py | `test_advance_own_scope_moves` | green |
| vcs-backends → An interrupted jj commit is resumed without loss | Someone else's commit | evals/vcs/test_advance.py | `test_advance_foreign_commit_stops` | green |
| vcs-backends → An interrupted jj commit is resumed without loss | More than 50 commits | evals/vcs/test_advance.py | `test_advance_over_cap_stops` | green |
| vcs-backends → A jj local merge keeps the merge proof | Local merge on jj with leftover edits | evals/vcs/test_merge.py | `test_merge_first_parent_and_carry` | green |
| vcs-backends → A jj local merge keeps the merge proof | Conflicted merge | evals/vcs/test_merge.py | `test_merge_conflict_abandons` | green |
| vcs-backends → A jj local merge keeps the merge proof | Interrupted after the merge commit | evals/vcs/test_merge.py | `test_merge_rerun_reuses_commit` | green |
| vcs-backends → A jj branch is deleted only locally and only once merged | Cleanup after local merge | evals/vcs/test_delete.py | `test_delete_forgets_no_remote_deletion` | green |
| vcs-backends → A jj branch is deleted only locally and only once merged | Not merged | evals/vcs/test_delete.py | `test_delete_unmerged_stops` | green |
| vcs-backends → A jj push publishes only the change bookmark | Ship on jj | evals/vcs/test_push.py | `test_push_only_change_bookmark` | green |
| vcs-backends → A jj push publishes only the change bookmark | Conflicted commit | evals/vcs/test_push.py | `test_push_conflicted_stops` | green |
| vcs-backends → A jj push publishes only the change bookmark | Bookmark not at the parent | evals/vcs/test_push.py | `test_push_bookmark_not_parent_stops` | green |
| vcs-backends → The jj pull fetches only main and only fast-forwards | Cleanup pull on jj | evals/vcs/test_fetch_pull.py | `test_pull_fast_forward_tracked_and_untracked` | green |
| vcs-backends → The jj pull fetches only main and only fast-forwards | Remote head branch deleted at merge | evals/vcs/test_fetch_pull.py | `test_pull_keeps_bookmark_of_deleted_remote` | green |
| vcs-backends → The jj pull fetches only main and only fast-forwards | Local main diverged | evals/vcs/test_fetch_pull.py | `test_pull_diverged_stops_before_jj_fetch` | green |
| vcs-backends → The jj pull fetches only main and only fast-forwards | Local main ahead | evals/vcs/test_fetch_pull.py | `test_pull_local_ahead_succeeds_unmoved` | green |
| vcs-backends → The jj pull fetches only main and only fast-forwards | Remote moved again during the pull | evals/vcs/test_fetch_pull.py | `test_pull_conflicted_main_set_back` (origin moved by a hook between read and fetch) | green |
| vcs-backends → Release tags are the one Git write on jj | Publish on jj | evals/release/test_release_jj.py | `test_publish_jj_only_tag_writes` | red |
| vcs-backends → Release tags are the one Git write on jj | Tag at another commit | evals/release/test_release_jj.py | `test_publish_jj_tag_elsewhere_exit_1` | red |
| vcs-backends → No other Git write runs under jj | Full local flow on jj | evals/vcs/test_flows.py | `test_local_flow_no_git_writes` | red |
| vcs-backends → No other Git write runs under jj | Full PR flow on jj | evals/vcs/test_flows.py | `test_pr_flow_no_git_writes` | red |
| vcs-backends → Debug never stashes on jj | Dirty working copy during a reproduction | evals/git-workflow/evals.json, evals/git-workflow/grade.py | `eval-debug-jj-dirty-no-stash` (live changed-path report, question and no stash write) | red |
| vcs-backends → Debug never stashes on jj | Clean working copy | evals/git-workflow/evals.json, evals/git-workflow/grade.py | `eval-debug-jj-clean` (live reproduction proceeds without an unnecessary question) | red |
| vcs-backends → The archive undo plan uses jj on a jj repo | Undo plan on jj | evals/finish/test_undo_jj.py | `test_undo_plan_jj_commands_and_result` | red |
| vcs-backends → The archive undo plan uses jj on a jj repo | Archive committed on another branch | evals/finish/test_undo_jj.py | `test_undo_plan_jj_other_branch_moves_wc` | red |
| vcs-backends → The archive undo plan uses jj on a jj repo | Touched path already changed | evals/finish/test_undo_jj.py | `test_undo_plan_jj_guard_fails_first` | red |
| vcs-backends → The archive undo plan uses jj on a jj repo | Wrong branch | evals/finish/test_undo_jj.py | `test_undo_plan_jj_wrong_branch` | red |
| vcs-backends → A jj store passes the update's branch check | jj store on main | evals/update/test_update_jj_store.py | `test_jj_store_on_main_not_refused` | red |
| vcs-backends → A jj store passes the update's branch check | Git store with a detached HEAD | evals/update/test_update_jj_store.py | `test_git_store_detached_still_refused` | red |
| vcs-backends → A jj store passes the update's branch check | Script missing from the download | evals/update/test_update_jj_store.py | `test_jj_store_vcs_script_missing` | red |
| vcs-backends → Paired repos each use their own backend | jj code repo with a Git store | evals/vcs/test_pair.py | `test_pair_jj_code_git_store_branch` | red |
| vcs-backends → Paired repos each use their own backend | Store probe fails | evals/vcs/test_pair.py, evals/git-workflow/evals.json, evals/git-workflow/grade.py | `test_pair_store_probe_fails`, `eval-branch-store-probe-fails` (live no branch creation and lock released) | red |
| github-identity → jj network commands are fenced like git | Push on jj | evals/pr-pair/test_as_jj.py | `test_jj_push_uses_fenced_token` (fake credential helper answers only the fenced token) | green |
| github-identity → jj network commands are fenced like git | Repository option | evals/pr-pair/test_as_jj.py | `test_jj_repository_option_refused` | green |
| github-identity → jj network commands are fenced like git | Config override | evals/pr-pair/test_as_jj.py | `test_jj_config_option_refused` | green |
| github-identity → jj network commands are fenced like git | Other jj subcommand | evals/pr-pair/test_as_jj.py | `test_jj_other_subcommand_refused` | green |
| eval-runner → Suites that need jj run with a pinned jj in CI | CI run | evals/runner/test_ci_workflow.py | `test_workflow_installs_pinned_jj_and_requires_it` | green |
| eval-runner → Suites that need jj run with a pinned jj in CI | Checksum mismatch | evals/runner/test_ci_workflow.py | `test_workflow_checks_jj_sha256_before_use` | green |
| eval-runner → Suites that need jj run with a pinned jj in CI | Local run without jj | evals/runner/test_jjenv.py | `test_jj_missing_skips_with_reason` | green |
| eval-runner → Suites that need jj run with a pinned jj in CI | Required but missing | evals/runner/test_jjenv.py | `test_jj_missing_required_fails` | green |

## 1. Decision, settings and eval scaffolding

- [x] 1.1 Write `docs/adr/0017-version-control-writes-go-through-one-backend-script.md` (MADR-short, `Status: accepted`, today's date) covering design D1-D13's binding decisions:
  - `vcs.sh` as the writer seam, and the per-repo setting with no inference;
  - colocated jj only, with Git reads;
  - bookmark at `@-`, and carried moves;
  - `FETCH_HEAD`-only read fetches and main-only pulls;
  - the release-tag exception;
  - jj fenced through `as.sh` with no new deadline, outside ADR 0014's scope.

  Update `openspec/architecture.md`: add the ADR index row, a `vcs.sh` component row, `vcs`/`planning_store.vcs` under the formats parsed by later runs, and the `as.sh` jj fence in the GitHub identity paragraph. Verify with `grep -n 0017 openspec/architecture.md`.
- [x] 1.2 Add `evals/vcs/` with `jjenv.py` (find jj, `SPECWRIGHT_REQUIRE_JJ`, scratch colocated repos under a short temp root, tracked and untracked main, a bare remote) and `gitlog.py` (a `git` shim that logs Specwright's calls and classifies writes, with jj routed to the real git). Write `evals/runner/test_jjenv.py` first (rows: Local run without jj, Required but missing) and see it fail; then implement and see it pass. Flip both rows green.
- [x] 1.3 Add `JJ_VERSION` (0.46.0) and a pinned SHA-256 for the Linux x86_64 archive, a workflow step in `.github/workflows/evals.yml` that downloads, checks and puts jj on PATH and sets `SPECWRIGHT_REQUIRE_JJ=1`, and `evals/vcs/**`, `skills/specwright-pr/scripts/vcs.sh` → `vcs` rules in `evals/suites.json`. Write `evals/runner/test_ci_workflow.py` assertions first (rows: CI run, Checksum mismatch: checksum verified before the binary is used; a mismatch exits non-zero). Verify with `python evals/run.py runner` (map test included) and flip both rows green.
- [x] 1.4 Add `pr-pair.sh vcs --code <dir>`, which prints `{"ok":true,"code":…,"store":…}` or `unknown_vcs` (exit 1). Add `vcs` and `planning_store.vcs` to `templates/openspec/specwright.yaml` (commented, default git, store not inherited). Tests in `evals/vcs/test_settings.py` (rows: Unset means Git, Store keeps its own backend, Unknown value) go red, then green.

## 2. vcs.sh: probe, state and the Git backend

- [x] 2.1 Write failing tests:
  - `evals/vcs/test_probe.py`, the five probe rows. A `jj` stub printing `jj 0.45.1` covers too-old.
  - `evals/vcs/test_state.py`: One bookmark; Two bookmarks; Neither main nor a bookmark; Dirty working copy (`test_state_dirty_lists_paths`); jj present on Git; no jj note on Git.
  - `evals/vcs/test_paths.py`, on captured `\` output.

  Confirm each fails because `vcs.sh` is missing.
- [x] 2.2 Implement `skills/specwright-pr/scripts/vcs.sh` (bash with an embedded Python 3.8+ body, like `pr-pair.sh`):
  - **Contract:** one JSON document, exits 0/1/2/3, `--repo --role --code`.
  - **`probe`:** settings via `pr-pair.sh vcs`; jj version floor 0.46; `.jj/` and Git work tree at the same toplevel; `jj_present` on Git.
  - **`state [--scope]`:** the jj bookmark rule (one non-main local bookmark at `@-`; conflicted bookmark or multi-parent `@` → `ambiguous_branch`); on-main; clean; dirty paths normalised to `/`; `behind` (cap 50). Git: `branch --show-current` and `status --porcelain` as today.

  Verify the 2.1 tests pass and flip their rows green.
- [x] 2.3 Write `evals/vcs/test_git_backend.py` with the git shim asserting the exact operation argv and consumer-visible result for every form the skills use today. Cover named-path `git add -- <paths>` then `git commit -F <msgfile> -- <paths>` (including nothing to commit), `checkout -b`, switch, `merge --no-ff <branch> -F <msgfile>`, safe `branch -d`, guarded PR cleanup `branch -D`, and `push -u origin HEAD`. Cover all fetch forms (`-q origin <main>`, `--no-tags origin <main>`, `origin <main>`) and both pull forms (`--ff-only`, `--ff-only origin <main>`), selected by explicit backend options rather than normalization. See the tests fail, then implement the Git branches of `branch-create`, `switch`, `commit`, `merge`, `delete-branch`, `fetch-main`, `pull` and `push`. Network calls use `as.sh` only when origin's fetch URL is on github.com, with no new deadline. Verify the tests and `python evals/run.py --changed main`, then flip the script rows green.
- [x] 2.4 In the same real-operation cases from 2.3, run the raw Git baseline and `vcs.sh` with inherited `GIT_TRACE` and parse both using the unedited `grade.git_trace`. Verify the same operation/write argv and order, allowing the backend's required read-only probe/settings calls while preserving branch guards and rejecting every unexpected write. Do not add duplicate permanent cases for an already-covered path, weaken existing graders or claim an offline test proves a live-agent run. Flip the trace-parity row green.

## 3. jj writes: branch, switch, commit, advance

- [x] 3.1 Write failing tests:
  - `evals/vcs/test_branch.py` (Gate on jj);
  - `evals/vcs/test_switch.py` (Switch with carry-over, Carry conflicts);
  - `evals/vcs/test_commit.py`, all six rows. The over-size file uses jj's default `snapshot.max-new-file-size`.
- [x] 3.2 Implement the jj `branch-create`, `switch` (`jj new` when `@` is empty; otherwise `jj rebase -r @ -o`, with conflict roll-back → `carry_conflict`) and `commit`:
  - the bookmark check;
  - the `path_not_tracked` (`jj file list`) pre-check before `nothing_to_commit`, so a lone ignored or over-size named file reports the actual reason;
  - `root:"…"` filesets with escaping;
  - the `too_many_paths` argv check;
  - `jj commit -m`, then `jj bookmark set -r @-`, then verify that `git rev-parse HEAD` equals the bookmark.

  Verify the 3.1 tests pass and flip the rows green.
- [x] 3.3 Write `evals/vcs/test_advance.py` (Bookmark left behind, Someone else's commit, More than 50 commits), then implement `advance --scope` with the own-scope subject rule. Verify and flip the rows green.

## 4. jj merge, delete, fetch, pull, push and the fence

- [x] 4.1 Write `evals/vcs/test_merge.py` (three rows) and `evals/vcs/test_delete.py` (two rows). Then implement:
  - `merge`: find or create with `jj new --no-edit`; abandon on conflict; carry `@`; set main; rerun reuse;
  - `delete-branch`: `jj bookmark forget`, with the merged check unless `--force`.

  Verify and flip the rows green.
- [x] 4.2 Write `evals/vcs/test_fetch_pull.py` (the two read-fetch rows and the five pull rows; tracked repos from `jj git clone --colocate`, untracked from `jj git init --colocate`). Then implement:
  - `fetch-main`: `git fetch --refmap= origin refs/heads/<main>`, printing `ref`;
  - `pull`: read and classify, then `jj git fetch --branch <main>`, the untracked fast-forward, the conflict set-back and the carry.

  Verify and flip the rows green.
- [x] 4.3 Write `evals/pr-pair/test_as_jj.py` (four rows; the push row uses a fake credential helper that answers only the fenced token over an `insteadOf` remote). Then extend `as.sh`:
  - accept only `jj git push` and `jj git fetch`;
  - refuse `-R`, `--repository`, `--config` and `--config-file`, and any other jj subcommand (exit 3);
  - keep the remote, rewrite and transport checks.

  Verify and flip the rows green.
- [x] 4.4 Write `evals/vcs/test_push.py` (three rows), then implement the jj `push`: bookmark at `@-`, no conflicted or undescribed commit in `main..b`, `jj git push --remote origin --bookmark b` through `as.sh`. Verify and flip the rows green.

## 5. Scripts that read the branch or emit commands

- [ ] 5.1 Write `evals/finish/test_undo_jj.py` (four rows). Then change `finish.sh`:
  - it reads the branch through `../../specwright-pr/scripts/vcs.sh state` (exit 2 naming the path when missing);
  - on jj it emits D13's script: the guards, `jj new <b>` for another branch, the moves, `jj restore --from`, removals, `jj commit` and the bookmark set, plus the failure warning.

  Verify the rows go green, and that `python evals/run.py finish` keeps the Git tests green.
- [ ] 5.2 Change `pr-pair.sh`:
  - `cleanup-plan` asks `vcs.sh plan` for each repo's switch, pull and delete commands, and reads the branch through `vcs.sh state`;
  - `remote_contains` adds `--refmap=` on a jj repo.

  Add the cases `test_cleanup_plan_jj_commands` and `test_remote_contains_jj_moves_no_ref` to `evals/pr-pair`, and verify that `python evals/run.py pr-pair` passes.
- [ ] 5.3 Write `evals/update/test_update_jj_store.py` (three rows). Then change `update.sh store_busy_reason`: for a jj store, read the branch through the download's `skills/specwright-pr/scripts/vcs.sh state` and refuse with `vcs_script_missing` when it is absent. A Git store is unchanged. Verify and flip the rows green, and confirm `python evals/run.py update` passes.
- [ ] 5.4 Write `evals/release/test_release_jj.py` (Release publish on jj with main tracked; Publish on jj; Tag at another commit). Then add `release.sh --base <branch>`, which `merged_pulls` uses when given; the tag fetch names `refs/tags/<tag>` only. Verify the rows go green, and that `python evals/run.py release` keeps the existing tests green.

## 6. Skill prose routes through vcs.sh

- [ ] 6.1 Before deleting an affected prose-pinning assertion, add an inventory table below this task: assertion → consumer-visible invariant → script behavior test or named live-agent eval → verification result. Include affected assertions in `evals/git-workflow/test_instructions.py`, `evals/pr-pair/test_skill_text.py`, `evals/release/test_skill_text.py` and `evals/review-routes/test_skill_text.py`. Delete the obsolete source-text assertions, never re-pin them to `vcs.sh` wording:
  - Invariants now owned by scripts use real behavior tests: wrong-branch refusal, named-path commits, no empty jj commit, safe versus guarded force deletion, annotated release tags and tag-only push.
  - Agent-order invariants use live evals with command traces and resulting repo state: store lock held before branch creation and released afterwards; subject fitting before commit; status/guard before switch and pull. Name the existing eval for each; when none covers it, add only the missing fixture/eval and additive grader predicate, leaving existing `grade.py` predicates and `test_grade.py` cases untouched.
  - Include `test_instructions.py`'s exact branch/commit `allowed-tools` pin in the inventory. Its replacement verifies script-invocation preapproval in the actual harness permission path, not another source regex; absence of an `allowed-tools` field is not itself a restrictive allowlist.
  - Add live cases `eval-branch-git-jj-note`, `eval-branch-jj-dirty-no-stash`, `eval-branch-store-probe-fails`, `eval-debug-jj-dirty-no-stash` and `eval-debug-jj-clean`, with fake external services and isolated fixtures. They check observed notes/questions, executed commands, lock/branch state and absence of stash writes, not source spelling.
  - Confirm new script behavior checks fail before implementation where applicable. Live checks remain red until the individually approved post-cutover runs in 7.3; an unrun eval is never green. Inventory coverage must be complete before an assertion is removed.
- [ ] 6.2 Rewrite the write steps and branch reads to name `vcs.sh` subcommands. On jj, `fetch-main`'s `ref` replaces `origin/<main>`. Files:
  - `skills/specwright-branch/SKILL.md`: gate, jj note, no stash on jj, store pair;
  - `skills/specwright-commit/SKILL.md`: planning, task, group, amend and Reconcile commits; `advance --scope`;
  - `skills/specwright-finish/SKILL.md`: archive commit, local merge, deletes, pulls, resume reads;
  - `skills/specwright-pr/SKILL.md`: base fetch, push, fix-round commits, cleanup;
  - `skills/specwright-roadmap/SKILL.md`: status fetch, init/close branches, commits, merge;
  - `skills/specwright-review/SKILL.md`: pre-ship round commits;
  - `skills/specwright-release/SKILL.md`: publish fetch, `--base`, and the tag exception named;
  - `skills/specwright-debug/SKILL.md`: no stash on jj.

  Bump each touched skill's `version:`. Update branch and commit's `allowed-tools` grants to permit the new `bash .../vcs.sh` calls (`Bash(bash *)`, as finish already grants), preserving their existing Git/OpenSpec grants. Audit all eight cutover skills' explicit or inherited script permissions and keep invocation usable under normal permissions, without silently relying on permission bypass. Remove obsolete raw write instructions in the cutover, retaining only the annotated release-tag exception and read-only Git operations. Run the affected script and offline regression tests after the cutover; these do not stand in for live ordering/permission evidence. Leave Debug and gate live-eval rows red until 7.3 exercises them with approval.
- [ ] 6.3 Document `vcs` and `planning_store.vcs` in `README.md`: setup, colocated requirement, jj 0.46+, no conversion, the tag exception, and that the user's own jj skill is optional, never installed by Specwright. Verify with `python evals/run.py --changed main`.

## 7. End-to-end on jj, and the release

- [ ] 7.1 Write and pass `evals/vcs/test_pair.py` (jj code repo with a Git store; Store probe fails). It drives the gate's `vcs.sh` sequence with the store lock, as in `skills/specwright-branch/SKILL.md`. Flip its rows green.
- [ ] 7.2 Write and pass `evals/vcs/test_flows.py`, with the Git-write log asserting every call:
  - local flow: branch, two groups, archive, local finish, on tracked and untracked main;
  - PR flow: branch, ship, a merge on the fake GitHub that deletes the head branch, then cleanup.

  Flip the Full local flow and Full PR flow rows green. Record the `vcs` suite's wall time in `evals/timings.md`.
- [ ] 7.3 After the group-6 cutover, run the live-agent evals named by the 6.1 inventory, on `vcs: git` for Git compatibility/order and on jj for the jj gate/debug scenarios. Ask the user before each heavy live-agent run; record the exact approved command, eval IDs, outcome, trace and repository-state evidence in the inventory. Grade actual run artifacts, not synthetic stand-ins. A run awaiting approval or not passing remains incomplete. Flip live rows green only after their runs pass.
- [ ] 7.4 Run `python evals/run.py --changed main` and `openspec validate add-jj-backend --strict`. Confirm every test-map row is green and the 6.1 coverage inventory is complete. Existing selected suites must pass; existing `grade.py` predicates and `test_grade.py` cases stay unchanged, except additive graders for previously uncovered behavioral invariants. The only affected instruction-test removals are those justified in the 6.1 inventory.
- [ ] 7.5 Run `bash skills/specwright-release/scripts/release.sh bump --to 0.11.0` and rewrite the proposal's Release Notes summary to describe the whole release. Verify with `bash skills/specwright-release/scripts/release.sh check` and `bash skills/specwright-release/scripts/release.sh notes --proposal openspec/changes/add-jj-backend/proposal.md`.

## Workflow follow-up

- Pre-ship review, then ship to a PR (pr mode); CI runs every suite on Linux with the pinned jj.
- Archive after merge readiness; finish per `finish: pr`.
