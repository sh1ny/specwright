# A1: a release created with a personal token starts `release.yml`

Assumption A1: a GitHub release created by `release.sh` with a personal token, not `GITHUB_TOKEN`, triggers `on: release: types: [published]` in this repository.

## What GitHub's documentation says

The source is GitHub Docs, "GITHUB_TOKEN: When GITHUB_TOKEN triggers workflow runs", https://docs.github.com/en/actions/concepts/security/github_token. It was fetched through `ctx7` (`/websites/github_en_actions`) on 2026-11-06.

> When you use the repository's `GITHUB_TOKEN` to perform tasks, events triggered by the `GITHUB_TOKEN` will not create a new workflow run, with the following exceptions: `workflow_dispatch` and `repository_dispatch` events always create workflow runs. [...]

The same documentation set has an example under "Trigger a workflow", https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow. It uses a personal access token so that a downstream workflow runs, "unlike when using GITHUB_TOKEN".

So the restriction applies only to events that `GITHUB_TOKEN` causes. An event caused by a user's own credential (a personal or OAuth token) starts workflow runs as normal.

## How `release.sh` authenticates

`skills/specwright-release/SKILL.md` (publish, step 3) runs `release.sh publish` as `bash <specwright-pr>/scripts/as.sh <run login> bash scripts/release.sh publish ...`. `as.sh` exports the run login's own `gh` token (`gh auth token --user <login>`) as `GH_TOKEN` for that process, so `gh release create --verify-tag` runs with the user's credential, not with an Actions `GITHUB_TOKEN`. This project's run login is `KintsugiBot` (`github.login`). Its `gh` credential is an OAuth token from `gh auth login`, not the workflow token.

## Result

From the documentation, A1 holds: a release that `release.sh publish` creates fires `release: published` and starts `release.yml`. The only token that suppresses runs is `GITHUB_TOKEN`, and `release.sh` never uses it.

One residual risk stays: the publish itself is the only observation. As tasks.md's follow-up says, after `v0.24.0` is published, check that the release received five binaries and `SHA256SUMS`. If it did not, run `release.yml` by hand through `workflow_dispatch` with the tag, which the documentation says always creates a run, and note it at the M7 close.
