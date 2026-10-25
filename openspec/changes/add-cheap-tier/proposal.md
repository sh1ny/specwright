# Proposal

## Why

Two kinds of Specwright work are long and mechanical but run on expensive models.

- **Watch.** Watch re-enters the orchestrator's full context on every wake. Most wakes need no action: a CI check went from pending to pass while others are still running.
- **LIGHT changes.** A LIGHT change's task groups (doc edits, template blocks, version bumps) go to the Sonnet implementer.

Issue #22 proposes Haiku as a cheap tier for bounded work, evals first. Haiku running the skill evals is also a wording test: where it fails, the instructions are vague.

This is change 6 of milestone **M4 - Cost tier** (0.8.0). It serves these exit criteria:
- The cheap-tier criterion, reworded here: watch has no Haiku agent, because a deterministic wake filter removes the no-op wakes with zero tokens, which is cheaper than any model.
- "Each change ships as its own release" (0.8.0).
- "Each code fix has a regression test in `evals/`".
- "The listed evals pass".

It relies on the exact grader from `exact-eval-grader` (0.7.3), so a Haiku run cannot pass on a missed write or a keyword.

## What Changes

- **Cheap-tier setting.** A new `cheap_tier.enabled` in `openspec/specwright.yaml`, `false` by default and in the template. With it off, apply dispatches exactly as in 0.7.3. `pr-pair.sh tier` reads it. Any value other than `true` counts as off, with a note.
- **`specwright-implementer-light`.** A new agent for Claude Code and OMP: the implementer's instructions word for word, pinned to the cheap model (Claude Code `haiku`, OMP the `pi/smol` role). With the cheap tier on, apply sends the task groups of a `TIER: LIGHT` change to it. A FULL change keeps `specwright-implementer`. The orchestrator verifies and commits as before.
- **Wake filter for watch.** `pr-snapshot.sh --wait --until attention` keeps waiting while the only thing that changed is check progress: checks still pending, no new failing check, no conflict. Anything else wakes it as today: feedback, reviewer state, head, PR state, failing checks, all checks done, a cut-off list. Watch always uses it, whatever the tier setting, so the orchestrator wakes only when it has to act.
- **Eval stress tier.** Evals marked `"stress": "watch" | "light-apply" | "implementer"` are run with the agent under test on Haiku, as a wording diagnostic. This is not a configuration Specwright ships. A new `eval-implementer-light-packet` case runs the light implementer's instructions on a packet directly. The deterministic `evals/git-workflow/tiers.py` compares each stress eval's grade between two configurations and names every difference. The default-vs-Haiku result and a real dispatch trial of the light implementer are recorded in `evals/git-workflow/stress.md`. Each wording gap found is fixed in the skills.
- **Roadmap.** The M4 cheap-tier exit criterion is reworded to match: the LIGHT implementer on Haiku when the tier is configured, with dispatch unchanged when it is not; watch woken only when it must act; stress-tier parity on Haiku.
- **Release 0.8.0**, a minor release, because the change adds a setting, an agent and a watch behaviour.

## Capabilities

### New Capabilities
- `cost-tiers`: which Specwright work may run on a cheaper model tier, the setting that turns it on, the cheap implementer's dispatch, and that reviews and orchestration never move down.

### Modified Capabilities
- `pr-watch`: `--wait --until attention` skips wakes that are only check progress, and watch waits with it.
- `eval-grading`: the stress-tier marks and the tier comparison report.

## Impact

- `agents/claude/` and `agents/omp/`: new `specwright-implementer-light.md`.
- `schemas/specwright/schema.yaml`: the apply DELEGATION rule picks the implementer by tier.
- `skills/specwright-pr/scripts/pr-snapshot.sh` (`--until attention`) and `pr-pair.sh` (`tier`), plus `skills/specwright-pr/SKILL.md` (watch step 1).
- `templates/openspec/specwright.yaml`, this repo's `openspec/specwright.yaml` (left `false`), README (agents table, settings, scripts table), CONTRIBUTING (stress-tier runs).
- `evals/git-workflow/` (`evals.json` marks, new case, `tiers.py` with tests, `stress.md`), `evals/pr-pair/` (filter, `tier` and skill-text tests).
- `openspec/roadmap.md` (the reworded criterion), `openspec/architecture.md` and ADR 0013.
- Version files to 0.8.0. Install and update copy every `specwright-*.md` agent, so they pick up the new one.
