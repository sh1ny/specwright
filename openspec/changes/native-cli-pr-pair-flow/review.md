# Review

## Metadata

- **Round:** 6 (full review after the owner-approved raw POSIX feedback environment amendment)
- **Prior round:** Round 5, APPROVE_WITH_CHANGES. Required Changes 1-7 were independently rechecked and marked applied. The D2 and C16 amendment voids that verdict.
- **Reviewer:** fresh-context Claude agent (`claude-opus-5-5`)
- **Recheck:** Round 6 Required Changes 1-10 only, by a Claude agent (`claude-opus-5-5`) in a new run. This is not a new round. Evidence is under Required Changes.
- **Reviewed:**
  - **Rules and artifacts:** `AGENTS.md`, `openspec/schemas/specwright/schema.yaml`, `templates/review.md`, and the change's `proposal.md`, `design.md`, `tasks.md`, `review.md` and all four delta specs
  - **Native code:** `pr/feedback_pass.dart`, `pr/feedback_record.dart`, `pr/feedback_record_files.dart`, `pr/context.dart`, `pr/pair.dart`, `pr/watch_state.dart:14-23`, `pr/workflow.dart:1-300, 800-830, 1386-1393`, `pr/settings_commands.dart:345-378`, `commands/pr.dart`, `commands/vcs.dart:40-103`, `settings/reviewer_config.dart:78-105, 120-208`, `vcs/codec.dart`, `vcs/document.dart` (searched), and the `fence/fence.dart` and `process/limits.dart` cited ranges
  - **Frozen script and shims:** every `pr-pair.sh` range cited in `design.md`, plus `:239-242`, `:966`, `:1909` and `:2245-2261`; `sw-path.sh`
  - **Tests and CI:** `cli/test/pr/feedback_pass_test.dart:30-99`, `cli/test/pr/feedback_record_test.dart:566-589`, `evals/pr-pair/test_workflow_records.py:1-75` and its test list, `evals/pr-pair/test_pr_pair.py` environment setup (searched), `evals/pr-pair/closing_bodies.py:1-42`, `evals/suites.json` (searched), `.github/workflows/evals.yml`, `cli.yml`, `sw-build.yml:1-70`, `mise.toml`, `cli/pubspec.yaml`
- **Verification limits:**
  - Nothing was edited, installed, built or run, and no Git mutation occurred. The Orca audit was not contacted.
  - `git ls-files` was not available, so tracked status rests on the supplied Git status. `feedback_pass.dart`, its test and `test_workflow_records.py` are untracked and were read at the owner's direction. `design.md` cites none of them.
  - Dart's `Platform.environment` behaviour, the Python `Path.home` passwd fallback and the group 6 test results come from the brief. They were not reproduced.
  - No raw environment reader exists yet, so this round reviews its design and its fit with the current code.
  - That APFS refuses non-UTF-8 names is outside knowledge. This repository cannot confirm it.

## Findings

### Critical (blocking)

None. The adapter is sound at its core:

- **Production reaches it.** `commands/pr.dart:73-78` builds `PrContext` with no environment, so the process branch is the production path.
- **Injection stays distinguishable.** `PrContext.environment` is nullable (`context.dart:90`).
- **The bytes round-trip.** `decodeEscaped` and `encodeEscaped` are inverses for these bytes (`codec.dart:16-20, 30-65`), and paths reach the filesystem through raw constructors (`feedback_record.dart:57`, `feedback_record_files.dart:46`).
- **No environment mutation exists.** `cli/lib` contains no `setenv`, `putenv` or `unsetenv`.

### Moderate

**M-1. "Existing resolver boundary" does not name one behaviour, although three exist.**

| Resolver | Behaviour with `HOME` unset | Evidence |
|---|---|---|
| Frozen `record_dir` | Passwd fallback through `Path.home()` | `pr-pair.sh:1909` |
| Native `_home` and `_directory` | Refuses | `reviewer_config.dart:83-99`, `feedback_pass.dart:141-154` |
| Native `stateBase` | Substitutes `/.cache/specwright` | `watch_state.dart:18-20` |

D2's sentence at `design.md:46` leaves an implementer to guess which one applies.

**Assessment: no further owner decision or passwd binding is needed while the refusal stands.** It fits the owner's "no new policy" limit for these reasons:

- Through the shim, unset `HOME` already aborts `sw-path.sh` under `set -u` (`:24, :60`) unless `SPECWRIGHT_HOME` is set (`:58`).
- Past that point, `context` calls `writeReviewerConfig` unconditionally (`settings_commands.dart:364`). `_home` runs outside its `try` (`reviewer_config.dart:167`), so the command stops with `internal_error` unless a state override exists. `SKILL.md:53-73` names `context` before the pass steps at `:102-104`.
- The remaining path is a direct `pass` call with `SPECWRIGHT_HOME` set, `HOME` unset and no override. A record the frozen script wrote under the passwd home then gets `internal_error`, exit 1. Nothing is lost or created, and setting `HOME` or the state directory recovers it.

The refusal does differ from the frozen outcome, so it must be recorded. Restoring passwd parity would be new ABI work needing separate owner approval.

**M-2. Workflow limits of a feedback-only reader are not carried (`schema.yaml:527-529`).**

Other commands still read `ctx.env`, backed by `Platform.environment` (`context.dart:106`):

- With a raw state value and a usable `HOME`, the workflow proceeds. `context` writes reviewer config under the default directory, which is harmless because that file is content-addressed.
- With a raw `HOME` and no override, `context` stops with `internal_error` before any pass, because the entry is omitted. D2's raw `HOME` path therefore helps direct pass calls, not the ordinary skill flow.

Both follow from the "no general retrofit" instruction. A future change could still mistake this for full raw-path support.

**M-3. The design does not say which root the first-seen read uses, and the current reuse creates a writer/reader split.**

- `_firstSeen` derives its root from `_directory` (`feedback_pass.dart:554`), so a raw-aware `_directory` silently changes it. The frozen script reads the same raw root (`pr-pair.sh:2248`), so that is the correct target.
- The native writer `stateBase` still uses the map (`watch_state.dart:17-20`). In a raw-state run, heads are written under the default directory and read from the raw one.
- When the push time is absent, the cutoff then falls from `first_seen` to `pass_written` (`pr-pair.sh:2257-2260`, `feedback_pass.dart:589-597`). A later cutoff can miss an existing re-request and report it as todo.
- The frozen read and the native snapshot writer already differ this way, so preserving it is acceptable. It must be stated and tested.

**M-4. Test scenarios do not reach all four process-environment branches.**

- D2 covers `HOME`, but the only raw scenario covers the state directory (`spec.md:122-124`, `tasks.md:38`).
- The owner requires that a state override works without home. The only existing check is injected (`feedback_pass_test.dart:50-55`), which cannot exercise `getenv` order.
- Missing-home refusal is tested only under Windows and only through injection (`feedback_pass_test.dart:74-80`).
- The harness can undermine these cases:
  - `NativePass.command` merges environments and cannot remove `HOME` (`test_workflow_records.py:26`).
  - It encodes arguments as strict UTF-8 (`:30`).
  - `pp` strictly decodes stdout (`:42`), while both implementations print raw path bytes (`pr-pair.sh:175, 241`, `document.dart:42-45`).
- The evals matrix includes `macos-latest` (`evals.yml:37`). Filesystem-dependent assertions need a visible capability check there.

The CI approach itself is right: evals build the shipped binary with the pinned SDK and require it (`evals.yml:139-152`).

**M-5. Task ordering and constraint tracking are incomplete.**

- Task 6.2 (`tasks.md:128`) introduces both the reader and its tests, while the schema requires the failing test first (`schema.yaml:677-678`). Task 6.1 (`tasks.md:127`) lists none of the environment cases.
- Task 8.4 (`tasks.md:142`) omits C16 from its destination check.

**M-6. The amendment does not meet the decision record rules.**

- The paragraph at `design.md:46` has no rejected alternative, reversal cost, importance or owner quote (`schema.yaml:326-343`). D2's `Chosen by` still quotes only the SDK decision (`design.md:44`).
- The summary row (`design.md:99`) is unchanged, contrary to `schema.yaml:365-370`.
- The Mechanism Ledger has no reader row, and Failure & Visibility has no directory-selection row (`schema.yaml:378-396`).

**M-7. Uncommitted group 6 moved the cited `commands/pr.dart` lines.**

| Location | Current citation | Actual lines |
|---|---|---|
| `design.md:10` | `12-31`, `59-97` | Handoff list `12-32`, dispatch `60-99` |
| `design.md:18` | `81-84`, `96` | The five commands are at `82-85` and `98`. Line `96` now reads `'item-issues' \|\|` |

No decision depends on the old positions, so this is not Critical.

### Suggestions

- **S-1.** Branch on `ctx.environment == null`, not `ctx.env`. `ctx.env` already substitutes `Platform.environment` (`context.dart:106`) and loses the signal C16 depends on.
- **S-2.** Have the reader return the state root and derive `/feedback` from it, instead of stripping a suffix at `feedback_pass.dart:554`.
- **S-3.** Directory resolution currently runs in the constructor (`feedback_pass.dart:130`, `workflow.dart:812-817`), before argument parsing. With no home, a malformed call gets exit 1 instead of usage exit 2, whereas the frozen script parses first (`pr-pair.sh:2515-2517`). Resolving lazily removes this difference.
- **S-4.** `feedback_record_test.dart:569-587` skips only Windows. If macOS CI refuses its raw directory, apply the probe from Required Change 3 there.

### Confirmed intact

- **Injected authority and credential isolation:** D2 and C16 keep raw values out of credential maps, and no process mutation is proposed.
- **Design citations:** every range other than M-7 supports its claim, including all `pr-pair.sh`, fence, VCS, limits, pair and corpus ranges.
- **Binding choices are unchanged:** product workflow over byte replica, html 0.15.7 raw-table interpretation, sidecar notices from 0.30, SDK-exclusive locks with legacy directories blocking, hard-link then exclusive fallback with explicit interruption recovery, no cross-FFI numeric branching and no umask change.
- **Network preflight:** `tokenFor` before the bounded segment (`workflow.dart:112-121`) matches `pr-pair.sh:324-325`.
- **Scope:** `ffi` is already a dependency (`pubspec.yaml:17`), and no package, handoff record or unrelated port is added. `cli/lib/src/pr/**` already routes to the suite map (`suites.json:33`).
- **Required Changes and owner decisions:** none reverses a `Chosen by: user` decision. Required Change 1 states the refusal D2 already implies.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. **`design.md:46`, D2 (M-1, M-3, M-6).** Replace "HOME-absent resolution remains the existing resolver boundary; this amendment does not authorize silently choosing a root cache or a new home-directory policy." with:

   > A state-directory override never consults home. With no nonempty state value and no usable home, feedback path selection refuses as `_home` does (`cli/lib/src/settings/reviewer_config.dart:83-99`): the command reports internal_error with exit 1, writes no record and chooses no substitute directory. POSIX has no passwd lookup for an unset `HOME`; this differs from the frozen `Path.home()` fallback (`skills/specwright-pr/scripts/pr-pair.sh:1909`), and adding one needs separate owner approval. The first-seen head read uses the same selected state root as the frozen script (`skills/specwright-pr/scripts/pr-pair.sh:2248`).

   Then append directly after that paragraph:

   > - **Rejected:** `Platform.environment` alone, which omits non-UTF-8 entries and would select a different default directory; a general environment retrofit; a new package; passwd ABI bindings for an unset `HOME`.
   > - **Reversal cost:** low
   > - **Important:** yes, changes where records are found and how a missing home is reported.
   > - **Chosen by:** user, "Preserve raw paths with the small adapter".

2. **`design.md:99`, D2 summary row (M-6).**
   - In the Choice cell, append: `; raw POSIX feedback environment reader, injected environments authoritative`.
   - In the Rejected cell, append: `; Platform.environment alone; general environment retrofit; passwd bindings`.

3. **`specs/pr-script-runtime/spec.md`, after line 128, and `tasks.md`, after line 39 (M-3, M-4).** Add these scenarios:

   > #### Scenario: Raw POSIX home keeps the record location
   > - **WHEN** a POSIX feedback call has no nonempty process state-directory value and a process `HOME` containing non-UTF-8 bytes
   > - **THEN** native and frozen calls find the same record location under that home
   >
   > #### Scenario: Process state override does not need a home
   > - **WHEN** a POSIX feedback call has a nonempty process state-directory value and `HOME` is unset
   > - **THEN** the record is located under the state directory and the call does not stop for a missing home
   >
   > #### Scenario: Missing home refuses without choosing a directory
   > - **WHEN** a POSIX process feedback call has a missing or empty state-directory value and `HOME` is unset or empty
   > - **THEN** it returns internal_error with exit 1, creates no record and uses no substitute directory
   >
   > #### Scenario: First-seen read follows the raw state directory
   > - **WHEN** a POSIX pass plan has a non-UTF-8 process state-directory value, a head record under it and no matching push activity
   > - **THEN** native and frozen plans report `cutoff_source` first_seen with the same cutoff

   Add these map rows:

   | Requirement | Scenario | Test file | Test name | State |
   |---|---|---|---|---|
   | pr-script-runtime - Feedback records interoperate across the port | Raw POSIX home keeps the record location | evals/pr-pair/test_workflow_records.py | WorkflowRecords.test_raw_posix_home_keeps_the_record_location | red |
   | pr-script-runtime - Feedback records interoperate across the port | Process state override does not need a home | evals/pr-pair/test_workflow_records.py | WorkflowRecords.test_process_state_override_does_not_need_a_home | red |
   | pr-script-runtime - Feedback records interoperate across the port | Missing home refuses without choosing a directory | evals/pr-pair/test_workflow_records.py | WorkflowRecords.test_missing_home_refuses_without_choosing_a_directory | red |
   | pr-script-runtime - Feedback records interoperate across the port | First-seen read follows the raw state directory | evals/pr-pair/test_workflow_records.py | WorkflowRecords.test_first_seen_read_follows_the_raw_state_directory | red |

4. **`tasks.md:127`, append to task 6.1 (M-4, M-5):**

   > Add failing POSIX child-process cases to `test_workflow_records.py` for every raw-environment, no-home and missing-home map row. Pass non-UTF-8 values only through the child's real environment, never through arguments or injected escaped strings, and build the no-`HOME` environment without that key. Decode child stdout with `surrogateescape`. Probe raw-path support with a bytes `os.mkdir`: on Linux the probe must succeed, a filesystem refusal elsewhere reports a skip naming the OS, and Windows reports a skip. Add the failing injected-precedence case to `cli/test/pr/feedback_pass_test.dart`: with the test process's own `HOME` present, an empty injected map refuses, and missing or empty injected state values do not use an ambient value. Verify each changed file red.

5. **`tasks.md:128`, task 6.2 (M-1, M-2, M-5).**
   - Replace "with actual raw-environment child-process coverage through the pinned SDK and injected-environment precedence checks" with "turning the raw-environment and injected-precedence rows from 6.1 green against the `sw` built by the pinned SDK".
   - Replace "Write C16 at its destination." with "Write C16 and C17 at their destination. After adding `feedback_environment.dart`, run the suite-map test."

6. **`tasks.md:142`, task 8.4 (M-5).** Change `C4/C5/C7/C8/C12/C13/C15` to `C4/C5/C7/C8/C12/C13/C15/C16/C17`.

7. **`design.md`, after line 127 (M-1, M-2, M-3).** Add:

   > - **C17:** The raw reader covers only feedback record paths and the first-seen head read. `context`'s reviewer-config writer and `stateBase` still read `Platform.environment`: with a non-UTF-8 state value they use the default directory, so a head written there is not found by pass plan, and with a non-UTF-8 or unset `HOME` and no override `context` stops with internal_error before a pass starts. An unset POSIX `HOME` has no passwd fallback, unlike the frozen script. Kind: deliberate gap. Destination: doc comment: cli/lib/src/pr/feedback_environment.dart feedbackDirectory.

8. **`design.md`, Failure & Visibility, after line 225 (M-6).** Add:

   | Component | Fails / dies mid-operation | Recovery | Retry safe? | Who finds out |
   |---|---|---|---|---|
   | Feedback directory selection | No usable state value or home, or the POSIX reader cannot be bound | Set `HOME` or `SPECWRIGHT_STATE_DIR` and rerun | Yes; nothing was written | Agent sees internal_error, exit 1 |

9. **`design.md`, Mechanism Ledger, after line 272 (M-6).** Add:

   | Mechanism | Built? | Concrete reason | Evidence that would change the call |
   |---|---|---|---|
   | POSIX feedback environment reader | yes | `Platform.environment` omits non-UTF-8 entries, so a raw state directory would silently select the default record location | Dart exposes raw environment bytes, or a later change owns a general environment boundary |

10. **Citations (M-7).**
    - At `design.md:10`, change `cli/lib/src/commands/pr.dart:12-31`, `59-97` to `cli/lib/src/commands/pr.dart:12-32`, `60-99`.
    - At `design.md:18`, change `cli/lib/src/commands/pr.dart:81-84`, `96` to `cli/lib/src/commands/pr.dart:82-85`, `98`.

### Reviewer resolution evidence

Line numbers below are current. The original positions in Required Changes 1-10 have shifted because of the edits themselves.

| # | Result | Evidence |
|---|---|---|
| 1 | Applied | `design.md:46` carries the replacement text and the old "existing resolver boundary" sentence is gone. It records the missing-`HOME` refusal, the difference from the frozen `Path.home()` fallback, no substitute directory and the first-seen state root. The four decision bullets are at `design.md:48-51`. |
| 2 | Applied | Both appended clauses are in the D2 row at `design.md:104`. The row has minor spacing differences around the separators (`fallback ; raw`, `authoritative\|`), which do not change the table or its meaning. |
| 3 | Applied | All four scenarios are at `specs/pr-script-runtime/spec.md:131-145`, within the requested requirement. All four map rows are at `tasks.md:91-94`, in state `red`, with the required file and test names. The rows sit at the end of the map instead of after line 39. The map is not ordered by requirement (for example `tasks.md:61, 80-82`), and the schema requires each scenario to be mapped, not a row position (`schema.yaml:613-615`). |
| 4 | Applied | The full required text is appended to task 6.1 at `tasks.md:131`, including real child environments, a no-`HOME` environment without the key, `surrogateescape` decoding, the bytes `os.mkdir` probe with its OS outcomes, and the injected-precedence case. |
| 5 | Applied | Task 6.2 at `tasks.md:132` has both replacements, and the replaced wording is gone. |
| 6 | Applied | Task 8.4 at `tasks.md:146` lists `C4/C5/C7/C8/C12/C13/C15/C16/C17`. |
| 7 | Applied | C17 at `design.md:133` directly follows C16, with the exact text, the feedback-only reader's writer and `context` limits, and the required destination. |
| 8 | Applied | The feedback directory selection row is at `design.md:232`, directly after the record publisher row. |
| 9 | Applied | The POSIX feedback environment reader row is at `design.md:280`, directly after the private filesystem primitive adapter row. |
| 10 | Applied | `design.md:10` cites `12-32`, `60-99`, and `design.md:18` cites `82-85`, `98`. These match the handoff list, dispatch and five settings/policy entries in `cli/lib/src/commands/pr.dart`. |

**Recheck limits:**

- This recheck read the artifacts and `commands/pr.dart` only. It ran no tests, builds or validators, so the strict validation pass is the coordinator's report and was not reproduced.
- The raw reader remains unimplemented. The new map rows are planned `red` tests, and nothing here claims they pass.
- No passwd binding or new package was adopted in the rechecked text. D2 rejects both, and C17 records the absent passwd fallback.
- This recheck added no new requirements. The earlier assessment that retained refusal needs no further owner decision is unchanged.

CHANGES_APPLIED: yes

## Rebuttals

None yet.