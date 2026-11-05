# Tasks

## Test map

| Requirement | Scenario | Test file | Test name | State |
|---|---|---|---|---|
| design-constraints → A design lists the constraints it carries forward | Deliberate gap in the data | evals/git-workflow/test_design_constraints.py | test_design_lists_carried_constraints_with_destination | green |
| design-constraints → A design lists the constraints it carries forward | Behavioural guarantee | evals/git-workflow/test_design_constraints.py | test_destination_rule_by_kind | green |
| design-constraints → A design lists the constraints it carries forward | Nothing outlives the change | evals/git-workflow/test_design_constraints.py | test_carried_constraints_none_when_empty | green |
| design-constraints → A design lists the constraints it carries forward | LIGHT design | evals/git-workflow/test_design_constraints.py | test_carried_constraints_above_light_boundary_and_in_light_list | green |
| design-constraints → Apply writes each carried constraint at its destination | Doc comment destination | evals/git-workflow/test_design_constraints.py | test_tasks_write_each_entry_at_destination | red |
| design-constraints → Apply writes each carried constraint at its destination | Destination moved during apply | evals/git-workflow/test_design_constraints.py | test_moved_destination_is_drift | red |
| design-constraints → The design review checks the list is complete | Rejected alternative not carried | evals/git-workflow/test_design_constraints.py | test_review_flags_unlisted_constraint_moderate | red |
| design-constraints → The design review checks the list is complete | Entry without a destination | evals/git-workflow/test_design_constraints.py | test_review_flags_entry_without_single_destination | red |
| design-constraints → The design review checks the list is complete | LIGHT design omits a constraint | evals/git-workflow/test_design_constraints.py | test_light_recheck_records_finding_and_withholds_verdict | red |
| design-constraints → The design review checks the list is complete | Design planned before this change | evals/git-workflow/test_design_constraints.py | test_missing_section_reads_as_none | green |
| preship-review → The pre-ship review checks each carried constraint against the diff | Carried constraint missing from the code | evals/git-workflow/test_design_constraints.py | test_brief_missing_carried_constraint_is_p1 | red |
| preship-review → The pre-ship review checks each carried constraint against the diff | Carried constraint present | evals/git-workflow/test_design_constraints.py | test_brief_checks_destination_in_range | red |
| preship-review → The pre-ship review checks each carried constraint against the diff | No carried constraints | evals/git-workflow/test_design_constraints.py | test_brief_no_finding_for_none | red |

## 1. Verify the base (A1)

- [x] 1.1 Verify A1 before any other task: `verify-design-claims` is merged on `main`. Rebase this branch onto `main`. Confirm that `schemas/specwright/templates/design.md` has `## Assumptions` above the LIGHT boundary, and that the schema's LIGHT list reads "Triage, Context, Decisions and Assumptions". If either is missing, stop: design D1 is drift, and the drift rule applies.

## 2. The contract

- [x] 2.1 Write `docs/adr/0026-design-constraints-are-carried-into-code-specs-or-adrs-during-apply.md` (MADR-short, `Status: accepted`, today's date). It carries C1 (no archive-time harvest), C2 (no step reads archived designs for planning) and C3 (the `## Carried constraints` format: heading, ids, kinds, exactly one destination in one of three forms, `None`, placement above the LIGHT boundary), plus D2-D4. Add its row to the in-force ADR index in `openspec/architecture.md`. Verify the ADR names C1, C2 and C3 and the index row exists.

## 3. The design section

- [x] 3.1 Create `evals/git-workflow/test_design_constraints.py` in the style of `evals/git-workflow/test_user_tasks.py`, with the red tests for the four "lists the constraints" rows and `test_missing_section_reads_as_none`. Run `python -m unittest evals/git-workflow/test_design_constraints.py` and confirm each fails because the rule is missing.
- [x] 3.2 In `schemas/specwright/schema.yaml`, design instruction:
  - Add `## Carried constraints` to SECTIONS: ids `C1`..., kind, exactly one destination (`doc comment: <path> <symbol>`, `spec: specs/<capability>/spec.md → Requirement: <name>`, or `ADR NNNN`), and `None` when nothing outlives the change.
  - Add the destination rule by kind (D2).
  - Make the LIGHT list "Triage, Context, Decisions, Assumptions and Carried constraints".

  In `schemas/specwright/templates/design.md`, add the section after `## Assumptions` and above the LIGHT boundary. Verify the five tests pass, `openspec schema validate specwright` passes, and flip the rows green.

## 4. Design review completeness

- [ ] 4.1 Add the red tests for "Rejected alternative not carried", "Entry without a destination" and "LIGHT design omits a constraint" to `evals/git-workflow/test_design_constraints.py`, and confirm they fail for the right reason.
- [ ] 4.2 In the review instruction of `schemas/specwright/schema.yaml`:
  - Add a **Carried constraints** checklist item. A stated rejected alternative, invariant or deliberate gap that a future change could break and that is not listed is a Moderate finding. So is an entry with zero or several destinations. A design with no section reads as `None`.
  - Extend the LIGHT paragraph: the re-check applies the same test. Each failure is recorded in review.md as a Moderate finding with no `VERDICT:` line. After the author's fix and a passing re-check, review.md gets `VERDICT: SKIPPED_LIGHT` with the findings marked fixed.

  Verify the rows pass and flip them green.

## 5. Tasks carry each entry

- [ ] 5.1 Add the red tests for the two "Apply writes each carried constraint" rows and confirm they fail for the right reason.
- [ ] 5.2 In the tasks instruction of `schemas/specwright/schema.yaml`, next to the ADR first-group rule, add the per-entry rule:
  - Each `## Carried constraints` entry gets a task that names its id and writes the fact at its destination.
  - ADR destinations ride the first-group ADR task.
  - The task is ticked only when the text is there.
  - A destination that is gone or no longer fits during apply is design drift.

  Verify the rows pass, `openspec schema validate specwright` passes, and flip them green.

## 6. Pre-ship brief

- [ ] 6.1 Add the red tests for the three preship-review rows and confirm they fail for the right reason.
- [ ] 6.2 In `skills/specwright-review/references/brief.md` under "What to report", add a **Carried constraints** item:
  - Read the design's `## Carried constraints`, from the archived design when the review runs after the archive commit.
  - Check that each entry's fact is present at its destination in the reviewed range. A missing entry, or text there that contradicts the design, is P1 `docs` naming the entry.
  - A section that reads `None`, or a design with no section, raises no such finding.

  Verify the rows pass and flip them green.

## 7. Docs, roadmap and coverage

- [ ] 7.1 Make the docs and roadmap edits:
  - `README.md`: add one or two sentences on carried constraints next to the design-grounding text (the section, the destinations, the review and pre-ship checks, and that archived designs are history only).
  - `openspec/roadmap.md`: make sure M7 lists `carry-design-constraints` (#198, closes #190) after `verify-design-claims`; add it if missing.

  Run `python -m unittest evals/runner/test_suite_map.py`, and add a rule to `evals/suites.json` if the new test file is reported uncovered. Verify that the map test passes.

## 8. Release

- [ ] 8.1 Run `release.sh bump --to 0.22.0`, rewrite the summary of the proposal's `## Release Notes` to describe the whole release, and verify with `release.sh check` and `release.sh notes --proposal openspec/changes/carry-design-constraints/proposal.md`.

## Workflow follow-up

- Pre-ship review, PR (body: `Closes #198`, `Closes #190`), watch, archive and the v0.22.0 release follow the usual `finish: pr` flow.
