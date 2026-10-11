# Review

## Metadata

- **Round:** 1
- **Prior round:** none
- **Reviewer:** fresh-context subagent (Claude Code, specwright-reviewer)
- **Reviewed:** `proposal.md`, `design.md`, `specs/project-planning/spec.md`, `specs/planning-stores/spec.md` (this change); main specs `openspec/specs/project-planning/spec.md` and `openspec/specs/planning-stores/spec.md`; `openspec/architecture.md` and in-force ADRs 0001-0006 (index); `openspec/roadmap.md`; `skills/specwright-roadmap/SKILL.md`, `skills/specwright-roadmap/references/roadmap.md`, `skills/specwright-branch/SKILL.md`, `skills/specwright-finish/SKILL.md`; `evals/git-workflow/evals.json`, `fixtures.py`, `grade.py`, `test_instructions.py`; issues sh1ny/specwright #51, #60, #66. Checks run: `openspec validate fix-roadmap-milestone-end --strict` (valid). In a scratch copy of `openspec/`: `openspec validate --specs --strict` fails on `planning-stores` before archive, and after `openspec archive fix-roadmap-milestone-end --yes` all 10 specs pass, which confirms the design's claim. Referenced stores: none.

<!-- This verdict covers only the contents reviewed. Editing proposal, specs or design afterward (other than applying Required Changes) voids it. -->

## Findings

### Critical (blocking)

None.

### Moderate

**M1. The split requirements leave their scenarios with the old requirement, which contradicts the proposal and leaves the new requirements under-tested.**
The proposal says "the split-off behaviour becomes its own requirement with the scenarios that test it". D4 says the MODIFIED requirement "keeps ... every scenario", and the delta follows D4. As a result, each shortened requirement still carries scenarios for behaviour its text no longer states:
- **Commands run where they resolve correctly** keeps "Private store readable only by the store login" and "Store login has no credential". Both test the network-read login rule, which now lives in **Git network reads authenticate as each repo's login**.
- **Watch covers the expected PR set** keeps "Store snapshot of an old head", "Snapshot of another PR" and "Snapshot without a head". All three test **A snapshot counts only for the PR and head discovery reports**, which itself has only "matches" and "code snapshot of an old head". The other-PR and no-head failure cases therefore sit under a requirement that no longer states them.
- **Feedback rounds span the PR pair** keeps "Round limit across both repos", "Recovered partial fix" and "Legacy branch without trailers". These test **Fix rounds are counted across both branches**.
- **An interrupted feedback pass is completed first** keeps "Review requests disabled", "Pass with an open question thread", "Reply posted, reaction not sent", "Reaction already present" and "Code PR adopted before the pair was linked". These test **A pass record is removed only when its pass is done**.

Consequence: verification maps scenarios to the wrong requirement, and the two copies drift apart. "Store login has no credential" and "Store login has no credential for a read" already say nearly the same thing in two places. A later MODIFIED of the new requirement would not touch the old requirement's scenarios that test it. Moving the scenarios changes no behaviour and keeps every scenario, so D4's "No behaviour changes" still holds.

**M2. The `Split agreed:` marker's lifetime contradicts the spec scenario and the Risks claim.**
The State & Ownership table says the line lives "until close promotes that milestone to Now, where the line is dropped". The case where close writes the marker is "Next lists changes without a recorded agreement": on yes close "keeps the four changes and records the agreement with that day's date". Close is promoting that same milestone in that run. So under the design the marker is written and dropped in the same commit, while the spec's THEN asserts that it is recorded. A grader written from the spec would look for a `Split agreed:` line that the design removes.

Risks / Trade-offs also says that "on yes close writes the marker, so the next close does not ask again". That is false: the next close examines a different Next milestone. Both texts need to describe the same behaviour. One option is that the line is kept, or moved, when the milestone becomes Now. The other is that on yes close keeps the split and records nothing, in which case the Risks sentence goes.

**M3. The rollback's scope ("each repo where `<branch>` exists") is wider than the repos the gate branched, and the ledger's premise for it is false for store-only roadmap gates.**
The ADDED requirement **A failed store gate branch leaves no new branch** says the gate SHALL, "in each repo where `<branch>` exists, switch back to that repo's main and delete `<branch>`". The Mechanism Ledger rejects tracking which repos were branched because "Step 2 guarantees `<branch>` existed in neither repo". However, roadmap Committing project files step 2 (`skills/specwright-roadmap/SKILL.md:34`) checks the code repo only "when project files are written in the code repo too". For a store-only init or close, the code repo's branch, cleanliness and existing branches are never checked.

Consequence: if the code checkout already has a `docs/close-<m>` (for example from an earlier attempt before the project moved its planning to a store), a store-side hook failure would make the gate switch that untouched code checkout to main, possibly carrying a dirty tree, and delete the branch. D3 already says "each repo the gate may have branched". The spec and the skill text should say the same thing. This needs no runtime record, because the set is static: the store, plus the code repo only when the gate ran `git checkout -b` there.

**M4. A hook-failure scenario is misnamed, and the evals and spec scenarios cover different paths.**
In the planning-stores delta, the scenario "Code hook fails after the store branch exists" has a WHEN that describes the opposite case: `specwright-branch` created the code branch and the store's hook fails. D5 lists:
- `eval-store-roadmap-close-hook-fail`: "a failing `post-checkout` in the code repo after the store branch exists" (close). No spec scenario describes this case.
- `eval-store-branch-hook-fail`: store hook after the code branch. This matches the misnamed scenario.

The spec's "Store hook fails after the branch is created" scenario for close (store hook first, nothing in the code repo yet) has no eval. Tasks derived from the scenarios would build a fixture from the misleading title, and the close/code-hook path that D5 tests has no requirement scenario to verify against.

### Suggestions

- **S1. The proposal's version rationale contradicts the design's triage.** Proposal Impact says "no setting or file format changes". Design T4 says the `Split agreed:` marker extends the `roadmap.md` format that next, status and close parse, and close gains a new question to the user. Under the pre-1.0 versioning rule (`openspec/strategy.md`; `openspec/architecture.md:91` treats changes to parsed formats as workflow changes), state why an additive, optional marker still counts as a fix (0.1.12), or let the user decide. The roadmap already fixes 0.1.12 for this change.
- **S2. Existing text checks will break.** `evals/git-workflow/test_instructions.py:239-242` (`test_roadmap_store_checks_code_repo_before_any_branch`) asserts the current per-case wording of roadmap step 3: "store's `git checkout -b` errors ... releas", and a fail-then-switch-store-then-delete pattern. The one-rule rewrite will likely fail these regexes. Name the update in D5 or the tasks so that the change does not delete the checks without replacing them.
- **S3. The out-of-scope rationale for single-repo `specwright-branch` is slightly wrong.** After a hook failure the repo is left on the new branch, so a retry stops first at step 4 ("Not on main", `skills/specwright-branch/SKILL.md:18`), which offers to switch to main. It reaches step 7's resume offer only after that. The call still holds, but the proposal and Mechanism Ledger should describe this two-stop recovery accurately.
- **S4. A Next split can be agreed only at init.** **An agreed Next split is recorded** covers only init, and the State table lets close write the marker only after confirming an unmarked list. When close promotes Later into the new Next and the author agrees its split then (or at any time mid-milestone, as in #51's downstream case), no rule records it. The author must hand-write the marker, or the next close will ask. Consider letting close (and an explicit user request) record an agreed split for the new Next.
- **S5. Say whether the rollback continues to the other repo when one repo fails to switch back.** D3 and the Failure table say "delete nothing there ... stop naming the repo". It is ambiguous whether the other repo is still rolled back first. Say that it is, so that one stuck repo does not leave both on `<branch>`.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. **M1:** In `specs/planning-stores/spec.md`, move the scenarios that test split-off behaviour from each MODIFIED requirement to the ADDED requirement that now states it:
   - "Private store readable only by the store login" and "Store login has no credential" → **Git network reads authenticate as each repo's login**.
   - "Store snapshot of an old head", "Snapshot of another PR" and "Snapshot without a head" → **A snapshot counts only for the PR and head discovery reports**.
   - "Round limit across both repos", "Recovered partial fix" and "Legacy branch without trailers" → **Fix rounds are counted across both branches**.
   - "Review requests disabled", "Pass with an open question thread", "Reply posted, reaction not sent", "Reaction already present" and "Code PR adopted before the pair was linked" → **A pass record is removed only when its pass is done**.

   Drop any newly written ADDED scenario that then duplicates a moved one. Update D4's "keeps ... every scenario under MODIFIED" so that it matches the proposal ("the split-off behaviour becomes its own requirement with the scenarios that test it").
2. **M2:** Make the marker's lifetime consistent in the State & Ownership row, D2, the Risks bullet and the project-planning scenario "Next lists changes without a recorded agreement". Either keep the `Split agreed:` line when the milestone becomes Now (and say so), or have close on yes keep the split without writing a marker and delete "and records the agreement with that day's date" from the scenario. Either way, remove the false claim "so the next close does not ask again".
3. **M3:** In the planning-stores ADDED requirement **A failed store gate branch leaves no new branch**, replace "in each repo where `<branch>` exists" with "in each repo where the gate ran `git checkout -b` and `<branch>` exists". In the Mechanism Ledger row "Record of which repos this run branched", correct the premise: step 2 checks the code repo only when project files are written there, and the scoping is static. D3's wording already matches.
4. **M4:** Rename the planning-stores scenario "Code hook fails after the store branch exists" to "Store hook fails after the code branch exists". Add a scenario for close where the code repo's `post-checkout` hook fails after the store branch exists: both repos end on main, `docs/close-m1` is in neither, the lock is released and the hook's error is shown. That scenario is the one `eval-store-roadmap-close-hook-fail` tests.

<!-- yes (applied, and re-checked by the reviewer - only the reviewer sets it) | no (outstanding) | n/a (any other verdict) -->
CHANGES_APPLIED: yes

## Re-check (round 1)

The reviewer re-checked only Required Changes 1-4, against the files on disk.

- **1 (M1):** The rebuttal is accepted (see Rebuttals). The proposal (#66 bullet) and D4 now quote the schema rule. The near-duplicate scenario is gone.
- **2 (M2):** Resolved. The requirement text, the "Close promotes an agreed split" THEN (no `Split agreed:` line), the unmarked-list scenario (no line written), D2, the State & Ownership row and the Risks bullet are consistent. The false claim is removed.
- **3 (M3):** Resolved. The requirement reads "in each repo where it ran `git checkout -b` and `<branch>` exists", and the Mechanism Ledger row states the static scope.
- **4 (M4):** Resolved. The scenario is renamed "Store hook fails after the code branch exists", and "Code hook fails after the store branch exists" is added for close.

`openspec validate fix-roadmap-milestone-end --strict` still passes. All four items are resolved, so CHANGES_APPLIED is set to yes.

## Rebuttals

<!-- Author: fixed (cite) or rebutted (reason) per finding. A Critical/Moderate rebuttal counts only once marked "accepted by reviewer". -->

- **M1 — rebutted in part, fixed in part. Accepted by reviewer:** the schema's spec instruction requires that a split keep "every scenario" under MODIFIED, so the scenarios stay. The proposal and D4 now agree with that rule, and the duplicate scenario is replaced by "Code remote accepts only the code login". The schema's spec instruction (`openspec instructions specs`) governs exactly this split: "Split an existing long requirement only when the user asks for it, in a change made for that purpose: under MODIFIED, keep its header and every scenario and cut its description down to one behavior without changing its meaning, then add each behavior you removed as its own ADDED requirement with its own scenarios." Moving the scenarios out of the MODIFIED blocks would break that rule, so they stay. Fixed: the proposal now says the shortened requirements keep all their scenarios and each split-off requirement gets new happy and failure scenarios (proposal, What Changes, #66). D4 cites the schema rule. The near-duplicate "Store login has no credential for a read" is replaced by a distinct scenario, "Code remote accepts only the code login".
- **M2 — fixed.** The line lives only while its milestone is Next, and close drops it on promotion (State & Ownership row, D2, the requirement text and the "Close promotes an agreed split" THEN). On yes for an unmarked list, close keeps the split and writes no line (scenario "Next lists changes without a recorded agreement"). The false Risks claim is replaced. Also from Suggestion 4: close records a split agreed for the new Next it writes (new scenario "Close records a split agreed for the new Next").
- **M3 — fixed.** The requirement now reads "in each repo where it ran `git checkout -b` and `<branch>` exists", and the Mechanism Ledger row states the static scope. Suggestion 5 is also covered: D3 says the other repo is still rolled back when one cannot switch back, with the new scenario "One repo cannot switch back".
- **M4 — fixed.** The scenario is renamed "Store hook fails after the code branch exists". "Code hook fails after the store branch exists" is added for close, matching `eval-store-roadmap-close-hook-fail`.
- **Suggestions:**
  - Version: the proposal's Impact now explains the 0.1.12 call. The marker is optional and roadmaps without it keep working; 0.1.12 is the roadmap's plan.
  - D5 names the update to `test_roadmap_store_checks_code_repo_before_any_branch`.
  - The single-repo ledger row describes the two-stop recovery.
