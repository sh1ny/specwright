# Spec Delta

## MODIFIED Requirements

### Requirement: The release commit is found on main
Publish SHALL release V at the first commit in main's first-parent history whose primary file reads V. GitHub publish SHALL bind the commit from its own fetch to the selected tag and release destination and a successful checkout-local fetch receipt. Non-GitHub publish SHALL use local main. Missing history, missing or inconsistent proof or a changed destination SHALL stop before creating, fetching or pushing a release tag or creating a release.

#### Scenario: Squash-merged change
- **WHEN** the PR that bumped to 0.4.2 was squash-merged as `4f9b823` and publish runs for 0.4.2
- **THEN** the release commit is `4f9b823`

#### Scenario: Merge-commit change
- **WHEN** the PR that bumped to 0.4.1 merged as the merge commit `9b33ec5` and publish runs for 0.4.1
- **THEN** the release commit is `9b33ec5`, not the bump task commit on the change branch

#### Scenario: Version not on main
- **WHEN** publish runs for 0.5.0 while the bump is only on the unmerged change branch
- **THEN** publish exits non-zero saying no main commit carries 0.5.0, and no tag is created

#### Scenario: Publication destination changes after main was fetched
- **WHEN** the release skill fetches the selected GitHub remote's main and the selected remote name or its effective destination changes before publish
- **THEN** publish rejects the fetched main proof before creating or pushing any tag or creating a release, even if the fetched commit still exists locally

#### Scenario: Fetched main has a custom refspec
- **WHEN** the selected remote fetches main with a nonstandard tracking refspec and the conventional tracking ref is stale
- **THEN** publish uses the commit fetched for its proof, tags the first main commit carrying the version, and leaves the conventional tracking ref unchanged

#### Scenario: Another fetch finishes before the release proof is read
- **WHEN** the release fetch observes main at A and another fetch in that checkout finishes at B before the release proof is read
- **THEN** the first proof still binds A; its release shows no evidence from B and the fetch does not move a user branch or tag

#### Scenario: The private fetch ref cannot be cleaned up
- **WHEN** a GitHub proof fetch writes objects and its invocation-private ref but cannot confirm removal of that ref
- **THEN** it stops without issuing a proof, recording a successful receipt or publishing

### Requirement: Notes list the changes merged since the previous release
Notes for V SHALL list changes merged after the previous release commit through V: use valid `## Release Notes` items, otherwise the change name, archived proposal's first Why sentence and any PR number in main's commit subject. Use the release commit of the highest lower version tagged locally or on the selected code remote, otherwise the first-parent commit where the primary file took the value before V.

#### Scenario: One change in the range
- **WHEN** publish runs for 0.4.2 and only `2026-10-15-pin-openspec-version` was archived between the 0.4.1 and 0.4.2 release commits, and its proposal has no `## Release Notes` section
- **THEN** the notes list `pin-openspec-version`, its first Why sentence and `#90`, and no other change

#### Scenario: Several changes in the range
- **WHEN** two changes were archived between the previous release commit and V's
- **THEN** the notes list both, in main's first-parent order

#### Scenario: No change in the range
- **WHEN** the range holds no archived change (only a roadmap `docs/close-*` merge)
- **THEN** the notes say no change was archived in this release and publish continues

#### Scenario: Backfill in a clone without the tags
- **WHEN** `v0.1.0` and `v0.4.0` exist only on the selected remote and publish runs for 0.3.0
- **THEN** the range starts at 0.1.0's release commit, and the notes list the 0.2.0 and 0.3.0 changes

#### Scenario: Backfill with no earlier tag
- **WHEN** no tag exists and publish runs for 0.4.1
- **THEN** the range starts at the commit where `VERSION` first read 0.4.0, and the notes list `fix-m2-gaps` with `#89`

#### Scenario: No change in the range has a section
- **WHEN** every change in V's range was archived without a `## Release Notes` section
- **THEN** the notes are byte-for-byte what they were before sections existed: `Changes in <tag>:`, then one `- <name> (#<pr>): <why>` line per change

### Requirement: Store-backed notes use the code-merge proof
In a store-backed project, a change SHALL be in V's notes when its archive is on the store main and its code-merge proof lies in range. The proof is `merge: <change-name>` in local mode, or a merged PR from the code repo's own `<prefix>/<change-name>` into its main in PR mode. Use the code main's branch name for PR discovery and the store main ref from its selected remote when available, else local main. Leave out planning-only changes (`code_changes: none`).

#### Scenario: Code PR merged in the range
- **WHEN** store-backed `add-x` is archived on the store's main and its code PR from `feat/add-x` merged in the range
- **THEN** the notes list `add-x`

#### Scenario: PR from another prefix
- **WHEN** a merged PR from `docs/add-x` has its merge commit in the range and `add-x`'s branch is `feat/add-x`
- **THEN** that PR is not proof, and the notes leave `add-x` out unless `feat/add-x` merged in the range

#### Scenario: Code still pending
- **WHEN** `add-y` is archived on store main but its code PR is still open
- **THEN** the notes leave `add-y` out, and a later release whose range holds its merge lists it

#### Scenario: PR discovery fails
- **WHEN** merged-PR discovery exits nonzero
- **THEN** publish stops before creating the tag and names the failed call

#### Scenario: Store and code use separate named remotes
- **WHEN** code fetch returns `publishing/main`, plans use `plans/main`, and an older `origin/main` has different archive contents
- **THEN** release queries merged code PRs with base `main` and uses archive contents from `plans/main`, not `origin/main`

#### Scenario: Local-store archive has not reached store main
- **WHEN** the in-range code PR merged and the user has manually archived the change on the retained local store branch but not brought it to store main
- **THEN** release publication can proceed, but the archive contributes no notes until it reaches store main

### Requirement: Publish creates and pushes an annotated tag
Publish SHALL create an annotated tag named by `release.tag` (default `v{version}`; a template without `{version}` SHALL stop every subcommand, since every version would map to one tag) on the release commit, with the notes as its message, and push only that tag ref to the selected code remote under the project's GitHub identity policy. It SHALL NOT push any branch. In a store-backed project it SHALL tag the code repo only.

#### Scenario: New release
- **WHEN** `remote: publishing` selects a remote and publish runs for 0.5.0 with neither a local nor a published `v0.5.0` tag
- **THEN** the local tag is annotated and points at the release commit, `publishing` has `refs/tags/v0.5.0`, and `origin` is unchanged

#### Scenario: Tag template without the version
- **WHEN** `release.tag` is `release`
- **THEN** every subcommand exits non-zero naming `release.tag` and `{version}`, and no file or tag is written

#### Scenario: Push refused by the fence
- **WHEN** `sw as` refuses (exit 3) or the tag push fails
- **THEN** publish exits non-zero with the push error, no GitHub release is created, and the report says the local tag exists and a re-run pushes it (or stops as in "Lost push race" when another clone's tag reached the selected remote first)

#### Scenario: Store-backed project
- **WHEN** publish runs in a store-backed project
- **THEN** the code repo has the tag and the store has no new tag

### Requirement: Older untagged versions are published first
`sw release untagged` SHALL list unpublished versions from main's first-parent primary-file history after the latest published version, oldest first (with none published, only the current version). Published means tagged on the selected code remote, or tagged locally when no remote is selected. Always include local tags missing on the remote. Publish of V SHALL stop before tag or release writes, naming any listed version lower than V.

#### Scenario: Older version untagged
- **WHEN** `v0.4.2` is the latest tag, 0.5.0 has no tag and publish runs for 0.5.1
- **THEN** publish exits non-zero naming 0.5.0, and `v0.5.1` is not created

#### Scenario: Tag push failed earlier
- **WHEN** `v0.4.2` is on the selected remote, `v0.5.0` exists only locally (its push failed), and 0.5.1 is merged
- **THEN** `untagged` lists 0.5.0, and publish of 0.5.1 exits non-zero naming 0.5.0

#### Scenario: First release's tag push failed
- **WHEN** the selected remote has no tag, `v0.3.0` exists only locally (its push failed) and 0.3.1 is merged
- **THEN** `untagged` lists 0.3.0 then 0.3.1, and publish of 0.3.1 exits non-zero naming 0.3.0

#### Scenario: Backfill below the latest tag
- **WHEN** `v0.5.0` is the only tag and publish runs for 0.4.1
- **THEN** publish is not blocked, and the notes range starts at the commit where `VERSION` first read 0.4.0

### Requirement: Re-runs never move a published tag
Before tag or release writes, publish SHALL check local tags and the selected remote (`ls-remote`). Keep a tag on the release commit and count it done; fetch a remote-only tag. Stop without changes on a tag at another commit (name both commits) or any lightweight tag (name its location). Publish SHALL NOT delete, move or force-push a tag.

#### Scenario: Re-run after an interrupted publish
- **WHEN** `v0.5.0` exists on the selected remote at the release commit but no GitHub release exists
- **THEN** publish creates only the GitHub release and reports the tag as already published

#### Scenario: Tag only on origin
- **WHEN** `v0.5.0` is on the selected remote at the release commit, there is no local tag and no GitHub release
- **THEN** publish fetches `v0.5.0` from that remote, creates no tag object, and creates the release with that remote's tag message as its body

#### Scenario: Tag on another commit
- **WHEN** `v0.4.2` is on the selected remote at a commit other than `4f9b823`
- **THEN** publish exits non-zero naming both commits, and the tag, its target and the GitHub releases are unchanged

#### Scenario: Lightweight tag
- **WHEN** `v0.5.0` is on the selected remote at the release commit as a lightweight tag (no `refs/tags/v0.5.0^{}` in `ls-remote`)
- **THEN** publish exits non-zero saying the tag is lightweight, and writes no tag and no GitHub release

#### Scenario: Remote tags unreadable
- **WHEN** `git ls-remote --tags <remote>` fails or the fence refuses it
- **THEN** publish stops before creating any tag and names the failed read

### Requirement: The tag is pushed where it was checked
Publish SHALL stop before proof fetch, tag changes or release creation on fetch/push repository mismatch or a rewrite to a different GitHub repo, naming both destinations. Compare owner/name across transports on the configured host and URLs elsewhere. Check tags at the fetch URL and create the release in the configured GitHub repo, falling back to the effective fetch URL when only it is on that host.

#### Scenario: Push URL elsewhere
- **WHEN** `remote.publishing.pushurl` names a fork while the selected `publishing` remote fetches from upstream
- **THEN** publish exits non-zero naming both URLs, and no tag is created or pushed and no GitHub release is created

#### Scenario: Rewrite to another GitHub repository
- **WHEN** an `insteadOf` rule turns the selected remote's `github.example.com/team/` into `github.example.com/other/` on the configured host
- **THEN** publish exits non-zero naming both repositories before reading remote tags

### Requirement: A release uses the tag on origin
A local tag and a tag on the selected code remote at the release commit that are different tag objects SHALL stop publish without changing tags or releases, naming both objects, so the release body is always the message of the tag on that remote.

#### Scenario: Lost push race
- **WHEN** `v0.5.0` is on the selected remote at the release commit, and the local `v0.5.0` is another annotated tag object at the same commit
- **THEN** publish exits non-zero naming both tag objects, and creates no GitHub release; once the user deletes the local tag, a re-run fetches the remote's tag and releases with its message

### Requirement: The GitHub release is optional and created once
With `release.github_release` true, publish SHALL create a GitHub release for the pushed tag on the configured GitHub host, after the tag is on the selected code remote, with the tag's message as its body (never notes derived again). A release that already exists for the tag SHALL be left unchanged. With the key false, or the selected remote not on the configured GitHub host, no release SHALL be created and the report SHALL say so.

#### Scenario: Shorthand rewritten to GitHub
- **WHEN** a selected remote's `corp:team/app` shorthand expands to the configured GitHub host
- **THEN** publish pushes the tag to `team/app` and creates the GitHub release there, and does not report `not_github`

#### Scenario: Release created
- **WHEN** `github_release` is true and `v0.5.0` is on the selected remote with no GitHub release
- **THEN** `gh release view v0.5.0` shows the release with the tag's notes

#### Scenario: Release created on GitHub Enterprise
- **WHEN** the selected remote is on `github.example.com`, that is the configured GitHub host, and `github_release` is true with no release for the published tag
- **THEN** publish creates the release there and reports its URL on `github.example.com`, with no GitHub call targeting github.com

#### Scenario: Release already exists
- **WHEN** a GitHub release for `v0.5.0` already exists
- **THEN** publish does not edit it and reports it as already published

#### Scenario: Release creation fails
- **WHEN** the tag push succeeds but `gh release create` exits non-zero
- **THEN** publish exits non-zero with the error, the tag stays on its remote, and a re-run creates only the release

### Requirement: Untagged versions can be read from local tags only
With `--local`, `sw release untagged` SHALL read local tags only, make no network call, and say in its output that the list comes from local tags. Its output SHALL say so whenever it read local tags, including with no selected code remote.

#### Scenario: Local tags only
- **WHEN** `v0.4.2` exists locally, the selected remote is unreachable, main's version is 0.5.0, and `untagged --local` runs
- **THEN** it exits 0, lists 0.5.0, reports that the list comes from local tags, and starts no `git ls-remote`

#### Scenario: Local read with a local-only tag
- **WHEN** `v0.5.0` exists only locally (its push failed) and `untagged --local` runs with main at 0.5.0
- **THEN** it lists nothing, and its output still says the list comes from local tags, so the selected remote may lack a tag it counted

### Requirement: Ship, local merge and watch check the version against main
With `release.enabled` true, when a code PR is expected, `specwright-pr` ship SHALL check the version against the selected code remote's freshly fetched main before any push, and watch SHALL refresh and check it before reporting ready or merging. `specwright-finish` SHALL run `check --main <main>` before a local merge. A refusal SHALL stop the step.

#### Scenario: Ship of a duplicate version
- **WHEN** `feat/a` merged at 0.5.0 and ship runs for `feat/b`, which also bumped 0.4.2 to 0.5.0
- **THEN** ship pushes nothing and opens no PR, and reports the 0.5.0 refusal

#### Scenario: Main merged a duplicate while the PR waited
- **WHEN** a PR bumped to 0.5.0 passed ship, another PR to 0.5.0 merged afterwards, and watch is about to report the first PR ready
- **THEN** watch runs the check against the selected remote's refreshed main, reports the duplicate 0.5.0, and neither reports ready nor merges

#### Scenario: Local merge of a duplicate version
- **WHEN** `finish` is `local`, local main already holds a merge at 0.5.0, and the branch also bumped 0.4.2 to 0.5.0
- **THEN** finish stops before `git merge`, main is unchanged, and the report names 0.5.0

#### Scenario: Releases disabled
- **WHEN** `release.enabled` is false and two branches carry the same `VERSION` edit
- **THEN** ship, the local merge and watch run no version check

### Requirement: A cut-off tag push or release creation is decided by a read-back
If a bound stops tag push or `gh release create`, publish SHALL read back only from the agreed destination. Count a tag done only if the remote holds the local tag object at the release commit; otherwise apply conflict or mismatch rules. Count an existing release done. A missing write is not done: name the limit. An unreadable or changed destination leaves state unknown; uncertain tag evidence SHALL NOT create a GitHub release.

#### Scenario: Push cut off after it landed
- **WHEN** the tag push passes its deadline after the selected remote received the local `v0.5.0` tag object
- **THEN** publish reports the tag as published, and goes on to create the GitHub release

#### Scenario: Push cut off while another clone's tag won
- **WHEN** the tag push passes its deadline, and the read-back finds `refs/tags/v0.5.0` on the selected remote at the release commit as a different tag object
- **THEN** publish exits 1 with `tag_mismatch` naming both tag objects, and creates no GitHub release

#### Scenario: Push cut off with origin's tag on another commit
- **WHEN** the tag push passes its deadline, and the read-back finds `refs/tags/v0.5.0` on the selected remote at another commit
- **THEN** publish exits 1 with `tag_conflict` naming both commits, and creates no GitHub release

#### Scenario: Release creation cut off before it landed
- **WHEN** `gh release create v0.5.0` passes its deadline and `gh release view v0.5.0` then finds no release
- **THEN** publish exits 3 with `"error": "deadline_exceeded"` naming `gh release create`, and says the tag is on the selected remote and a re-run creates the release

#### Scenario: Read-back fails too
- **WHEN** the tag push passes its deadline and the `git ls-remote` read-back fails
- **THEN** publish exits 3 saying the tag's state on the selected remote is unknown, and creates no GitHub release

#### Scenario: Remote retargeted after the tag push is cut off
- **WHEN** the tag push is cut off and the remote name now resolves to a different destination
- **THEN** publish does not use the new destination to decide what happened, reports unknown if the original cannot be read safely, and does not create a release from the uncertain result
