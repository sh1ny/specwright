# Spec Delta

## MODIFIED Requirements

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


### Requirement: Release operations run in the project's sw
Each `release.sh` subcommand SHALL run as `sw release`, called directly, keeping its options, JSON fields, error names and exits 0/1/2/3. The operations SHALL NOT start Python, bash, sh or a shipped script for their own work, and SHALL read the code repo's VCS backend in process. When the project's `VERSION` is missing or differs from the running `sw`'s version, the command SHALL print one `sw_mismatch` JSON document and exit 1, with no fallback.

#### Scenario: Publish without Python or bash
- **WHEN** `release.sh publish --version 0.5.0` runs on Linux, Windows and macOS with failing `python`, `python3`, `bash` and `sh` first on `PATH` for `sw`, a merged release commit for 0.5.0, a bare origin and a fake `gh`
- **THEN** it exits 0 with `tag_local: created`, `tag_remote: pushed` and `github_release: created`, the tag is on origin, and none of the failing programs was started by `sw`

#### Scenario: Check reads the GitButler backend in process
- **WHEN** `release.sh check --main origin/main` runs without `--branch` in a code repo whose settings select `vcs: gitbutler`, with no shipped script on disk
- **THEN** it exits 2 with the existing usage error asking for `--branch`, and no `sw vcs` or `sw pr` process starts

#### Scenario: Status keeps its document
- **WHEN** `release.sh status --version 0.5.0` runs on a repository where the Python `release.sh` printed a status document before the port
- **THEN** the document has the same fields with the same values, `notes` included, apart from message wording

#### Scenario: No matching sw
- **WHEN** `sw release untagged --dir <project>` runs and the project's `VERSION` names another version than the running `sw`, or is missing
- **THEN** it prints one `sw_mismatch` JSON document, exits 1, and reads no tag and starts no `git ls-remote`
