# Tasks

## Test map

Text tests live in `evals/git-workflow/test_instructions.py`, class `TestOpenSpecPin`. Agent evals live in `evals/git-workflow/evals.json` and are graded by `evals/git-workflow/grade.py`.

| Requirement | Scenario | Test file | Test name | State |
|---|---|---|---|---|
| install-update → Install checks the OpenSpec version against the pin | Pinned version installed | evals/git-workflow/test_instructions.py | test_step3_compares_with_downloaded_pin_before_step4 | green |
| install-update → Install checks the OpenSpec version against the pin | Newer patch release installed | evals/git-workflow/evals.json | eval-install-openspec-mismatch | red |
| install-update → Install checks the OpenSpec version against the pin | Newer patch release installed | evals/git-workflow/test_instructions.py | test_mismatch_stops_before_any_write | green |
| install-update → Install checks the OpenSpec version against the pin | Pre-release of the pinned version installed | evals/git-workflow/test_instructions.py | test_exact_match_counts_prerelease_as_mismatch | green |
| install-update → Install checks the OpenSpec version against the pin | Version output has no version number | evals/git-workflow/test_instructions.py | test_unreadable_version_stops | green |
| install-update → Install checks the OpenSpec version against the pin | Downloaded copy has no pin file | evals/git-workflow/test_instructions.py | test_missing_pin_file_stops | green |
| install-update → Install checks the OpenSpec version against the pin | Root check fails on an unpinned OpenSpec | evals/git-workflow/test_instructions.py | test_step1_root_failure_on_unpinned_cli_names_pin_not_init | green |
| install-update → Install checks the OpenSpec version against the pin | OpenSpec missing | evals/git-workflow/test_instructions.py | test_step1_missing_openspec_names_pinned_install | green |
| install-update → Explicit override of the OpenSpec pin | Override stated | evals/git-workflow/evals.json | eval-install-openspec-override | red |
| install-update → Explicit override of the OpenSpec pin | Override stated | evals/git-workflow/test_instructions.py | test_override_requires_found_version_and_is_reported | green |
| install-update → Explicit override of the OpenSpec pin | General confirmation is not an override | evals/git-workflow/test_instructions.py | test_general_confirmation_is_not_override | green |
| install-update → Explicit override of the OpenSpec pin | Override names another version | evals/git-workflow/test_instructions.py | test_override_for_other_version_stops | green |
| install-update → Public install commands name the pinned version | Commands match the pin | evals/git-workflow/test_instructions.py | test_install_commands_and_badge_match_pin | green |
| install-update → Public install commands name the pinned version | Pin bumped in one place only | evals/git-workflow/test_instructions.py | test_pin_drift_names_disagreeing_line | green |

## 1. Pin file and public install commands

- [x] 1.1 Add `TestOpenSpecPin` with `test_install_commands_and_badge_match_pin` and `test_pin_drift_names_disagreeing_line`. Put the drift check in a helper that takes the README and CONTRIBUTING text and the pin, and returns the disagreeing lines: every `npm i -g @fission-ai/openspec` must carry `@<pin>`, the badge must read `OpenSpec-<pin>`, the "forked from `spec-driven` (<pin>)" note must name the pin, and no "OpenSpec ... or later" claim may remain. The drift test feeds the helper the real README with the pin swapped to `1.15.0` and asserts that the README line is named. Run `python -m unittest discover evals/git-workflow -p "test_instructions.py" -k TestOpenSpecPin` and confirm both fail because `OPENSPEC_VERSION` is missing and the commands are unversioned.
- [x] 1.2 Add `OPENSPEC_VERSION` (`1.14.1` and a newline) at the repo root. Version the install commands in the README prerequisites (`README.md:44`) and Step 1 (`README.md:57-58`) as `npm i -g @fission-ai/openspec@1.14.1`. Change both store notes (`README.md:75`, `:322`) from "1.14.1 or later" to the pinned version. Extend the `CONTRIBUTING.md:51` upgrade rule to `OPENSPEC_VERSION` and the install commands. Verify that both 1.1 tests pass, and flip their rows to green.

## 2. Version check in the install prompt

- [x] 2.1 Write the failing text tests for the check: `test_step3_compares_with_downloaded_pin_before_step4`, `test_mismatch_stops_before_any_write`, `test_exact_match_counts_prerelease_as_mismatch`, `test_unreadable_version_stops`, `test_missing_pin_file_stops`, `test_step1_root_failure_on_unpinned_cli_names_pin_not_init` and `test_step1_missing_openspec_names_pinned_install`. Use the existing `step()` and `install_bullet()` helpers (`test_instructions.py:65`, `:483`). Each asserts where its rule sits and its key terms: Step 3 reads `OPENSPEC_VERSION` and compares the whole version token, pre-release included, with the pin; the mismatch, unreadable-output and missing-pin bullets STOP before Step 4, name both versions and the pinned install command, and delete the temporary clone; the Step 1 root-check branch names the found version and the pinned command, not `openspec init`, when the version differs from the pin. Run the tests and confirm each fails on the current README.
- [x] 2.2 Edit the README install prompt. Step 1 records the `openspec --version` output, and its `"root": null` branch gets the unpinned-CLI case (design D1). Step 3 reads the downloaded `OPENSPEC_VERSION` and adds the check bullet (design D2): exact token match; on a mismatch, unreadable output or a missing pin it STOPs before Step 4, names both versions and `npm i -g @fission-ai/openspec@<pin>`, and deletes the temporary clone. Step 8 reports `OpenSpec <found> (pinned)`. Verify that the 2.1 tests and the existing Step 1 tests (`test_instructions.py:492-521`) pass, and flip the rows to green.

## 3. Explicit override

- [x] 3.1 Write the failing tests `test_override_requires_found_version_and_is_reported`, `test_general_confirmation_is_not_override` and `test_override_for_other_version_stops`. They assert that the Step 3 override bullet requires the user's own words naming the found version (`continue with OpenSpec <found>`), rules out a general confirmation and a different version, is not offered as a default, holds for one run only, and that Step 8 reports `OpenSpec <found> (pinned <pin>, override)`. They also assert that the README documents the override outside the prompt block, next to the prerequisites. Run the tests and confirm they fail.
- [x] 3.2 Add the override bullet to Step 3, the override report line to Step 8, and a short override note under the README prerequisites (design D3). Verify that the 3.1 tests pass, and flip their rows to green.

## 4. Agent evals for the refusal and the override

- [x] 4.1 In `evals/git-workflow/fixtures.py`, add `install_fake_openspec(dest, version)`, following `install_fake_gh` (`fixtures.py:101`). It writes `bin/openspec`, a sh script that prints `<version>` for `--version` and otherwise `exec`s the real `openspec`, whose absolute path is resolved with `shutil.which` when the fixture is built. Map `eval-install-openspec-mismatch` and `eval-install-openspec-override` in the `install_base` dispatch (`fixtures.py:1096-1097`) to the `store` base plus the fake at `1.15.0`. Verify that building both fixtures succeeds, and that `bin/openspec --version` prints `1.15.0` while `bin/openspec list --json` from `code/` still reports the store root.
- [x] 4.2 Add both evals to `evals/git-workflow/evals.json`, with the install prompt of the existing install evals. The override eval's prompt adds `continue with OpenSpec 1.15.0`. Assertions for the refusal: no skill, agent, schema or `specwright.yaml` was written in either repo; `openspec/.specwright/VERSION` is absent; the report names `1.15.0`, `1.14.1` and `npm i -g @fission-ai/openspec@1.14.1`, and does not say the install completed. Assertions for the override: the install-store assertions hold, and the report shows `OpenSpec 1.15.0 (pinned 1.14.1, override)`. Verify that `python -m pytest evals/git-workflow` passes (the existing `test_grade.py` and fixture checks cover the new entries).
- [ ] 4.3 Run both evals with a fresh agent, as the README Evals section describes, grade them with `grade.py`, and record the results in the PR description. Verify that both pass, and flip the `eval-install-openspec-*` rows to green.

## 5. Architecture, release and integration

- [x] 5.1 Update `openspec/architecture.md`. The OpenSpec boundary (`:105`) says the pin is enforced at install from `OPENSPEC_VERSION`. The install-prompt row (`:73`) reads `OPENSPEC_VERSION`. Remove the #37 known-gap row (`:143`). Verify with `grep -n "#37" openspec/architecture.md`, which should print nothing.
- [ ] 5.2 Bump the release to 0.4.2: `VERSION`, the README version badge, and `metadata.version` in every `skills/*/SKILL.md` (`CONTRIBUTING.md` Releases). Verify with `python -m pytest evals/review-routes`, which includes `test_frontmatter_version`.
- [ ] 5.3 Integration: run `python -m pytest evals/pr-pair evals/git-workflow evals/review-routes`, `openspec validate pin-openspec-version --strict` and `openspec schema validate specwright`. All of them must pass.

## Workflow follow-up

- Archive with `/opsx:archive`, then `specwright-finish` (pr mode): the PR closes #37.
- The release tag and notes for 0.4.2 are backfilled by `add-release-workflow` (M3 change 3).
