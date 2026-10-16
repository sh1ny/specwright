# Proposal

## Why

Specwright takes a change to a merged PR and then stops (#28). The version moves by hand across `VERSION`, the README badge and `metadata.version` in every `skills/*/SKILL.md` (`CONTRIBUTING.md` Releases), and only one test checks one of those files against `VERSION`. The repository has no tags, so "0.4.2" names no commit, and the only release notes are proposals and PR descriptions. Without tags, the safe-update work that follows (#36) has nothing to install or roll back to.

This is change 3 of milestone **M3 - Distribution** (release 0.5.0). It serves the exit criterion "a Specwright release is cut by the release workflow: one version-bump commit across the configured version files, an annotated `v<version>` tag on the merged main commit, notes built from the archived changes, and a GitHub release. The workflow also backfills tags and notes for 0.4.1 and 0.4.2". It also serves the criteria that every issue is closed by a merged PR with a regression test in `evals/`, that the three eval suites pass, and that each change ships as its own release.

## What Changes

- New skill `specwright-release` with a script, `release.sh`, opt-in through a new `release:` block in `specwright.yaml` (`enabled: false` by default). It has two modes:
  - **bump** rewrites the version in every configured version file in one commit, made on the change branch as a tracked task before the pre-ship review. Before it writes, it checks that every file carries exactly one version and that all of them agree.
  - **publish** runs after the change is on main. It finds the merged main commit that first carries the version, builds notes from the changes merged since the previous release, creates an annotated `v<version>` tag there, and pushes the tag under the run login. With `release.github_release: true` it also creates a GitHub release. A tag or release that already exists for the same commit is left as it is, so publish can be re-run and can backfill earlier versions. A tag that points at another commit stops it.
- Version files are declared as a map from a path or glob to a regular expression with one capture group for the version. The first entry is the primary file. This covers plain files, badges and frontmatter without a plugin system.
- The bump level follows the pre-1.0 rule in `CONTRIBUTING.md` (minor for a feature, config key or workflow change; patch for a fix). The proposal states it, and the design review checks it.
- Notes list each change whose merge lands between the previous release and this one, with its name, the first sentence of its proposal's Why and its PR number. In a repo-local project that means archive directories added in that range. In a store-backed project it means changes whose code-merge proof (as in roadmap status) falls in the code range.
- Offers: after a change is on main, `specwright-finish` (local merge or PR merged) and `specwright-pr` watch (after an agent merge) offer **publish** when the merged version has no tag. With `release.auto: true` they run publish without asking, except after a local merge, which is not pushed: then finish only reports that the version can be published once `main` is pushed. `specwright-roadmap close` lists versions on main that have no tag and offers to publish them.
- Store-backed projects tag the code repo only. The store is never tagged.
- This repository opts in, cuts 0.5.0 with publish after merge, and backfills 0.4.1 (`9b33ec5`) and 0.4.2 (`4f9b823`).
- `CONTRIBUTING.md` Releases replaces the manual three-file bump with `specwright-release`. A test checks that every version file in this repo agrees with `VERSION`.
- Out of scope: installing from a tag instead of `main` (#36), other VCS backends (#19) and package publishing.

## Capabilities

### New Capabilities

- `releases`: version files and their agreement check, the bump commit, finding the release commit, building notes, publishing the tag and the GitHub release, idempotent re-runs and backfill, and the opt-in settings.

### Modified Capabilities

- `change-finish`: after the change is on main, offer publish (or run it with `release.auto`) when releases are enabled and the version has no tag.
- `pr-merge`: after an agent merge and cleanup, watch offers publish under the same rule.
- `project-planning`: **close** lists versions on main that have no tag and offers to publish them.

## Impact

- New `skills/specwright-release/` (`SKILL.md`, `scripts/release.sh`). Install copies every `skills/specwright-*` directory, so the install prompt itself does not change.
- `skills/specwright-finish`, `skills/specwright-pr`, `skills/specwright-roadmap`: the offer steps.
- `schemas/specwright`: when `release.enabled` is true, the tasks instruction puts the bump task (`release.sh bump`) in the last task group.
- `templates/openspec/specwright.yaml` and the README Settings section: the `release:` block. `openspec/specwright.yaml`: this repo enables it with its three version files.
- `README.md` (skill tables, a Releases note), `CONTRIBUTING.md` (Releases), `openspec/architecture.md` (component, state and boundary rows) and a new ADR on tags as published, never-moved release markers.
- New eval suite `evals/release/` (unittest, temporary git repos, the fake `gh` from `evals/fakes/`).
- Outward effect: publish pushes tags and creates GitHub releases under the run login, and only when the project opts in.
- Release 0.5.0 (minor: a new skill, a new settings block and a workflow step).
