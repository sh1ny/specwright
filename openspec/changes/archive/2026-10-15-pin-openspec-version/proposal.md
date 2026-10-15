# Proposal

## Why

Specwright is checked against one OpenSpec version (1.14.1), but nothing enforces it (#37). The README badge and `CONTRIBUTING.md` name the pin. The public prerequisite still installs OpenSpec without a version (`npm i -g @fission-ai/openspec`), and install Step 1 runs `openspec --version` without comparing the result to anything. A public adopter can therefore run a newer OpenSpec whose CLI output or schema format Specwright was never checked against, and the install reports success.

This is change 2 of milestone **M3 - Distribution** (release 0.4.2). It serves the exit criterion "the install prompt compares `openspec --version` with the pin and does not complete on a mismatch until the pinned version is installed, except through an explicit, documented override; an eval covers both the refusal and the override. The public install command names the pinned version". It also serves the criteria that every issue is closed by a merged PR with a regression test in `evals/`, that the three eval suites pass, and that each change ships as its own release.

## What Changes

- A machine-readable pin, `OPENSPEC_VERSION`, sits at the repo root next to `VERSION` and ships with every download. It is the single source for the pinned version.
- Every public install command names the pinned version: `npm i -g @fission-ai/openspec@<pin>` in the README prerequisites, in install Step 1, and in `CONTRIBUTING.md`. A text test fails when any of these, or the README badge, disagrees with `OPENSPEC_VERSION`.
- The install prompt compares the installed OpenSpec version with the downloaded copy's `OPENSPEC_VERSION` before it writes any file, and requires an exact match. A newer patch release counts as a mismatch, because Specwright parses OpenSpec's CLI output and schema format, and a patch release can change either.
- On a mismatch the install stops before writing anything. It names both versions and the command that installs the pin, and it leaves `openspec/.specwright/VERSION` untouched, so a mismatched update never reports success.
- An explicit override: the user can continue with the unpinned version only by stating it in their own words, naming the found version (for example `continue with OpenSpec 1.15.0`). The README documents the override, the agent never offers it as a default and never infers it, and the report records `OpenSpec <found> (pinned <pin>, override)`.
- The README's store note ("OpenSpec stores, 1.14.1 or later") changes to name the pin, so the docs never contradict the exact match.
- Regression coverage: text tests in `evals/git-workflow/test_instructions.py`, plus two graded agent evals (`eval-install-openspec-mismatch`, `eval-install-openspec-override`) that put a fake `openspec` reporting another version first on `PATH`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `install-update`: adds the OpenSpec version check (exact match against the shipped pin, a stop before any write, the explicit override and its report line) and the rule that the public install commands name the pin.

## Impact

- `README.md`: prerequisites, install Steps 1, 3, 7 and 8, the override note and the store note.
- `CONTRIBUTING.md`: the OpenSpec upgrade rule also updates `OPENSPEC_VERSION`.
- New `OPENSPEC_VERSION` at the repo root. Install does not copy it into projects, and `openspec/.specwright/VERSION` keeps its format.
- `evals/git-workflow/`: new text tests, two agent evals in `evals.json`, and a fixture that adds a fake `openspec` wrapper to `PATH`.
- No skill behaviour, schema, script or `specwright.yaml` key changes, so the release is a patch (0.4.2). `VERSION`, the README badge and `metadata.version` in every `skills/*/SKILL.md` all move to 0.4.2 (`CONTRIBUTING.md` Releases; `evals/review-routes/test_skill_text.py:48` checks the skill version against `VERSION`).
- Adopters running an OpenSpec version other than 1.14.1 now stop at install until they install the pin or state the override.
