# Review

## Metadata

- **Round:** 9 (FULL)
- **Prior round:** APPROVE_WITH_CHANGES (round 8); applied in cce051f, 0203952; pre-ship amendments 8555be0, 32c0528
- **Reviewer:** OMP / openai-codex/gpt-6.2-sol
- **Reviewed:** Round 8 findings, proposal, design, tasks and test map, affected deltas and matching main specs, finish and PR skills, README install steps, and relevant CLI and eval source. The local reflog confirms all four commits; `git show` was unavailable. Static review; no evals run. #243, #249, and waived regex gaps excluded.

## Findings

### Critical (blocking)

None.

### Moderate

1. **The archive-only requirement still directs ship to validate on `sw_mismatch`.** The normative paragraph (`specs/change-finish/spec.md:67`) requires `pr.validate` on “a check error,” but the new scenario at lines 89–91 requires ship to stop before validation. Both `git_error` and `sw_mismatch` exit 1; the distinction is the JSON `error` field. The same paragraph requires the classifier before every push, even though `--base` needs a ready head and the skill calls it only when the planning ready head was handed over (`skills/specwright-pr/SKILL.md:102`). The task map and task 6.1 still say “any non-zero,” and the release summary repeats the unqualified fallback. State the three paths consistently: no planning ready head → skip classification and validate; `sw_mismatch` → show its message and stop; other classifier failures → report and validate.
2. **The undo delta does not limit the display and JSON field contract to a successful plan.** `specs/change-finish/spec.md:40–44` separates the two arrays from their display, but still requires both the fields and their display without an exit-0 condition. The same delta says a `dirty_tree` or `no_archive` refusal prints no steps, and the finish skill shows the refusal instead of reading plan fields (`skills/specwright-finish/SKILL.md:74–76`). A consumer following the unconditional contract can try to read absent fields instead of showing the refusal. Scope the plan fields and display to exit 0, and make the success scenario require each step’s `cwd` and `argv`.
3. **The resumed-orphan scenarios omit the refusal guard.** The requirement and README correctly stop when a completed swap and a refusal appear together, but the removal scenario (`specs/install-update/spec.md:207–209`) requires removal and permits stamping without establishing that the plan has no refusals. `sw update plan` can return both `orphans` and a `swapped` journal with `error: refused` and `unchanged: false` (`cli/lib/src/update/plan.dart:456–485`). A rerun with pre-authorized removal can therefore satisfy the scenario’s conditions while README requires no removal. Make both success scenarios explicitly refusal-free and map the refused-resume case to the existing README check.
4. **The pack-orphan prompt can remove a skill the same update installs.** README Step 4 filters out current install targets for core skill orphans but not for the other `orphans` entries (`README.md:367–374`). When a still-enabled `web` stops shipping `web-ui-layout` and a newly enabled `web-ui` ships the identical skill under the valid longer prefix, the planner can report the same destination as both an orphan of `web` and an adopted install target of `web-ui` (`cli/lib/src/update/packs.dart:263–285,1040–1077`). Following the prompt and accepting removal deletes a required skill after the swap, so Step 7 cannot stamp. Exclude current install targets by destination from every orphan removal prompt.

### Suggestions

- **Specify watch’s outcome if the classifier also fails after the push.** Ship can now validate and push after `git_error`, but watch’s second classifier call only branches on `archive_only: true` or `false` and the explicit re-review setting (`skills/specwright-pr/SKILL.md:165–167`). With a persistent error and the default setting, the archive is already pushed and watch has no stated next step. Report the error and explicitly withhold carry-over; state whether watch stops or requests a fresh review.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

CHANGES_APPLIED: yes

Resolve the four moderate findings in the affected specs, task map, release summary, and README prompt.

## Rebuttals

None.