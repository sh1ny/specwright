# Design

## Triage

| Trigger | Applies? | Evidence |
|---|---|---|
| T1 Components | yes | The schema calls an author/orchestrator, native `sw`, and an isolated reviewer or fresh-context subagent (`schemas/specwright/schema.yaml:459-486`). |
| T2 State | yes | The CLI and subagent currently replace the reviewed file atomically (`cli/lib/src/review/run.dart:652-662,1780-1782`); checkpoint decisions and repairs must survive replacement. |
| T3 Concurrency | yes | A reviewer runs in the background (`skills/specwright-review/SKILL.md:52-56`); result publication and owner choices must serialize when separate invocations overlap. |
| T4 Boundaries | yes | Two new project settings, a reviewer input section, and state in `review.md`. |
| T5 Volume | yes | Rule files and review history grow with use; never truncate criteria or owner decisions. |
| T6 Risk | yes | The code reads paths to send to a review provider; the existing checklist does not open untracked or linked citations (`schemas/specwright/schema.yaml:516-521`). |

TIER: FULL

## Context

The schema is the design-review orchestrator and describes both dispatch routes and the checklist (`schemas/specwright/schema.yaml:459-537`). The native CLI reads review settings from the project (`cli/lib/src/review/run.dart:215-224`) and validates both output fields (`cli/lib/src/review/run.dart:2291-2318`); pre-ship builds its own input from named branch ranges (`cli/lib/src/review/run.dart:435-477`). Task creation checks the recorded verdict (`schemas/specwright/schema.yaml:593-609`); the old change loop escalates after two consecutive `REVISE` results and offers an owner override (`schemas/specwright/schema.yaml:539-553`). The motivating replay is described in the proposal.

## Decisions

### D1: Declare and read rule inputs from the code repository

- **Choice:** Optional `review.standing_rules` in the code checkout's `openspec/specwright.yaml` lists UTF-8 text file paths relative to the code Git toplevel, using `/`. Match literal tree entries at the resolved code branch commit; accept only normal blobs (Git mode `100644` or `100755`). Refuse invalid paths, bad entries, decode failures and overflow; do not follow filesystem paths. Extend `requireSettingsPinnedTo` to accept a resolved commit and return whether a pin was enforced: its private `_settingsPinned` already accepts an explicit ref (`cli/lib/src/pr/settings_commands.dart:135-177,265-280`). On GitButler pin against that exact commit even with no declared rules, then parse its settings blob through the shared reader instead of rereading the workspace. Git and jj read the code toplevel's project YAML. The FULL workflow does not accept `--settings`. `select --change-review --branch <branch>` runs this same settings preparation before probing a route. Its selection file binds the selected route to the code repository, branch and fingerprint of the settings bytes used. FULL `run` and subagent `record --scratch` and completion require that selection; a stale settings fingerprint or different route is refused before starting the reviewer or publishing a result. The store supplies only planning artifacts. Absent or empty rules share the same identity and produce no standing section or rule blob lookups.
- **Rejected:** Discover ambient instructions or read configured paths from the worktree. Discovery is not owner selection, and worktree reads can send uncommitted content or follow links outside the repo.
- **Reversal cost:** Medium.
- **Important:** yes (configuration and repository-to-provider contract).
- **Chosen by:** user (code-repo-relative tracked declaration; agent selected committed Git object reads).

### D2: Use one renderer for both change-design routes only

- **Choice:** `--change-review` distinguishes FULL change design from ordinary baseline review. On both FULL routes, include the ordered full rule text only when configured and check any existing tests the design preserves. Use live proposal, design and spec deltas, the existing checklist and template. Guard ordinary writers targeting active change reviews and the source of an ordinary move, so they cannot erase the FULL record.
- **LIGHT write guard:** Keep a controller-marked or unresolved FULL report on the FULL path even when the design currently triages LIGHT. `design-step --light` checks eligibility and `record --kind light` checks it again under the publication lock.
- **Reviewer access:** Require effective file reads for a FULL CLI route (OMP `read`, Claude `Read`, or Codex's fixed read-only file access). Refuse before dispatch, without adding tools or falling through. The author checks for file reads before requesting subagent scratch.
- **Rejected:** Inject in all routes including pre-ship and baseline, or require the reviewer to read rule paths itself. The evidence covers change-design review alone, and a path is not proof the full text reached a no-tools route. Applying rules to pre-ship, where the reviewer sees a finished diff, is a candidate follow-up for the owner; baseline and LIGHT are also unchanged.
- **Reversal cost:** Low.
- **Important:** yes (review scope and reviewer input contract).
- **Chosen by:** user (scope); agent chose the shared renderer.

### D3: Native checkpoint state; leave the reviewer verdict authoritative

- **Choice:** `review.design_max_rounds` is a positive integer, default 3. Count only validated results in the current scope. A full `APPROVE` passes even at the limit; `REVISE` and `APPROVE_WITH_CHANGES/no` are unresolved. At the limit `sw review design-step` reports `owner_checkpoint` and new attempts refuse until the owner chooses. Show open findings or Required Changes and repair notes. `--choice scoped-pass --detail <scope>` permits one more full attempt after edits in the authorized scope; if still unresolved, hand back immediately. `--choice scope-change --detail <reason>` requires changed artifacts and starts a fresh scope budget. `--choice stop` leaves the review blocked. A decision is bound to its round and never changes the verdict. Earlier overrides, waivers and deferrals stay distinct; keep the roadmap, pre-ship and PR limits unchanged.
- **Rejected:** Add a second threshold alongside the old two-`REVISE` escalation, use a stalled count, or substitute a computed verdict. Those either cut off later valid catches or let the controller disagree with the reviewer on readiness.
- **Reversal cost:** Medium.
- **Important:** yes (configuration and changed task eligibility at the handoff).
- **Chosen by:** user.

### D4: Persist only workflow progress in the same review record

- **Choice:** Atomically append a controller-owned `## Review progress` section to the validated report, distinct from the template. A reserved exact comment line starts the footer, with a versioned base64url UTF-8 JSON payload for round, scope count, latest artifact and rule fingerprints, repair notes and owner choices. Regenerate the human-readable log from validated state and refuse a noncanonical or malformed stored footer. Reject that exact marker even in a reviewer fenced example; an ordinary `## Review progress` heading is not a marker. Reject line separators in repair summaries and encode owner detail as quoted text with all line separators escaped, so it cannot introduce verdict or framing lines. Preserve every reviewer verdict/findings line when recording a choice. Older unresolved reviews seed the global and scope round from the one positive `Round` metadata entry or report an actionable error. A fresh review after an amended passing design begins a new scope budget. The author reports real repairs before the next pass (or `none`); a successful result carries them forward. Do not parse findings or derive a verdict.
- **Rejected:** Overwrite owner decisions with each result, keep them only in machine-local state, or introduce a cumulative finding ledger. The current review plus durable progress is sufficient.
- **Reversal cost:** Medium.
- **Important:** yes (durable review record).
- **Chosen by:** agent (delegated within the approved contract).

### D5: Publish only results for the starting review inputs

- **Choice:** Check byte digests of the live proposal, design and spec deltas alongside the recorded report and effective rule/settings identity at dispatch and publication. Hold the OS lock only while validating and publishing state or reserving subagent scratch, never while reviewing or waiting for the owner. Publication installs one bounded, validated report atomically. The `APPROVE` result binds to the planning digests and rule identity at tasks/apply.
- **Verdict:** A fresh FULL pass uses the whole checklist. `APPROVE_WITH_CHANGES/no` asks for edits and never grants readiness. Required Changes and Release Notes are ordinary edits and require another full `APPROVE`; there is no limited confirmation.
- **Reason (owner):** “Pre-ship kept finding holes in the review-capture tracking; incremental rechecks were never part of the brief (delta-only rounds were rejected by the experiment). Design review keeps today's behaviour: every round is a full review, and any later edit voids a pass.”
- **Rejected:** Private planning snapshots, a Markdown exclusion scanner, persistent conditional baselines, or holding a lock while the reviewer reads. Digests detect different contents at either check, not an edit restored before publication.
- **Reversal cost:** Medium.
- **Important:** yes (scope change and readiness).
- **Chosen by:** user.

### Decision summary

| # | Decision | Choice | Rejected | Reversal cost | Important | Chosen by |
|---|---|---|---|---|---|---|
| S1 | Scope | FULL change design only | All reviews | Low | yes | user |
| S2 | Readiness | Authoritative reviewer verdict | Count-based stop or override | Medium | yes | user |
| S3 | Planning inputs | Live files and a new full review after any edit | Private snapshots, exclusions or tracked conditional baselines | Medium | yes | user |
| D1 | Rule source | Declared code-branch blobs | Ambient or worktree text | Medium | yes | user |
| D2 | Brief | Shared renderer on the FULL change path | All review modes or rule paths alone | Low | yes | user |
| D3 | Handoff | Configured owner checkpoint | Competing threshold or computed verdict | Medium | yes | user |
| D4 | Record | Native progress section in `review.md` | Ephemeral or duplicate record | Medium | yes | agent |
| D5 | Result publication | Compare live byte digests and state under the short lock | Conditional confirmations or keeping snapshots | Medium | yes | user |

## Assumptions

None.

## Carried constraints

- **C1:** Rules declared by a project are criteria, not permission to change workflow or reviewer isolation. Kind: invariant. Destination: spec: specs/review-routes/spec.md → Requirement: FULL change-design reviews receive binding standing requirements.
- **C2:** An unresolved reviewer disposition remains unresolved after any checkpoint choice. Kind: invariant. Destination: spec: specs/design-review-gate/spec.md → Requirement: The owner checkpoint records its choice without overriding the verdict.
- **C3:** Git object reads avoid reading the work tree, so configured rule paths never need a filesystem fallback. Kind: rejected alternative. Destination: ADR 0044.
- **C4:** Binding rules do not apply to pre-ship, roadmap baseline or LIGHT review. Kind: deliberate gap. Destination: spec: specs/review-routes/spec.md → Requirement: FULL change-design reviews receive binding standing requirements.
- **C5:** No stop on an unchanged or increased finding count. Kind: rejected alternative. Destination: spec: specs/design-review-gate/spec.md → Requirement: Unresolved design review reaches an owner checkpoint.
- **C6:** An invalid, stale or failed result does not use an authorized scoped pass. Kind: invariant. Destination: spec: specs/design-review-gate/spec.md → Requirement: The owner checkpoint records its choice without overriding the verdict.
- **C7:** Reviews, owner deliberation and waits happen outside the publication lock. Kind: invariant. Destination: ADR 0044.
- **C8:** Both routes read live planning files; a changed fingerprint cannot publish. Kind: invariant. Destination: spec: specs/review-routes/spec.md → Requirement: FULL review results apply only to the current design.
- **C9:** A prior pass no longer authorizes tasks or apply after standing-rule identity changes. Kind: invariant. Destination: spec: specs/review-routes/spec.md → Requirement: A design review pass covers its standing rules.
- **C10:** Every round uses the full checklist; any change to design inputs requires a fresh pass. Kind: invariant. Destination: spec: specs/design-review-gate/spec.md → Requirement: Any edit to FULL design inputs voids the pass.
- **C12:** Refuse a route without file access to the live artifacts. Kind: invariant. Destination: spec: specs/review-routes/spec.md → Requirement: FULL design review requires usable evidence and bounds failure retention.
- **C13:** Failed FULL attempts cannot leave a series of diagnostic files or archives of session transcripts. Kind: invariant. Destination: spec: specs/review-routes/spec.md → Requirement: FULL design review requires usable evidence and bounds failure retention.

## Diagrams (FULL)

```mermaid
flowchart LR
  Settings[Code project settings] --> Controller[sw review]
  Tree[Code branch rule blobs] --> Controller
  Author[Specwright schema author] -->|Existing brief and repair summary| Controller
  Controller -->|Existing brief plus optional rule section| Reviewer[CLI or subagent]
  Reviewer -->|Original-format result| Controller
  Controller -->|Atomic verdict and progress| Record[review.md]
  Record --> Author
  Author -->|At checkpoint| Owner
  Owner -->|Choice and scoped detail| Author
```

```mermaid
stateDiagram-v2
  [*] --> Review
  Review --> DesignPass: reviewer passes
  Review --> Review: unresolved below checkpoint; repair
  Review --> Checkpoint: unresolved at limit or after extra pass
  Checkpoint --> Review: scoped pass
  Checkpoint --> RevisedScope: scope change with reason
  RevisedScope --> Review: revised artifacts; new scope budget
  Checkpoint --> Stopped: stop
```

```mermaid
sequenceDiagram
  participant A as Author
  participant W as sw review
  participant G as Git code branch
  participant R as Reviewer
  A->>W: run or subagent scratch
  W->>G: literal paths to regular blob IDs and bytes
  W->>R: CLI brief, or author includes returned section
  R-->>W: review report (record scratch for subagent)
  W-->>A: validated report and next workflow state
```

## State & Ownership (FULL)

| State | Owner (sole writer) | Lifetime | Invalidation / rebuild | Authoritative copy |
|---|---|---|---|---|
| Config and rule blobs | Project owner through Git | Project | New config or committed rules are used on the next review; rules are never inferred from elsewhere | Code project config plus selected branch commit |
| Verdict / findings | Fresh reviewer produces input; native review owns the file write | Until a new validated report; verdict covers only reviewed design | Invalid or interrupted output does not replace it | Latest report in `review.md` |
| Round, repairs and checkpoint choice | Native review; receives author repairs and owner decisions, not reviewer instructions | Change lifetime | Atomic replacement preserves history; missing file follows first-review behavior; malformed progress stops | Progress section in `review.md` |
| Brief | Native renderer with existing author packet | One invocation | Re-render from current inputs on each pass; clean run directory as today | The input actually supplied to the route |
| Attempt reservation | Native review controller | Until a subagent result is completed or a known-stopped attempt is reclaimed | Recheck input and state digests under the lock; no copies of planning content | Private scratch path and attempt token |
| Retained failed result | Native FULL controller under the publication lock | At most the most recent retained bounded failure | Replace one fixed slot only; never retain an oversized result, full CLI session or multiple scratch results. Diagnostic loss or partial data on interrupted write cannot affect review state | `last-failed` per canonical review record, not part of `review.md` |

## Failure & Visibility (FULL)

| Component | Fails / dies mid-operation → | Recovery | Retry safe? | Who finds out |
|---|---|---|---|---|
| Rules resolution | Missing code branch, invalid path/mode/text or overflow → named error before reviewer; no record mutation | Fix setting or commit a valid rule | Yes after fix | Author and owner |
| Reviewer | Existing route validation or timeout → prior report/progress untouched | Existing failed-review workflow; no implicit route retry | A fresh review remains same round | Author and owner |
| Missing read capability | FULL review route refused before dispatch with the missing tool named | Restore the file-read capability or explicitly select a usable reviewer | Yes after configuration changes | Author and owner |
| Progress write | Invalid or corrupt record → refuse; failed atomic write → original remains | Recover bad record or fix disk and re-run | Yes; an already recorded choice is not recorded twice | Author and owner |
| Publication lock | Concurrent completion or owner choice → busy or stale before replacing the record | Re-read the record; a dead writer no longer holds an OS lock | Only after checking current state | Author |
| Owner | No answer → wait; explicit stop → record followed by blocked review | New owner-directed work is separate, not auto-resume | No automatic retry | Owner |

- **Failure reporting in the schema and review skill:** For a FULL failure, report the route, exit status and error; `review.md` stays untouched and tasks do not start. Report the controller's `diagnostic` path only if the current failed attempt retained a bounded result. Never report the former subagent `scratch` path as preserved, and never reuse an earlier diagnostic path to explain a newer failure. A completed subagent attempt removes its scratch (or reports a cleanup error when the reservation could not be released). Baseline and other non-FULL design record failures still name and retain that attempt's original scratch as today.

## Resource Bounds (FULL)

| Queue / buffer / cache / transfer | Bound | At the bound | Timeout | At 10x / 100x |
|---|---|---|---|---|
| Git input verification | At most 32 rule paths of 512 UTF-8 bytes each, 256 KiB aggregate blob bytes, and finite ref, settings, pin and tree output caps | Refuse during capture, never truncate. Do not print rule contents on error | One monotonic 60 s budget for all Git commands per preparation or publication check, including root/ref resolution, the GitButler settings pin/filter helper and rule reads. Pass remaining time through the shared bounded launcher; a failure releases the publication lock without modifying the record | A larger policy is not a standing review brief |
| Report input | Existing 2 MiB ceiling (`cli/lib/src/review/run.dart:29,1576-1580,2551-2557`) | Same failed-output behavior | Existing review timeout | No change |
| Review record history | Bound by the existing 2 MiB answer limit plus the same bound for the progress section; refuse rather than drop entries | Owner sees error; record stays intact | No new independent wall deadline | Normal progress grows by one short note per round and one owner decision per handoff, not by copying all prior reports |
| Planning identity and scratch | Hash up to 16 MiB across 256 regular live planning files; at most two unfinished subagent reservations per record | Report oversized inputs or occupied slots before dispatch; reclaim only a known-stopped attempt | Git inputs have the budget above | Store no private planning copies or prior baselines |
| Failed or invalid output (FULL) | One fixed `last-failed` file per canonical review record, at most 2 MiB as written, shared by both CLI and subagent attempts | Retain a complete bounded answer only; discard oversized and incomplete output without publishing it or returning a misleading result path. At RECORD after the subagent has stopped, read at most 2 MiB plus one byte from its scratch, then remove the transient attempt (not an OS quota for an actively writing subagent). Reuse the existing CLI transport and answer limits. Do not preserve FULL OMP session directories (`cli/lib/src/review/run.dart:1594-1598,1617-1633,1790-1804`); keep receipt and error as today. Write/truncate the single diagnostic file under the same lock without creating backup files. Report cleanup/write errors; a diagnostic is never gate input | Existing route timeout; no extra report-read wait on local regular files | Repeated refusals replace one diagnostic rather than growing state; never copy or keep oversized results |

## Flow & State Gaps (FULL)

- An interrupted CLI review leaves the previous verdict and owner choice untouched. The subagent result is not installed until recorded and validated against its dispatch digest. A rejected, stale or failed run does not consume an accepted scoped pass. The author checks `design-step` on resume.
- A concurrent publication sees the current record under the same lock as owner choice writes. A losing result is refused as stale or busy; an earlier accepted result or owner decision survives. The lock is not held while waiting on a child, and does not claim to prevent worktree edits by a user or external processes after publish.
- The reviewer reads the live artifact paths in the request using existing route access (including the store if supplied). Digests detect persistent input changes; they cannot detect an edit that is restored during the review. Do not edit the inputs while the reviewer works.
- `scope-change` does not alter the current verdict. An amendment to live planning artifacts opens the revised scope's budget; a reason alone does not.
- `stop` and waiting do not invalidate or remove existing review artifacts; they prevent another pass without the proper owner action and never allow tasks while unresolved.

## Mechanism Ledger (FULL)

| Mechanism | Built? | Why | Evidence that would change the call |
|---|---|---|---|
| Code branch blobs, literal path lookup and mode check | yes | A filesystem path could leak untracked or linked local data to the reviewer | Provider never receives project content |
| One shared brief renderer | yes | CLI and subagent otherwise drift or review different criteria | Only one supported review route |
| Review progress section, written atomically | yes | A resume after replacement or process death would lose the checkpoint or owner choice | Different single authoritative review storage format |
| Finding-count gate or experimental finding schema | no | Replays found real defects after unchanged counts; verdict is already validated | Separate owner-approved evidence and contract |
| Short lock and input digest comparison | yes | A stale result cannot consume the owner's choice; record writers serialize | Only one process can ever publish or record a choice |
| Private planning copies, exclusions and conditional baseline | no | The core needs a full review after edits, not separate review modes or a previous input cache | New owner-approved scope and evidence |

## Risks / Trade-offs

- Declared text reaches the review provider in full. Restrict the source to intentional, committed regular files and document the transfer; do not include secrets or unrelated policy.
- The default changes for projects that declare nothing: the brief is unchanged, but the change-design owner handoff is after three unresolved validated rounds instead of two consecutive `REVISE` rounds. No project PR feedback policy changes.
- Only the latest reviewer report is authoritative; the repair and owner log is not a cumulative findings validator and does not claim problems disappeared just because their counts changed.

## ADRs

- **In force, constraining this change:** 0007 (reviewer and orchestrator split, fail-closed output), 0019 as amended by 0021 (GitButler settings pin), 0026 (carry constraints), 0035 and 0036 (unchanged isolation and tool policy).
- **To record during apply:** 0044, covering deliberate committed standing-rule inputs and the distinction between checkpoint and readiness. Amend only the design decision; no ADR has its accepted text edited.
