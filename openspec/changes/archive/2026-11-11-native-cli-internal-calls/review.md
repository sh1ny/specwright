# Review

## Metadata
- **Round:** 1 (re-check of Required Changes)
- **Prior round:** none
- **Reviewer:** cross-model CLI (OMP)
- **Reviewed:** Requested sections of `openspec/changes/native-cli-internal-calls/design.md` and its `specs/native-cli/spec.md`; cited portions of `snapshot.dart`, `reviewers.dart`, `git_common.dart`, `gitbutler_backend.dart`, `tool_runner.dart`, `plan.dart`, `workflow.dart`, `exec_inherit.dart`, `bounded_run.dart`, `undo_plan.dart`, `commands/finish.dart`, and `evals/pr-pair/test_workflow_transport.py`.
- **Citation boundary:** Unchanged references to `cli/lib/src/vcs/jj_backend.dart`, `cli/lib/src/vcs/scripts.dart`, and `cli/lib/src/pr/text.dart` were treated as untracked and not opened. Their claims were not re-reviewed.

## Findings

### M1 — Fixed
`openspec/changes/native-cli-internal-calls/design.md:85-88` now requires literal self-launch argument heads, fixes the evaluator to `PrContext.bounded`, rejects nonliteral self-launch lists, checks script-name literals away from launches, and specifies count-preserving negative fixtures.

The argument heads match `cli/lib/src/process/bounded_run.dart:83` and `cli/lib/src/pr/snapshot.dart:492-500`. The spec includes changed-subcommand, missing-bound, nonliteral-list, and indirect-script cases at `openspec/changes/native-cli-internal-calls/specs/native-cli/spec.md:113-119`. Decision-summary row D7 matches at `design.md:127`.

### M2 — Fixed
`openspec/changes/native-cli-internal-calls/design.md:60` explicitly includes `readFull`, preserving printed output, exit 1 for `error: not_found`, and the exit-3 failed-read stop. These distinctions match `cli/lib/src/pr/snapshot.dart:348-352`.

Compact and spaced `not_found` coverage is specified at `design.md:60,96`; decision-summary row D4 includes `readFull` at `design.md:124`.

### M3 — Fixed
`openspec/changes/native-cli-internal-calls/design.md:96` now cites the authorized, requester-verified tracked file with narrow range `evals/pr-pair/test_workflow_transport.py:24-45`.

That range contains the recording scripts, exit-92 probes, log reset, and assertion that no sentinel ran.

### M4 — Fixed
`openspec/changes/native-cli-internal-calls/design.md:143` carries S7 as C7, retaining both bash transports until `native-cli-launcher`, with exactly one durable destination: the `runFramed` doc comment in `cli/lib/src/vcs/tool_runner.dart`.

The transport descriptions match `cli/lib/src/vcs/tool_runner.dart:239-250` and `cli/lib/src/fence/exec_inherit.dart:64-69`.

### M5 — Fixed
`openspec/changes/native-cli-internal-calls/design.md:21,44` correctly places Git’s `not_fast_forward` check before exit-3 mapping, matching `cli/lib/src/vcs/git_common.dart:118-124`. D2 retains the user’s mapping decision at `design.md:48`.

The resource row at `design.md:209` correctly identifies plain GitButler pull as unbounded `runTool`, matching `cli/lib/src/vcs/gitbutler_backend.dart:670-674`. `cli/lib/src/vcs/tool_runner.dart:184-199` confirms that path supplies no cap. No cap is added.

No new Critical or Moderate problems found in the scoped edits.

## Verdict
VERDICT: APPROVE_WITH_CHANGES
CHANGES_APPLIED: yes