# Review

## Metadata

- **Round:** 2
- **Prior round:** 1, APPROVE_WITH_CHANGES with M1 (D3 "bumped" defeated by merging main), M2 (subagent route overwrote `review.md`), M3 (D8 blamed the change for an invalid installed schema) and S1-S5. All were applied and re-checked, and the changes were marked applied. Commit 502db47 then amended design.md (the #97 diagram order, plus a new Flow & State Gaps entry), which voided that verdict.
- **Reviewer:** fresh-context subagent (Claude Code, `specwright-reviewer` role, Opus 5.5). Project skill loaded: `github-account-switch-race-fencing`. I applied it to the #93 decision (D2 removes the unfenced read; publish keeps the fenced one) and to the fenced fetch named in D3. I made no authenticated `gh` call for this round.
- **Reviewed:**
  - Change artifacts: `proposal.md`, `design.md` (whole document, plus `git show 502db47`), the six delta specs (`change-finish`, `debugging`, `install-update`, `planning-stores`, `releases`, `review-routes`), round 1 `review.md` and `tasks.md` (#97 rows and section 4).
  - ADRs: 0007, 0008, 0009, 0010 by reference, and 0011.
  - `scripts/update.sh`: the header contract for stage, swap, recover and finish; `do_plan`'s recover-first path; `do_stage`; `swap_store_prepare`; `store_busy_reason`; `dirty_paths`; `written_by_update`; `cmd_store_check` in both modes; `checkout_id`, `mk_group` and `build_groups`; `check_change`, `installed_note`, `inflight_entries`, `make_plan` and `cmd_swap_check`. These include the uncommitted working-tree diff.
  - `README.md`: the update prompt's plan, stage and swap steps, the refusal handling, and Step 7's `recover --rollback`.
  - `skills/specwright-review/scripts/review-run.sh`: `validate_design`, `codex_windows_sandbox`, `command_line`, the OMP `agent_end` reader with `MAX_EVENT_LINE`, `design_scratch`, and `record --scratch`/`--out`.
  - `skills/specwright-release/scripts/release.sh`: the `check --main` and `untagged --local` usage and dispatch.
  - `evals/update/test_store.py`: the new `TestStagingPerCheckout` tests, from the working-tree diff.

<!-- This verdict covers only the contents reviewed. Editing proposal, specs or design afterward (other than applying Required Changes) voids it. -->

## Findings

### Critical (blocking)

None.

### Moderate

**M1. #97: once two checkouts have each had a swap refused, rerunning the update prompt in either one never gets either update through. The new Flow & State Gaps entry says it does.**

The amendment says: "Each one's staging makes the store busy for the other, so neither swap runs. ... the user recovers one checkout (its own staging only) and the other then swaps." The code and the README do not do that.

- A refused swap keeps its staging and journal. `swap_store_prepare` (`update.sh:748-749`) releases the gate and exits 1 without removing anything. The `planning-stores` scenario "Another checkout's staging makes the store busy" requires this: "B's own staging remains for `recover`".
- The only documented way for a user to "recover" is to rerun the update prompt. README Step 4 says that on a refusal the prompt reports that nothing changed and STOPs (`README.md:230-235`). The next run's first `plan` runs `recover` (`README.md:198-201`, `do_plan`). That recover discards the leftover, and then the same run goes on to `stage`, which creates a new `.specwright-update-schemas-<id>` (`do_stage`, `update.sh:656-690`). Nothing in plan or stage checks for another checkout's staging; `store_busy_reason` is called only from `cmd_store_check`.

Timeline: A and B both swap and are refused. Each is refused by the other's staging, or both are refused because the store sat on a change branch. Both now have staging in the store.
1. The user follows A's busy message ("finish or recover it from that checkout") and reruns the prompt in B. B's recover discards `<idB>`, B stages `<idB>` again, and its swap is refused by A's leftover `<idA>`.
2. The user reruns the prompt in A. A's recover discards `<idA>`, A stages `<idA>` again, and its swap is refused by the new `<idB>`.

This repeats for as long as the user follows the prompt. The only exits are undocumented: a bare `update.sh recover` (the tests use it, `test_store.py` `self.ok(self.b, dl, "recover")`, but the user has only the prompt) or a manual `rm -rf`.

The trigger does not need a race. Two projects on one store that both try a workflow update while the store is on a change branch (a release day) both end up with a refused swap and a leftover staging directory. Before D7, B's stage pre-clean deleted the shared directory. That was #97's data loss, but it also kept this from looping. D7 trades that for a loop the design records as solved.

A related gap is not recorded anywhere. `cmd_store_check --mode rollback` uses `store_busy_reason` with `written_by_update`. So a foreign `<idB>` also refuses A's `recover --rollback` after a failed Step 7, until B is cleaned up, and B is cleaned up only through the loop above. The spec scenario "Discard after a refused swap keeps the other checkout's rollback copy" passes only because its B runs a bare `recover` first.

### Suggestions

- **S1 (D7, busy message).** Whatever M1's fix, make the busy message name an action that works from the prompt. Today it says "finish or recover it from that checkout", and in practice that means "rerun the update there". If M1's fix makes a refused swap discard its own staging, the remaining foreign staging can come only from a live or interrupted update in that checkout, and "rerun the update prompt in that checkout" is then accurate.
- **S2 (review-routes delta, carried over from the round-1 nit).** The scenario "Subagent design review without a verdict" still says the subagent "writes a `review.md`". Since D5 it writes a scratch result file, so name the scratch file to keep the scenario assertable as written.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. **M1: `design.md` (D7, Failure & Visibility, the Flow & State Gaps entry "both checkouts staged before either swapped"), `specs/planning-stores/spec.md`.** Make the two-checkout case converge through the documented prompt.
   - Preferred: a swap refused before its first rename (any `store-check --mode swap` stop, `verify` or `swap-check` refusal) discards this update's own staging and journal before it exits, exactly as `recover`'s "swap not started → discarded" path would. With that, two refused checkouts leave the store clean, and the next prompt run in either one swaps.
   - Acceptable alternative: `plan` (and so `stage`) refuses before staging while another checkout's `.specwright-update-schemas-*` is untracked in the store, naming it. Keep the patch code-only path working when the schema is byte-identical.
   - Either way:
     - rewrite the Flow & State Gaps entry to describe the real convergence;
     - change the `planning-stores` scenario "Another checkout's staging makes the store busy" so that its THEN matches ("B's own staging is removed", or "B stages nothing");
     - add a scenario: "**WHEN** A and B both had a swap refused with their staging left in the store, and the user reruns the update prompt in A / **THEN** A's update swaps, or B's leftover is named and the next rerun in A swaps, with no step outside the prompt";
     - record that a foreign staging directory also refuses `recover --rollback` (the Failure & Visibility table), so a user whose Step 7 failed knows which checkout to clean up first.

CHANGES_APPLIED: no

## Rebuttals

- **M1 fixed, preferred option (the user's choice).** D7 now says a swap refused before its first rename (a busy store, changes in flight that differ from the plan, a failed verification) removes this update's staging directories and journal, as `recover` does for a swap that never started; the alternative is recorded as rejected there. The patch code-only path is not a refusal and is unchanged. Flow & State Gaps "#97, both checkouts staged before either swapped" describes the real convergence. `planning-stores`: the requirement text adds the rule; "Another checkout's staging makes the store busy" now ends with B's staging and journal removed; "Discard after a refused swap ..." has B's refused swap remove only its own; new scenario "Both checkouts staged before either swapped" (A refused and cleaned, B swaps, A's rerun not refused for staging). The requested scenario's starting state, two refused swaps that left their staging behind, can no longer arise, so the new scenario starts one step earlier. Failure & Visibility gains the refused-swap row and the `recover --rollback` row blocked by B's staging. Tasks 4.1/4.2 and the test map carry the new test.
- **S1 applied.** The busy message says `finish or recover it by rerunning the update in that checkout`.
- **S2 applied.** "Subagent design review without a verdict" names the scratch result file.
