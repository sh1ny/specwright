# Review

## Metadata

- **Round:** 8
- **Prior round:** Round 7 returned APPROVE_WITH_CHANGES; both Required Changes were applied. The subsequent D8 amendment voided that verdict.
- **Reviewer:** Cross-model CLI — Codex (GPT-6).
- **Reviewed:** `native-cli-spike` proposal, design, both delta specs, tasks and current review; ADRs 0002, 0003, 0010, 0011, 0012, 0014, 0021, 0025, 0026 and 0027; architecture and its In-force ADRs section; every source range cited by the design, checked against tracked paths; historical toolchain absence at `e6e17e0`; implementation evidence in `kernel32.dart`, `exec_helper.dart`, `command_line.dart`, `bounded_run.dart`, `windows_tree.dart` and `tree_stop.dart`. Static design review; no files modified or tests run.

This verdict covers only the contents reviewed. Editing proposal, specs or design afterward (other than applying Required Changes, or an edit confined to the proposal's `## Release Notes` section) voids it.

## Findings

### Critical (blocking)

None.

### Moderate

None.

### Suggestions

None.

## Verdict

VERDICT: APPROVE

The amended batch launch is consistent with the containment protocol, specs and ADR 0027. Runtime verification remains required by the implementation tasks.

## Required Changes

None.

CHANGES_APPLIED: n/a

## Rebuttals

- **D8 versus rejected Option B:** The helper passes one exact command line to `CreateProcessW` after go. It does not create a suspended process or manage native pipes and read loops. D1’s rejection and ADR 0027 distinguish these mechanisms consistently; D12 and task 6.2 include the additional calls.
- **ADR 0014 and the assignment window:** Before assignment, the cooperative helper starts no command. Assignment precedes go; the batch interpreter subsequently inherits the helper’s job membership. The amendment does not restore the child-escape window ADR 0014 rejected.
- **Identity and stopping:** The batch path introduces no parent-side PID operation. The checked handle remains owned through assignment, stopping, fallback and cleanup. Pre-go cancellation still prevents the command from starting.
- **Limits and batch scenarios:** Output remains on the inherited streams monitored by the parent; deadlines and tree termination remain parent-owned. Refusal precedes process creation, and the test map covers forwarding boundaries, trailing backslashes, injection-shaped arguments, expandable paths and oversized lines.
- **Round-7 findings:** State & Ownership now retains `H` until run end. The pre-hello survivor exception is reconciled across the spec, failure and flow sections, C12, ADR 0027 and deterministic test planning.