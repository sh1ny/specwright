# Tasks

## Test map

Script behaviour is tested in `evals/review-routes/test_review_run.py` against fake `codex`/`claude`/`omp` executables on `PATH` (`evals/fakes/`). Skill and prompt text rules are checked in `evals/review-routes/test_skill_text.py` and `evals/git-workflow/test_instructions.py`, by position and key terms, in the style of `evals/pr-pair/test_skill_text.py`. Real-CLI behaviour is evidenced by the trial (group 2).

| Requirement | Scenario | Test file | Test name | State |
|---|---|---|---|---|
| review-routes → Routes tried in configured order | Claude Code with Codex installed | evals/review-routes/test_review_run.py | test_select_skips_runtime_takes_codex | red |
| review-routes → Routes tried in configured order | First route missing | evals/review-routes/test_review_run.py | test_select_missing_first_route_takes_omp | red |
| review-routes → Routes tried in configured order | No route available | evals/review-routes/test_review_run.py | test_select_none_available_is_subagent | red |
| review-routes → Routes tried in configured order | Cross-model reviews turned off | evals/review-routes/test_review_run.py | test_select_cross_model_false_no_probe | red |
| review-routes → Routes tried in configured order | Unknown route name | evals/review-routes/test_review_run.py | test_select_unknown_route_exits_1 | red |
| review-routes → OMP model unresolved makes OMP unavailable | Configured role exists | evals/review-routes/test_review_run.py | test_omp_role_passed_as_model | red |
| review-routes → OMP model unresolved makes OMP unavailable | Unknown role | evals/review-routes/test_review_run.py | test_omp_unknown_role_falls_to_next | red |
| review-routes → Reviewers run isolated and read-only | OMP review starts a fresh session | evals/review-routes/test_review_run.py | test_omp_fresh_session_dir_per_run | red |
| review-routes → Reviewers run isolated and read-only | Reviewer tries to write | evals/review-routes/test_review_run.py | test_command_lines_read_only_allowlists (argv); trial record `evals/review-routes/trial.md` (real CLIs, task 2.2) | red |
| review-routes → Review input built by Specwright | Route without a shell | evals/review-routes/test_review_run.py | test_prompt_embeds_code_and_store_diff | red |
| review-routes → Review input built by Specwright | Diff over the bound | evals/review-routes/test_review_run.py | test_diff_over_bound_stops_before_reviewer | red |
| review-routes → Output validated, fails closed | Valid findings | evals/review-routes/test_review_run.py | test_valid_findings_recorded | red |
| review-routes → Output validated, fails closed | Output that is not JSON | evals/review-routes/test_review_run.py | test_prose_output_invalid_no_fallthrough | red |
| review-routes → Output validated, fails closed | Subagent design review without a verdict | evals/review-routes/test_review_run.py | test_record_design_without_verdict_invalid | red |
| review-routes → Output validated, fails closed | Design review with two verdicts | evals/review-routes/test_review_run.py | test_design_two_verdicts_invalid_no_file | red |
| review-routes → Output validated, fails closed | Reviewer exceeds the deadline | evals/review-routes/test_review_run.py | test_timeout_kills_reviewer_exit_3 | red |
| review-routes → Every review records a receipt | OMP review receipt | evals/review-routes/test_review_run.py | test_receipt_omp_actual_model_from_session | red |
| review-routes → Every review records a receipt | Model not reported | evals/review-routes/test_review_run.py | test_receipt_unknown_actual_model | red |
| preship-review → Runs when every task is committed | Default settings | evals/review-routes/test_skill_text.py | test_commit_step3_runs_preship_before_handoff | red |
| preship-review → Runs when every task is committed | Opted out | evals/review-routes/test_skill_text.py | test_commit_step3_preship_false_skips | red |
| preship-review → Runs when every task is committed | Store-backed change | evals/review-routes/test_review_run.py | test_store_backed_record_names_both_heads | red |
| preship-review → Passing review recorded per head | Clean review | evals/review-routes/test_review_run.py | test_gate_pass_with_only_p2_p3 | red |
| preship-review → Passing review recorded per head | Blocking finding | evals/review-routes/test_review_run.py | test_gate_blocked_with_p1 | red |
| preship-review → Passing review recorded per head | Fix after a blocking finding | evals/review-routes/test_review_run.py | test_gate_missing_after_new_commit; evals/review-routes/test_skill_text.py test_fix_subject_and_preship_round_trailer | red |
| preship-review → Passing review recorded per head | Pre-ship fixes do not use up PR fix rounds | evals/pr-pair/test_pr_pair.py | test_rounds_ignore_preship_fix_commits | red |
| preship-review → Waiver only from the user | User waives a finding | evals/review-routes/test_review_run.py | test_waive_turns_blocked_into_pass | red |
| preship-review → Waiver only from the user | No answer | evals/review-routes/test_skill_text.py | test_waive_only_after_user_answer | green |
| preship-review → Ship and local merge require a pass | Ship with a pass on the head | evals/review-routes/test_skill_text.py | test_ship_gate_before_first_push | red |
| preship-review → Ship and local merge require a pass | Ship after an unreviewed commit | evals/review-routes/test_review_run.py | test_gate_missing_after_non_archive_commit | red |
| preship-review → Ship and local merge require a pass | Local merge after archive | evals/review-routes/test_review_run.py | test_gate_accepts_archive_commit_repo_local; evals/review-routes/test_skill_text.py test_finish_local_gate_before_merge | red |
| preship-review → Ship and local merge require a pass | Store-backed local merge after archive | evals/review-routes/test_review_run.py | test_gate_accepts_store_archive_commit | red |
| preship-review → Ship and local merge require a pass | PR already exists | evals/review-routes/test_skill_text.py | test_ship_gate_only_when_no_pr_in_change | red |
| preship-review → A failed review stops ship | Invalid output | evals/review-routes/test_skill_text.py | test_failed_review_stops_ship_and_merge | green |
| preship-review → Repeated blocking reviews escalate | Blocked after the second round | evals/review-routes/test_review_run.py | test_rounds_reads_preship_round_trailers; evals/review-routes/test_skill_text.py test_escalate_after_round_2 | red |
| preship-review → Repeated blocking reviews escalate | New session after two rounds | evals/review-routes/test_review_run.py | test_rounds_without_records_from_git | red |
| preship-review → Spec findings classed | Contradictory wording | evals/review-routes/test_skill_text.py | test_clarification_amend_commit_and_rereview | green |
| preship-review → Spec findings classed | Edit would change behaviour | evals/review-routes/test_skill_text.py | test_behaviour_change_asks_user | green |
| preship-review → Spec findings classed | Approved behaviour change | evals/review-routes/test_skill_text.py | test_behaviour_change_follows_drift_rule | green |
| install-update → Commented-out template keys optional | Project sets an optional key | evals/git-workflow/test_instructions.py | test_install_step6_commented_paths_optional | red |
| install-update → Commented-out template keys optional | Project lacks an optional key | evals/git-workflow/test_instructions.py | test_install_step6_never_adds_commented; test_install_step7_uncommented_only | red |
| install-update → Commented-out template keys optional | Reviewer entries are user data | evals/git-workflow/test_instructions.py | test_install_reviewer_entries_user_data | red |
| install-update → Commented-out template keys optional | Same name at two paths | evals/git-workflow/test_instructions.py | test_install_compares_dotted_paths | red |
| install-update → Commented-out template keys optional | Key really removed upstream | evals/git-workflow/test_instructions.py | test_install_step6_asks_before_removing (existing rule kept) | red |
| pr-watch → Archive head gets no new review round | Archive pushed after a clean review | evals/review-routes/test_review_run.py | test_archive_only_true_for_archive_commit; evals/pr-pair/test_skill_text.py test_watch_archive_head_no_request_no_reviewers | red |
| pr-watch → Archive head gets no new review round | Setting turned on | evals/pr-pair/test_skill_text.py | test_watch_review_after_archive_true_rerequests | red |
| pr-watch → Archive head gets no new review round | Archive commit touches other files | evals/review-routes/test_review_run.py | test_archive_only_false_outside_paths | red |
| pr-watch → Archive head gets no new review round | Another commit after the reviewed head | evals/review-routes/test_review_run.py | test_archive_only_false_two_commits | red |
| pr-watch → Archive head gets no new review round | Branch protection wants a fresh approval | evals/pr-pair/test_skill_text.py | test_watch_archive_review_required_asks_once | red |
| pr-watch → Archive head gets no new review round | Store-backed archive | evals/review-routes/test_review_run.py | test_archive_only_in_store_dir | red |
| pr-descriptions → Lists amendments and open findings | Clarification after pre-ship review | evals/pr-pair/test_skill_text.py | test_description_lists_amendment_trailers | red |
| pr-descriptions → Lists amendments and open findings | Open P3 finding | evals/pr-pair/test_skill_text.py | test_description_lists_open_p2_p3 | red |
| pr-descriptions → Lists amendments and open findings | Waived P1 finding | evals/pr-pair/test_skill_text.py | test_description_lists_waivers | red |
| pr-descriptions → Lists amendments and open findings | Drift amendment during apply | evals/pr-pair/test_skill_text.py | test_description_ignores_untrailered_amendments | red |
| pr-descriptions → Lists amendments and open findings | Nothing to list | evals/pr-pair/test_skill_text.py | test_description_review_section_only_with_content | red |

## 1. ADR and architecture

- [x] 1.1 Write `docs/adr/0007-reviewer-routes-with-a-specwright-owned-contract.md` (`Status: accepted`, `Supersedes: 0005`), restating 0005's orchestrator/implementer/reviewer split and recording design D2-D4, D8 and the ADR 0003 exception (machine-local records and waivers; escalation from `Preship-Round:` trailers). Leave 0005's file unchanged. Verify: `git diff --stat docs/adr/0005*` is empty and the new file has every MADR-short heading.
- [x] 1.2 Update `openspec/architecture.md`. Components: `specwright-review` plus `review-run.sh`, and the flowchart edges (D1 diagram). Add State ownership rows for review records and `Preship-Round:`/`Amendment:` trailers. Replace the Cross-model review contract with the route contract. Add Resource-bound rows for the review deadline and diff bound. In the in-force index, swap 0005 for 0007. Verify: `grep -n "0007\|review-run.sh\|Preship-Round" openspec/architecture.md` shows each, and the index has no 0005 row.

## 2. Trial run on each reviewer CLI

- [x] 2.1 Create the trial fixture: a throwaway git repo in a temp dir with a two-commit range holding one known defect, plus a store repo with one planning commit. Script it as `evals/review-routes/trial_fixture.sh`. Verify: running it prints both repo paths and `git -C <repo> log --oneline` shows the range.
- [x] 2.2 Run each of `codex`, `claude` and `omp` once with the D3 command line (prompt from a file, embedded diff, findings schema), plus once with a prompt asking the reviewer to edit a file. Record in `evals/review-routes/trial.md`: CLI version, exact working argv, exit code, whether the output validated against a draft schema, the model and level fields each CLI reports, and `git status --porcelain` after the write attempt (must be empty). Fix the D3 lines where a flag differs (for example `--restricted`, OMP's model probe command). Verify: `trial.md` has three rows, each with empty status after the write attempt; any argv change is noted against D3.

## 3. Findings contract and route runner

- [ ] 3.1 Add `skills/specwright-review/references/findings.schema.json` (draft 2020-12 subset the script validates: `summary`, `findings[≤100]` with `id`, `priority` P0-P3, `category` code|spec|test|docs, `file`, `line`, `title`, `body`, and `spec_class` required when `category` is `spec`) and `references/brief.md` (reporting criteria, the clarification and behaviour-change tests, credits to compound-engineering `ce-code-review` and oh-my-pi `reviewer.md` with links). Verify: `python -I -c "import json;json.load(open('skills/specwright-review/references/findings.schema.json'))"` exits 0.
- [ ] 3.2 Add fake `codex`, `claude` and `omp` executables under `evals/fakes/`, driven by environment variables (exit code, stdout file, delay, `Model not found`, argv log, session file). Write the failing select/run tests in `evals/review-routes/test_review_run.py` for the test map rows of review-routes. Verify: `python -m unittest discover evals/review-routes` fails on the missing script, for each row.
- [ ] 3.3 Implement `skills/specwright-review/scripts/review-run.sh` with `select` and `run`:
  - settings read from `openspec/specwright.yaml` (stdlib YAML subset, like `pr-pair.sh` context);
  - D3 command lines, prompt via a file with a nonce-delimited diff region, the `review.max_diff_kb` check before any spawn;
  - the `review.timeout` deadline with a process-tree kill by PID;
  - validation, and the receipt (OMP session file, Claude JSON usage, Codex events; `unknown` otherwise).

  Verify: the review-routes rows for routes, isolation argv, input, validation and receipt pass; flip them green.

## 4. Records, gate and rounds

- [ ] 4.1 Write failing tests in `evals/review-routes/test_review_run.py` for `record` (preship and design), `waive`, `gate` (repo-local and store-backed, archive matching), `archive-only` and `rounds`, using temp git repos and `SPECWRIGHT_STATE_DIR`. Verify: the new tests fail for the missing subcommands.
- [ ] 4.2 Implement `record`, `waive`, `gate`, `archive-only` and `rounds` per D2, D5 and D6: atomic rename, no stored outcome, records keyed by head(s), `Preship-Round:` from `git log`. Verify: the preship-review and pr-watch rows mapped to `test_review_run.py` pass; flip them green.
- [ ] 4.3 Add `test_rounds_ignore_preship_fix_commits` to `evals/pr-pair/test_pr_pair.py`: a branch with two `address pre-ship review` commits carrying `Preship-Round:` gives `rounds` 0, so the next pass is round 1. Verify: it passes against the current `pr-pair.sh` (the subject is distinct by design); flip it green, and if it fails, fix `pr-pair.sh` matching first.

## 5. The specwright-review skill and review steps

- [x] 5.1 Write failing text checks in `evals/review-routes/test_skill_text.py` for `skills/specwright-review/SKILL.md`: route selection via `select`, background run, fail closed with no fallthrough, waiver only after the user's answer, fix commit subject and trailer, escalation after round 2, clarification versus behaviour-change handling and the drift rule. Verify: they fail on the missing skill.
- [x] 5.2 Write `skills/specwright-review/SKILL.md` (frontmatter `metadata.version: 0.2.0`; pre-ship mode; route rules cited by other skills; credits). Verify: the 5.1 checks pass; flip their rows green.
- [x] 5.3 Replace the hardcoded pairing in `schemas/specwright/schema.yaml` (review step) with `specwright-review` route selection, including validation of subagent-written review files via `record --kind design`. Point the `specwright-roadmap` baseline review at the same routes. Add a pre-ship mode with findings-file output to `agents/claude/specwright-reviewer.md` and `agents/omp/specwright-reviewer.md` (descriptions too). Verify: `openspec schema validate specwright` passes after copying the schema into `openspec/schemas/specwright/`, and `python -m unittest discover evals/git-workflow -p "test_instructions.py"` passes, with its checks on the old pairing updated to the route rule.

## 6. Wiring into commit, ship, finish and watch

- [x] 6.1 Write failing text checks: `specwright-commit` step 3 runs the pre-ship review (skipped with `review.preship: false`) before the hand-off (`evals/review-routes/test_skill_text.py`). In `evals/pr-pair/test_skill_text.py`:
  - ship runs `discover` and `gate` before the first push, only when no PR exists in the change;
  - a failed review stops ship;
  - watch's archive rule (`archive-only`, no request and no reviewers, the `REVIEW_REQUIRED` ask, `pr.review_after_archive: true` keeping 0.1.13 behaviour);
  - the description Review section.

  The `specwright-finish` local gate before the merge goes in `test_skill_text.py`. Verify: the new checks fail.
- [ ] 6.2 Edit `skills/specwright-commit/SKILL.md` step 3, `skills/specwright-pr/SKILL.md` (ship gate, watch step 3 archive rule) and `references/description.md` (Review section from `Amendment:` trailers, open P2/P3 and waivers), and `skills/specwright-finish/SKILL.md` (local merge gate). Verify: the 6.1 checks and the full `python -m unittest discover evals/pr-pair` pass; flip their rows green.

## 7. Settings, install prompt and docs

- [ ] 7.1 Write failing text checks in `evals/git-workflow/test_instructions.py` for the README install prompt:
  - Step 6 compares dotted paths;
  - commented-out paths are optional, never removed or added;
  - `pr.reviewers.*` and `planning_store.reviewers.*` are user data;
  - Step 7 requires only uncommented paths;
  - the removed-key question stays.

  Verify: they fail.
- [ ] 7.2 Edit the README install prompt Steps 6-7 (D10). Add `review.order`, `review.models`, `review.thinking`, `review.timeout`, `review.max_diff_kb`, `review.preship` and `pr.review_after_archive`, with comments and safe defaults, to `templates/openspec/specwright.yaml` and to this repo's `openspec/specwright.yaml`, keeping `cross_model: false`. Update the README settings example, skills table, the pre-ship review section with the opt-out and the BREAKING note, and credits. Update the `CONTRIBUTING.md` copy table and its Reviews section. Verify: the 7.1 checks pass; flip their rows green. Then run the key comparison by hand: this repo's file against the new template, by dotted path, which lists no removed key.

## 8. Release and integration

- [ ] 8.1 Bump to 0.2.0: `VERSION`, the README badge and `metadata.version` in every `skills/*/SKILL.md`. Verify: `grep -rn "0.1.13" VERSION README.md skills/*/SKILL.md` prints nothing.
- [ ] 8.2 Integration check: run `python -m unittest discover evals/review-routes`, `python -m unittest discover evals/pr-pair` and `python -m unittest discover evals/git-workflow`, then `openspec validate add-preship-review --strict`. Re-install into this repo (install prompt) and run `openspec schema validate specwright`. Verify: all pass and every test map row is green.

## Workflow follow-up

- Ship opens the PR with `Fixes #27`, `Fixes #69` and `Fixes #78`. After the merge, release 0.2.0 and note the BREAKING default (`review.preship: true`) in the release notes.
