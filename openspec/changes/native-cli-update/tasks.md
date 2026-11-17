# Tasks

## Test map

New or changed behaviour starts `red`. A scenario of a MODIFIED requirement that rides along unchanged and already passes starts `green`, and a task re-runs it. Rows in `evals/update/` run through the `update.sh` shim once group 7 lands. "README text" rows check the install prompt's wording, because only an agent follows the prompt. The bootstrap eval runs the prompt's per-OS commands on each runner.

| Requirement | Scenario | Test file | Test name | State |
|---|---|---|---|---|
| install-update → sw update carries every update subcommand | A workflow update through sw update | evals/update/test_update.py | test_update_completes | red |
| install-update → sw update carries every update subcommand | A refusal keeps its code | evals/update/test_update.py | test_refusal_reports_unchanged | red |
| install-update → sw update carries every update subcommand | A usage error | cli/test/update/command_test.dart | no subcommand or a plan-only misuse is a usage error | red |
| install-update → sw update needs no bash or Python | Install and update with failing interpreters first on PATH | evals/update/test_sw_update.py | test_install_and_update_with_failing_interpreters | red |
| install-update → sw update needs no bash or Python | Interrupted swap recovered with failing interpreters | evals/update/test_sw_update.py | test_interrupted_swap_recovered_with_failing_interpreters | red |
| install-update → sw update needs no bash or Python | A jj store read in process | evals/update/test_update_jj_store.py | test_busy_jj_store_read_in_process | red |
| install-update → sw update refuses settings the shared reader refuses | A plain yes in the settings | evals/update/test_sw_update.py | test_plain_yes_setting_refused_settings_invalid | red |
| install-update → sw update refuses settings the shared reader refuses | No settings file | evals/update/test_update.py | test_plan_without_installed_version_is_fresh | red |
| install-update → update.sh hands over to the download's sw | Shim with the download's sw placed | evals/update/test_shim.py | test_shim_hands_over_to_download_sw | red |
| install-update → update.sh hands over to the download's sw | Shim with no matching sw | evals/update/test_shim.py | test_shim_without_matching_sw_reports_sw_missing | red |
| install-update → sw update recovers journals that older update scripts left | A format-2 journal from update.sh | evals/update/test_sw_update.py | test_format_2_journal_from_update_sh_resumed | red |
| install-update → sw update recovers journals that older update scripts left | Unknown journal format | evals/update/test_sw_update.py | test_unknown_journal_format_refused | red |
| install-update → The install prompt drives sw update interface 3 | Matching interface | evals/update/test_sw_update.py | test_interface_reports_3_and_writes_nothing | red |
| install-update → The install prompt drives sw update interface 3 | Interface mismatch | evals/git-workflow/test_instructions.py | test_readme_interface_mismatch_stops_before_sw_install (README text) | red |
| install-update → The install prompt needs no bash or Python | Windows host without Git Bash or Python | evals/update/test_bootstrap.py | test_bootstrap_commands_without_bash_or_python | red |
| install-update → The install prompt needs no bash or Python | No SHA-256 tool | evals/git-workflow/test_instructions.py | test_readme_step1_checks_hash_tool_not_bash_or_python (README text) | red |
| install-update → The agent fetches and checks the first sw before any write | Fresh install on macOS arm64 | evals/update/test_bootstrap.py | test_bootstrap_hashes_then_chmods_then_runs | red |
| install-update → The agent fetches and checks the first sw before any write | Hash mismatch at the bootstrap | evals/update/test_bootstrap.py | test_bootstrap_hash_mismatch_never_runs | red |
| install-update → The agent fetches and checks the first sw before any write | Missing or corrupt notice at the bootstrap | evals/update/test_bootstrap.py | test_bootstrap_bad_notice_never_runs | red |
| install-update → The agent fetches and checks the first sw before any write | Version report differs from the tag | evals/git-workflow/test_instructions.py | test_readme_step3_version_must_match_tag (README text) | red |
| install-update → The bootstrap downloads are bounded and https only | Bootstrap downloads in time | evals/update/test_bootstrap.py | test_bootstrap_fetch_follows_https_redirect | red |
| install-update → The bootstrap downloads are bounded and https only | Stalled, oversized or downgraded bootstrap download | evals/git-workflow/test_instructions.py | test_readme_step3_curl_is_bounded_and_https_only (README text) | red |
| install-update → A main install builds sw from the clone | main install with mise | evals/cli/test_install_sw.py | test_expected_interface_build_placed | red |
| install-update → A main install builds sw from the clone | main install without mise | evals/git-workflow/test_instructions.py | test_readme_main_needs_mise (README text) | red |
| install-update → A main install builds sw from the clone | main build reports another interface | evals/cli/test_install_sw.py | test_interface_mismatch_places_nothing | red |
| install-update → Update installs a release tag by default | Latest tag | evals/git-workflow/test_instructions.py | test_readme_default_is_latest_tag (README text) | red |
| install-update → Update installs a release tag by default | Named version has no tag | evals/git-workflow/test_instructions.py | test_readme_missing_tag_stops (README text) | red |
| install-update → Update installs a release tag by default | Named version predates the update script | evals/git-workflow/test_instructions.py | test_readme_minimum_release_is_0_37_0 (README text) | red |
| install-update → Update installs a release tag by default | Latest tag predates the update script | evals/git-workflow/test_instructions.py | test_readme_latest_below_minimum_offers_main (README text) | red |
| install-update → Update installs a release tag by default | Script interface differs from the prompt | evals/git-workflow/test_instructions.py | test_readme_interface_mismatch_stops_before_sw_install (README text) | red |
| install-update → Update installs a release tag by default | No tags | evals/git-workflow/test_instructions.py | test_readme_no_tag_installs_main (README text) | red |
| install-update → The release-tag lookup is bounded | Tags listed in time | evals/update/test_store.py | test_other_project_minor_refused_names_matching_tag | red |
| install-update → The release-tag lookup is bounded | Hung tag lookup | evals/update/test_store.py | test_hung_tag_lookup_names_deadline_exceeded | red |
| install-update → The release-tag lookup is bounded | Oversized tag list | evals/update/test_store.py | test_oversized_tag_list_names_response_too_large | red |
| install-update → A tagged install places a checked sw for the host | Install of a tag with binaries on Linux x64 | evals/update/test_sw_install.py | test_tag_install_places_checked_binary | red |
| install-update → A tagged install places a checked sw for the host | SPECWRIGHT_HOME set | evals/update/test_sw_install.py | test_specwright_home_is_the_root | red |
| install-update → A tagged install places a checked sw for the host | Host on a platform with no target | evals/update/test_sw_install.py | test_unsupported_platform_stops | red |
| install-update → A tagged install places a checked sw for the host | Run from the agent's temporary copy | evals/update/test_sw_install.py | test_install_from_temporary_copy_never_moves_itself | red |
| install-update → An install without release binaries says so | Install of main | evals/update/test_sw_install.py | test_main_install_reports_no_sw | red |
| install-update → An install without release binaries says so | Install of an older tag | evals/git-workflow/test_instructions.py | test_readme_minimum_release_is_0_37_0 (README text) | red |
| install-update → An install without release binaries says so | Install of main reports the build | evals/git-workflow/test_instructions.py | test_readme_main_reports_sw_built_from_main (README text) | red |
| install-update → An install without release binaries says so | Existing binaries stay untouched on main | evals/update/test_sw_install.py | test_main_install_leaves_bin_untouched | red |
| install-update → An install whose VCS steps need a missing sw says so | main install with no binary | evals/git-workflow/test_install_sw_warning.py | test_main_without_binary_warns | red |
| install-update → An install whose VCS steps need a missing sw says so | main install with a matching binary already placed | evals/git-workflow/test_install_sw_warning.py | test_matching_binary_gets_no_warning | green |
| install-update → An install whose VCS steps need a missing sw says so | Older tag whose scripts need no sw | evals/git-workflow/test_install_sw_warning.py | test_older_tag_gets_no_warning | red |
| install-update → An install whose VCS steps need a missing sw says so | Tagged install with sw placed | evals/git-workflow/test_install_sw_warning.py | test_tagged_install_gets_no_warning | green |
| install-update → Contributors place a tree-built sw with one task | Build placed | evals/cli/test_install_sw.py | test_build_placed_and_resolved | red |
| install-update → Contributors place a tree-built sw with one task | Build fails the check | evals/cli/test_install_sw.py | test_mismatched_build_leaves_existing_file | red |
| install-update → Contributors place a tree-built sw with one task | No bash on PATH | evals/cli/test_install_sw.py | test_install_sw_task_without_bash | red |
| native-cli → sw starts itself only for its helper and the reviewer evaluator | Retrofitted paths with sentinels and no Python | evals/vcs/test_sw_fence.py | test_retrofitted_vcs_paths_run_no_script_or_python | green |
| native-cli → sw starts itself only for its helper and the reviewer evaluator | Reviewer evaluator stays a separate process | cli/test/pr/snapshot_test.dart | a limit on the evaluator names reviewers.py, not sw | green |
| native-cli → sw starts itself only for its helper and the reviewer evaluator | Printed commands are not launches | evals/vcs/test_sw_fence.py | test_printed_plan_commands_are_not_launched | green |
| native-cli → sw starts itself only for its helper and the reviewer evaluator | sw update checks a downloaded sw and starts no script | evals/update/test_sw_update.py | test_sw_install_and_jj_swap_start_no_script | red |
| native-cli → A launch-site allowlist guards process starts | Current tree passes | cli/test/launch_sites_test.dart | the tree matches the allowlist | red |
| native-cli → A launch-site allowlist guards process starts | A new unlisted launch fails | cli/test/launch_sites_test.dart | an unlisted runner call fails naming the file | green |
| native-cli → A launch-site allowlist guards process starts | A script in launch arguments fails | cli/test/launch_sites_test.dart | a script name in launch arguments fails | red |
| native-cli → A launch-site allowlist guards process starts | A self-launch outside the allowed two fails | cli/test/launch_sites_test.dart | a changed, non-literal or unbounded self-launch fails | green |
| native-cli → A launch-site allowlist guards process starts | A script name built away from the launch fails | cli/test/launch_sites_test.dart | a script name built away from the launch fails | green |
| native-cli → A launch-site allowlist guards process starts | The binary checks of sw update are listed | cli/test/launch_sites_test.dart | the binary check of sw update allows only version --json | red |

The `evals/update` tests not named above (`test_update.py`, `test_store.py`, `test_inflight.py`, `test_packs.py`, `test_shipped_packs.py`, `test_interrupt.py`, `test_update_jj_store.py`, `test_sw_install.py`) also run through the shim once group 7 lands. Their behavioural assertions stay as they are. The only expected edits are the interface number (2 → 3), the kill seam (D3) and versioned binaries (D8).

## 1. ADR, architecture and assumptions

- [ ] 1.1 Write `docs/adr/0039-install-runs-in-sw.md`, "The install runs in `sw`, and the agent fetches the first `sw`" (adds to 0011 and 0027). It carries C2 (journal format 2 stays readable by 0.36.0's `update.sh`; formats 1 and 2 stay recoverable) and C3 (the prompt drives only `sw update` interface 3, from minimum release 0.37.0, and the agent fetches and checks the first `sw`). Index it in `openspec/architecture.md`. Update the architecture rows for the install prompt, `update.sh` (now a shim) and `sw` (`update` family). Verify: the ADR holds the C2 and C3 text, the index links it, and `python -m unittest evals/runner/test_suite_map.py` passes.
- [ ] 1.2 Verify A2: write `cli/test/update/copy_mode_test.dart`, which copies an executable file with `File.copy` and asserts the mode bits on POSIX. Run it locally and in PR CI on Linux and macOS. If it fails, record the drift and make the staging copy set the mode explicitly (task 5.1).
- [ ] 1.3 Verify A3: write `cli/test/update/kill_seam_test.dart`. It starts a helper that calls `exit(137)` inside a `try`/`finally` that would write a marker, and asserts that no marker and no unflushed journal bytes are left. Run it locally. On failure, stop under the drift rule.

## 2. `sw update` skeleton: command, interface, file operations, journal, lock

- [ ] 2.1 Write failing tests: `cli/test/update/command_test.dart` (usage errors, exit 2; `interface` prints `{"ok":true,"interface":3}` and touches no file) and `evals/update/test_sw_update.py::test_interface_reports_3_and_writes_nothing`. Verify they fail because `update` is an unknown command.
- [ ] 2.2 Add `cli/lib/src/commands/update.dart` and `cli/lib/src/update/options.dart` with every subcommand's options, the usage document, and `sw update interface` (D11). Verify: the 2.1 tests pass, and the rows "A usage error" and "Matching interface" turn green.
- [ ] 2.3 Write failing tests in `cli/test/update/file_ops_test.dart` for the counting wrapper: each copy, rename, remove and mkdir logs `<n> <op> <args>` when `SPECWRIGHT_UPDATE_COUNT` is set, `SPECWRIGHT_UPDATE_KILL_AT=<n>` ends the process with 137 at op n, and nothing is logged without the variables. Then implement `cli/lib/src/update/file_ops.dart` `UpdateFileOps`, with C1 written as its doc comment. Verify: the tests pass, and the doc comment holds C1.
- [ ] 2.4 Write failing tests in `cli/test/update/journal_test.dart`: read format 1 and format 2 journals written as `update.sh` writes them (`scripts/update.sh:220-226`), write format 2 byte-compatible fields, and refuse `"format": 9` and trailing garbage as `journal_unreadable`. Then implement `cli/lib/src/update/journal.dart`. Verify: the tests pass.
- [ ] 2.5 Write failing tests in `cli/test/update/lock_test.dart` that mirror the lock cases of `evals/update/test_update.py:436-642` (ownerless, partial-owner, dead-owner, taken meanwhile). Then implement `cli/lib/src/update/lock.dart` (`scripts/update.sh:227-229`). Verify: the tests pass.

## 3. Downloads, binary check and placement

- [ ] 3.1 Write failing tests in `cli/test/update/download_test.dart` against a local TLS test server: https only on the start URL and on every redirect, an http redirect refused, `file://` allowed, `http://` refused, 120 s deadline and 64 MiB cap with the partial file deleted, proxy taken from the environment. Then implement `cli/lib/src/update/download.dart` `downloadReleaseFile` (D4), with C5 written as its doc comment. Verify: the tests pass, and the doc comment holds C5.
- [ ] 3.2 Write failing tests in `cli/test/update/place_test.dart`. `checkBinary` runs `version --json` under 10 s and 1 MiB, and requires the version to equal the download's `VERSION` and the interface to equal `interfaceVersion`. Placement puts the notice before the binary and replaces it only by rename, and the running file is never renamed (D6, D7). Then implement `cli/lib/src/update/place.dart`, with C6 written as `checkBinary`'s doc comment. Verify: the tests pass, and the doc comment holds C6.
- [ ] 3.3 Implement `sw update sw-install`: tag, host asset and `SHA256SUMS`, hash check before run, quarantine rule (`scripts/update.sh:3199-3213`), `--ref main` reports `skipped`, and `--build <file> --download <tree>`. Add the Dart tests for `--build`. Verify: `cli/test/update/sw_install_test.dart` passes. Add `test_install_from_temporary_copy_never_moves_itself` to `evals/update/test_sw_install.py`; it turns green in group 7.

## 4. Plan: settings, changes in flight, store, tag lookup, packs

- [ ] 4.1 Write failing tests: `evals/update/test_sw_update.py::test_plain_yes_setting_refused_settings_invalid` and `cli/test/update/settings_test.dart`, for a missing file read as no settings. Then read the four settings through `readSettingsText`/`readSettingsYaml` and stop with `settings_invalid` (D5). Verify: the tests pass, and the "A plain yes in the settings" row turns green.
- [ ] 4.2 Port the plan's kinds, targets, orphans, root checks and changes-in-flight validation (`openspec` through `launch()`) into `cli/lib/src/update/plan.dart` and `inflight.dart`, keeping every message word for word (D9). Verify with Dart tests per module in `cli/test/update/plan_test.dart` and `inflight_test.dart`.
- [ ] 4.3 Port store roles, the store gate lock and the jj store reads in process through `sw`'s VCS interfaces (`cli/lib/src/vcs/jj_backend.dart:296`). Port the bounded `git ls-remote` tag lookup (60 s, 32 MiB, process tree stopped). Add `test_busy_jj_store_read_in_process` to `evals/update/test_update_jj_store.py`. Verify: `cli/test/update/store_test.dart` passes.
- [ ] 4.4 Port `pack-check` and the plan's pack refusals (ADR 0023). Verify: `cli/test/update/packs_test.dart` passes.

## 5. Stage, swap, note-config, finish, recover, pack verify and docs

- [ ] 5.1 Port staging with SHA-256 verification before any installed file changes. Every file op goes through `UpdateFileOps` (C1), and the mode is set explicitly if 1.2 disproved A2. Verify: `cli/test/update/stage_test.dart` passes.
- [ ] 5.2 Port `swap`, `note-config`, `finish` and `recover`: the journal state machine, resume and rollback as the staged copy decides, and config rollback. Verify: `cli/test/update/swap_recover_test.dart` passes, including a format-2 journal written by the 0.36.0 script layout.
- [ ] 5.3 Port `pack-verify` and `pack-docs`. Verify: `cli/test/update/packs_test.dart` passes.

## 6. Build tool, mise task and `install-sw.sh` removal

- [ ] 6.1 Write failing tests in `evals/cli/test_install_sw.py`: `test_expected_interface_build_placed`, `test_interface_mismatch_places_nothing` (an existing binary, notice, pending journal and installed files unchanged), `test_install_sw_task_without_bash`, and update the existing tests to call the task without bash. Verify they fail for the right reason.
- [ ] 6.2 Add `--version <v>`, `--output <file>`, `--install` and `--expect-update-interface <n>` to `cli/tool/build.dart` (D7, D8). Point the `install-sw` task in `mise.toml` at `dart run cli/tool/build.dart --install` with arguments passed through. Delete `scripts/install-sw.sh` and update `evals/suites.json`. Verify: the 6.1 tests and `evals/runner/test_suite_map.py` pass, and the rows "main install with mise", "main build reports another interface", "Build placed", "Build fails the check" and "No bash on PATH" turn green.

## 7. `update.sh` shim and the eval fixtures

- [ ] 7.1 Write failing tests in `evals/update/test_shim.py`: `test_shim_hands_over_to_download_sw` and `test_shim_without_matching_sw_reports_sw_missing`. Verify they fail against today's `update.sh`.
- [ ] 7.2 Add `provision_sw(home, version)` to `evals/update/fixtures.py`. It builds once per version per run with `cli/tool/build.dart --version <v> --output <cache>/<v>/sw[.exe]`, then copies the binary and notice into each test's isolated `SPECWRIGHT_HOME`. `make_download` and `make_mini_download` call it. Switch `run_update` from the `mv`/`cp`/`rm` shims to `SPECWRIGHT_UPDATE_KILL_AT`/`SPECWRIGHT_UPDATE_COUNT` (D3). Verify: `evals/update/test_fixtures.py` passes locally.
- [ ] 7.3 Replace `scripts/update.sh` with the ADR 0028 shim (D8), with C4 written in its header. Delete `evals/update/shims/` if nothing else uses it, and update `evals/suites.json`. Change the interface assertions from 2 to 3 (`evals/update/test_update.py::test_plan_reports_interface`, `evals/update/test_packs.py:346`, `:354`). Verify: `test_shim.py` passes locally, the header holds C4, and `evals/runner/test_suite_map.py` passes.
- [ ] 7.4 Add `evals/update/test_sw_update.py` cases: failing `bash`/`sh`/`python`/`python3` first on `PATH` for install, update and interrupted-swap recovery; a format-2 journal left by the 0.36.0 script and recovered; `"format": 9` refused; `sw-install` and an owner's jj swap with recording sentinels. Verify: open a draft PR and run the `evals/update` suite in PR CI on Linux, Windows and macOS. Every `evals/update` row in the test map turns green.
- [ ] 7.5 Compare the counted operation list of one interrupted run with the 0.36.0 bash run's (D3's weak-evidence check). Verify: the interruption matrix in `evals/update/test_interrupt.py` passes in PR CI on three OSes, and the comparison is noted in the PR.

## 8. Launch allowlist

- [ ] 8.1 Write failing tests in `cli/test/launch_sites_test.dart`: `update.sh` and `install-sw.sh` count as shipped script names, and `the binary check of sw update allows only version --json`. Verify they fail.
- [ ] 8.2 List `sw update`'s launch sites (`git`, `openspec`, `xattr` as external tools; the downloaded `sw` as a binary check). Verify: `mise exec -- dart test test/launch_sites_test.dart` from `cli/` passes, and the allowlist rows turn green. Re-run the green native-cli rows (`test_retrofitted_vcs_paths_run_no_script_or_python`, `test_printed_plan_commands_are_not_launched`, the evaluator test) in PR CI.

## 9. README install prompt, CONTRIBUTING and the bootstrap eval

- [ ] 9.1 Verify A4 and A5: write `evals/update/test_bootstrap.py`. On each runner it fetches the real `v0.36.0` release's host asset, notice and `SHA256SUMS` with the README's exact per-OS `curl` line, checks both hashes with the README's hash command, then runs `chmod`, `xattr` (macOS) and `version --json`, with no `bash` or `python` in the step's environment. Add the cases for a hash mismatch and a bad notice, in which the file is never run. Verify in PR CI on three OSes. A curl or TLS failure is design drift.
- [ ] 9.2 Write failing README text tests in `evals/git-workflow/test_instructions.py` for every "(README text)" row. Replace the interface-2 tests (`test_readme_accepts_interface_2` and its siblings) with interface-3 ones, and point the pack-step tests at `sw update`. Verify they fail against today's README.
- [ ] 9.3 Rewrite the README install prompt (prerequisites and Steps 1, 3, 4, 5, 7 and 8) to drive `sw update` only. The new prompt adds per-OS bounded https-only `curl` lines, both hash checks before `chmod`, quarantine and run, `sw update interface` before `sw-install`, minimum release 0.37.0, and `main` through `mise run install-sw -- --expect-update-interface 3`. Update the Step 8 report in `test_install_sw_warning.py` for the older-tag and `main` cases. Update `CONTRIBUTING.md`'s bootstrap. Verify: the 9.2 tests and `evals/git-workflow/test_install_sw_warning.py` pass, the README-text rows turn green, and the `git-workflow` suite passes in PR CI.

## 10. Release

- [ ] 10.1 Verify A1, then bump: `release.sh bump --to 0.37.0`. Rewrite the summary of the proposal's `## Release Notes` to describe the whole release. Verify: `release.sh check` and `release.sh notes --proposal openspec/changes/native-cli-update/proposal.md` pass, and the minimum release in the README and the specs reads 0.37.0.
- [ ] 10.2 Integration check: every row in the test map is green, and the `evals.yml` and `cli.yml` workflows pass on the PR head on Linux, Windows and macOS.

## Workflow follow-up

- After merge, publish v0.37.0 with `specwright-release`. The bootstrap eval can then also run against the first interface-3 release.
- `native-cli-retire-scripts` removes the `update.sh` shim (C4).
