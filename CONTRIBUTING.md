# Contributing to Specwright

Specwright is built with Specwright: changes to it go through the same branch → artifacts → apply → PR → archive flow it gives other projects.

## Setup

1. Install the OpenSpec CLI at the version in the README badge (`npm i -g @fission-ai/openspec@1.14.1`), plus `git`, `bash` with a POSIX userland (Git Bash on Windows), `gh` 2.40 or later and Python 3.8 or later.
2. Clone the repository and run `openspec init` in it.
3. Run the [install prompt](README.md#-install--update) from the README in the clone. It installs Specwright into the repo's own `openspec/` and asks for this repo's settings; `finish: pr` fits here.
4. Start a new agent session: installed skills and agent definitions load only in a session started after the install.

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
- Apply with `/opsx:apply`; `specwright-commit` makes one commit per task. Open the PR, address review feedback and archive with `specwright-pr` and `specwright-finish`.
- Small mechanical fixes (typos, links, renames) may go straight to `main` with the maintainer's agreement.

## Conventions

- **Commits:** `<type>(<scope>): <summary>`, at most 72 characters, where `<scope>` is the change name or the skill touched (`fix(specwright-pr): ...`). Stage files by name, never `git add -A`.
- **Skills and schema text are instructions for agents.** Keep them terse and imperative: every step checkable, every stop condition explicit, no explanatory padding. Say what to do when a check fails, not just what to check.
- **README follows behaviour.** A change to a skill's triggers, settings, modes or messages updates the matching README table or section in the same change.
- **Settings:** a new `specwright.yaml` key goes into `templates/openspec/specwright.yaml` with a comment and a safe default, and into the README settings example.

## Testing

- Git-skill changes: run the [`evals/git-workflow`](evals/git-workflow/) cases (see the README's Evals section) and add a case when the change adds a stop condition or branch-state rule.
- Schema or template changes: `openspec schema validate specwright` after re-installing.
- Reviewer routes (`review-run.sh`): run `python -m unittest discover evals/review-routes`; it uses fake CLIs from `evals/fakes/` and hides any real `codex`, `claude` or `omp` on `PATH`. A change to a route's command line needs a new trial against the real CLIs, recorded in `evals/review-routes/trial.md`.
- PR scripts: exercise the changed path against a real PR, and keep them to bash, git, `gh` and the Python 3.8+ standard library. Run `python -m unittest discover evals/pr-pair`. `test_pass_write_on_python38` runs a pass write on Python 3.8: install one with `uv python install 3.8` (or point `SPECWRIGHT_PY38` at a 3.8 interpreter); without one the test is skipped and names the missing interpreter.

## Releases

- Every user-visible change bumps the version: `VERSION`, the README badge and `metadata.version` in every `skills/*/SKILL.md`, together.
- Before 1.0: bump the minor version (0.x.0) for a new feature, configuration key or workflow change, and the patch version (0.x.y) for a fix. 1.0 is the maintainer's call.
- Any change to the install prompt is a release, because users copy it from the README of `main`. Keep the prompt safe to re-run over every earlier version.
- An OpenSpec upgrade updates `OPENSPEC_VERSION`, the badge, the pinned version above, the versioned install commands in the README (prerequisites and install Step 1), the README's "forked from `spec-driven` (1.14.1)" note and every other README line that spells out the pinned version (the OpenSpec version note, Step 1's comparison, Step 3's example and the Stores note) in the same change. `TestOpenSpecPin` in `evals/git-workflow/test_instructions.py` fails while any of them disagrees with `OPENSPEC_VERSION`.

## Reviews

PRs are reviewed by the bots listed under `pr.reviewers` in `openspec/specwright.yaml`; `specwright-pr` **watch** waits for them and answers every finding. Reviewers that only run when tagged (Codex) need their request posted again after every pushed round.

Before the first PR, `specwright-commit` runs the pre-ship review (`specwright-review`) on the finished change. This repo keeps `review.cross_model: false`, so the `specwright-reviewer` agent does that review. The archive commit is pushed without new review requests when it only archives the change (`pr.review_after_archive: false`).
