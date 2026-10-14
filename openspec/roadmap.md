# Specwright Roadmap

Strategy: [openspec/strategy.md](strategy.md) · Architecture: [openspec/architecture.md](architecture.md)

Specwright already exists (0.1.8), so M1 is not a walking skeleton: it closes the gaps between the code and the architecture baseline that most often force a manual rescue. Issue numbers refer to sh1ny/specwright. Versions follow the pre-1.0 rule in [strategy.md](strategy.md#assumptions): one minor version per feature, configuration key or workflow change, and a patch version per fix.

## Now: M3 - Distribution

**Outcome:** Specwright installs, updates and pins safely across projects: each release is a tagged version with notes, an update never breaks a change in flight or a shared planning store, and the pinned OpenSpec version is enforced. The ship-flow gaps found during M2 are closed first.

**Exit criteria:**
- Every issue in the changes below is closed by a merged PR, and each code fix has a regression test in `evals/`. (agent)
- `evals/pr-pair`, `evals/git-workflow` and `evals/review-routes` pass. (agent)
- The install prompt compares `openspec --version` with the pin and asks before continuing on a mismatch; the public install command names the pinned version. (agent)
- A Specwright release is cut by the release workflow: one version-bump commit across the configured version files, an annotated `v<version>` tag on the merged main commit, notes built from the archived changes, and a GitHub release. (agent)
- An eval interrupts an update at every step before the swap and shows the previous version still runnable each time, and the interrupted update then resumes or rolls back cleanly; an update across a workflow change, while a change is in flight, either refuses or proceeds only after preserving or migrating that change, which then still validates and ships. (agent)
- An eval with two projects sharing one planning store updates one project and shows the other unaffected: the store records its schema version and owner, and the other project's change in flight still validates and ships. (agent)
- A dogfood project updates from one tagged release to the next with a change in flight, and that change still ships. (user)
- Each change ships as its own release: 0.4.1, 0.4.2, 0.5.0 and 0.6.0. (agent)

**Changes** (in order; each about one PR):
1. `fix-m2-gaps` (0.4.1) - known gaps filed during M2: #75 and #77 finish resume with a reused change or branch name; #81 the pre-ship recovery review after the archive commit reads the moved artifact paths; #83 `as.sh` accepts the trailing-dot host `github.com.`; #84 `pr-pair.sh` restores enterprise `gh` tokens for unfenced non-GitHub store reads.
2. `pin-openspec-version` (0.4.2) - #37 the pinned OpenSpec version enforced at install, not just documented.
3. `add-release-workflow` (0.5.0) - #28 an opt-in release step: version bump across configured files, annotated tag, notes from the OpenSpec archive, optional GitHub release, offered at milestone close. Specwright cuts its own releases with it.
4. `safe-update-lifecycle` (0.6.0) - #36 updates staged and swapped in last, a restart notice for running sessions, schema ownership and its version recorded in a shared store, and an update across a workflow change refused or warned while a change is in flight. Builds on the tags from #28.

## Next: M4 - Cost tier

Cheaper and bounded runs. #22 Haiku for bounded work, evals first; #40 bounds and deadlines in the PR scripts, with #80 bounding reviewer output while the CLI runs; #64 the closing-reference parser reads GitHub's rendered Markdown; #53 `specwright-debug` recovers an interrupted stash; and the eval grader made exact before a cheaper tier leans on it: #74 GraphQL operations parsed, #76 writes classified by a read-only allowlist, #87 the agent-merge eval checks a real next-step offer.

## Later

- M5 - Commits and VCS backends: #20 one commit per task group, made at the group boundary only, with `Specwright-Task:` trailers; then #19 jj; GitButler as a separate change after that.
- Unplanned features, placed at a later **close**: #68 packs (opt-in domain extensions, first gamedev); #42 stealth mode; #72 a configurable report signal per reviewer in `pr.reviewers`.
- Unscheduled `known-gap` issues filed after a milestone is planned are placed into a milestone at the next **close**, or into an earlier change that touches the same code.
- Parked: #9 snapshot pagination beyond 100 items; revisit if large PRs become routine.

## Done

- **M2 - Ship flow** (closed 2026-10-14; PRs #71, #73, #79, #82, #85; releases 0.1.12-0.4.0). Six of seven exit criteria passed; the user-verified dogfood run of the pre-ship review and agent merge is deferred to #86, by the user's choice, because it needs a full change in a dogfood project. Learned: the review-run.sh tests landed in a third suite, `evals/review-routes`, that the criteria did not name, so M3's criteria name all three; nine known gaps were filed during M2 (most found by the pre-ship and Codex reviews before merge), so M3 again opens with a gap-fix change; and graded agent evals must be re-run after late skill edits (the agent-merge evals were re-run at close for that reason).
- **M1 - Hardening** (closed 2026-10-11; PRs #59, #62, #67; releases 0.1.9-0.1.11). Learned: PR-flow gaps surfaced faster than they closed (16 issues filed during M1), and local cross-model reviews before push caught what Codex would have (it found nothing on #67), so M2 opens with two gap-fix changes and makes the pre-ship review a step.
