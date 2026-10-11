---
name: specwright-debug
description: "Root-cause debugging discipline: reproduce, trace, test hypotheses, fix test-first. Use for unexplained failures, not for the deliberate red step of test-first work. Triggers: a bug report, an issue link, an unexpected test or CI failure, an error or crash, 'debug this', 'why does X happen', 'fix this bug', or specwright-pr watch handing off a CI failure."
metadata:
  version: 0.1.13
---

# Specwright Debug

Find the cause before changing code. One hypothesis, one change, at a time.

## 1. Reproduce
- Read the whole report or thread, not just the title. Get the exact error, inputs and environment.
- Build a named, repeatable check that fails on this bug now (a test, a command, a script). No reproduction means no fix - report what you tried.
- A dirty tree is a suspect: check `git status`; if needed, test with `git stash push -u` and restore.

## 2. Trace
- Work backward from the symptom to where valid state first became invalid, using observed values (logs, prints, debugger), not assumptions.
- Check history: `git log -S`, `git log -p <file>`, related issues and PRs. A recent change near the failure is the first suspect.
- Audit your assumptions: list what you believe about the code path, and verify the ones the failure depends on.

## 3. Hypothesize
- Rank 1-3 hypotheses. Each names the observation that supports it and a prediction you have not checked yet.
- Test the prediction. A confirmed prediction supports the hypothesis; a fix that works when the prediction was wrong is a symptom fix.
- Do not move to a fix until you can state the full causal chain from trigger to symptom. "Somehow X leads to Y" is a gap.

## 4. Fix
- Write or extend a test that fails for this cause. Make the minimal fix. The test passes, the reproduction passes, then run the broader suite.
- On a failed fix, explicitly reject the current hypothesis and go back to step 2. Do not stack fixes.

## Escalate instead of trying again
| Signal | Means |
|---|---|
| 2-3 hypotheses exhausted, or 3 failed fixes | Your model of the system is wrong - re-trace from observations |
| Hypotheses point at different subsystems | A design problem - report it, propose a change |
| Evidence contradicts itself | Wrong mental model or wrong environment |
| Works locally, fails in CI | Environment difference - diff versions, env vars, paths, OS |

In a Specwright change, a cause that invalidates a spec, scenario or design decision is drift: amend the artifact rather than coding around it.

## CI mode (from specwright-pr watch)
- Input: the failing checks and their logs (`pr-snapshot.sh --logs`). Handle all failures in one pass.
- Infrastructure flakes (runner died, network, timeouts unrelated to the change) → re-run, not a code fix.
- Fix only convergent failures - where the right fix is clear and keeps the existing contract. Never weaken, skip or mock away a failing assertion.
- A failure whose fix would reverse a deliberate contract is needs-human: report it with options.
- Do not commit or push: `specwright-pr` watch owns publishing. Report one of: fixed (verified locally; list the changed files), diagnosed-no-fix, flaky-infra, needs-human.
