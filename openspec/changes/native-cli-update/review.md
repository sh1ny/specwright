# Review

## Metadata

- **Round:** 3, with a re-check of its Required Changes 1-2
- **Prior round:** Round 2 REVISE: C1 notice before first run; C2 missing chmod; C3 interface check after writes; M1 unbounded bootstrap curl; M2 wrong old-prompt claim; M3 citation. Specs and design were amended; the user requested round 3 after escalation.
- **Reviewer:** Codex, independent review context.
- **Reviewed:** Proposal, both delta specs, design, main specs, architecture, roadmap, relevant ADRs, cited source ranges, build tooling and update fixtures. No files changed.

## Findings

### Critical (blocking)

None.

### Moderate

**M1 — `main` placement still precedes the interface check.**

design.md:109 runs `mise run install-sw`, then probes the **placed** build. D7 makes that task place the binary and notice. This contradicts D11’s guarantee that an interface mismatch stops before placement, and the interface requirement’s “before … any other write” contract.

A `main` checkout reporting another update interface can therefore replace an existing version’s binary and notice before the prompt refuses it. The tagged bootstrap fix closes this path for releases, but leaves it open for `main`.

**M2 — Exact-version shim resolution lacks a workable fixture plan.**

D8 requires the download’s exact-version binary, while D1 and Risks rely on the existing update suite passing through that shim. However, `evals/update/fixtures.py:120` constructs downloads with synthetic versions and places no matching binary. The interruption matrix specifically uses `0.5.0` and `0.6.0` downloads (`evals/update/test_interrupt.py:37`).

Changing `run_update`’s kill variables alone will leave these tests stopping at `sw_missing`, before staging or recovery. The design needs to explain how fixtures obtain matching native binaries while preserving the production resolver checks.

### Suggestions

None.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. Amend D7/D10 and the interface scenarios so the `main` bootstrap checks the newly built binary’s update interface **before placement**. Preserve `mise run install-sw` as the user-facing task. Add a mismatch scenario asserting that an existing binary, notice, pending journal and installed files remain unchanged.
2. Amend the verification plan to describe provisioning isolated, exact-version native binaries for synthetic fixture downloads, including the interruption matrix. Preserve exact-version/interface enforcement and the behavioral assertions; qualify the claim that the suite runs “unchanged” to acknowledge the required fixture adaptations.

## Re-check of Required Changes 1-2

A new Codex run re-checked only these two items against the amended design.md (D1, D7, D8, D10, Risks, decision table) and specs/install-update/spec.md ("A main install builds sw from the clone", scenario "main build reports another interface"). Its result, verbatim:

> Both Required Changes are correctly applied. No new blocking defect was found.
>
> 1. D7/D10 and the `main` mismatch scenario require checking the newly built binary before placement, preserving the existing binary, notice, pending journal and installed files.
> 2. D1/D8 and Risks describe isolated exact-version fixture binaries, cover the interruption matrix, retain version/interface enforcement and behavioral assertions, and qualify “unchanged.”

The re-check run could not write this file (read-only session), so the author restored round 3's text above and recorded the re-check here.

CHANGES_APPLIED: yes

## Rebuttals

- **Round 2 C1, C2:** Accepted as fixed for tagged bootstrap: both hashes precede chmod, quarantine removal and execution.
- **Round 2 C3:** Fixed for tagged bootstrap; the remaining `main` ordering gap is M1 above.
- **Round 2 M1:** Accepted as fixed in the documented bootstrap bounds.
- **Round 2 M2:** Accepted as fixed: Risks now describes the old prompt’s pre-placement `plan` failure.
- **Round 2 M3:** Accepted as fixed: the notice-order citation supports the revised claim.
