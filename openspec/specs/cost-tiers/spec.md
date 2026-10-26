# cost-tiers Specification

## Purpose

Decides which Specwright work may run on a cheaper model tier, the setting that turns it on, how the cheap implementer is dispatched, and that reviews and orchestration never move to the cheaper tier.

## Requirements

### Requirement: The cheap tier is off unless enabled
`cheap_tier.enabled` SHALL turn the cheap tier on only when it reads as a boolean true (`true` or `yes`, like the other boolean settings). Missing, `false` or `no` SHALL leave it off. Any other value, or a `cheap_tier` that is not a map, SHALL leave it off with a note. `pr-pair.sh tier --code <toplevel>` SHALL print `{"ok": true, "cheap_tier": bool}` plus any `note`, and exit 0 whatever other settings hold. The template SHALL ship `false`.

#### Scenario: Unset leaves dispatch unchanged
- **WHEN** `openspec/specwright.yaml` has no `cheap_tier` key and apply delegates a task group of a LIGHT change
- **THEN** `pr-pair.sh tier` prints `"cheap_tier": false`, and the group goes to `specwright-implementer`

#### Scenario: An unrecognised value is off and reported
- **WHEN** `cheap_tier.enabled` is `on`
- **THEN** `pr-pair.sh tier` prints `"cheap_tier": false` and a `note` naming `on`, and apply's report repeats that note once

#### Scenario: The section is not a map
- **WHEN** the settings hold `cheap_tier: true` instead of `cheap_tier: { enabled: true }`
- **THEN** `pr-pair.sh tier` prints `"cheap_tier": false` and a `note` saying `cheap_tier` must hold `enabled`

#### Scenario: Another setting is invalid
- **WHEN** `pr.merge` is `agent`, `pr.merge_method` is `fast`, and `cheap_tier.enabled` is `true`
- **THEN** `pr-pair.sh tier` exits 0 and prints `"cheap_tier": true`

#### Scenario: The setting cannot be read
- **WHEN** `pr-pair.sh tier` exits non-zero, or its output has no `cheap_tier` field
- **THEN** apply treats the cheap tier as off and says once that the setting could not be read

### Requirement: The light implementer is a pinned copy of the implementer
Specwright SHALL ship `specwright-implementer-light` for Claude Code and for OMP, pinned to the cheap model in its own definition: `haiku` for Claude Code and the `pi/smol` role for OMP. Its body and `tools:` line SHALL match those of `specwright-implementer` for the same harness; only its name, description and model differ. Install and update SHALL copy it along with the other agents.

#### Scenario: Light implementer matches the implementer
- **WHEN** the skill-text tests compare `agents/claude/specwright-implementer-light.md` with `agents/claude/specwright-implementer.md`
- **THEN** the bodies after the frontmatter and the `tools:` lines are identical, and the light file's frontmatter has `model: haiku`

#### Scenario: The instructions drift apart
- **WHEN** a change edits the body of `agents/omp/specwright-implementer.md` and leaves `agents/omp/specwright-implementer-light.md` as it was
- **THEN** the skill-text test fails and names both files

### Requirement: A LIGHT change's groups go to the cheap implementer
With the cheap tier on, apply SHALL send every task group of a `TIER: LIGHT` change to `specwright-implementer-light`, small groups included (no inline exception). A FULL change SHALL keep `specwright-implementer` and today's rule. When `specwright-implementer-light` is not available, apply SHALL use `specwright-implementer` and say so once. The orchestrator SHALL verify and commit each group the same way, whichever implementer did it.

#### Scenario: LIGHT change with the tier on
- **WHEN** `cheap_tier.enabled` is `true` and the change's design has `TIER: LIGHT`
- **THEN** every group, a one-edit group included, goes to `specwright-implementer-light`, and the orchestrator re-runs each task's verification before it commits

#### Scenario: FULL change with the tier on
- **WHEN** `cheap_tier.enabled` is `true` and the change's design has `TIER: FULL`
- **THEN** each delegated group goes to `specwright-implementer`

#### Scenario: Light implementer not installed
- **WHEN** the cheap tier is on, the change is LIGHT, and the harness has no `specwright-implementer-light` agent
- **THEN** the groups go to `specwright-implementer`, and the report says once that the light implementer was not available

### Requirement: Reviews and orchestration never move to the cheap tier
The cheap tier SHALL NOT change the reviewer route selection, the `specwright-reviewer` model, the pre-ship review, watch, or the orchestrator's own model. Only the implementer of a LIGHT change SHALL move.

#### Scenario: Design review with the tier on
- **WHEN** `cheap_tier.enabled` is `true` and a FULL change reaches its design review
- **THEN** `review-run.sh select` picks its route exactly as with the tier off, and the `specwright-reviewer` definition keeps its own model

#### Scenario: A LIGHT change's pre-ship review
- **WHEN** a LIGHT change applied by `specwright-implementer-light` reaches its pre-ship review
- **THEN** the pre-ship review runs on the route `select` picks, never on `specwright-implementer-light`
