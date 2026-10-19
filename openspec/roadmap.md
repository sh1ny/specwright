# Specwright Roadmap

Strategy: [openspec/strategy.md](strategy.md) · Architecture: [openspec/architecture.md](architecture.md)

Specwright already exists (0.1.8), so M1 is not a walking skeleton: it closes the gaps between the code and the architecture baseline that most often force a manual rescue. Issue numbers refer to sh1ny/specwright. Versions follow the pre-1.0 rule in [strategy.md](strategy.md#assumptions): one minor version per feature, configuration key or workflow change, and a patch version per fix.

## Now: M4 - Cost tier

**Outcome:** Specwright runs cheaper and bounded: bounded work (watch, LIGHT implementation, the eval stress tier) can run on Haiku, the PR scripts and reviewer runs stop within set bounds instead of hanging, and the eval grader is exact enough for a cheaper tier to lean on. The gaps found during M3 are closed first.

**Exit criteria:**
- Every issue in the changes below is closed by a merged PR, and each code fix has a regression test in `evals/`. (agent)
- `evals/pr-pair`, `evals/git-workflow`, `evals/review-routes`, `evals/update` and `evals/release` pass. (agent)
- An eval with a hung or oversized `gh` response shows each PR script stopping within its deadline or bound with a named error, and an eval shows a reviewer run stopped once its output passes the bound, with no partial review recorded. (agent)
- The grader evals show GraphQL mutations and every listed git and `gh` write classified as writes (anything off the read-only allowlist counts as a write), and the agent-merge eval fails a reply that names the next step without offering it. (agent)
- With the cheap tier configured, watch and the LIGHT implementer run on Haiku, and the stress-tier evals reach the same grade on it as on the default tier; with it unset nothing changes. (agent)
- Each change ships as its own release: 0.6.1, 0.7.0, 0.7.1, 0.7.2, 0.7.3 and 0.8.0. (agent)

**Changes** (in order; each about one PR):
1. `fix-m3-gaps` (0.6.1) - known gaps filed during M3 and #53: #91 the install version check needs a boundary after the OpenSpec version token; #93 the remote tag read in `finish: local` fenced or avoided; #94 a version already on main rejected before a second change merges; #95 the codex design review reads the repo on Windows, and an invalid `VERDICT` is refused; #97 store staging directories isolated between checkouts; #99 an update refusal names the installed version when the change already fails there; #53 `specwright-debug` recovers an interrupted stash.
2. `record-review-dispositions` (0.7.0) - #100 a FULL-tier design review that is deferred (a parking change that is never applied) or waived by the user is recorded explicitly, instead of stretching `USER_OVERRIDE`. A workflow change, so it ships as a minor release on its own.
3. `fix-deferral-followups` (0.7.1) - gaps found while shipping the first two M4 changes: #106 the finish step 0 undo of a deferred archive becomes a plan-only script, tested against real repo states (later amendments re-applied, the newest add commit as the target, no uncommitted edit lost); #105 how a parked (DEFERRED) change counts at milestone close; #103 an unreadable merge-base version no longer counts as a release bump. Placed ahead of the cost tier because 0.7.0 already ships the undo text it replaces.
4. `bound-pr-scripts` (0.7.2) - #40 bounded metadata processing and command deadlines in the PR scripts; #80 reviewer output bounded while the CLI runs; #64 the closing-reference parser reads GitHub's rendered Markdown.
5. `exact-eval-grader` (0.7.3) - #74 GraphQL operations parsed instead of matched by first token; #76 git and `gh` writes classified by a read-only allowlist; #87 the agent-merge eval checks a real next-step offer, with a roadmap in its fixture.
6. `add-cheap-tier` (0.8.0) - #22 Haiku as a cheap tier for bounded work (watch, LIGHT implementer, eval stress tier), evals first. Leans on the exact grader from change 5.

## Next: M5 - Commits and VCS backends

Commits shaped by the work, not by the tool. #20 one commit per task group, made at the group boundary only, with `Specwright-Task:` trailers; then #19 jj as a backend; GitButler as a separate change after that.

## Later

- Unplanned features, placed at a later **close**: #68 packs (opt-in domain extensions, first gamedev); #42 stealth mode; #72 a configurable report signal per reviewer in `pr.reviewers`.
- Deferred dogfood check, run when a dogfood project is at a convenient point; it does not block a milestone: #98 (M3) an update with a change in flight. (#86, the M2 agent-merge check, passed in sh1ny/blackgrid#44.)
- Unscheduled `known-gap` issues filed after a milestone is planned are placed into a milestone at the next **close**, or into an earlier change that touches the same code.
- Parked: #9 snapshot pagination beyond 100 items; revisit if large PRs become routine.

## Done

- **M3 - Distribution** (closed 2026-10-17; PRs #89, #90, #92, #96; releases 0.4.1-0.6.0). Seven of eight exit criteria passed; the user-verified dogfood update with a change in flight is deferred to #98, by the user's choice, because it can only run once a release is out and waiting for it would hold up M4. Learned: a user-verified check against a published release cannot pass before close, so later milestones list such checks as follow-ups instead of exit criteria; `safe-update-lifecycle` took six fix rounds, four past the limit, with each round finding a new lock or interruption race, so concurrency-heavy changes need race tests in the design, not just in review; the update suite takes about half an hour on Windows because it spawns a process per file operation; and seven gaps were filed during M3 (#91, #93, #94, #95, #97, #99, #100; the last two found by the first attempt at the deferred dogfood check), so M4 again opens with a gap-fix change.
- **M2 - Ship flow** (closed 2026-10-14; PRs #71, #73, #79, #82, #85; releases 0.1.12-0.4.0). Six of seven exit criteria passed; the user-verified dogfood run of the pre-ship review and agent merge is deferred to #86, by the user's choice, because it needs a full change in a dogfood project. Learned: the review-run.sh tests landed in a third suite, `evals/review-routes`, that the criteria did not name, so M3's criteria name all three; nine known gaps were filed during M2 (most found by the pre-ship and Codex reviews before merge), so M3 again opens with a gap-fix change; and graded agent evals must be re-run after late skill edits (the agent-merge evals were re-run at close for that reason).
- **M1 - Hardening** (closed 2026-10-11; PRs #59, #62, #67; releases 0.1.9-0.1.11). Learned: PR-flow gaps surfaced faster than they closed (16 issues filed during M1), and local cross-model reviews before push caught what Codex would have (it found nothing on #67), so M2 opens with two gap-fix changes and makes the pre-ship review a step.
