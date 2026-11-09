# Review

## Metadata

- **Round:** 3 required-changes recheck
- **Prior round:** APPROVE_WITH_CHANGES (round 3): 1 Critical, 5 Moderate and 4 Suggestions, giving ten Required Changes. The owner approved all ten revisions and the behavioural choices on 2026-11-10 ("yes go ahead.").
- **Reviewer:** Claude (claude-opus-5-5), fresh-context subagent (Claude Agent SDK), read-only. This recheck covers only the ten round-3 Required Changes. It is not a new full review.
- **Reviewed:** review.md (round 3), proposal.md, design.md, tasks.md, and specs/{native-cli,pr-script-runtime,vcs-backends,task-commits,change-finish}/spec.md. Source and tests checked: `evals/pr-pair/test_workflow_parity.py` (test names; lines 381-405), `evals/git-workflow/test_instructions.py:614-640`, `openspec/strategy.md:13`, `openspec/architecture.md:150` and `cli/test/settings/reviewer_config_test.dart:110-143`. The review instruction and template come from `openspec/schemas/specwright/schema.yaml` and `templates/review.md`. Nothing was run. The author reports that strict `openspec validate` and the diff checks pass, and I did not re-run them.

## Findings

Round-3 findings and their status after this recheck:

### Critical (blocking)

**C1. The D8 settings "stop" had no mechanism, and policy's raw YAML integers were missing from the producer table. Verified resolved.**
- D8 now states the rule exactly. The rules layer never returns a `BigInt`. `duration` (timeout and poll_interval), `max_fix_rounds` and `reviewersOf` report `bad_setting` and substitute the defaults 1200, 300 and 2.
- D8 now spells out what each caller does:
  - `context` stops with exit 2 before it writes any config.
  - `workflowContexts` collects problems, and `rounds` and `pass` stop with exit 2.
  - Policy's main side stops through `bads`.
  - Policy's head side lists the key in `invalid` and uses the defaults in `values`, `drift`, `pr.reviewers` and the reviewer config.
- The producer table has a new row for policy's raw values (`policy.dart:218-225`, `:256-257`) using `settingText`.
- Both new native-cli scenarios exist with red test-map rows (tasks.md rows 68-69). Row 68 targets `test_rounds_without_feedback_trailers`, the test that holds the `max_fix_rounds: 9999…` setting at `test_workflow_parity.py:386`, and turns it into an explicit difference from the oracle.
- Task 2.5 matches.

### Moderate

**M1. The reviewer and policy integer claims were wrong. Verified resolved.**
- The D8 JSON-input row no longer cites `:597`.
- A `cfg.now` note follows the table: it stays `num`-typed, and an oversized value stops in `_formatIso` (`reviewers.dart:406-413`). The note also says policy compares strings only.
- D2 now names reviewer-config `timeout` and feedback `round`.
- The "An integer that cannot be held exactly" row is remapped to `cli/test/pr/reviewers_test.dart` under "a timeout beyond 64 bits is a config error". Its THEN now reads "config error with exit 2 and nothing on stdout".

**M2. A7 and A3 ignored lone surrogates. Verified resolved.**
- A7 now says "including strings holding lone surrogates".
- D1 names the fallback: a small string writer that emits lone surrogates raw, with `JsonEncoder` for everything else. D7, the decision summary and task 2.1 refer to the same fallback.
- A green row in `reviewer_config_test.dart` pins a fixed pre-change digest (tasks.md row 70, with a matching native-cli scenario).

**M3. `sw` read its own documents as text. Verified resolved.**
- C12 is added with the requested text. Kind: deliberate gap. Destination: doc comment on `cli/lib/src/pr/text.dart`. Task 2.8 carries it.
- C2 and the native-cli requirement name C12 as the only exception.
- The proposal now says the in-binary snapshot regex readers are an explicit temporary gap. That narrows the original claim in substance.
- The red row "the reviewers document keeps the compact keys the watcher reads" is present (row 71).
- Task 3.2 now scans Dart consumers and allows only C12.

**M4. The `--slurp` inventory was incomplete. Verified resolved.**
- Task 4.1 changes the `:405` injection to `api --paginate (--slurp )?repos/o/n/pulls`.
- The "Unknown read permits no follow-on mutation" row is red.
- In pr-script-runtime, the requirement is scoped to "a list read that decodes whole pages". It states that `item-issues` keeps `--paginate --jq` and its `unreadable response` refusal. D4 matches.

**M5. The `gh` floor inventory was incomplete. Verified resolved.**
- Line 640 (`PR workflow not ready: gh 2\.40\+`, confirmed in source) is now in both the proposal and task 4.3.
- "gh missing" is remapped to `test_install_reports_pr_workflow_not_ready` (red).
- `openspec/strategy.md:13` and `openspec/architecture.md:150` (both confirmed to state 2.40) are in the proposal's "Skills and scripts that change" and in task 4.3. Accepted ADRs stay unchanged.

### Suggestions

- **S1. Verified resolved.** The test-map table no longer has a blank line, so every row sits under the header.
- **S2. Verified resolved.** D6 and task 6.2 now say "every package in the runtime closure (`dart pub deps --no-dev`)".
- **S3. Verified resolved.** D3 now says "flags are declared with `negatable: false`".
- **S4. Verified resolved.**
  - "Line separators parse back" is added and mapped (row 43).
  - The historical title "Line separators stay escaped" is kept, because strict validation won't allow dropping it. Its THEN now asserts the parsed character, the same as the new scenario. design.md explains why both exist, and both are mapped (rows 43 and 72). This keeps the current scenario's name while removing the contradiction with S5, so I accept it.
  - The Resource Bounds JSON-file row now lists workflow snapshots and feedback intent and records.

Two notes for implementation. They are not blocking and don't reopen any finding:
- **Row 70 names a test that doesn't exist yet.** The test "a lone surrogate in a report string keeps its pre-change digest" isn't in `reviewer_config_test.dart`. The existing test `a lone surrogate encodes as ? (errors="replace")` at `:116-128` pins a login surrogate. Task 2.1 must capture the report-string digest from the current code before the encoder changes.
- **One existing test conflicts with D8 and C11.** `reviewer_config_test.dart:130-142` (`U+2028 stays raw and a timeout past 64 bits keeps its digits`) passes a `BigInt` timeout into `reviewerConfigBytes`. Task 2.5 or 2.7 should retire or rewrite it.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

All ten round-3 Required Changes are applied and verified above:

1. (C1) Applied: one rule for oversized integer settings, with the behaviour of each caller, the policy raw-value row, two new scenarios with red rows, and task 2.5.
2. (M1) Applied: the reviewer and policy integer claims are corrected, and the row is remapped to `reviewers_test.dart`.
3. (M2) Applied: A7 is widened, the D1 surrogate-string fallback is added, and the digest row exists.
4. (M3) Applied: C12, the narrowed proposal, the compact-keys row and the wider task 3.2 scan.
5. (M4) Applied: the `--slurp` injection pattern, the red row and the `item-issues` scoping.
6. (M5) Applied: line 640, the "gh missing" remap, and strategy.md and architecture.md.
7. (S1) Applied.
8. (S2) Applied.
9. (S3) Applied.
10. (S4) Applied, with the historical scenario title kept for strict validation as explained in design.md.

CHANGES_APPLIED: yes

## Rebuttals

None.