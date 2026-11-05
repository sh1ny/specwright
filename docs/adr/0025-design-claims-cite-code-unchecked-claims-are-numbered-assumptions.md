# 0025. Design claims cite code; unchecked claims are numbered assumptions

- Status: accepted
- Date: 2026-11-05
- Adds to: 0007 (the design review contract gains a claim check; no verdict or route changes)

## Context

A design can say how existing code behaves without anyone checking. The design instruction asked for `file:line` citations of patterns, and for a check on claims that something does not exist. The review had no item on whether a design's own citations hold. In blackgrid's `fix-frozen-map-metadata` (#197), the design cited a 108-line range whose doc comment said the opposite of the claim. Design review passed, and apply stopped after 8 of 14 tasks. LIGHT designs get no independent review at all: the author re-checks only the triage.

Review runs before `tasks.md` exists, so it cannot see whether a task verifies an assumption. The schema, and the agent definitions that defer to it, are what every reviewer route reads (ADR 0007).

## Decision

- **Every claim about existing behaviour cites `path:line` (D3).** That covers what existing code, data or a format does, cited as the narrowest range that shows it. No line cap: a range too broad to show the claim is a finding.
- **Unchecked claims are numbered assumptions (D1).** design.md has a `## Assumptions` section in both tiers, after the Decision summary and above the template's LIGHT boundary. The LIGHT list is "Triage, Context, Decisions and Assumptions". Each entry has an id (`A1`, `A2`...), the claim, why it was not checked, and the decisions or tasks that depend on it (or `none`). The section reads `None` when every claim is cited. A design planned before this rule has no section, which counts as `None`.
- **The FULL review checks claims (D2, D4).** The reviewer re-reads every cited range. Each of these is a finding: a claim with neither a citation nor an assumption entry, a citation that does not show its claim (too broad, moved or missing), and an assumption the code settles. A contradicted claim that a decision or task depends on is Critical; any other claim finding is at least Moderate.
- **The LIGHT re-check re-reads citations.** The author fixes a contradiction in design.md before any verdict. A fix that trips a trigger makes the design FULL.
- **Tasks verify load-bearing assumptions first (D5).** Each assumption with dependents gets a task that names its id and settles it, ordered before the first task that relies on it. A disproved assumption is design drift.

## Consequences

A wrong claim about code the change depends on is caught at review, or by a verify task before dependent work starts, instead of mid-apply. The `## Assumptions` section and its ids are read by the review, the LIGHT re-check and the tasks step in every installed project, so changing the format is a workflow change (minor version). Reversal cost: medium for the section format, low for the rest.

The check is instruction text, not a script (ADR 0002): a script can tell that a range exists, not that it supports the claim. A reviewer that skips the check leaves residual risk, and a wrong cited claim can still surface in apply under the drift rule.
