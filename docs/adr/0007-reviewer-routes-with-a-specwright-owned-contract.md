# 0007. Reviewer routes with a Specwright-owned contract

- Status: accepted
- Date: 2026-10-12
- Supersedes: 0005

## Context
ADR 0005 split the work into an orchestrator, an implementer and a reviewer, and paired a FULL design review with a different model's CLI by a hardcoded rule (a Claude author uses `codex`, a Codex author uses `claude`). The agent built that CLI's command line itself from `--help`, so flags drifted per run, the user's own skills and rules leaked into the review (#27), OMP could not be chosen, and nothing checked the output beyond one `VERDICT:` line. A pre-ship review of the finished diff needs the same reviewers with a stricter contract, because a review that silently fails lets unreviewed code ship.

## Decision
The role split of 0005 stands: the orchestrating agent plans, verifies, ticks tasks and commits; a `specwright-implementer` agent implements one task group test-first from a packet and never commits or ticks; FULL design reviews never run in the authoring context, and a LIGHT design only has the orchestrator re-check its triage and record `SKIPPED_LIGHT`.

What changes is how a reviewer is chosen and run. The `specwright-review` skill owns it through `scripts/review-run.sh`, which prints one JSON document per call (ADR 0002):
- **Routes in order.** `select` walks `review.order` (default `[codex, claude, omp]`), skips the route of the harness the agent runs in, and takes the first route whose CLI is installed and whose probe passes. With none left, or `review.cross_model: false`, the `specwright-reviewer` subagent reviews. An unknown route name stops. A probe failure (including an unresolved OMP model) means unavailable and moves on.
- **Fixed, isolated command lines.** Each route has one command line in the script, set by a recorded trial run, never assembled by the agent: read-only tools by allowlist, the user's skills, extensions, rules and slash commands off where the CLI supports it, and a fresh OMP session directory per run. The prompt goes through a file or stdin, never argv.
- **Specwright builds the review input.** For a pre-ship review the script puts the diff of the code range, and of the store range when store-backed, into the prompt inside a nonce-delimited untrusted region. Over `review.max_diff_kb` it stops before any reviewer starts; it never reviews a truncated diff.
- **Fail closed.** Output is validated by the script: pre-ship findings against `findings.schema.json`, design reviews as a review file with exactly one `VERDICT:` line and a `CHANGES_APPLIED:` line, from every route, the subagent included (`record --kind design`). Invalid output, a crash or a passed `review.timeout` is a failed review (exit 3): the process tree is killed by PID and the caller stops. It never falls through to the next route. Every run writes a receipt with the route, the skipped routes and their reasons, and the requested and actual model and level (`unknown` when not reported).
- **Spec findings carry a class.** A finding with `category: spec` has `spec_class: clarification|behaviour_change`. A clarification amendment is committed as `<type>(<change>): amend specs` with `Amendment: clarification`; a behaviour change only after the user approves it, with `Amendment: behaviour-change`, and through the drift rule.

**Exception to ADR 0003.** Pre-ship review records (the findings of one head and the user's waivers) live under `${SPECWRIGHT_STATE_DIR:-~/.cache/specwright}/reviews/`, keyed by the reviewed head(s), and are machine-local working state, not git evidence. Committing them would move the head they name. Losing them, or shipping from another machine, means a new review, and the user decides waivers again; nothing passes silently, because the gate reads only records of the exact heads. The escalation count is not an exception: it is the highest `Preship-Round:` trailer on the change branch, in either repo, and the trailer and `address pre-ship review` subject are git evidence formats under 0003.

**Rejected: keep the hardcoded pairing and let the agent build each call.** It needs no script, but it cannot include OMP or configure model and level, flags drift between runs, user skills leak into reviews, and unvalidated output can pass as "no findings".

**Rejected: skip routes by model family.** The model behind an OMP `@role` is known only after OMP starts; the receipt records the actual model instead.

**Reversal cost: medium.** The route list, the findings schema and the `review-run.sh` JSON fields are a contract for five skills and pinned by `evals/review-routes`; the new trailers are stored formats.

## Consequences
- The default order reproduces 0005's pairing for Claude and Codex authors; `review.cross_model: false` still keeps every review in-harness.
- A review sends the diff and the files the reviewer reads to the chosen CLI's provider, as cross-model design reviews did under 0005.
- CLI flag changes are absorbed by editing one script after a new trial, and an unknown flag fails the probe or the run loudly.
- The orchestrator still re-verifies delegated work; the implementer's report is evidence, not proof.
