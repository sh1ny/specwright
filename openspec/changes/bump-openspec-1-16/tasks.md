# Tasks

## Test map

This change sets `skip_specs: true` and has no spec deltas, so no `#### Scenario:` needs a row. The existing pin tests guard the change and must pass on the new pin:

| Requirement | Scenario | Test file | Test name | State |
|---|---|---|---|---|
| n/a (no spec delta) | Pin mentions agree with `OPENSPEC_VERSION` | evals/git-workflow/test_instructions.py | `TestOpenSpecPin` (all) | green |
| n/a (no spec delta) | Pin evals report the pin and a fake version other than it | evals/git-workflow/test_grade.py | `eval-install-openspec-mismatch`, `eval-install-openspec-override` grading tests | green |
| n/a (no spec delta) | Schema stays loadable | mechanical: `openspec schema validate specwright` | n/a: schema validation, not a test | green |

## 1. Pin-derived Step 3 tests

- [ ] 1.1 In `evals/git-workflow/test_instructions.py`, make `test_exact_match_counts_prerelease_as_mismatch`, `test_exact_match_counts_build_metadata_as_mismatch`, `test_step3_run_on_token_is_unreadable` and `test_readme_token_rule_on_sample_outputs` build their example versions from `openspec_pin()` (`<pin>-beta.1`, `<pin>+vendor.1`, `<pin>.0`, `<pin>vendor`, the next patch), per design D5; verify `python -m unittest evals/git-workflow/test_instructions.py` still passes on the current pin 1.14.1.

## 2. Move the pin to 1.16.0

- [ ] 2.1 Set `OPENSPEC_VERSION` to `1.16.0`; verify `python -m unittest evals/git-workflow/test_instructions.py` goes red in `TestOpenSpecPin` and the Step 3 example tests, naming the stale README and CONTRIBUTING lines.
- [ ] 2.2 Update every pin mention `CONTRIBUTING.md:59` names: the README badge, prerequisites, version note, install Step 1, Step 3's pin and examples (`1.16.1`, `1.16.0-beta.1`, `1.16.0+vendor.1`, `1.16.0.0`, `1.16.0vendor`), the "forked from `spec-driven`" note and the Stores note; `CONTRIBUTING.md`'s install line; and add "Node.js 22.12 or later" next to the `npm i -g` command in the README prerequisites and `CONTRIBUTING.md` (design D2). Verify `python -m unittest evals/git-workflow/test_instructions.py` passes.
- [ ] 2.3 Update the pin evals: the expected pin in `evals/git-workflow/grade.py`, `test_grade.py` and `evals.json` becomes 1.16.0 (the fake `openspec` keeps reporting 1.15.0, a version other than the pin); verify `python -m unittest evals/git-workflow/test_grade.py` passes and `test_eval_scaffolding_matches_pin` in `test_instructions.py` passes.
- [ ] 2.4 Update `openspec/strategy.md` ("pinned (1.16.0 today)"); verify `grep -rn "1\.14\.1" README.md CONTRIBUTING.md openspec/strategy.md OPENSPEC_VERSION evals/git-workflow/grade.py evals/git-workflow/test_grade.py evals/git-workflow/evals.json` prints only intentional mentions (the 1.14.1 fixture of the stale v0.5.0 release in `fixtures.py` is out of that list and stays).

## 3. Schema line from upstream

- [ ] 3.1 Add upstream 1.16.0's line ("Every scenario MUST have a WHEN/GIVEN step (its trigger) and a THEN step (its outcome). …") to the specs artifact in `schemas/specwright/schema.yaml`, after the "Each THEN MUST be an assertable outcome" bullet and before the description-length bullet (design D3); verify `openspec schema validate specwright` passes against a copy installed with the change and `openspec validate --all --strict` still passes.

## 4. Roadmap and release

- [ ] 4.1 Record `bump-openspec-1-16` (0.14.1, #164) in the M6 section of `openspec/roadmap.md` (changes list and the release list in the exit criteria); verify by reading the M6 section.
- [ ] 4.2 Run `release.sh bump --to 0.14.1`, and rewrite the summary of the proposal's `## Release Notes` to describe the whole release; verify with `release.sh check` and `release.sh notes --proposal openspec/changes/bump-openspec-1-16/proposal.md`.

## Workflow follow-up

- Locally (not tracked, gitignored): once the global OpenSpec CLI is 1.16.0, run `openspec update` here to regenerate `/.claude/skills/openspec-*/`, and reinstall Specwright in the dogfood projects.
