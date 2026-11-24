# 0044. Change design review binds rules and records owner checkpoints

- Status: accepted
- Date: 2026-11-24
- Adds to: 0007 (FULL change-design input and workflow)
- Supersedes: 0015's Release Notes-only review exemption for FULL changes

## Context

A project rule may govern tests the current design preserves, even if the change does not add those tests. In the Kumiko replay, giving the existing reviewer the standing test rules surfaced a profile-lock race in all three first passes; two baseline replays missed it. Later rounds found other real failures without a falling finding count.

## Decision

- FULL change-design reviews take an ordered list of project-declared rules. Read regular blobs from the named code branch, not the checkout, a planning store, ambient instructions, or filesystem links. Include the full text as criteria, not authority to change tools or workflow. Do not add these criteria to LIGHT, roadmap baseline or pre-ship reviews.
- The round limit is an owner checkpoint. Keep the reviewer's unresolved verdict, record the actual owner choice in `review.md`, and require a passing review for tasks and apply. Do not derive readiness or a stopping rule from finding counts.
- Use live planning files and the full checklist each round. Compare byte digests of current inputs and the review record at dispatch and publication. Any later planning or rule edit voids a pass, including Release Notes and Required Changes. Do not keep copies of planning inputs or a conditional baseline. Serialize only state checks, writes and scratch reservation; never hold the publication lock across a review, owner deliberation or a wait for either.

## Consequences

Projects declare deliberate versioned criteria without editing the shipped reviewer, but the configured text can reach the selected review provider. A new rule identity requires a new full review. An unresolved checkpoint survives repeated invocations and authorizations without becoming an override or a pass. Pre-ship, roadmap and PR feedback retain separate policies.
