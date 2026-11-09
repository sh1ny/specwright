# Review

## Metadata

- **Round:** 5 (full review after the owner-approved SDK-exclusive file creation amendment)
- **Prior round:** Round 4, APPROVE_WITH_CHANGES, marked applied by the coordinator. The D2 amendment voids that verdict. This round checked all nine Required Changes independently.
- **Reviewer:** fresh-context Claude agent (`claude-opus-5-5`)
- **Recheck:** fresh-context Claude agent (`claude-opus-5-5`) rechecked only Required Changes 1-7. It is not a new round. See "Reviewer recheck of Required Changes" under Rebuttals.
- **Reviewed:**
  - **Rules and artifacts:** `AGENTS.md`, `schemas/specwright/schema.yaml`, `schemas/specwright/templates/review.md`, and the change's `proposal.md`, `design.md`, `tasks.md`, `review.md`, all three delta specs and `evidence/html-dependency-check.md`
  - **Baseline and ADRs:** `openspec/specs/feedback-passes/spec.md`, ADR 0031, the existence of ADR 0032, and lock references in `openspec/architecture.md`
  - **Frozen protocol:** `skills/specwright-pr/scripts/pr-pair.sh:1908-2043`, `2114-2186`, `2514-2562`, `3023-3033`, and every other range cited in `design.md`
  - **Native code:** `cli/lib/src/commands/pr.dart`, `pr/pair.dart`, `pr/context.dart:100-111, 218-229`, `commands/vcs.dart:1-105`, `fence/fence.dart` cited ranges, `process/limits.dart`, `vcs/codec.dart`, `settings/reviewer_config.dart:140-175`, `native/kernel32.dart` and `process/windows_tree.dart` `lastError` uses, `mise.toml`
  - **Tests:** `evals/pr-pair/test_pr_pair.py:2425-2558, 2628-2640, 2881-2991`, `evals/update/test_sw_install.py` notice and manifest cases, `evals/cli` notice test names, `cli/test/pr/closing_test.dart:47-48`
  - **Packaging:** `sw-build.yml`, `attach_release.py`, `update.sh` and `install-sw.sh` notice paths, `.gitattributes`
  - **Consumer text:** `skills/specwright-pr/SKILL.md:102, 123`
- **Verification limits:**
  - Nothing was edited, installed, run or built, and no Git mutation occurred. The Orca audit was not contacted.
  - The three untracked group 5 files were not opened and are not treated as implementation.
  - `git ls-files` was not available, so tracked status rests on the supplied Git status snapshot.
  - The SDK behaviour (exclusive create across 8 isolates, the different exception for a directory) and Dart issue 38832 come from the brief. SDK C++ source is not in this repository.
  - `openspec validate` was not run. M-1 is a character count against the schema's rule.
  - Group 4's test results come from the brief and the evidence file. They were not re-run.

## Findings

### Critical (blocking)

None. The approved design is safe at its core:

- Python's `os.mkdir` (`pr-pair.sh:2019`) refuses a native lock file as `record_busy`.
- SDK exclusive creation cannot overwrite an occupied path.
- Any failed hard link falls through to a creation that refuses occupancy, which gives the same outcome as `publish` (`:1933-1941`) without classifying the link error.
- `SKILL.md:102, 123` say only "a `.lock` is left" and "never remove a lock without the user", so no consumer assumes a directory.

### Moderate

**M-1. The amended requirement breaks strict validation and states several behaviours.**

- `specs/pr-script-runtime/spec.md:112` sits under `## ADDED Requirements` and its description is over 800 characters.
- `schema.yaml:201` limits a description to 500 characters and says `openspec validate --strict` fails above that. It also asks for one behaviour per requirement.
- Tasks 8.4 and 9.1 both depend on strict validation passing.
- The same text names an implementation choice ("SDK-exclusively"), which `schema.yaml:154` excludes from specs. D2 already owns that choice.

**M-2. Two scenarios assign the wrong error to `pass write` on an unreadable new-key record.**

- `pass_write` checks `path.exists()` and returns `record_exists` before reading the record (`pr-pair.sh:2127-2129`).
- Only `pass plan` (`:2318`), `adopt` (`:2541`) and `done` (`:2521`) reach `load_record` and return `record_unreadable`. `pass write` does so only for a sole unreadable legacy file, through `locate_record` (`:1984-1989`, `test_pr_pair.py:2510-2519`).
- "Interrupted SDK publication stays recoverable" (`spec.md:138-140`) and "Unreadable record blocks a new pass" (`:142-144`) both say otherwise. C8 says the same at `design.md:117`.
- The amendment makes this path more likely, so an implementer following the spec would diverge from the frozen workflow.

**M-3. A failed POSIX permission change after exclusive creation has no defined outcome.**

- D2 requires private permissions before content, and `File.createSync` takes no mode, so the fallback must create, set permissions, then write.
- D2, C8, the requirement and task 5.1 cover only open, write and close failures. A failed `chmod` would leave an empty file that blocks every later pass for that change.
- This is reachable. The fallback exists for filesystems without hard links, and those can also reject mode changes. Python's fallback never changed the mode (`:1941`), so this step is new.
- D2's rule implies failing closed, but the design must say so and test it.

**M-4. Rejected alternatives that a future change could reintroduce are not carried.**

- `schema.yaml:527-529` makes an uncarried rejected alternative a Moderate finding.
- C8 omits D2's rejection of numeric error branching across FFI calls. A public accessor already exists (`cli/lib/src/native/kernel32.dart:108`), so reintroducing it would be easy.
- Neither D2 nor C8 mentions the owner's rule against changing the global umask. C8 also omits the exists-then-create ban, which only D2 states.

**M-5. The baseline `feedback-passes` capability describes only a lock directory, and this change has no delta for it.**

- `openspec/specs/feedback-passes/spec.md:31-33` says "finds the record's lock directory already present". After the port, a native interrupted handover leaves a file, which that scenario does not cover.
- The proposal's Capabilities section (`proposal.md:25-29`) omits this capability, and a search of the change finds no mention of it.
- After archive, the main spec would misdescribe the state an operator finds. This only aligns the baseline with the approved decision and does not broaden scope.

**M-6. The test map does not reach the real script boundary for two scenarios.**

- "Native and legacy locks exclude each other" covers a legacy script call finding a native lock file, but it maps only to `cli/test/pr/feedback_record_test.dart` (`tasks.md:41`). A Dart directory call cannot prove what Python's `os.mkdir` does (`schema.yaml:619-621`).
- "Interrupted SDK publication stays recoverable" needs the command-level error codes from M-2, and only a store-level Dart test maps to it (`tasks.md:42`).

**M-7. Failure visibility omits process death during the fallback.**

- The "Record publisher" row (`design.md:220`) lists `record_exists` and `internal_error`. It does not cover a process dying between creation and the end of the write, or `record_unreadable`.
- The T2 diagram has no path from `Absent` to `Refused` for that case (`design.md:150, 156`). `schema.yaml:378-381` requires this per component.

**M-8. Group 4 moved the `commands/pr.dart` lines the design cites.**

- `design.md:10` cites `12-26` and `54-87`, and `design.md:18` cites `76-79` and `86`.
- Handoff commands now span `12-31` and dispatch `59-97`. The five commands are at `81-84` and `96`, while line `86` now reads `'ensure-pr' ||`.
- `schema.yaml:521-524` makes a moved citation a finding. No decision depends on the old position, so it is not Critical.

### Suggestions

- **S-1.** In task 5.1, treat the SDK's path-exists exception as busy without a follow-up check. Use the post-failure check, without following links, only for other exception types. Otherwise a holder releasing between the failed create and the check can produce a spurious `internal_error` in the concurrent tests.
- **S-2.** `File.fromRawPath` supports the raw-path requirement, and `rawFile` already provides it (`pr/context.dart:223`). The state directory, however, arrives as a Dart string from `Platform.environment` (`:105-106`), whereas Python's `record_dir` reads `os.environ` (`pr-pair.sh:1909`). Whether non-UTF-8 environment bytes survive was not verified. Task 5.1's raw-path check should start from that same environment input, not only from a prebuilt escaped string.

### Confirmed intact

- **Round 4 Required Changes 1-9, independently verified:**

| # | Evidence |
|---|---|
| 1 | D7 version gate at `design.md:82`; `sw-build.yml:71-79`; `.gitattributes:7` |
| 2 | D7 placement order at `design.md:82`; `update.sh:3177-3195, 3280-3295` |
| 3 | `specs/native-cli/spec.md:4, 15, 30, 60, 74-84` |
| 4 | `design.md:190-194, 207, 219, 236, 247, 270` |
| 5 | `design.md:285`; `proposal.md:33`; ADR 0032 exists |
| 6 | Task 4.5 text; fixture tag selection in `TestNotices` |
| 7 | Map at `tasks.md:5, 9-77`; duplicate-name variant at `test_sw_install.py:487`; old-manifest case at `:497-501` |
| 8 | D7, task 4.4 and C14 text; evidence lists all eight runtime packages plus the Dart SDK |
| 9 | Tasks 8.1, 8.2 and 8.5 text |

- **Round 4 suggestions:** the raw-table test now asserts `o/r#1` (`closing_test.dart:47-48`), and the `update.sh` wording was updated (`:3080`, `:3270`).
- **Round 4 open item:** `MAX_PAGES = 50` (`bounded.py:62`) confirms the 50-page figure at `design.md:227`.
- **Design citations:** apart from M-8, every cited range supports its claim.
- **Coherence:**
  - D2, its summary row, State & Ownership, the Mechanism Ledger, Resource Bounds and Flow gaps agree on the approved design.
  - ADR 0031 stays unedited. Task 5.2 records the refinement additively.
  - The record key, version 2, legacy byte handling and `lock_left` boundary are preserved (`pr-pair.sh:1916-1927, 1979, 1995, 3028-3033`).
- **Task order:** primitives in group 5, pass operations in group 6 and final shim, Python 3.8 and source-extraction checks in 8.1, 8.2 and 8.5 are correctly sequenced. Local verification stays within named test files and modules.
- **Scope:** no new package, unrelated port or product feature is added. None of the Required Changes reverses a `Chosen by: user` decision.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. **`specs/pr-script-runtime/spec.md`, split the requirement (M-1, M-2, M-3).**
   - Replace the description at line 112 with:

     > Native pass operations SHALL preserve record keys, version-2 JSON, LF encoding, ownership, legacy migration and exclusive publication. Interrupted or foreign-owned state SHALL retain the existing recovery result; the port SHALL NOT start a new pass beside an unreadable record or silently adopt another owner.

   - Replace the THEN of "Unreadable record blocks a new pass", and change its WHEN to say "a new-key record or a sole matching legacy record":

     > **THEN** `pass plan`, `pass adopt` and `pass done` return record_unreadable; `pass write` returns record_unreadable for a sole legacy record and record_exists for a new-key record; and the file is left in place

   - Add this requirement after that block, and move "Concurrent mutations acquire one lock", "Native and legacy locks exclude each other" and "Interrupted SDK publication stays recoverable" under it:

     > ### Requirement: Feedback record locks and fallback publication stay exclusive
     > Write SHALL publish exclusively; adopt and done SHALL hold their own record lock and never remove another call's lock. Native locks SHALL be exclusively created files at the existing `.lock` path; legacy lock directories SHALL still block and SHALL never be removed automatically. A failed hard link MAY fall back to exclusive creation that refuses an occupied destination. An ordinary failure after that creation SHALL remove only the file the request created.

   - Replace the THEN of "Interrupted SDK publication stays recoverable" with:

     > **THEN** the empty or partial record remains in place, `pass write` refuses with record_exists, and `pass plan`, `pass adopt` and `pass done` return record_unreadable

   - Add this scenario to the new requirement:

     > #### Scenario: Fallback permission failure leaves no record
     > - **WHEN** the publication fallback exclusively creates a POSIX record and setting its private permissions fails
     > - **THEN** the error is reported, no record content was written, only the created file is removed, and a later `pass write` can create the record

   - In `tasks.md:40-42`, change the requirement column of the three moved scenarios to the new requirement, and add this row:

     | Requirement | Scenario | Test file | Test name | State |
     |---|---|---|---|---|
     | pr-script-runtime - Feedback record locks and fallback publication stay exclusive | Fallback permission failure leaves no record | cli/test/pr/feedback_record_test.dart | fallback permission failure leaves no record | red |

2. **Permission failure (M-3).**
   - In D2 (`design.md:40`), replace "ordinary open/write/close failures remove only the file this request created." with:

     > Set private POSIX permissions on a created file through the minimal adapter before opening it for content, and never change the process umask. Ordinary failures after exclusive creation, including a failed permission change or an open, write or close failure, remove only the file this request created and report a generic filesystem error; a failed permission change writes no content.

   - In C8 (`design.md:117`), replace "Interruption can leave an empty or partial record, which is refused as unreadable, never treated as absent or silently replaced. Ordinary open/write/close failure cleans up only the request-created file." with:

     > Interruption can leave an empty or partial record: `pass write` refuses it as record_exists, the other pass operations as record_unreadable, and it is never treated as absent or silently replaced. An ordinary permission, open, write or close failure cleans up only the request-created file.

   - In task 5.1, after "exclusive-create open/write/close cleanup", add "and permission-failure cleanup through an injected adapter failure".

3. **Failure visibility (M-7).**
   - In the Failure & Visibility "Record publisher" row, replace the failure, recovery and visibility cells with: "Concurrent write, failed publication, or death during the SDK fallback", "Exclusive refusal; cleanup own incomplete fallback/temp file on ordinary failure; a record left by death stays for explicit recovery", and "Agent sees record_exists, record_unreadable or internal_error".
   - Add this edge to the T2 diagram: `Absent --> Refused: interrupted fallback leaves empty or partial record`.

4. **Carried constraint (M-4).** Add to `## Carried constraints`:

   > - **C15:** The feedback record store classifies outcomes from SDK exceptions, post-failure occupancy and one-call OS success results. Numeric `errno` or `GetLastError` branching across FFI calls (dart-lang/sdk#38832), exists-then-create exclusivity and process-wide umask changes stay rejected. Kind: rejected alternative. Destination: doc comment: cli/lib/src/pr/feedback_record.dart FeedbackRecordStore.

   In task 5.2, change "Write C8 at its destination" to "Write C8 and C15 at their destination". In task 8.4, add C15 to the code-comment list.

5. **`feedback-passes` delta (M-5).**
   - Add `specs/feedback-passes/spec.md` with `## MODIFIED Requirements`, containing the whole block from baseline lines 8-41 with one change. The WHEN at line 32 becomes:

     > **WHEN** a handover or removal finds the record's `.lock` path already occupied, by a native lock file or a legacy lock directory

   - Add to `proposal.md` Modified Capabilities:

     > - `feedback-passes`: an occupied `.lock` path may be a native lock file or a legacy lock directory; both remain `record_busy` and are never removed automatically.

   - At `tasks.md:5`, change "all three deltas" to "all four deltas", and add these rows:

     | Requirement | Scenario | Test file | Test name | State |
     |---|---|---|---|---|
     | feedback-passes - A feedback pass has one owner | Two sessions start a pass for one change | evals/pr-pair/test_workflow_records.py | WorkflowRecords.test_concurrent_writers_publish_one_record | red |
     | feedback-passes - A feedback pass has one owner | Resume by the owning session | evals/pr-pair/test_pr_pair.py | PassOwnership.test_pass_owner_plans_and_completes | green |
     | feedback-passes - A feedback pass has one owner | Record left by another session | evals/pr-pair/test_pr_pair.py | PassOwnership.test_pass_plan_reports_foreign_owner | green |
     | feedback-passes - A feedback pass has one owner | User confirms the owner is gone | evals/pr-pair/test_pr_pair.py | PassOwnership.test_pass_adopt_hands_over_the_record | green |
     | feedback-passes - A feedback pass has one owner | Handover races another session | evals/pr-pair/test_pr_pair.py | PassOwnership.test_pass_adopt_refuses_a_stale_from | green |
     | feedback-passes - A feedback pass has one owner | Lock left by an interrupted handover | cli/test/pr/feedback_record_test.dart | native and legacy locks exclude each other | red |
     | feedback-passes - A feedback pass has one owner | Record write fails while it is created | cli/test/pr/feedback_record_test.dart | fallback write failure leaves no record | red |
     | feedback-passes - A feedback pass has one owner | Removal by a non-owner | evals/pr-pair/test_pr_pair.py | PassOwnership.test_pass_done_refuses_a_non_owner | green |

   - Append to task 8.2: "Rerun the green `PassOwnership` rows through the native shim."

6. **Real boundary rows (M-6).**
   - Add these rows to the test map:

     | Requirement | Scenario | Test file | Test name | State |
     |---|---|---|---|---|
     | pr-script-runtime - Feedback record locks and fallback publication stay exclusive | Native and legacy locks exclude each other | evals/pr-pair/test_workflow_records.py | WorkflowRecords.test_frozen_script_refuses_a_native_lock_file | red |
     | pr-script-runtime - Feedback record locks and fallback publication stay exclusive | Interrupted SDK publication stays recoverable | evals/pr-pair/test_workflow_records.py | WorkflowRecords.test_interrupted_record_is_refused_by_each_pass_operation | red |

   - Append to task 6.1: "Run the frozen script's adopt and done against a regular file at the `.lock` path, expecting record_busy with the file unchanged. Run all four native pass operations against empty and partial new-key records, expecting the codes in the interrupted-publication scenario."

7. **Citations (M-8).**
   - At `design.md:10`, change `cli/lib/src/commands/pr.dart:12-26`, `54-87` to `cli/lib/src/commands/pr.dart:12-31`, `59-97`.
   - At `design.md:18`, change `cli/lib/src/commands/pr.dart:76-79`, `86` to `cli/lib/src/commands/pr.dart:81-84`, `96`.

CHANGES_APPLIED: yes

## Rebuttals

Coordinator application of Required Changes, awaiting reviewer recheck:

1. Split the long description into record interoperability and exclusive lock/publication requirements. Moved the three scenarios, corrected per-operation interrupted/unreadable codes, added permission failure and its map row. Strict validation passes.
2. D2 and C8 now cover permission failure before content, cleanup of only the created file and no global umask change; task 5.1 includes injected permission failure.
3. The state diagram and record-publisher failure row now show death during fallback and explicit recovery.
4. C15 records the rejected cross-FFI numeric error branching, exists-then-create exclusivity and process-wide umask change. Tasks 5.2 and 8.4 carry its destination.
5. Added the full owned baseline requirement as the feedback-passes delta, changing only the held-lock trigger. Proposal, all-four-delta map and task 8.2 cover it.
6. Added both real-boundary group 6 map rows and task 6.1 checks against the frozen script and all four native pass operations.
7. Updated the moved commands/pr.dart citation ranges.

Suggestions S-1 and S-2 were passed to the fresh implementation worker: SDK path-exists exceptions classify occupied paths directly; other post-failure checks preserve raw paths, with environment-path coverage to be checked rather than assumed.

### Reviewer recheck of Required Changes

Rechecked by a fresh-context Claude agent (`claude-opus-5-5`). Only Required Changes 1-7 were in scope. Each item was compared with the current files and is resolved as written. Line numbers refer to the current files.

| # | Resolved by | Reviewer-verified evidence |
|---|---|---|
| 1 | M-1, M-2, M-3 | The description is replaced at `specs/pr-script-runtime/spec.md:112`. The "Unreadable record blocks a new pass" WHEN and THEN are at `:131-132`. The new requirement, within the 500-character limit, is at `:134-135`. The three moved scenarios appear once each, at `:137-147`, with the Interrupted THEN at `:147`. The permission scenario is at `:149-151`. The requirement column is updated at `tasks.md:40-42`, and the new row is at `tasks.md:78`. |
| 2 | M-3 | The D2 replacement is at `design.md:40`, the C8 replacement at `design.md:117`, and the task 5.1 addition at `tasks.md:120`. |
| 3 | M-7 | The three "Record publisher" cells match at `design.md:222`, with the retry cell unchanged. The T2 edge is at `design.md:152`. |
| 4 | M-4 | C15 matches at `design.md:124`. Task 5.2 carries it at `tasks.md:121` and task 8.4 at `tasks.md:140`. |
| 5 | M-5 | `specs/feedback-passes/spec.md:1-36` has `## MODIFIED Requirements` and the entire block from baseline `openspec/specs/feedback-passes/spec.md:8-41`. The only difference is the required WHEN at delta line 27, which replaces baseline line 32. The proposal entry is at `proposal.md:30`. "All four deltas" is at `tasks.md:5`, all eight rows are at `tasks.md:81-88`, and the task 8.2 sentence is at `tasks.md:138`. The five green rows name existing tests at `evals/pr-pair/test_pr_pair.py:2583, 2599, 2609, 2622, 2642`, in `PassOwnership` (`:2378`). |
| 6 | M-6 | Both rows are at `tasks.md:79-80`, and the task 6.1 sentences are at `tasks.md:125`. |
| 7 | M-8 | The citations are updated at `design.md:10` and `design.md:18`. They match `cli/lib/src/commands/pr.dart`: handoff list `12-31`, dispatch `59-97`, native commands `81-84` and `96`. |

Recheck limits:

- Nothing was edited, installed, run or built, and no Git mutation occurred. The Orca audit was not contacted.
- The strict validation pass is the coordinator's report and was not re-run here.
- The new red rows stay red until their assigned groups are implemented. This recheck does not claim they pass.
- The green rows' results and group 4's verification and commit come from the existing record and the brief. They were not re-run.
- The untracked group 5 files were not opened and are not delivered implementation.
- S-1 and S-2, including the environment raw-path input, remain with the fresh implementation worker and are not resolved by this recheck.
- `design.md:40` has a capital "Set" after a semicolon. That comes from applying the required text literally, and it is cosmetic.