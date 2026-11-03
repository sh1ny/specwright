# Tasks

## Test map

New tests live in `evals/git-workflow/test_roadmap_autonomy.py` (wording checks on `skills/specwright-roadmap/SKILL.md`, its `references/strategy.md`, `skills/specwright-pr/SKILL.md`, `templates/openspec/specwright.yaml`, `README.md` and `openspec/architecture.md`, in the style of `test_decision_making.py`). Rows marked green ride along unchanged inside a MODIFIED requirement and already pass in `evals/git-workflow/test_instructions.py`.

| # | Requirement | Scenario | Test file | Test name | State |
|---|---|---|---|---|---|
| 1 | Roadmap runs read their decision mode from the project setting | Key unset | test_roadmap_autonomy.py | ModeFromSetting.test_unset_means_important_interview | green |
| 2 | Roadmap runs read their decision mode from the project setting | Unknown value | test_roadmap_autonomy.py | ModeFromSetting.test_unknown_value_stops_before_write | green |
| 3 | Roadmap runs read their decision mode from the project setting | Change planning keeps its own setting | test_roadmap_autonomy.py | ModeFromSetting.test_top_level_decision_making_not_read | green |
| 4 | A user instruction overrides the roadmap mode for one run | Override at init | test_roadmap_autonomy.py | Override.test_override_recorded_with_words_setting_unchanged | green |
| 5 | A user instruction overrides the roadmap mode for one run | Next run without an instruction | test_roadmap_autonomy.py | Override.test_override_for_one_run_only | green |
| 6 | An autonomous roadmap run asks nothing and records every answer | Autonomous init | test_roadmap_autonomy.py | Autonomous.test_init_asks_nothing_and_records_rows | green |
| 7 | An autonomous roadmap run asks nothing and records every answer | Autonomous pack setup | test_roadmap_autonomy.py | Autonomous.test_pack_mode_autonomous | green |
| 8 | An autonomous roadmap run asks nothing and records every answer | Pack offer at an autonomous init | test_roadmap_autonomy.py | Autonomous.test_pack_offer_pending_not_enabled | green |
| 9 | A question round may span several ask-tool calls | Init round larger than the ask tool | test_roadmap_autonomy.py | Rounds.test_round_spans_calls_init | green |
| 10 | A question round may span several ask-tool calls | Pack round larger than the ask tool | test_roadmap_autonomy.py | Rounds.test_round_spans_calls_pack | green |
| 11 | In all mode every roadmap decision goes to the user | ADR choices in all mode | test_roadmap_autonomy.py | AllMode.test_adr_and_replan_choices_in_further_batches | green |
| 12 | In all mode every roadmap decision goes to the user | Session ends before the answers | test_roadmap_autonomy.py | AllMode.test_asked_before_file_written | green |
| 13 | The strategy carries the roadmap's decision summary | Close adds rows after the baseline passed | test_roadmap_autonomy.py | Summary.test_summary_edit_does_not_void_baseline | green |
| 14 | The strategy carries the roadmap's decision summary | PR feedback fixes only summary rows | test_roadmap_autonomy.py | Summary.test_pr_feedback_summary_only_no_rerun | green |
| 15 | The strategy carries the roadmap's decision summary | Edit outside the section | test_roadmap_autonomy.py | Summary.test_edit_outside_section_still_voids | green |
| 16 | The strategy carries the roadmap's decision summary | Pending rows at the next close | test_roadmap_autonomy.py | Summary.test_close_puts_pending_rows_to_owner | green |
| 17 | The strategy carries the roadmap's decision summary | Strategy written before this change | test_roadmap_autonomy.py | Summary.test_assumptions_list_kept | green |
| 18 | Autonomy never passes a gate meant for the owner | Autonomous close with an agreed split and an amendment | test_roadmap_autonomy.py | OwnerGates.test_agreed_split_amendment_pending | green |
| 19 | Autonomy never passes a gate meant for the owner | Autonomous close with an unagreed listing | test_roadmap_autonomy.py | OwnerGates.test_unagreed_listing_promoted_no_split_line | green |
| 20 | Autonomy never passes a gate meant for the owner | Autonomous close with an unverified user criterion | test_roadmap_autonomy.py | OwnerGates.test_user_criterion_never_passed | green |
| 21 | Autonomy never passes a gate meant for the owner | Autonomous close with untagged versions | test_roadmap_autonomy.py | OwnerGates.test_release_not_published | green |
| 22 | Baseline review rounds follow the schema's escalation rule | Two consecutive revise verdicts | test_instructions.py | test_roadmap_review_escalates_after_two_consecutive_revise | green |
| 23 | Baseline review rounds follow the schema's escalation rule | Edit after a passing verdict | test_instructions.py | test_baseline_edit_after_pass_reruns_review | green |
| 24 | An autonomous baseline escalation stops the run | Round 1 findings kept when round 2 replaces the file | test_roadmap_autonomy.py | Escalation.test_findings_copied_before_next_round | green |
| 25 | An autonomous baseline escalation stops the run | Two consecutive revise verdicts in autonomous mode | test_roadmap_autonomy.py | Escalation.test_autonomous_escalation_stops | green |
| 26 | Roadmap init includes enabled packs' questions and documents | Pack questions join the interview | test_instructions.py | test_roadmap_init_asks_pack_questions_in_two_rounds | green |
| 27 | Roadmap init includes enabled packs' questions and documents | Pack questions in an autonomous init | test_roadmap_autonomy.py | Autonomous.test_pack_questions_autonomous_init | green |
| 28 | Roadmap init includes enabled packs' questions and documents | A pack document edited after the baseline passed | test_instructions.py | test_pack_documents_are_not_gated | green |
| 29 | Roadmap init includes enabled packs' questions and documents | A pack document is missing at init | test_instructions.py | test_roadmap_init_missing_pack_document | green |
| 30 | Roadmap pack mode sets up a pack enabled later | Setting up a pack after the baseline | test_instructions.py | test_roadmap_pack_mode_commits_on_docs_branch | green |
| 31 | Roadmap pack mode sets up a pack enabled later | The pack is not installed | test_instructions.py | test_roadmap_pack_mode_needs_installed_pack | green |
| 32 | Close keeps an agreed Next split | Close promotes an agreed split | test_instructions.py | test_roadmap_close_keeps_agreed_split | green |
| 33 | Close keeps an agreed Next split | Close finds a reason to amend the agreed split | test_roadmap_autonomy.py | OwnerGates.test_amendment_asked_in_interactive_modes | green |
| 34 | Close keeps an agreed Next split | Amendment to an agreed split in autonomous mode | test_roadmap_autonomy.py | OwnerGates.test_agreed_split_amendment_pending | green |
| 35 | Close keeps an agreed Next split | Next without a split | test_instructions.py | test_roadmap_close_keeps_agreed_split | green |
| 36 | Close keeps an agreed Next split | Next lists changes without a recorded agreement | test_roadmap_autonomy.py | OwnerGates.test_unmarked_split_asked_in_interactive_modes | green |
| 37 | Close keeps an agreed Next split | Unagreed listing in autonomous mode | test_roadmap_autonomy.py | OwnerGates.test_unagreed_listing_promoted_no_split_line | green |
| 38 | Autonomy never passes a gate meant for the owner | Owner agrees in an interactive run | test_roadmap_autonomy.py | OwnerGates.test_owner_agreement_still_acts | green |

## 1. Reading the mode and the override

- [x] 1.1 Create `evals/git-workflow/test_roadmap_autonomy.py` with the tests for rows 1-5. Run `python -m unittest evals/git-workflow/test_roadmap_autonomy.py` and confirm they fail because the skill and template lack the rules.
- [x] 1.2 In `skills/specwright-roadmap/SKILL.md`, add a decision-mode paragraph that init, close and pack read at their start, before any branch or write (design D1):
  - read `project.decision_making`; unset means `important`, today's interview;
  - an unknown value stops, naming it and `autonomous`, `important`, `all`;
  - the top-level `decision_making` is never read by the roadmap;
  - a spoken instruction at run start sets the mode for that run only, is recorded with the user's words in the run line, and leaves `specwright.yaml` unchanged.

  Verify that rows 1-5 pass and flip them green.
- [x] 1.3 Add a commented `# decision_making: important` line inside `project:` in `templates/openspec/specwright.yaml`, with a comment naming the three values and that unset means `important`. Add the key to the README settings block and a paragraph to the README roadmap section (design D7). Add tests that the template line is commented and inside `project:` and that the README names the key. Verify that they pass.

## 2. Asking per mode

- [x] 2.1 Add the tests for rows 6-12 and 27 and confirm they fail for the right reason.
- [x] 2.2 In init step 2, close and pack, make asking depend on the mode:
  - `autonomous` asks nothing: each gap, pack question, ADR choice and re-plan choice becomes an `agent` row with its reason, a pack offer becomes a `pending` row, `packs:` stays unchanged, and the rows are shown at the end without a wait;
  - `important` keeps today's interview;
  - `all` also puts ADR choices (before step 4 writes them) and close's re-plan choices to the user in further batches;
  - a round is one set of questions put together before any of its answers is written, and may span several ask-tool calls; init keeps two rounds, pack one, and no question is dropped.

  Point to the schema's proposal instruction for the ask-tool, options and discuss rules (design D6). Keep the wording `test_instructions.py` checks for the two batched rounds and the recommended default. Verify that rows 6-12 and 27 pass and flip them green, and re-run `python -m unittest evals/git-workflow/test_instructions.py -k pack` for rows 26 and 28-31.

## 3. The decision summary and the gate exemption

- [x] 3.1 Add the tests for rows 13-17 and for the strategy reference template, and confirm they fail for the right reason.
- [x] 3.2 Replace `## Assumptions` in `skills/specwright-roadmap/references/strategy.md` with `## Decision summary` (design D2):
  - run lines `- <run> <YYYY-MM-DD>: <mode> (source: ...)`;
  - one table with the columns #, Run, Decision, Choice, Rejected, Reason, Important, Chosen by;
  - `R` ids that continue across runs;
  - `Chosen by` is `agent`, `user` or `pending`; rows are settled in place and never deleted.

  In the skill:
  - rows are written in every mode;
  - an existing `## Assumptions` list is left as is and the section is added after it;
  - close lists open `pending` rows at its start and, in `important`/`all` mode, puts them to the owner.

  Verify that rows 16-17 pass and flip them green.
- [x] 3.3 Exempt edits confined to the strategy's `## Decision summary` from voiding the baseline (design D3):
  - in init step 5's voiding rule;
  - in `skills/specwright-pr/SKILL.md` feedback step 7;
  - in `openspec/architecture.md`'s design-review row.

  Add a Contracts bullet in `openspec/architecture.md` for `project.decision_making`, the summary format and the exemption (a workflow change, minor version). Verify that rows 13-15 pass and flip them green, and re-run `test_baseline_edit_after_pass_reruns_review` for row 23.

## 4. Owner gates, close and the escalation

- [x] 4.1 Add the tests for rows 18-21, 24-25, 33-34 and 36-38, and confirm they fail for the right reason.
- [x] 4.2 In close, qualify for the mode (design D4, D5):
  - an agreed split's amendment is asked in `important`/`all` mode and is a `pending` row in `autonomous`;
  - the unmarked-split question is asked in `important`/`all` mode, and in `autonomous` the listing is promoted as it stands with an `agent` row;
  - the new Next never gets a `Split agreed` line from an autonomous run;
  - an unverified user criterion stays unverified and close stops; in `autonomous` mode it stops before its `docs/close-*` branch exists, writes nothing and lists the criterion in the run's report (review round 2, finding 2);
  - each owner gate forbids the action only without the owner's explicit agreement: an interactive run still acts on an agreement the owner gave (review round 2, finding 1);
  - untagged versions become a `pending` row and nothing is published.

  Keep the wording that `test_instructions.py` checks. Verify that rows 18-21, 33-34 and 36-38 pass and flip them green, and re-run `python -m unittest evals/git-workflow/test_instructions.py -k split` for rows 32 and 35.
- [x] 4.3 In init step 5, for `autonomous` mode:
  - before a new baseline round replaces `openspec/architecture-review.md`, copy the previous round's findings (severity and one line each) into the summary;
  - after 2 consecutive REVISE rounds, stop without asking: no roadmap, ADRs stay proposed, no `USER_OVERRIDE`, and a `pending` escalation row names round 1's findings.

  Verify that rows 24-25 pass and flip them green, and re-run `test_roadmap_review_escalates_after_two_consecutive_revise` for row 22.

## 5. Map and release

- [x] 5.1 Run `python -m unittest evals/runner/test_suite_map.py` to confirm that `evals/suites.json` covers the new test module. Add a rule if it reports the module uncovered.
- [x] 5.2 Run `release.sh bump --to 0.19.0` and rewrite the summary of the proposal's `## Release Notes` to describe the whole release. Verify with `release.sh check` and `release.sh notes --proposal openspec/changes/roadmap-init-autonomy/proposal.md`.

## Workflow follow-up

- CI (`.github/workflows/evals.yml`) runs every suite on Linux, Windows and macOS on the PR. No full local suite run.
- Archive with `/opsx:archive`, then `specwright-finish` (pr mode).
