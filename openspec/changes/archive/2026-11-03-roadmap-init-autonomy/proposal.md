# Proposal

## Why

`decision_making` (#182, 0.17.0) only covers the planning of a change. Roadmap **init**, **close** and **pack** always run their own interview. A common way to work is the reverse split (#184): the owner wants the roadmap drafted autonomously, for example overnight, and then wants every change started by **next** to put its decisions to them. Today the only way to get the autonomous half is a spoken "take the defaults", which no later session can read. This change serves M6 - Packs, change 10 (0.19.0), and advances these exit criteria:
- "every issue in the changes below is closed by a merged PR, with a regression test in `evals/`";
- "each change ships as its own release (0.19.0, #184)".

It lands before `gamedev-pack`, so a project closing its first milestone keeps the mode its owner chose.

## What Changes

- **New setting** `project.decision_making: autonomous | important | all` in `openspec/specwright.yaml`, beside the roadmap paths. It governs roadmap **init**, **close** and **pack**.
  - Unset means `important`, which is today's interview: only the gaps that would change the architecture or the first milestone are asked, in at most two batched rounds with recommended defaults.
  - Any other value stops the run before anything is written, naming the three valid values.
  - The top-level `decision_making` keeps its meaning for change planning and is not read by the roadmap.
- **`autonomous`**: the roadmap modes ask nothing. Every gap answer, ADR choice and re-plan choice the agent takes becomes a row in a decision summary table in `strategy.md`, with the reason it was chosen. The table replaces the free-form `## Assumptions` list and is shown at the end of the run without waiting.
- **`important`**: as today, with each answer recorded in the same table with who chose it.
- **`all`**: the interview gaps, the foundational ADR choices and close's re-plan choices are all put to the user. They go through the harness's ask tool in batches, as change planning does.
- **Per-run override.** A user instruction when a roadmap run starts ("decide yourself for this roadmap") sets the mode for that run only. It is recorded with the user's words in the table's mode line.
- **Gates are never relaxed by autonomy.**
  - After 2 consecutive `VERDICT: REVISE` baseline rounds, an autonomous run stops. It writes no roadmap, leaves the ADRs `Status: proposed`, keeps round 2's review in `openspec/architecture-review.md` (the review script replaces the file each round), records the escalation as a summary row awaiting the owner that carries round 1's findings, and leaves the decision to the owner.
  - The agent never marks a user-verified exit criterion passed.
  - The agent never records a Next split as agreed.
  - The agent never publishes a release without the owner's yes.
- **Docs:** the `specwright.yaml` template, the README settings block and the roadmap skill's `strategy.md` reference template describe the key and the table.

## Capabilities

### New Capabilities

### Modified Capabilities
- `project-planning`:
  - roadmap init, close and pack follow a decision mode from `project.decision_making`, or from a per-run override;
  - agent-chosen answers are recorded in a decision summary in the strategy;
  - autonomous runs stop at the baseline escalation instead of passing it;
  - the init and pack question requirements depend on the mode.

## Impact

- `skills/specwright-roadmap/SKILL.md` (init, close, pack and Rules) and `skills/specwright-roadmap/references/strategy.md` (the decision summary replaces Assumptions).
- `templates/openspec/specwright.yaml` and `README.md` (settings block and the roadmap section).
- `skills/specwright-pr/SKILL.md` feedback step 7: a fix confined to the strategy's decision summary on a `docs/project-baseline` or `docs/close-*` branch does not re-run the baseline review.
- `openspec/architecture.md`:
  - a Contracts bullet for the new key and the strategy table, since later runs read them;
  - the design-review rule row, which gains the summary-section exception.
- A new eval module under `evals/git-workflow/` checking the skill, template and README wording. `evals/suites.json` already maps `skills/**`, `templates/**` and `README.md` to that suite.
- Existing projects: an unset key keeps today's interview. A strategy with an `## Assumptions` list is read as it is and is not rewritten.

## Decision Making

DECISION_MAKING: important
- **Source:** setting

### S1: Setting shape and default

- **Choice:** a nested key `project.decision_making: autonomous | important | all`. Unset means `important`, today's interview. The top-level `decision_making` stays change-only.
- **Rejected:**
  - A map form of `decision_making` (`{ roadmap, change }`): every reader of the key would have to handle two shapes.
  - A separate top-level `roadmap_decision_making`: a second sibling key with the same values.
  - Falling back to `decision_making` when unset: the default `autonomous` would silently drop init's interview for every existing project.
- **Reversal cost:** medium. Moving a key projects already set needs a migration note.
- **Important:** yes. It is a config key users see.
- **Chosen by:** user

### S2: Roadmap modes covered

- **Choice:** init, close and pack: every roadmap mode that asks the user planning questions.
- **Rejected:** init and close only, as the issue named them. `pack` would then still stop an unattended run for its questions.
- **Reversal cost:** low
- **Important:** yes. It changes behaviour users see.
- **Chosen by:** user

### S3: Where agent-chosen answers are recorded

- **Choice:** a decision summary table in `strategy.md` that replaces the free-form `## Assumptions` list. It holds the mode line and one row per decision: decision, choice, rejected, reason, important, chosen by.
- **Rejected:**
  - The top of `roadmap.md`: the roadmap would grow at every close and stop being only a plan.
  - A new `openspec/roadmap-decisions.md`: one more file and one more `project:` path.
- **Reversal cost:** medium. Later runs read the table.
- **Important:** yes. It binds a format later runs read.
- **Chosen by:** user

### S4: Baseline escalation in autonomous mode

- **Choice:** after 2 consecutive REVISE rounds the run stops, records the escalation, writes no roadmap and leaves the ADRs proposed. The gate is never passed by the agent.
- **Rejected:**
  - Proceeding as an agent override, as the issue sketched: the agent would pass its own gate.
  - More rounds before stopping: more review cost, and it still has to stop somewhere.
- **Reversal cost:** low
- **Important:** yes. It changes behaviour users see.
- **Chosen by:** user

### S5: Per-run override and change planning untouched

- **Choice:** a spoken instruction sets the mode for one roadmap run and is recorded with the user's words. Changes started by **next** keep following `decision_making` and their own per-change override.
- **Rejected:** having no override. The issue asks for one, and the roadmap entry says roadmap planning follows a decision mode "the way change planning follows `decision_making`".
- **Reversal cost:** low
- **Important:** yes. It changes behaviour users see.
- **Chosen by:** user (stated in the roadmap entry for this change and in #184)

## Release Notes

Roadmap planning now has its own decision mode. `project.decision_making` (`autonomous`, `important` or `all`; unset keeps today's interview) decides how far roadmap init, close and pack ask you. With `autonomous`, a roadmap can be drafted while you are away: every answer the agent chose is listed in a decision summary in `strategy.md` for later review. The agent never agrees anything for you: packs, splits, user checks, releases and a stuck baseline review wait for you. Changes still follow `decision_making`, so they can still put every decision to you.

### Added
- `project.decision_making` for roadmap init, close and pack, a per-run override, and a decision summary table in `strategy.md`; an autonomous run stops at the baseline escalation and never passes a gate itself (#184).

### Changed
- An edit confined to the strategy's decision summary no longer voids the baseline review verdict, in roadmap runs and in PR feedback fixes (#184).
