# Review

## Metadata

- **Round:** 5 (FULL)
- **Prior round:** USER_OVERRIDE after round 4; amendments 14b7799 and 2bbf08d since
- **Reviewer:** OMP / openai-codex/gpt-6.2-sol
- **Reviewed:** Proposal, design, tasks, prior review, all 21 deltas and matching main-spec requirements, both guards, README and its evals, and ADRs 0027/0040/0042. Static review only. The local reflog confirmed both amendments and the preceding task commits; no command tool was available to run `git show` or evals, so the shortened text was checked against the main specs and current implementation rather than the exact parent diff.

## Findings

### Critical (blocking)

1. **S8 exempts executable uses, not just the literals the guard needs.** `design.md:46` and `tasks.md:371` call for skipping the whole module. In `evals/runner/test_oracle_migration.py:76–95`, that bypasses all three checks: retired names, shipped script paths, and frozen-oracle references. **[INFERENCE]** A later edit that copies or runs a retired script from the exempt module would pass this check, even though the amended requirement says the module names scripts only to inspect spec text. Keep the user-selected exemption at that exact path, but allow only the data literals needed by the guard. Keep checking other references in the module and test that an executable use is rejected there.

### Moderate

1. **Task 5.1’s fixture does not pin the path boundary and cannot use `scan()` unchanged.** The two-file fixture at `tasks.md:371` can pass a basename-wide exclusion if the other file has a different name. Also, `scan(root=...)` formats findings relative to the real checkout (`test_oracle_migration.py:95`), so reporting a hit from a temp tree outside it raises `ValueError`. Compare the exact path relative to the supplied eval root, preserve the `evals/...` diagnostic, and assert that a same-basename file elsewhere and a renamed guard are both reported.
2. **The new scenario promises more than the scanner checks.** `specs/eval-runner/spec.md:6,20–22` says “one exception” and “any other eval file.” The scanner already skips itself despite its retired-name literals (`test_oracle_migration.py:26–30,81`), and `reviewers.py` is not in its ordinary literal check. The existing snapshot eval legitimately asserts that name in a diagnostic (`evals/pr-pair/test_snapshot_native.py:128`). State the scanner’s actual scope and self-skip; do not promise rejection of every mention.
3. **The shortened finish requirement lets finish omit recovery instructions.** `specs/change-finish/spec.md:39–44` requires finish to show only `steps`; it requires the planner to emit `after_rerun_steps` and warnings, but not finish to relay them. The skill explicitly shows both (`skills/specwright-finish/SKILL.md:74`). **[INFERENCE]** On a bulk undo, showing only `steps` leaves the user without the instructions to rearchive the non-deferred members and restore saved spec amendments. Require finish to display both lists when present and relay the warnings.
4. **The new Step 8 scenario is marked green without a test for the distinction it adds.** `tasks.md:76` points to an unchanged `evals/update/` test. The actual README check in `evals/git-workflow/test_install_sw_warning.py:30–39` accepts the old interface phrase; it does not require the instruction to take the value from the standalone line rather than prose. Removing that clarification from `README.md:556–559` would leave the mapped verification green. Pin the standalone-line rule and map the scenario to that assertion.

### Suggestions

1. **Fix the integration references.** `tasks.md:5` sends wording-only verification to 5.1, which now runs only the oracle-migration module; the PR CI check moved to 5.2. `design.md:247` still counts 78 modified blocks; S8 makes it 79, consistent with the proposal’s 77 reworded plus 2 changed requirements.

## Verdict

VERDICT: REVISE

## Required Changes

CHANGES_APPLIED: n/a

Narrow S8 and verify its exact boundary; align the eval-runner contract, restore the finish display obligation, and correct the Step 8 test map.

## Rebuttals

- **Round 4 Moderate 2:** Both stamp scenarios now require every other Step 7 check to pass, consistent with `README.md:510`.
- **Round 4 Moderate 3:** The sweep overlay excludes the exact parked verdict. Fixtures cover both the parked case and a nonmatching verdict suffix (`evals/runner/test_spec_retired_names.py:844–854`).