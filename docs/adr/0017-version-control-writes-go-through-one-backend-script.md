# 0017. Version-control writes go through one backend script

- Status: accepted
- Date: 2026-10-29

## Context

Specwright's branch reads and version-control writes are spread across skill prose and scripts. Supporting jj without diverging implementations requires one executable boundary for backend selection, branch state and every write. jj is supported only in colocated repositories: existing Git reads continue to consume the exported Git history, while jj owns its working-copy and bookmark operations. The `vcs` and `planning_store.vcs` settings must remain independent so a code repository never silently selects the store's backend.

## Decision

- **One seam:** `skills/specwright-pr/scripts/vcs.sh` owns the branch read and all version-control writes for both backends. Each subcommand probes the selected per-repository backend before reading branch state or writing. The setting is explicit, accepts `git` or `jj`, defaults independently to `git`, and is never inferred from `.jj/`; an unknown value stops with `unknown_vcs` and the accepted values.
- **Colocated jj, Git reads:** jj is supported only when `.jj/` and the Git work tree share a toplevel. Existing read-only history, trailers, ranges and tree queries stay on Git. Specwright never initializes, converts or otherwise manages a repository on the user's behalf.
- **Working-copy invariant:** on jj, the change bookmark points to `@-`; `@` contains only uncommitted work. Branch creation starts the bookmark at `@-`, and commits advance it to the new `@-`. Moving the working copy carries its edits; if that carry conflicts, it is rolled back to the old parent and the operation stops. Merge construction is performed off to the side and reused on retry; branch deletion forgets the bookmark rather than publishing a remote deletion.
- **Fetch and pull:** a read-only main refresh writes only `FETCH_HEAD`, reads that fetched commit in the same call, and never imports remote-tracking movements. A pull first checks fast-forward ancestry, then fetches only main through jj; it does not fetch all branches or remove change bookmarks. The Git backend retains its current behavior.
- **Network fence:** jj fetch and push run through `as.sh` under the existing GitHub identity fence. They gain no deadline: that behavior remains outside ADR 0014's scope, matching the current fenced Git commands.
- **Release exception:** release publication continues to use Git only for its annotated release tag and the tag-specific fetch/push. No other Specwright write bypasses `vcs.sh`.
- **Recovery and evals:** jj operation state is rebuilt from jj and Git evidence; no operation journal or stash emulation is added. Evals use real pinned jj in short-lived colocated repositories, and log Specwright's Git calls to enforce the write boundary. CI verifies the pinned archive checksum before using the binary.
- **Undo:** on jj, the undo plan restores and moves files in the working copy before committing the named paths; its warning makes clear that this is not an atomic Git-index workflow.

## Consequences

All skills, scripts and evals that read branches or write version-control state must use the backend seam. Git history remains the shared evidence format, and Git is still the default. Supporting non-colocated jj workspaces, inferring a backend, adding deadlines to these network commands or broadening the release-tag exception requires a new decision. The annotated-tag exception remains limited to `release.sh` and the named tag refs. This ADR supersedes none. Reversal cost: medium; the callers can return to Git-specific behavior, but the backend boundary and per-repository setting would need to be removed together.
