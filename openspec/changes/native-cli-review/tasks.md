# Tasks

## Test map

| Requirement | Scenario | Test file | Test name | State |
|---|---|---|---|---|
| review-routes → Review operations run in the project's sw | Pre-ship run without Python or bash | evals/review-routes/test_review_sw.py | test_preship_runs_without_python_or_bash | red |
| review-routes → Review operations run in the project's sw | Gate reads a record written before the port | evals/review-routes/test_review_sw.py | test_gate_passes_preport_record | red |
| review-routes → Review operations run in the project's sw | VCS backend read in process | evals/review-routes/test_review_sw.py | test_gitbutler_backend_read_without_pr_pair | red |
| review-routes → Review operations run in the project's sw | No matching sw | evals/review-routes/test_review_sw.py | test_select_sw_missing_starts_no_probe | red |
| review-routes → Each route's tools, features and extra flags are settings | OMP tool list from settings | evals/review-routes/test_review_settings.py | test_omp_tools_from_settings | red |
| review-routes → Each route's tools, features and extra flags are settings | Extra Codex feature disabled | evals/review-routes/test_review_settings.py | test_codex_extra_disable_keeps_defaults | red |
| review-routes → Each route's tools, features and extra flags are settings | Extra flag passed | evals/review-routes/test_review_settings.py | test_claude_extra_arg_after_fixed_flags | red |
| review-routes → Each route's tools, features and extra flags are settings | Key on the wrong route | evals/review-routes/test_review_settings.py | test_wrong_route_key_bad_route_setting | red |
| review-routes → Each route's tools, features and extra flags are settings | Wrong value type | evals/review-routes/test_review_settings.py | test_tools_string_bad_route_setting | red |
| review-routes → A route setting that weakens isolation is refused | Shell tool for claude | evals/review-routes/test_review_settings.py | test_claude_bash_tool_refused | red |
| review-routes → A route setting that weakens isolation is refused | OMP write and memory tools | evals/review-routes/test_review_settings.py | test_omp_refused_tools | red |
| review-routes → A route setting that weakens isolation is refused | Sandbox override in Codex args | evals/review-routes/test_review_settings.py | test_codex_sandbox_flags_refused | red |
| review-routes → A route setting that weakens isolation is refused | Protected Codex key set through its parent table or quoting | evals/review-routes/test_review_settings.py | test_codex_protected_key_forms_refused | red |
| review-routes → A route setting that weakens isolation is refused | Flag Specwright sets itself | evals/review-routes/test_review_settings.py | test_omp_owned_flags_refused | red |
| review-routes → Shipped defaults keep each reviewer within the checkout | Default OMP command line | evals/review-routes/test_review_settings.py | test_default_omp_command_line | red |
| review-routes → Shipped defaults keep each reviewer within the checkout | Default Codex command line | evals/review-routes/test_review_settings.py | test_default_codex_command_line | red |
| review-routes → Shipped defaults keep each reviewer within the checkout | OMP older than the verified version | evals/review-routes/test_review_settings.py | test_omp_below_floor_skipped_and_refused | red |
| review-routes → Shipped defaults keep each reviewer within the checkout | Codex version without a listed feature | evals/review-routes/test_review_settings.py | test_codex_unknown_feature_fails_closed | red |
| review-routes → Reviewers run isolated and read-only | OMP review starts a fresh session | evals/review-routes/test_review_run.py | test_omp_fresh_session_dir_per_run | green |
| review-routes → Reviewers run isolated and read-only | Reviewer tries to write | evals/review-routes/trial.md | recorded trial, `git status --porcelain` after the write request (task 6.3) | n/a (recorded trial: needs real reviewer CLIs) |
| review-routes → Reviewers run isolated and read-only | Codex on Windows with a sandbox setting | evals/review-routes/test_review_run.py | test_codex_windows_forwards_sandbox_only | green |
| review-routes → Reviewers run isolated and read-only | Codex on Windows without a usable setting | evals/review-routes/test_review_run.py | test_codex_windows_no_usable_sandbox_adds_nothing | green |
| review-routes → Reviewers run isolated and read-only | Codex off Windows | evals/review-routes/test_review_run.py | test_codex_off_windows_adds_no_sandbox | green |
| review-routes → Every review records a receipt | OMP review receipt | evals/review-routes/test_review_run.py | test_receipt_omp_actual_model_from_session | green |
| review-routes → Every review records a receipt | Model not reported | evals/review-routes/test_review_run.py | test_receipt_unknown_actual_model | green |
| review-routes → Every review records a receipt | Effective tools in the receipt | evals/review-routes/test_review_settings.py | test_receipt_effective_tools | red |
| review-routes → Every review records a receipt | Receipt of a refused setting | evals/review-routes/test_review_settings.py | test_refused_setting_writes_nothing | red |
| review-routes → Reviewer output is bounded while the CLI runs | Output within the bounds | evals/review-routes/test_review_run.py | test_omp_stream_within_bounds_passes | green |
| review-routes → Reviewer output is bounded while the CLI runs | Runaway stdout | evals/review-routes/test_review_run.py | test_claude_stdout_flood_stopped_nothing_written | green |
| review-routes → Reviewer output is bounded while the CLI runs | Runaway stderr | evals/review-routes/test_review_run.py | test_codex_stderr_flood_stopped_review_unchanged | green |
| review-routes → Reviewer output is bounded while the CLI runs | Codex event stream over the bound | evals/review-routes/test_review_run.py | test_codex_event_stream_flood_stopped | green |
| review-routes → Reviewer output is bounded while the CLI runs | Codex answer file over the bound | evals/review-routes/test_review_run.py | test_codex_command_line_has_json_and_no_answer_file | green |

The `green` rows pass against the Python today. Task 4.9 re-runs them through the shim and `sw`.

## 1. ADR, roadmap, assumptions and the pre-port fixture

- [x] 1.1 [evidence] Verify A1, A2 and A3 on the CLIs installed at apply under D11 → evidence/cli-tools.md. A1/A3: capture native tool definitions and the complete mounted-tool inventory; source-ground their equivalence to the exact reviewer command, accounting for diagnostic-mode defaults and settings sources. Check each refused capability against those captures; model lists/refusals are corroboration only, not runtime rejection proof. Record `omp --version` and prove `learn` and `manage_skill` are absent under the D5 overlay. A2: keep every planned isolation flag, ask Codex to spawn with `fork_turns="none"` and attempt the checkout marker write, record the actual denied attempt and `git status --porcelain` before/after, and distinguish direct child tool results from parent-relayed reports. Retain full-history spawn failures separately. Missing equivalence, mounted-tool coverage or denied-write proof keeps the task blocked. A disproved assumption is design drift: stop and amend the design.
- [x] 1.2 Write `docs/adr/0035-reviewer-command-lines-are-a-fixed-core-plus-checked-settings.md` (`Status: accepted`), carrying C2, C5 and C11, amending ADR 0007's "Fixed, isolated command lines" point only. Add it to the ADR index in `openspec/architecture.md` and mark 0007 as amended by 0035. Verify: both files show the entries, and ADR 0007 is unchanged (`git diff --stat docs/adr/0007*` empty).
- [x] 1.3 Reword change 7 in `openspec/roadmap.md` to include the `review.routes` settings and the isolation defaults (proposal S4). Verify by reading the entry.
- [x] 1.4 Capture the pre-port record fixture: run the current Python `review-run.sh record --kind preship` on a scratch repo with a valid findings file, and copy the record into `evals/review-routes/fixtures/preport-record.json` with the heads it names. Add the fixture to `evals/suites.json` (review-routes) and run `python -m unittest evals/runner/test_suite_map.py`. Verify: the map test passes.

## 2. The `toml` package and BoundedRun's `pipesHeld`

- [x] 2.1 [evidence] Verify A4: list the closure of `toml` 0.18.0 (`petitparser`, `collection`, `meta`, `web`), check each for build hooks and its licence against ADR 0033 → evidence/toml-package.md. Then add `toml` to `cli/pubspec.yaml` and its notices to the shipped notices. Verify: `mise exec -- dart test test/no_build_hooks_test.dart` from `cli/` passes, and the notices list each package.
- [x] 2.2 Write a failing test in `cli/test/bounded_run_test.dart`: a child that exits while a grandchild holds stdout gives `pipesHeld: true` and its exit code; a normal exit gives `pipesHeld: false`. Verify it fails because the field is missing.
- [x] 2.3 Add `BoundedResult.pipesHeld` in `cli/lib/src/process/bounded_run.dart`, set where the tree is stopped after the exit, with the C4 doc comment. Verify: the 2.2 test passes and `launch_test.dart` still passes.

## 3. Route settings, refused lists and defaults (Dart)

- [ ] 3.1 Write failing tests in `cli/test/review/routes_test.dart` for: reading `review.routes.<route>` (`tools`, `disable`, `args`; a key on the wrong route and a wrong type give `bad_route_setting`); the refused tools and flags of each route from D2, case-insensitive tool names, `--flag=value` and `-sread-only` forms; `-c` key normalization (trimmed, quoted segments, ancestor tables `features={...}`, `windows={...}`, `sandbox_workspace_write={...}`); each default command line (OMP `--tools read,grep,glob` with `--config <overlay>`, Codex with every D6 `--disable` and `-c web_search="disabled"`, claude unchanged); and the OMP version floor (`18.18.9` refused, `18.19.0` accepted). Verify they fail for the missing code.
- [ ] 3.2 Implement `cli/lib/src/review/routes.dart`: route settings, refused lists, command-line builder, the OMP overlay writer and `ompMinVersion`, with the C3 doc comment on `codexDefaultDisable` and the C10 doc comment on `ompMinVersion`. Verify: the 3.1 tests pass.
- [ ] 3.3 Write a failing test, then read Codex's `[windows] sandbox` with `toml` in `cli/lib/src/review/routes.dart`: plain names forwarded on Windows only; a missing or bad file, a parse error or a value that is not a plain name gives nothing. Verify: the routes tests pass.
- [ ] 3.4 Write failing tests in `cli/test/review/settings_test.dart`, then read review settings with `readSettingsText`/`loadSettings`, searching the cwd then its toplevel, stopping with `bad_settings` naming the line when `yamlProblem` reports one (D4). Verify: the tests pass.

## 4. `sw review` and the shim

- [ ] 4.1 Write the failing evals in `evals/review-routes/test_review_sw.py` (rows 1-4) and `evals/review-routes/test_review_settings.py` (rows 5-18, 26 and 27), against the script path with fake CLIs on `PATH`. Add both to `evals/suites.json` and run the map test. Verify: `python -m unittest evals/review-routes/test_review_settings.py` fails on the missing settings, not on a harness error.
- [ ] 4.2 Write failing Dart tests, then implement `cli/lib/src/review/records.dart` (record path and JSON as `review-run.sh:825-867`, atomic write) with the C1 doc comment on `recordPath`. Verify: a record written for the 1.4 fixture's heads is byte-equal in path and fields to the fixture.
- [ ] 4.3 Implement `sw review select` and `preflight` in `cli/lib/src/review/`: probes through the native launcher, `review.order`, `cross_model`, OMP roles and the OMP floor at select, the VCS backend through `readVcsSettings`. Verify: `SelectTests` in `test_review_run.py` and the select rows of 4.1 pass when run through `sw` on this machine.
- [ ] 4.4 Implement `sw review run` in `cli/lib/src/review/run.dart`: prompt assembly as `review-run.sh:870-941`, the reviewer started through `BoundedRun` with the stream bounds and `review.timeout`, `pipesHeld` failing the run, answer parsing per route, receipts with `tools`, `disabled` and `extra_args`. Put the C6 and C7 doc comments on `runReviewer`. Verify: `RunTests` and `OutputBound` pass through `sw`, and rows 15-18, 26 and 27 turn green.
- [ ] 4.5 Implement `cli/lib/src/review/snapshot.dart`: the tip snapshot reading `git cat-file --batch` incrementally and copying each blob in 64 KiB chunks, a non-UTF-8 path as a named stop, with the C9 doc comment on `snapshotTip`. Write a Dart test with one blob larger than 64 KiB first. Verify: that test and the GitButler snapshot evals pass.
- [ ] 4.6 Implement `record`, `waive`, `gate`, `archive-only` and `rounds`. Verify: `RecordGateTests` and `ArtifactPathTests` pass through `sw`, and `test_gate_passes_preport_record` turns green.
- [ ] 4.7 Register `sw review` in `cli/lib/src/cli.dart` with `--args-stdin`. Turn `skills/specwright-review/scripts/review-run.sh` into an ADR 0028 shim whose `sw_missing` text is escaped in bash (D7). Remove `skills/specwright-review/scripts/bounded.py`. Verify: rows 1, 3 and 4 turn green, and `grep -n python skills/specwright-review/scripts/review-run.sh` finds nothing.
- [ ] 4.8 Update the evals that assumed the Python: replace `test_reviewer_output_on_disk_never_passes_its_bound` with an in-memory bound check, update `test_no_bytecode.py` for the removed `bounded.py`, and put the C8 module docstring in `test_review_run.py`. Update `evals/suites.json` for the removed file and run the map test. Verify: the map test passes.
- [ ] 4.9 Re-run the `green` rows through the shim and `sw`. Verify: each still passes in the PR CI run of task 6.1.

## 5. Skill text and settings docs

- [ ] 5.1 Document `review.routes` (`tools`, `disable`, `args`, the refusal stops `route_setting_unsafe` and `bad_route_setting`, the defaults, the OMP floor and `bad_settings`) in `skills/specwright-review/SKILL.md` and the settings template `templates/openspec/specwright.yaml`, listing the Codex default disable list. Add checks to `evals/review-routes/test_skill_text.py` first. Verify: `python -m unittest evals/review-routes/test_skill_text.py` passes.
- [ ] 5.2 Add the short manual CLI-version-check procedure governed by ADR 0035/C11 to `skills/specwright-review/SKILL.md`: capture native tool definitions and complete mounted-tool inventory, demonstrate equivalence to the exact reviewer invocation, check refused capabilities and add new risky tools to refused lists, and obtain direct child denied-write evidence with every fixed isolation flag retained. Model lists/refusals are corroboration only; missing proof or an infrastructure failure does not pass. Add a skill-text check for that standard. Verify: the skill-text test passes.

## 6. Integration and release

- [ ] 6.1 Open a draft PR and run the CI evals and the Dart tests on Linux, Windows and macOS (`.github/workflows/evals.yml`, `.github/workflows/cli.yml`). Verify: both workflows are green on the PR head, and every `red` row of the test map is flipped `green`.
- [ ] 6.2 [evidence] Run a real design review on each of `codex`, `claude` and `omp` through the shim → evidence/real-routes.md, with each receipt's `tools`, `disabled` and `extra_args`. Verify: each run exits 0.
- [ ] 6.3 Re-run the write trial in `evals/review-routes/trial.md` on all three routes with the new defaults, and record `git status --porcelain` after each. Verify: the porcelain output is unchanged after each run.
- [ ] 6.4 `release.sh bump --to 0.34.0` and rewrite the summary of the proposal's `## Release Notes` for the whole release. Verify: `release.sh check` passes and `release.sh notes --proposal openspec/changes/native-cli-review/proposal.md` prints the notes.

## Workflow follow-up

- Archive the change and ship it through `specwright-finish`; after merge, publish v0.34.0 through `specwright-release`.
