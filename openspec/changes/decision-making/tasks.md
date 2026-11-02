# Tasks

## Test map

All tests are wording checks in `evals/git-workflow/test_decision_making.py`, in the style of `evals/git-workflow/test_instructions.py`. They assert where each rule sits and its key terms in the delivered schema, templates and README. They prove a rule is in the instructions, not that a live agent follows it.

| Requirement | Scenario | Test file | Test name | State |
|---|---|---|---|---|
| decision-making → The decision mode comes from the setting | Setting unset | evals/git-workflow/test_decision_making.py | test_setting_unset_means_autonomous | green |
| decision-making → The decision mode comes from the setting | Setting has an unknown value | evals/git-workflow/test_decision_making.py | test_unknown_value_stops_naming_valid_values | green |
| decision-making → A user instruction overrides the mode for one change | Override recorded | evals/git-workflow/test_decision_making.py | test_override_recorded_in_proposal_with_words | green |
| decision-making → A user instruction overrides the mode for one change | Session resumes after the proposal, without the conversation | evals/git-workflow/test_decision_making.py | test_resumed_session_reads_mode_from_proposal | green |
| decision-making → A user instruction overrides the mode for one change | Next change after an override | evals/git-workflow/test_decision_making.py | test_override_is_for_one_change_only | green |
| decision-making → A user instruction overrides the mode for one change | Change planned before this feature | evals/git-workflow/test_decision_making.py | test_missing_mode_line_falls_back_to_setting | green |
| decision-making → Every decision records its importance and who chose it | Config key decision | evals/git-workflow/test_decision_making.py | test_importance_criteria_listed | green |
| decision-making → Every decision records its importance and who chose it | Tactical decision | evals/git-workflow/test_decision_making.py | test_design_template_has_important_and_chosen_by | green |
| decision-making → Every decision records its importance and who chose it | Not a decision | evals/git-workflow/test_decision_making.py | test_wording_order_layout_not_decisions | green |
| decision-making → Every change carries a decision summary | Autonomous planning ends | evals/git-workflow/test_decision_making.py | test_summary_shown_at_end_without_waiting | green |
| decision-making → Every change carries a decision summary | Autonomous with a choice the user stated | evals/git-workflow/test_decision_making.py | test_stated_choice_is_user_without_asking | green |
| decision-making → Every change carries a decision summary | Summary out of step with the decisions | evals/git-workflow/test_decision_making.py | test_summary_rows_match_entries | green |
| decision-making → Decisions go to the user per the mode | Important mode | evals/git-workflow/test_decision_making.py | test_important_mode_asks_important_only | green |
| decision-making → Decisions go to the user per the mode | All mode | evals/git-workflow/test_decision_making.py | test_all_mode_asks_every_decision | green |
| decision-making → Decisions go to the user per the mode | Ask tool that takes four questions | evals/git-workflow/test_decision_making.py | test_batches_of_at_most_four_through_ask_tool | green |
| decision-making → Decisions go to the user per the mode | Ask tool that takes three questions | evals/git-workflow/test_decision_making.py | test_batch_shrinks_to_tool_question_limit | green |
| decision-making → Decisions go to the user per the mode | Ask tool with a smaller option limit | evals/git-workflow/test_decision_making.py | test_options_fit_tool_limit_keeping_recommended_and_discuss | green |
| decision-making → Decisions go to the user per the mode | Ask tool not usable in the current mode | evals/git-workflow/test_decision_making.py | test_unusable_tool_falls_back_to_plain_text | green |
| decision-making → Decisions go to the user per the mode | Harness without an ask tool | evals/git-workflow/test_decision_making.py | test_plain_text_only_as_fallback | green |
| decision-making → Decisions go to the user per the mode | User asks to discuss | evals/git-workflow/test_decision_making.py | test_discuss_option_holds_the_decision | green |
| decision-making → Decisions go to the user per the mode | User hands the decision back | evals/git-workflow/test_decision_making.py | test_you_decide_records_agent | green |
| decision-making → A user-chosen decision changes only with the user | Reviewer asks to change a user choice | evals/git-workflow/test_decision_making.py | test_review_change_to_user_choice_asks_first | green |
| decision-making → A user-chosen decision changes only with the user | Autonomous mode, review or drift would replace a user choice | evals/git-workflow/test_decision_making.py | test_user_choice_protected_in_every_mode | green |
| decision-making → A user-chosen decision changes only with the user | Reviewer changes only agent choices | evals/git-workflow/test_decision_making.py | test_agent_choices_applied_without_asking_in_autonomous | green |
| decision-making → Decisions changed after planning follow the mode | Drift in important mode | evals/git-workflow/test_decision_making.py | test_apply_drift_follows_mode | green |
| decision-making → Decisions changed after planning follow the mode | Drift in autonomous mode | evals/git-workflow/test_decision_making.py | test_autonomous_drift_amends_agent_choice_and_rereviews | green |
| decision-making → The setting is documented where it is set | Fresh install | evals/git-workflow/test_decision_making.py | test_template_names_setting_and_values | green |
| decision-making → The setting is documented where it is set | Existing project updated | evals/git-workflow/test_decision_making.py | test_readme_documents_setting_default | green |

## 1. Mode resolution and the proposal record

- [x] 1.1 Create `evals/git-workflow/test_decision_making.py` with the tests for the first two requirements (test map rows 1-6). Run `python -m unittest evals/git-workflow/test_decision_making.py` and confirm each fails because the rule is missing, not because of an import or path error.
- [x] 1.2 In `schemas/specwright/schema.yaml`'s proposal instruction, add the decision mode: read `decision_making` from the code repo's `openspec/specwright.yaml` (unset = `autonomous`, unknown value stops before any decision is written and names the value and the three valid ones), a user instruction at change start sets the mode for this change only, and the mode is resolved before `proposal.md` is written. Add the `## Decision Making` section to `schemas/specwright/templates/proposal.md` (before `## Release Notes`): `DECISION_MAKING: <mode>`, `Source:` (`setting`, or `user` with the quoted words), and scope decisions `S1`... with Choice, Rejected, Reversal cost, Important, Chosen by. Later steps read the mode there, and a proposal without the line uses the setting. Verify that rows 1-6 pass, flip them green, and that `openspec schema validate specwright` passes.

## 2. Decision fields and the summary

- [x] 2.1 Add tests for rows 7-12 and confirm they fail for the right reason.
- [x] 2.2 In the design instruction and `schemas/specwright/templates/design.md`, add per-decision `Important: yes|no` with the criterion met (the four criteria from design D4) and `Chosen by: agent|user` (user when the user chose or stated it, in any mode). State that wording, task order and test layout are not decisions. Add the `### Decision summary` table after the last decision, with one row per `S` and `D` entry, updated in the same edit as any entry. In the tasks instruction, show the summary table to the user at the end of planning, with no wait in `autonomous` mode. Verify that rows 7-12 pass, flip them green, and that `openspec schema validate specwright` passes.

## 3. Putting decisions to the user

- [x] 3.1 Add tests for rows 13-21 and confirm they fail for the right reason.
- [x] 3.2 In the proposal and design instructions, ask before the artifact is written. In `important` mode, ask about each important decision; in `all` mode, ask about every decision. Questions go in batches of at most 4, or the usable ask tool's lower question limit (more decisions: more batches), each with 2-4 options cut to the tool's option limit, always keeping the recommended one marked and a way to discuss (the tool's free-text answer, else a discuss option), put through the harness's own ask tool when it is usable in the current session and mode, so the user picks instead of typing; plain text with lettered options only when no ask tool is usable. A decision under discussion is not written until the user settles it. "You decide" takes the recommended option, recorded `Chosen by: agent` with a note. Verify that rows 13-21 pass and flip them green.

## 4. Protecting user choices and later changes

- [x] 4.1 Add tests for rows 22-26 and confirm they fail for the right reason.
- [x] 4.2 In the review instruction (Required Changes applied by the author), a change that reverses a `Chosen by: user` decision goes to the user first, in any mode. Its entry and summary row stay unchanged until the user answers; agent choices are applied per the mode. In the apply instruction's drift rule, a replacement decision follows the change's recorded mode, and a user choice always goes to the user. Verify that rows 22-26 pass, flip them green, and that `openspec schema validate specwright` passes.

## 5. Settings, docs and the contract

- [x] 5.1 Add tests for rows 27-28 and confirm they fail for the right reason.
- [x] 5.2 Add an active `decision_making: autonomous` line with a comment naming `autonomous`, `important` and `all` to `templates/openspec/specwright.yaml`. Add it to the README settings block (default `autonomous`, unset means `autonomous`) and a short paragraph to the README's planning flow. Add a Contracts bullet in `openspec/architecture.md` for the `## Decision Making` section and the `Important`/`Chosen by` fields that later runs parse (a workflow change, minor version). Verify that rows 27-28 pass and flip them green.
- [x] 5.3 Run `python -m unittest evals/runner/test_suite_map.py` to confirm the new test module is covered by the suite map. Add a rule to `evals/suites.json` if the test reports it uncovered.

## 6. Release

- [ ] 6.1 Run `release.sh bump --to 0.17.0`, rewrite the summary of the proposal's `## Release Notes` to describe the whole release, and verify with `release.sh check` and `release.sh notes --proposal openspec/changes/decision-making/proposal.md`.

## Workflow follow-up

- CI (`.github/workflows/evals.yml`) runs every suite on Linux, Windows and macOS on the PR; no full local suite run.
- Archive with `/opsx:archive`, then `specwright-finish` (pr mode).
