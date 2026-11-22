# Spec Delta

## MODIFIED Requirements

### Requirement: Publish creates and pushes an annotated tag
Publish SHALL create an annotated tag named by `release.tag` (default `v{version}`; a template without `{version}` SHALL stop every subcommand, since every version would map to one tag) on the release commit, with the notes as its message, and push only that tag ref to `origin` under the run login (through `sw as` for a github.com origin). It SHALL NOT push any branch. In a store-backed project it SHALL tag the code repo only.

#### Scenario: New release
- **WHEN** publish runs for 0.5.0 and no `v0.5.0` tag exists locally or on origin
- **THEN** `git cat-file -t v0.5.0` prints `tag`, `v0.5.0^{commit}` is the release commit, and `origin` has `refs/tags/v0.5.0`

#### Scenario: Tag template without the version
- **WHEN** `release.tag` is `release`
- **THEN** every subcommand exits non-zero naming `release.tag` and `{version}`, and no file or tag is written

#### Scenario: Push refused by the fence
- **WHEN** `sw as` refuses (exit 3) or the tag push fails
- **THEN** publish exits non-zero with the push error, no GitHub release is created, and the report says the local tag exists and a re-run pushes it (or stops as in "Lost push race" when another clone's tag reached origin first)

#### Scenario: Store-backed project
- **WHEN** publish runs in a store-backed project
- **THEN** the code repo has the tag and the store has no new tag

### Requirement: Older untagged versions are published first
`sw release untagged` SHALL list the versions in main's first-parent history of the primary file, after the latest published version (with none published: only the current version), that are not published, oldest first. Published means the tag is on `origin` (with no `origin` remote: a local tag). A version with a local tag not on origin SHALL always be listed. Publish of V SHALL stop before any write while a version on that list is lower than V, naming it.

#### Scenario: Older version untagged
- **WHEN** `v0.4.2` is the latest tag, 0.5.0 has no tag and publish runs for 0.5.1
- **THEN** publish exits non-zero naming 0.5.0, and `v0.5.1` is not created

#### Scenario: Tag push failed earlier
- **WHEN** `v0.4.2` is on origin, `v0.5.0` exists locally but not on origin (its push failed), and 0.5.1 is merged
- **THEN** `untagged` lists 0.5.0, and publish of 0.5.1 exits non-zero naming 0.5.0

#### Scenario: First release's tag push failed
- **WHEN** origin has no tag, `v0.3.0` exists only locally (its push failed) and 0.3.1 is merged
- **THEN** `untagged` lists 0.3.0 then 0.3.1, and publish of 0.3.1 exits non-zero naming 0.3.0

#### Scenario: Backfill below the latest tag
- **WHEN** `v0.5.0` is the only tag and publish runs for 0.4.1
- **THEN** publish is not blocked, and the notes range starts at the commit where `VERSION` first read 0.4.0

### Requirement: Untagged versions can be read from local tags only
With `--local`, `sw release untagged` SHALL read local tags only, make no network call, and say in its output that the list comes from local tags. Its output SHALL say so whenever it read local tags, including with no `origin` remote.

#### Scenario: Local tags only
- **WHEN** `v0.4.2` exists locally, origin points at an unreachable URL, main's version is 0.5.0, and `untagged --local` runs
- **THEN** it exits 0, lists 0.5.0, reports that the list comes from local tags, and starts no `git ls-remote`

#### Scenario: Local read with a local-only tag
- **WHEN** `v0.5.0` exists only locally (its push failed) and `untagged --local` runs with main at 0.5.0
- **THEN** it lists nothing, and its output still says the list comes from local tags, so origin may lack a tag it counted

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
