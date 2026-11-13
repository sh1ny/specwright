# 0036. OMP review tools use a fixed trusted local-target policy

- Status: accepted
- Date: 2026-11-12
- Supersedes: —
- Adds to: 0035 (OMP's fixed trusted policy and target-denial proof)

## Context

A read-only tool name does not imply local-only inputs: OMP's retained read/search tools accept remote resources. Native web-fetch disable does not cover every transport. Native inventories remain necessary evidence under ADR 0035, but cannot establish argument-level target restrictions. The user chose a fixed first-party hook rather than weakening the remote-target ban or adding a cross-platform OS sandbox.

## Decision

- **One fixed first-party exception (C12).** `sw review run` emits its compiled OMP policy source into the private run directory and passes exactly one fixed `--trusted-extension` path while retaining `--no-extensions`. Ambient/user extensions remain disabled. User settings cannot supply policy source or add/replace trusted modules; protected-flag aliases are refused alongside canonical flags. The module runs inside OMP, not in a separate interpreter process.
- **Tool-target and operation boundary.** The hook blocks remote URI/resource and network-root targets, including native compound/encoded/aliased interpretations, while preserving local review inputs. Optional LSP remains outside defaults and accepts only read-only operations with local file targets. The module only hooks calls: it neither registers nor invokes tools. This is not an OS-wide network or filesystem sandbox. Model-provider transport, underlying filesystem mounts and trusted native tool/language-server implementations remain outside this lexical target boundary.
- **Fail closed and identify the policy.** A missing/invalid module fails startup; a callback fault blocks the affected call. Never recover by dropping the module, enabling user extensions or relaxing the overlay. Receipts identify the policy and hash the actual module. Each run owns its module until ordinary work-directory cleanup; ADR 0027's accepted parent-death limitation is unchanged.
- **Prove actual denials.** CLI-version/default checks require paired native tool errors and zero controlled-fixture TCP connections/requests, successful local compatibility cases and module/callback fault controls, with exact arguments and policy digest. Inventory or model-authored refusals alone do not pass. A limited prototype proves only its stated scope; the emitted production module needs its own full-grammar replay. ADR 0035's inventory/mode-correspondence and child-write standards remain in force.

**Rejected: fetch-disable alone,** because other transports remain. **Rejected: allowing other remote resources,** because the user retained their ban. **Rejected: ambient extensions, a separate policy interpreter or an OS-wide sandbox,** because none is the chosen fixed in-process boundary.

## Consequences

- The compiled binary owns the policy; Node is development-only test tooling, not a production dependency.
- Upgrades maintain both known unsafe tool/flag aliases and native input-grammar compatibility. Tests execute the emitted JavaScript rather than a policy mirror.
- Provider traffic and trusted host behavior must not be described as OS-wide network isolation.
- Reversal cost: medium. This is a trusted-code boundary and a user-visible isolation contract. ADR 0035 remains accepted and unchanged.
