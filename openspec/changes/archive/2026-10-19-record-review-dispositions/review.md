# Review

## Metadata

- **Round:** 1 (re-check run: verifies only Required Changes 1-4 from round 1 and whether the applied edits contradict each other; the design was not reviewed again)
- **Prior round:** round 1 returned APPROVE_WITH_CHANGES with Required Changes 1-4 (M1 managed context-line prefix, M2 baseline gate list, M3 how a parking change reaches main, M4 restore guidance) and suggestions S1-S3
- **Reviewer:** fresh-context subagent (specwright-reviewer, Claude Code)
- **Reviewed:** review.md (round 1 + Rebuttals), proposal.md, design.md, specs/design-review-gate/spec.md, specs/review-routes/spec.md, specs/project-planning/spec.md; evidence: README.md install Step 5 (context merge, lines 254-262), templates/openspec/config.yaml (`context:` lines), skills/specwright-pr/SKILL.md (watch Archive before merge, Merge), skills/specwright-roadmap/SKILL.md (init step 5, next steps 1-3), openspec/architecture.md (baseline review row). Installed project skills: none.

<!-- This verdict covers only the contents reviewed. Editing proposal, specs or design afterward (other than applying Required Changes) voids it. -->

## Findings

### Critical (blocking)

None.

### Moderate

None. Required Changes 1-4 are applied, as checked below.

- **RC1 (M1), applied.** D3 item 1 gives the line the fixed opening `MANDATORY: Before archiving a change (...)`. D3 also adds that prefix to README Step 5's managed-line list and calls for an instruction test asserting that every template `context:` line starts with a managed prefix. Proposal Impact lists "README install Step 5 (its managed-line prefixes)". None of the five current template lines (`templates/openspec/config.yaml:4-8`) breaks the new test: each starts with `MANDATORY: Invoke the 'specwright-`, `Project-level planning (strategy` or `Specwright settings (`. The new opening does not overlap the existing `MANDATORY: Invoke the 'specwright-` prefix, so Step 5's remove-then-append now replaces the line.
- **RC2 (M2), applied.** D6 replaces the cross-reference in roadmap init step 5 with an explicit list and excludes `DEFERRED`, `WAIVED` and `SKIPPED_LIGHT`. It also updates the architecture.md baseline row. The project-planning spec adds "The baseline gate passes only a review or an escalation", with the WAIVED/DEFERRED scenario. Proposal What Changes, Capabilities and Impact all match.
- **RC3 (M3), applied.** D5 says a parking change reaches main only through the user's merge: `--no-ff` by hand in local mode, or on GitHub in pr mode. Watch's Archive before merge skips a `DEFERRED` change and reports it as parked. The State & Ownership row now reads "then main through the user's own merge (D5)". The design's claim that agent merge then merges nothing holds: the existing Merge rule merges a branch only when it has the archive directory, and otherwise sends nothing ("a branch without the archive directory is not a change: merge nothing", `skills/specwright-pr/SKILL.md` Merge). D5 covers next and status on the parking branch. The spec adds "A parking change lands without archive" (watch scenarios) and "Next run on the parking change's branch". Impact lists `skills/specwright-pr/SKILL.md`.
- **RC4 (M4), applied.** D3 item 2 and the "Archive ran anyway" scenario now list three things separately: modified main specs (`git restore -- <file>`, with the uncommitted-edits warning), created main specs (the user deletes them), and the change directory (`git restore` when it was committed, otherwise move it back from the archive). Finish runs none of these.
- **Consistency of the applied edits.** No contradiction found. The Failure table's apply-gate row, the new pr-mode Risks entry (S1) and D5 agree: watch reports the change as parked, and only a user merge can land it. The Bulk-archive flow gap and D3 item 2 agree, because finish step 0 checks each archived change. The proposal's "A parking change lands without archive" bullet matches the design-review-gate requirement.

### Suggestions

**S4.** The Tests bullet in proposal Impact does not yet name three tests the applied changes call for: the managed-prefix assertion (D3), the watch parked-change skip, and the baseline-gate list (D6). The M1 rebuttal says the test is in "proposal Impact", but only D3 names it. Add all three to that bullet, so the task list built from the proposal does not miss them.

**S5.** D5 says **status** on the parking branch also reports that the parking change is on its own branch. The new project-planning scenario covers **next** only. A matching status scenario would make that part testable too. This is optional: Required Change 3 asked only for the next scenario.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. **D3 / Impact / README Step 5 (M1).** In D3 item 1, give the new `context:` line a fixed opening, for example `MANDATORY: Before archiving a change (/opsx:archive, /opsx:bulk-archive, openspec-archive-change, 'openspec archive'), read its review.md ...`. Add that exact prefix to the managed-line prefixes in `README.md` install Step 5, and list `README.md` Step 5 in Impact. Add a `evals/git-workflow/test_instructions.py` assertion that the template's every `context:` line starts with one of the managed prefixes Step 5 names. (Applied.)
2. **Baseline gate (M2).** Add to Impact and to a decision (D4 or a new D6): `skills/specwright-roadmap/SKILL.md` init step 5 replaces "passes the same precheck as tasks" with its own explicit list (APPROVE; APPROVE_WITH_CHANGES with `CHANGES_APPLIED: yes`; USER_OVERRIDE after escalation), and states that `DEFERRED`, `WAIVED` and `SKIPPED_LIGHT` never pass the baseline. Add a scenario to `specs/project-planning/spec.md`: WHEN `openspec/architecture-review.md` holds `VERDICT: WAIVED` or `VERDICT: DEFERRED`, THEN init writes no roadmap and accepts no ADR. Update `openspec/architecture.md`'s baseline row (line 111) to say neither verdict is written there. (Applied.)
3. **Parking change's home (M3).** In D5 (and its State & Ownership row), state how a parking change reaches the planning repo's main without archive. For example: the user merges its planning-only branch by hand (local) or merges its PR (pr), and watch's archive-before-merge and agent merge do not apply to a change whose `review.md` is `DEFERRED` (watch reports it as parked and merges nothing). Also say what **next** and **status** do when run on the parking change's branch: they say the parking change is on its own branch and that next starts from main. List `skills/specwright-pr/SKILL.md` in Impact if watch changes. Add a project-planning scenario for next run on the parking branch. (Applied.)
4. **Restore guidance (M4).** In D3 item 2 and the "Archive ran anyway" scenario, have finish step 0 list main specs in two groups: modified (tracked) ones, restored with `git restore -- <file>`, with a warning that this also discards the user's own uncommitted edits in that file, and created (untracked) ones, which the user deletes. List the change directory's restore separately: `git restore -- <P>/changes/<name>/` when it was committed, otherwise move it back from the archive directory. Finish still runs none of these. (Applied.)

<!-- yes (applied, and re-checked by the reviewer - only the reviewer sets it) | no (outstanding) | n/a (any other verdict) -->
CHANGES_APPLIED: yes

## Rebuttals

- **M1** fixed: design D3 item 1 gives the line the fixed opening `MANDATORY: Before archiving a change (...)`; README Step 5 adds that prefix; an instruction test asserts every template `context:` line starts with a managed prefix (proposal Impact). (accepted by reviewer) The test is named in D3; see S4 for adding it to the proposal's Tests bullet.
- **M2** fixed: new D6; project-planning spec adds "The baseline gate passes only a review or an escalation" with a WAIVED/DEFERRED scenario; Impact lists roadmap init step 5 and the architecture.md baseline row. (accepted by reviewer)
- **M3** fixed: D5 now says a parking change reaches main through the user's merge; watch's archive-before-merge skips a DEFERRED change and reports it parked, and agent merge sends nothing (its existing archive-directory rule); next/status on the parking branch say so and start nothing. Specs: design-review-gate "A parking change lands without archive"; project-planning "Next run on the parking change's branch". Impact lists `skills/specwright-pr/SKILL.md`. (accepted by reviewer)
- **M4** fixed: D3 item 2 and the "Archive ran anyway" scenario list modified specs (`git restore`, with the uncommitted-edits warning), created specs (delete), and the change directory restore separately; finish runs none. (accepted by reviewer)
- **S1** fixed: the Failure row no longer credits the pre-ship review; a Risks entry records the pr-mode residual risk and why ship does not check the verdict (it would block the parking change's own PR). (accepted by reviewer)
- **S2** fixed: the "Apply on a deferred change" THEN says applying needs a design review first. (accepted by reviewer)
- **S3** fixed: D1 adds the Reviewer values `none (DEFERRED by the user)` / `none (WAIVED by the user)` for the template. (accepted by reviewer)
