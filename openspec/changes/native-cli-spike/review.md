# Review

## Metadata

- **Round:** 7
- **Prior round:** Round 6 returned REVISE with Critical C1 concerning helper identity and PID reuse.
- **Reviewer:** Cross-model CLI — Codex (GPT-6).
- **Reviewed:** `native-cli-spike/{proposal.md,design.md,tasks.md,review.md,specs/native-cli/spec.md,specs/eval-runner/spec.md}`; ADRs 0002, 0003, 0010, 0011, 0012, 0014, 0021, 0025, 0026 and 0027; `openspec/architecture.md`, including In-force ADRs; cited ranges in `bounded.py`, `test_bounded.py`, `evals/run.py`, `evals.yml`, `evals/suites.json`, `update.sh`, `README.md`, `VERSION` and `openspec/specwright.yaml`; existing bounded-run, helper, frame, tree-stop, inheritance-test and dependency-hook code under `cli/`. Cited source tracking and regular-file status were checked with Git; historical toolchain absence was checked against `e6e17e0`. Static review only. No files modified.

This verdict covers only the contents reviewed. Editing proposal, specs or design afterward (other than applying Required Changes, or an edit confined to the proposal's `## Release Notes` section) voids it.

## Findings

### Critical (blocking)

None. Round-6 C1’s mechanism is addressed by the creation-time check, retained Windows handle, explicit startup failure and stop-before-close ordering, subject to the consistency correction below.

### Moderate

**M1 — State & Ownership still instructs immediate closure of the identity handle.**

`design.md:285` says the parent’s helper-process handle “is closed right after the assignment.” The next row, D1 step 8, task 5.3 and ADR 0027 require retaining `H` until run end.

Following the first row would remove the PID pin needed by subsequent cancellation and PID fallback, restoring the risk the amendment addresses. This is a localized contradiction with an otherwise explicit lifecycle.

**M2 — The pre-hello escape path contradicts the startup-cleanup guarantee.**

D1 step 6 (`design.md:43`) permits returning after five seconds with an unresponsive pre-hello helper still alive, reporting `bounded: helper not stopped`. However, the native-cli startup-limit scenario (`specs/native-cli/spec.md:90`) guarantees that no process `sw` started survives. Flow & State Gaps also describes startup cleanup without this exception.

A helper stalled before its identity frame can therefore satisfy the designed implementation while violating the spec. The held-startup tests begin after hello and cannot establish the unconditional guarantee. This additional survivor case also lacks its own carried constraint; C6 covers parent death, and C11 covers POSIX PID reuse.

### Suggestions

None.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

The revised Windows identity mechanism closes C1’s substantive gap. Two localized consistency corrections remain.

## Required Changes

1. Remove the immediate helper-handle closure instruction from State & Ownership. State consistently that `H` remains open through assignment, cancellation, fallback and pipe cleanup, and closes exactly once at run end.
2. Reconcile the pre-hello survivor path with the spec. If retaining the bounded-wait exception, qualify the startup-cleanup guarantee, update Failure & Visibility and Flow & State Gaps, carry the exception into ADR 0027 through a named constraint and task, and add deterministic pre-hello coverage with a test-owned cleanup mechanism. Preserve the guarantee that the command never starts.

CHANGES_APPLIED: yes

## Rebuttals

- **Round-6 C1:** The identity frame validates the process opened by PID; retaining `H` preserves that identity through later actions. D9’s injected identity seam covers failed opens, mismatches and already-exited processes. M1 identifies the remaining contradictory instruction.
- **ADR 0014:** Assigning the cooperative helper before go addresses its rejected alternative’s concrete harm: no command or descendant can start before assignment.
- **Startup cancellation:** Stopping through `H` before closing stdin removes the EOF-induced Windows cancellation race. The held-before-read fixtures remain appropriate.
- **POSIX residual window:** C11 and ADR 0027 explicitly accept it; the cited Python watcher and PID-based group cleanup support the comparison.
- **A1 and tasks 5.1–5.3:** Verification remains ordered before dependent implementation and covers nested-job assignment, startup death and identity validation. Their design is acceptable; runtime proof remains outstanding.