# Review

## Metadata

- **Round:** 2
- **Prior round:** Round 1 was APPROVE_WITH_CHANGES (C1 re-request ordering, M1 #58 eval fixture, M2 branch-check scenario precondition). All four Required Changes were applied and re-checked (CHANGES_APPLIED: yes), and S1-S4 were applied or accepted. A later edit to the ADRs section's ADR 0004 note voided that verdict.
- **Reviewer:** fresh-context subagent (Claude Code, specwright reviewer)
- **Re-check of Required Changes (same round):** design.md D2 (Scope of the Settings rule), D4 (head selection), D5 (local-mode row), the ADRs note; specs/feedback-passes/spec.md ("Feedback snapshots the pushed head before re-requesting"); pr-pair.sh:556-564 and :607-635.
- **Reviewed:** proposal.md, design.md (whole, with particular attention to the ADRs section and D2, D4, D5, D6), specs/{change-finish,planning-stores,feedback-passes,pr-evidence,pr-script-runtime}/spec.md, tasks.md (context only); docs/adr/0004-process-scoped-github-identity.md, openspec/architecture.md (index head), openspec/roadmap.md (`default-identity-fencing` entry); skills/specwright-pr/SKILL.md (Settings: identity and **Re-request review** :46-52, change PRs :59-62, ship 4-6 :70-76, feedback 1-11 and After the limit :83-112, watch :119-121, **Cleanup after merge** :131-136); skills/specwright-finish/SKILL.md (Resume :15-47, Steps :49-62, local and pr :64-76 including **After the PR is merged** :76); skills/specwright-pr/scripts/pr-pair.sh (norm_pr/discover :542-565, cmd_discover :592-596, expected_set :607-635, request_state :1577-1589, cmd_cleanup :1862-1891, COMMANDS :1894-1897); skills/specwright-pr/scripts/pr-snapshot.sh (resolve_first_seen and prepare_cfg :380-435).

<!-- This verdict covers only the contents reviewed. Editing proposal, specs or design afterward (other than applying Required Changes) voids it. -->

## Findings

### Critical (blocking)

None.

### Moderate

**M1. D2's ordering fix leaves the skill rule that step 9 delegates to unchanged, and that rule is the #57 behaviour itself.**
Feedback step 9 does not describe how to re-request. It says "**re-request review** on its PR (see Settings and identity)" (skills/specwright-pr/SKILL.md:103). The resume `todo` rows also say "push, re-request, reply ... as in steps 7-9" (:85). The rule they point to, the Settings **Re-request review** paragraph (:52), says: "Unless a comment from its poster with that exact body was created at or after that push time, post it ... If the push time is not found, post anyway." D2's **Ordering** names only "feedback step 9 and the resume `rerequest` row". The proposal, design, specs and tasks never mention the Settings paragraph (a grep for "Settings" or "post anyway" finds nothing in the change), and task 3.3 edits only "feedback steps 2 and 9".

After apply, step 9 would say "snapshot, run `pass plan`, post only the rows not `done`", while the paragraph it cites still says "push time not found → post anyway". When the activity log lacks the push, which is exactly the #57 case, an agent that follows the cited rule posts a request on every pass resume. The script tests (`test_rerequest_*`) and the step-9 text test would still pass, so the regression would ship without any test failing.

Watch's re-requests (CI fix :124, archive before merge :127) also use this paragraph and run outside a pass, where "post anyway" once per pushed head is still the right rule. So the paragraph has to be scoped, not deleted.

### Suggestions

- **S1. The edited ADR 0004 note is now correct. It could be more precise about the store-backed `--head` source and about `[as]`.** I checked it against the source. It agrees with D4: repo-local `--head` comes only from `discover --state merged`'s `head_sha`, never from `gh pr view`. It agrees with specwright-finish:76, where the trigger `gh pr view <branch> --json state,headRefOid` stays, and task 4.3 allows dropping `headRefOid`. It agrees with specwright-pr:135, which has no `gh pr view` today and will gain `discover`. It also describes ADR 0004 correctly: the ADR names "one `gh` call even with a login configured: `specwright-finish` checks the merged PR with a plain `gh pr view` (also tracked in #38)", and roadmap.md:24 puts that exception in `default-identity-fencing`. Two small imprecisions remain. First, "`discover --state merged`, the source of `branch-check --head`" covers only repo-local cleanup. Store-backed `--head` comes from `cleanup-plan`'s `pr.head_sha` (`expected_set` → `discover`, with the store read under `read_store_as`, pr-pair.sh:628-629). Second, "runs through `as.sh`" holds only when a login is configured, per `[as]` (SKILL.md:46). With the default empty login, it is the ambient-account exception that ADR 0004 also lists. A wording such as "runs under `[as]` (repo-local) or inside `cleanup-plan` with its store fence (store-backed)" would be exact. This has no effect on behaviour.
- **S2. D4 does not say which merged PR supplies `--head` when there are several.** `discover` returns `prs` newest first, plus `newest` (pr-pair.sh:556-564). A reused branch name can have an older merged PR. If the agent picks it, `branch-check` sees a head that is not the current tip's, and the result falls to `lacking`. That is the safe outcome, but it is a confusing report. Name `newest` (with `--base <main>`) as the source, as `cmd_cleanup`'s `pr_of` effectively does.
- **S3. D5's Rejected rationale says the directory "also covers the bulk path in local mode", but no resume row turns local-mode "A on main, no M, no B" into done.** The spec scenario "Bulk archive commit" holds as written, because it has both branches merged, so in local mode each has its own `merge: <name>` (row "M, not B"), and in pr mode it lands in D6's row. The single-branch local bulk case (specwright-finish:61, "one archive commit naming them all", merged as `merge: <first change>`) still matches no row for the other change. Drop the local-mode claim, or note that case as out of scope.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. **M1 (design.md D2, Ordering sub-bullet):** Add that the Settings **Re-request review** paragraph in `skills/specwright-pr/SKILL.md` is reworded with two scopes. Inside a feedback pass (fresh step 9 and the resume `rerequest` row), the post-push snapshot and the `pass plan` `rerequest` row decide, and "if the push time is not found, post anyway" does not apply. Outside a pass (watch's CI-fix and archive-before-merge re-requests), the existing once-per-pushed-head rule stays. In specs/feedback-passes/spec.md, extend the scenario "Feedback snapshots the pushed head before re-requesting" so its THEN also asserts that the Settings re-request rule does not tell the agent to post when the push time is missing inside a pass. (A matching edit to tasks.md 3.3, naming the Settings paragraph and asserting it in `test_feedback_snapshots_pushed_head_before_rerequest`, follows from this but is not part of the verdict.)

Re-check results (same round; only the Required Change and the S1-S3 edits were re-checked):
1. Satisfied. design.md D2 has a new sub-bullet, "Scope of the Settings rule". It names the Settings **Re-request review** paragraph (`SKILL.md:52`) and its "post anyway" sentence, and splits the rule in two. Inside a feedback pass, where a pass record exists, the `pass plan` `rerequest` row alone decides. Outside a pass (watch's CI-fix and archive-before-merge pushes), the existing once-per-pushed-head rule stays. In specs/feedback-passes/spec.md, the THEN of "Feedback snapshots the pushed head before re-requesting" now asserts that "post anyway" applies only outside a feedback pass, and that THEN can be asserted by a text test.

S1-S3 re-check:
- S1: the ADR note now separates the two sources. Repo-local `--head` comes from `discover --state merged` run as `[as]`, which goes through `as.sh` only when a login is configured. Store-backed `--head` comes from `cleanup-plan`, under its internal store fence. This matches D4's last sub-bullet, `expected_set` (pr-pair.sh:607-635, `read_store_as` at :628) and ADR 0004's Decision text. The `gh pr view` exception is still described correctly.
- S2: the claim is accurate. `discover` sorts `prs` by `-number` (pr-pair.sh:556), filters by base and state after that (:558-562), and `newest` is `prs[0]` (:564). With `--state merged --base <main>`, `newest` is the merged PR with the highest number into main. "The PR most recently opened from the branch" is a fair reading, since PR numbers grow with creation. The stated fallback (an older PR's head keeps the branch) is consistent with branch-check's `lacking` path.
- S3: D5 adds a `local` row after `M, not B`: A on main through the archive directory, not M, not B → repo done. Rows are matched in order, and none of the earlier rows (uncommitted archive, A on branch with B, store-only, M and B, M not B) can capture this state, so the placement is sound. The exact last-component match still keeps "Only a longer change name is archived" reporting no archive. No new contradiction with the specs or D6.

- **S4 (from the re-check, not blocking).** D5's directory check and the new `local` row are meant for the planning repo. The spec requirement says "a repo SHALL count ... when the planning repo's main holds the archive directory". In a store-backed pair, the code repo is then evaluated with the same rows. If an implementer applies the store's directory fact to the code repo, the new row, which comes before the "code repo with no A, M or B" rows, would mark a code repo with no branch and no merge as done. That repo would then skip the "report and ask" check for missing code work. Say in D5 that fact A from the directory applies only to the planning repo, and that a store-backed code repo keeps its own rows.

<!-- yes (applied, and re-checked by the reviewer - only the reviewer sets it) | no (outstanding) | n/a (any other verdict) -->
CHANGES_APPLIED: yes

## Rebuttals

<!-- Author: fixed (cite) or rebutted (reason) per finding. A Critical/Moderate rebuttal counts only once marked "accepted by reviewer". -->

- **M1 (round 2):** fixed. design.md D2 adds "Scope of the Settings rule": inside a feedback pass the `pass plan` row alone decides and "post anyway" does not apply, while outside a pass (watch's CI-fix and archive-before-merge pushes) the once-per-head rule stays. specs/feedback-passes, scenario "Feedback snapshots the pushed head before re-requesting", now asserts that scoping. tasks 3.3 edits and tests the Settings paragraph. **Accepted by reviewer.**
- **S1:** applied (ADR note: repo-local `--head` from `discover` run as `[as]`, through as.sh when a login is configured; store-backed from `cleanup-plan`'s internal fence). Accepted by reviewer.
- **S2:** applied (D4: `--head` is `discover`'s `newest`, the highest PR number, verified at pr-pair.sh:556-564; an older-PR match keeps the branch). Accepted by reviewer.
- **S3:** applied (D5: a new `local` row after `M, not B` for an archive that reached main through another change's merge, with test `test_finish_resume_local_bulk_archive_on_main_is_done` in tasks 5.1). Accepted by reviewer; see S4 from the re-check.

