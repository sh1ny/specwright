**All four Required Changes are correctly applied, so I set `CHANGES_APPLIED: yes`.** I edited nothing, so the updated document below still needs to be written to `review.md`. Group 8 and task 9 are still recorded as pending.

---

# Review

## Metadata

- **Round:** 7 (full review after the final shim switch and historical citation amendment)
- **Prior round:** Round 6, APPROVE_WITH_CHANGES. Required Changes 1-10 were rechecked and marked applied. The later edits to `design.md` void that verdict.
- **Reviewer:** fresh-context Claude agent (`claude-opus-5-5`)
- **Recheck:** Round 7 Required Changes 1-4 only, by a separate read-only `claude-opus-5-5` run. This is not a new full round. The findings, verdict and Required Changes below are preserved as written in round 7, and the recheck adds only this bullet, the Resolution evidence and the `CHANGES_APPLIED` value.
- **Reviewed:**
  - **Rules and artifacts:** `AGENTS.md`, `openspec/schemas/specwright/schema.yaml`, `openspec/schemas/specwright/templates/review.md`, `.claude/skills/specwright-review/SKILL.md`, and the change's `proposal.md`, `design.md`, `tasks.md` and `review.md`. The `pr-script-runtime`, `github-identity` and `feedback-passes` deltas were read in full. For `native-cli`, the requirement and scenario list and `spec.md:41-48` were read.
  - **ADRs:** `docs/adr/0031-direct-native-workflow-calls-and-project-selection.md`, `docs/adr/0032-third-party-notices-accompany-sw.md`
  - **Native code:** `commands/pr.dart`; `commands/vcs.dart:1-135`; `pr/pair.dart:1-115`; `fence/fence.dart:15-44, 145-164, 428-578`; `process/limits.dart:1-79`; `settings/reviewer_config.dart:78-107`; `vcs/scripts.dart:28-167`; `vcs/git_common.dart:100-123`; `vcs/plan.dart:22-47`; `pr/workflow.dart:28-62, 838-867, 932-1066, 1720-1728`; `pr/feedback_environment.dart`; and the carried-constraint comments in `feedback_record.dart`, `workflow_transport.dart` and `closing.dart`
  - **Shims and oracle:** `skills/specwright-pr/scripts/{pr-pair.sh,as.sh,sw-path.sh}`, `pr-snapshot.sh:80-95`, `pr-reply.sh:46-61`, and every design-cited range of `evals/pr-pair/oracle/pr-pair.sh`, with enough surrounding lines to locate the code each claim describes
  - **Consumers and tests:** store-selector text in `skills/specwright-pr/SKILL.md` and `skills/specwright-finish/SKILL.md`; `evals/pr-pair/closing_bodies.py:1-45`; test names in `test_pr_shims.py`, `test_project_shims.py` and `test_workflow_records.py`; the C13 comment in `test_workflow_parity.py`
  - **Notices:** `evidence/html-dependency-check.md`, `cli/pubspec.yaml`, `cli/pubspec.lock`, `mise.toml`, and `cli/THIRD_PARTY_NOTICES.txt`
- **Verification limits:**
  - Nothing was edited, installed, built or run, and no Git command or mutation occurred. The Orca audit was not contacted.
  - Only file read and search tools were available. Tracked status for each file `design.md` cites came from searching `.git/index` for those paths. The other files read are covered by the supplied Git status, which listed no untracked files.
  - The pre-port production script is not in the working tree, and history could not be read. The corrected oracle ranges below come from matching each claim to the oracle's actual code, not from a diff.
  - Group 8 tests were not run. The red map rows are treated as planned work. Named tests were confirmed to exist, but their assertions and results were not reviewed. Task 9 has not been performed.
  - `openspec/architecture.md` and in-force ADRs other than 0031 and 0032 were not reopened, because the request scoped the ADR reading to those two.
  - The notice file was checked through its section headings, copyright lines and tail, not compared word for word. The pub cache and `.dart_tool` are untracked and were not opened, and no upstream source was reachable. The transitive package closure, the licence texts, the SDK scan results and the DEPS revisions in the evidence are therefore not independently reproduced. This is not a legal opinion, and the test results recorded in that evidence are not certified here.

## Findings

### Critical (blocking)

None. The claims behind the bad citations hold once the ranges are corrected, so no decision or task rests on a contradicted claim.

### Moderate

**M-1. The historical citation amendment is wrong: every oracle range points 35 lines too late (`schema.yaml:514-524`).**

The brief and amendment state that the oracle has the same frozen line ranges as the former production script. It does not. The oracle is a separate, older copy, frozen "before native-cli-pr-pair" (`evals/pr-pair/oracle/pr-pair.sh:2`), and it ends at line 2999 (`:2999`). All 15 `design.md` lines naming the oracle carry shifted ranges:

| Design citation | Claim | What the cited oracle range holds | Where the code is |
|---|---|---|---|
| `design.md:7, 18` `3017-3021` | Pre-port dispatch | Past end of file | `2982-2986` |
| `design.md:24` `3027-3034` | `lock_left` boundary | Past end of file | `2992-2998` |
| `design.md:11` `2996-3014` | Paged issue read | Exception handler, then past end of file | `2961-2979` |
| `design.md:10, 26` `2743-2766` | Merge and read-back | `reply_message`, `policy_gh` | `2708-2731` |
| `design.md:22, 239` `256-267` | `net` limit behaviour | `started_in`, `toplevel_path` | `221-232` |
| `design.md:24` `1916-1927` | Feedback keys | `publish` tail, `exists_here` | `1881-1892` |
| `design.md:46` `1909` | `Path.home()` fallback | `os.fdopen` in `publish` | `1874` |

A constant offset of 35 fits every cited range, as listed in Required Change 1. The consequence is concrete. Future planners and the apply and pre-ship audits open these citations against the file that remains. Three ranges run past its end, and the others show unrelated code.

**M-2. "Before this port, the five settings/policy commands dispatched natively" has no supporting citation (`design.md:18`).**

The sentence is followed by the oracle's dispatch, labelled pre-port. That table lists all nineteen commands in Python (`oracle/pr-pair.sh:2982-2986`), because the oracle predates the five-command port. It cannot show the claim. The claim is true and has a tracked citation: `cli/lib/src/pr/pair.dart:4-5` names the five subcommands that moved to `sw pr`.

**M-3. The corrected runtime inventory creates an SDK-pin invariant that nothing durable carries (`schema.yaml:527-529`).**

- The sidecar now holds notices tied to the pinned SDK's runtime: BoringSSL, ICU, zlib, double-conversion, V8-derived code and BigInt (`THIRD_PARTY_NOTICES.txt:292-1155`).
- The evidence says "Dependency/SDK or build-flag changes require another inventory" (`evidence/html-dependency-check.md:52`). Its line 58 attributes the SDK trigger to ADR 0032 and C14.
- C14 and ADR 0032 name only "the compiled dependency set" and "Dependency changes" (`design.md:130`, `0032:19, 23`). The Mechanism Ledger trigger has the same gap (`design.md:283`).

A routine bump of `dart = "3.13.7"` (`mise.toml:2`) can therefore ship stale runtime attribution while checksums still pass. ADR 0032 is accepted and stays unchanged, so the fact needs its own entry at the pin.

### Suggestions

- **S-1.** ADR 0031's evidence still cites the production `pr-pair.sh:2574-2603` and `2700-2713` (`0031:31-32`), and that file is now 195 lines. The ADR labels these locations pre-port and must not be edited. For a future reader, the oracle equivalents are `2539-2568` and `2665-2678`.
- **S-2.** `pr-pair.sh:132-135` still exports `PR_PAIR_BASH`, and the comments at `:132` and `:136` refer to Python that is gone. Outside the oracle, the only non-archive reference to that variable is this script. Group 8 could drop the export and comments.
- **S-3.** The snapshot/reply limitation is at its durable destination (`0031:33`, `SKILL.md:75`), but it has no `## Carried constraints` entry. No consequence follows today. Note that "S-1" there is unrelated to the proposal's scope decision S1.

### Confirmed intact

- **Current Dart citations:** the refreshed `commands/pr.dart` and `commands/vcs.dart` ranges support their claims, as do the `pair.dart`, `fence.dart`, `limits.dart`, `reviewer_config.dart` and `closing_bodies.py` ranges.
- **Shim coherence with D4 and the specs:**
  - The Python probe comes first (`pr-pair.sh:126-130`).
  - Selector parsing refuses a missing, empty or repeated value (`:150-160`).
  - Resolution comes before usage, with no fallback (`:177-182`).
  - All nineteen commands dispatch, and invalid calls keep their records through `pair` (`:184-194`, `commands/pr.dart:84-88`).
  - A relative selector resolves from the unchanged cwd (`sw-path.sh:48`). `as.sh:22-54` matches.
- **C11:** `fencePrefix` is empty unless `branchFetchProject` is set (`scripts.dart:36-38`, `vcs.dart:59`). The only caller setting it is fetch-main (`workflow.dart:854`). Cleanup's jj store pull prints `vcs.sh` without a selector (`workflow.dart:1054-1061`, `plan.dart:29-41`), so `networkGit` keeps the unselected hop (`git_common.dart:111-114`).
- **D5:** both `as.sh` calls in the retained hop carry the prefix (`scripts.dart:136-139, 166`). "Sole" exception is accurate for workflow-initiated calls, because the other workflow VCS use is state and plan.
- **S-1 limit:** `pr-snapshot.sh:85-88` and `pr-reply.sh:51-54` still resolve from cwd. `SKILL.md:75` states the limit and does not claim a fix.
- **C17:** `feedbackDirectory` covers records and the first-seen read (`feedback_environment.dart:47-78`, `feedback_pass.dart:138, 540`). `stateBase` and `ctx.env` still use the map (`watch_state.dart:16`, `context.dart:106`). The limit is documented at `feedback_environment.dart:41-46`.
- **C1-C17 destinations:** C1, C6, C9, C10 and C11 are in ADR 0031, and C14 is in ADR 0032. C2 and C3 name existing requirements. C4, C5, C7, C8, C12, C13, C15, C16 and C17 are present at their named symbols. Task 8.4's confirmation remains planned.
- **Notice inventory:** the eight listed packages appear in the lockfile at the listed versions, and the html archive hash matches (`pubspec.lock:136`). The sidecar has a section for every package and runtime component in the evidence, and ADRs 0031 and 0032 are unchanged in substance by this amendment.
- **Owner decisions:** the HTML5 interpretation, html package, SDK-exclusive locks and publication, and POSIX environment adapter are unchanged. No Required Change reverses a `Chosen by: user` decision. C18 records a fact that the approved sidecar choice already implies.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. **`design.md`, oracle citations (M-1).** Keep the path `evals/pr-pair/oracle/pr-pair.sh` and replace only these ranges:

   | Line | Replace | With |
   |---|---|---|
   | 7 | `3017-3021`, `2634-2676` | `2982-2986`, `2599-2641` |
   | 8 | `2160-2186` | `2125-2151` |
   | 9 | `1930-1955`, `2013-2030` | `1895-1920`, `1978-1995` |
   | 10 | `2743-2766` | `2708-2731` |
   | 11 | `2996-3014` | `2961-2979` |
   | 12 | `357-371`, `2954-2984` | `322-336`, `2919-2949` |
   | 22 | `309-328`, `256-267`, `245-254` | `274-293`, `221-232`, `210-219` |
   | 24 | `1916-1927`, `1968-2002`, `2172-2186`, `2534-2562`, `2013-2030`, `3027-3034`, `2315-2359`, `2498-2507` | `1881-1892`, `1933-1967`, `2137-2151`, `2499-2527`, `1978-1995`, `2992-2998`, `2280-2324`, `2463-2472` |
   | 26 | `1436-1492`, `2743-2766`, `2679-2728` | `1401-1457`, `2708-2731`, `2644-2693` |
   | 40 | `2037-2043`, `1979`, `1995` | `2002-2008`, `1944`, `1960` |
   | 46 | `1909`, `2248` | `1874`, `2213` |
   | 239 | `256-267`, `2285-2312` | `221-232`, `2250-2277` |
   | 265 | `325-328`, `1888-1896` | `290-293`, `1853-1861` |
   | 266 | `2641-2646`, `2650-2658`, `2667-2675` | `2606-2611`, `2615-2623`, `2632-2640` |

2. **`design.md:18` (M-1, M-2).** Replace the sentences "Before this port, the five settings/policy commands dispatched natively and the other commands remained in Python. The frozen pre-port dispatch is at `evals/pr-pair/oracle/pr-pair.sh:3017-3021`." with:

   > Before this port, the five settings/policy commands dispatched natively (`cli/lib/src/pr/pair.dart:4-5`) and the other commands remained in Python. The oracle was frozen before `native-cli-pr-pair` (`evals/pr-pair/oracle/pr-pair.sh:2`), so its dispatch table lists all nineteen commands in Python (`evals/pr-pair/oracle/pr-pair.sh:2982-2986`).

3. **`design.md`, after line 133 (M-3).** Add:

   > - **C18:** The third-party notice also covers the Dart runtime embedded by `dart compile exe`, inventoried for the pinned SDK and its default desktop build. Changing the SDK pin or build flags requires a new runtime notice inventory; binary hashes cannot detect stale attribution. Kind: invariant. Destination: doc comment: mise.toml tools.dart.

4. **`tasks.md:154`, append to task 9.1 (M-3):**

   > Write C18 as a comment on the `dart` pin in `mise.toml`, and verify the comment is present there.

### Resolution evidence (recheck of Required Changes 1-4)

**Scope of this evidence:** files were read directly, and nothing was run. The coordinator reports that strict validation passes, but this recheck did not reproduce that. Without Git history, the recheck cannot show that these were the only edits made to `design.md` since round 7. Group 8 and task 9 remain unexecuted, and their checkboxes are still unticked (`tasks.md:145-150, 154-155`).

**1. Applied (M-1).** All 14 table rows match the current `design.md`, value for value. The C18 insertion moved the last three rows down one line, so rows 239, 265 and 266 are now `design.md:240, 266, 267`. A search of `design.md` for every replaced value finds only `1995`, at lines 9 and 24, and both are the end of the required new range `1978-1995`. `design.md` has 15 lines citing `pr-pair.sh:<n>`, matching M-1's count. The oracle has 2999 lines, so no cited range runs past its end. Each range was read in the oracle and supports its claim:

| Design line | Oracle range | Code found |
|---|---|---|
| 7, 18 | `2982-2986` | `COMMANDS` table, nineteen entries |
| 7 | `2599-2641` | `vcs_sh`, `vcs_plan`, `vcs_json`, `vcs_state`, `vcs_branch` |
| 8 | `2125-2151` | Heads, marker and owner in the record. The first line, 2125, is the tail of the preceding `misrouted` stop, which is harmless. |
| 9 | `1895-1920`, `1978-1995` | `publish`; `record_lock` |
| 10, 26 | `2708-2731` | One merge PUT, then read-back and decision |
| 11 | `2961-2979` | Paged issue read and lowest-number marker index |
| 12 | `322-336`, `2919-2949` | `token_for`; `cmd_delete_remote` guards and delete. The final `kept` stop at 2950 is just outside the range and does not affect the claim. |
| 22 | `274-293`, `221-232`, `210-219` | `git_net`; `net` with `limit_ok`; plain `run` and `git` |
| 24 | `1881-1892`, `1933-1967` | Record keys; `locate_record` migration |
| 24 | `2137-2151`, `2499-2527` | Sibling temporary file and exclusive publish; `pass_adopt` lock and `os.replace` |
| 24 | `2992-2998`, `2280-2324`, `2463-2472` | `lock_left` boundary; `pass_plan` opening through the partial-edit comment at 2323; completion result |
| 26 | `1401-1457`, `2644-2693` | `RenderedLines` and `rendered_lines`; `cmd_cleanup` returning commands |
| 40 | `2002-2008`, `1944`, `1960` | `load_record`; byte comparison; `publish(old, path)` |
| 46 | `1874`, `2213` | `Path.home()` fallback in `record_dir`; first-seen state root |
| 240 | `221-232`, `2250-2277` | `net`; `has_reaction` paging to `MAX_PAGES` |
| 266 | `290-293`, `1853-1861` | Prefixed exit 3 mapped to `fence_refused`; `Refused` re-raised and `Stop` reported as unreadable in rounds |
| 267 | `2606-2611`, `2615-2623`, `2632-2640` | `vcs_plan`, `vcs_json` and `vcs_branch` error mappings |

**2. Applied (M-1, M-2).** `design.md:18` contains the required replacement text exactly, and the following "delivered native entries" sentence is kept. The historical claim now has its requested citation: `cli/lib/src/pr/pair.dart:4-5` names "the five `pr-pair.sh` subcommands that moved to `sw pr`". The frozen note is at `oracle/pr-pair.sh:2`, and the dispatch table at `:2982-2986` lists nineteen commands, each bound to a Python `cmd_` function.

**3. Applied (M-3).** C18 is at `design.md:134`, directly after C17, with the required text exactly, including `Kind: invariant` and `Destination: doc comment: mise.toml tools.dart`.

**4. Applied (M-3).** Task 9.1 at `tasks.md:154` ends with "Write C18 as a comment on the Dart pin in mise.toml, and verify the comment is present there." The only differences from the required text are "Dart" for `` `dart` `` and no code formatting on `mise.toml`, which name the same pin and destination. Task 9.1 is unticked.

**Destination status (pending, not credited as execution).** The working-tree `mise.toml:2-4` carries a C18 comment directly above the pin, now at `mise.toml:5`, stating the runtime coverage, the inventory trigger and the hash limit. It omits the design's "inventoried for the pinned SDK and its default desktop build" clause; task 9.1's check should judge whether that wording is sufficient. The comment is uncommitted, to land with group 9. Round 7's `mise.toml:2` citation in M-3 is preserved as written and describes the file as it was then.

CHANGES_APPLIED: yes

## Rebuttals

None yet.