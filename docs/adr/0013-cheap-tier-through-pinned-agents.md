# 0013. A cheap tier only through pinned agents for bounded, re-verified work

- Status: accepted
- Date: 2026-10-26

## Context
Issue #22 asks for a cheaper model (Haiku) for Specwright work that is long and mechanical. Two candidates came up: the implementer of a LIGHT change (doc edits, template blocks, version bumps) and watch, which re-enters the orchestrator's full context on every wake although most wakes only show a CI check finishing. ADR 0007 already splits the roles: the orchestrator verifies and commits, an implementer agent builds from a packet, and reviews run on isolated reviewer routes. Each agent's model is pinned in its definition's frontmatter. OMP's task tool takes no per-call model, while Claude Code's Agent tool does. A first design put a Haiku watcher agent in front of watch's wakes; its review showed it saved only the wakes a deterministic filter removes for free, and that it put a cheap model next to untrusted comment text with a shell able to reach `gh`.

## Decision
A cheaper model takes only bounded work whose result the orchestrator re-verifies before anything is committed, and it does so through an agent definition pinned to that model and chosen by name.

- **The only cheap agent is `specwright-implementer-light`.** It is a copy of `specwright-implementer`, word for word in its body and `tools:` line, pinned to `haiku` (Claude Code) or the `pi/smol` role (OMP). A test keeps the copies identical. With `cheap_tier.enabled: true` (read only by `pr-pair.sh tier`), every task group of a `TIER: LIGHT` change goes to it; a FULL change and the tier off keep `specwright-implementer`. The orchestrator verifies, ticks and commits exactly as for the implementer (0007).
- **Never on the cheap tier:** the orchestrator itself, design and pre-ship reviews (route selection and the `specwright-reviewer` model), watch, and every GitHub write.
- **Watch gets cheaper without a model.** A deterministic filter (`pr-snapshot.sh --wait --until attention`) skips the wakes that are only check progress, with zero tokens (0002).
- **A new cheap use needs the same shape:** bounded work, a pinned agent chosen by name, and orchestrator re-verification. Anything else needs a new ADR.

**Rejected: a per-dispatch model override** (`cheap_tier.model` passed as the Agent tool's `model`), because OMP has no such override and the setting would carry a harness-specific model name. **Rejected: templating the model into the agent at install**, because it adds a substitution step and a second form of every agent file (0001 installs plain copies). **Rejected: a Haiku watcher agent**, because the filter removes the same wakes for free and the agent would read untrusted text with `gh` in reach.

## Consequences
- The cheap tier saves money only on LIGHT changes, and only where the harness maps `haiku` to a cheaper model. On OMP both implementers use `pi/smol`, so the tier changes nothing unless the user points the implementer's `model:` line at a stronger role.
- Every edit to an implementer body must be copied to its light twin in the same change; the body-equality test fails otherwise.
- Haiku's ability to follow the skill text is measured by the eval stress tier (`evals/git-workflow/tiers.py`, recorded in `evals/git-workflow/stress.md`) as a wording diagnostic, not as a shipped configuration or a CI gate.
- Extends 0007's role split; supersedes nothing.
- Reversal cost: low. One installed file per harness, one dispatch rule and one optional setting.
