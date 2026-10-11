# Proposal

## Why

Milestone **M2 - Ship flow** promises that a change is reviewed before it ships. Today nothing reviews the finished `main...HEAD` diff before it reaches a PR or a local merge. A review the user runs by hand has no rules for what it may change: in another project it led the agent to amend a spec delta with no guidance on whether that was allowed (#27). Design reviews also pick their reviewer through a hardcoded pairing (a Claude author gets `codex`, a Codex author gets `claude`). That leaves OMP out, and model and reasoning level can't be configured. And on every PR, the mechanical archive commit triggers a second review round of 10-20 minutes that finds nothing (#69).

This change serves M2 change 3 (`add-preship-review`, 0.2.0) and advances these exit criteria:
- the pre-ship review has a recorded trial run on each reviewer CLI (OMP, Codex, Claude);
- output that fails the findings schema stops ship;
- every issue in the change (#27, #69, #78) is closed by a merged PR, each code fix with a regression test.

It is bound by ADR 0002 (the script I/O contract: one JSON document on stdout, exit codes for stops) and ADR 0004 (process-scoped GitHub identity; the review itself makes no `gh` call).

## What Changes

- **New `specwright-review` skill** that owns reviewer selection and runs reviews.
  - It holds one reviewer brief, a findings JSON schema and `scripts/review-run.sh`, which has one fixed, isolated, read-only command line per route (`codex`, `claude`, `omp`), runs within a deadline and validates the output in Python, failing closed.
  - Every review records a receipt: the route used, the routes skipped and why, the requested model and the model that actually ran.
  - Credits compound-engineering `ce-code-review` and oh-my-pi `reviewer.md`.
- **Ordered reviewer list for every review.** New settings: `review.order` (default `[codex, claude, omp]`), `review.models`, `review.thinking`, `review.timeout` (default 20m) and `review.max_diff_kb` (default 1024). Specwright builds the review input itself: the diff of both ranges goes into the prompt, and an over-bound diff stops before any reviewer starts.
  - Selection walks the list in order, skips the harness the agent is running in, and takes the first route whose CLI is installed and whose probe passes. With none left, the `specwright-reviewer` subagent reviews.
  - A route that ran but returned output failing validation is a failed review: it stops, and never falls through to the next route.
  - OMP takes an `@role` or a `provider/id` model and always runs with a fresh `--session-dir`.
  - Design reviews (FULL tier and the roadmap baseline) use the same selection. This replaces the hardcoded pairing; the default order reproduces it for Claude and Codex authors.
  - `review.cross_model: false` still means the subagent only.
- **Pre-ship review, on by default** (`review.preship: true`; `false` opts out).
  - When every task is committed, `specwright-commit` runs it over `<main>...HEAD` (plus the store range when store-backed), before the hand-off to ship or archive.
  - Ship, before the first PR of the change exists, and a local finish, before its merge, check that a passing review exists for the current head, or for a head whose only later commit is the archive commit. Without one, they run the review first.
  - **BREAKING (workflow):** a project that does not set `review.preship` now gets a review step before ship and before a local merge.
- **Blocking rule.** P0/P1 findings stop ship until they are fixed or the user waives them. A fix is an `address pre-ship review` commit with a `Preship-Round:` trailer, followed by a new review. After round 2 the user decides. P2/P3 findings are fixed or listed in the PR description.
- **Spec amendment rule.**
  - A `spec` finding is classed as a *clarification*: one reading is consistent with every other scenario, and the code and tests already match it. The agent may make that amendment as an `amend <artifact>` commit, followed by a new pre-ship review.
  - Or it is a *behaviour change*: a requirement or scenario would then allow something different. That needs the user's approval and goes through the drift rule.
  - The PR description lists every spec amendment made after the design review.
- **No review round on the archive head (#69).** New `pr.review_after_archive` (default `false`).
  - After the archive push, watch posts no review requests and waits only for CI.
  - Required reviewers' reports on the previous head stay valid while the only commit after it is the archive commit and that commit touches only the archive paths and the synced main specs.
- **Install prompt (#78).** Step 6 treats a key commented out in the downloaded settings template as optional: it is never listed as removed, and never added when missing. Step 7's key check counts only uncommented keys.

## Capabilities

### New Capabilities
- `review-routes`: how a reviewer CLI is chosen, isolated, run, validated and recorded, shared by design and pre-ship reviews.
- `preship-review`: when the pre-ship review runs, what blocks ship or merge, waivers, and the spec amendment rule.
- `install-update`: how the install/update prompt merges settings, starting with the rule for keys commented out in the template.

### Modified Capabilities
- `pr-watch`: watch neither re-requests nor waits for reviewers on an archive-only head unless `pr.review_after_archive` is true.
- `pr-descriptions`: a PR description lists the spec amendments made after the design review, and P2/P3 pre-ship findings left open.

## Impact

- New `skills/specwright-review/` (`SKILL.md`, `references/brief.md`, `references/findings.schema.json`, `scripts/review-run.sh`). The install prompt already copies every `specwright-*` directory.
- `schemas/specwright/schema.yaml` (review instruction), `skills/specwright-commit`, `specwright-pr` (ship gate, watch archive rule, description), `specwright-finish` (local merge gate), `specwright-roadmap` (baseline review route), `agents/*/specwright-reviewer.md` (pre-ship mode and findings output).
- `templates/openspec/specwright.yaml`, `openspec/specwright.yaml`, README (settings, skills table, install prompt Steps 6-7, credits), `CONTRIBUTING.md`, `openspec/architecture.md` (components, state, the cross-model contract, bounds).
- New evals: `evals/review-routes/` (route selection, command lines, validation, gate and archive-only check, with fake CLIs), plus additions to `evals/pr-pair` and `evals/git-workflow` text checks.
- Release 0.2.0 (minor: new skill, new settings keys, workflow change).
- The review sends the diff and the files the reviewer reads to the chosen CLI's provider, as cross-model design reviews already do.
