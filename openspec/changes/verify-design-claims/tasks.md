# Tasks

## Test map

| Requirement | Scenario | Test file | Test name | State |
|---|---|---|---|---|
| design-grounding → A design cites the code behind each claim | Claim checked against the code | evals/git-workflow/test_design_grounding.py | test_design_claims_cite_path_line | red |
| design-grounding → A design cites the code behind each claim | Claim the author could not check | evals/git-workflow/test_design_grounding.py | test_unchecked_claim_is_numbered_assumption | red |
| design-grounding → A design cites the code behind each claim | Design with no claims about existing code | evals/git-workflow/test_design_grounding.py | test_assumptions_none_when_all_cited | red |
| design-grounding → The design review checks each cited claim | Citation contradicts the claim | evals/git-workflow/test_design_grounding.py | test_review_rereads_citations_contradiction_critical | red |
| design-grounding → The design review checks each cited claim | Claim without citation | evals/git-workflow/test_design_grounding.py | test_review_flags_uncited_claim | red |
| design-grounding → The design review checks each cited claim | Assumption the code settles | evals/git-workflow/test_design_grounding.py | test_review_flags_settleable_assumption | red |
| design-grounding → The design review checks each cited claim | Cited range no longer exists | evals/git-workflow/test_design_grounding.py | test_review_flags_citation_not_showing_claim | red |
| design-grounding → The LIGHT re-check also re-reads citations | LIGHT citations hold | evals/git-workflow/test_design_grounding.py | test_light_recheck_rereads_citations | red |
| design-grounding → The LIGHT re-check also re-reads citations | LIGHT citation contradicts the claim | evals/git-workflow/test_design_grounding.py | test_light_contradiction_fixed_before_verdict | red |
| design-grounding → Tasks verify load-bearing assumptions first | Assumption with dependent tasks | evals/git-workflow/test_design_grounding.py | test_tasks_verify_assumption_before_dependents | red |
| design-grounding → Tasks verify load-bearing assumptions first | Assumption disproved during apply | evals/git-workflow/test_design_grounding.py | test_disproved_assumption_is_drift | red |
| design-grounding → Tasks verify load-bearing assumptions first | Assumption nothing depends on | evals/git-workflow/test_design_grounding.py | test_no_verify_task_without_dependents | red |

Extra tests (design D1, required by the review): `test_template_assumptions_above_light_boundary` and `test_light_section_list_names_assumptions` in the same file.

## 1. The contract

- [x] 1.1 Write `docs/adr/0025-design-claims-cite-code-unchecked-claims-are-numbered-assumptions.md` (MADR-short, `Status: accepted`, today's date) from design D1-D3 and D5: the `path:line` citation rule, the `## Assumptions` section in both tiers with ids `A1`..., its consumers (the FULL review's Claims item, the LIGHT re-check, verify-first tasks) and the severity rule. Add its row to the in-force ADR index in `openspec/architecture.md`. Verify that the ADR file and the index row exist.

## 2. Design grounding

- [ ] 2.1 Create `evals/git-workflow/test_design_grounding.py` in the style of `evals/git-workflow/test_user_tasks.py` (assert where a rule sits and its key terms in the flattened schema block). Add the red tests for the three "cites the code" rows plus `test_template_assumptions_above_light_boundary` and `test_light_section_list_names_assumptions`. Run `python -m unittest evals/git-workflow/test_design_grounding.py` and confirm each fails because the rule is missing, not because of a fixture error.
- [ ] 2.2 In `schemas/specwright/schema.yaml`, design instruction:
  - Step 2 GROUND: every claim about how existing code, data or a format behaves cites the narrowest `path:line` range that shows it (D3). A claim not checked against the code becomes an `## Assumptions` entry with an id, why it was not checked, and the decisions or tasks that depend on it (or `none`). The section reads `None` when everything is cited.
  - LIGHT list: "Triage, Context, Decisions and Assumptions".
  - Add `## Assumptions` to the SECTIONS list.

  In `schemas/specwright/templates/design.md`, add the `## Assumptions` section after the Decision summary and above the LIGHT boundary, and make the Context comment ask for `path:line` on claims about existing behaviour. Verify the five tests pass, `openspec schema validate specwright` passes, and flip the rows green.

## 3. Review checks claims

- [ ] 3.1 Add the red tests for the four "design review checks" rows and the two LIGHT rows to `evals/git-workflow/test_design_grounding.py`, plus one asserting that both reviewer agent definitions name the claim check. Confirm they fail for the right reason.
- [ ] 3.2 Make the review changes:
  - In the review instruction of `schemas/specwright/schema.yaml`, add a **Claims** item to the "Try to break the design" list. The reviewer re-reads every cited range. Each of these is a finding: a claim about existing behaviour with neither a citation nor an Assumptions entry; a citation that does not show its claim (too broad, moved or missing); and an assumption the code settles. A contradicted claim that a decision or task depends on is Critical; any other claim finding is at least Moderate (D2).
  - Extend the LIGHT paragraph: the re-check also re-reads each citation against its claim, fixes a contradiction in design.md before any verdict, and goes FULL when the fix trips a trigger. A design with no `## Assumptions` section (planned before this change) counts as `None`, and its citations are still checked.
  - In `agents/claude/specwright-reviewer.md` and `agents/omp/specwright-reviewer.md`, the design-review line names the claim check (D4).

  Verify the rows pass and flip them green.

## 4. Tasks verify assumptions

- [ ] 4.1 Add the red tests for the three "Tasks verify load-bearing assumptions first" rows to `evals/git-workflow/test_design_grounding.py` and confirm they fail for the right reason.
- [ ] 4.2 In the tasks instruction of `schemas/specwright/schema.yaml` (next to the ADR first-group rule), add the verify-first rule:
  - Each Assumptions entry that names a dependent decision or task gets a task. The task names its id, says what to read or run to settle it, and comes before the first task that relies on it.
  - An entry with no dependents gets no task.
  - A disproved assumption is design drift: point to the apply drift rule.

  Add one example line to `schemas/specwright/templates/tasks.md`. Verify the rows pass, `openspec schema validate specwright` passes, and flip them green.

## 5. Docs, roadmap and coverage

- [ ] 5.1 Make the docs and roadmap edits:
  - `README.md`: add one or two sentences on design grounding where the design review is described (citations, Assumptions, the Claims check, verify-first tasks).
  - `openspec/roadmap.md`: insert `verify-design-claims` (#197) and `carry-design-constraints` (#198, closes #190) into M7's change list ahead of `native-cli-spike`, renumbering the rest.

  Run `python -m unittest evals/runner/test_suite_map.py`, and add a rule to `evals/suites.json` if the new test file is reported uncovered. Verify that the map test passes.

## 6. Release

- [ ] 6.1 Run `release.sh bump --to 0.21.0`, rewrite the summary of the proposal's `## Release Notes` to describe the whole release, and verify with `release.sh check` and `release.sh notes --proposal openspec/changes/verify-design-claims/proposal.md`.

## Workflow follow-up

- Pre-ship review, PR, watch, archive and the v0.21.0 release follow the usual `finish: pr` flow.
