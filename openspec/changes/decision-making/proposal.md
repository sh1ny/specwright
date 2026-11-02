# Proposal

## Why

When a change is planned, the agent takes every design decision on its own and the user sees them only by reading `design.md`, so a decision the user would have made differently surfaces late, often during review or apply (#182). Users need to choose how far they are kept in the loop: some want the agent to decide and report, others want the important choices put to them, and some want every choice. This change serves M6 - Packs, change 8 (0.17.0), and advances the exit criteria "every issue in the changes below is closed by a merged PR, with a regression test in `evals/`" and "each change ships as its own release (0.17.0)". It lands before `user-verified-tasks` and `gamedev-pack` so both are planned with it.

## What Changes

- New setting `decision_making` in `openspec/specwright.yaml`: `autonomous` (default), `important` or `all`. Unset means `autonomous`; any other value stops planning before a decision is written, naming the three valid values.
- A decision is a `design.md` Decisions entry, or a scope or non-goal choice in the proposal. Wording, task order and test layout are not decisions.
- `proposal.md`, the first artifact written, gains a `## Decision Making` section: the mode in force and its source, and the scope decisions. It survives an interrupted session, so a resumed one keeps the override and the user's answers.
- Each decision records whether it is important and who chose it. A decision is important when any of these holds: high reversal cost; it binds future changes (contract, data format, config key, boundary: the ADR test); it changes behaviour or settings that users see; it is chosen on weak evidence.
- `autonomous`: the agent decides. `design.md` carries a decision summary table (decision, choice, rejected alternatives, reversal cost, important), and the same table is shown to the user at the end of planning, before apply. Planning does not wait for an answer.
- `important`: each important decision is put to the user before it is written, with 2-4 options, one marked recommended, and an option to discuss; the rest are decided as in `autonomous` and listed in the summary table.
- `all`: every decision is put to the user that way.
- Questions go in batches of at most 4, through the harness's own ask tool (Claude Code, Codex, OMP and pi each have one), so the user picks an option instead of typing. A tool that takes fewer questions or options gets smaller batches and fewer options, always keeping the recommended one and a way to discuss. Plain text with lettered options is only the fallback when no ask tool is usable in the current session or mode.
- A decision the user chose, or stated before planning, is marked `Chosen by: user`, in every mode. A design review's required change or a fix round that would change it goes back to the user; it is never changed silently.
- Decisions changed after planning (a review fix round, a decision found wrong during apply) follow the same mode.
- A user's instruction when a change starts ("ask me everything for this one") overrides the setting for that change only. `proposal.md` records the mode in force and where it came from, so later sessions of the same change keep it.
- The installed `specwright.yaml` template and the README settings block gain `decision_making` with a comment. Init asks no new question.

## Capabilities

### New Capabilities
- `decision-making`: how decisions made while planning a change are classified, recorded, put to the user or reported, per the `decision_making` setting or a per-change override.

### Modified Capabilities

## Impact

- `schemas/specwright/schema.yaml`: proposal, design, review, tasks and apply instructions; `schemas/specwright/templates/proposal.md` (`## Decision Making` section: mode, source, scope decisions) and `schemas/specwright/templates/design.md` (per-decision fields, summary table).
- `templates/openspec/specwright.yaml`, `README.md` (settings block and the planning section).
- New eval module under `evals/git-workflow/` checking the schema, template and README wording; `evals/suites.json` if the map needs it.
- Existing changes in flight: a `proposal.md` with no mode line uses the setting, so nothing already planned has to change.

## Decision Making

DECISION_MAKING: autonomous
- **Source:** setting (this repository sets no `decision_making`; the choices the user stated while this change was discussed are recorded `Chosen by: user`)

### S1: Scope: every change start, not only roadmap next

- **Choice:** the setting applies wherever a change is planned; roadmap **next** inherits it through propose.
- **Rejected:** roadmap **next** only, because a change started by hand would skip it.
- **Reversal cost:** low
- **Important:** yes - user-visible behaviour
- **Chosen by:** user

### S2: Placement in M6

- **Choice:** change 8 at 0.17.0, before `user-verified-tasks` and `gamedev-pack`.
- **Rejected:** after `gamedev-pack`, or folded into `user-verified-tasks`, because the last two M6 changes should be planned with it and one PR should hold one scope.
- **Reversal cost:** low
- **Important:** no
- **Chosen by:** user

## Release Notes

Planning can now keep you in the loop on design decisions. The new `decision_making` setting chooses whether the agent decides and reports a summary table (`autonomous`, the default), puts only important decisions to you (`important`), or puts every decision to you (`all`), each with options and a recommended one.

### Added
- `decision_making: autonomous | important | all` in `openspec/specwright.yaml`, a per-change spoken override recorded in a `## Decision Making` section of `proposal.md`, `Important` and `Chosen by` fields and a decision summary table in `design.md`; a review never changes a user-chosen decision without the user (#182).
