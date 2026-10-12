# Review

## Metadata

- **Round:** 1
- **Prior round:** none
- **Reviewer:** fresh-context subagent (Claude Code, specwright-reviewer role); project skills named: none
- **Reviewed:** proposal.md, design.md, specs/review-routes, specs/preship-review, specs/install-update, specs/pr-watch, specs/pr-descriptions; schemas/specwright/schema.yaml (review step, apply drift rule); skills/specwright-commit/SKILL.md; skills/specwright-pr/SKILL.md (ship, feedback step 3, watch steps 1-3); skills/specwright-pr/scripts/pr-pair.sh (round counting, lines 88-89, 1225-1234); skills/specwright-pr/scripts/pr-snapshot.sh (state dir, lines 389-404); skills/specwright-finish/SKILL.md; skills/specwright-roadmap/SKILL.md (baseline review); agents/claude and agents/omp specwright-reviewer.md; README.md install Steps 6-7; templates/openspec/specwright.yaml; openspec/specwright.yaml; docs/adr/0003; issues #69 and #78 (read-only); `claude --help` and `omp --help` (read-only, flag check)

<!-- This verdict covers only the contents reviewed. Editing proposal, specs or design afterward (other than applying Required Changes) voids it. -->

## Findings

### Critical (blocking)

**C1. On the `claude` and `omp` routes the reviewer cannot see the diff it is asked to review.**
D3 gives the Claude route no shell (`--disallowedTools ... Bash ...`) and the OMP route `--tools read,grep,find,ls` (no `bash`). The Resource Bounds row "Diff sent to the reviewer" says "the prompt names the range, not the diff text", so the reviewer is expected to compute `<main>...HEAD` itself. Without `git`, neither route can: it cannot list the changed files, see deleted lines, or tell new code from old (git objects are zlib-compressed, so `read` does not help). The store range is worse: it lives in another checkout, and Claude's file tools are confined to the working directories unless `--add-dir` names the store. Only Codex (`-s read-only` still runs commands) can see the change. The output will still validate against the findings schema, so the gate records a pass for a review that never saw the change. That is the harm the Mechanism Ledger's first row exists to prevent ("ship unreviewed code: harm nobody catches"). The design also contradicts itself here: the ledger builds "nonce-delimited untrusted regions in the prompt", which only make sense if diff text is in the prompt.

### Moderate

**M1. The Claude command line is a denylist, so the reviewer can still write, which breaks the review-routes isolation requirement.**
`--disallowedTools Edit Write Bash Task Skill 'mcp__*'` leaves `NotebookEdit`, `WebFetch` and, on Windows (this repo's platform), the `PowerShell` tool enabled. The installed `claude 2.1.296` documents an allowlist, `--tools <tools...>` ("Specify the list of available tools from the built-in set"), and `--restricted`, which also confines file tools to the working directories. The requirement "allows read-only tools only" and the scenario "Reviewer tries to write" only hold with an allowlist. The scenario is written for Codex only, so no test would catch the Claude gap.

**M2. Pre-ship fix commits have no defined subject or trailer, and the obvious one consumes the PR's fix rounds.**
D6 rejects sharing `pr.max_fix_rounds` because PR rounds use "a different trailer", but the design never defines a pre-ship fix commit's subject or trailer; D8 covers only `amend specs`. `pr-pair.sh rounds` counts every subject matching `address review feedback` when the branch has no `Feedback-Round:` trailer yet (`pr-pair.sh:89`, `:1231-1234`). An agent fixing pre-ship findings will naturally reuse `fix(<change>): address review feedback`. With two pre-ship fix commits, the first PR feedback pass then sees round 2 = `max_fix_rounds` and goes straight to After the limit, without fixing anything.

**M3. The pass-to-merge rules for #69 can stall watch when branch protection dismisses approvals.**
`specwright-pr` watch step 3 (`SKILL.md:128`) says the archive commit "is a new head that branch protection may treat as needing fresh approval", which is why today's flow re-requests review. Under D7 the archive head gets no request. Readiness requires `merge_state` CLEAN, so on a repo that dismisses stale approvals the head stays BLOCKED. Nobody is asked to re-review, and watch loops until the "about 2 hours with no progress" stop. Neither D7 nor the pr-watch spec has a scenario for it.

**M4. Two writers of the record's `outcome`, so a waiver either never turns into a pass or gets miscounted.**
The State & Ownership table makes `run`/`record` the writers of `outcome` and says `waive` "adds waivers only". D6 defines `pass` as "every P0/P1 is in `waivers`". If `waive` does not rewrite `outcome`, the stored outcome stays `blocked` after the user waives, and `rounds`, which counts records with outcome `blocked`, counts a waived review toward escalation. The preship spec scenario "User waives a finding ... the review passes" then depends on whether `gate` reads `outcome` or recomputes it. Five skills consume this contract (D2), so leaving this open makes the implementations diverge.

**M5. The record store conflicts with ADR 0003 without saying so.**
ADR 0003 (in force): "Status, completion and round counts are derived from that evidence [git/GitHub] and never stored separately. Local state is limited to working state that can be rebuilt or safely asked about." D5/D6 derive the pre-ship escalation count (`rounds`) and the user's waivers from machine-local records. The design cites 0003 only as "records are machine-local cache, not evidence". A lost or foreign-machine state dir silently resets the escalation count, and drops waived findings from the PR description (D9 reads waivers from the record). Both may be acceptable, but they are deviations from an in-force ADR. The planned ADR 0007 must state them, or a later change will "fix" them against 0003.

**M6. Store-backed local merge after archive: the gate's "HEAD's parent" rule is undefined for a two-head key.**
Records are keyed `<code head>+<store head>` (D5). In store-backed mode the archive commit lands only in the store (`specwright-finish` step 3), so the code head is unchanged and only the store head moves. D2's gate ("a pass on HEAD, or on HEAD's parent when `archive-only` holds") and the preship scenario "Local merge after archive" do not say which head's parent to take. A direct implementation (code `HEAD^`) finds no record and re-runs a 5-20 minute review before every store-backed local merge. Running `archive-only` in the wrong repo fails safe, but at the same cost.

**M7. The install-update rule still flags supported settings as removed, including on this repo.**
The rule compares keys by bare name (`# key:` at any indentation). Two consequences follow from the template and this repo's file:
- (a) Children of map-valued settings are user data, not schema keys. `openspec/specwright.yaml` has `pr.reviewers.kody-ai`, which appears in the template neither uncommented nor commented, so the new "Key really removed upstream" scenario lists it and asks to remove it on every update. That is the noise #78 reports, moved one level down.
- (b) `login` and `reviewers` appear both uncommented (`github.login`) and commented (`planning_store.login`, `planning_store.reviewers`), so a bare-name match cannot tell "commented only" from "present".

### Suggestions

**S1.** preship-review "A passing review is recorded per head" says "A commit made after it SHALL require a new review, except the change's archive commit". That contradicts the "PR already exists" scenario and D11, under which PR feedback fixes are never re-reviewed locally. Reword it to "a later commit, other than the archive commit, leaves the new head without a pass", so a test of the requirement does not demand gating feedback pushes.

**S2.** Ship step 4a pushes before 4b discovers the PR, but the spec requires the gate "before any push". State that ship runs `discover` and the gate before 4a. Also say whether "first PR" is per change or per repo: in store-backed mode, feedback step 9 can run ship for a code repo whose store PR already exists.

**S3.** D7's prose uses `true`/`false` both for the `archive-only` result and for `pr.review_after_archive` ("On `true`, it posts no review request ... or with the setting `true`, it does what 0.1.13 does"). Name the result (`archive_only: true`) to avoid an inverted implementation. The pr-watch spec says "after watch pushes the archive commit", but `specwright-finish` `## pr` pushes it through ship. Say "after the archive commit is pushed".

**S4.** The review-routes validation requirement covers design reviews from CLI routes (`run --out`). Nothing validates a design review written by the `specwright-reviewer` subagent beyond the existing tasks precheck. State that, or route it through a `record --kind design` check.

**S5.** The pr-descriptions spec lists "each `amend specs` commit" after the design review, but D9 reads only `Amendment:` trailers. Apply-phase drift amendments carry no trailer and are followed by a new design review. Align the spec text with D9: amendments made after the pre-ship review starts, identified by trailer.

**S6.** `gate` returns `stale`, but neither D2 nor the Flow & State Gaps section defines when `stale` differs from `missing`. Define it or drop it.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. **(C1)** In design.md D3 and Resource Bounds, `review-run.sh run` builds the review input itself: `git diff --no-color <base>...<head>` for the code range, and for the store range when `--store` is given, embedded in the prompt file inside the nonce-delimited untrusted region. Record a byte bound for it (for example 1 MB). At the bound, the run exits 1 with `diff_too_large` and the size, and the user chooses to raise the bound or opt out. It never runs a truncated review. Replace the "Diff sent to the reviewer" row accordingly. Add a review-routes scenario: a Claude or OMP review's prompt contains the changed lines of both ranges, and an over-bound diff stops before any reviewer starts.
2. **(M1)** In D3, replace the Claude `--disallowedTools ...` list with an allowlist (`--tools Read,Grep,Glob`, plus `--restricted` if the trial confirms it), and say that the trial verifies the allowlist on Windows. Extend the "Reviewer tries to write" scenario to every route, not only Codex.
3. **(M2)** In D6, define the pre-ship fix commit subject (for example `<type>(<change>): address pre-ship review`) and an optional trailer. Neither may match `address review feedback` or `Feedback-Round:`. Add a scenario: after two pre-ship fix commits, the first PR feedback pass is round 1.
4. **(M3)** In D7 and the pr-watch spec, add: when the archive head is not ready only because `merge_state` is BLOCKED by a required review, watch reports it and asks whether to post the review requests on the archive head. Add a scenario for it.
5. **(M4)** In D6 and the State & Ownership table, make one rule: either the record stores no `outcome`, and `gate` and `rounds` derive it from findings plus waivers, or `waive` atomically rewrites `outcome` and is listed as its second writer. Make `rounds` count a review as blocking only while it has an unwaived P0/P1.
6. **(M5)** In the ADRs section, state that ADR 0007 records the exceptions to ADR 0003 (review records, waivers and the pre-ship escalation count are machine-local, and losing them means a new review and a reset count), or explain why 0003 does not apply.
7. **(M6)** In D2 (`gate`) and the preship spec, define the store-backed archive case: a record matches when its code head equals code HEAD and its store head is the store HEAD's parent, with `archive-only` true in the store. Add a store-backed "Local merge after archive" scenario.
8. **(M7)** In D10 and the install-update spec, compare keys by dotted path, deriving a commented key's path from its indentation within its commented block. Treat the entries under map-valued settings (`pr.reviewers`, `planning_store.reviewers`) as user data that is never listed as added or removed. Add a scenario with `pr.reviewers.kody-ai` set in the project, where Step 6 asks nothing.

<!-- yes (applied, and re-checked by the reviewer - only the reviewer sets it) | no (outstanding) | n/a (any other verdict) -->
CHANGES_APPLIED: yes

## Rebuttals

<!-- Author: fixed (cite) or rebutted (reason) per finding. A Critical/Moderate rebuttal counts only once marked "accepted by reviewer". -->
- C1 fixed: design D3 (review input built by the script, nonce-delimited, `review.max_diff_kb` bound, `diff_too_large`), Resource Bounds row; review-routes requirement "The review input is built by Specwright, within a bound" with scenarios "Route without a shell" and "Diff over the bound".
- M1 fixed: D3 Claude allowlist `--tools Read,Grep,Glob` (`--restricted` if the trial confirms), trial verifies writes on Windows; review-routes "Reviewer tries to write" covers all three routes.
- M2 fixed: D6 subject `<type>(<change>): address pre-ship review` + `Preship-Round:` trailer, never matching `address review feedback`/`Feedback-Round:`; preship-review scenario "Pre-ship fixes do not use up PR fix rounds".
- M3 fixed: D7 branch-protection bullet; pr-watch scenario "Branch protection wants a fresh approval".
- M4 fixed: D5/D6 and State & Ownership: no stored outcome, pass/blocked derived from findings + waivers; `waive` sole writer of `waivers`; escalation no longer counts records.
- M5 fixed: escalation now derived from `Preship-Round:` trailers in git (D6, preship-review "Repeated blocking reviews escalate" with scenario "New session after two rounds"); ADRs section states 0007 records the remaining exception (records and waivers machine-local; loss = new review, user re-decides).
- M6 fixed: D2 `gate` matching rules for repo-local and store-backed archive; preship-review scenario "Store-backed local merge after archive"; Flow & State Gaps updated.
- M7 fixed: D10 dotted paths, commented paths from indentation, `pr.reviewers.*`/`planning_store.reviewers.*` as user data; install-update requirement reworded with scenarios "Reviewer entries are user data" and "Same name at two paths".
- S1 fixed: preship-review requirement reworded ("leave the new head without a pass"); "PR already exists" scenario made store-backed per S2.
- S2 fixed: D11 ship gate before 4a, "first PR" per change.
- S3 fixed: D7 names `archive_only: true|false` vs the setting; pr-watch requirement says "after a change's archive commit is pushed".
- S4 fixed: D2 `record --kind design`; review-routes validation covers the subagent, scenario "Subagent design review without a verdict".
- S5 fixed: D9 and pr-descriptions list only `Amendment:`-trailer commits; scenario "Drift amendment during apply".
- S6 fixed: `stale` dropped from `gate` (D2, D11).

## Re-check (round 1, reviewer)

I re-checked Required Changes 1-8 and S1-S6 against the current proposal.md, design.md and specs/*/spec.md.

- RC1 is applied in D3, the Resource Bounds row and the review-routes requirement "The review input is built by Specwright, within a bound". RC2 is applied in D3 (the `--tools Read,Grep,Glob` allowlist and the Windows trial check) and in the "Reviewer tries to write" scenario, which now covers all three routes.
- RC3 is applied in D6 (the `address pre-ship review` subject and the `Preship-Round:` trailer) and in the preship scenario "Pre-ship fixes do not use up PR fix rounds". RC4 is applied in D7's branch-protection bullet and the pr-watch scenario; `review_decision` already exists in the snapshot (`pr-snapshot.sh:345`).
- RC5 is applied in D5, D6 and the State & Ownership table: no outcome is stored, and `waive` is the only writer of waivers. RC6 is applied in the ADRs section, and the escalation count now comes from git trailers. RC7 is applied in D2's `gate` matching and the "Store-backed local merge after archive" scenario. RC8 is applied in D10 and the install-update scenarios "Reviewer entries are user data" and "Same name at two paths".
- S1-S6 are all addressed.

The edits introduce no new Critical or Moderate finding. One behaviour change to note: escalation now counts every `Preship-Round:` trailer on the branch and is no longer reset by a pass. This is stricter than before, not unsafe, and the specs state it consistently.

All of the author's fixes above are accepted by the reviewer.

