# Contributing to Specwright

Specwright is built with Specwright: changes to it go through the same branch → artifacts → apply → PR → archive flow it gives other projects.

## Setup

1. Install the OpenSpec CLI at the version in the README badge (`npm i -g @fission-ai/openspec@1.16.0`, which needs Node.js 22.12 or later), plus `git`, `bash` with a POSIX userland (Git Bash on Windows), `gh` 2.40 or later and Python 3.8 or later.
2. Clone the repository and run `openspec init` in it.
3. Run the [install prompt](README.md#-install--update) from the README in the clone. It installs Specwright into the repo's own `openspec/` and asks for this repo's settings; `finish: pr` fits here.
4. Start a new agent session: installed skills and agent definitions load only in a session started after the install.

## Bootstrap a checkout from its own tree

The install prompt installs tags and `main`, and a `main` install places no `sw`. Since 0.25.0 every `vcs.sh` call runs `sw`, so a checkout that dogfoods Specwright (this repository's own install, or a clone of it) stops its VCS steps with `sw_missing` until it holds the `sw` of its installed version. To install from the checkout's own tree, run these steps from its root, in this order:

1. Run `bash scripts/update.sh --code . --skills <dir> --agents <kind>=<dir> --download . --ref <branch> plan`. Repeat `--skills <dir>` and `--agents <kind>=<dir>` for each target (`plan` refuses with `no_targets` without one); this repository uses `--skills .claude/skills --agents claude=.claude/agents`. `--download .` makes the checkout the download tree, and `--ref` is free text recorded as the installed ref (the checkout's branch).
2. Run the same command with `stage`, then with `swap`. They copy the skills, agents and schema.
3. Run the install prompt's Step 7 checks: `openspec schema validate specwright`, and the installed skills and agents match the tree.
4. Only when they pass, copy `VERSION` to `openspec/.specwright/VERSION` (the stamp). `finish` refuses with `not_stamped` until it reads the new version.
5. Run the same `update.sh` command with `finish`.
6. Run `mise run install-sw`. It builds `cli/`, checks the build, and places it at `<home>/.specwright/bin/<VERSION>/sw[.exe]`, with `cli/THIRD_PARTY_NOTICES.txt` beside it; it prints the binary path.
7. Run `bash skills/specwright-pr/scripts/sw-path.sh --code .`. It prints the same path when the checkout's `VERSION` matches the placed binary.

The build workflow packages the same LF notice bytes and SHA-256 sidecar for every target from version 0.30.0. Release attachment reads back the notice and five binaries before uploading `SHA256SUMS` last. Old tags keep the five-binary format. When changing runtime dependencies or the embedded SDK, review their licences and update `cli/THIRD_PARTY_NOTICES.txt` (ADR 0032); an integrity hash does not check attribution completeness.

## Source vs. installed copies

| Edit this | Installed copy (git-ignored) |
|---|---|
| `skills/specwright-*/` | `.claude/skills/`, `.agents/skills/` |
| `agents/claude/`, `agents/omp/` | `.claude/agents/`, `.omp/agents/` |
| `schemas/specwright/` | `openspec/schemas/specwright/` |
| `templates/openspec/` | `openspec/config.yaml`, `openspec/specwright.yaml` (merged by dotted path; commented-out template keys are optional) |
| `VERSION` | `openspec/.specwright/VERSION` |

Never edit the installed copies; your changes would be lost on the next install. `templates/openspec/` is what ships to users, while `openspec/` holds this repo's own settings, specs and changes, so keep project-specific values out of `templates/`.

Your agent follows the installed copies, not the source. A change that edits a skill is still guided by the old version until you re-run the install prompt.

## Making a change

- Start every change through OpenSpec (`/opsx:propose`, `/opsx:new` or `/opsx:ff`); `specwright-branch` creates the `<prefix>/<change-name>` branch.
- Apply with `/opsx:apply`; `specwright-commit` makes one commit per task, or one per task group with `commit_granularity: group` in `openspec/specwright.yaml`. Open the PR, address review feedback and archive with `specwright-pr` and `specwright-finish`.
- Small mechanical fixes (typos, links, renames) may go straight to `main` with the maintainer's agreement.

## Conventions

- **Commits:** `<type>(<scope>): <summary>`, at most 72 characters, where `<scope>` is the change name or the skill touched (`fix(specwright-pr): ...`). Stage files by name, never `git add -A`.
- **Skills and schema text are instructions for agents.** Keep them terse and imperative: every step checkable, every stop condition explicit, no explanatory padding. Say what to do when a check fails, not just what to check.
- **README follows behaviour.** A change to a skill's triggers, settings, modes or messages updates the matching README table or section in the same change.
- **Implementer twins:** `agents/<harness>/specwright-implementer-light.md` is `specwright-implementer.md` word for word apart from `name`, `description` and `model`. Copy every implementer body or frontmatter edit to its light twin in the same change; `TestCheapTier` in `evals/git-workflow/test_instructions.py` fails and names both files when they drift.
- **Settings:** a new `specwright.yaml` key goes into `templates/openspec/specwright.yaml` with a comment and a safe default, and into the README settings example.

## Testing

- Which suites to run: during a change, rely on CI. The workflow `.github/workflows/evals.yml` runs every suite on Linux, Windows and macOS for each pull request, one job per suite. Do not run a whole suite locally. Run only the test module you are writing, red then green: `python -m unittest evals/<suite>/test_<x>.py`. At a milestone close, rely on a green `gh workflow run evals.yml --ref main` run on the closing head of `main`.
- Dart tests (`cli/`): locally run only the test file you are writing, through the SDK `mise.toml` pins: `mise exec -- dart test <file>` from `cli/`. CI runs the Dart tests on the three OSes and builds `sw` for five targets (linux-x64, linux-arm64, windows-x64, macos-arm64, macos-x64) on native runners through `.github/workflows/sw-build.yml`, which `cli.yml` (pull requests) and `release.yml` (published releases) call.
- Adding an `sw` target: add its row to the matrix in `.github/workflows/sw-build.yml`, its asset name to `BINARIES` in `cli/tool/attach_release.py`, and its host mapping to the host map in `scripts/update.sh`. The asset names and the `SHA256SUMS` format are a contract every install reads, so a new target is a workflow change (minor version).
- The suite map: [`evals/suites.json`](evals/suites.json) maps each tracked path to the suites that cover it. When you add a tracked file, add a rule or a `no_eval` entry to it, then run `python -m unittest evals/runner/test_suite_map.py`; the test fails on an uncovered file. `python evals/run.py --list-suites` prints the suites as JSON.
- Runner: `evals/run.py` runs the suites in parallel, one process per test file, and CI uses it. A test file whose tests assert deadlines of a few seconds goes in `SERIAL` in `evals/run.py`, with the reason as a comment.
- Git-skill changes: run the [`evals/git-workflow`](evals/git-workflow/) cases (see the README's Evals section) and add a case when the change adds a stop condition or branch-state rule.
- Stress tier: when a change rewords the instructions a stress-marked eval exercises (`"stress"` in `evals.json`), re-run those evals through skill-creator with the executor on the default model (`base`) and on Haiku (`haiku`), grade them, and run `python evals/git-workflow/tiers.py <iteration-dir> --base base --cheap haiku`. Fix each wording gap a difference shows and re-run; record the run and any difference that is a model limit, with its evidence, in a dated section of `evals/git-workflow/stress.md`. It is a wording diagnostic, not a shipped configuration and not a CI gate. `evals/git-workflow/test_tiers.py` checks the marks and the comparison.
- Schema or template changes: `openspec schema validate specwright` after re-installing.
- Reviewer routes (`review-run.sh`): CI runs the `review-routes` suite; locally run only the module you are writing. It uses fake CLIs from `evals/fakes/` and hides any real `codex`, `claude` or `omp` on `PATH`. A change to a route's command line needs a new trial against the real CLIs, recorded in `evals/review-routes/trial.md`.
- Release script (`release.sh`): CI runs the `release` suite; locally run only the module you are writing.
- Finish script (`finish.sh`, the deferred-archive undo plan): CI runs the `finish` suite; locally run only the module you are writing. Each test builds a temp git repo, applies the printed `script` and `after_rerun` with `bash`, and asserts on the tree, index and refs.
- Update script (`scripts/update.sh`, the install prompt's Step 4): CI runs the `update` suite; locally run only the module you are writing. It works on scratch repos and shims `mv`, `cp` and `rm` to interrupt every step.
- PR scripts: exercise the changed path against a real PR, and keep them to bash, git, `gh` and the Python 3.8+ standard library. CI runs the `pr-pair` suite; locally run only the module you are writing. `test_pass_write_on_python38` (in `evals/pr-pair/`) runs a pass write on Python 3.8: install one with `uv python install 3.8` (or point `SPECWRIGHT_PY38` at a 3.8 interpreter); without one the test is skipped and names the missing interpreter.

## Releases

- Every user-visible change bumps the version. The last task of the change runs `bash skills/specwright-release/scripts/release.sh bump --to <version>`, which rewrites `VERSION`, the README badge and `metadata.version` in every `skills/*/SKILL.md` together (the files are listed in `release.version_files`); verify with `release.sh check`. After the change is merged, `publish` (through the `specwright-release` skill) tags the merged main commit `v<version>`.
- Before 1.0: bump the minor version (0.x.0) for a new feature, configuration key or workflow change, and the patch version (0.x.y) for a fix. 1.0 is the maintainer's call.
- Any change to the install prompt is a release, because users copy it from the README of `main`. Keep the prompt safe to re-run over every earlier version.
- An OpenSpec upgrade updates `OPENSPEC_VERSION`, the badge, the pinned version above, the versioned install commands in the README (prerequisites and install Step 1), the README's "forked from `spec-driven` (<version>)" note and every other README line that spells out the pinned version (the OpenSpec version note, Step 1's comparison, Step 3's example with its edge-case versions, and the Stores note), the Node.js version the npm package needs next to each install command, and the expected versions in the two OpenSpec-pin evals (`grade.py`, `test_grade.py`, `evals.json` in `evals/git-workflow/`; the fake `openspec` in `fixtures.py` must report a version other than the pin) in the same change. `TestOpenSpecPin` in `evals/git-workflow/test_instructions.py` fails while any of them disagrees with `OPENSPEC_VERSION`.

## Reviews

PRs are reviewed by the bots listed under `pr.reviewers` in `openspec/specwright.yaml`; `specwright-pr` **watch** waits for them and answers every finding. Reviewers that only run when tagged (Codex) need their request posted again after every pushed round.

Before the first PR, `specwright-commit` runs the pre-ship review (`specwright-review`) on the finished change. This repo keeps `review.cross_model: false`, so the `specwright-reviewer` agent does that review. The archive commit is pushed without new review requests when it only archives the change (`pr.review_after_archive: false`).
