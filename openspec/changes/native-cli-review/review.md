# Review

## Metadata

- **Round:** 3
- **Prior round:** Round 2 returned REVISE with C1–C2 and M1–M3; all five are resolved in the revised artifacts.
- **Reviewer:** Codex CLI, independent review context
- **Reviewed:** Proposal, delta and main review-routes specs, design, schema review instruction, review template, architecture, M8 roadmap change 7, ADRs 0007/0022/0027/0028/0031/0033/0034, and the cited tracked source ranges. Also checked the cited snapshot shim.

## Findings

### Critical (blocking)

None.

### Moderate

**M1 — The shared `context` command does not refuse malformed settings as claimed.**

Design Context and D4 describe `context` as stopping when `yamlProblem` reports a problem. The cited `settings_commands.dart:344-346` computes that problem, but the command subsequently returns `ok: true` with `settings_problem` (`cli/lib/src/pr/settings_commands.dart:378-385`). By comparison, `policy.dart:163-164` explicitly throws on the problem.

Strict refusal in `sw review` is a valid chosen behavior, but describing it as the existing `context` behavior gives implementers the wrong precedent: reproducing that command’s response would fail the new before-probe stop requirement.

**M2 — The 72 MiB figure bounds stream payload, not peak memory.**

D1 and the Resource Bounds table claim at most 72 MiB of memory. `BoundedRun` accumulates stream chunks in `BytesBuilder`, appends a chunk before checking its bound, and later materializes output through `takeBytes()` (`cli/lib/src/process/bounded_run.dart:159-180,388-392`). Answer decoding and event parsing also require memory beyond the captured bytes.

The capture remains bounded, but the stated peak is unsupported and understates the resource cost used to justify rejecting disk-backed capture.

### Suggestions

None.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. Correct Context, D4 and Risks to distinguish the existing commands: `context` reports `settings_problem` while returning `ok: true`; `policy` refuses unreadable settings. Keep the chosen `sw review` refusal and identify it as an intentional behavior change.
2. Replace the “at most 72 MiB” and “memory peaks at 72 MiB” claims with “72 MiB combined stream payload limits, plus chunk overshoot, buffer materialization, decoding and parsing overhead.” Retain the bounded-memory decision without asserting an unmeasured process-memory peak.

CHANGES_APPLIED: yes

## Rebuttals

- **Round-2 C1 — Fixed; accepted by reviewer.** D5 requires OMP ≥18.19.0, the delta specifies selection fallback and explicit-run refusal, and C10 carries the floor.
- **Round-2 C2 — Fixed; accepted by reviewer.** The Failure table and C6 acknowledge orphaned reviewer processes after the parent is killed, consistent with ADR 0027.
- **Round-2 M1 — Fixed; accepted by reviewer.** D2 covers normalized quoted segments and protected ancestor tables; the delta adds a matching refusal scenario.
- **Round-2 M2 — Fixed; accepted by reviewer.** D9 specifies 64 KiB blob copies, with file-count-dependent metadata retained in memory.
- **Round-2 M3 — Fixed; accepted by reviewer.** C7–C10 carry the rejected capture/oracle alternatives, snapshot deadline gap and OMP floor, each to one destination.