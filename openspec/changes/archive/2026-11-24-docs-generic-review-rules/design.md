# Design

## Triage

| Trigger | Applies? | Evidence |
|---|---|---|
| T1 Components | No | Only README prose and the settings template's comments change (`README.md:898-913`, `templates/openspec/specwright.yaml:34-37`). |
| T2 State | No | No runtime state changes. The patch version uses the existing release task. |
| T3 Concurrency | No | No execution flow changes. |
| T4 Boundaries | No | The key, accepted paths, and review scope stay the same (`README.md:900-911`). |
| T5 Volume | No | No data processing changes. |
| T6 Risk | No | No auth, security, or user data changes. |

TIER: LIGHT

## Context

The README currently names a specific rollout, and both files show that rollout's rule path (`README.md:900-913`, `templates/openspec/specwright.yaml:34-35`). See [proposal.md](proposal.md) for the intended correction.

The owner approved the manual branch gate for this Orca worktree: the clean detached checkout matched freshly fetched `origin/main` at `95beef69`, the change name was unused, and `docs/docs-generic-review-rules` was created there before scaffolding. The separate checkout holding local `main` was left untouched.

## Decisions

### D1: Use a project-owned example

- **Choice:** Show `rules/review-criteria.md` as a file the reader creates, commits, and lists under `review.standing_rules`.
- **Rejected:** Keep the rollout recipe because it names a source file readers of the public docs do not have.
- **Reversal cost:** low.
- **Important:** yes (public documentation scope).
- **Chosen by:** user.

### Decision summary

| # | Decision | Choice | Rejected | Reversal cost | Important | Chosen by |
|---|---|---|---|---|---|---|
| D1 | Example | Project-owned rules | Team-specific migration | low | yes | user |

## Assumptions

None.

## Carried constraints

None.
