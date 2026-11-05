# Proposal

## Why

A change's design records constraints that later changes must respect: invariants, deliberate gaps, rejected alternatives. Once the change is archived, nothing reads its design again. In blackgrid (2026-11-05), the archived design of `unpin-map-toolchain` said that 477 of 8,960 indexed tile sources are deliberately not carried by a generation, and that vendoring them was rejected. Three days later `fix-frozen-map-metadata` was planned on the opposite assumption, and apply stopped after 8 of 14 tasks (#198). Reading archives wholesale does not scale. The fact has to live where the next planner reads anyway: the code it constrains, the main spec, or an ADR. This also answers #190, which asks how learnings carry from one change to the next.

This change is inserted into M7 (Native CLI foundation), after `verify-design-claims` and ahead of `native-cli-spike`, by the user's choice. It changes only instructions, templates and the pre-ship brief, not the scripts M7 migrates. It advances the criterion "All M7 changes are archived on main and their releases are published" for itself.

## What Changes

- **Carried constraints:** design.md gets a `## Carried constraints` section in both tiers. Each entry (`C1`, `C2`...) names one fact a future change must respect, and its destination:
  - a doc comment on the code it constrains (code-level facts),
  - a requirement in this change's delta spec (behavioural guarantees), or
  - an ADR (decisions that bind future changes).

  The section reads `None` when nothing outlives the change.
- **Tasks:** each entry gets a task that writes it at its destination during apply, as ADR files are written today. The constraint ships with the reviewed code, not in the archive commit.
- **Design review:** the FULL review and the LIGHT re-check flag a constraint the design states but does not list (a rejected alternative, an invariant, a deliberate gap a future change could break).
- **Pre-ship review:** the brief checks that each entry is present at its destination in the diff. A missing one is P1 and blocks ship.
- The archive commit and finish are unchanged. Once a change is archived its design is history only, and no workflow step needs to read it.

## Capabilities

### New Capabilities
- `design-constraints`: how a design lists the constraints a future change must respect, where each is carried (doc comment, spec, ADR), and how the design review and tasks handle the list.

### Modified Capabilities
- `preship-review`: the brief checks each carried constraint against the diff.

## Impact

- `schemas/specwright/schema.yaml`: design instruction (the new section and its destinations), review instruction (the completeness check, LIGHT re-check), tasks instruction (a task per entry).
- `schemas/specwright/templates/design.md`: the `## Carried constraints` section above the LIGHT boundary.
- `skills/specwright-review/references/brief.md`: the carried-constraints check.
- `docs/adr/0026-*.md` and the architecture index: the section's format and consumers.
- `README.md`, `openspec/roadmap.md` (M7 entry, if `verify-design-claims` has not already added it), and wording tests under `evals/git-workflow/` and `evals/review-routes/` as needed.
- This change follows `verify-design-claims` (#197), which edits the same design instruction, template and LIGHT list. It is applied on top of that change once it is on main.

## Decision Making

DECISION_MAKING: important
- **Source:** setting

### S1: Constraints are carried during apply, not at archive

- **Choice:** the design lists the constraints and apply writes them at their destinations, so the pre-ship review and the PR review see them.
- **Rejected:** a harvest step in `specwright-finish` before archive, as #198 proposes. Finish runs after `openspec archive`, and its archive commit holds only archive paths. Ship treats that commit as archive-only, with no new review. Code doc comments edited there would ship unreviewed.
- **Reversal cost:** low
- **Important:** yes (changes behaviour users see)
- **Chosen by:** user

### S2: The record is the design.md section, not the archive commit

- **Choice:** `## Carried constraints` is the record of what was carried and where. The archive commit stays as it is.
- **Rejected:** a `harvested: N items → files` line in the archive commit. It needs a new finish rule, and it records after the fact what the design and the pre-ship review already show.
- **Reversal cost:** low
- **Important:** yes (changes behaviour users see)
- **Chosen by:** user

### S3: Forward only, no backfill

- **Choice:** only changes planned after this one carry constraints. Archived designs are not walked.
- **Rejected:** a backfill mode that walks archived designs and proposes carries. Its cost grows with history, which is the scaling problem this change avoids. A project can backfill a known case by hand.
- **Reversal cost:** low
- **Important:** no
- **Chosen by:** user

### S4: The pre-ship review checks destinations

- **Choice:** the pre-ship brief checks each entry against the diff, and a missing one is P1.
- **Rejected:** relying on ticked tasks alone, which lets a task be ticked with the comment left out.
- **Reversal cost:** low
- **Important:** yes (changes behaviour users see: ship can block)
- **Chosen by:** user

### S5: Closes #190

- **Choice:** this change closes #190. Knowledge goes where the next change reads anyway, so the cost stays flat as history grows.
- **Rejected:** keeping #190 open for an append-only `learnings.md`, which every planner would have to read and which grows without bound.
- **Reversal cost:** low
- **Important:** no
- **Chosen by:** user

## Release Notes

Designs now list, in both tiers, the constraints a later change must respect: invariants, deliberate gaps and rejected alternatives. Each goes where the next planner reads anyway: a doc comment on the code, a spec requirement or an ADR. Apply writes it there in a task. The design review and the LIGHT re-check flag a constraint left off the list, and the pre-ship review blocks ship when one is missing at its destination. Once a change is archived, no step reads its design again (ADR 0026; #198, #190).

### Added
- A `## Carried constraints` section in design.md. Each entry names its destination, and a task writes it during apply (#198).
- The pre-ship review blocks ship when a carried constraint is missing from its destination (#198).

### Changed
- The design review and the LIGHT re-check flag a constraint the design states but does not list (#198).
