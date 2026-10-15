---
name: specwright-release
description: "Opt-in release tagging for Specwright projects (release.enabled): bumps the version files as a tracked task in a change, and after the change is on main publishes the annotated tag and the GitHub release through scripts/release.sh. Backfills an older untagged version on request. Triggers: 'release', 'tag', 'publish v0.5.0', 'backfill a tag', or specwright-finish, specwright-pr watch and specwright-roadmap close offering a release."
metadata:
  version: 0.5.0
---

# Specwright Release

The script lives in `${CLAUDE_SKILL_DIR}/scripts/` (in other harnesses: the `scripts/` folder next to this SKILL.md); below, `scripts/release.sh` means that path. Run it with `bash` (Git Bash on Windows) from the code checkout, as `bash scripts/release.sh [--dir <repo>] <sub>`. It prints one JSON document. Exit 0 = done, 1 = stop (show its `message`), 2 = usage error, 3 = a git or `gh` network call failed or was refused.

Acts only with `release.enabled: true` in `openspec/specwright.yaml`; otherwise do nothing and mention no release.

```yaml
release:
  enabled: false                      # opt in
  version_files:                      # path or glob -> regex; the first is the primary
    VERSION: '^(\d+\.\d+\.\d+)$'
  tag: "v{version}"
  github_release: true                # also create the GitHub release from the tag's message
  auto: false                         # true = callers publish without asking
```

`release.enabled` with `pr.merge_method: rebase` is refused: a rebase rewrites the release commit.

## bump

A tracked task in the change's last task group, committed by the orchestrator through `specwright-commit`: `bash scripts/release.sh bump --to <version>` rewrites every version file and commits nothing. Verify with `bash scripts/release.sh check`, which reports the target version when all files agree.

## publish

Once the change is on main (callers: `specwright-finish`, `specwright-pr` **watch**, `specwright-roadmap` **close**):

1. Fetch main and tags fenced when origin is on github.com (`bash <specwright-pr>/scripts/as.sh <run login> git fetch origin <main> --tags`), else plain `git fetch`. Pass `--main origin/<main>` after a fetch, `--main <main>` otherwise.
2. `bash scripts/release.sh untagged --main <ref>` lists the versions after the latest tagged one that have no tag, oldest first (no tag at all: only the current version). Publish each oldest first and stop at the first failure.
3. `bash <specwright-pr>/scripts/as.sh <run login> bash scripts/release.sh publish --version <version> --main <ref>` from the code repo, so every git and `gh` call inherits the fence; with no run login, plain `bash scripts/release.sh publish ...`. It checks the remote, stops on a conflicting tag, creates the annotated tag, pushes only `refs/tags/<tag>` and creates the GitHub release. It is idempotent: a re-run resumes.
4. Store-backed: add `--store <store toplevel>` (and `--store-main <ref>`, `--store-prefix <P>`) to `status` and `publish`, so the notes come from the store's archive. Only the code repo is tagged.

The tagger is git's committer identity: the commit-identity rules of the project (CLAUDE.md/AGENTS.md) apply.

Report per version: `release v0.5.0: tag pushed at <sha>, GitHub release created`, or `release v0.5.0: already published`.

## Stops

Show the error and tag nothing more. None is fixed by moving, deleting or forcing a tag.

| Exit | Error | Do |
|---|---|---|
| 1 | releases disabled | do nothing |
| 1 | `pr.merge_method` rebase, or a rebase-merged release commit | report the commit or settings; the user tags by hand or changes the merge method |
| 1 | version files disagree | the user fixes them by hand; run `check` |
| 1 | version not on main | publish after the release commit reaches main |
| 1 | tag exists at another commit | the user fixes it by hand |
| 1 | an older version is untagged | publish it first (`untagged` lists it) |
| 3 | network or fence failure | report it; a re-run of publish resumes |

## Backfill

`publish --version <old>` for an older untagged version, only when the user asks.

## Never

Never delete or move a tag, use `--force` or `--tags`, push a branch, tag the store, or publish without `release.enabled`.
