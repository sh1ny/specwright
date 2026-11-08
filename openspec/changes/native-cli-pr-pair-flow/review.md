# Review

## Metadata

- **Round:** 2 (required-changes recheck; not a new full review)
- **Prior round:** Round 2 full review, APPROVE_WITH_CHANGES: no Critical findings, two Moderates (M-1 nested `fetch-main` project source, M-2 unrecorded store network gap), one Suggestion (S-1), and three Required Changes.
- **Reviewer:** cross-model CLI (claude, claude-opus-5-5)
- **Reviewed:** `review.md`, `design.md` (D5, Decision summary, Carried constraints) and `specs/pr-script-runtime/spec.md` for `native-cli-pr-pair-flow`.
- **Source read:**
  - `skills/specwright-pr/scripts/pr-pair.sh` (2574-2603, 2700-2713)
  - `cli/lib/src/commands/vcs.dart` (40-59)
  - `cli/lib/src/vcs/scripts.dart` (115-161), `vcs/plan.dart` (25-44), `vcs/git_common.dart` (105-118)
  - `cli/lib/src/vcs/jj_backend.dart` (line search for `networkJj` and `jjFetchMain`)
- **Verification limits:**
  - Tracked status and modes come from the coordinator's manifest; every source file opened is a regular stage-0 file there.
  - `as.sh`, `vcs.sh` and `test_pr_shims.py` are not in the manifest and were not reopened. The claim that `as.sh` resolves only from the current directory, and that a store has no `VERSION`, is carried from the prior full review.
  - Decisions and findings outside Required Changes 1-3 were not reopened. No referenced stores were involved, and no tests or code were run.

## Findings

### Critical (blocking)

None.

### Moderate

No open Moderate findings. Both findings from the prior review are resolved:

| Finding | Status | Evidence |
|---|---|---|
| M-1 project source for the nested `fetch-main` hop | Fixed by Required Changes 1 and 2 | `design.md:64`; `spec.md:142-143`. Source agrees: `fetch-main` is reached only inside the `--code` branch (`pr-pair.sh:2578-2585`), `openSession` resolves `code` (`vcs.dart:49`), and the hop's two `as.sh` calls are login resolution (`scripts.dart:131`) and the fenced command (`scripts.dart:158`). |
| M-2 unrecorded store network gap | Fixed by Required Change 3 | `design.md:100`. Source agrees: cleanup-plan prints the VCS pull plan (`pr-pair.sh:2708`), the plan is a `vcs.sh` command (`plan.dart:29-41`), and the Git network path uses the same unselected `fenceLogin` and `runAs` calls (`git_common.dart:111-113`). |

### Suggestions

- **S-1 (still open, nonblocking).** `pr-snapshot.sh:85-92` and `pr-reply.sh:51-58` also resolve only from the current directory, and neither gets `--project`. During apply, check the store-caller instructions and either confirm no caller starts them from a store or record the gap beside C11.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. In `design.md` D5 **Choice**, replace "Propagate the explicit code-project selection through that hop so it resolves the right binary without changing the target repository." with: "The nested hop's project is branch-check's own `--code`, in the absolute form VCS resolved for its session, since fetch-main is reached only with `--code`; no handoff record is added. Both as.sh calls in that hop, login resolution when no `--login` was given and the fenced fetch, carry `--project <that directory>` without changing the target repository or login." In the same **Choice**, replace "observing the one permitted nested invocation and its project selector, target and login" with "observing the permitted nested fence hop, including its login-resolution call when no `--login` is given, and its project selector, target and login".
   - **Rechecked: applied.** Both replacements match at `design.md:64`, and the old phrases are gone. The D5 summary row at `design.md:82` was updated to match.
2. In `specs/pr-script-runtime/spec.md`, scenario "Nested VCS fetch retains its temporary fence hop":
   - Replace the WHEN line with "**WHEN** non-Git branch-check with `--code` invokes native VCS fetch-main for a store".
   - Replace the THEN line with "**THEN** only that nested fence path may invoke as.sh and sw as, each as.sh call in it (login resolution when no `--login` was given, then the fetch) receives `--project` with the resolved `--code` directory, the target cwd and login remain the store's, and the other workflow paths do not gain script launches".
   - **Rechecked: applied.** The wording at `spec.md:142-143` matches. The only difference is that the flags are written without inline-code backticks, as other scenarios in the same requirement group do (`spec.md:181`, `193`). This does not change the meaning or how the scenario is tested, so no further edit is required.
3. In `design.md` `## Carried constraints`, add: "**C11:** Network operations run through `sw vcs` on a GitHub-origin store other than D5's branch-check fetch-main, including the `vcs.sh pull` that cleanup-plan prints for a jj store, keep their existing as.sh hop without a project selector, so they still stop with sw_missing from the store until native-cli-internal-calls. Kind: deliberate gap. Destination: ADR 0031."
   - **Rechecked: applied.** `design.md:100` matches exactly and has one destination.

No required edits remain.

CHANGES_APPLIED: yes

## Rebuttals

None. M-1 and M-2 were fixed as cited above, not rebutted.