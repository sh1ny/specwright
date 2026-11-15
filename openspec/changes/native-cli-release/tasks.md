# Tasks

## Test map

| Requirement | Scenario | Test file | Test name | State |
|---|---|---|---|---|
| releases → Release operations run in the project's sw | Publish without Python or bash | evals/release/test_release_sw.py | test_publish_runs_without_python_or_bash | red |
| releases → Release operations run in the project's sw | Check reads the GitButler backend in process | evals/release/test_release_sw.py | test_gitbutler_backend_read_without_pr_pair | red |
| releases → Release operations run in the project's sw | Status keeps its document | evals/release/test_release_sw.py | test_status_matches_preport_document | red |
| releases → Release operations run in the project's sw | No matching sw | evals/release/test_release_sw.py | test_untagged_sw_missing_starts_no_network | red |
| releases → Version file patterns are JavaScript regular expressions | Shipped patterns read the version | evals/release/test_release_sw.py | test_shipped_patterns_read_version | red |
| releases → Version file patterns are JavaScript regular expressions | CRLF line ends | evals/release/test_release_sw.py | test_crlf_version_read_and_bump_keeps_crlf | red |
| releases → Version file patterns are JavaScript regular expressions | Python-only syntax | evals/release/test_release_sw.py | test_python_only_pattern_bad_version_files | red |
| releases → A misreadable settings line stops a release | Settings read as written | evals/release/test_release_sw.py | test_shipped_settings_check_passes | red |
| releases → A misreadable settings line stops a release | Misreadable line | evals/release/test_release_sw.py | test_misreadable_settings_publish_bad_settings | red |
| releases → A misreadable settings line stops a release | Notes ignores the settings | evals/release/test_release_sw.py | test_notes_ignores_misreadable_settings | red |
| releases → Bump refuses a version file that is not UTF-8 | Valid UTF-8 files | evals/release/test_release_sw.py | test_bump_valid_utf8_files | red |
| releases → Bump refuses a version file that is not UTF-8 | A malformed file after a valid one | evals/release/test_release_sw.py | test_bump_malformed_file_changes_nothing | red |
| releases → Bump refuses a version file that is not UTF-8 | Check reads the malformed file | evals/release/test_release_sw.py | test_check_reads_malformed_file | red |

Every row runs through the `release.sh` shim and native `sw` on the three platforms of `.github/workflows/evals.yml` (task 8.1). The existing `evals/release/test_release.py` and `test_release_jj.py` cases are the port's contract (design D8) and must stay green there too.

## 1. ADR, assumptions and the pre-port fixture

- [x] 1.1 Write `docs/adr/0037-release-version-patterns-are-javascript-regexes.md` (`Status: accepted`, `Adds to: 0030`), carrying C1: `release.version_files` patterns are JavaScript regexes in Unicode and multiline mode, the refused Python syntax, the `bad_version_files` stop, and the `\w`/`\b` differences ADR 0030 lists. Add it to the ADR index in `openspec/architecture.md`. Verify: both files show the entry, and ADR 0030 is unchanged (`git diff --stat docs/adr/0030*` empty).
- [x] 1.2 Verify A3: grep `skills/`, `agents/`, `schemas/` and `evals/` for assertions or prose that read a `release.sh` `message` text rather than `error`, `ok` or a named field. Record each hit and adjust the eval assertion in the group that ports its subcommand. A caller that parses message text is design drift: stop and amend D8.
- [x] 1.3 Capture the pre-port status fixture: run the current Python `release.sh status --version 0.5.0` on the `evals/release/fixtures.py` repository that the status tests build, and save the document as `evals/release/fixtures/preport-status.json` with the commit ids it names. Add a `evals/suites.json` rule for it (release) and run `python -m unittest evals/runner/test_suite_map.py`. Verify: the map test passes.
- [x] 1.4 Verify A1 before any matcher code: a Dart unit test in `cli/test/release/regex_dialect_test.dart` asserts that `RegExp(p, multiLine: true, unicode: true)` throws `FormatException` for `(?P<v>\d+)`, `\A1`, `1\Z` and `(?i)x`, and that `^(\d+\.\d+\.\d+)$` matches `0.4.2` in `"0.4.2\r\n"` with the match ending before the `\r`. Run `mise exec -- dart test test/release/regex_dialect_test.dart` from `cli/`. A failing assertion is design drift: stop and amend D3.
- [x] 1.5 Verify A2: run Python's `glob.glob('**/*', recursive=True)` and `glob.glob('*')` in a scratch directory holding `.hidden/VERSION`, `a/.VERSION` and `a/VERSION`, and record which names are returned in `cli/test/release/glob_test.dart`'s header comment. Verify: the glob test in task 3.1 pins the same rule.

## 2. Evals on the native shim (red)

- [x] 2.1 Point the release eval fixtures at a matching `sw`: in `evals/release/fixtures.py` give each fixture repository `SPECWRIGHT_HOME=sw_home()` and `stamp_version()` (`evals/vcs/vcs_test_support.py`), and write the fake `gh` in `test_release.py` and `test_release_jj.py` with `fakeexe.write_fake`. Each fake records its calls, and every test that expects a `gh` call asserts the fake recorded it. Verify: `python -m unittest evals/release/test_release.py -k TestStatus` still passes against the Python script, which ignores the new environment.
- [x] 2.2 Route release code to the release suite: add the `evals/suites.json` rule from design D8 (`cli/lib/src/release/**`, `cli/lib/src/commands/release.dart`, `cli/test/release/**`, `cli/lib/src/process/**`, `cli/lib/src/settings/**`, `cli/lib/src/pr/gh.dart`, `cli/lib/src/pr/settings_commands.dart`, `cli/lib/src/fs/**` → `release`, beside their `cli` rule) and the new `evals/release/test_release_sw.py`. Verify: `python -m unittest evals/runner/test_suite_map.py` passes.
- [x] 2.3 Write every Test map test in `evals/release/test_release_sw.py`, using `swharness` failing-interpreter `PATH` directories for the Python/bash row and a `0xFF` byte fixture for the UTF-8 rows. Run `python -m unittest evals/release/test_release_sw.py`. Verify: each test fails for the reason its row names (Python is still started, `pr-pair.sh` runs, `(?P<` is accepted, misreadable settings are read, the malformed bump succeeds), not for a fixture error.

## 3. Settings, globs and version files (Dart)

- [x] 3.1 Write failing unit tests in `cli/test/release/glob_test.dart` (the `glob_regex` rules, the dot-name rule from 1.5, links refused at every path segment) and `cli/test/release/versions_test.dart` (one match per file, agreement, `bad_version_files` for a pattern with no or two groups and for a refused dialect, CRLF offsets, the bump write plan, an interrupted bump completed, a non-UTF-8 file refused before any write). Verify: they fail because `cli/lib/src/release/` does not exist yet.
- [x] 3.2 Implement `cli/lib/src/release/settings.dart` (D2: `yamlProblem`, then `loadSettings`; the `Settings` mapping and gate of `release.sh:390-441`), `glob.dart` (D5) and `versions.dart` (D3, D4: work tree and commit trees, `cat-file --batch` through `launch`, `agree`, `bump` with temp file and rename per file). Write C3 into the spec requirement already carried (no extra text) and C4 as the `VersionGlob` doc comment. Verify: the 3.1 tests pass.

## 4. History, gates, notes and status (Dart)

- [ ] 4.1 Write failing unit tests in `cli/test/release/history_test.dart` for `primary_history`, `Releases`, the D3/D5/D9 bump-detection walk of `release.sh:694-776` (one case per branch of `own_bump`, taken from the existing `TestCheckMain*` evals), the release-commit shape and the older-untagged gate, and in `cli/test/release/notes_test.dart` for the section parser, the first Why sentence, the summary choice and `build_notes`. Verify: they fail for missing code.
- [ ] 4.2 Implement `history.dart` and `notes.dart`, including the store-backed code-merge proof with `gh api --paginate --slurp` through `runBoundedCommand` (D6). Write C6 as the `whyLines` doc comment. Verify: the 4.1 tests pass.
- [ ] 4.3 Implement `check` (with the in-process `readVcsSettings` backend read, D7), `bump`, `notes`, `status` and `untagged` in `cli/lib/src/release/commands.dart`, printing the script's JSON fields and exit codes. Verify: the `TestCheck*`, `TestBump*`, `TestNotes*`, `TestStatus*` and `TestUntagged*` classes of `evals/release/test_release.py` pass against `sw release` directly (`SPECWRIGHT_RELEASE_SW=1` selects it in the fixtures until the shim lands in 6.1).

## 5. Publish and bounded network commands (Dart)

- [ ] 5.1 Implement `cli/lib/src/release/git.dart` (`ReleaseGit`: local `git` through `launch`, `ls-remote`, `fetch` and `push` through `runBoundedCommand`) and `publish.dart` (push-destination check, tag checks, tag create with the notes temp file, push, GitHub release, read-backs of `release.sh:1680-1748`). `gh` runs with `GH_REPO` removed and no `bash -c`. Write C2 as the `ReleaseGit` doc comment and C5 as a note on `resolveLimits` in `cli/lib/src/process/limits.dart`. Verify: `TestPublish*`, `TestBoundedNetwork` and `test_release_jj.py` pass against `sw release` directly.
- [ ] 5.2 Fix #211 in `test_release_create_cut_off_not_found` (design D9): a first publish under the normal bound with `release create` failing, then the cut-off run. Verify: the test passes, and with the first run removed it still fails the way #211 reported only when the push is slow (reasoned in the test's docstring, not timed).

## 6. The shim, launch sites and removals

- [ ] 6.1 Add `sw release --args-stdin` and plain `sw release <sub>` to `cli/lib/src/cli.dart` and `cli/lib/src/commands/release.dart` (D1), and replace `skills/specwright-release/scripts/release.sh` with an ADR 0028 shim that takes the project from a leading `--dir`, else from `pwd`. Remove `skills/specwright-release/scripts/bounded.py` and its `evals/suites.json` entry (D10), and drop the `SPECWRIGHT_RELEASE_SW` switch from 4.3. Verify: `python -m unittest evals/runner/test_suite_map.py` passes and `evals/release/test_release.py` passes through the shim.
- [ ] 6.2 List every process-runner call of `cli/lib/src/release/` in `cli/test/launch_sites_test.dart` as an external tool. Verify: `mise exec -- dart test test/launch_sites_test.dart` passes, and fails when a `Process.start` is added to `cli/lib/src/release/git.dart`.
- [ ] 6.3 Run `python -m unittest evals/release/test_release_sw.py` and flip every Test map row green. Verify: all 13 tests pass locally on this platform.

## 7. Skill text and settings docs

- [ ] 7.1 In `skills/specwright-release/SKILL.md` and `templates/openspec/specwright.yaml`, name the `release.version_files` dialect (JavaScript regexes, Unicode and multiline mode, Python-only syntax refused with `bad_version_files`), the `bad_settings` stop and the non-UTF-8 bump stop in the stop table. Add a `evals/release/test_skill_text.py` check for the dialect line. Verify: `python -m unittest evals/release/test_skill_text.py` passes.
- [ ] 7.2 In README.md's releases section, add a `**BREAKING (0.35.0):**` line, as README.md:506 does for 0.2.0: `release.version_files` patterns are JavaScript regexes, so rewrite any pattern with Python-only syntax; misreadable settings lines stop with `bad_settings`; bump refuses a non-UTF-8 version file. Verify: the line is there, `python -m unittest evals/release/test_skill_text.py` passes, and `grep -rn "(?P<" openspec/specwright.yaml templates/` finds nothing.

## 8. Integration and release

- [ ] 8.1 Run the release, cli and vcs suites on Linux, Windows and macOS through PR CI (`.github/workflows/evals.yml` and `cli.yml`, on a draft PR). Verify: every job is green, and the Test map rows hold on all three platforms.
- [ ] 8.2 `release.sh bump --to 0.35.0` and rewrite the summary of the proposal's `## Release Notes` for the whole release. Verify: `release.sh check` passes and `release.sh notes --proposal openspec/changes/native-cli-release/proposal.md` prints the notes.

## Workflow follow-up

- Pre-ship review, ship, watch, archive and finish per `finish: pr`.
- Close #211 with the merged PR.
