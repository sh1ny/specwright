# Proposal

## Why

A design can say how existing code behaves without anyone checking. The design instruction already asks for `file:line` citations of existing patterns and for checks on claims that something does not exist. Nothing asks the review to re-read what a design cites. In blackgrid's `fix-frozen-map-metadata` (2026-11-05), design.md claimed `FrozenInputs.fromGeneration` could stage every raw input and cited `tool/maps/pack.dart:146-254`. The doc comment inside that range said the opposite. Design review passed, and apply stopped after 8 of 14 tasks (#197). The citation was there; the check was not.

This change is inserted into M7 (Native CLI foundation) ahead of `native-cli-spike`, by the user's choice. It changes only instructions and templates, not the scripts M7 migrates. It advances the criterion "All M7 changes are archived on main and their releases are published" for itself.

## What Changes

- **Design grounding:** every claim in design.md about how existing code, data or formats behave cites the `path:line` range that shows it, as narrow as the claim allows. A claim the author did not check against the code is written as an assumption in a `## Assumptions` section, each with an id (`A1`, `A2`...), and says which decisions or tasks depend on it.
- **FULL review:** the reviewer re-reads each cited range and checks that it supports the claim. A claim that has no citation, or whose citation contradicts it, is a finding. An assumption that the reviewer could settle by reading the code is also a finding: it should have been checked, not assumed. The roadmap baseline review uses the same checklist, so it gets the same check.
- **LIGHT re-check:** the author's existing LIGHT triage re-check also re-reads each citation against its claim. A contradiction means the design is fixed, and a fix that trips a trigger makes the change FULL, as it does today.
- **Tasks:** each assumption that a decision or task depends on gets a verify-first task, before any task that relies on it. A disproved assumption is design drift: apply stops and the existing drift rule applies (amend, re-review, resume).
- The design template carries the `## Assumptions` section and the citation rule; the reviewer agent definitions name the claim check.

## Capabilities

### New Capabilities
- `design-grounding`: how a design states claims about existing code (citations, assumptions), how the design review and the LIGHT re-check verify them, and how tasks verify the assumptions a design depends on.

### Modified Capabilities

None. `design-review-gate` governs verdict dispositions, which do not change.

## Impact

- `schemas/specwright/schema.yaml`: design instruction (GROUND step, Assumptions section), review instruction (LIGHT re-check, a Claims item in the checklist), tasks instruction (verify-first tasks).
- `schemas/specwright/templates/design.md` and `schemas/specwright/templates/review.md`: Assumptions section, citation guidance, claim findings.
- `agents/claude/specwright-reviewer.md`, `agents/omp/specwright-reviewer.md`: the claim check for design reviews.
- `README.md`: one line on design grounding where the design review is described.
- `openspec/roadmap.md`: insert this change into M7.
- Wording tests under `evals/git-workflow/`; `evals/suites.json` if a new file needs a rule.
- Projects pick this up on their next update; designs already written are not rewritten.

## Decision Making

DECISION_MAKING: important
- **Source:** setting

### S1: #197 and #198 are separate changes

- **Choice:** this change covers #197 (verifying cited claims) only. #198 (carrying design constraints into code docs, specs or ADRs) is its own change, planned next.
- **Rejected:** one combined "grounded planning" change. It would mean a bigger PR and one review loop over two different phases (plan review, and apply/archive).
- **Reversal cost:** low
- **Important:** no
- **Chosen by:** user

### S2: LIGHT designs get an author re-check of citations

- **Choice:** the LIGHT triage re-check, done by the author, also re-reads each citation against its claim.
- **Rejected:** FULL only, which leaves LIGHT designs unchecked. Also rejected: an independent reviewer run for every LIGHT change with citations, which costs a reviewer run per LIGHT change and blurs the tier split.
- **Reversal cost:** low
- **Important:** yes (changes behaviour users see)
- **Chosen by:** user

### S3: Inserted into M7 ahead of the native CLI work

- **Choice:** this change and the #198 change go into M7 before `native-cli-spike`. The #198 change closes #190.
- **Rejected:** planning them outside any milestone and placing them at the next close. That would leave the blackgrid failure mode in place for the whole native-CLI migration.
- **Reversal cost:** low
- **Important:** yes (changes behaviour users see)
- **Chosen by:** user

### S4: Pre-ship review is unchanged

- **Choice:** only the design review, the LIGHT re-check and the tasks step change. The pre-ship review keeps its brief.
- **Rejected:** adding claim checks to the pre-ship review. By then the code exists and the tests are the evidence, and a wrong design claim has already cost the apply work this change is meant to save.
- **Reversal cost:** low
- **Important:** no
- **Chosen by:** agent

## Release Notes

Design reviews now check what a design says about existing code. A design cites the code behind each claim and lists the claims it did not check as assumptions. The reviewer re-reads every citation, and the LIGHT re-check does too. Tasks verify each assumption the plan depends on before relying on it (#197).

### Added
- Design claims about existing code cite `path:line`. Unchecked claims go in a `## Assumptions` section, and tasks verify each load-bearing assumption first (#197).

### Changed
- The design review and the LIGHT re-check re-read each cited range. A missing or contradicting citation is a finding (#197). They open only files tracked in the repository, so a citation cannot send an ignored local file to the review provider.
