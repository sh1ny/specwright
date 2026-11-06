Filesystem access is read-only, so I could not replace `review.md`. Full replacement content follows.

# Review

## Metadata

- **Round:** 8
- **Prior round:** Round 7 — APPROVE.
- **Reviewer:** Codex
- **Reviewed:** Proposal, both delta specs, design, tasks, round-7 review, architecture, named ADRs including 0028, and cited source, particularly `vcs.sh` and `evals/update/test_update_jj_store.py`. Static design review; SDK implementation details accepted as reported evidence. No tests run.

## Findings

### Critical (blocking)

None.

### Moderate

None.

### Suggestions

None.

## Verdict

VERDICT: APPROVE

## Required Changes

None.

CHANGES_APPLIED: n/a

## Rebuttals

- **Raw-path amendment accepted.** D4 now explicitly excludes `statSync` and uses raw-path `Link.existsSync`, `File.existsSync` and `File.lengthSync`. This addresses the reported Linux failure. The accepted difference when `lengthSync` throws remains explicit. A5 and task 2.2 reflect these calls and limit non-UTF-8 checks to Linux, consistent with the reported APFS refusal.
- **Requirement shortening accepted.** The jj-store requirement is 486 characters, below the reported 500-character limit. It preserves the jj branch rule, the download’s own `VERSION`, resolution through the download’s `sw-path.sh`, exclusion of the project’s installed binary, and refusals for no branch, `vcs_script_missing` and `sw_missing`. Task 8.5 retains the C5 check.
- The round-7 walk-order resolution remains intact. Re-review of the complete change found no new design-level finding. Implementation parity, assumption verification and the planned CI gates remain required.