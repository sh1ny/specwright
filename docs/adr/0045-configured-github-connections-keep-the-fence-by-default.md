# 0045. Configured GitHub connections keep the fence by default

- Status: accepted
- Date: 2026-11-27
- Amends: 0008 (fixed host and credential routing), 0018 (remote selection and release fetch), 0031 and 0040 (project selection)
- Retains: 0024 (committed user task evidence)

## Context

One GitHub host, the `origin` remote and a stored `gh` account fit many projects but prevent SSH, Enterprise Server, token-only automation and named-remote workflows. A planning store with no publication destination must not prevent the code PR from being opened.

## Decision

- `github.host` defaults to `github.com`; `github.fence` defaults to `true`. The fence resolves or receives one run login, verifies it on the configured host and supplies its token only over HTTPS to that host. A handoff carries the bound login or explicit permission to defer the first lookup, never an implicit fallback. Do not change global accounts or persistent Git credentials.
- `github.fence: false` uses the caller's Git and `gh` credentials, including SSH and environment tokens. It is an explicit choice, never a fallback. Named account or review-poster settings conflict with ambient mode. The PR or release still targets the configured GitHub host and selected repository.
- `remote` and `planning_store.remote` are independent and default to `origin`. Each repository selects one remote; cross-repository head and base PRs are not supported. Fetches use their effective fetch URL; pushes check every effective push URL. Preserve safe indexed URL rewrites and verify destinations in the execution environment without retaining inherited authentication overrides. A PR or release refuses mismatched destinations. An omitted Git remote setting preserves the branch's bare pull and classifies its actual upstream; setting any name explicitly pins it, including `origin`.
- The physical code project selected for the version check also supplies the GitHub connection settings. `--project` does not redirect the execution directory, repository, or command arguments. Native dispatch stays in process and retains the caller's bounds and original-destination read-back.
- Ship inspects local work and transport before requiring publication credentials, and only pushes and opens expected PRs. A proven local-only planning store is reported for manual sharing while the expected code PR ships. PR watch, feedback and finish hand the store back for manual sharing and archiving; a missing store PR is not ready evidence and does not replace the committed user task gate. Explicit local finish is unchanged.
- GitHub release proof binds the exact commit read from an invocation-isolated main fetch to the verified destination for tag and release writes. The ordinary backend main refresh is unchanged. A different or unreadable destination never becomes a fallback for read-back.

## Consequences

Users can keep the default identity protection on an Enterprise Server. Opting out requires trusted local Git and `gh` credentials. Existing projects keep github.com, `origin`, and process-scoped fencing when the new keys are absent. One verified destination owns all PR evidence and actions for each role; code and planning roles cannot identify the same GitHub repository.
