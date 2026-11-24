# Proposal

## Why

In the replay of Kumiko #26, the existing reviewer caught the profile-lock race in 3/3 first rounds when given the project's standing test rules, versus 0/2 without them. Later rounds still found bugs, so M9 (Adoption and configuration) advances the design-cap portion of #172 by making a round limit an owner checkpoint, not a readiness test; the pre-ship cap portion remains open.

## What Changes

- Make explicitly declared, versioned project rules binding input to FULL change-design reviews, including for existing tests the design preserves. Leave the brief alone when no rules are declared.
- Replace the change-design escalation after two consecutive `REVISE` verdicts with a per-project checkpoint after three unresolved rounds by default. Record the owner's choice to allow one scoped pass, change the scope with a reason, or stop, without changing the review verdict.
- Keep the existing checklist and run it in full every round. Any later edit to design inputs, including Release Notes or Required Changes, voids a pass. Pre-ship, roadmap baseline and PR feedback policies stay separate. Do not add a finding-count stop or the experimental findings format.
- Document the config and rollout of `rules/windows-ci-tests.md`; this change modifies no other repository.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `review-routes`: include standing requirements in a FULL change-design brief regardless of route.
- `design-review-gate`: hand off unresolved reviews at the configured checkpoint and retain the owner's decision without approving.

## Impact

Project settings, the Specwright review workflow and native `sw review`, review-route evals, and project documentation. No external service or runtime dependency.

The coordinator authorized the manual branch-gate equivalent for this Orca worktree: its clean initial `HEAD`, local `main` and fetched `origin/main` were all `0dd03e8c74a132cad66d9306cdf3d35707998076`; the feature branch was created from that tip without switching the primary worktree.

## Decision Making

DECISION_MAKING: important
Source: setting; the coordinator delegated design choices within the approved contract.

### S1: Keep this change to FULL change-design reviews

- **Choice:** Ship binding rules and the checkpoint for FULL change-design reviews; no changes to pre-ship, baseline, LIGHT, or PR feedback policy.
- **Rejected:** Extend the policy to all review modes. The replay studied change designs, not those other gates.
- **Reversal cost:** Low.
- **Important:** yes (changes behavior users see).
- **Chosen by:** user.

### S2: Keep owner choices separate from approval

- **Choice:** At the checkpoint allow one scoped pass, a reasoned scope change, or stop; preserve the review verdict and require another review to pass an unresolved design.
- **Rejected:** Stop on a stalled count, derive readiness from a count, or turn the owner's checkpoint choice into `USER_OVERRIDE`. Later rounds find defects and a handoff grants no approval.
- **Reversal cost:** Medium.
- **Important:** yes (changes the design gate users see).
- **Chosen by:** user.

### S3: Remove planning captures and incremental rechecks

- **Choice:** Keep standing rules and the owner checkpoint; read live design files in every full pass, and require a new pass after any edit.
- **Rejected:** Private planning snapshots, a Markdown Release Notes exclusion, and a persisted conditional baseline.
- **Reason (owner):** “Pre-ship kept finding holes in the review-capture tracking; incremental rechecks were never part of the brief (delta-only rounds were rejected by the experiment). Design review keeps today's behaviour: every round is a full review, and any later edit voids a pass.”
- **Reversal cost:** Medium.
- **Important:** yes (removes incremental rechecks).
- **Chosen by:** user.

## Release Notes

FULL change-design reviews can use a repository's own versioned rules, including when the design preserves existing tests. The review hands off to the owner after three unresolved rounds by default; the reviewer verdict still controls readiness. Pre-ship and PR feedback policies are unchanged.

### Added

- Declare standing design-review criteria with `review.standing_rules` in `openspec/specwright.yaml` (#172).

### Changed

- `review.design_max_rounds` controls the design review owner checkpoint, default three. The checkpoint records the owner's choice without turning outstanding findings into an approval (#172).
- An in-flight FULL approval recorded before Specwright tracked review inputs needs a fresh FULL review before tasks or apply. Historical `USER_OVERRIDE` records keep their disposition.
- FULL change-design review runs the whole checklist after edits, including Required Changes and Release Notes.
- A failed FULL design review may retain one bounded diagnostic per change. It no longer retains the original subagent scratch reply or a full session transcript.
