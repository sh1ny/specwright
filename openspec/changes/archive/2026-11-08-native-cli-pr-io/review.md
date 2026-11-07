Both Required Changes are applied in the design artifacts. I found no new defect in the scoped edits. Filesystem access is read-only, so I could not save `openspec/changes/native-cli-pr-io/review.md`; its content should be:

```markdown
# Review

## Metadata

- **Round:** 3
- **Prior round:** Round 2 was the second consecutive REVISE; escalated to the user, who chose to fix and run round 3.
- **Reviewer:** Codex, fresh review context
- **Reviewed:** All five supplied artifacts; `openspec/architecture.md`; relevant ADRs, main specs, process and VCS implementations; the three scripts and resolver; cited eval fixtures, tests, workflow and suite map.
- **Referenced stores:** `openspec context --json` reported no members or unresolved references.
- **Installed project skills:** none.
- **Re-check:** 2026-11-07, Required Changes 1 and 2

## Findings

### Critical (blocking)

None.

### Moderate

**M1. D6 still loses non-UTF-8 path bytes on POSIX.**

D6 routes `reviewers.py` through `planLaunch` and `BoundedRun`. However, `transportFor` returns arguments unchanged on POSIX (`cli/lib/src/process/transport.dart:38`), and `BoundedRun` passes them through Dart process arguments (`bounded_run.dart:125`, `exec_helper.dart:148`).

Consequently, a valid reviewer config filename containing a non-UTF-8 byte cannot reliably reach Python unchanged. The old script passes that filename directly (`pr-snapshot.sh:134`, `510`). The existing VCS runner explicitly avoids Dart argument encoding for this reason (`tool_runner.dart:171-177`), and D3 acknowledges the same limitation.

This breaks the promised script parity for valid POSIX filenames.

**M2. The accepted nonce-collation gap is not carried forward.**

D9 and the mechanism ledger explicitly accept byte comparison differing from an old watcher's locale comparison for equal claim numbers. C6 carries byte ordering as an invariant, but omits this interoperability exception and the stated reconsideration trigger, observing duplicate ownership.

The destination requirement promises shared ownership without documenting that exception. After archival, a future planner could assume both implementations always elect the same owner, although the design expressly accepts otherwise.

### Suggestions

None.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. Amend D6 and its summary row to transport subprocess argument bytes losslessly on POSIX as well as Windows, while retaining bounded execution and the existing command labels. Add a differential test using a valid reviewer config filename containing a non-UTF-8 byte, covering validation and evaluation.
2. Add a carried constraint for the accepted mixed-watcher collation exception and its duplicate-ownership reconsideration trigger, with exactly one destination. Document that exception alongside the shared-watch requirement so its guarantee matches D9.

CHANGES_APPLIED: yes

## Rebuttals

The current artifacts address round 2 findings C1, C2 and M1–M4 through the revised D2, D3, D6, D10 and D12, the shim-based takeover scenario, and C13–C14. Those findings are accepted as fixed.

- Required Change 1 — Applied in the design artifacts: D6 specifies count-framed, surrogateescape-encoded stdin transport on every OS through `BoundedRun`, retaining logical command labels (`design.md:85`); its summary agrees (`design.md:168`), D12 adds the Linux differential case covering config validation and evaluation (`design.md:137`), and C16 carries the transport invariant (`design.md:200`). The mechanism matches `tool_runner.dart:59-80`, `171-193` and avoids the POSIX argument path in `transport.dart:38-42` and `bounded_run.dart:125-130`.
- Required Change 2 — Applied: C15 records the mixed-watcher collation exception, the observed-duplicate-owner reconsideration trigger, and exactly one destination (`design.md:199`); the destination shared-watch requirement now includes an explicit equal-claim-number scenario documenting possible duplicate ownership as an accepted gap (`specs/pr-script-runtime/spec.md:50-59`).
```