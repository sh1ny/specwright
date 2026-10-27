# Review

## Metadata

- **Round:** 4
- **Prior round:** 3 - APPROVE_WITH_CHANGES (1 Moderate, 3 Suggestions; three Required Changes, re-checked as applied, `CHANGES_APPLIED: yes`). Commit 0649fdb then reworded the MODIFIED requirement "Notes list the changes merged since the previous release" in specs/releases/spec.md (567 to 499 characters, for OpenSpec's 500-character strict limit), which voids that verdict, so this is a full review. Nothing else in proposal, specs or design changed since round 3.
- **Reviewer:** fresh-context subagent (specwright-reviewer, Claude Code)
- **Reviewed:** openspec/changes/sectioned-release-notes/{proposal.md, design.md, review.md (round 3), specs/releases/spec.md, specs/preship-review/spec.md, specs/design-review-gate/spec.md}; `git show 0649fdb`; the review instruction and template at HEAD (`schemas/specwright/schema.yaml` review artifact and tasks rule, `schemas/specwright/templates/review.md`); openspec/specs/releases/spec.md (the requirement being modified and "Store-backed notes use the code-merge proof"); openspec/architecture.md at HEAD (components row for `specwright-release`, "Releases" data-format bullet, "Release publish" bounds row, in-force ADR index); docs/adr/ listing (0002, 0003, 0010, 0014 as the design cites them); openspec/roadmap.md at HEAD (Now: M5 and its release-notes exit criterion); skills/specwright-release/scripts/release.sh at HEAD (`cat_batch`, `MAX_PROPOSAL`/`MAX_LISTED`, `first_sentence`, `whys`, `local_changes`, `store_changes`, `build_notes`, `status_doc`, `Settings.gate`, `main`); skills/specwright-release/SKILL.md and skills/specwright-review/references/brief.md at HEAD. Ran `openspec validate sectioned-release-notes --strict` (valid). Installed project skills named: none.

<!-- This verdict covers only the contents reviewed. Editing proposal, specs or design afterward (other than applying Required Changes) voids it. -->

## Findings

History, kept short: round 1 and round 2 findings were resolved by round 3 (summary found by the ticked bump task, size pass as a real bound, overflow layout, pre-ship checks gated on `release.enabled`, P1 for a section that breaks the format, Impact naming architecture.md rows). Round 3's three Required Changes (D2 title and the ADR 0015 text, the size pass limited to section and `tasks.md` reads, the over-64 KB `notes --proposal` scenario and D5 size check) were re-checked as applied and still read that way.

The edit since round 3 (0649fdb), checked on its own:
- Old text: "every change whose merge lands after the previous release commit and up to V's release commit: a change whose archived proposal has a valid `## Release Notes` section by that section's items, any other change by its change name, the first sentence of its archived proposal's Why, and its PR number when main's commit subject names one."
- New text: "every change merged after the previous release commit, up to V's release commit: one with a valid `## Release Notes` section by its items, any other by its change name, its archived proposal's first Why sentence and its PR number when main's commit subject names one."
- Same range, same split (sectioned changes by their items, others by name, Why and PR), same previous-release rule. The section's source (the archived proposal at the release commit, or the store's main) is still pinned by D1 and by the requirement "A Release Notes section has one format", so dropping "archived proposal has" loses nothing. The requirement is 499 characters and `openspec validate --strict` passes. The scenarios are unchanged and still match the main spec's five plus the added byte-for-byte scenario. No finding.

Full re-check of the rest against the code: the design's line references into release.sh still match HEAD (`whys` reads 64 KB of each listed proposal through one `cat_batch`; `local_changes` sorts by `(position, dirname)`; `build_notes` emits `Changes in <tag>:`, a blank line, then the lines; `main` calls `git rev-parse` and `st.gate()` before any subcommand, so `notes --proposal` must be dispatched before both, as D5 says). The tasks rule at HEAD fixes the bump task's text as `release.sh bump --to <version>`, which the bump-task lookup relies on. ADR 0010 (permanent tag message), 0003 (notes rebuilt from the repo), 0002 (parser in the thin script) and 0014 (no new network command) are respected. No new Critical or Moderate finding.

### Critical (blocking)

None.

### Moderate

None.

### Suggestions

1. **The scenario "Two changes with sections" still does not say whether either change has a bump task (round 3 finding 4, carried forward, advisory).**
   - Its THEN ("the notes open with `add-b`'s summary") follows from the requirement "The release summary comes from the bumping change" only when neither archived `tasks.md` has the ticked `release.sh bump --to <V>` task, or `add-b`'s does.
   - A fixture that gives `add-a` the bump task makes the scenario contradict that requirement, and the scenario "No change has a bump task" shows the condition is meant to be stated.
   - Fix: add "and neither archived `tasks.md` has a ticked `release.sh bump --to` task" to its WHEN. An edit to specs voids this verdict, so make it only together with another spec edit, or accept it as is.

## Verdict

VERDICT: APPROVE

## Required Changes

None.

CHANGES_APPLIED: n/a

## Rebuttals
