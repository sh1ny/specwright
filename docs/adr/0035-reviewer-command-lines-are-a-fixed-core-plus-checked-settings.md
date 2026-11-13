# 0035. Reviewer command lines are a fixed isolating core plus checked settings

- Status: accepted
- Date: 2026-11-12
- Supersedes: —
- Amends: 0007 (its "Fixed, isolated command lines" point only)

## Context

Reviewer CLIs change their tools and flags independently of Specwright. Fixed command lines required users to edit the shipped script when a default became unsuitable. Unchecked arguments would instead let a settings change remove reviewer isolation. ADR 0007's routing, input construction, fail-closed validation and machine-local review records remain in force.

## Decision

- **A fixed isolating core plus checked settings.** Code builds each route's command line from fixed isolation flags and `review.routes.<route>`. Claude and OMP accept a replacement `tools` list; Codex accepts additive `disable` features; each route accepts checked extra `args`. Neither a setting nor an agent may remove a fixed isolating flag. Agents never assemble reviewer command lines themselves.
- **Refuse weakening settings before execution (C2).** Per-route refused tool and flag lists reject tools that execute code, write files, reach the network, start agents or retain memory, and flags/configuration keys that override isolation or Specwright-owned settings. Newly discovered risky CLI tools join the refused list. Refused values stop before a probe or reviewer starts; receipts record the effective tools, disabled features and extra arguments.
- **Manual proof, not runtime discovery (C5).** `sw` does not discover tool sets by parsing CLI help or feature-list output: those formats are not contracts. Installed versions and changed defaults are checked manually using the evidence standard below.
- **Evidence must demonstrate isolation (C11).** Capture native tool definitions and the complete mounted-tool inventory. Establish that diagnostic-mode captures correspond to the exact reviewer invocation, accounting for mode defaults and settings sources. Model-authored lists and refusals only corroborate those captures; they are not unknown-tool runtime rejections. Child-write trials require an actual denied attempt with every fixed isolation flag retained. An infrastructure failure, missing mounted-tool coverage or an unequated diagnostic mode does not pass. Record exact versions, commands and before/after checkout state; missing proof stops dependent implementation or a changed-default approval.

**Rejected: unchecked free-form arguments,** because copied flags could disable isolation. **Rejected: keeping every parameter fixed,** because CLI changes would keep requiring script edits. **Rejected: runtime tool discovery,** because help and feature lists are unstable. **Rejected: model-only proof or dropping isolation flags for a successful trial,** because neither demonstrates the shipped reviewer configuration.

## Consequences

- Users tune reviewer parameters in settings rather than editing shipped scripts. Fixed isolation remains owned by Specwright.
- Refused lists require maintenance when a CLI adds a risky tool. Manual version checks follow C11, even when a model cannot issue unknown tool names.
- A CLI which rejects a required disabled feature fails closed; Specwright does not retry without that isolation setting.
- Reversal cost: medium. Route settings are a user-facing contract; the evidence procedure is low-cost to change but cannot be silently weakened.
