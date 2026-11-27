---
name: specwright-release
description: "Opt-in release tagging for Specwright projects (release.enabled): bumps the version files as a tracked task in a change, and after the change is on main publishes the annotated tag and the GitHub release through the project's `sw` binary. Backfills an older untagged version on request. Triggers: 'release', 'tag', 'publish v0.5.0', 'backfill a tag', or specwright-finish, specwright-pr watch and specwright-roadmap close offering a release."
metadata:
  version: 0.40.2
---

# Specwright Release

**`<sw>`.** Specwright's own work runs in one binary, `sw`, which the install prompt places. Read `openspec/.specwright/VERSION` in the code checkout; it must be `x.y.z` with an optional `-<pre-release>` and `+<build>` suffix and nothing else. Any other value (a path, a space, an empty file, no file): stop before building any path and tell the user to rerun the install prompt. `<sw>` is `<home>/.specwright/bin/<VERSION>/sw` (`sw.exe` on Windows); `<home>` is `SPECWRIGHT_HOME` when set, else the user's home. Never run an `sw` found on `PATH`, another version's binary or a copy elsewhere. When that file does not exist, stop the step and tell the user to rerun the install prompt. Before the first other `<sw>` command of a run, run `<sw> version --json` with a 10-second tool timeout and stop unless it exits 0 in time and prints one JSON object whose `version` is `<VERSION>` and which reports interface 3: on any other result run no other `<sw>` command and tell the user to rerun the install prompt. A project at an older version, whose binary reports interface 2 or 1, stops the same way; tell the user to update this project. Any `<sw>` command that prints a `sw_mismatch` document (the binary and the project's `VERSION` differ) stops the step the same way, showing its `message`. Every `<sw>` command prints one JSON document unless its section says otherwise.

Run it from the code checkout as `<sw> release [--dir <repo>] <sub>`; it prints one JSON document. Exit 0 = done, 1 = stop (show its `message`), 2 = usage error, 3 = a git or `gh` network call failed or was refused.

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

`release.version_files` patterns are JavaScript regular expressions, read in Unicode and multiline mode (ADR 0037): `^` and `$` match at each line, also before a CRLF. Python-only syntax (`(?P<name>`, `\A`, `\Z`, `(?i)`) is refused with `bad_version_files`, naming the entry, before anything is read or written. Each pattern has exactly one capture group, the version.

## bump

A tracked task in the change's last task group, committed by the orchestrator through `specwright-commit`: `<sw> release bump --to <version>` rewrites every version file and commits nothing. Verify with `<sw> release check`, which reports the target version when all files agree.

Two changes can bump to the same version. `<sw> release check --main <ref> --branch <branch>` compares the change branch's version with `<ref>` and refuses `version_not_ahead_of_main` if a bump is not greater. On GitButler always pass `--branch`; HEAD is the workspace. A branch that did not bump, or a `<ref>` without a readable version, passes. With `release.enabled: true`, ship and watch check against freshly fetched main from the selected code remote; local finish checks against local main.

## Release notes

The notes of a release (the annotated tag's message, then the GitHub release body) come from the `## Release Notes` section of each change's archived `proposal.md`, read at the release commit. The section runs to the next `##` heading or the end of the file and holds a summary of at most 600 characters, then one or more of `### Added`, `### Changed`, `### Fixed` and `### Removed` (each at most once), each followed only by list items (`-`, `*` or `+` and a space; an indented line continues the item) of at most 500 characters. HTML comments and blank lines are ignored. Anything else (another heading, prose under a heading, no summary, no item) makes the section invalid.

```markdown
## Release Notes

One or two sentences saying what this release brings.

### Added

- New `--dry-run` flag on publish
```

An item that names no issue or PR (`#<n>` or `<owner>/<repo>#<n>` outside a code span) is listed with the change's PR appended, ` (#<pr>)`; with no PR known it is listed as written. The notes open with the release summary, then list `Added:`, `Changed:`, `Fixed:` and `Removed:` with every change's items in the changes' order (150 items at most, then `…and <n> more items`), and `Changes:` with one line per change that has no valid section.

The summary comes from the bumping change: the change in the release's range whose archived `tasks.md` has a ticked `<sw> release bump --to <version>` task and a valid section; with none or several, the last change with a valid section. The bump task rewrites that summary to describe the whole release, not only its own change, and checks the section with `<sw> release notes --proposal <proposal.md>`, where `<proposal.md>` is the change's `<P>/changes/<change>/proposal.md` in the planning repo: in the store when the project is store-backed, not under the code checkout. That subcommand reads one file, needs no git, network or `release.enabled`, and reads no settings; run it from the code checkout, where the script finds the project's `sw`; it exits 0 with the summary and each item's line (an unreferenced item ends in the literal ` (#<pr>)`), 1 with `release_notes_invalid` and every error with its line (or `no_release_notes`), 2 when the file is missing. Run it again after every edit of the section.

A change whose section is invalid, or whose proposal is over 64 KB, falls back to its Why line under `Changes:`, and `status` and `publish` list it in `warnings` (the change and the first error) without stopping. A change with no section is listed as before.

## publish

Once the change is on main (callers: `specwright-finish`, `specwright-pr` **watch**, `specwright-roadmap` **close**):

Read `<sw> pr context --code <code toplevel> --only repos` for the selected `remote`, main, `github_host` and `github_fence`. In fenced mode, pass the caller's bound `--login <login>` if supplied. A direct run uses `github.login` or the active gh account on the selected host; keep the `run_login` returned by the first GitHub proof for later calls. Omit `--login` in ambient mode. The ambient Git transport and `gh` credentials must be usable on that host; configure SSH separately from `gh`. The fence supplies a verified token only for HTTPS.

1. Run `<sw> release prove-main --main <main branch>` in the code checkout. A GitHub target fetches only `refs/heads/<main>` to a private ref and returns `commit`, `main_branch` and `proof`; it leaves the checkout, tracking refs, tags and `FETCH_HEAD` unchanged. A non-GitHub target returns the local main commit and no proof. Do not substitute a tracking ref, branch tip, or `FETCH_HEAD` for the returned proof.
2. Run `<sw> release untagged --proof <proof>` (non-GitHub: `--main <commit>`) and pass the bound `--login` when applicable. Published means there is a tag on the selected remote, or a local tag if the remote is absent. A local tag whose push failed is listed. Publish missing versions oldest first and stop at the first failure. `untagged --local` needs neither network nor login and prints `"tags": "local"`.
3. Run `<sw> release publish --version <version> --proof <proof>` (non-GitHub: `--main <commit>`; pass `--login` when applicable). Pass the proof unchanged for every version; `publish` refuses if the connection changed. A direct GitHub `publish` without a proof fetches its own. Fetch and push URLs must name the same repository; keep the selected remote, host and URL rewrite rules unchanged during publication. Publish annotates and pushes only `refs/tags/<tag>` and creates the GitHub release on the selected host. A re-run resumes after checking the tag.
4. Store-backed: add `--store <store toplevel>` (optional `--store-main <ref>` and `--store-prefix <P>`) to `status` and `publish`. The planning archive must reach store main before it contributes notes; an archive left on a manually shared planning branch does not count. The default store main comes from `planning_store.remote` and `planning_store.main_branch`. Only the code repo is tagged.

The tagger is git's committer identity: the project's commit-identity rules apply. On jj the release fetch may write and remove its isolated Git ref, and publish writes only the annotated release tag; it never moves a branch or bookmark.

Report per version: `release v0.5.0: tag pushed at <sha>, GitHub release created`, or `release v0.5.0: already published`.

When `publish` creates the tag, its JSON has `warnings` (`[{"change", "error"}]`): report each change and its error next to the release line, for example `release v0.5.0: tag pushed at <sha>, GitHub release created; warning: add-x: line 12: unknown heading 'Security'`. The notes were derived from the archive, so the tag keeps the Why-line fallback for that change; nothing is rewritten. A re-run that finds the tag reports `warnings: []`.

## Stops

Show the error and tag nothing more. None is fixed by moving, deleting or forcing a tag.

| Exit | Error | Do |
|---|---|---|
| 1 | releases disabled | do nothing |
| 1 | `pr.merge_method` rebase, or a rebase-merged release commit | report the commit or settings; the user tags by hand or changes the merge method |
| 1 | version files disagree | the user fixes them by hand; run `check` |
| 1 | version not on main | publish after the release commit reaches main |
| 1 | tag exists at another commit | the user fixes it by hand |
| 1 | a lightweight tag at the release commit | the user replaces it by hand with an annotated tag, or deletes it |
| 1 | `push_url_mismatch`: release fetch and push destinations disagree | use a selected remote whose URLs name the same repository |
| 1 | `release_target_changed`: the remote or binding changed | fetch a fresh proof; do not reuse an old proof |
| 1 | `tag_mismatch`: distinct annotated tag objects at the release commit | delete the local tag by hand (`git tag -d <tag>`); a re-run fetches the selected remote's |
| 1 | a `version_files` entry outside the repository, or a symlink | the user fixes `release.version_files` (list the file a link points to) |
| 1 | `bad_version_files`: a pattern that is not a JavaScript regex in Unicode mode (Python-only syntax), or with no or several capture groups | the user rewrites the entry it names |
| 1 | `bad_version_files` from bump: a version file it would rewrite is not valid UTF-8 | nothing was written; the user fixes the file's encoding, or bumps it by hand |
| 1 | `bad_settings`: a line in `openspec/specwright.yaml` the settings reader would misread (a tab indent, a key given twice, a plain `yes` or `no` for a boolean: write `true` or `false`) | the user fixes the line it names; `notes` is unaffected |
| 1 | an older version is untagged | publish it first (`untagged` lists it) |
| 1 | `version_not_ahead_of_main`: the branch bumped to a version not greater than main's | rerun `bump --to` with a greater version, commit it, and ship or merge again |
| 3 | network or fence failure | report it; a re-run of publish resumes |
| 3 | `deadline_exceeded` or `response_too_large`: a network command exceeded its deadline or byte bound | report the named call; do not retry blindly. After a cut-off write, publish reads back only from the original destination. A tag matching the local tag object at the release commit or a release found there counts as done. |
| 3 | `state: unknown` after a cut-off write or an observed destination change | check the tag or release on the original destination by hand before re-running; do not use the new remote as proof |

## Backfill

`publish --version <old>` for an older untagged version, only when the user asks.

## Never

Never delete or move a tag, use `--force` or `--tags`, push a branch, tag the store, or publish without `release.enabled`.
