# Tasks

## Test map

| Requirement | Scenario | Test file | Test name | State |
|---|---|---|---|---|
| native-cli → sw reports its version and interface version | Version report of a CI build | evals/cli/test_sw_version.py | test_version_json_reports_version_and_interface | red |
| native-cli → sw reports its version and interface version | Unknown command or flag | evals/cli/test_sw_version.py | test_unknown_command_or_flag_prints_usage_and_exits_2 | red |
| native-cli → sw run --bounded keeps bounded.py's command-line contract | Command finishes within its limits | evals/cli/test_sw_run.py | test_passes_output_and_status_through | red |
| native-cli → sw run --bounded keeps bounded.py's command-line contract | Deadline reached | evals/cli/test_sw_run.py | test_deadline_exits_124_with_the_limit_line | red |
| native-cli → sw run --bounded keeps bounded.py's command-line contract | Output over the bound | evals/cli/test_sw_run.py | test_too_large_exits_125_before_the_deadline | red |
| native-cli → sw run --bounded keeps bounded.py's command-line contract | Invalid invocation | evals/cli/test_sw_run.py | test_invalid_invocation_exits_2_and_starts_nothing | red |
| native-cli → sw run --bounded keeps bounded.py's command-line contract | Command cannot be started | evals/cli/test_sw_run.py | test_missing_command_exits_127 | red |
| native-cli → sw run --bounded keeps bounded.py's command-line contract | A limited command is never run again | evals/cli/test_sw_run.py | test_limited_command_started_at_most_once | red |
| native-cli → sw run --bounded keeps bounded.py's command-line contract | Limit line names the command a shell wraps | evals/cli/test_sw_run.py | test_limit_line_names_the_command_inside_bash_c | red |
| native-cli → Bounded limits can only be lowered | Environment lowers the deadline | evals/cli/test_sw_run.py | test_env_lowers_the_deadline | red |
| native-cli → Bounded limits can only be lowered | Environment tries to raise a limit | evals/cli/test_sw_run.py | test_env_cannot_raise_a_limit | red |
| native-cli → Bounded limits can only be lowered | Deadline-at already in the past | evals/cli/test_sw_run.py | test_deadline_at_in_the_past_exits_124_unstarted | red |
| native-cli → Bounded limits can only be lowered | Malformed override | evals/cli/test_sw_run.py | test_malformed_override_is_ignored | red |
| native-cli → A command's exit is judged when it happens | Exit just before the deadline while a child holds the pipe | evals/cli/test_sw_run.py | test_exit_before_deadline_with_pipe_holder_keeps_status | red |
| native-cli → A command's exit is judged when it happens | Exit after the deadline | evals/cli/test_sw_run.py | test_exit_after_deadline_exits_124 | red |
| native-cli → The whole process tree is stopped | Orphaned grandchild on a deadline | evals/cli/test_sw_tree.py | test_orphaned_grandchild_is_stopped | red |
| native-cli → The whole process tree is stopped | A limit before the command has started | evals/cli/test_sw_tree.py | test_held_startup_before_containment, test_held_startup_after_ready_before_go | red |
| native-cli → The whole process tree is stopped | sw itself already runs in a job | evals/cli/test_sw_tree.py | test_nested_job_holds_the_tree | red |
| native-cli → The whole process tree is stopped | No job object on Windows | evals/cli/test_sw_tree.py | test_no_job_announces_and_stops_by_pid | red |
| native-cli → Secret mode keeps output off disk | Token lookup | evals/cli/test_sw_run.py | test_secret_mode_writes_nothing_to_disk | red |
| native-cli → Secret mode keeps output off disk | Secret command floods its output | evals/cli/test_sw_run.py | test_secret_flood_never_echoes_output | red |
| native-cli → Commands resolve as the shell would find them | A .cmd shim on Windows | evals/cli/test_sw_args.py | test_cmd_shim_resolves_through_pathext | red |
| native-cli → Commands resolve as the shell would find them | A name that resolves nowhere | evals/cli/test_sw_args.py | test_unresolved_name_exits_127 | red |
| native-cli → Arguments reach native executables unchanged | A long argument to a native executable | evals/cli/test_sw_args.py | test_long_argument_to_native_exe_is_unchanged | red |
| native-cli → Arguments reach native executables unchanged | A long argument through bash -c on Windows | evals/cli/test_sw_args.py | test_long_argument_through_bash_c_transport | red |
| native-cli → Arguments reach native executables unchanged | A missing transport end marker | evals/cli/test_sw_args.py | test_missing_transport_marker_exits_126 | red |
| native-cli → Batch shims get escaped arguments or none | Metacharacters reach the shim literally | evals/cli/test_sw_args.py | test_batch_metacharacters_reach_recorder | red |
| native-cli → Batch shims get escaped arguments or none | Trailing backslashes survive forwarding | evals/cli/test_sw_args.py | test_batch_trailing_backslashes_survive | red |
| native-cli → Batch shims get escaped arguments or none | A shim found in a directory whose name cmd.exe would expand | evals/cli/test_sw_args.py | test_batch_path_with_percent_is_refused | red |
| native-cli → Batch shims get escaped arguments or none | An argument that cmd.exe would expand | evals/cli/test_sw_args.py | test_batch_unsafe_argument_is_refused | red |
| native-cli → Batch shims get escaped arguments or none | A batch command line over the cmd.exe limit | evals/cli/test_sw_args.py | test_batch_line_over_limit_is_refused | red |
| native-cli → Every platform's binary is built and checked in CI | All three builds pass | evals/runner/test_cli_workflow.py | test_cli_workflow_builds_tests_and_verifies_each_os | red |
| native-cli → Every platform's binary is built and checked in CI | Checksum does not match | evals/cli/test_verify_artifact.py | test_checksum_mismatch_fails_without_running | red |
| native-cli → Every platform's binary is built and checked in CI | Version drifts from VERSION | evals/cli/test_verify_artifact.py | test_version_drift_fails_naming_both | red |
| native-cli → The macOS binary runs after a documented quarantine step | Quarantined binary after the documented step | evals/runner/test_cli_workflow.py | test_macos_verify_sets_quarantine_and_applies_step | red |
| native-cli → The macOS binary runs after a documented quarantine step | The documented step does not unblock it | evals/runner/test_cli_workflow.py | test_macos_verify_fails_when_step_does_not_unblock | red |
| eval-runner → Suites that need sw run against a binary built from the tree in CI | CI run | evals/runner/test_ci_workflow.py | test_cli_suite_jobs_build_sw_and_require_it | red |
| eval-runner → Suites that need sw run against a binary built from the tree in CI | Build fails | evals/runner/test_ci_workflow.py | test_sw_build_step_fails_the_job | red |
| eval-runner → Suites that need sw run against a binary built from the tree in CI | Local run without sw | evals/cli/test_sw_harness.py | test_skips_with_sw_not_built | red |
| eval-runner → Suites that need sw run against a binary built from the tree in CI | Required but missing | evals/cli/test_sw_harness.py | test_require_sw_fails_naming_the_binary | red |
| eval-runner → A stopped test file's sw process groups are stopped too | Runner timeout during a hung sw test | evals/runner/test_run.py | test_sweep_stops_sw_sessions_after_timeout | red |
| eval-runner → A stopped test file's sw process groups are stopped too | Variable unset | evals/cli/test_sw_tree.py | test_no_spawn_record_without_variable | red |
| eval-runner → A stopped test file's sw process groups are stopped too | Unwritable spawn directory | evals/cli/test_sw_tree.py | test_unwritable_spawn_dir_leaves_result_unchanged | red |
| eval-runner → Dart tests run locally only for the module being written | Both files carry the rule | evals/runner/test_agent_instructions.py | test_dart_single_file_rule_in_both_files | red |
| eval-runner → Dart tests run locally only for the module being written | A file tells the reader to run every Dart test | evals/runner/test_agent_instructions.py | test_whole_dart_run_instruction_fails_naming_line | red |

The two `test_cli_workflow.py` macOS rows and the "All three builds pass" row check the workflow's structure in code; their runtime proof is the CI run in task 7.2 (evidence). The CI-only test files run in CI per `AGENTS.md`; locally only the module being written runs, red then green.

## 1. ADR and architecture

- [x] 1.1 Write `docs/adr/0027-shipped-tooling-is-one-dart-binary.md` (MADR-short, Status accepted, Supersedes 0002, adds to 0014) as design.md's ADRs section describes, carrying C4 (install root, exact version and interface, unsigned-first with the quarantine step and signing trigger; rejected: per-project binary, interface-only matching, `dart build cli`, signing first), C5 (scripts and `bounded.py` copies stay until each port and M8), C6 (parent killed by SIGKILL or task kill can leave the helper and command; evals close it via the spawn record) and C8 (CI artifacts only; linux-arm64, macOS x64 and release assets are `native-cli-distribution`'s). Verify: the file exists and states the facts of C4, C5, C6 and C8.
- [x] 1.2 Add ADR 0027 to the in-force index in `openspec/architecture.md`, mark 0002 superseded by 0027 and note 0014's addition; update any section the decision changes (tooling shape). Verify: the index row exists and 0002 is no longer listed as in force.

## 2. Dart package scaffold and toolchain

- [ ] 2.1 Verify A6 and A4 locally: read the owner's Dart pin (Dart 3.13.7 through mise) and confirm `mise exec -- dart --version` resolves pure Dart from a new root `mise.toml` (`[tools] dart = "3.13.7"`). Record the version in the task's commit message. Verify: the command prints 3.13.7.
- [ ] 2.2 Create `cli/` (`pubspec.yaml` with `package:args` and `package:ffi` only, `analysis_options.yaml` with lints, `dart_test.yaml` with tags, `bin/sw.dart`), mise tasks `test`, `analyze`, `format`, `build` in `mise.toml`, and `.gitignore` entries for `cli/.dart_tool/` and build outputs. Write C3 as the doc comment above `dependencies` in `cli/pubspec.yaml`. Verify: `mise exec -- dart analyze cli` and `mise exec -- dart format --set-exit-if-changed cli` pass; the comment is present.
- [ ] 2.3 Verify A3: run `mise exec -- dart pub get` in `cli/` and `mise exec -- dart compile exe cli/bin/sw.dart -o <tmp>/sw`; confirm `pubspec.lock` holds no package with build hooks and compile succeeds. Verify: the binary runs.
- [ ] 2.4 Write the failing Dart test `cli/test/no_build_hooks_test.dart` (fails when any `pubspec.lock` package declares `hooks`), then make it pass. Verify: `mise exec -- dart test cli/test/no_build_hooks_test.dart` green.
- [ ] 2.5 Add rules to `evals/suites.json` for `cli/**`, `mise.toml` and `.github/workflows/cli.yml` (suite `cli`, plus `runner` for the workflow), and create `evals/cli/` with a shared harness module that resolves `SPECWRIGHT_SW` and skips or fails per `SPECWRIGHT_REQUIRE_SW`. Verify: `python -m unittest evals/runner/test_suite_map.py` passes.

## 3. sw version and the eval harness

- [ ] 3.1 Write failing `evals/cli/test_sw_harness.py` (`test_skips_with_sw_not_built`, `test_require_sw_fails_naming_the_binary`) and `evals/cli/test_sw_version.py` (both version rows); verify they fail (or skip) for the right reason.
- [ ] 3.2 Implement the harness skip/fail behaviour and `sw version --json` with `--define=SW_VERSION` (default `0.0.0-dev`) and `interface: 1`, plus usage and exit 2 for unknown commands and flags, with Dart unit tests in `cli/test/version_test.dart`. Verify: the four rows go green (locally with `SPECWRIGHT_SW` pointing at a `mise run build` binary); flip them.

## 4. Bounded runner core (all OSes)

- [ ] 4.1 Verify A5: write a Dart spike test `cli/test/inherit_stdio_test.dart` showing a helper started with `inheritStdio` hands its pipes to a child, and that a one-byte stdin read leaves the following bytes for the child. Verify: the test passes on this machine; a failure is design drift (stop).
- [ ] 4.2 Write failing tests in `evals/cli/test_sw_run.py` for every `test_sw_run.py` row in the test map (contract, limits, exit timing, secret mode, shell-wrapper attribution, at most once), with fresh fixtures (no copied code). Verify: each fails for the right reason.
- [ ] 4.3 Implement `cli/lib/src/process/bounded_run.dart` (`BoundedRun`, D7: stream byte counting, deadline timer racing the exit future, 2 s grace, 5 s pipe release, limit line with wrapper attribution, env lowering and `SPECWRIGHT_NET_DEADLINE_AT`), `sw run --bounded` argument parsing, and the helper startup protocol (D1 steps 1–7: ready frame, go byte, pre-go cancellation closing the pipe and killing the helper by PID). Write C1 and C7 as checked (they are already in specs/native-cli/spec.md under "sw run --bounded keeps bounded.py's command-line contract"; confirm the text) and C10 as the doc comment on `BoundedRun`. Add Dart unit tests for the limit parsing and frame stripping. Verify: the `test_sw_run.py` rows go green on this machine; flip them; `mise exec -- dart test` for each new Dart test file passes.

## 5. Process trees: Windows job and POSIX session

- [ ] 5.1 Verify A1: a Dart test `cli/test/windows_job_test.dart` (Windows only) showing a self-started compiled `sw __exec` joins an inherited job handle, also inside an outer job. Verify: passes on this machine; a failure is design drift (stop).
- [ ] 5.2 Write failing `evals/cli/test_sw_tree.py`: true orphan fixture (child records grandchild PID, exits, then the limit hits; every recorded PID gone), nested job, no-job announcement (`SPECWRIGHT_TEST_NO_JOB=1`), held startup with `SPECWRIGHT_TEST_HOLD_START` (`before` and `after`, the `after` case with `SPECWRIGHT_TEST_PRE_GO`), spawn-record unset and unwritable cases. Verify: each fails for the right reason.
- [ ] 5.3 Implement `cli/lib/src/native/` bindings (D12: kernel32 job calls; libc `setsid`, `kill`), `cli/lib/src/process/windows_tree.dart` (`WindowsTree`, job without kill-on-close, PID fallback with its announcement) and the POSIX session/group kill with the `SPECWRIGHT_TEST_SPAWN_DIR` record (D6), and the test-only hold and pre-go hooks. Write C2 as the doc comment on `WindowsTree`. Verify: the `test_sw_tree.py` rows go green on Windows here; flip them after CI shows Linux and macOS green (task 7.2).
- [ ] 5.4 Write failing `test_sweep_stops_sw_sessions_after_timeout` in `evals/runner/test_run.py`, then make `evals/run.py`'s sweep stop recorded `sw` groups (pass `SPECWRIGHT_TEST_SPAWN_DIR` to `cli` test files). Verify: the row goes green in CI on Linux and macOS; flip it.

## 6. Command lookup and arguments

- [ ] 6.1 Write failing `evals/cli/test_sw_args.py` for every `test_sw_args.py` row: PATHEXT resolution, 127, long native argument, `bash -c` stdin transport and missing marker (126), batch metacharacters through a `%*`-forwarding shim and native recorder (seven arguments; `x & echo pwned` runs nothing), trailing one and two backslashes, `%SW_SLOT%` PATH directory with a decoy shim, unsafe arguments, over-limit line. Verify: each fails for the right reason.
- [ ] 6.2 Implement `cli/lib/src/process/command_line.dart` (D8): PATH/PATHEXT lookup (default `.COM;.EXE;.BAT;.CMD`), native direct start, the `bash -c` NUL transport written after the go byte, and batch quoting (path and arguments double-quoted, trailing backslashes doubled, refusal of `%`, `!`, `"`, CR, LF, NUL in arguments, `%` or `!` in the resolved path, and lines over 8,191 characters). Confirm C9's text in specs/native-cli/spec.md under "Batch shims get escaped arguments or none". Add Dart unit tests for the quoting function. Verify: the `test_sw_args.py` rows go green on Windows here; flip them.

## 7. CI build, artifacts and download-and-run

- [ ] 7.1 Write failing `evals/runner/test_cli_workflow.py` (three rows) and `evals/cli/test_verify_artifact.py` (checksum mismatch, version drift) against a new `cli/tool/verify_artifact.py`; then write `.github/workflows/cli.yml` (D10: build per OS through `jdx/mise-action` pinned to mise 2026.10.12, analyze, format, test, compile with the version define, SHA-256 artifact; a verify job per OS that downloads, checks the checksum, runs `sw version --json` against `VERSION`; on macOS sets `com.apple.quarantine`, logs whether it runs, applies `xattr -d` and requires success), and add the `cli` suite to `.github/workflows/evals.yml` with `sw` built from the tree and `SPECWRIGHT_REQUIRE_SW=1` (eval-runner rows `CI run`, `Build fails`). Verify: these rows go green locally (structure) and A4 and A2 are settled by the PR's CI run.
- [ ] 7.2 [evidence] After the PR's CI is green on all three OSes, record the run URL, each artifact's SHA-256, and the macOS log line saying whether the quarantined binary ran before the step (A2) → evidence/ci-run.md. Flip the CI-proved rows green.

## 8. Contributor rules

- [ ] 8.1 Write failing `test_dart_single_file_rule_in_both_files` and `test_whole_dart_run_instruction_fails_naming_line` in `evals/runner/test_agent_instructions.py`, then add the Dart rule to `AGENTS.md` and `CONTRIBUTING.md` (`mise exec -- dart test <file>` for the file being written; CI runs the rest on three OSes). Verify: both rows go green with `python -m unittest evals/runner/test_agent_instructions.py`; flip them; `python -m unittest evals/runner/test_suite_map.py` passes.

## 9. Owner check and release

- [ ] 9.1 [user] Download the Windows `sw.exe` artifact from the PR's CI run, check it against its SHA-256, run `sw version --json`, and report whether Malwarebytes blocks or quarantines it (S3). A block makes signing the next decision under ADR 0027.
- [ ] 9.2 Run `bash skills/specwright-release/scripts/release.sh bump --to 0.23.0`, rewrite the summary of proposal.md's `## Release Notes` to describe the whole release. Verify: `release.sh check` and `release.sh notes --proposal openspec/changes/native-cli-spike/proposal.md` pass.

## Workflow follow-up

- Archive the change after the PR is ready (`opsx:archive`), then merge through `specwright-finish`.
- `native-cli-distribution` builds the install into `~/.specwright/bin/<version>/` and the skill-side version check.
