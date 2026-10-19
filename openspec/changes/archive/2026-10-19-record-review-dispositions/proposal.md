# Proposal

## Why

A FULL-tier change can only pass its design review by being reviewed. The schema allows `VERDICT: USER_OVERRIDE` only after two consecutive REVISE rounds are escalated to the user. Two real outcomes have no verdict of their own:

- A **parking change** is a backlog that is never applied or archived. Each part of it moves into its own change, and that change gets the full review. Its review is deferred, not skipped.
- The user may decide to apply a change **without any design review**.

In yagura (#100, found during the M3 deferred dogfood check #98), `platform-backlog` was such a parking change. `openspec status` showed its `review` missing, which blocked an update, and the user had to write `USER_OVERRIDE` well outside that verdict's meaning. The parking change also stays in `openspec list` forever, so roadmap **next** would offer to "resume" it, which can never happen.

This is change 2 of **M4 - Cost tier** (release 0.7.0, a minor release because it changes the workflow). It advances these exit criteria: every issue in the milestone's changes is closed by a merged PR, and each code fix has a regression test in `evals/`; `evals/git-workflow` and `evals/review-routes` pass; each change ships as its own release.

## What Changes

- **New verdict `VERDICT: DEFERRED`** for a FULL-tier change that is never applied, such as a parking change. `review.md` records where each part's review will happen (the change or milestone that takes each part over). `CHANGES_APPLIED: n/a`.
  - The tasks precheck accepts it, so planning can complete.
  - The apply gate refuses it, and so does archive, so a deferral can never ship unreviewed code.
- **New verdict `VERDICT: WAIVED`** for a change that is applied with no design review, by an explicit user decision. `review.md` quotes the user's own words and states that no design review ran. `CHANGES_APPLIED: n/a`.
  - The tasks and apply prechecks accept it only when the user's words are recorded. Without them it is refused.
  - The agent never offers it and writes it only on an explicit user decision, the same rule as the pre-ship waiver.
  - The pre-ship review is not waived by it: that review still runs.
- **`USER_OVERRIDE` keeps its narrow meaning:** proceeding after two consecutive REVISE rounds were escalated. Deferral and waiver may no longer be recorded as `USER_OVERRIDE`.
- **A reviewer may not return either verdict.** `review-run.sh` already refuses any design verdict other than APPROVE, APPROVE_WITH_CHANGES and REVISE. Regression tests now pin DEFERRED and WAIVED to that refusal.
- **A parking change lands without archive.** The user merges its branch. Watch's archive-before-merge skips a `DEFERRED` change and reports the PR ready as parked, and agent merge sends no merge request.
- **The roadmap baseline gate keeps its own list** (APPROVE, APPROVE_WITH_CHANGES with `CHANGES_APPLIED: yes`, USER_OVERRIDE after escalation). Neither new verdict ever passes it.
- **Roadmap parking changes.** `specwright-roadmap` describes the parking-change pattern: its review is `DEFERRED`, and **next** moves a milestone's part out into its own change. **next** and **status** do not count a `DEFERRED` change as a change in progress to resume. **status** lists it as parked.
- The review template, the README verdict table and the schema's review, tasks and apply text cover both verdicts.
- Release 0.7.0 (minor): `VERSION`, the README badge and the skill `metadata.version` fields.

## Capabilities

### New Capabilities
- `design-review-gate`: which `review.md` verdicts let a change write tasks, apply and archive, who may write each verdict, and what each one must record. Today these rules exist only in schema text. The deferred and waived dispositions are new.

### Modified Capabilities
- `review-routes`: the verdicts a reviewer may not set now include `DEFERRED` and `WAIVED`.
- `project-planning`: roadmap **next** and **status** treat a `DEFERRED` parking change as parked, never as an active change to resume, and say so on the parking change's own branch. The baseline gate lists its own passing verdicts, and neither new verdict is among them.

## Impact

- `schemas/specwright/schema.yaml`: review, tasks and apply instruction text only. No artifact or dependency changes, so a change in flight needs no migration. Its existing `review.md` keeps passing.
- `schemas/specwright/templates/review.md`, `README.md` (verdict table, review section).
- Archive refusal: `templates/openspec/config.yaml` (a new `context:` line that reaches the archive workflow), README install Step 5 (its managed-line prefixes), and `skills/specwright-finish/SKILL.md` (a backstop before the archive commit).
- `skills/specwright-pr/SKILL.md` (watch's archive before merge skips a `DEFERRED` change).
- `skills/specwright-roadmap/SKILL.md` (init step 5's own gate list, **next** step 2, **status**, a parking-change note), `openspec/architecture.md` (the `review.md` and baseline writer rows), `skills/specwright-commit/SKILL.md` if its apply start restates the gate.
- `skills/specwright-review/scripts/review-run.sh`: no behaviour change expected. Its tests gain DEFERRED and WAIVED cases. `skills/specwright-review/SKILL.md` (Design reviews) adds both to the values it lists as invalid.
- Tests: `evals/git-workflow/test_instructions.py` (both verdicts accepted at the tasks precheck, a waiver without the user's words refused, the agent never offers either one, apply and archive refuse `DEFERRED`, roadmap next skips a parked change) and `evals/review-routes/test_review_run.py`.
- No new configuration key and no dependency change. Installed projects get the new `context:` line through the existing config.yaml merge (install Step 5).
