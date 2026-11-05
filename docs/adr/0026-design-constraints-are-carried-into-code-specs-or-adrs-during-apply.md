# 0026. Design constraints are carried into code, specs or ADRs during apply

- Status: accepted
- Date: 2026-11-05
- Adds to: 0007 (the design review and the pre-ship review gain a check; no verdict or route changes) and 0025 (a second section beside `## Assumptions`)

## Context

A change's design records constraints later changes must respect: invariants, deliberate gaps, rejected alternatives. Once the change is archived, nothing reads its design again. In blackgrid, an archived design said that some indexed tile sources were deliberately not carried and that vendoring them was rejected. A later change was planned on the opposite assumption, and apply stopped after 8 of 14 tasks (#198). Reading archives wholesale does not scale: its cost grows with history. A fact has to live where the next planner reads anyway, the code it constrains, the main spec or an ADR.

Finish commits only archive paths, and ship treats an archive-only push as already reviewed. A pre-ship pass carries over to it too.

## Decision

- **C1: no archive-time harvest.** Constraints are never harvested when the change is archived. The archive commit holds only archive paths, and code edits made there would ship unreviewed. They are written during apply, so the pre-ship review and the PR review see them.
- **C2: no step reads archived designs for planning.** Once a change is archived its design is history only. Planning reads code, main specs, the architecture file and in-force ADRs, never `changes/archive/`. Nothing is backfilled from archives.
- **C3: the `## Carried constraints` format.** design.md has a `## Carried constraints` section in both tiers, after `## Assumptions` and above the template's LIGHT boundary. The LIGHT list is "Triage, Context, Decisions, Assumptions and Carried constraints". Each entry has an id (`C1`, `C2`...), the fact, its kind (invariant, deliberate gap or rejected alternative), and exactly one destination in one of three forms:
  - `doc comment: <path> <symbol>`
  - `spec: specs/<capability>/spec.md → Requirement: <name>`
  - `ADR NNNN`

  The section reads `None` when nothing outlives the change. A design planned before this rule has no section, which counts as `None`. The design review, the LIGHT re-check, the tasks step and the pre-ship review all read this format.
- **Destination by kind (D2).** A fact about specific code (what an input holds, why a path is not taken) goes in that code's doc comment, where the next planner reads it while grounding. A guarantee users or downstream systems rely on goes in the delta spec. A decision that binds future changes beyond one module goes in an ADR, under the ADR rules. When the constrained code is in a file that cannot hold a comment, the destination is the nearest owning code or the spec.
- **The design review checks the list is complete (D3).** A stated fact a future change could break that is not listed is a Moderate finding, and so is an entry with zero or several destinations. The LIGHT re-check applies the same test: each failure is recorded in review.md as a Moderate finding with no `VERDICT:` line, so the tasks precheck stops. After the author's fix and a passing re-check, review.md gets `VERDICT: SKIPPED_LIGHT` with the findings marked fixed.
- **A task per entry; pre-ship checks each at P1 (D4).** Each entry gets a task that names its id and writes the fact at its destination, ticked only when the text is there. ADR destinations ride the task that writes that ADR file. A destination that is gone or no longer fits during apply is design drift. The pre-ship brief checks each entry at its destination in the reviewed range: a missing entry, or text there that contradicts the design, is P1 `docs`. As in ADR 0025's Claims check, the reviewer opens a destination only when it is a tracked file and not a symlink; an ignored, untracked, outside or symlinked destination is not opened and is itself P1 `docs`. A section that reads `None`, or no section, raises no such finding.

## Consequences

A fact a later change could break lands in a file the next planner reads, and two reviews check that it is listed and that it landed. The cost stays flat as history grows. The section format is read by four workflow steps in every installed project, so changing it is a workflow change (minor version). Reversal cost: medium for the format, low for the rest.

No script parses the section (ADR 0002): a script cannot judge whether a paraphrased comment carries the fact. Residual risk: a later change can edit the code and drop a carried comment. That change's own grounding reads the comment first, and ADR 0025's citation check covers designs that cite it.
