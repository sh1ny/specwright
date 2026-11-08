# 0031. Native workflows call ported operations directly

- Status: accepted
- Date: 2026-11-08
- Adds to: 0027 (one native binary), 0028 (compatibility shims) and 0029 (private fence handoff)
- Supersedes: none

## Context

`native-cli-pr-pair-flow` ports the remaining fourteen PR workflow commands, including all four feedback pass operations. Launching a shim or another `sw` for an already native operation would keep unnecessary transport boundaries and could restart a caller's deadline. The existing native integration points are `cli/lib/src/commands/vcs.dart` (`openSession`, `vcsHandlers`) and `cli/lib/src/fence/fence.dart` (`verifyIdentity` and injected execution callbacks).

A planning store can serve several code projects and need not contain `openspec/.specwright/VERSION`. Its working directory identifies the repository whose URLs the fence must check; it does not identify the binary to use. Moving execution into the code checkout would check the wrong repository.

The accepted design preserves program-readable results, effects, credentials, feedback-record version 2 and recovery behavior. It keeps later M8 work separate: the internal-call retrofit, native launcher, remaining ports and runtime retirement retain their own roadmap changes.

## Decision

- **C1 — direct native integration.** Ported operations call Dart settings, fence and VCS interfaces directly, without launching `as.sh`, `vcs.sh` or a second `sw`, except C9 below. Helper isolation, reviewer evaluation and checks of another installed or downloaded binary remain allowed. These are deliberate process boundaries, not ordinary internal workflow calls.
- **Caller-owned execution.** A workflow supplies the target directory and private per-login environment explicitly. It never changes global cwd or environment. A formerly whole-operation bounded read shares one monotonic budget through checks and execution, while smaller inner limits keep their refusal classification. Existing unbounded local Git/VCS state and planning calls stay unbounded. Standalone fence inherited-stdio and default-unbounded behavior stay intact.
- **C10 — binary project and target repository are distinct.** `as.sh` and `pr-pair.sh` accept one optional leading `--project <code-checkout>` selector. It selects only the exact-version binary, never cwd, the target repository or login. Store callers and nested resolver invocations that need it name the code project explicitly; they do not infer it from a shared store. Relative selectors resolve from the caller's cwd. A leading selector with a missing or empty value, or a repeated leading selector, is a usage error after the existing Python prerequisite check; resolution failure has no fallback.
- **C6 — compatibility transport remains.** Keep the ADR 0028 NUL stdin handoff and ADR 0029 private-file fence handoff, the script paths and the Bash/Python prerequisite probes until their named M8 removals. No direct argv protocol or launcher replacement is introduced here. Complete native PR dispatch removes embedded workflow Python, not those prerequisites.
- **C9 — one temporary nested fence exception.** Non-Git `branch-check` with `--code` retains its VCS `fetch-main` fence hop until `native-cli-internal-calls`. Both `as.sh` calls in that hop (login resolution when no `--login` was supplied, then the fenced fetch) receive `--project` with the session-resolved absolute `--code`. No handoff record is added; target cwd and login stay the store's. This does not widen selector forwarding to other VCS paths.
- **C11 — remaining store-network gap.** Other network operations through `sw vcs` on a GitHub-origin store retain their existing `as.sh` hop without a project selector. This includes the `vcs.sh pull` printed by cleanup for a jj store. Those operations still stop with `sw_missing` from a store without a resolvable binary until `native-cli-internal-calls` fixes the gap.

**Rejected:** subprocess adapters for ordinary native calls, which preserve avoidable transport and risk fresh deadlines; global cwd/environment changes, which make repository and credential checks unsafe under concurrency; inferring a code project from a shared store; expanding this port to retrofit every VCS caller or replace the shell launcher.

## Evidence and limitations

These locations describe the pre-port boundaries audited for this decision:

- `skills/specwright-pr/scripts/pr-pair.sh:2574-2603` reaches non-Git `fetch-main` only under `--code`; `cli/lib/src/commands/vcs.dart:40-59` resolves that code directory for the session. `cli/lib/src/vcs/scripts.dart:115-161` contains the separate login-resolution and fenced-command `as.sh` calls. These bound C9's forwarding scope.
- `skills/specwright-pr/scripts/pr-pair.sh:2700-2713` emits VCS cleanup plans; `cli/lib/src/vcs/plan.dart:25-44` prints the VCS command. `cli/lib/src/vcs/git_common.dart:105-118` passes network work through `fenceLogin` and `runAs` without project selection. The jj paths use the same fence helpers. This is C11, not a claim that cleanup fixes every store network operation.
- **S-1 — store-started snapshot/reply resolution remains a limitation.** `skills/specwright-pr/scripts/pr-snapshot.sh:85-92` and `pr-reply.sh:51-58` resolve from cwd and have no project selector. `skills/specwright-pr/SKILL.md`, “The repos and PRs of a change” (store settings), “feedback” (per-PR snapshots and replies) and “watch” step 1 require store calls to start inside that PR's repository with its login. A store without VERSION therefore cannot resolve those separate shims, even when an enclosing `as.sh` selects the code project's binary. Adding a selector to the outer fence does not alter the nested shim's discovery. This change records the gap and does not fix or claim to fix snapshot/reply selection.

## Consequences

- Native workflow tests must verify effects, call ordering, target cwd, private credentials and outer versus inner deadline outcomes, alongside structured output. Feedback records remain readable in both directions across the port, with the same ownership, exclusive publication, lock and recovery protocol.
- Printed cleanup commands remain scripts until retirement; only the approved selector positions change. Printing a command is not an internal process launch.
- The two known store-resolution gaps remain explicit follow-up work. The approved M8 roadmap amendment is retained, and earlier accepted ADRs remain unchanged.
- Reversal cost: medium. Changing native boundaries or selector meaning affects callers, deadline ownership and repository validation; it needs a new decision rather than an edit to this accepted ADR.
