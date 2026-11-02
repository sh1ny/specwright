# Review

## Metadata

- **Round:** 1 (re-check of Required Changes)
- **Prior round:** none
- **Reviewer:** fresh-context subagent (specwright-reviewer, Claude Code)
- **Reviewed:** openspec/changes/bump-openspec-1-16/{proposal.md,design.md,.openspec.yaml}; OPENSPEC_VERSION; README.md (badge :9, prerequisites :54, version note :56, Step 1 :70-100, Step 3 :155-175, fork note :427, Stores note :572); CONTRIBUTING.md (:7, :59); evals/git-workflow/test_instructions.py (pin_drift :1216, TestOpenSpecPin :1248-1424); evals/git-workflow/{grade.py :1598-1660 and :1739, test_grade.py :810-838, evals.json :1040-1072 and :1248, fixtures.py :1077-1095 and :1575-1583}; evals/git-workflow/test_specs_strict.py; schemas/specwright/schema.yaml :100-140; schemas/specwright/templates/spec.md; openspec/strategy.md :34; openspec/roadmap.md (M6); openspec/specs/install-update/spec.md; openspec/architecture.md (ADR index, OpenSpec boundary :129); docs/adr/0001; .github/workflows/evals.yml :70-85; skills/*/SKILL.md root-check wording; scripts/update.sh validate path; upstream CHANGELOG.md sections 1.14.2-1.16.0 and the v1.14.1...v1.16.0 compare (package.json engines, schemas/spec-driven/schema.yaml, src/core/root-selection.ts, src/core/project-config.ts).
- **Re-check:** the edited design.md (D3, D5, Flow & State Gaps) and proposal.md (Impact file list, Release Notes), against README.md:160-170 and evals/git-workflow/test_instructions.py:1210 (`openspec_pin`) and :1320-1420.

## Findings

### Critical (blocking)

None.

### Moderate

1. **The Step 3 example cannot follow the pin without editing tests the design does not list.** The proposal moves "Step 3 example" to 1.16.0, and `pin_drift` (test_instructions.py:1232, the `\ba\s+pin\s+of\s+` branch) forces README:165 to read "Against a pin of 1.16.0". The rest of that sentence and the next one give examples derived from the pin: `1.14.2` (a newer patch), `1.14.1-beta.1` (a pre-release of the pin), `1.14.1+vendor.1` (a build of the pin), and `1.14.1.0` / `1.14.1vendor` (README:168, "not a match on its first part"). Two outcomes are possible, and both have a concrete cost:
   - If the examples stay at 1.14.x, the install prompt that agents run says "Against a pin of 1.16.0, 1.14.2, 1.14.1-beta.1 and 1.14.1+vendor.1 are each a mismatch". That is true, but it no longer shows the edge cases the rule exists for. "Not a match on its first part" no longer makes sense either, because 1.14.1 is no longer the pin. An agent reading that prompt no longer learns that `1.16.0-beta.1` or `1.16.0+vendor.1` are mismatches.
   - If the examples move to 1.16.x, three tests fail in CI: `test_exact_match_counts_prerelease_as_mismatch` (:1329-1331 hardcodes `1.14.1-beta.1` and `1.14.2`), `test_exact_match_counts_build_metadata_as_mismatch` (:1339 hardcodes `1.14.1+vendor.1`) and `test_step3_run_on_token_is_unreadable` (:1383-1384 hardcodes `1.14.1.0` and `1.14.1vendor`). `evals/git-workflow/test_instructions.py` is not in the proposal's Files list, and the design says nothing about these tests.

   The design has to choose one, or the implementer will either ship an incoherent prompt or hit unplanned red CI. Required Change 1 gives the fix.

   **Re-check: resolved.** D5 now takes the second option. It moves the README:165 and :168 examples to `1.16.1`, `1.16.0-beta.1`, `1.16.0+vendor.1`, `1.16.0.0` and `1.16.0vendor`. It names the three tests at their current lines (:1326, :1334, :1379) and has them build their expected strings from `openspec_pin()` (defined at test_instructions.py:1210). It also covers a fourth test the original finding missed: `test_readme_token_rule_on_sample_outputs` (:1395). That test does not read the README examples, so it would not have failed. Its sample outputs at :1413-1414 hardcode `1.14.1`, `1.14.1+vendor.1`, `1.14.1.0` and `1.14.1vendor`, and deriving them from the pin keeps the file consistent. The proposal's Impact list now includes `test_instructions.py` (proposal.md:30). D4 still keeps the `install-update` scenarios at 1.14.x. The rejected option in D5 records the reason Moderate 1 gave.

### Suggestions

1. **"Every output Specwright parses is unchanged" does not cover the no-root error path.** The Context comparison ran `list`, `context` and the other commands in a project that has a root. In 1.16.0, #2077 (`src/core/root-selection.ts`) changed the `root: null` error. When the repo's origin name matches a registered store, it now says to rerun with `--store <id>` or add `store: <id>` to config.yaml. Specwright's prefix parse (`Declared in` / `Invalid store declaration in`, used in README Step 1 and the five skills' Root step) is unaffected, because those messages did not change. However, README Step 1 still tells the user to run `openspec init` with the pinned version. In exactly the case 1.16.0 now detects (a store-backed project missing its `store:` line), that is the advice the README itself warns "would create a root that overrides the store". This behaviour existed before the bump, so it does not block this change. Consider adding a line to Context or a follow-up issue so the "unchanged" claim is scoped accurately.
   - **Re-check:** addressed in scope. Flow & State Gaps (design.md:95) now names #2077 and says the Step 1 advice is out of scope. A follow-up issue for the `openspec init` advice is still worth filing.
2. **Flow & State Gaps names only the 1.16.0 scenario rule.** Between the old and new pins, `--strict` also started failing on two more things, and Specwright's `pr.validate` default (`openspec validate --all --strict`, skills/specwright-pr/SKILL.md:43) reaches in-flight changes through both:
   - Delta-spec text that archive drops: an extra `## ` section, or prose before the first requirement (1.14.2, #2054).
   - An unreadable or invalid `openspec/config.yaml`, which now makes `validate` exit 1 (1.16.0, #2127).

   Specwright's own template (`schemas/specwright/templates/spec.md`) does not trigger either. Naming them in the release notes or in Flow & State Gaps would tell adopters why a previously passing `--strict` run on an in-flight change can fail after they upgrade.
   - **Re-check:** applied. Flow & State Gaps (design.md:94) names both, and the Release Notes have a third Changed item for them (proposal.md:40).
3. **D3's insertion point.** Upstream added the line after "Every requirement MUST have at least one scenario.", next to the other validate-warning bullet. "After `schema.yaml:118`" in the fork would put it between "Each scenario: … WHEN/THEN format" and the CRITICAL hashtag line. Placing it after the fork's "Each THEN MUST be an assertable outcome" bullet (:124-125), just before the 500-character bullet (:126), keeps the fork's order the same as upstream's and makes the next diff against `spec-driven` easier to read.
   - **Re-check:** applied. D3 (design.md:41) now places the line after :124-125, before the description-length bullet. Minor: Context (design.md:22) still calls `schema.yaml:118` "the matching spot". D3 is the decision the implementer follows, so this does not block. Aligning the two lines would remove the contradiction.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. In design.md, add a decision (or extend D1) for README Step 3's examples:
   - Move the examples with the pin: `1.16.1` (newer patch), `1.16.0-beta.1`, `1.16.0+vendor.1`, `1.16.0.0` and `1.16.0vendor`.
   - Update `test_exact_match_counts_prerelease_as_mismatch`, `test_exact_match_counts_build_metadata_as_mismatch` and `test_step3_run_on_token_is_unreadable` in `evals/git-workflow/test_instructions.py` to match. Preferably derive the expected strings from `openspec_pin()` so the next upgrade does not repeat this.
   - Add `evals/git-workflow/test_instructions.py` to the proposal's Impact file list.
   - The `install-update` spec scenarios can keep their 1.14.x examples, as D4 argues.

   **Status: applied.** D5 in design.md covers the examples, the three tests and `test_readme_token_rule_on_sample_outputs`, with expected strings derived from `openspec_pin()`. proposal.md:30 lists `test_instructions.py`. D4 is unchanged.

CHANGES_APPLIED: yes

## Rebuttals
