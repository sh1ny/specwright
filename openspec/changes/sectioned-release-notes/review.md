# Review

## Metadata

- **Round:** 3
- **Prior round:** 2 - APPROVE_WITH_CHANGES with 1 Moderate and 5 Suggestions (four Required Changes); the author applied all four plus advisory findings 2, 3 and 5, which voids that verdict, so this is a full review
- **Reviewer:** fresh-context subagent (specwright-reviewer, Claude Code)
- **Reviewed:** openspec/changes/sectioned-release-notes/{proposal.md, design.md, review.md (round 2), specs/releases/spec.md, specs/preship-review/spec.md, specs/design-review-gate/spec.md}; schemas/specwright/schema.yaml (proposal, review, tasks and apply instructions); schemas/specwright/templates/{review.md, proposal.md}; openspec/specs/{releases, preship-review, design-review-gate}/spec.md; openspec/architecture.md (components, data formats, bounds, ADR index); docs/adr/0002, 0003, 0010, 0014 (as indexed in architecture.md); openspec/roadmap.md (Now: M5); skills/specwright-release/scripts/release.sh (header, `cat_batch`, `sv`, the notes section `MAX_PROPOSAL` to `local_changes`, `store_changes`, `build_notes`, `status_doc`, `main`); skills/specwright-release/SKILL.md; skills/specwright-review/references/brief.md; evals/release/test_release.py (`test_over_100_lists_names_only`); archived `tasks.md` bump task lines and proposal/tasks sizes under openspec/changes/archive/. Installed project skills named: none.

<!-- This verdict covers only the contents reviewed. Editing proposal, specs or design afterward (other than applying Required Changes) voids it. -->

## Findings

Round 2 findings, each re-checked against the current artifacts:

- R2-1 (no gate for a section made invalid after the bump task): **resolved.** The pre-ship requirement now makes a section that breaks the format rules a P1 `docs` finding when `release.enabled` is true, with the scenario "Section breaks the format" (`### Security`, P1, ship waits). D6 gives the reason (publish would drop the whole section), and D7 makes every commit that edits the section, pre-ship and PR fix commits included, run `release.sh notes --proposal` as its verification.
- R2-2 (pre-ship check applied with releases off): **resolved.** The requirement opens with "With `release.enabled` true", says no finding concerns the section with releases off, and the scenario "Releases off" covers both a stale item and a missing section. D6 says the same.
- R2-3 (bumping change not always last in a multi-archive release commit): **resolved in the spec.** The requirement "The release summary comes from the bumping change" finds it by the ticked `release.sh bump --to <V>` task in the archived `tasks.md`, the scenario "Bumping change archived with another in the same commit" pins it, and D2, Flow & State Gaps and the Mechanism Ledger say why. Two design passages still state the old rule (finding 1 below).
- R2-4 (stated read bound not a bound): **resolved.** Resource Bounds now names a `git cat-file --batch-check` size pass and a true worst case (1 000 × 2 × 64 KB), and the Mechanism Ledger records it. The pass as written now contradicts the Why-line row above it (finding 2 below).
- R2-5 (overflow line layout): **resolved.** The scenario "Many items" pins the count line right after the 150th item with no blank line, a group wholly past the cap left out, and `Changes:` after one blank line.
- R2-6 (Impact missing architecture.md): **resolved.** Impact lists the component row, the "Release publish" bounds row, the "Releases" data-format bullet and the ADR index row for 0015. These match the current rows at architecture.md:84, :131 and :148.

### Critical (blocking)

None.

### Moderate

1. **The ADR 0015 text and D2's title still give the summary rule that round 2 replaced, so apply would record the wrong rule in a permanent ADR.**
   - The design's "To record during apply" entry for ADR 0015 says "the summary taken from the last change with a valid section". D2 is still titled "The release summary is the last section's summary".
   - The spec now says otherwise. The requirement "The release summary comes from the bumping change" takes the summary from the change whose archived `tasks.md` has the ticked `release.sh bump --to <V>` task, and falls back to the last change with a valid section only when no change matches, or more than one does. The scenario "Bumping change archived with another in the same commit" is the case where the two rules give different answers: `c-other` sorts last (`local_changes` sorts by `(position, dirname)`, `release.sh:1099`), but `b-bump`'s summary must open the notes.
   - The first task group writes the ADR files (the tasks rule). An ADR copied from this text would contradict the spec it records. Later design reviews read architecture.md and the in-force ADRs as the baseline, so a later change could rely on "last change wins" and undo the R2-3 fix.

### Suggestions

2. **The size pass as written drops the Why line of a proposal over 64 KB. That contradicts the row above it and can break the byte-for-byte backfill rule.**
   - Today `whys` reads each listed proposal's blob whole through `cat_batch` and takes `first_sentence` of its first 64 KB (`release.sh:1055-1058`). An oversized proposal therefore still gets its Why line.
   - The Resource Bounds row "Proposal read per change" keeps that: "the Why line keeps today's cut". The next row says "A blob over the bound is never read". If one pass serves both reads, as the row describes, an over-64 KB no-section proposal loses its Why. Its line then becomes `- <name> (#<pr>)`.
   - That breaks two spec rules: the scenario "No change in the range has a section" (notes byte-for-byte as before) for any old range with such a proposal, and the expected Why line in "Proposal over the read bound".
   - No archived proposal here is near the bound (the largest is about 7.7 KB). The dogfood projects' archives were not checked, and the conflict is in the design text an implementer follows.
   - Fix: say the size pass covers the section and `tasks.md` reads only, and that Why lines for listed no-section changes are read as today.

3. **`notes --proposal` reads at most 64 KB, so the author's check can pass a section that publish will drop.**
   - D5 says the subcommand "reads one file (at most `MAX_PROPOSAL`)". D4 judges the full archived blob, so that "a cut can never parse as a shorter valid section". At publish, a proposal over 64 KB is therefore invalid.
   - A 70 KB proposal checked by the bump task or a D7 fix commit is cut at 64 KB. It can parse as valid and exit 0, and publish then falls back to the Why line with only a warning (with `release.auto: true` nobody acts on it).
   - The requirement "One proposal's section can be checked before it merges" has no scenario for this case. The author's tool and publish should give the same answer.

4. **The scenario "Two changes with sections" does not say whether either change has a bump task.**
   - Under the new summary rule, its THEN ("the notes open with `add-b`'s summary") holds only when neither `tasks.md` has the ticked bump task, or when `add-b`'s does. The scenario "No change has a bump task" states that condition and this one does not.
   - A fixture that adds a bump task to `add-a` (archived in the same commit) makes the scenario fail against the requirement. Add "and neither archived `tasks.md` has a ticked `release.sh bump --to` task" to its WHEN. This is advisory.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. In design.md, retitle D2 to "The release summary is the bumping change's summary, written by the bump task". In ADRs, "To record during apply", replace "the summary taken from the last change with a valid section" in the 0015 entry with "the summary taken from the change whose archived `tasks.md` has the ticked `release.sh bump --to <V>` task and a valid section, else from the last change with a valid section".
2. In design.md Resource Bounds, the "Proposals and tasks files parsed per release" row: say the size pass applies to the section and `tasks.md` reads only. Say also that Why lines for the listed no-section changes are read as today, the blob read whole and `first_sentence` taken from its first 64 KB, so that an over-bound proposal keeps its Why line under `Changes:`.
3. In specs/releases/spec.md, the requirement "One proposal's section can be checked before it merges": add a scenario. WHEN `--proposal` names a file over 64 KB whose first 64 KB hold a valid section, THEN it exits 1 with `release_notes_invalid` and an error naming the 64 KB limit. In design.md D5, replace "reads one file (at most `MAX_PROPOSAL`)" with a size check first: a file over `MAX_PROPOSAL` is invalid, as in D4.

Finding 4 is advisory and needs no edit for this verdict.

Re-check of the Required Changes (a separate run, these three items only):

1. **Applied.** design.md D2 is titled "The release summary is the bumping change's summary, written by the bump task" (design.md:33), and its Choice gives the bump-task rule with the last-valid-section fallback. The ADR 0015 entry under "To record during apply" (design.md:151) now reads "the summary taken from the change whose archived `tasks.md` has the ticked `release.sh bump --to <V>` task and a valid section, else from the last change with a valid section", which matches the requirement "The release summary comes from the bumping change".
2. **Applied.** The Resource Bounds row "Proposals and tasks files parsed per release" (design.md:110) now says the size pass applies to the section and `tasks.md` reads only, and that Why lines for the listed no-section changes are read as today (blob read whole, `first_sentence` of its first 64 KB), so an over-bound proposal keeps its Why line under `Changes:`. This agrees with the row "Proposal read per change" above it.
3. **Applied.** specs/releases/spec.md adds the scenario "File over the read bound" (spec.md:177-179): a 70 KB `--proposal` file whose first 64 KB hold a valid section exits 1 with `release_notes_invalid` and an error naming the 64 KB limit. D5 (design.md:53) now checks the size first, and a file over `MAX_PROPOSAL` is invalid with an error naming the 64 KB limit, as in D4.

CHANGES_APPLIED: yes

## Rebuttals
