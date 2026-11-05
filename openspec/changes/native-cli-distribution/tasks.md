# Tasks

## Test map

| Requirement | Scenario | Test file | Test name | State |
|---|---|---|---|---|
| native-cli → Every platform's binary is built and checked in CI | All three builds pass | `.github/workflows/cli.yml` run on this branch (task 2.5) | linux-x64, windows-x64, macos-arm64 build and verify jobs | green |
| native-cli → Every platform's binary is built and checked in CI | All five builds pass | `evals/cli/test_workflows.py`; CI run (task 2.5) | `test_build_matrix_has_five_native_targets`; the run's ten jobs | red |
| native-cli → Every platform's binary is built and checked in CI | Checksum does not match | `evals/cli/test_verify_artifact.py` | `test_checksum_mismatch_fails_without_running` | green |
| native-cli → Every platform's binary is built and checked in CI | Version drifts from VERSION | `evals/cli/test_verify_artifact.py` | `test_version_drift_fails_naming_both` | green |
| native-cli → Every platform's binary is built and checked in CI | Interface differs from the skills' | `evals/cli/test_verify_artifact.py` | `test_interface_mismatch_fails_naming_both` | red |
| native-cli → Every platform's binary is built and checked in CI | One target's runner fails | `evals/cli/test_workflows.py` | `test_matrix_is_not_fail_fast` | red |
| native-cli → Each published release carries checked binaries | Release published | `evals/cli/test_attach_release.py` | `test_unsealed_release_gets_five_binaries_then_sums` | red |
| native-cli → Each published release carries checked binaries | One target fails its check | `evals/cli/test_workflows.py` | `test_attach_needs_every_verify_job` | red |
| native-cli → Each published release carries checked binaries | Tag's VERSION differs from the tag | `evals/cli/test_attach_release.py` | `test_tag_version_mismatch_attaches_nothing` | red |
| native-cli → Each published release carries checked binaries | Interface mismatch at the tag | `evals/cli/test_verify_artifact.py`; `evals/cli/test_workflows.py` | `test_interface_mismatch_fails_naming_both`; `test_release_verify_checks_interface` | red |
| native-cli → Release assets have fixed names and one checksum file | Checksum file content | `evals/cli/test_attach_release.py` | `test_sums_has_five_sorted_lines_matching_binaries` | red |
| native-cli → Release assets have fixed names and one checksum file | A malformed checksum line | `evals/update/test_sw_install.py` | `test_malformed_sums_line_is_rejected` | red |
| native-cli → SHA256SUMS is uploaded last and seals the release | Re-run after a failed upload | `evals/cli/test_attach_release.py` | `test_partial_unsealed_release_is_replaced_then_sealed` | red |
| native-cli → SHA256SUMS is uploaded last and seals the release | Overlapping runs for one tag | `evals/cli/test_workflows.py`; `evals/cli/test_attach_release.py` | `test_release_concurrency_queues_per_tag`; `test_sealed_complete_release_changes_nothing` | red |
| native-cli → SHA256SUMS is uploaded last and seals the release | A binary changed before the seal | `evals/cli/test_attach_release.py` | `test_readback_mismatch_writes_no_seal` | red |
| native-cli → SHA256SUMS is uploaded last and seals the release | Sealed release run again | `evals/cli/test_attach_release.py` | `test_sealed_complete_release_changes_nothing` | red |
| native-cli → SHA256SUMS is uploaded last and seals the release | Sealed release missing a binary | `evals/cli/test_attach_release.py` | `test_sealed_release_missing_binary_fails` | red |
| native-cli → SHA256SUMS is uploaded last and seals the release | No release for the tag | `evals/cli/test_attach_release.py` | `test_tag_without_release_fails` | red |
| native-cli → A project's sw is found and checked before use | Matching binary | `evals/cli/test_sw_path.py` | `test_matching_binary_prints_path` | red |
| native-cli → A project's sw is found and checked before use | SPECWRIGHT_HOME override | `evals/cli/test_sw_path.py` | `test_specwright_home_is_used` | red |
| native-cli → A project's sw is found and checked before use | Override set but its binary missing | `evals/cli/test_sw_path.py` | `test_override_without_binary_does_not_fall_back` | red |
| native-cli → A project's sw is found and checked before use | Project has no VERSION | `evals/cli/test_sw_path.py` | `test_no_version_file_stops` | red |
| native-cli → A missing or mismatched sw stops with one message | Binary missing | `evals/cli/test_sw_path.py` | `test_missing_binary_ignores_other_versions` | red |
| native-cli → A missing or mismatched sw stops with one message | Interface mismatch | `evals/cli/test_sw_path.py` | `test_interface_mismatch_stops` | red |
| native-cli → A missing or mismatched sw stops with one message | Version report is not JSON | `evals/cli/test_sw_path.py` | `test_non_json_report_stops` | red |
| install-update → A tagged install places a checked sw for the host | Install of a tag with binaries on Linux x64 | `evals/update/test_sw_install.py` | `test_tag_install_places_checked_binary` (host target) | red |
| install-update → A tagged install places a checked sw for the host | SPECWRIGHT_HOME set | `evals/update/test_sw_install.py` | `test_specwright_home_is_the_root` | red |
| install-update → A tagged install places a checked sw for the host | Host on a platform with no target | `evals/update/test_sw_install.py` | `test_unsupported_platform_stops` | red |
| install-update → The macOS install clears quarantine only on the file it checked | Quarantined download on macOS arm64 | `evals/update/test_sw_install.py` | `test_quarantine_cleared_after_checksum` (macOS only) | red |
| install-update → The macOS install clears quarantine only on the file it checked | Mismatched file is left quarantined | `evals/update/test_sw_install.py` | `test_mismatch_keeps_quarantine_and_never_runs` | red |
| install-update → A missing or incompatible sw stops a tagged install before any change | Release assets not uploaded yet | `evals/update/test_sw_install.py` | `test_unsealed_release_stops_assets_not_uploaded` | red |
| install-update → A missing or incompatible sw stops a tagged install before any change | Checksum mismatch | `evals/update/test_sw_install.py` | `test_checksum_mismatch_stops_before_stage` | red |
| install-update → A missing or incompatible sw stops a tagged install before any change | Wrong interface | `evals/update/test_sw_install.py` | `test_wrong_interface_stops_before_stage` | red |
| install-update → The sw download is bounded | Download completes in time | `evals/update/test_sw_install.py` | `test_tag_install_places_checked_binary` | red |
| install-update → The sw download is bounded | Server stalls | `evals/update/test_sw_install.py` | `test_stalled_download_hits_deadline` | red |
| install-update → The sw download is bounded | Oversized answer | `evals/update/test_sw_install.py` | `test_oversized_download_is_refused` | red |
| install-update → An install without release binaries says so | Install of main | `evals/update/test_sw_install.py` | `test_main_install_reports_no_sw` | red |
| install-update → An install without release binaries says so | Install of an older tag | `evals/update/test_sw_install.py` | `test_plan_without_sw_field_means_no_sw` | red |
| install-update → An install without release binaries says so | Existing binaries stay untouched on main | `evals/update/test_sw_install.py` | `test_main_install_leaves_bin_untouched` | red |
| install-update → Placing sw is atomic and keeps other versions | Rerun with the binary already placed | `evals/update/test_sw_install.py` | `test_rerun_keeps_matching_binary` | red |
| install-update → Placing sw is atomic and keeps other versions | Interrupted before the rename | `evals/update/test_sw_install.py` | `test_interrupt_before_rename_leaves_no_final_file` | red |
| install-update → Placing sw is atomic and keeps other versions | A stale file at the final path | `evals/update/test_sw_install.py` | `test_stale_final_file_is_replaced` | red |
| install-update → Placing sw is atomic and keeps other versions | Matching hash but not runnable | `evals/update/test_sw_install.py` | `test_unrunnable_matching_file_is_replaced` (POSIX) | red |
| install-update → Placing sw is atomic and keeps other versions | Two installs of one version at once | `evals/update/test_sw_install.py` | `test_concurrent_installs_both_succeed` | red |
| install-update → Placing sw is atomic and keeps other versions | Rename blocked by a running binary | `evals/update/test_sw_install.py` | `test_blocked_rename_with_matching_file_is_kept` | red |
| install-update → Placing sw is atomic and keeps other versions | A temporary file left by a killed run | `evals/update/test_sw_install.py` | `test_only_old_part_files_are_cleaned` | red |
| install-update → Recovery leaves placed binaries in place | Rollback after the binary was placed | `evals/update/test_sw_install.py` | `test_rollback_keeps_placed_binaries` | red |
| install-update → Recovery leaves placed binaries in place | Previous version had no binary | `evals/update/test_sw_install.py` | `test_rollback_to_version_without_sw` | red |

## 1. The shared resolver

- [ ] 1.1 Write `evals/cli/test_sw_path.py` with the eight resolver tests of the test map, driving `bash skills/specwright-pr/scripts/sw-path.sh` against a temp code checkout and a temp `SPECWRIGHT_HOME`. A matching binary is a copy of the `SPECWRIGHT_SW` build (skip as `sw not built` without it). Mismatched or broken binaries are small stubs given through `--file` (a shell script on POSIX, a `.cmd` on Windows). Run `python -m unittest evals/cli/test_sw_path.py` and confirm each fails because `sw-path.sh` does not exist.
- [ ] 1.2 Write `skills/specwright-pr/scripts/sw-path.sh` (D2): `--code`, `--version`, `--file`; path `<home>/.specwright/bin/<version>/sw[.exe]`; the check runs through the `bounded.py` beside it with `SPECWRIGHT_NET_DEADLINE=10` and `SPECWRIGHT_NET_MAX_BYTES=1048576`; `SW_INTERFACE=1`; stdout carries only the path; every failure prints `sw missing or mismatched: rerun the install prompt` and a detail line, exit 1. Its header comment carries C10 (bounds) and C6 (no fallback to another version or `PATH`). Verify `test_sw_path.py` passes and flip its rows green.
- [ ] 1.3 Add `evals/cli/test_sw_interface_pin.py`: it reads `SW_INTERFACE` from `sw-path.sh` and `interfaceVersion` from `cli/lib/src/commands/version.dart` and fails when they differ. Add the doc comment on `interfaceVersion` that carries C2 (change both together, pinned by that test). Verify the test passes, and fails when one value is edited locally.
- [ ] 1.4 Add rules to `evals/suites.json` so `skills/specwright-pr/scripts/sw-path.sh` also routes to the `cli` suite, and so the new workflows and `cli/tool/*.py` are covered. Run `python -m unittest evals/runner/test_suite_map.py`.

## 2. Five-target build and the interface check in CI

- [ ] 2.1 Extend `evals/cli/test_verify_artifact.py` with `test_interface_mismatch_fails_naming_both`, a stub reporting the right version and another interface; run it and see it fail for the right reason (no interface argument yet).
- [ ] 2.2 Add `--interface-from <sw-path.sh>` to `cli/tool/verify_artifact.py`: it reads `SW_INTERFACE` and fails naming both interfaces on a mismatch. Verify `test_verify_artifact.py` passes and flip the two interface rows' verify-artifact part green.
- [ ] 2.3 Write `evals/cli/test_workflows.py` (text checks of the workflow files with the standard library): five targets on `ubuntu-24.04`, `ubuntu-24.04-arm`, `windows-latest`, `macos-latest`, `macos-15-intel`; `fail-fast: false`; verify runs `verify_artifact.py` with `--interface-from`; `release.yml` has the per-tag concurrency group with `cancel-in-progress: false`, `contents: write` only on `attach`, and `attach` needs every verify job. Run it and see it fail.
- [ ] 2.4 Move the build and verify jobs into `.github/workflows/sw-build.yml` (`workflow_call`, input `ref`) with the five-target matrix and the interface check, and have `cli.yml` call it for pull requests (path filters keep `cli/**`, `mise.toml`, `VERSION`, the workflow files and `skills/specwright-pr/scripts/sw-path.sh`). Its header comment carries C14 (one shared build for pull requests and releases). Verify the `sw-build.yml` parts of `test_workflows.py` pass.
- [ ] 2.5 [evidence] Verify A2 and A3: push the branch (`[vcs] push`, fenced) and run `gh workflow run cli.yml --ref feat/native-cli-distribution` through `as.sh`. Wait for all ten build and verify jobs and record the run URL, each job's result and the size of each binary. A failing arm64 or Intel runner is design drift: stop and decide under the drift rule. Flip `All three builds pass` and `All five builds pass` green → evidence/ci-five-targets.md

## 3. Release workflow and the seal

- [ ] 3.1 [evidence] Verify A1: read GitHub's documentation on which events start workflow runs (a release created with a personal token, not `GITHUB_TOKEN`) through `ctx7` or the GitHub docs, and record what it says and how `release.sh` authenticates (`as.sh` run login) → evidence/release-trigger.md
- [ ] 3.2 Write `evals/cli/test_attach_release.py` against `cli/tool/attach_release.py`, driven with the fake `gh` in `evals/fakes/gh.py` (extended for `release view --json assets`, `release download` and `release upload`, if it lacks them): tests for an unsealed release, a partial unsealed release, a sealed complete release, a sealed release missing a binary, a tag without a release, a read-back hash mismatch, the tag's `VERSION` differing, and the `SHA256SUMS` content. Run it and see it fail.
- [ ] 3.3 Write `cli/tool/attach_release.py` (D5): check the tag's `VERSION` and that the release exists; a sealed release is complete or fails; otherwise upload the five binaries with `--clobber`, download each back and compare hashes, then build and upload `SHA256SUMS` last (sorted, `<hash>  <name>`). Verify `test_attach_release.py` passes and flip its rows green.
- [ ] 3.4 Write `.github/workflows/release.yml`: `on: release: [published]` and `workflow_dispatch` (input `tag`), `concurrency: {group: sw-release-<tag>, cancel-in-progress: false}`, the call to `sw-build.yml` at the tag, and `attach` (`contents: write`, `needs` every verify job) running `attach_release.py`. Verify `test_workflows.py` passes in full and flip its rows green.
- [ ] 3.5 Carry C1 and C9: confirm the delta spec `specs/native-cli/spec.md` holds the asset-name and `SHA256SUMS` format requirement (C1) and the seal requirement (C9) with the text the design names, and add one line to `CONTRIBUTING.md` on how to add a target (matrix in `sw-build.yml`, the asset list in `attach_release.py`, the host map in `update.sh`). Verify by reading the files.

## 4. Install: `update.sh sw-install`

- [ ] 4.1 [evidence] Verify A4: fetch the headers of one asset of an existing public GitHub release (no auth) with a bounded `python -I` urllib call that does not follow redirects, and record each redirect hop's scheme and host → evidence/release-download-redirects.md
- [ ] 4.2 Write `evals/update/test_sw_install.py` with every install-update row of the test map. A fixture release directory served through `--release-url file://...` holds the `SPECWRIGHT_SW` build under the host's asset name and a `SHA256SUMS` line. Stalls and oversized answers come from a local `http.server` thread. The rollback tests reuse the interrupt fixtures of `evals/update/test_interrupt.py`. Run it and see it fail.
- [ ] 4.3 Add the `sw` field to `plan` (D1, D8: `{asset, target}` or `{asset: null, reason: unsupported_platform}`) and the host map. Verify the plan rows of `test_sw_install.py` pass.
- [ ] 4.4 Implement `sw_download` (D3): origin to `<owner>/<repo>` (github.com `https` only, else `no_github_origin`), `--release-url`, a `python -I` child under `bounded.run_bounded` (120 s) that streams to the part file and stops past 64 MiB, `https`-only redirects, `asset_missing` and `assets_not_uploaded`. Its doc comment carries C8 (anonymous, no `gh`), C13 (no retry) and C15 (`https`-only redirects). Verify the download and stop rows pass.
- [ ] 4.5 Implement `sw_install` placement (D7): cleanup of parts older than one hour, the SHA-256 before `xattr -d` and before the first run, `chmod`, `sw-path.sh --file` checks of the part and of an existing final file, rename, and the re-check after a failed rename (`kept` or `sw_in_use`). Its doc comment carries C4 (no pruning) and C5 (checksum proves integrity, not authorship). Wire the subcommand into the usage text and dispatch (`scripts/update.sh:281`, `:962-971`). The comment on `INTERFACE` carries C7 (additive, interface stays 2). Verify every `test_sw_install.py` row passes and flip them green.
- [ ] 4.6 Carry C3, C11, C12, C16 and C17: confirm the delta spec `specs/install-update/spec.md` holds each requirement the design names for them, with the stated text. Verify by reading the file.

## 5. Install prompt and docs

- [ ] 5.1 Update the README install prompt: in Step 3, after `plan`, a tag whose `plan` has an `sw` field runs `update.sh sw-install` and stops before Step 4 on a non-zero exit, naming its `error` and `message`; `main` and a `plan` without the field skip it. Step 8 reports the `sw` path, or why none was installed. Verify with the `update` suite's prompt-text tests, if any cover Step 3, and by reading the steps against the spec scenarios.
- [ ] 5.2 Update `openspec/architecture.md`: the `sw` row (`:92`: binaries per release, the install places them, `sw-path.sh` resolves them), the install and `update.sh` rows (`sw-install`, the `plan` field), and the state table (`<home>/.specwright/bin/<version>/`, release assets and the seal). Verify that no row still says that nothing installs `sw`.

## 6. Release

- [ ] 6.1 Run `release.sh bump --to 0.24.0` and rewrite the summary of the proposal's `## Release Notes` section for the whole release. Verify with `release.sh check` and `release.sh notes --proposal openspec/changes/native-cli-distribution/proposal.md`.

## Workflow follow-up

- After merge, publishing `v0.24.0` triggers `release.yml`. Check that the release gets five binaries and `SHA256SUMS` (A1). If it does not, run the workflow by hand for the tag and note it at the M7 close.
