# Review

## Metadata

- **Round:** 6 (FULL)
- **Prior round:** REVISE (round 5); fixes in 8808c6a
- **Reviewer:** OMP / openai-codex/gpt-6.2-sol
- **Reviewed:** Amendment message, round 5 findings, proposal, design, task map, affected deltas and main specs, both guards, README Step 8 and its evals, and the finish skill. Static review; no evals run. #243 excluded.

## Findings

### Critical (blocking)

1. **S8 still exempts executable uses of retired names.** `proposal.md` S8, `design.md:46`, and `tasks.md:372` narrow the exemption from all findings to retired-name findings, but still suppress that category across the entire file. **[INFERENCE]** Adding `shutil.copy("vcs.sh", destination)` to the sweep guard would produce only `script vcs.sh` in `test_oracle_migration.py:52–63`; the planned exemption would discard it. Neither new scenario catches that case. Exempt only the identified spec-text data sites at the exact path, and add a same-file fixture that reports a direct copy or run while allowing the legitimate data.

### Moderate

1. **Task 5.1 still misses one path boundary and gives a misleading red step.** A same-basename file outside `runner/` catches a basename-wide exemption, but not one that suppresses retired-name findings throughout `runner/`. Add a renamed guard beside the real one and assert both controls are reported. With the current `scan()`, a hit in a temp tree outside the checkout raises `ValueError` at `test_oracle_migration.py:95` before either fixture can assert its result. Normalize paths first, then show that the exemption test fails on the unexpected guard finding. The scripts-directory and frozen-oracle controls should pass before and after the exemption.
2. **The eval-runner requirement still overstates the scanner’s scope.** `specs/eval-runner/spec.md:6` now names the self-skip, but still says the check fails on “any eval naming a removed script.” The ordinary matcher omits `reviewers.py` (`test_oracle_migration.py:28–30`), and `evals/pr-pair/test_snapshot_native.py:128` legitimately names it in a diagnostic assertion. Define the actual matching scope in the requirement rather than making a valid diagnostic a contract violation.
3. **The Step 8 scenario cannot distinguish the two sources.** `specs/install-update/spec.md:76–78` gives both the prose and the standalone line interface 3, so reading the wrong source produces the same result. Task 5.2 correctly pins the README’s standalone-line instruction, but its mapped test does not assert the no-warning outcome in the scenario. Make the standalone line normative, use a different number in the prose, and map the source-selection and matching-binary no-warning clauses to their respective README assertions.

### Suggestions

None.

## Verdict

VERDICT: REVISE

## Required Changes

CHANGES_APPLIED: n/a

Limit S8 to spec-text data, prove its exact boundary with a behavioral red step, and align the eval-runner and Step 8 scenarios with what their tests assert.

## Rebuttals

- **Round 5 Critical:** Partially fixed. The scripts-directory and frozen-oracle checks remain enabled, but direct uses of a retired basename still escape.
- **Round 5 Moderates 1, 2 and 4:** Partially fixed. Root-relative diagnostics, the self-skip, and the dedicated README test are in the plan; the remaining gaps are above.
- **Round 5 Moderate 3:** Fixed. Finish must show all plan output, including `after_rerun_steps` and warnings, consistent with `skills/specwright-finish/SKILL.md:74`.
- **Round 5 Suggestion:** Fixed. The test-map introduction points to CI task 5.3, and the design counts 79 MODIFIED blocks.