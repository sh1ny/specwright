# Spec Delta

## ADDED Requirements

### Requirement: Release operations run in the project's sw
Each `release.sh` subcommand SHALL run in the project's matching `sw`, resolved as other ported scripts are, keeping its options, JSON fields, error names and exits 0/1/2/3. The operations SHALL NOT start Python, bash, sh or a shipped script for their own work, and SHALL read the code repo's VCS backend in process. With no matching `sw`, the shim SHALL print one `sw_missing` JSON document and exit 1, with no fallback.

#### Scenario: Publish without Python or bash
- **WHEN** `release.sh publish --version 0.5.0` runs on Linux, Windows and macOS with failing `python`, `python3`, `bash` and `sh` first on `PATH` for `sw`, a merged release commit for 0.5.0, a bare origin and a fake `gh`
- **THEN** it exits 0 with `tag_local: created`, `tag_remote: pushed` and `github_release: created`, the tag is on origin, and none of the failing programs was started by `sw`

#### Scenario: Check reads the GitButler backend in process
- **WHEN** `release.sh check --main origin/main` runs without `--branch` in a code repo whose settings select `vcs: gitbutler`, and `pr-pair.sh` is absent from the install
- **THEN** it exits 2 with the existing usage error asking for `--branch`, and no `pr-pair.sh` or `vcs.sh` process starts

#### Scenario: Status keeps its document
- **WHEN** `release.sh status --version 0.5.0` runs on a repository where the Python `release.sh` printed a status document before the port
- **THEN** the document has the same fields with the same values, `notes` included, apart from message wording

#### Scenario: No matching sw
- **WHEN** `release.sh untagged` runs in a project whose `sw` is missing or reports another version
- **THEN** it prints one `sw_missing` JSON document, exits 1, and reads no tag and starts no `git ls-remote`

### Requirement: Version file patterns are JavaScript regular expressions
Each `release.version_files` pattern SHALL be a JavaScript regular expression read in Unicode and multiline mode, so `^` and `$` match at each line, including before a CRLF line end. A pattern that mode refuses, including Python-only syntax such as `(?P<name>`, `\A`, `\Z` and `(?i)`, SHALL stop the run before any read or write with `bad_version_files`, naming the entry. A pattern SHALL never be matched under another meaning than the one it was written for.

#### Scenario: Shipped patterns read the version
- **WHEN** `release.version_files` holds `VERSION: '^(\d+\.\d+\.\d+)$'`, `README.md: 'badge/version-(\d+\.\d+\.\d+)-blue'` and `"skills/*/SKILL.md": '^  version: (\S+)$'`, and every file carries `0.4.2`
- **THEN** `release.sh check` exits 0 with version `0.4.2` and the files it read

#### Scenario: CRLF line ends
- **WHEN** the `VERSION` file holds `0.4.2` followed by a CRLF and its pattern is `^(\d+\.\d+\.\d+)$`
- **THEN** check reads `0.4.2`, and `bump --to 0.4.3` writes `0.4.3` followed by the same CRLF

#### Scenario: Python-only syntax
- **WHEN** a `release.version_files` pattern is `(?P<v>\d+\.\d+\.\d+)` or starts with `\A`
- **THEN** `check`, `bump`, `status`, `untagged` and `publish` exit 1 with `error: bad_version_files` naming that entry, and no file, tag or release is written

### Requirement: A misreadable settings line stops a release
Release subcommands that read `openspec/specwright.yaml` SHALL stop with `bad_settings`, exit 1, naming the line, when the file has a line the shared settings reader would misread, before any git call, network call or write. `notes` reads no settings and SHALL be unaffected.

#### Scenario: Settings read as written
- **WHEN** `openspec/specwright.yaml` holds the shipped `release:` block with `enabled: true` and `release.sh check` runs
- **THEN** check exits 0 and reports the version

#### Scenario: Misreadable line
- **WHEN** `openspec/specwright.yaml` has a line under `release:` indented with a tab, or a `release:` key given twice, and `release.sh publish --version 0.5.0` runs
- **THEN** it exits 1 with `error: bad_settings` naming the line, and no tag is created, pushed or released

#### Scenario: Notes ignores the settings
- **WHEN** the same settings file is present and `release.sh notes --proposal proposal.md` runs on a valid proposal
- **THEN** it exits 0 and prints the section's summary and items

### Requirement: Bump refuses a version file that is not UTF-8
Bump SHALL check every version file it would rewrite before it writes any file. When one is not valid UTF-8, it SHALL stop with `bad_version_files`, exit 1, naming that file, and SHALL change no file. Reads by `check`, `status`, `untagged` and `publish` SHALL still read the version from such a file.

#### Scenario: Valid UTF-8 files
- **WHEN** every version file is valid UTF-8 and carries `0.4.2`, and `release.sh bump --to 0.4.3` runs
- **THEN** it exits 0 and every file carries `0.4.3`

#### Scenario: A malformed file after a valid one
- **WHEN** `VERSION` is valid UTF-8, `README.md` holds the byte `0xFF` outside its version badge, both carry `0.4.2`, and `release.sh bump --to 0.4.3` runs
- **THEN** it exits 1 with `error: bad_version_files` naming `README.md`, and both files keep their exact bytes

#### Scenario: Check reads the malformed file
- **WHEN** the same `README.md` holds `0xFF` and `release.sh check` runs
- **THEN** it exits 0 with version `0.4.2`
