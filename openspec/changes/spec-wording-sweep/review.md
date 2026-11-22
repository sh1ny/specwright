# Review

## Metadata

- **Round:** 4 (FULL)
- **Prior round:** REVISE. The revised specs reconcile kept orphans with completion, exclude pack and agent rows from orphan deletion, restore settings consent, narrow the usage-error rule, and correct the reviewer diagnostic. D1 now keys exceptions by scenario and covers rename collisions.
- **Reviewer:** Codex (round 4 findings); user (USER_OVERRIDE)
- **User decision:** "Fix M2+M3, file C1+M1 (Recommended)": fix the two real items, file the two inferred orphan-rerun cases as one issue, record them as rebuttals, and write tasks.md without a round 5. This came after rounds 1 to 4 were REVISE and rounds 2, 3 and 4 were escalated.
- **Reviewed:** Proposal, design, all 20 delta specs and corresponding main-spec requirements, architecture and ADRs 0027/0040/0042, README, PR skill, CLI source, settings files, and cited evals. Static review; no evals run.

## Findings

### Critical (blocking)

1. **A rerun against a newer tag can stamp the update that failed Step 7.** The new orphan rule withholds the stamp when an approved removal fails (`openspec/changes/spec-wording-sweep/specs/install-update/spec.md:200–209`). The README tells the user to rerun, but the rerun defaults to the latest tag and `plan` runs recovery before returning (`README.md:145–163,316–325,482–487`; `cli/lib/src/update/plan.dart:501–520`). When the download differs from the pending journal’s `to`, recovery writes that older `to` into `VERSION` and removes the journal before the prompt reaches orphan handling (`cli/lib/src/update/recover.dart:216–230`). This behavior is required by the existing different-version scenario and pinned by `evals/update/test_update.py:332–349`. **[INFERENCE]** If a new tag appears after a failed removal, rerunning with defaults can stamp the failed installation even if the new update then refuses. Define which recovery paths the no-stamp guarantee covers. To keep the guarantee, the prompt must resume with the pending journal’s download or require rollback before planning another version.

### Moderate

1. **The resume path can offer deletion in a directory the completed swap did not touch.** D2 and the Step 4 requirement take orphan rows from the current plan after confirming a completed swap (`design.md:56`; `specs/install-update/spec.md:204–213`, relative to this change). The README’s resume check matches only phase and version. Recovery uses the journal’s targets, but the planner discovers orphans in the directories passed on this run (`README.md:114–130,316–325`; `cli/lib/src/update/recover.dart:169–173,218–224`; `cli/lib/src/update/plan.dart:153–171,298–306`). **[INFERENCE]** A Claude-only swap followed by a same-tag rerun selecting `.agents/skills` can skip the swap and offer to remove an orphan from `.agents/skills` before Step 7 notices that directory was never updated. Require the resumed targets to match before offering deletion. The eval should check that an approved removal happens before Step 5, not just that the question does (`design.md:59–66`).

2. **Two new scenarios promise a stamp after only one check passes.** The custom `release.version_files` scenario and the resumed orphan-removal scenario assert stamping without saying the other Step 7 checks passed (`specs/install-update/spec.md:158–160,207–209`, relative to this change). An invalid schema or a missing agent file still blocks the stamp (`README.md:454–482`). Assert the affected check’s result, or state that all other checks pass before asserting the stamp.

3. **The guard overlays parked changes that will never sync to main.** D1 overlays every active change except archived ones (`design.md:36–41`). A parked change can land on main with its delta still under `changes/` and its main specs untouched (`openspec/specs/design-review-gate/spec.md:58–67`). **[INFERENCE]** A parked delta that removes a retired mention can hide that mention in main indefinitely; one that adds a mention can fail CI for text that never becomes a main spec. Exclude parked deltas using the workflow’s whole-line deferral marker and cover that case in the overlay fixture.

### Suggestions

None.

## Verdict

VERDICT: USER_OVERRIDE

## Required Changes

CHANGES_APPLIED: n/a

## Rebuttals

- **Critical 1 (rerun against a newer tag stamps a failed install):** not fixed here, by the user's decision. The behaviour comes from the existing different-version recovery, which this change does not touch. The change only adds the rule that Step 4 asks about orphans on a resume. Filed as #243.
- **Moderate 1 (resumed run offers deletion in a directory the swap did not touch):** not fixed here, by the user's decision. It needs a rerun that selects different skills directories from the journal's. Filed as #243.
- **Moderate 2 (stamp asserted after one check):** fixed after this round. Both scenarios now stamp `VERSION` only "with every other Step 7 check passing". Not re-reviewed.
- **Moderate 3 (parked deltas in the overlay):** fixed after this round. D1 excludes changes whose `review.md` holds `VERDICT: DEFERRED`, and the overlay fixture covers one. Not re-reviewed.

Open findings at override: Critical 1 and Moderate 1 (#243).
