# releases Specification

## Purpose

Cuts a project's releases from its merged work: one version across the configured files, an annotated tag on the merged main commit, notes from the archived changes, and an optional GitHub release, all opt-in and safe to re-run.

## Requirements

### Requirement: Releases are opt-in
`specwright-release` SHALL act only when `release.enabled` is true in `openspec/specwright.yaml`. With the key false or missing, bump and publish SHALL refuse before any write and name the setting, and no other skill SHALL offer a release.

#### Scenario: Enabled project
- **WHEN** `release.enabled` is true and the user asks for a release of 0.5.0
- **THEN** publish runs for 0.5.0

#### Scenario: Missing release block
- **WHEN** `specwright.yaml` has no `release:` block and the user runs publish
- **THEN** publish exits non-zero with a message naming `release.enabled`, and no tag, commit or GitHub release is created

### Requirement: Version file paths stay inside the repository
Each `release.version_files` path or glob SHALL be relative and inside the repository: an absolute entry, one with a `..` segment, or a working-tree match that resolves outside the repository (through a symlink) SHALL stop the run before any write, naming it.

#### Scenario: Entry outside the repository
- **WHEN** `release.version_files` has the entry `../shared/VERSION`
- **THEN** check and bump exit non-zero naming the entry, and no file inside or outside the repository is changed

#### Scenario: Glob through a symlink outside the repository
- **WHEN** `skills/linked` is a symlink to a directory outside the repository and `skills/*/SKILL.md` matches a file in it
- **THEN** check and bump exit non-zero naming that file, and it is unchanged

### Requirement: Version files are not symlinks
A version file match that is a symlink, or is reached through one, inside the repository SHALL stop the run before any write, naming it, in the working tree and at a commit: git stores a link as its text, so the version could not be read at the release commit.

#### Scenario: Symlink inside the repository
- **WHEN** `release.version_files` has `pkg/VERSION`, a symlink to `VERSION`
- **THEN** check and bump exit non-zero naming `pkg/VERSION`, no file is changed, and status of a commit holding the link exits non-zero naming it

### Requirement: Version files agree before any write
`release.version_files` SHALL map each path or glob to a regular expression with one capture group; its first entry is the primary file. Every matched file SHALL hold exactly one match and all captured versions SHALL be equal, else the run SHALL stop before any write naming each offending file. Bump and check read the working tree; status and publish read V's release commit, with the current `version_files`, and stop unless the shared version there is V.

#### Scenario: All files agree
- **WHEN** `VERSION`, the README badge and every `skills/*/SKILL.md` frontmatter carry `0.4.2`
- **THEN** the check reports version `0.4.2` with the list of files it read and exits 0

#### Scenario: One file disagrees
- **WHEN** `skills/specwright-debug/SKILL.md` carries `0.4.1` and the other files carry `0.4.2`
- **THEN** the check exits non-zero naming `skills/specwright-debug/SKILL.md` and both versions, and no file is changed

#### Scenario: A pattern matches nothing or twice
- **WHEN** the README pattern matches no line, or matches two lines
- **THEN** the check exits non-zero naming `README.md`, the entry's pattern and the match count

#### Scenario: Backfill checks the release commit
- **WHEN** the checkout carries 0.5.0 and publish runs for 0.4.1
- **THEN** the agreement check reads the files at `9b33ec5`, finds 0.4.1 in every one, and publish continues

#### Scenario: A glob matches no file
- **WHEN** an entry's path is `pkg/*/VERSION` and no file matches it
- **THEN** the check exits non-zero naming the entry

### Requirement: Bump writes one commit across the version files
Bump SHALL take a target version greater than the current one under semver ordering, rewrite only the captured version in every version file, and change no file when any file fails the agreement check. A write error part-way SHALL be reported, and rerunning the same bump SHALL complete it. The orchestrator SHALL commit exactly those files as one tracked task commit on the change branch, before the pre-ship review.

#### Scenario: Minor bump
- **WHEN** the files agree on `0.4.2` and bump runs with `0.5.0`
- **THEN** every version file carries `0.5.0`, no other line of those files changed, and one task commit holds exactly those files

#### Scenario: Target not greater
- **WHEN** the files agree on `0.4.2` and bump runs with `0.4.2` or `0.4.1`
- **THEN** bump exits non-zero naming both versions and no file is changed

#### Scenario: Interrupted bump is completed
- **WHEN** a previous bump to `0.5.0` stopped after rewriting `VERSION` while the other files still carry `0.4.2`
- **THEN** rerunning bump with `0.5.0` leaves every version file at `0.5.0`, and a bump to any other target exits non-zero naming the split

#### Scenario: Malformed target
- **WHEN** bump runs with `v0.5` or `0.5.0-beta`
- **THEN** bump exits non-zero saying the target must be `MAJOR.MINOR.PATCH`, and no file is changed

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

### Requirement: Rebase-merged releases are refused
Publish SHALL stop before any write, naming the commit, when V's release commit is neither a merge commit nor a commit whose subject ends in `(#<n>)` (a rebase-merged or directly pushed bump). Bump and publish SHALL refuse `release.enabled` together with `pr.merge_method: rebase`.

#### Scenario: Rebase-merged bump
- **WHEN** the first main commit reading 0.6.0 is a replayed `feat(x): task 6.1 bump to 0.6.0` commit with one parent
- **THEN** publish exits non-zero naming that commit and saying the release commit must be a merge or squash commit, and no tag is created

#### Scenario: Rebase merge method configured
- **WHEN** `release.enabled` is true and `pr.merge_method` is `rebase`
- **THEN** bump and publish exit non-zero naming both settings, and no file or tag is written

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

### Requirement: A bumped version is greater than main's before it merges
`sw release check --main <ref>` SHALL refuse, before any write, a branch that bumped (its version differs from its merge base with `<ref>`, or the newest of its own non-merge commits that changed the primary file's version raised it) to a version not greater than `<ref>`'s, naming both versions and saying to bump again. No readable version at `<ref>` SHALL pass.

#### Scenario: Two changes bump to the same version
- **WHEN** branches `feat/a` and `feat/b` both start at 0.4.2 and bump to 0.5.0, `feat/a` has merged, and ship runs for `feat/b` with `origin/main` at 0.5.0
- **THEN** `check --main origin/main` exits non-zero naming 0.5.0 on the branch and on `origin/main`, nothing is pushed, and the message says to bump `feat/b` again

#### Scenario: Main moved past the bump
- **WHEN** the branch bumped from 0.4.2 to 0.5.0 and `origin/main` is at 0.6.0
- **THEN** the check exits non-zero naming 0.5.0 and 0.6.0

#### Scenario: Bump still ahead
- **WHEN** the branch bumped from 0.4.2 to 0.5.0 and `origin/main` is still at 0.4.2
- **THEN** the check exits 0 and reports version 0.5.0

#### Scenario: Version file edited without a bump
- **WHEN** a change branch edits the primary file but leaves its version at 0.4.2, and `origin/main` has moved to 0.5.0
- **THEN** the check exits 0: an edit that keeps the version is not a bump

#### Scenario: Bump reverted on the branch
- **WHEN** a change branch bumped 0.4.2 to 0.5.0, a later commit set it back to 0.4.2, and `origin/main` has moved to 0.5.0
- **THEN** the check exits 0: the branch carries no bump

#### Scenario: Branch did not bump
- **WHEN** a change branch leaves the version at 0.4.2 and `origin/main` has moved to 0.5.0
- **THEN** the check exits 0 and refuses nothing, since the branch carries no release of its own

#### Scenario: Main was merged into the branch after the duplicate landed
- **WHEN** `feat/a` and `feat/b` both bumped 0.4.2 to 0.5.0, `feat/a` merged, and `origin/main` was then merged into `feat/b`
- **THEN** `check --main origin/main` exits non-zero naming 0.5.0 on the branch and on `origin/main`, and says to bump again

#### Scenario: Main has no version yet
- **WHEN** the branch adds `VERSION` at 0.1.0 with `release.enabled`, and `origin/main` has no `VERSION` file
- **THEN** the check exits 0 and reports version 0.1.0

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

### Requirement: An unreadable version is not absent
In `sw release check --main <ref>`, a primary file that exists but does not read exactly one version SHALL be unreadable, which is not absent. An unreadable merge base, or an unreadable parent on `<ref>`, SHALL count as a bump only when the branch's or commit's version is not among the versions it matched. A commit whose parent is unreadable and on the branch SHALL be judged against its nearest first-parent ancestor that is readable or on `<ref>`, in place of that parent.

#### Scenario: Merge base repeats the version
- **WHEN** the merge base's `VERSION` holds `0.4.2` twice, the branch's only commit on it removes the duplicate and keeps `0.4.2`, and `origin/main` has moved to 0.5.0
- **THEN** `check --main origin/main` exits 0 and reports version 0.4.2: the branch did not bump

#### Scenario: Bump after a repair of an unreadable version
- **WHEN** the merge base's `VERSION` holds `0.4.2` twice, one branch commit removes the duplicate, a later one bumps to 0.5.0, and `origin/main` is at 0.5.0
- **THEN** the check exits non-zero with `version_not_ahead_of_main`, naming 0.5.0 on the branch and on `origin/main`

#### Scenario: One commit repairs and bumps
- **WHEN** the merge base's `VERSION` holds `0.4.2` twice, the branch's only commit on it writes `0.5.0` once, and `origin/main` is at 0.5.0
- **THEN** the check exits non-zero with `version_not_ahead_of_main`, naming 0.5.0 on the branch and on `origin/main`

#### Scenario: Bump made through an unreadable version
- **WHEN** a branch commit changes `VERSION` from `0.4.2` to hold `0.4.2` and `0.5.0`, a later one keeps only `0.5.0`, and the branch then merges `origin/main` at 0.5.0
- **THEN** the check exits non-zero with `version_not_ahead_of_main`, naming 0.5.0 on the branch and on `origin/main`

#### Scenario: Broken main version repaired on both sides
- **WHEN** the merge base's `VERSION` lists `0.4.2` and `0.5.0`, the branch's only commit on it keeps `0.5.0`, and `origin/main` has since repaired it to 0.5.0
- **THEN** `check --main origin/main` exits 0 and reports version 0.5.0

#### Scenario: Stray version line added and removed
- **WHEN** the branch starts at 0.5.0, one commit adds a `0.4.2` line to `VERSION`, a later one removes it, and `origin/main` is at 0.5.0
- **THEN** the check exits 0 and reports version 0.5.0

### Requirement: An unreadable commit changes the version only when its parent is not among its versions
In `check --main`'s history walk, a commit whose parent is unreadable and on the branch SHALL be a change when it matched a version the parent did not. Otherwise a commit whose own version is unreadable SHALL be no change when its base (the version it is judged against) is among those it matched, or is unreadable too. A change SHALL be a bump only when it matched a version and all it matched are greater than its base or, when the base is unreadable, than each version the base matched.

#### Scenario: Bump reverted through an unreadable version
- **WHEN** the branch bumps 0.4.2 to 0.5.0, a later commit sets `VERSION` back to `0.4.2` twice, a still later one removes the duplicate, and `origin/main` is at 0.5.0
- **THEN** `check --main origin/main` exits 0 and reports version 0.4.2

#### Scenario: Bump reverted between two unreadable versions
- **WHEN** `origin/main` and the merge base are at 0.5.0, one branch commit sets `VERSION` to `0.6.0` twice, a later one sets it to `0.5.0` twice, and a still later one removes the duplicate
- **THEN** `check --main origin/main` exits 0 and reports version 0.5.0

#### Scenario: Unreadable bump reverted by a readable commit
- **WHEN** `origin/main` and the merge base are at 0.5.0, one branch commit sets `VERSION` to `0.6.0` twice, and a later one sets it to `0.5.0` once
- **THEN** `check --main origin/main` exits 0 and reports version 0.5.0

#### Scenario: Unreadable edit that keeps the matched versions
- **WHEN** the merge base is at 0.5.0, one branch commit sets `VERSION` to `0.6.0` twice, a later one adds a third `0.6.0` line, a still later one keeps one line, and the branch then merges `origin/main` at 0.6.0
- **THEN** `check --main origin/main` exits non-zero with `version_not_ahead_of_main`, naming 0.6.0 on the branch and on `origin/main`

### Requirement: Publish's network commands are bounded
Every `git` or `gh` network command `sw release` runs SHALL run under ADR 0012's bounds: 120 seconds, or 300 seconds for the paginated closed-PR read, and at most 32 MiB from each command. When one passes a bound, its process tree SHALL be stopped, and `sw release` SHALL exit 3 with `deadline_exceeded` or `response_too_large` as its `error`, naming the command. It SHALL NOT use a partial answer.

#### Scenario: Remote tags answer in time
- **WHEN** `sw release untagged` runs and `git ls-remote --tags origin` answers within its deadline
- **THEN** the command lists the untagged versions as before this change, and no limit is named

#### Scenario: Hung tag lookup
- **WHEN** publish runs and `git ls-remote --tags origin` never answers
- **THEN** `sw release` exits 3 within the deadline plus 10 seconds with `"error": "deadline_exceeded"` naming `git ls-remote`, no tag is created, and no process it started is still running

#### Scenario: Oversized closed-PR read
- **WHEN** store-backed publish reads merged PRs and the paginated `gh api` read prints more than 32 MiB
- **THEN** `sw release` exits 3 with `"error": "response_too_large"` naming `gh api`, and creates no tag

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

### Requirement: A Release Notes section has one format
A proposal's `## Release Notes` section SHALL run to the next `##` heading or the end of the file and hold a summary of at most 600 characters, then one or more of the headings `### Added`, `### Changed`, `### Fixed` and `### Removed`, each at most once, each followed only by list items. Each item SHALL be at most 500 characters. Any other content SHALL make the section invalid.

#### Scenario: Valid section
- **WHEN** a section holds a one-sentence summary, `### Fixed` with two items and `### Added` with one
- **THEN** it parses to that summary and three items under `fixed` and `added`

#### Scenario: Unknown heading
- **WHEN** a section has a `### Security` heading
- **THEN** it is invalid, and the error names `Security` and its line

#### Scenario: Prose under a heading
- **WHEN** a line that is neither a list item, an indented continuation nor blank follows `### Changed`
- **THEN** it is invalid, and the error names that line

#### Scenario: No summary or no item
- **WHEN** a section starts with `### Added`, or has a summary and no list item
- **THEN** it is invalid, and the error says which is missing

#### Scenario: Item over the limit
- **WHEN** one item is 501 characters long after whitespace is collapsed
- **THEN** the section is invalid, and the error names the item's line

### Requirement: A Release Notes section tolerates comments, blank lines and wrapped items
Before parsing, HTML comments (`<!-- ... -->`, also across lines) SHALL be removed. Blank lines SHALL be allowed anywhere in the section. The summary SHALL be all text before the first `###` heading, joined with single spaces. A list item SHALL start with `-`, `*` or `+` and a space; a following line indented by at least one space or tab SHALL be joined to it.

#### Scenario: Template guidance comment left in
- **WHEN** a section still holds the template's `<!-- ... -->` guidance between the heading and the summary, and under `### Added`
- **THEN** it parses as if the comments were absent

#### Scenario: Only a comment
- **WHEN** a section holds nothing but the template's comment
- **THEN** it is invalid, and the error says the summary is missing

#### Scenario: Wrapped item
- **WHEN** an item's text continues on the next line, indented by two spaces
- **THEN** the two lines are one item, joined with a single space

#### Scenario: Unindented line after an item
- **WHEN** an unindented line that is not a list item follows an item under `### Fixed`
- **THEN** the section is invalid, and the error names that line

#### Scenario: Two-paragraph summary
- **WHEN** the summary is two sentences on two lines separated by a blank line
- **THEN** the summary is both sentences joined by one space

### Requirement: Notes open with the release summary and group the items
When at least one change in V's range has a valid section, the notes SHALL open with the release summary (next requirement), then list `Added:`, `Changed:`, `Fixed:` and `Removed:` in that order, each with every item from every change's section under that heading, in the changes' order, leaving out a heading with no item. Changes without a valid section SHALL follow under `Changes:`, one `- <name> (#<pr>): <why>` line each.

#### Scenario: One change with a section
- **WHEN** the range holds only `fix-m4-gaps` (#129), whose section has a summary and eight `Fixed` items
- **THEN** the notes are the summary, a blank line, `Fixed:` and the eight items, and nothing under `Added:`, `Changed:`, `Removed:` or `Changes:`

#### Scenario: Exact layout of several groups
- **WHEN** the range holds `old-x` (#7, no section) then `new-y` (#8), whose section has summary `S.`, `### Fixed` item `F (#5)` and `### Added` item `A`
- **THEN** the notes are exactly `S.`, blank, `Added:`, `- A (#8)`, blank, `Fixed:`, `- F (#5)`, blank, `Changes:`, `- old-x (#7): <why>`, with one blank line between groups and no trailing blank line

#### Scenario: Two changes with sections
- **WHEN** the range holds `add-a` then `add-b`, both with sections, and both have `Added` items
- **THEN** the notes open with `add-b`'s summary, and `Added:` lists `add-a`'s items before `add-b`'s

#### Scenario: A change with a section and an older one without
- **WHEN** the range holds `old-x` (no section) then `new-y` (a section with one `Changed` item)
- **THEN** the notes are `new-y`'s summary, `Changed:` with its item, then `Changes:` with `- old-x (#<pr>): <why>`

#### Scenario: Many items
- **WHEN** the sections in the range hold 170 items together
- **THEN** the notes list the first 150 in group and change order, the line `…and 20 more items` follows the 150th item directly with no blank line, a group whose items all fall past the 150th is left out, and `Changes:` (when present) follows after one blank line

#### Scenario: More than 100 changes in the range
- **WHEN** the range holds 120 changes, only the last of which (the bumping change) has a section
- **THEN** the notes open with that change's summary and list its items, and `Changes:` lists the first 100 of the other 119 by name only, then `…and 19 more`

### Requirement: The release summary comes from the bumping change
The release summary SHALL be the summary of the change in V's range whose archived `tasks.md` has a ticked task running `release.sh bump --to <V>` or `sw release bump --to <V>` (the form skills write from this change on; the older form stays recognised for earlier releases and backfills) and whose section is valid. When no change or more than one matches, it SHALL be the summary of the last change with a valid section in the notes' order.

#### Scenario: Bumping change archived with another in the same commit
- **WHEN** the release commit adds the archives `2026-11-02-b-bump` (its `tasks.md` has `- [x] 3.1 release.sh bump --to 0.9.0`) and `2026-11-02-c-other`, both with valid sections, and `c-other` sorts last
- **THEN** the notes open with `b-bump`'s summary

#### Scenario: No change has a bump task
- **WHEN** no archived `tasks.md` in the range has a ticked `release.sh bump --to 0.9.0` task, and `add-a` then `add-b` have valid sections
- **THEN** the notes open with `add-b`'s summary

#### Scenario: Bumping change without a valid section
- **WHEN** the change with the bump task has no section, and an earlier change in the range has one
- **THEN** the notes open with the earlier change's summary

#### Scenario: Native bump task wins over a later-sorting archive
- **WHEN** the release commit adds `2026-11-02-b-bump`, whose `tasks.md` has `- [x] 3.1 <sw> release bump --to 0.9.0`, and `2026-11-02-c-other`, both with valid sections, and `c-other` sorts last
- **THEN** the notes open with `b-bump`'s summary

### Requirement: An item without a reference gets its change's PR
An item that names no issue or PR (`#<n>` or `<owner>/<repo>#<n>` outside a code span) SHALL be listed with ` (#<pr>)` appended, `<pr>` being its change's PR from main's commit subject or the store-backed code-merge proof. With no PR known, the item SHALL be listed as written.

#### Scenario: Item without a reference
- **WHEN** `add-a` merged as #140 and its section has the item `New --dry-run flag`
- **THEN** the notes list `- New --dry-run flag (#140)`

#### Scenario: Item with its own reference
- **WHEN** an item reads `Bounded tag push (#111)`
- **THEN** it is listed as written, without `(#140)` appended

#### Scenario: Reference only inside a code span
- **WHEN** an item reads ``Parse `#123` comments`` and its change merged as #140
- **THEN** it is listed with ` (#140)` appended

#### Scenario: Local merge with no PR
- **WHEN** a `finish: local` change whose merge subject names no PR has the item `New --dry-run flag`
- **THEN** it is listed as `- New --dry-run flag`

### Requirement: An invalid section falls back to the Why line
When an archived proposal's `## Release Notes` section is invalid, or the proposal is over 64 KB, `status` and `publish` SHALL list that change under `Changes:` as a change without a section, with a `warnings` entry naming the change and the first error. It SHALL NOT stop either subcommand. `warnings` describe the derived notes: publish reports them only when it creates the tag, and `[]` when the tag exists.

#### Scenario: Unknown heading in an archived proposal
- **WHEN** publish runs for V and one change's archived section has a `### Security` heading
- **THEN** the tag is created, the notes list that change under `Changes:` with its Why line, and the JSON's `warnings` names the change and `Security`

#### Scenario: Valid sections
- **WHEN** every section in the range is valid
- **THEN** `warnings` is an empty list

#### Scenario: Proposal over the read bound
- **WHEN** a change's archived `proposal.md` is 70 KB, with a valid section in its first 64 KB
- **THEN** that change is listed under `Changes:`, and `warnings` names it and the 64 KB limit

#### Scenario: Publish re-run after the tag exists
- **WHEN** publish runs again for V after its tag was created, and an archived section in the range is invalid
- **THEN** the notes reported are the tag's message, and `warnings` is `[]`

### Requirement: One proposal's section can be checked before it merges
`sw release notes --proposal <file>` SHALL parse that file's section and print its summary, its items by heading and the line the notes would give each item (an unreferenced item's line ending in the literal ` (#<pr>)`), with no git or network call and whether or not releases are enabled. A valid section SHALL exit 0. An invalid one SHALL exit 1 with `release_notes_invalid` and every error, and a file without the section SHALL exit 1 with `no_release_notes`.

#### Scenario: Valid section
- **WHEN** the bump task runs `notes --proposal openspec/changes/add-a/proposal.md` on a valid section
- **THEN** it exits 0, and its JSON holds the summary and each item under its heading

#### Scenario: Two errors
- **WHEN** the section has an unknown heading and an item over 500 characters
- **THEN** it exits 1 with `release_notes_invalid` and both errors, each with its line

#### Scenario: No section
- **WHEN** the proposal has no `## Release Notes` heading
- **THEN** it exits 1 with `no_release_notes`

#### Scenario: Missing file
- **WHEN** `--proposal` names a file that does not exist
- **THEN** it exits 2 with a usage error naming the path

#### Scenario: File over the read bound
- **WHEN** `--proposal` names a 70 KB file whose first 64 KB hold a valid section
- **THEN** it exits 1 with `release_notes_invalid` and an error naming the 64 KB limit

### Requirement: The bump task writes the release summary
With `release.enabled` true, the task that bumps the version SHALL rewrite the summary of the bumping change's section to describe the whole release, and check it with `sw release notes --proposal`. The proposal instruction SHALL ask for the section when `release.enabled` is true, and apply SHALL keep its items current with what the change ships.

#### Scenario: Bump task in a project with releases
- **WHEN** the tasks of a change in a project with `release.enabled: true` are written
- **THEN** the last group's bump task names rewriting the section's summary for the release and verifies it with `sw release notes --proposal`

#### Scenario: Releases off
- **WHEN** `release.enabled` is false and a proposal is written
- **THEN** the instruction does not ask for a `## Release Notes` section, and no task checks one

### Requirement: The release skill names the proposal in the planning repo
`specwright-release` SHALL tell the bump task to check the section with `sw release notes --proposal <proposal.md>`. It SHALL say that `<proposal.md>` is the change's proposal in the planning repo: in the store when the project is store-backed. No Specwright skill text SHALL pass `--proposal` a path fixed under the code checkout's `openspec/`.

#### Scenario: Store-backed project
- **WHEN** an agent follows the release skill's notes check for change `add-a` in a project whose planning lives in a store at `../plans`
- **THEN** the command it is told to run names the proposal as `<proposal.md>`, the skill says that file is in the store, and the skill's notes section does not contain `openspec/changes/<change>/proposal.md`

#### Scenario: A hardcoded path comes back
- **WHEN** any `skills/*/SKILL.md` contains `--proposal openspec/`
- **THEN** the release skill-text test fails and names that file

### Requirement: Release operations run in the project's sw
Each `release.sh` subcommand SHALL run as `sw release`, called directly, keeping its options, JSON fields, error names and exits 0/1/2/3. The operations SHALL NOT start Python, bash, sh or a shipped script for their own work, and SHALL read the code repo's VCS backend in process. When the project's `VERSION` is missing or differs from the running `sw`'s version, the command SHALL print one `sw_mismatch` JSON document and exit 1, with no fallback.

#### Scenario: Publish without Python or bash
- **WHEN** `sw release publish --version 0.5.0` runs on Linux, Windows and macOS with failing `python`, `python3`, `bash` and `sh` first on `PATH` for `sw`, a merged release commit for 0.5.0, a bare origin and a fake `gh`
- **THEN** it exits 0 with `tag_local: created`, `tag_remote: pushed` and `github_release: created`, the tag is on origin, and none of the failing programs was started by `sw`

#### Scenario: Check reads the GitButler backend in process
- **WHEN** `sw release check --main origin/main` runs without `--branch` in a code repo whose settings select `vcs: gitbutler`, with no shipped script on disk
- **THEN** it exits 2 with the existing usage error asking for `--branch`, and no `sw vcs` or `sw pr` process starts

#### Scenario: Status keeps its document
- **WHEN** `sw release status --version 0.5.0` runs on a repository where the Python `release.sh` printed a status document before the port
- **THEN** the document has the same fields with the same values, `notes` included, apart from message wording

#### Scenario: No matching sw
- **WHEN** `sw release --dir <project> untagged` runs and the project's `VERSION` names another version than the running `sw`, or is missing
- **THEN** it prints one `sw_mismatch` JSON document, exits 1, and reads no tag and starts no `git ls-remote`

### Requirement: Version file patterns are JavaScript regular expressions
Each `release.version_files` pattern SHALL be a JavaScript regular expression read in Unicode and multiline mode, so `^` and `$` match at each line, including before a CRLF line end. A pattern that mode refuses, including Python-only syntax such as `(?P<name>`, `\A`, `\Z` and `(?i)`, SHALL stop the run before any read or write with `bad_version_files`, naming the entry. A pattern SHALL never be matched under another meaning than the one it was written for.

#### Scenario: Shipped patterns read the version
- **WHEN** `release.version_files` holds `VERSION: '^(\d+\.\d+\.\d+)$'`, `README.md: 'badge/version-(\d+\.\d+\.\d+)-blue'` and `"skills/*/SKILL.md": '^  version: (\S+)$'`, and every file carries `0.4.2`
- **THEN** `sw release check` exits 0 with version `0.4.2` and the files it read

#### Scenario: CRLF line ends
- **WHEN** the `VERSION` file holds `0.4.2` followed by a CRLF and its pattern is `^(\d+\.\d+\.\d+)$`
- **THEN** check reads `0.4.2`, and `bump --to 0.4.3` writes `0.4.3` followed by the same CRLF

#### Scenario: Python-only syntax
- **WHEN** a `release.version_files` pattern is `(?P<v>\d+\.\d+\.\d+)` or starts with `\A`
- **THEN** `check`, `bump`, `status`, `untagged` and `publish` exit 1 with `error: bad_version_files` naming that entry, and no file, tag or release is written

### Requirement: A misreadable settings line stops a release
Release subcommands that read `openspec/specwright.yaml` SHALL stop with `bad_settings`, exit 1, naming the line, when the settings reader refuses the file, a plain `yes` or `no` value included, before any git call, network call or write. `notes` reads no settings and SHALL be unaffected.

#### Scenario: Settings read as written
- **WHEN** `openspec/specwright.yaml` holds the shipped `release:` block with `enabled: true` and `sw release check` runs
- **THEN** check exits 0 and reports the version

#### Scenario: Misreadable line
- **WHEN** `openspec/specwright.yaml` has a line under `release:` indented with a tab, or a `release:` key given twice, and `sw release publish --version 0.5.0` runs
- **THEN** it exits 1 with `error: bad_settings` naming the line, and no tag is created, pushed or released

#### Scenario: A yes for enabled
- **WHEN** `release.enabled` is written `yes` and `sw release publish --version 0.5.0` runs
- **THEN** it exits 1 with `error: bad_settings` naming the line, `true` and `false`, and no tag is created, pushed or released

#### Scenario: Notes ignores the settings
- **WHEN** the same settings file is present and `sw release notes --proposal proposal.md` runs on a valid proposal
- **THEN** it exits 0 and prints the section's summary and items

### Requirement: Bump refuses a version file that is not UTF-8
Bump SHALL check every version file it would rewrite before it writes any file. When one is not valid UTF-8, it SHALL stop with `bad_version_files`, exit 1, naming that file, and SHALL change no file. Reads by `check`, `status`, `untagged` and `publish` SHALL still read the version from such a file.

#### Scenario: Valid UTF-8 files
- **WHEN** every version file is valid UTF-8 and carries `0.4.2`, and `sw release bump --to 0.4.3` runs
- **THEN** it exits 0 and every file carries `0.4.3`

#### Scenario: A malformed file after a valid one
- **WHEN** `VERSION` is valid UTF-8, `README.md` holds the byte `0xFF` outside its version badge, both carry `0.4.2`, and `sw release bump --to 0.4.3` runs
- **THEN** it exits 1 with `error: bad_version_files` naming `README.md`, and both files keep their exact bytes

#### Scenario: Check reads the malformed file
- **WHEN** the same `README.md` holds `0xFF` and `sw release check` runs
- **THEN** it exits 0 with version `0.4.2`
