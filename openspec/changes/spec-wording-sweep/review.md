# Review

## Metadata

- **Round:** 7 (FULL)
- **Prior round:** REVISE (round 6); guard dropped in fb3ef97
- **Reviewer:** OMP / openai-codex/gpt-6.2-sol
- **Reviewed:** Round 6 review, proposal, design and Allowlist inventory, task map and groups 2 and 5, install-update delta, README Step 8, and the relevant evals and suite map. Confirmed `fb3ef97` in the local reflog; `git show --stat` was unavailable. Static review; no evals run. #243 excluded.

## Findings

### Critical (blocking)

None.

### Moderate

1. **Task 5.2 specifies a narrower warning rule than Step 8.** `tasks.md:368` says to test that the warning appears *only* when the version or interface differs. `README.md:560–569` and `specs/install-update/spec.md:65–82` also require it when the binary is missing or the probe fails. A test that enforced task 5.2 literally would reject correct prompt wording or encourage dropping those warnings. Map source selection to the new standalone-line test and the no-warning outcome to the existing `TestInstallSwWarning.test_matching_binary_gets_no_warning`. Make the standalone-only rule explicit in the requirement, and have the scenario's binary pass the full probe, not just report matching values.
2. **The replacement milestone check disagrees with the roadmap it verifies.** `openspec/roadmap.md:13` allows only the name map and history. Design D1 also accepts five deferred requirements, including `change-finish`'s current instruction to run network steps through `as.sh` (`openspec/specs/change-finish/spec.md:277`). The close workflow walks the roadmap criteria, so a literal close can stop on wording this change intentionally leaves. Link the archived Allowlist inventory from the roadmap, explicitly account for the D3 exceptions, and name separate README evidence for the other half of the criterion. Carry issue IDs #244–#248 into the inventory before deleting the guard that records the mapping.

### Suggestions

None.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

CHANGES_APPLIED: yes

Align task 5.2 and its test map with the actual Step 8 contract. Make the milestone roadmap point to the manual check and state its accepted exceptions and README evidence.

## Rebuttals

- **Round 6 Critical and Moderates 1–2:** Moot. The eval-runner delta is gone, the scanner adds no exemption, and task 5.1 removes both the guard and its suite-map target. Group 2's C1 reference records completed work; no remaining task enforces it.
- **Round 6 Moderate 3:** The fixture now distinguishes prose interface 2 from standalone interface 3, and the README explicitly rejects prose as the source. The requirement and test-map gaps remain as noted above.