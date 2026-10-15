# Review

## Metadata

- **Round:** 1
- **Prior round:** none
- **Reviewer:** fresh-context subagent (specwright-reviewer, Claude Code)
- **Reviewed:** openspec/changes/pin-openspec-version/proposal.md, design.md, specs/install-update/spec.md; openspec/specs/install-update/spec.md; openspec/architecture.md (ADR index, lines 73, 105, 143); docs/adr 0001 and 0002 as cited in the architecture index; openspec/roadmap.md (M3 exit criteria); openspec/strategy.md; README.md (badge, prerequisites, Install / Update prompt Steps 1-8, lines 217 and 322); CONTRIBUTING.md; evals/git-workflow/test_instructions.py (prerequisites, install_bullet, Step 1 tests); evals/git-workflow/fixtures.py (env_file, install_fake_gh, install_base, build dispatch); evals/git-workflow/evals.json (eval-install-store, -store-other-schema, -nested-store); evals/review-routes/test_skill_text.py (test_frontmatter_version); skills/*/SKILL.md metadata.version; issue #37 text as given in the request.

<!-- This verdict covers only the contents reviewed. Editing proposal, specs or design afterward (other than applying Required Changes) voids it. -->

## Findings

### Critical (blocking)

None.

### Moderate

**M1. The release bump leaves out the skills' `metadata.version`, which fails an existing suite.**
The proposal (Impact) says "No skill ... changes ... `VERSION` and the README badge both move to 0.4.2". `CONTRIBUTING.md` (Releases) requires `VERSION`, the README badge and `metadata.version` in every `skills/*/SKILL.md` to move together. Every `skills/*/SKILL.md` has `version: 0.4.1` today. `evals/review-routes/test_skill_text.py:48-51` (`test_frontmatter_version`) asserts that the specwright-review SKILL.md version equals `VERSION`. If the change bumps only `VERSION` and the badge, as the proposal says, `evals/review-routes` goes red, and that breaks the M3 exit criterion that the three suites pass. The skill text itself does not change, but the version stamp in each skill does. The proposal needs to say so, so the tasks include it.

**M2. With an older OpenSpec, Step 1 stops with the wrong message before the version check can run, and that message points the user at a harmful fix.**
D1 moves the comparison to the end of Step 3. Step 1, however, still runs `openspec list --json` and reads `root` (`README.md:69-76`). The README says stores need "OpenSpec 1.14.1 or later" (`README.md:75`, `:322`), so an OpenSpec older than the pin cannot resolve the `store:` pointer. In a store-backed project (the very setup the install evals build in `fixtures.py` `install_base`), Step 1 then takes the `"root": null` / "tell the user to run `openspec init` first and STOP" branch. The user is never told that the version is wrong. If they follow the advice, `openspec init` creates a real `openspec/` root in the code checkout, which the prompt itself warns "would override the store" (`README.md:81-82`). The Flow & State Gaps section covers OpenSpec changing between Step 1 and Step 3, but not an off-pin CLI failing Step 1's own `openspec` calls. The spec has no scenario for it either: "OpenSpec missing" covers only a failing `--version`.

### Suggestions

- **S1.** D4's drift test covers the badge and the install commands. The State & Ownership row also names the README's schema fork note ("forked from OpenSpec's `spec-driven` (1.14.1)", `README.md:217`), which the `CONTRIBUTING.md` upgrade rule updates together with the others. Add it to the drift test, or the pin can drift from that note with no test failing.
- **S2.** The Failure table says the temporary clone is deleted when the Step 3 check stops. Today the only deletion is in Step 7 (`README.md:180`). Have the new Step 3 bullet say the deletion explicitly, and have the mismatch scenario assert it. The install evals use the local checkout instead of a clone, so only the prompt text can carry this guarantee.
- **S3.** The new eval names need entries in the `build()` dispatch dict (`fixtures.py:1096-1097`). An unmapped `eval-install-*` name raises `KeyError`, not the `unknown eval` exit. List this as a task item.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. In proposal.md, Impact: replace "No skill, schema, script or `specwright.yaml` key changes, so the release is a patch (0.4.2): `VERSION` and the README badge both move to 0.4.2" with wording that says no skill behaviour, schema, script or `specwright.yaml` key changes, so the release is a patch (0.4.2), and that `VERSION`, the README badge and `metadata.version` in every `skills/*/SKILL.md` all move to 0.4.2 (per `CONTRIBUTING.md` Releases and `evals/review-routes/test_skill_text.py:48`).
2. In design.md, add the Step 1 case to Flow & State Gaps and to D1: Step 1 records the `openspec --version` output. When the `openspec list --json` root check then fails or returns no `root`, and that version differs from the pin in the README's own install command, the stop message names the version found and `npm i -g @fission-ai/openspec@<pin>` first, and does not tell the user to run `openspec init`. Add a matching scenario to specs/install-update/spec.md under "Install checks the OpenSpec version against the pin". For example: WHEN `openspec --version` prints `1.13.0` and `openspec list --json` reports no root, THEN the install stops in Step 1, names `1.13.0` and `npm i -g @fission-ai/openspec@1.14.1`, does not suggest `openspec init`, and writes no file.

<!-- yes (applied, and re-checked by the reviewer - only the reviewer sets it) | no (outstanding) | n/a (any other verdict) -->
CHANGES_APPLIED: yes

## Rebuttals

Re-check (round 1, fresh-context reviewer, 2026-10-15): checked only the two Required Changes.
- RC1 applied: proposal.md Impact (line 35) now says "No skill behaviour, schema, script or `specwright.yaml` key changes", and that `VERSION`, the README badge and `metadata.version` in every `skills/*/SKILL.md` all move to 0.4.2, citing `CONTRIBUTING.md` Releases and `evals/review-routes/test_skill_text.py:48`.
- RC2 applied: design.md D1 (line 28) has Step 1 record the `openspec --version` output. When the root check fails or returns no `root` and that version differs from the README's pin, the stop names the version found and `npm i -g @fission-ai/openspec@<pin>`, and does not suggest `openspec init`. Flow & State Gaps (line 89) adds the "Root check fails on an unpinned CLI" case, which writes no file and keeps the `openspec init` advice for the pinned version. specs/install-update/spec.md (lines 29-31) adds the scenario "Root check fails on an unpinned OpenSpec" (1.13.0 found, pin 1.14.1, no root: stops in Step 1, names both, no `openspec init`, writes no file).
