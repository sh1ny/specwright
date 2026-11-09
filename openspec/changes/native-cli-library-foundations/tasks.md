# Tasks

## Test map

| Requirement | Scenario | Test file | Test name | State |
|---|---|---|---|---|
| native-cli → sw documents are compact JSON ending in one line feed | Document on Windows | evals/cli/test_documents.py | test_document_is_compact_with_one_lf | red |
| native-cli → sw documents are compact JSON ending in one line feed | Non-UTF-8 file name in a document | cli/test/vcs/document_test.dart | non-UTF-8 name bytes survive the document | green |
| native-cli → sw documents are compact JSON ending in one line feed | A value a document cannot hold | cli/test/vcs/document_test.dart | a value JSON cannot hold is internal_error | red |
| native-cli → JSON input that is not plain JSON is refused | Well-formed input | cli/test/pr/reviewers_test.dart | valid material is evaluated | green |
| native-cli → JSON input that is not plain JSON is refused | Non-finite number | cli/test/pr/reviewers_test.dart | NaN and Infinity in material stop naming the file | red |
| native-cli → JSON input that is not plain JSON is refused | Very deep nesting | cli/test/vcs/document_test.dart | 100,000 levels never crash | red |
| native-cli → JSON input that is not plain JSON is refused | An integer that cannot be held exactly | cli/test/pr/policy_test.dart | an integer beyond 64 bits stops the comparison | red |
| native-cli → JSON input that is not plain JSON is refused | A JSON file over the size limit | cli/test/vcs/document_test.dart | a file over 32 MiB stops naming the file | red |
| native-cli → JSON input that is not plain JSON is refused | An integer setting beyond 64 bits | cli/test/settings/rules_test.dart | an integer setting beyond 64 bits is bad_setting | red |
| native-cli → JSON input that is not plain JSON is refused | Reviewer config for ordinary values | cli/test/settings/reviewer_config_test.dart | bytes and digest are unchanged | green |
| native-cli → sw options follow one parsing rule | Equals form | cli/test/options_test.dart | equals form matches the two-word form | red |
| native-cli → sw options follow one parsing rule | A value that looks like an option | cli/test/options_test.dart | the next word is the value | red |
| native-cli → sw options follow one parsing rule | A repeated option holding a comma | cli/test/options_test.dart | repeated values keep their commas | red |
| native-cli → sw options follow one parsing rule | Abbreviated option | cli/test/pr/reviewers_test.dart | an abbreviated option is a usage stop | red |
| native-cli → sw options follow one parsing rule | Missing value | cli/test/vcs/args_test.dart | a missing value is a usage stop | green |
| native-cli → sw options follow one parsing rule | Words that are not paths | cli/test/vcs/args_test.dart | a word before -- is a usage stop | green |
| native-cli → sw options follow one parsing rule | Shipped callers use whole option names | evals/cli/test_option_callers.py | test_shipped_callers_use_whole_names | red |
| native-cli → The shipped dependencies stay hook-free and carry their notices | Current dependency set | cli/test/no_build_hooks_test.dart | the closure has no hooks and every package has a notice | red |
| native-cli → The shipped dependencies stay hook-free and carry their notices | A hook package enters the lock file | cli/test/no_build_hooks_test.dart | a hook package is named | green |
| native-cli → The shipped dependencies stay hook-free and carry their notices | A dependency without a notice | cli/test/no_build_hooks_test.dart | a package with no notice is named | red |
| pr-script-runtime → Paginated GitHub lists read every page or decide nothing | Several pages | cli/test/pr/workflow_test.dart | slurped pages flatten in order | red |
| pr-script-runtime → Paginated GitHub lists read every page or decide nothing | No items | cli/test/pr/workflow_test.dart | an empty slurp is an empty list | red |
| pr-script-runtime → Paginated GitHub lists read every page or decide nothing | A page that is not an array | cli/test/pr/workflow_test.dart | a non-array page is an unknown read | red |
| pr-script-runtime → Paginated GitHub lists read every page or decide nothing | gh older than 2.48 | cli/test/pr/workflow_test.dart | a slurp failure names gh 2.48 | red |
| pr-script-runtime → Prerequisites are stated and checked at install | All prerequisites present | evals/git-workflow/test_instructions.py | existing prerequisite cases, stating 2.48 | red |
| pr-script-runtime → Prerequisites are stated and checked at install | Python missing | evals/git-workflow/test_instructions.py | existing prerequisite cases | green |
| pr-script-runtime → Prerequisites are stated and checked at install | gh missing | evals/git-workflow/test_instructions.py | existing prerequisite cases | green |
| pr-script-runtime → The ported pr-pair subcommands keep the script's contracts | Policy's remote settings read is strict | evals/pr-pair/test_parity.py | test_policy_stops | green |
| pr-script-runtime → The ported pr-pair subcommands keep the script's contracts | Git Bash path forms | evals/pr-pair/test_parity.py | existing path-form cases | green |
| pr-script-runtime → The ported pr-pair subcommands keep the script's contracts | Unchanged black-box evals pass on sw | .github/workflows/evals.yml | evals/pr-pair on three OSes | green |
| pr-script-runtime → The ported pr-pair subcommands keep the script's contracts | Differential run against the frozen script | evals/pr-pair/test_parity.py | assertParity on parsed values | red |
| pr-script-runtime → The ported pr-pair subcommands keep the script's contracts | A malformed settings file names its line | evals/pr-pair/test_parity.py | test_context_tab_in_indentation_names_line_7 | green |
| pr-script-runtime → The ported pr-pair subcommands keep the script's contracts | Settings not pinned on GitButler | evals/pr-pair/test_parity.py | existing GitButler settings case | green |
| pr-script-runtime → sw pr reviewers keeps the evaluator's contract | Unchanged evaluator tests | .github/workflows/evals.yml | evaluator tests on three OSes | green |
| pr-script-runtime → sw pr reviewers keeps the evaluator's contract | Material that is not its head | evals/pr-pair/test_parity.py | ReviewersParity on parsed values | red |
| vcs-backends → sw vcs keeps vcs.sh's output and exit-code contract | Unchanged black-box evals pass on sw | .github/workflows/evals.yml | evals/vcs on three OSes | red |
| vcs-backends → sw vcs keeps vcs.sh's output and exit-code contract | Unknown subcommand | cli/test/vcs/args_test.dart | an unknown subcommand is a usage stop | green |
| vcs-backends → sw vcs documents keep their values and name bytes | Line separators stay escaped | cli/test/vcs/document_test.dart | U+2028 and U+2029 parse back | red |
| vcs-backends → sw vcs documents keep their values and name bytes | A non-UTF-8 name from a tool round-trips | evals/vcs/test_sw_bytes.py | existing round-trip case | green |
| vcs-backends → sw vcs documents keep their values and name bytes | A valid U+FFFD in a name is just a character | evals/vcs/test_sw_bytes.py | existing U+FFFD case | green |
| vcs-backends → sw vcs documents keep their values and name bytes | Tool input reaches the tool | evals/vcs/test_sw_scripts.py | existing oversized ignored file case | green |
| task-commits → sw commit task-cover keeps task-cover.sh's contract | Unchanged task-cover evals pass on sw | .github/workflows/evals.yml | task-cover tests on three OSes | red |
| task-commits → sw commit task-cover keeps task-cover.sh's contract | Usage error | cli/test/commit/task_cover_test.dart | usage stop names the usage line | green |
| task-commits → sw commit task-cover keeps task-cover.sh's contract | A group number beyond 64 bits is not a task | cli/test/commit/task_cover_test.dart | a group number beyond 64 bits is not a task | red |
| task-commits → sw commit task-cover keeps task-cover.sh's contract | A numbered heading beyond 64 bits is ignored | cli/test/commit/task_cover_test.dart | an oversized heading leaves the report intact | red |
| task-commits → sw commit task-cover keeps task-cover.sh's contract | Task ids are ASCII digits | cli/test/commit/task_cover_test.dart | non-ASCII digits are not a task | green |
| change-finish → sw finish undo-archive-plan keeps finish.sh's contract | Unchanged finish evals pass on sw | .github/workflows/evals.yml | evals/finish on three OSes | red |
| change-finish → sw finish undo-archive-plan keeps finish.sh's contract | Output bytes equal the old script's | evals/finish | frozen-script comparison on parsed values | red |
| change-finish → sw finish undo-archive-plan keeps finish.sh's contract | Printed scripts still call vcs.sh by path | evals/finish | existing GitButler script case | green |
| change-finish → sw finish undo-archive-plan keeps finish.sh's contract | Usage error | evals/finish | existing usage case | green |
| change-finish → sw finish undo-archive-plan keeps finish.sh's contract | User-task ids are ASCII digits | evals/finish | existing ASCII digits case | green |

Test names in `cli/test` and `evals` that this table marks `green` are descriptions of existing cases. Task 1.1 replaces each with the exact name found at the refresh.

## 1. Refresh and dependencies

- [ ] 1.1 Verify A6 and refresh this plan after `native-cli-pr-pair-flow` merges: recheck every citation in `design.md`, the JSON and argument callers, the scanner's place in `cli/lib/src/pr/workflow.dart`, the version (this plan assumes pair-flow took 0.30.0), the notice file and the MODIFIED requirement text. Verify with a strict `openspec validate native-cli-library-foundations` and exact test names in the test map.
- [ ] 1.2 Verify A8 and add `crypto` and `path` to `cli/pubspec.yaml`: run `dart pub get`, then `mise exec -- dart test test/no_build_hooks_test.dart` from `cli/`, and confirm the test passes with the new lock file.
- [ ] 1.3 Carry C6: confirm ADR 0033 states that focused packages need approval and no build hooks, and that a port preserves workflow guarantees and not Python bytes. Verify by reading the accepted ADR.

## 2. JSON wrapper, integers and crypto

- [ ] 2.1 Verify A1, A2, A3 and A7: run the SDK on 100,000 nested levels, an integer beyond 64 bits and lone surrogate escapes, and compare `reviewerConfigBytes` with `JsonEncoder` output for values within 64 bits. Verify by recording the results in the group's test comments; a disproved assumption stops this group under the drift rule.
- [ ] 2.2 Write the failing tests for the red rows of "sw documents are compact JSON ending in one line feed", "JSON input that is not plain JSON is refused", "A group number beyond 64 bits is not a task", "A numbered heading beyond 64 bits is ignored" and "Line separators stay escaped". Verify each fails for the right reason.
- [ ] 2.3 Reduce `documentText` and `documentBytes` in `cli/lib/src/vcs/document.dart` to `JsonEncoder` and `encodeEscaped`, and add `decodeJson` and `readJsonFile` with the 32 MiB bound (D1, D2). Verify the document and deep-nesting rows turn green.
- [ ] 2.4 Move every JSON read onto the wrapper and delete `cli/lib/src/settings/pyjson.dart` and `cli/test/settings/pyjson_test.dart`. Verify with `grep` that no `pyjson` import remains and the non-finite, oversized-file and policy-integer rows turn green.
- [ ] 2.5 Stop integers beyond 64 bits where they enter (D8): `bad_setting` in `cli/lib/src/settings/rules.dart`, and `int` group numbers with ignored tasks, subjects, trailers and headings in `cli/lib/src/commit/task_cover.dart`. Verify the integer-setting and both task-cover rows turn green.
- [ ] 2.6 Replace the hand-written SHA-256 in `cli/lib/src/settings/reviewer_config.dart` with `crypto`. Verify "Reviewer config for ordinary values" still passes with a fixed digest from before the change.
- [ ] 2.7 Move stdout comparisons to parsed values in `evals/pr-pair/test_parity.py` (`assertParity`, lines 536 and 1084, `ReviewersParity.pair`), `evals/finish`, `evals/vcs` and the `task-cover` tests in `evals/git-workflow`, listing the `NaN` and abbreviated-option differences. Remove the retired cases from `cli/test/vcs/document_test.dart`. Verify in the PR's CI on three OSes and flip the eval rows green.
- [ ] 2.8 Carry C1, C3, C4 and C10: write the doc comments on `reviewerConfigBytes`, `documentBytes`, `decodeJson` and `readJsonFile`. Verify by reading each at its destination.
- [ ] 2.9 Carry C2 and C11: confirm the requirements "sw documents are compact JSON ending in one line feed" and "JSON input that is not plain JSON is refused" hold those facts after the refresh. Verify by reading the delta spec.

## 3. Option parsing

- [ ] 3.1 Verify A5: run `ArgParser` on a repeated single option, `--` as an option value and single-dash words. Verify by recording results in `cli/test/options_test.dart` comments; a disproved assumption stops this group under the drift rule.
- [ ] 3.2 Write `evals/cli/test_option_callers.py`, which scans shipped skills, scripts and `sw`'s own launches for option words and for text matching on documents, and add it to `evals/suites.json`. Verify with `python -m unittest evals/cli/test_option_callers.py` and the map test.
- [ ] 3.3 Write the failing tests for the red rows of "sw options follow one parsing rule". Verify each fails for the right reason.
- [ ] 3.4 Add `cli/lib/src/options.dart` (D3) and replace `parsePairArgs`, `_parseArgs`, the loop in `parseVcsArguments` and `_parseOptions`. Verify the option rows turn green and usage tests in `cli/test/vcs/args_test.dart`, `cli/test/pr/*` and `cli/test/commit/task_cover_test.dart` assert the stop and exit status.
- [ ] 3.5 Carry C7: write the doc comment on `parseVcsArguments`. Verify by reading it at its destination.

## 4. Paginated reads and the gh floor

- [ ] 4.1 Write the failing tests for "Paginated GitHub lists read every page or decide nothing", and make `evals/fakes/gh.py` emit one array of pages for `--slurp`, covered in `evals/pr-pair/test_fake_gh.py`. A6 was settled by task 1.1. Verify each test fails for the right reason.
- [ ] 4.2 Replace the page scanner in `cli/lib/src/pr/workflow.dart` `list` with `gh api --paginate --slurp` through the wrapper (D4). Verify the four list rows turn green.
- [ ] 4.3 Raise the `gh` floor to 2.48 in `cli/lib/src/fence/fence.dart`, `README.md`, `CONTRIBUTING.md`, `skills/specwright-pr/SKILL.md`, the `pr-pair.sh` prerequisite comment and `evals/git-workflow/test_instructions.py` lines 614, 625 and 628. Verify the "All prerequisites present" row in CI.
- [ ] 4.4 Carry C5: confirm the requirement "Paginated GitHub lists read every page or decide nothing" holds the rule after the refresh. Verify by reading the delta spec.

## 5. Paths

- [ ] 5.1 Verify A4: run `path` in `windows` style on mixed case, another drive and lone surrogates. Verify by recording results in `cli/test/vcs/raw_path_test.dart` comments; a disproved assumption stops this group under the drift rule.
- [ ] 5.2 Replace `PyPath` in `cli/lib/src/commit/task_cover.dart` and the relpath helpers in `cli/lib/src/vcs/walk.dart` with `path.Context` (D5), keeping the raw-path symlink call and the cross-drive error, and narrow the `relpathText` group to the relative path produced for each OS style. Verify with `mise exec -- dart test test/vcs/raw_path_test.dart` from `cli/`, with a cross-drive case.
- [ ] 5.3 Carry C8 and C9: write the doc comments on `realpath` and `relpathText`. Verify by reading each at its destination.

## 6. Notice, integration and release

- [ ] 6.1 Run the map test `python -m unittest evals/runner/test_suite_map.py` and add a rule to `evals/suites.json` for any new tracked file. Verify the test passes.
- [ ] 6.2 Add `crypto` and its closure to `cli/THIRD_PARTY_NOTICES.txt`, creating it if pair-flow did not (D6), and add the closure check to `cli/test/no_build_hooks_test.dart`. Verify the "Current dependency set" and "A dependency without a notice" rows turn green; re-confirm A8.
- [ ] 6.3 Confirm the full suites are green in the PR's `evals.yml` and `cli.yml` runs on Linux, Windows and macOS. Verify by the PR's checks.
- [ ] 6.4 Run `release.sh bump --to 0.31.0` and rewrite the summary of the proposal's `## Release Notes` to describe the whole release. Verify with `release.sh check` and `release.sh notes --proposal openspec/changes/native-cli-library-foundations/proposal.md`.
