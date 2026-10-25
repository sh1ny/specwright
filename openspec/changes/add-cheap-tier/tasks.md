# Tasks

## Test map

| Requirement | Scenario | Test file | Test name | State |
|---|---|---|---|---|
| cost-tiers → The cheap tier is off unless enabled | Unset leaves dispatch unchanged | evals/pr-pair/test_pr_pair.py | TestTier.test_unset_is_off | red |
| cost-tiers → The cheap tier is off unless enabled | Unset leaves dispatch unchanged (dispatch text) | evals/git-workflow/test_instructions.py | TestCheapTier.test_delegation_tier_off_keeps_implementer | red |
| cost-tiers → The cheap tier is off unless enabled | An unrecognised value is off and reported | evals/pr-pair/test_pr_pair.py | TestTier.test_unrecognised_value_is_off_with_note | red |
| cost-tiers → The cheap tier is off unless enabled | The section is not a map | evals/pr-pair/test_pr_pair.py | TestTier.test_non_map_section_is_off_with_note | red |
| cost-tiers → The cheap tier is off unless enabled | Another setting is invalid | evals/pr-pair/test_pr_pair.py | TestTier.test_bad_merge_settings_do_not_affect_tier | red |
| cost-tiers → The cheap tier is off unless enabled | The setting cannot be read | evals/git-workflow/test_instructions.py | TestCheapTier.test_delegation_unreadable_tier_is_off | red |
| cost-tiers → The light implementer is a pinned copy of the implementer | Light implementer matches the implementer | evals/git-workflow/test_instructions.py | TestCheapTier.test_light_implementer_matches_implementer | red |
| cost-tiers → The light implementer is a pinned copy of the implementer | The instructions drift apart | evals/git-workflow/test_instructions.py | TestCheapTier.test_light_implementer_drift_names_both_files | red |
| cost-tiers → A LIGHT change's groups go to the cheap implementer | LIGHT change with the tier on | evals/git-workflow/test_instructions.py | TestCheapTier.test_delegation_light_tier_on_uses_light_implementer | red |
| cost-tiers → A LIGHT change's groups go to the cheap implementer | FULL change with the tier on | evals/git-workflow/test_instructions.py | TestCheapTier.test_delegation_full_keeps_implementer | red |
| cost-tiers → A LIGHT change's groups go to the cheap implementer | Light implementer not installed | evals/git-workflow/test_instructions.py | TestCheapTier.test_delegation_light_missing_falls_back | red |
| cost-tiers → Reviews and orchestration never move to the cheap tier | Design review with the tier on | evals/review-routes/test_skill_text.py | test_cheap_tier_never_reaches_review_routes | red |
| cost-tiers → Reviews and orchestration never move to the cheap tier | A LIGHT change's pre-ship review | evals/review-routes/test_skill_text.py | test_preship_never_uses_light_implementer | red |
| pr-watch → A wait can skip wakes that are only check progress | A check passes while others run | evals/pr-pair/test_pr_snapshot.py | TestUntilAttention.test_check_progress_is_filtered | red |
| pr-watch → A wait can skip wakes that are only check progress | The last check finishes | evals/pr-pair/test_pr_snapshot.py | TestUntilAttention.test_last_check_done_wakes | red |
| pr-watch → A wait can skip wakes that are only check progress | A check fails | evals/pr-pair/test_pr_snapshot.py | TestUntilAttention.test_new_failure_wakes | red |
| pr-watch → A wait can skip wakes that are only check progress | Feedback arrives during check progress | evals/pr-pair/test_pr_snapshot.py | TestUntilAttention.test_feedback_during_checks_wakes | red |
| pr-watch → A wait can skip wakes that are only check progress | A conflict appears | evals/pr-pair/test_pr_snapshot.py | TestUntilAttention.test_dirty_wakes | red |
| pr-watch → A wait can skip wakes that are only check progress | Unknown mode or no wait | evals/pr-pair/test_pr_snapshot.py | TestUntilAttention.test_bad_until_exits_2_without_gh | red |
| pr-watch → Watch waits for attention | Watch's wait command | evals/pr-pair/test_skill_text.py | test_watch_waits_until_attention | red |
| pr-watch → Watch waits for attention | Ready after a quiet wait with a check re-run | evals/pr-pair/test_pr_snapshot.py + evals/pr-pair/test_skill_text.py | TestUntilAttention.test_rerun_back_to_baseline_times_out + test_watch_timeout_counts_as_full_wait | red |
| eval-grading → Stress-tier evals are marked by kind | Every kind is covered | evals/git-workflow/test_tiers.py | TestStressMarks.test_every_kind_marked | red |
| eval-grading → Stress-tier evals are marked by kind | A kind loses its last mark | evals/git-workflow/test_tiers.py | TestStressMarks.test_missing_kind_named | red |
| eval-grading → Stress-tier evals are marked by kind | An unknown kind | evals/git-workflow/test_tiers.py | TestStressMarks.test_unknown_kind_named | red |
| eval-grading → The tier comparison names every difference | Same grades | evals/git-workflow/test_tiers.py | TestCompare.test_same_grades_exit_0 | red |
| eval-grading → The tier comparison names every difference | The cheap configuration fails an assertion | evals/git-workflow/test_tiers.py | TestCompare.test_difference_named_with_assertion | red |
| eval-grading → The tier comparison names every difference | A grading is missing or unreadable | evals/git-workflow/test_tiers.py | TestCompare.test_missing_or_unreadable_is_missing | red |

## 1. Roadmap criterion and ADR

- [x] 1.1 In `openspec/roadmap.md`, replace M4's cheap-tier exit criterion with the exact text in design D5, and update change 6's line (`add-cheap-tier`) to the light implementer, `--until attention` and the Haiku stress run. Verify with `grep -n 'until attention' openspec/roadmap.md` (both lines) and that no line still reads "watch and the LIGHT implementer run on Haiku".
- [x] 1.2 Write `docs/adr/0013-cheap-tier-through-pinned-agents.md` (MADR-short, `Status: accepted`, today's date) per design D6: a cheaper model takes only bounded, re-verified work, through a pinned agent chosen by name; reviews, orchestration, watch and GitHub writes never move down; rejected: a per-dispatch model override. Add its row to `openspec/architecture.md`'s in-force index. Add `specwright-implementer-light` to the component table, `pr-pair.sh tier` and the wake filter to the `specwright-pr` row, and `tiers.py` to the Evals row. Verify with `grep -n 0013 openspec/architecture.md` and `openspec schema validate specwright`.

## 2. The setting and `pr-pair.sh tier`

- [ ] 2.1 Write the failing `TestTier` tests in `evals/pr-pair/test_pr_pair.py`: unset off; `false`/`no` off; `true`/`yes` on; `on` off with a note naming `on`; `cheap_tier: true` (not a map) off with the not-a-map note; the inline form `cheap_tier: { enabled: on }` off with a note (the parsed value when the text is not kept, design S10); `merge: agent` with `merge_method: fast` still exits 0 with the tier as set. Run `python -m unittest evals.pr-pair.test_pr_pair -k TestTier` (or the discover form) and confirm they fail because `tier` is an unknown subcommand.
- [ ] 2.2 Implement `pr-pair.sh tier --code <toplevel>` per design D2 (reuse `load_settings` and `setting_text`; validate nothing else; `{"ok": true, "cheap_tier": bool}` plus `note`). Add it to the script's usage header. Verify `TestTier` passes and flip its rows green.
- [ ] 2.3 Add `cheap_tier: { enabled: false }` with a comment to `templates/openspec/specwright.yaml` and to this repo's `openspec/specwright.yaml` (stays `false`). Document the setting in the README settings block and the `pr-pair.sh` row of the scripts table. Verify with `python -m unittest discover evals/pr-pair` (template and settings tests) and `grep -n cheap_tier README.md templates/openspec/specwright.yaml`.

## 3. The light implementer and its dispatch

- [ ] 3.1 Write the failing `TestCheapTier` tests in `evals/git-workflow/test_instructions.py`:
  - for each harness, `specwright-implementer-light.md` has the same body after the frontmatter and the same `tools:` line as `specwright-implementer.md`, and `model: haiku` (Claude Code) or `model: pi/smol` (OMP);
  - a drift helper fails and names both files when the bodies differ, tested on a temp copy;
  - the apply DELEGATION text in `schemas/specwright/schema.yaml`:
    - runs `pr-pair.sh tier`;
    - sends every group of a `TIER: LIGHT` change to `specwright-implementer-light` when the tier is on, with no inline exception;
    - keeps `specwright-implementer` and the small-group clause for FULL changes or the tier off;
    - falls back to `specwright-implementer`, saying so once, when the light agent is missing;
    - treats a failed or field-less `tier` call as off, with a note.
  
  Run them and confirm each fails because the files or text are missing.
- [ ] 3.2 Create `agents/claude/specwright-implementer-light.md` and `agents/omp/specwright-implementer-light.md` (copies of the implementer bodies and `tools:` lines, with their own name, description and model). Edit the DELEGATION paragraph in `schemas/specwright/schema.yaml` as the tests expect. Verify `TestCheapTier` passes and `openspec schema validate specwright` exits 0. Flip the rows green.
- [ ] 3.3 Write failing `test_cheap_tier_never_reaches_review_routes` and `test_preship_never_uses_light_implementer` in `evals/review-routes/test_skill_text.py`. They check that `review-run.sh`, `skills/specwright-review/SKILL.md` and both `specwright-reviewer.md` files never mention `cheap_tier` or `specwright-implementer-light`, and that the reviewer models are unchanged (`inherit`, `pi/slow`). Confirm they fail only if a mention exists. If they pass at once because nothing mentions it, record that the test is a guard, and keep it. Verify with `python -m unittest discover evals/review-routes` and flip both rows green.
- [ ] 3.4 Update the README agents table (the light implementer row with `haiku` / `pi/smol`, plus the OMP note from design D1), the Apply row and the delegated-agents check paragraph. Note in CONTRIBUTING that an implementer body edit is copied to its light twin in the same change. Verify with `grep -n implementer-light README.md CONTRIBUTING.md`.

## 4. The wake filter

- [ ] 4.1 Write the failing `TestUntilAttention` tests in `evals/pr-pair/test_pr_snapshot.py` with the fake `gh` and short `--interval`/`--timeout`, one per pr-watch scenario:
  - a check passes while two are still pending: filtered, then the timeout wake has `filtered >= 1`;
  - the last pending check passes: wakes `changed`;
  - a pending check fails with others pending: wakes `changed`;
  - a new comment while checks are pending: wakes `changed`;
  - the merge state turns `DIRTY` while pending: wakes `changed`;
  - an all-pass baseline with one check re-run to pending, then passing: wakes `timeout` with `filtered >= 1`;
  - `--until quiet`, and `--until attention` without `--wait`: exit 2 with `--until` in the message and no line in the fake gh log;
  - no `--until`: a check passing wakes `changed`, as today.
  
  Run them and confirm they fail on the unknown argument.
- [ ] 4.2 Implement per design D3 in `skills/specwright-pr/scripts/pr-snapshot.sh`:
  - add the `attn` field beside `sig`;
  - parse and validate `--until`;
  - apply the skip rule in the wait loop against the first good snapshot;
  - count `filtered` and add it to the wake JSON;
  - document it in the header comment.
  
  Verify `TestUntilAttention` and the whole `python -m unittest discover evals/pr-pair` pass. Flip the six filter rows green.
- [ ] 4.3 Write failing `test_watch_waits_until_attention` and `test_watch_timeout_counts_as_full_wait` in `evals/pr-pair/test_skill_text.py`. Then edit `skills/specwright-pr/SKILL.md`: watch step 1's command gets `--until attention` and the `filtered` field, and step 3's ready rule says a `timeout` wake counts as a full wait with no new activity even with filtered polls. Also update the README's `pr-snapshot.sh` row. Verify both tests pass and flip the rows green.

## 5. The stress tier tooling

- [ ] 5.1 Write the failing `evals/git-workflow/test_tiers.py`.
  - `TestStressMarks`: every kind (`watch`, `light-apply`, `implementer`) has a marked eval; a temp copy with the only `implementer` mark removed fails naming `implementer`; a temp copy with `"stress": true` fails naming the eval and value.
  - `TestCompare`, on temp iteration dirs: same grades exit 0; a cheap-only failure is named with both rates and the assertion text, exit 1; a missing or invalid `grading.json` is listed as missing, exit 1; unmarked evals are skipped.
  
  Confirm they fail because `tiers.py` and the marks do not exist.
- [ ] 5.2 Implement `evals/git-workflow/tiers.py` (standard library only; `--base`, `--cheap`, `--evals` defaulting to the eval list next to it; one JSON document on stdout). Mark eval 3 `light-apply` and evals 55, 56 and 64 `watch` in `evals.json`. Verify `TestCompare` passes.
- [ ] 5.3 Add `eval-implementer-light-packet` (kind `implementer`) to `evals.json`, using the add-greeting fixture. The prompt hands a packet for one task group and tells the agent to follow `agents/claude/specwright-implementer-light.md`. Add its `check` branch to `grade.py`: the group's tests exist and pass, no new commit, `tasks.md` unticked, the report gives the red and green evidence. Add a grader test in `evals/git-workflow/test_grade.py` against a scripted good run and a run that committed. Verify `python -m unittest discover evals/git-workflow` passes and flip the `TestStressMarks` rows green.
- [ ] 5.4 Document the stress tier in the README Evals section and CONTRIBUTING. It is the stress-marked evals run through skill-creator with the executor on the default model (`base`) and on Haiku (`haiku`), then `python evals/git-workflow/grade.py <it>` and `python evals/git-workflow/tiers.py <it> --base base --cheap haiku`. It is a wording diagnostic, not a shipped configuration and not a CI gate. Verify with `grep -n tiers.py README.md CONTRIBUTING.md`.

## 6. Stress run and dispatch trial

- [ ] 6.1 Run the stress-marked evals through skill-creator in both configurations (`base`, `haiku`), grade them with `grade.py`, and run `tiers.py`. For each difference, decide whether it is a wording gap. If it is, fix the skill or agent text (never with model-specific wording) and re-run that eval in both configurations. Repeat until every remaining difference is either gone or shown, by a re-run after a wording attempt, to be a model limit. Verify by `tiers.py`'s final JSON being saved in the record of 6.3.
- [ ] 6.2 Run the dispatch trial: in a scratch project with Specwright installed from this branch and `cheap_tier.enabled: true`, start a new session and apply a small LIGHT change. Confirm from the harness transcript that every group went to `specwright-implementer-light` on a Haiku model, and that the orchestrator re-verified before each commit. Then run the same apply with the setting unset and confirm the groups went to `specwright-implementer`. Delete the scratch project afterwards. Verify by the transcript excerpts (agent name and model) in the record of 6.3.
- [ ] 6.3 Write `evals/git-workflow/stress.md`, a dated section with:
  - the models the transcripts showed;
  - per stress eval, the pass rates in both configurations;
  - `tiers.py`'s JSON;
  - each wording fix with its eval;
  - each recorded model limit with its evidence;
  - the dispatch trial's excerpts;
  - the watch-wake counts with and without the filter, if a real watch ran during the trial.
  
  Verify that the file exists and that each difference `tiers.py` listed is accounted for in it.

## 7. Release and integration

- [ ] 7.1 Run every suite the M4 exit criteria list: `python -m unittest discover evals/pr-pair`, `evals/git-workflow`, `evals/review-routes`, `evals/update`, `evals/release` and `evals/finish`. Also run `openspec schema validate specwright` and `openspec validate add-cheap-tier --strict`. Verify that all exit 0.
- [ ] 7.2 `bash skills/specwright-release/scripts/release.sh bump --to 0.8.0`; verify with `bash skills/specwright-release/scripts/release.sh check` exiting 0.

## Workflow follow-up

- Pre-ship review, PR, watch (with `--until attention`), archive and merge per `finish: pr` and `pr.merge: agent`.
- After the merge, publish 0.8.0, then run roadmap **close** for M4: this is its last change.
