# 0041. A bounded launch reports a newly refused line as a failed helper start

- Status: accepted
- Date: 2026-11-20
- Supersedes: —
- Amends: 0034 (its "Refusals" clause, for bounded launches only)

## Context

ADR 0034 requires a named `unrepresentable` result for a Windows command line over 32,767 UTF-16 units, before anything starts. The `fix-sw-port-gaps` change tightens the Windows checks on what is actually started: the terminating NUL now counts, so a resolved native line of exactly 32,767 visible units is refused; the raw `cmd.exe` line of a batch launch is checked with its interpreter prefix; and a bounded launch checks the serialized helper line (the `sw __exec` helper's own argument list), which carries the target command as arguments.

On a bounded launch, every line these checks refuse used to reach the helper start and fail there. Callers already decide on that failed start: the review base probe reads it as a missing ref, `sw pr reply` exits 127, `sw run --bounded` writes `bounded: cannot start <cmd>`, and the review invocation reports `reviewer_failed`.

## Decision

- **Reported as a failed helper start.** On a bounded launch, a line refused by one of the new checks is still refused before anything starts, but the result is the failed helper start with the fixed diagnostic `cannot start the helper: its command line is too long`, not a named `unrepresentable` refusal. Every bounded caller keeps the decision it makes today for such a line.
- **A review can report `no_base` without Git having run.** This is already true when the helper fails to start; the change does not add a new cause.
- **The one caller that needs the cause** (the GitButler commit) gets it through `lineTooLong`.
- **Everything else keeps ADR 0034's named refusal.** Direct (non-helper) launches, including the raw batch line, and the checks that existed before (the as-given check, a NUL or lone surrogate, the batch payload cap, a resolved native line over 32,767 visible units) keep throwing as today.

**Rejected: the named refusal on every bounded path,** because it changes each caller's result for lines that used to fail at the start, and costs a mapping per caller.

## Consequences

- The text after `cannot start the helper:` can differ by OS; only Windows reaches these checks.
- Reversal cost: a mapping per bounded caller.
