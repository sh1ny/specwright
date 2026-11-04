# Specwright Roadmap

Strategy: [openspec/strategy.md](strategy.md) · Architecture: [openspec/architecture.md](architecture.md)

Specwright already exists (0.1.8), so M1 is not a walking skeleton: it closes the gaps between the code and the architecture baseline that most often force a manual rescue. Issue numbers refer to sh1ny/specwright. Versions follow the pre-1.0 rule in [strategy.md](strategy.md#assumptions): one minor version per feature, configuration key or workflow change, and a patch version per fix.

## Now: M7 - Native CLI foundation

**Outcome:** a compiled Dart `sw` can be delivered on the supported platforms and replaces the VCS, commit and finish scripts incrementally, retaining their existing contracts. The remaining shipped scripts move in M8 (#148). The distribution and bounded-process spike comes first; the migration's new architecture decision is reviewed before implementation supersedes ADR 0002.

**Exit criteria:**
- A reviewed architecture decision establishes the binary's distribution, installation and interface-version contract, and records how it supersedes the relevant existing ADRs. (agent)
- CI builds and checks a versioned binary on Linux, Windows and macOS; distribution artifacts and checksums are verified and the install path handles a missing or incompatible binary explicitly. (agent)
- Bounded processes preserve deadlines, output bounds, secret handling and process-tree cleanup on Windows and POSIX, with regression coverage. (agent)
- VCS, commit and finish operations use `sw`; their existing JSON, exit-code and workflow contracts are covered by the corresponding black-box evals on the three CI platforms. (agent)
- All M7 changes are archived on main and their releases are published. (agent)

**Changes** (in order; each about one PR):
1. `native-cli-spike` - #148: establish the Dart executable and reviewed architecture; prove bounded process handling, build artifacts and download-and-run on all three platforms before committing to distribution details.
2. `native-cli-distribution` - deliver and verify versioned binaries, integrate installation and contract-version checks, and preserve the existing updater's recovery guarantees during transition.
3. `native-cli-vcs` - move the VCS boundary to `sw` with Git, jj and GitButler parity, retaining the existing eval contracts.
4. `native-cli-commit` - move task coverage and subject fitting to `sw` while retaining task and commit evidence contracts.
5. `native-cli-finish` - move finish operations to `sw`, preserving local and store-backed recovery behavior.

## Next: M8 - Complete the native CLI migration

Continue #148 script by script: migrate the PR, review, release and update paths with their identity, process, journal and recovery contracts intact; complete bootstrap and remove obsolete shipped scripts and runtime prerequisites only after parity is proven. Split into PR-sized changes at M7 close.

## Later

- M9 - Adoption and configuration: plan the known gaps #167-#173, covering GitHub connection options, remotes, reviewer routes, implementer defaults, project conventions, review limits and neutral examples.
- Unplanned features, placed at a later **close**: #42 stealth mode; #72 a configurable report signal per reviewer in `pr.reviewers`; #140 implementer agents can use the project's MCP servers.
- Deferred dogfood check, run when a dogfood project is at a convenient point; it does not block a milestone: #98 (M3) an update with a change in flight; the gamedev pack used for a real change in Tower of Lament once 0.20.0 is out (M6). (#86, the M2 agent-merge check, passed in sh1ny/blackgrid#44.)
- Parked: #154 GitButler tests on macOS and Windows await standalone versioned `but` builds upstream; Linux CI runs them.
- Unscheduled `known-gap` issues filed after a milestone is planned are placed into a milestone at the next **close**, or into an earlier change that touches the same code.
- Parked: #9 snapshot pagination beyond 100 items; revisit if large PRs become routine.
- Parked: #118 the codex route on Windows (`fix-codex-windows-route`, moved out of M5 on 2026-10-28). It could not be reproduced: on 2026-10-28 an exact replay of the failed review (same codex-cli 0.163.0, `elevated` sandbox, Specwright 0.7.2, the original prompt) passed, and so did four codex reviews in a dogfood project, so the 2026-10-21 failure was most likely transient. Revisit if it fails again; the fix then starts by reading codex's own error from its `--json` event stream and keeping that stream when a run fails.

## Done

- **M6 - Packs** (closed 2026-11-04; PRs #156, #158, #159, #160, #163, #165, #174, #179, #183, #187, #188, #195; releases 0.12.1-0.20.0). The closing-head eval matrix passed on Linux, Windows and macOS; the first shipped packs, user-verified tasks and roadmap decision modes are in place. Learned: pack installation and delivered instructions need complementary coverage; cross-platform GitButler coverage remains limited by upstream binary availability (#154); and the native CLI migration needs a distribution and process-runner spike before incremental replacement.

- **M5 - Commits and VCS backends** (closed 2026-10-31; PRs #129, #132, #135, #137, #142, #147, #149; releases 0.8.1-0.12.0). All nine exit criteria passed; the suites were verified by the Linux CI run of every suite on #149, not by a local full run. Learned: the Windows suites still take about 80 minutes after `fix-eval-gaps` cut them from about 140 (`evals/timings.md`), and three `test_git_backend` cases crash real `git` only on this Windows machine, so M6 opens with OS-matrix CI (#145) and local full runs stop; a backend with a shared work tree (GitButler) turns every read of settings or skills from the work tree into a trust question, which the reviews of `add-gitbutler-backend` found late and #150 and #151 track; Codex's security review on sh1ny/kehai#2 found that agent merge trusts the merge policy on the PR branch (#141), so M6 fixes that before packs add more project-supplied content; and eight gaps were filed during M5, so M6 again includes a gap-fix change.
- **M4 - Cost tier** (closed 2026-10-26; PRs #102, #104, #108, #112, #120, #126; releases 0.6.1-0.8.0). All six exit criteria passed. Learned: fifteen gaps were filed during M4 (#109-#125, less the PRs), mostly edge cases that reviews of `fix-deferral-followups`, `bound-pr-scripts` and `exact-eval-grader` found and that were filed as issues instead of fixed in those PRs, plus #118 from a dogfood project, so M5 opens with three gap-fix changes; the codex route still fails on Windows after #95 because a failing run discards codex's own error, so the next fix starts with diagnostics; the Haiku stress run found two wording gaps and one grader false negative and no model limit, so wording tests on the cheap tier are worth keeping; `evals/finish`, added by `fix-deferral-followups` (itself inserted mid-milestone), was not named in the criteria, so M5's criteria name it; and the six suites took about two and a half hours on Windows at about 215 ms per process launch, so M5 cuts launches per test (#127).
- **M3 - Distribution** (closed 2026-10-17; PRs #89, #90, #92, #96; releases 0.4.1-0.6.0). Seven of eight exit criteria passed; the user-verified dogfood update with a change in flight is deferred to #98, by the user's choice, because it can only run once a release is out and waiting for it would hold up M4. Learned: a user-verified check against a published release cannot pass before close, so later milestones list such checks as follow-ups instead of exit criteria; `safe-update-lifecycle` took six fix rounds, four past the limit, with each round finding a new lock or interruption race, so concurrency-heavy changes need race tests in the design, not just in review; the update suite takes about half an hour on Windows because it spawns a process per file operation; and seven gaps were filed during M3 (#91, #93, #94, #95, #97, #99, #100; the last two found by the first attempt at the deferred dogfood check), so M4 again opens with a gap-fix change.
- **M2 - Ship flow** (closed 2026-10-14; PRs #71, #73, #79, #82, #85; releases 0.1.12-0.4.0). Six of seven exit criteria passed; the user-verified dogfood run of the pre-ship review and agent merge is deferred to #86, by the user's choice, because it needs a full change in a dogfood project. Learned: the review-run.sh tests landed in a third suite, `evals/review-routes`, that the criteria did not name, so M3's criteria name all three; nine known gaps were filed during M2 (most found by the pre-ship and Codex reviews before merge), so M3 again opens with a gap-fix change; and graded agent evals must be re-run after late skill edits (the agent-merge evals were re-run at close for that reason).
- **M1 - Hardening** (closed 2026-10-11; PRs #59, #62, #67; releases 0.1.9-0.1.11). Learned: PR-flow gaps surfaced faster than they closed (16 issues filed during M1), and local cross-model reviews before push caught what Codex would have (it found nothing on #67), so M2 opens with two gap-fix changes and makes the pre-ship review a step.
