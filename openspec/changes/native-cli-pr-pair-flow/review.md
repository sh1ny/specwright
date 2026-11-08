# Review

## Metadata

- **Round:** 3 (full review after a user-directed planning amendment)
- **Prior round:** Round 2 recheck, APPROVE_WITH_CHANGES with its changes applied. The amendment to proposal, specs and design voids that verdict.
- **Reviewer:** cross-model CLI (claude, claude-opus-5-5)
- **Reviewed:**
  - Rules and change artifacts: `AGENTS.md`, `schemas/specwright/schema.yaml` (FULL design review), `schemas/specwright/templates/review.md`, and `proposal.md`, `design.md`, `tasks.md`, prior `review.md` and both delta specs in `openspec/changes/native-cli-pr-pair-flow`
  - Source: every cited range of `skills/specwright-pr/scripts/pr-pair.sh`; `cli/lib/src/commands/pr.dart`; `cli/lib/src/commands/vcs.dart:1-110`; `cli/lib/src/pr/pair.dart:1-114`; `cli/lib/src/fence/fence.dart:1-45,145-169,425-577`; `cli/lib/src/process/limits.dart:1-78`
  - Dependency policy: `cli/pubspec.yaml`, `cli/test/no_build_hooks_test.dart`, `cli/tool/hooks_scan.dart`
  - Evidence and consumers: `evals/pr-pair/closing_bodies.py`, `evals/suites.json`, targeted searches of `evals/pr-pair/test_pr_pair.py` and `skills/`, `docs/adr/0031-direct-native-workflow-calls-and-project-selection.md`, `openspec/roadmap.md:7-28`
- **Verification limits:**
  - Nothing was run, built or edited.
  - The `html` package source is not in this repository and was not opened. Its licence, dependency graph, hook status and exact parser behavior remain the checks D6 and task 4.2 assign to apply. Statements below about tree construction come from the HTML5 parsing rules, not from that package.
  - Tracked status of the cited source and eval files was confirmed by searching `.git/index` for each path. File modes and symlink status could not be read that way.
  - Other in-force ADRs were covered only by a search of 0027-0029 for parser, licence and dependency terms, which found nothing.

## Findings

### Critical (blocking)

None.

### Moderate

**M-1. Exact-preservation wording remains where the amendment should have changed it.**

- `design.md:40` (D2) still says "retain Python ordering and escaping when the stored bytes are observable". S2 rejects treating "every Python quirk or serialized byte" as a requirement (`proposal.md:50`), and D2 claims S2 as its authority (`design.md:43-44`).
- The evidence does not support a serializer-byte contract. Records are read through `json.loads` (`pr-pair.sh:2037-2043`). The only byte comparison is between the two copies left by an interrupted legacy move (`pr-pair.sh:1979`, `1995`).
- A file is always "observable", so the clause would push apply toward a custom emulation of `json.dumps(rec, indent=2)` (`pr-pair.sh:2178`, `2556`). That is the compatibility code the user asked to avoid.
- `proposal.md:12` keeps JSON fields, error codes and exit statuses without qualification, and `proposal.md:73` publishes the same promise. Both conflict with `proposal.md:16` and the delta (`spec.md:15`, `85`).
- Task 8.2 (`tasks.md:102`) allows updating only assertions "explicit in the proposal". Existing evals reach the native code only after that shim switch, so a documented S2/D6 difference would first fail there with no permitted update.
- Required Changes 1-3 and 5 resolve this. The D2 edit applies S2's later user direction and does not reverse D2's choice to keep the protocol.

**M-2. The approved parser's rendered-closing scenario is not assertable and names a library.**

- `spec.md:105` says "the approved HTML parser and workflow adapter" and "incidental parser differences are documented and do not change the product workflow".
- The schema excludes library choices from specs and requires each THEN to be an assertable outcome.
- The real outcome is defined elsewhere. `design.md:252` says closing targets require the user's decision, and `skills/specwright-pr/SKILL.md:92` branches on `status`, `intended`, `missing` and `extra`.

**M-3. The new parser's constraint and the documented differences have no destination.**

- D6 forbids an authored HTML parser or entity table (`design.md:72-73`), and a future change could break that. It is absent from Carried Constraints (`design.md:97-109`).
- D6, task 4.2 and task 7.3 all require documented differences but name no place for them.
- Only task 4.2 tells apply to ask the user before a difference changes an outcome. The other commands, reached through task 7.3 (`tasks.md:97`), lack that instruction, although material workflow decisions must go to the user.

**M-4. Bounds and failure tables omit the new DOM stage.**

- `design.md:198` covers only a failed render read. `design.md:204-218` has no row for parsing the response into a whole DOM.
- A parser or adapter exception would become `internal_error` with exit 1 (`pair.dart:92-98`). That is safe, because it reports no `match`, but the design does not state it.
- The old parser is event-driven and tracks code with a counter (`pr-pair.sh:1443-1472`), so nesting depth cannot overflow its stack. A recursive DOM walk could turn a deeply nested description into a new `internal_error`, which is a product-outcome difference.
- Task 4.1's case list also omits malformed markup, although `design.md:252` names it as the main risk. Under HTML5 tree construction, text directly inside a raw `<table>` is moved in front of the table, so `Fixes <table>#1</table>` could join into a directive that the old parser split at the block boundary.
- Recordings require a live render (`closing_bodies.py:1-6`), but `closing_test.dart` can use handwritten HTML, so this coverage is feasible without live requests.

**M-5. The licence condition has no recorded result.**

- The user's approval is conditional on the licence check.
- Task 4.2 says only "applicable notices", with no destination. The distribution is one compiled file (`cli/pubspec.yaml:12-14`), a search of `cli/tool` found no licence or notice handling, and the repository has no third-party notice file.
- Apply could tick the task with no evidence of the check and no decision about notices for the shipped binary.

**M-6. Two citations moved because of this branch's own Group 3 work.**

- `design.md:10` cites `commands/pr.dart:11-24` and `48-75`, and `design.md:18` cites `67-74` for the five settings commands.
- The handoff list is now `pr.dart:12-26`, validation and dispatch are `54-87`, and the five entries are at `76-79` and `86`. Lines 67-74 now show context construction.
- The claims remain true, so this is not Critical.

### Suggestions

- **S-1.** `openspec/roadmap.md:9` and `:14` still describe existing JSON and exit-code contracts as intact. This does not conflict unless a coordinated change alters one of those contracts. The ask-the-user instruction in Required Change 3 covers that case, so no roadmap edit is needed now.
- **S-2.** Python's `\b`, `\w` and `\d` are Unicode-aware on `str`, while Dart's default classes are ASCII-only. `éfixes #1` could therefore become a directive in Dart. Task 4.1 already requires Unicode coverage; include a keyword next to a non-ASCII letter.

### Confirmed intact

- **Maintained parser use:** D3 withdraws the no-new-package assumption (`design.md:48`), and D6 permits the public `html` parser. Other dependency adoptions return to the user (`design.md:72`, `proposal.md:32`). `no_build_hooks_test.dart:52-56` and `hooks_scan.dart:12-16` scan every package in the resolved config, so that check is enforceable.
- **Workflow safety:** `design.md:234` and `spec.md:85-101` keep identity, ownership, mutation order and guards, deadlines and recovery outside any normalization. One PUT with read-back (`pr-pair.sh:2743-2766`) and delete guards (`pr-pair.sh:2972-2977`) remain specified.
- **D5 and C11:** the nested fetch constraint and the store-network gap are unchanged and consistent across `design.md:64`, `design.md:109`, `spec.md:142-143`, `tasks.md:95-96` and ADR 0031 (`:22-23`).
- **Retained contracts:** these are justified by workflows and are testable. `SKILL.md:92` branches on the closing fields and on exit 3, and the record key, owner, lock and unreadable results (`pr-pair.sh:1916-1922`, `2013-2022`, `2037-2043`) support interrupted-pass recovery. Exact argument bytes (`spec.md:169-171`) protect tool input and match `roadmap.md:18`; they are not a Python representation quirk.
- **Scope and feasibility:** no requirement forces a rewrite of existing ports. Pending groups 4-9 remain feasible, and the build-hook, dependency and closing-parser work stays confined to Group 4.
- **Remaining citations:** the other design citations support their claims. ADR 0031 needs no amendment: its statement about program-readable results is context and matches S2's default of retaining interfaces.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. In `design.md` D2 **Choice**, replace "Reuse the existing codec/JSON helpers where they match the protocol; retain Python ordering and escaping when the stored bytes are observable." with: "Reuse the existing codec/JSON helpers. JSON key order, indentation and non-ASCII escaping are not part of the protocol: readers parse the record (`skills/specwright-pr/scripts/pr-pair.sh:2037-2043`). Legacy migration compares and moves existing file bytes (`1979`, `1995`), so migration copies them unchanged, but a native writer need not reproduce Python's serialized form."

2. In `proposal.md`:
   - At line 12, replace "Keep its path, arguments, JSON fields, error codes, exit statuses and persisted formats." with "Keep its path and arguments. Keep JSON fields, error codes and exit statuses unless S2's documented coordinated producer/consumer change applies, and keep persisted records interoperable."
   - At line 73, replace "preserving their JSON, exit codes, feedback records and recovery behavior" with "preserving their workflow outcomes, feedback records and recovery behavior".

3. In `tasks.md`:
   - At the end of task 7.3, append: "Ask the user before any difference changes a workflow outcome. Write C13 at its destination."
   - In task 8.2, replace "whose behavior changes are explicit in the proposal" with "whose behavior changes are explicit in the proposal, plus assertions for differences documented under S2/D6 with their consumer coverage".

4. In `specs/pr-script-runtime/spec.md`, scenario "Rendered closing lines preserve code boundaries", replace the THEN line with: "- **THEN** `intended`, `missing`, `extra` and `status` name the same issues and state as the frozen script for that rendered body, a reference inside code is not an intended issue, and a code span between references ends the closing list".

5. In `design.md` `## Carried constraints`, add these entries:
   - "**C12:** Closing prose comes from the `html` package's public parser plus a closing-reference adapter. No HTML tokenizer, parser or entity table is authored to match Python, and each observed parser difference is listed here with its consumer check. Kind: rejected alternative. Destination: doc comment: cli/lib/src/pr/closing.dart renderedLines."
   - "**C13:** Each representation difference from the frozen oracle is listed with its producer/consumer contract test, and one that changes a workflow outcome needs the user's decision. Kind: invariant. Destination: doc comment: evals/pr-pair/test_workflow_parity.py WorkflowParity."

   In `tasks.md` task 4.2, append "Write C12 at its destination." In task 8.4, replace "C4/C5/C7/C8" with "C4/C5/C7/C8/C12/C13".

6. In `design.md`:
   - Replace the Failure & Visibility row "Closing parser" with: "| Closing parser | Render read fails, or the parser or adapter raises | Render read: unknown result, no closing proof. Parser or adapter error: internal_error, no closing proof | Read may repeat | Agent sees exit 3, or internal_error exit 1; never `match` |".
   - Add this Resource Bounds row after "Manual reaction paging": "| Rendered description parse | Render output within the existing 32 MiB stream bound; one DOM per check, released after line extraction | Limited read stays unknown; a parser or adapter error is internal_error and gives no closing proof | Memory grows with response size up to the bound; the adapter walks the DOM iteratively, so nesting depth cannot overflow its stack |".

   In `tasks.md` task 4.1, replace "Add `cli/test/pr/closing_test.dart` for the parser boundary." with "Add `cli/test/pr/closing_test.dart` for the parser boundary, using handwritten HTML for malformed and misnested markup, text inside a raw table, and deep nesting."

7. In `tasks.md`, after task 4.3, add: "- [ ] 4.4 [evidence] Record each newly resolved runtime package's version, licence, build-hook result and any notice required for the distributed `sw` binary, with where that notice is delivered; if a required notice has no shipped location, stop and ask the user before release → evidence/html-dependency-check.md".

8. In `design.md`:
   - At line 10, replace `cli/lib/src/commands/pr.dart:11-24`, `48-75` with `cli/lib/src/commands/pr.dart:12-26`, `54-87`.
   - At line 18, replace `cli/lib/src/commands/pr.dart:67-74` with `cli/lib/src/commands/pr.dart:76-79`, `86`.

CHANGES_APPLIED: yes

## Rebuttals

None yet.

## Required change application

The coordinator applied Required Changes 1-8 after this review. D2 now distinguishes parsed record semantics from legacy-file byte copying. Proposal, delta and shim-test scope follow S2. C12/C13 and their task/comment destinations are recorded. The parser failure/resource rows and malformed/deep HTML tests are explicit. Task 4.4 records dependency/licence evidence and the notice-delivery gate. Dispatch citations were refreshed. `openspec validate native-cli-pr-pair-flow --strict`, the release-notes check and `git diff --check` passed. These are coordinator checks, not additional reviewer execution. The user's notice-delivery choice is pending; no dependency or implementation has been added yet.
