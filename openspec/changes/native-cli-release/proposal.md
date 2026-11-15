# Proposal

## Why

`release.sh` is the last large Python program behind the release workflow. It embeds about 1,760 lines of Python, carries its own YAML reader and a copy of `bounded.py`, starts `bash pr-pair.sh vcs` to learn the code repo's backend, and starts `gh` through `bash -c`. This change serves M8, Complete the native CLI migration (#148), as change 8. It advances these exit criteria: the release operations use `sw`, with their JSON, exit-code and workflow contracts covered by the black-box evals on the three CI platforms; `sw` never starts a shipped script or Python for its own work; and `sw` starts no bash or sh. It also unblocks change 9, `native-cli-yaml-settings`, which needs the Python settings readers in `review-run.sh` and `release.sh` gone.

It carries #211: `test_release_create_cut_off_not_found` lowers the network bound for every command in a publish, so on a slow Windows runner the real tag push can reach that bound before the hung `gh release create` does, and the test fails while publish behaves correctly.

## What Changes

- **Port.** All six `release.sh` subcommands move to `sw release`: `check`, `bump`, `status`, `notes`, `untagged` and `publish`, with `--dir`. Each keeps its options, JSON fields, error names, exit codes (0, 1, 2, 3) and the workflow guarantees of the `releases` spec: the version-file agreement, the bump's temp-file-and-rename writes and resumable rerun, the release-commit and older-untagged gates, the tag checks before any write, the read-back after a cut-off push or release, and the notes built from each archived proposal. Following ADR 0033, message wording may change where no caller reads it; error names and fields do not.
- **Shim.** `release.sh` becomes an ADR 0028 shim that resolves the project's `sw`. Its embedded Python and YAML reader go. The `bounded.py` copy in `skills/specwright-release/scripts/` goes too, because no shipped caller uses it once `release.sh` is a shim. The skills keep calling `release.sh` until `native-cli-retire-scripts`.
- **In-process calls.** The code repo's VCS backend comes from `sw`'s settings reader, not from `bash pr-pair.sh vcs`. `git` and `gh` start through the native launcher (ADR 0034) under the existing ADR 0012 bounds, with no `bash -c` wrapper.
- **Settings.** `release.*`, `pr.merge_method`, `finish` and `main_branch` come from `sw`'s shared settings reader. A settings line that reader would misread stops every subcommand except `notes` with `bad_settings`, naming the line, as `sw review` and `sw pr policy` already do. **BREAKING** for a settings file that `release.sh` read leniently.
- **Regex dialect.** `release.version_files` patterns become JavaScript regular expressions in Unicode and multiline mode, as ADR 0030 decided for reviewer patterns. A pattern using Python-only syntax (`(?P<name>`, `\A`, `\Z`, `(?i)`) stops with `bad_version_files`, naming the entry; it never matches under another meaning. The shipped template, the docs and this repository's own patterns mean the same in both dialects. **BREAKING** for a project whose pattern uses Python-only syntax.
- **Non-UTF-8 version files.** Bump stops with `bad_version_files`, naming the file, when a file it would rewrite is not valid UTF-8, before it writes any file. `release.sh` wrote such a file's other bytes back unchanged. Reads still work. **BREAKING** for a bump of such a file.
- **#211.** The eval pushes the tag in an earlier run under the normal bound. The run with the shortened bound then starts only quick reads before the hung `gh release create`, so the tag push can no longer reach that bound first.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `releases`: the release operations run in the project's `sw` with their contracts kept, start no Python, bash or shipped script, and read the VCS backend in process. `release.version_files` patterns are JavaScript regular expressions in Unicode and multiline mode. A settings line the shared reader would misread is refused with `bad_settings`. Bump refuses a version file that is not valid UTF-8.

## Impact

- **Code:** new `cli/lib/src/release/` modules and an `sw release` command in `cli/lib/src/cli.dart`. They reuse `cli/lib/src/process/` (bounded runs and the launcher), `cli/lib/src/settings/` and the VCS settings reader.
- **Scripts:** `skills/specwright-release/scripts/release.sh` becomes a shim; `skills/specwright-release/scripts/bounded.py` is removed.
- **Skills and docs:** `skills/specwright-release/SKILL.md` and the settings template name the regex dialect. The call sites in `specwright-commit`, `specwright-pr`, `specwright-finish` and `specwright-roadmap` keep working through the shim.
- **Evals:** `evals/release/test_release.py` and `test_release_jj.py` run against the shim and `sw`, with new cases for runs with Python, bash and sh absent, an in-process backend read, the regex dialect and `bad_settings`. The #211 test is fixed. Dart unit tests go under `cli/test/release/`.
- **ADRs:** a new ADR extends ADR 0030's dialect to `release.version_files`.
- **Settings:** no new key. `release.version_files` changes dialect, and misreadable lines are refused.
- **Dependencies:** none expected. Glob matching, semver and the notes parser are small enough to write in `sw`; a package would need the owner's approval (ADR 0033).

## Decision Making

DECISION_MAKING: important
- **Source:** setting

### S1: `release.version_files` patterns are JavaScript regexes in Unicode mode

- **Choice:** Compile each pattern as `RegExp(pattern, multiLine: true, unicode: true)`, extending ADR 0030 to release patterns in a new ADR. A pattern Unicode mode refuses is `bad_version_files`, naming the entry, before any read or write.
- **Rejected:** A translator from Python syntax to `RegExp`, because its correctness needs its own proof and ADR 0030 already rejected it for the same reason. Keeping a Python evaluator, because M8 removes Python.
- **Reversal cost:** medium (users rewrite patterns again if the dialect changes)
- **Important:** yes: changes settings users see, and binds future changes (a config format)
- **Chosen by:** user

### S2: A misreadable settings line stops release with `bad_settings`

- **Choice:** Read the settings through `sw`'s shared reader and refuse a line its strict check finds, naming the line, as `sw review` does. `notes` reads no settings and is unaffected. Lenient `yes` and `no` booleans stay accepted until `native-cli-yaml-settings`.
- **Rejected:** Reading leniently as `release.sh` does, because release would then be the one ported command that decides on a line it may have misread.
- **Reversal cost:** low
- **Important:** yes: changes behaviour users see
- **Chosen by:** user

### S3: #211 is fixed in the eval, not in publish

- **Choice:** The eval first publishes with `gh release create` failing, under the normal bound, so the tag is on origin. The cut-off run then needs only quick reads before the hung `gh release create`: the tag steps count as done. Publish's behaviour is unchanged; #211 records that it was correct.
- **Rejected:** A per-command test bound in `sw`, because it adds a test-only knob to production code. A longer shortened bound, because it slows the test and is still a race.
- **Reversal cost:** low
- **Important:** no
- **Chosen by:** agent

### S4: The `bounded.py` copy beside `release.sh` is removed in this change

- **Choice:** Remove `skills/specwright-release/scripts/bounded.py` with the port, as `native-cli-review` removed its copy.
- **Rejected:** Keeping it until `native-cli-retire-scripts`, because nothing would call it.
- **Reversal cost:** low
- **Important:** no
- **Chosen by:** agent

## Release Notes

`sw release` runs all six release operations natively: check, bump, status, notes, untagged and publish. Their options, JSON, error names and exit codes stay compatible, and they start no Python, bash or shipped script. `release.version_files` patterns are now JavaScript regexes in Unicode mode, and a misreadable settings line stops release with `bad_settings`.

### Changed

- `release.sh` is a shim over native `sw release`. Its subcommands, JSON documents, error names and exit codes remain compatible. Release operations read the VCS backend in process and start `git` and `gh` without a shell (#148).
- `release.version_files` patterns are JavaScript regular expressions in Unicode and multiline mode. A pattern with Python-only syntax stops with `bad_version_files`, naming the entry (#148).
- Bump stops with `bad_version_files`, naming the file, when a version file it would rewrite is not valid UTF-8, before writing any file (#148).
- A release stops with `bad_settings`, naming the line, when `openspec/specwright.yaml` has a line the settings reader would misread; `release.sh` used to read it leniently (#148).

### Fixed

- The release eval for a cut-off `gh release create` no longer fails on slow Windows runners: the tag is pushed before the shortened bound applies (#211).

### Removed

- `skills/specwright-release/scripts/bounded.py` (#148).
