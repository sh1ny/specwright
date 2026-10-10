# Specwright Roadmap

Strategy: [openspec/strategy.md](strategy.md) · Architecture: [openspec/architecture.md](architecture.md)

Specwright already exists (0.1.8), so M1 is not a walking skeleton: it closes the gaps between the code and the architecture baseline that most often force a manual rescue. Issue numbers refer to sh1ny/specwright. Versions follow the pre-1.0 rule in [strategy.md](strategy.md#assumptions): one minor version per feature, configuration key or workflow change, and a patch version per fix.

## Now: M2 - Ship flow

**Outcome:** a change is reviewed before it ships and, when the project opts in, merged and cleaned up by the agent, with identity fencing on by default and the PR-flow gaps found during M1 closed.

**Exit criteria:**
- Every issue in the changes below is closed by a merged PR, and each code fix has a regression test in `evals/pr-pair` or `evals/git-workflow`. (agent)
- `evals/pr-pair` and `evals/git-workflow` pass. (agent)
- The pre-ship review has a recorded trial run on each reviewer CLI (OMP, Codex, Claude), and a review whose output fails the findings schema stops ship. (agent)
- With `github.login` empty, the #38 regression cases prove every `gh` and git network call is fenced or refused. (agent)
- An agent-merge eval merges a ready PR and runs cleanup when the project opts in, and never merges when it does not. (agent)
- One change in a dogfood project goes from ship to merge through the pre-ship review and agent merge. (user)
- Each change ships as its own release: 0.1.12, 0.1.13, 0.2.0, 0.3.0 and 0.4.0. (agent)

**Changes** (in order; each about one PR):
1. `fix-roadmap-milestone-end` (0.1.12) - #51 `next` offers **close** at a milestone end and `close` keeps an agreed Next split; #60 roll back a roadmap branch left by a failing post-checkout hook; #66 split the over-long `planning-stores` requirements so strict validation passes.
2. `fix-ship-flow-gaps` (0.1.13) - known gaps in ship, feedback and finish: #58 the store PR opens only after the code push succeeds; #57 no re-request on every resume when the push time is missing; #56 no marker-only reply when the body file is missing; #54 reply temp files removed on failure; #55 cleanup never deletes a branch with commits main lacks; #63 and #65 finish resume after a squash or bulk archive, and after a merged PR's branch is already deleted.
3. `add-preship-review` (0.2.0) - #27 the pre-ship review: OMP, Codex or Claude, each with its own configurable model; one brief and findings schema owned by Specwright; the reviewer runs isolated from the user's installed skills; output validated against the schema, failing closed; a spec amendment is a clarification the agent may make, or a behaviour change the user must approve. Its first task is a trial run on each reviewer CLI; the design is recorded on #27, with credits to compound-engineering `ce-code-review` and oh-my-pi `reviewer.md`. Also #69, a setting that skips the review round on the archive commit. Main risk retired: review quality across harnesses.
4. `default-identity-fencing` (0.3.0) - #38 fencing by default, which an agent merge relies on, closing every exception it tracks with regression coverage: the empty default login; `specwright-finish`'s post-merge `gh pr view`; `git fetch` and `git pull` on main (branch gate, roadmap status, finish and pr cleanup); and credential-bearing remote URLs, with cases for credential-free HTTPS URLs and credential-bearing fetch and push URLs (including several push URLs) that prove git receives the verified token or refuses to publish.
5. `add-agent-merge` (0.4.0) - #15 the opt-in agent merge mode.

## Next: M3 - Distribution

Specwright installs, updates and pins safely across projects. #28 versions, tags and GitHub releases; #36 an update lifecycle that is safe for running sessions and shared planning stores; #37 the pinned OpenSpec version enforced, not just documented.

## Later

- M4 - Cost tier: #22 Haiku for bounded work, evals first; #40 bounds and deadlines in the PR scripts; #64 the closing-reference parser reads GitHub's rendered Markdown; #53 `specwright-debug` recovers an interrupted stash.
- M5 - Commits and VCS backends: #20 one commit per task group, made at the group boundary only, with `Specwright-Task:` trailers; then #19 jj; GitButler as a separate change after that.
- Unplanned features, placed at a later **close**: #68 packs (opt-in domain extensions, first gamedev); #42 stealth mode.
- Unscheduled `known-gap` issues filed after a milestone is planned are placed into a milestone at the next **close**, or into an earlier change that touches the same code.
- Parked: #9 snapshot pagination beyond 100 items; revisit if large PRs become routine.

## Done

- **M1 - Hardening** (closed 2026-10-11; PRs #59, #62, #67; releases 0.1.9-0.1.11). Learned: PR-flow gaps surfaced faster than they closed (16 issues filed during M1), and local cross-model reviews before push caught what Codex would have (it found nothing on #67), so M2 opens with two gap-fix changes and makes the pre-ship review a step.
