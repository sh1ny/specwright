# Review

## Metadata

- **Round:** 7
- **Prior round:** Round 6 APPROVE; selector clarification requested during apply.
- **Reviewer:** Codex CLI, fresh independent context.
- **Reviewed:** Original round-7 review history: TIER first (`FULL`); `proposal.md`, `design.md`, `tasks.md`, `review.md`, `specs/review-routes/spec.md`, and `evidence/cli-tools.md`; retained OMP prototype events, Codex observer evidence and patch, and TOML package evidence. Applicable ADRs read: 0007, 0014, 0022, 0025–0028, 0031, 0033–0036. Source grounding included the historical script and settings ranges at `cf269784284a15ca0dcbfedd6ea7ae4872c1cbaa`, current OMP policy and tests, review execution/record code, BoundedRun, launcher, architecture index, and CLI workflows. Installed `C:/Users/bgshi/.claude/skills/codebase-design/SKILL.md` supplied guidance; Specwright workflow skills were not used as project guidance.
- **Recheck:** Fresh independent recheck of only the three Required Changes, retaining round 7. Read current `review.md`, `tasks.md` and `design.md`, and verified against tracked `cli/lib/src/review/omp_policy.dart`, `cli/test/review/omp_policy_test.dart`, `cli/lib/src/process/bounded_run.dart`, ADR 0036 and `openspec/architecture.md`. Applied the installed codebase-design guidance.
- **Scope:** Repository files were verified tracked before opening. External links and scratch paths were not followed. No files changed; no builds, tests, linters, formatters or project scripts ran. Historical review coverage above was not repeated as a whole-plan review.

## Findings

### Critical (blocking)

None.

### Moderate

**M1. The selector clarification needs an open implementation task and an explicit carried constraint.**

`design.md:149` requires schema-revalidated replacement with `./`, validation of the effective input, and rejection of a regex-only relaxation. The new automated test at `cli/test/review/omp_policy_test.dart:93–107` asserts the effective replacement. However, the current hook in `cli/lib/src/review/omp_policy.dart` only inspects the original path and returns permission or denial; it does not return replacement input.

This is expected unfinished work during clarification, but `tasks.md:71` leaves task 3.5 checked, and no open task explicitly implements the replacement. Task 6.5 requests evidence rather than implementation. The plan therefore has a new red scenario without an open task to make it pass.

C13 (`design.md:201`) carries the general all-interpretations-local rule, but omits the specific normalization invariant and the rejected regex-only alternative. The new spec scenario preserves the required observable behavior; it does not preserve why widening the guard alone is unsafe. ADR 0026 requires these durable constraints to be listed with one destination and assigned implementation work.

**Round-7 required-change recheck: resolved as a planning finding.** Unticked task 4.11 (`tasks.md:85`) explicitly requires D12’s schema-revalidated `./` replacement, effective-input validation before dispatch, the C13 comment update, passing the existing bare-selector emitted-module case and retaining compound/encoded/aliased remote-denial coverage. It follows 4.10 in group 4, before integration group 6 and native replay 6.5; existing task IDs and the integration CI gate remain intact. C13 now carries normalization and rejects regex-only relaxation because native opaque-resource routing remains reachable, with exactly one durable destination: `doc comment: cli/lib/src/review/omp_policy.dart OmpLocalPolicy`. The current implementation and comment still need the work assigned to 4.11; this resolution does not mark that work complete.

**M2. Current-state grounding still contains stale claims and moved citations.**

- `design.md:29` cites `bounded_run.dart:378–400` for the post-exit `pipesHeld` branch. That range now concerns helper startup/failure handling. The relevant current branch is `bounded_run.dart:522–543`; the field invariant is at `46–50`.
- A5 (`design.md:185`) says the production module “is not implemented yet.” The tracked production module exists, as do completed tasks 3.5 and 4.10. What remains unresolved is the selector amendment and renewed native production acceptance.
- The ADR section still describes ADR 0036 as awaiting recording, although the tracked ADR is accepted and task 1.6 is checked.

These discrepancies obscure which implementation exists and which proof remains outstanding. ADR 0025 explicitly treats moved supporting citations and assumptions settled by current source as claim findings. Correcting them must retain A5’s unresolved production acceptance rather than promote prototype evidence into a pass.

**Round-7 required-change recheck: resolved.** `design.md:29` now cites `bounded_run.dart:46–50,522–543`; those tracked ranges contain the caller invariant and post-exit branch preserving the command exit code while reporting `pipesHeld`. A5 explicitly acknowledges the existing production module and tasks 3.5/4.10 while keeping selector task 4.11 and native acceptance task 6.5 pending. It retains the prototype’s single-root limitation. The ADR section now records ADR 0036 as accepted, matching the tracked ADR’s status and architecture-index entry.

### Suggestions

None.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

S6 and D12 choose a coherent remedy: force explicit local interpretation through supported input replacement, then validate the effective input while preserving fail-closed handling of compound and remote ambiguity. The new scenario maps to an automated emitted-module test. Task 6.5 appropriately requires renewed native proof using the final production bytes, effective local inputs, actual contents, paired denials, fixture counters and failure controls.

The remaining FULL design provisions address ownership, retries, bounds, concurrent runs, stale records and accepted interruption limitations. The findings require planning corrections without changing the user’s chosen policy.

All three Required Changes are verified satisfied in the current planning artifacts. This recheck does not establish completion of task 4.11, passing tests or CI, or native production acceptance under task 6.5.

## Required Changes

1. **Resolved.** Add an **unticked selector implementation task before task 6.5**. Require implementing D12’s schema-revalidated `./` replacement, validating effective input, passing the existing bare-selector emitted-module test, and retaining compound/encoded/aliased remote-denial coverage. Keep task 6.5 open for renewed native proof. Verified in task 4.11 (`tasks.md:85`), placed in group 4 before integration; task 6.5 remains unticked.
2. **Resolved.** Extend **C13**, retaining its single destination `doc comment: cli/lib/src/review/omp_policy.dart OmpLocalPolicy`, to carry the bare open-ended selector normalization rule and the rejection of regex-only relaxation because native opaque-resource routing remains possible. Have the new task explicitly update that comment. Verified in `design.md:201` and task 4.11.
3. **Resolved.** Refresh `design.md`’s current-state grounding: cite `bounded_run.dart:46–50,522–543`; describe A5 as pending selector amendment and production replay despite the existing implementation; and mark ADR 0036 as recorded and accepted. Preserve the distinction between prototype evidence and task 6.5 acceptance. Verified in `design.md:29,185,326`, against the cited tracked BoundedRun source, existing policy module, accepted ADR 0036 and architecture index.

CHANGES_APPLIED: yes

## Rebuttals

None.