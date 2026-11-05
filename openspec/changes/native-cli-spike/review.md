# Review

## Metadata

- **Round:** 5
- **Prior round:** Rounds 1–4 returned REVISE. Round 1 identified startup cancellation, Windows argument integrity, orphan coverage, interrupted-eval cleanup, carried-constraint and citation gaps. Round 2 identified batch caret escaping, incomplete startup fixtures and diagrams, shell-wrapper attribution and contradictory no-retry wording. Round 3 accepted those revisions and left trailing-backslash corruption and expansion of the resolved batch path. Round 4 accepted trailing-backslash doubling, refusal of resolved batch paths containing `%` or `!`, and the earlier fixes, but left C4: post-ready, pre-go cancellation depended on the helper reaching its stdin read. The owner chose to fix C4 and authorized round 5.
- **Reviewer:** OMP, fresh review context; no authoring transcript supplied.
- **Reviewed:** `openspec/changes/native-cli-spike/{proposal.md,design.md,specs/native-cli/spec.md,specs/eval-runner/spec.md}`; `openspec/architecture.md`; ADRs 0002, 0003, 0010, 0011, 0012, 0014, 0021, 0025 and 0026; M7/M8 in `openspec/roadmap.md`; `openspec/specs/eval-runner/spec.md`; every source range cited in `design.md`, including `skills/specwright-pr/scripts/bounded.py`, `evals/pr-pair/test_bounded.py`, `evals/run.py`, `.github/workflows/evals.yml`, `evals/suites.json`, `scripts/update.sh`, `README.md`, `openspec/specwright.yaml` and `VERSION`.
- **Installed project skills:** none.
- **Verification limits:** static review only. No command-execution tool was available; reviewer selection, `git ls-files`, tests and runtime experiments were not executed. Tracking and symlink status remain unverified. The historical main-tree absence claim could not be independently checked. No external owner-project source was opened.
- **Unresolved context reference:** referenced-store discovery through `openspec context --json` could not be executed. Referenced-store context remains unresolved; no external store was opened.
- **Task map:** `tasks.md` is absent; scenario-to-task assignments and assumption-verification ordering could not be checked.

Artifact references below are relative to `openspec/changes/native-cli-spike/` unless otherwise stated. No artifacts were modified.

This verdict covers the reviewed proposal, specs and design. Editing them afterward voids it, except for an edit confined to the proposal’s `## Release Notes` section.

## Findings

### Critical (blocking)

None.

### Moderate

None.

### Suggestions

None.

## Verdict

VERDICT: APPROVE

C4 is addressed at design level. Pre-go cancellation now forcibly stops and reaps the helper regardless of readiness or whether the helper can read EOF. The revised fixture explicitly holds the parent before writing `g`, preventing post-go tree termination from masking a broken pre-go cancellation path.

The whole-change re-review found no additional concrete design defect. Approval does not establish runtime behavior; A1–A6 and the specified cross-platform process, argument and artifact checks remain implementation verification obligations.

## Required Changes

None.

CHANGES_APPLIED: n/a

## Rebuttals

- **Round-4 C4 — Fixed at design level; accepted by reviewer.** D1 step 6 at `design.md:42` requires closing the control pipe without `g`, killing the helper by PID and waiting for its exit, both before and after receiving readiness. Cancellation no longer depends on the helper reaching its stdin read. The post-ready sequence at `design.md:228-231`, startup transition at `design.md:253`, failure row at `design.md:289` and startup discussion at `design.md:314` agree with that rule.

- **Round-4 C4 fixture gap — Fixed at design level; accepted by reviewer.** D9 at `design.md:112` adds the parent-side `SPECWRIGHT_TEST_PRE_GO` gate. The parent marks that it consumed readiness and defers `g` while its deadline continues running; the helper remains held before its stdin read. The fixture requires exit 124 and no surviving helper before releasing the hold, then requires no command-start marker after release. Both startup hold points remain covered on POSIX and on Windows with and without a job. Runtime execution was not available in this review.

- **Round-3 trailing-backslash finding — Remains fixed at design level; accepted by reviewer.** D8 at `design.md:102` accounts for both command-line parsers, doubles trailing backslash runs inside argument quotes and limits the unchanged-value guarantee to native `%*` forwarding. D9 at `design.md:113` and the trailing-backslash scenario in `specs/native-cli/spec.md` require exact values and argument boundaries, including an ordinary and an empty argument after the path arguments.

- **Round-3 resolved batch-path expansion finding — Remains fixed at design level; accepted by reviewer.** D8 refuses a resolved batch path containing `%` or `!` before starting any process. D9 and the corresponding native-cli scenario require refusal of a shim found under a literal `%SW_SLOT%` directory, with neither the intended shim nor the expansion-selected decoy running.

- **Earlier startup, orphan and interrupted-eval findings — Accepted on this re-review.** The ready/go gate preserves containment before command launch; the internal frame is stripped before stderr accounting; the true-orphan fixture requires unconditional recorded-PID assertions; and D6 retains the POSIX spawn record consumed by the existing eval sweep at `evals/run.py:226-244`.

- **Other round-1 and round-2 findings — Accepted on this re-review.** The shell-wrapper attribution matches `bounded.py:394-396` and its cited regression case. The no-retry scenario retains “at most once” and permits zero command starts when startup is cancelled. C1–C10 retain one destination each, including the accepted parent-death gap, deferred migration and distribution scope. The cited current source ranges support their associated claims, subject to the metadata’s tracking and historical-tree verification limits.