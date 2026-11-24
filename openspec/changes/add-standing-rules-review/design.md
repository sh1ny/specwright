# Design

## Triage

| Trigger | Applies? | Evidence |
|---|---|---|
| T1 Components | yes | The schema's review instruction calls the native `sw review` and the existing isolated reviewer routes. |
| T2 State | yes | Round counts and owner decisions survive replacement of the result in `review.md`. |
| T3 Concurrency | no new surface | One author owns the review loop; result installation still uses main's atomic write, not a new controller lock. |
| T4 Boundaries | yes | New project settings and a provider-facing criteria section for FULL change design only. |
| T5 Volume | yes | The criteria section is bounded; never silently truncate a configured rule. |
| T6 Risk | yes | The rule texts are sent to the selected review provider, so read only explicitly declared committed regular files. |

TIER: FULL

## Context

The accepted replay compares the existing reviewer with and without binding standing rules. Later rounds still found genuine defects. Use the existing review checklist and routes; change only the binding inputs and the point where an unresolved review asks the owner. This supersedes S3 in the proposal. Main's conditional Required Changes confirmation, Release Notes exemption, tasks/apply precheck and delegation stay unchanged.

## Decisions

### D1: Rules are declared and read as committed text

- **Choice:** `review.standing_rules` in the code project's `openspec/specwright.yaml` is an ordered list of code-root-relative UTF-8 files. Take each literal path from the named code branch's tree, require a regular Git blob, and read its full text. Both FULL change-design routes use the same renderer; the CLI appends it to the existing brief and the fresh-context subagent receives it with its scratch request. No declaration or `[]` leaves the brief unchanged. Existing tests the design preserves are in scope.
- **Rejected:** Read ambient instructions or worktree files, or send only paths instead of the text.
- **Reversal cost:** medium (project config and provider input).
- **Important:** yes.
- **Chosen by:** user.

### D2: Review policy stays local to a change design

- **Choice:** Baseline, LIGHT and pre-ship do not receive binding rules. The replay tested change designs only; pre-ship reviews the completed diff against a different brief. Existing isolation, task gates, report writers, verdict validation, conditional confirmation and Release Notes exemption outside the checkpoint remain as on main.
- **Rejected:** Extend standing rules, controls or freshness checks to other workflows.
- **Reversal cost:** low.
- **Important:** yes.
- **Chosen by:** user.

### D3: A round limit asks the owner; only a review can pass

- **Choice:** `review.design_max_rounds`, a positive integer defaulting to 3, replaces the two-consecutive-REVISE escalation for the FULL change-design loop. An unresolved valid round counts regardless of finding count. The existing passing verdicts pass as before. When the limit is reached without a passing verdict, show the report's open findings/Required Changes and the repairs recorded to date, then ask the owner. An explicitly authorized scoped pass allows one more result and hands back if unresolved. A scope change records the owner's reason, and the author applies the revised scope before starting a fresh budget. Stop records the decision and leaves the verdict unresolved. No choice creates `USER_OVERRIDE`. Outstanding historical overrides remain as recorded.
- **Rejected:** A second threshold, stall detection, computed approval, tracking planning-file digests, or auto-resetting the round counter without an owner's choice.
- **Reversal cost:** medium.
- **Important:** yes.
- **Chosen by:** user.

### D4: Store only progress beside the existing result

- **Choice:** The existing atomic result write carries a progress footer containing the total round, rounds in scope, whether the last round spent a scoped pass, actual repairs, and owner choices/reasons. A choice appends to the footer without modifying the existing report body. There is no publication lock, private attempt token, changed scratch lifecycle, conditional baseline, or apply gate. Follow the existing one-author workflow: do not edit while a reviewer is reading; do not run competing reviews. Failed validation does not write or spend a choice. Legacy unresolved records seed the count from their recorded Round when present.
- **Rejected:** A machine-local decision record, persisted planning snapshots, strict new verdict parsing, or changing how all other writers work.
- **Reversal cost:** medium.
- **Important:** yes.
- **Chosen by:** agent within the owner-approved core.

## Decision summary

| # | Choice | Rejected | Reversal cost | Important | Chosen by |
|---|---|---|---|---|---|
| D1 | Declared code-branch regular blobs | Ambient or worktree rules | Medium | yes | user |
| D2 | FULL change-design only | All reviews or apply | Low | yes | user |
| D3 | Configured owner checkpoint, verdict unchanged | Stalls and automatic approval | Medium | yes | user |
| D4 | Progress beside the existing result | Separate state and planning tracking | Medium | yes | agent |

## Assumptions

The existing author serializes design-review requests and is responsible for applying a requested scope change before continuing; this change does not track edits or enforce scope with a diff.

## Carried constraints

- **C1:** Declared text is criteria, not authority to change workflow or isolation. Kind: invariant. Destination: spec: `specs/review-routes/spec.md` → FULL change-design reviews receive binding standing requirements.
- **C2:** Owner choices leave an unresolved verdict intact. Kind: invariant. Destination: spec: `specs/design-review-gate/spec.md` → The owner checkpoint records its choice without overriding the verdict.
- **C3:** Keep rules from committed regular blobs; do not follow worktree links. Kind: rejected alternative. Destination: ADR 0044.
- **C4:** No criteria change for pre-ship, roadmap baseline or LIGHT. Kind: deliberate gap. Destination: spec: `specs/review-routes/spec.md` → FULL change-design reviews receive binding standing requirements.
- **C5:** No stop based on a finding count. Kind: rejected alternative. Destination: spec: `specs/design-review-gate/spec.md` → Unresolved design review reaches an owner checkpoint.
- **C6:** A failed reviewer result does not use a scoped pass. Kind: invariant. Destination: spec: `specs/design-review-gate/spec.md` → The owner checkpoint records its choice without overriding the verdict.
- **C7:** Keep compatibility for existing verdicts, tasks/apply gates and scratch paths; no new locking or capture. Kind: invariant. Destination: ADR 0044.

## State and failure

| State | Authoritative copy | Failure behavior |
|---|---|---|
| Project review config and rule blobs | Code project config and named code branch tree | Invalid or missing declared blob fails before the reviewer; no truncated brief. |
| Verdict and findings | Latest validated result in `review.md` | A failed review leaves the prior result in place, as today. |
| Budget, repair log and owner choice | Progress footer in `review.md` | Malformed progress stops the change-design review; a failed result does not advance the round. No response means stop at the checkpoint. |

Rule reads permit at most 32 paths, at most 512 UTF-8 bytes per path, and 256 KiB total committed text, with a shared Git lookup budget. The footer is bounded by the existing 2 MiB answer limit; refuse a new result or choice rather than silently drop history. Review outputs, scratch, and transport failure handling keep main's bounds and behavior.

## ADRs

0007, 0015, 0026, 0035 and 0036 remain in force. ADR 0044 covers declared criteria and the owner checkpoint only.

## Removed in scope cut 2

Inventory against `main` at pre-cut head `1154e6f2` (line ranges refer to that head):

| Extra | Files and approximate lines | Why it was added |
|---|---|---|
| Fingerprints of live planning files, branch tip, effective settings and rules; stale selection and result refusal; required fresh approval after any edit | `cli/lib/src/review/design_inputs.dart:8–203,205–326,349–420`; `design_progress.dart:18–125,296–308,575–634,696–770`; `run.dart:234–312,399–582` | Replaced private planning copies and conditional baselines after scope cut 1; then tied publication, tasks and apply to those fingerprints. |
| Removal of legacy conditional confirmation and Release Notes exemption; upgrade invalidation of earlier approvals | `run.dart:2397–2439`; `design_progress.dart:131–231,595–634,727–770`; `schemas/specwright/schema.yaml:537–553,582–604,773–775`; `schemas/specwright/templates/review.md:13,32`; `skills/specwright-commit/SKILL.md:39`; `README.md:887–896`; `openspec/architecture.md:171–172,214` | Used a fresh full approval in place of every conditional recheck, and tried to enforce a stricter interpretation of review freshness. |
| Disposition-aware native tasks/apply guards, per-task apply checks and serialization of FULL delegation | `cli/lib/src/review/run.dart:315–334`; `design_progress.dart:8–11,310–348`; `schemas/specwright/schema.yaml:598–603,707–775`; `agents/{claude,omp}/specwright-implementer{,-light}.md:8–11` | Prevented another task from starting after a Release Notes edit and repaired the waiver and delegated-worker bypasses introduced by that gate. |
| New LIGHT publication command and readiness check; guards on ordinary review output and moves | `run.dart:433–435,598–665`; `design_progress.dart:243–253,350–437`; `schemas/specwright/schema.yaml:435–463,601–603` | Prevented a retiered or ordinary writer from replacing active FULL progress. |
| Publication lock, canonical-path state directory, attempt reservation/token, interrupted-slot cleanup and recheck of starting state | `design_progress.dart:245–295,350–574,636–812`; `run.dart:489,534–545,580–587,599–645,1640–1650` | Made competing writers and stale work refuse under a short lock. |
| Additional FULL GitButler settings pin APIs, bounded local and committed settings reads, selected-settings identity, shared deadline for pin/filters and Git reads | `cli/lib/src/pr/settings_commands.dart:6,138–222,278–304`; `cli/lib/src/review/settings.dart:47–50`; `design_inputs.dart:11–203,255–326`; `run.dart:234–311,470–476` | Kept FULL route selection pinned to branch settings and hardened that new pin path against oversized inputs. The ordinary main settings path was separate. |
| Refuse no-read reviewer routes before dispatch | `design_progress.dart:~440–510`; `schemas/specwright/schema.yaml:465–491`; `skills/specwright-review/SKILL.md:81–92` | Protected the path-only live evidence packet introduced by the new controller. |
| FULL-only strict verdict line parser, HTML-comment filter and legacy-body/footer workaround | `run.dart:2397–2439`; `design_progress.dart:8–11,155–238,310–348,727–770` | Aligned successive versions of the new controller and apply gate; legacy bodies required compatibility once choices used the new footer. |
| Different FULL scratch lifecycle, malformed-byte refusal, fixed failed-result retention and suppressed session archives | `design_progress.dart:430–574,668–812`; `run.dart:599–645,1690–1700,1880–1910`; `schemas/specwright/schema.yaml:486–491`; `skills/specwright-review/SKILL.md:86–92` | Bounded the new controller's diagnostic and scratch storage, and kept invalid bytes out of its report. |
| Tests, instructions and contracts for those mechanisms | `cli/test/review/design_publication_test.dart:1–240`; `evals/review-routes/test_design_review.py:~139–498`; `evals/review-routes/test_skill_text.py:280–314`; `evals/git-workflow/test_instructions.py:128–134,1980–1992`; `evals/release/test_skill_text.py:~355`; `openspec/changes/add-standing-rules-review/specs/{design-review-gate,review-routes}/spec.md` and `tasks.md` | Captured the new mechanisms in fault tests and regressions, removed tests of restored behavior, and documented the widened contracts. Core rule and checkpoint coverage remains in the cut. |
| Documentation for the narrowed-but-still-extra mechanisms | This `design.md:22–195`; `proposal.md:11,52–59,72–74`; `docs/adr/0044-change-design-review-binds-rules-and-records-owner-checkpoints.md:1–20`; `README.md:887–896`; `openspec/architecture.md:85,142,171–172,214,243` | Explained the former design, install migration, and publication/freshness decisions. The history of scope decisions remains, but the shipping contract describes only the core. |

**Owner's reason for scope cut 2:** “fix rounds were creating new bugs in gating that the brief never asked for”.


### Follow-up issue candidates on main

- Reject noncanonical and commented-out design verdicts consistently. Main's validator trims and scans raw reply lines (`cli/lib/src/review/run.dart`, `_validateDesign`), while downstream instructions match whole lines. A reviewer can publish an unusable record today; this cut deliberately restores the existing parser.
- Bound the existing review selection and settings readers. Main decodes the entire selection in `_loadSelection` and uses the ordinary `readSettingsText` path for review settings. This does not require any new apply gate, GitButler pin API or private attempt state.
- Check usable evidence on configured reviewer routes. The existing design instructions give the reviewer file paths; a route that disables file reads can still be selected. Address this in reviewer route policy, not in a parallel design controller.
- Review a named GitButler branch with that branch's settings. Main's design routing reads workspace settings, so a sibling edit can change the selected route without affecting the branch being reviewed. Confirm expectations separately before changing shared pinning.
- Prevent late or competing design results from replacing a newer result or covering old inputs. Main validates and atomically replaces the report, but does not compare earlier report or planning bytes. Investigate if multi-author review needs a supported contract; do not assume the former capture controller is the solution.

The removed gates introduced the GitButler partial-group deadlock, `WAIVED` next-task refusal and legacy-verdict/footer mismatch; main had none of those gates. Main's existing subagent JSON/result handling and scratch retention are unchanged, including replacement decoding of malformed UTF-8.
