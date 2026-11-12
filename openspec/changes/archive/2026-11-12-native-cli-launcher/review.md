# Review

## Metadata

- **Round:** 4
- **Prior round:** Round 3, Codex: APPROVE_WITH_CHANGES; R3 required changes applied. Behaviour-change amendment c4cab29 removed the requirement that committing other dirty files also stop, voiding that verdict.
- **Reviewer:** Codex CLI
- **Reviewed:** Amendment c4cab29; vcs-backends delta and main spec; proposal; design, including D5, D10 and strict-name decisions; vcs-backends test-map rows and group 8 tasks; prior review records; Git, jj and GitButler backends; mapped byte-handling eval. Only tracked files were opened. No tests were run.

This verdict covers only the contents reviewed. Editing proposal, specs or design afterward (other than applying Required Changes, or an edit confined to the proposal's `## Release Notes` section) voids it.

## Findings

### Critical (blocking)

None.

### Moderate

**R4-M1 — The remaining state scenario promises a refusal for a backend explicitly exempted from strict decoding.**

The [amended scenario](F:/Dev/specwright/openspec/changes/native-cli-launcher/specs/vcs-backends/spec.md:39) specifies no backend: any dirty tracked name containing 0xFF must produce `not_utf8` naming `\xFF`.

Git satisfies this through strict decoding of `git status -z`. jj also reads its state path listing strictly, and its commit still calls `jjState` before committing; removing the clause does not require jj to allow unrelated commits.

GitButler differs. Its [state implementation](F:/Dev/specwright/cli/lib/src/vcs/gitbutler_backend.dart:216) reads dirty names from `but status --json`, whose output uses [replacement decoding](F:/Dev/specwright/cli/lib/src/vcs/gitbutler_backend.dart:146). The enclosing requirement expressly preserves that behavior: “`but` output is read as before.” A state call without a branch does not perform the strict Git diff read either. Consequently, the scenario demands a raw-byte diagnostic that this retained path cannot supply. Its mapped eval exercises Git only, leaving the contradiction undetected.

### Suggestions

None.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. Scope “A non-UTF-8 name from a tool stops by name” explicitly to the Git backend, matching its mapped eval and the preserved `but` exception. Clarify that dropping the subsequent-commit clause permits Git’s named-path behavior without requiring other backends to bypass their existing checks.

CHANGES_APPLIED: yes

## Rebuttals

None.